"""
Background task processing worker using QThread.

Handles the complete pipeline: download → transcription → summary.
Runs in background thread to avoid blocking the UI.
"""

import sys
import os
import time
import importlib
import logging
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import QThread, Signal, QObject

# Configure logging
logger = logging.getLogger(__name__)

# Add python-service to path for importing services
sys.path.insert(0, str(Path(__file__).parent.parent / "python-service"))

_downloader = importlib.import_module("services.downloader")  # pyright: ignore[reportMissingImports]
_transcriber = importlib.import_module("services.transcriber")  # pyright: ignore[reportMissingImports]
_summarizer = importlib.import_module("services.summarizer")  # pyright: ignore[reportMissingImports]

download_video = _downloader.download_video
DownloadResult = _downloader.DownloadResult
RetryConfig = _downloader.RetryConfig
transcribe_audio = _transcriber.transcribe_audio
TranscriptionResult = _transcriber.TranscriptionResult
summarize_text = _summarizer.summarize_text

from app.database import (
    update_video_status,
    add_transcripts_batch,
    add_summary,
    delete_transcripts_by_video,
    get_video,
)

from config import config, DOWNLOAD_DIR


class ProcessWorker(QThread):
    """
    Background worker thread for processing Bilibili videos.
    
    Pipeline stages:
    1. Download video/audio using yt-dlp
    2. Transcribe audio using WhisperX
    3. Generate summary using Ollama
    
    Signals:
        progress: Emits (stage, percent, message) for progress updates
        finished: Emits (video_id, success, message) when task completes
        error: Emits (video_id, error_message) on failure
        stage_changed: Emits stage name when entering new stage
    """
    
    # Signals for communication with main thread
    progress = Signal(str, int, str)  # (stage, percent, message)
    finished = Signal(int, bool, str)  # (video_id, success, message)
    error = Signal(int, str)  # (video_id, error_message)
    stage_changed = Signal(str)  # stage name
    status_changed = Signal(int, str)  # (video_id, status) - 用于实时更新表格状态
    
    # Stage constants - 更清晰的状态名称
    STAGE_PENDING = "pending"
    STAGE_DOWNLOAD = "downloading"
    STAGE_TRANSCRIBE = "transcribing"
    STAGE_SUMMARIZE = "summarizing"
    STAGE_COMPLETE = "completed"
    STAGE_FAILED = "failed"
    
    # 阶段中文映射
    STAGE_NAMES = {
        "pending": "等待中",
        "downloading": "下载中",
        "transcribing": "转录中",
        "summarizing": "整理中",
        "completed": "已完成",
        "failed": "失败",
        "cancelled": "已取消"
    }
    
    def __init__(self, video_id: int, url: str, title: str, 
                 bilibili_id: str, max_retries: int = 3):
        """
        Initialize the worker with video information.
        
        Args:
            video_id: Database ID of the video
            url: Bilibili video URL
            title: Video title
            bilibili_id: Bilibili video ID (BV号)
            max_retries: Maximum retry attempts for each stage
        """
        super().__init__()
        self.video_id = video_id
        self.url = url
        self.title = title
        self.bilibili_id = bilibili_id
        self.max_retries = max_retries
        self._is_cancelled = False
        self._audio_path: Optional[str] = None
        
    def run(self):
        """
        Execute the processing pipeline in background thread.
        
        This method is called by QThread.start() and runs in a separate thread.
        """
        logger.info(f"[Worker {self.video_id}] Starting processing pipeline for video {self.bilibili_id}")
        
        try:
            # Stage 1: Download
            logger.info(f"[Worker {self.video_id}] Stage 1: Starting download")
            update_video_status(self.video_id, self.STAGE_DOWNLOAD)
            self.status_changed.emit(self.video_id, self.STAGE_DOWNLOAD)
            self._emit_stage(self.STAGE_DOWNLOAD)
            
            audio_path = self._download_with_retry()
            
            if self._is_cancelled:
                logger.info(f"[Worker {self.video_id}] Task cancelled by user")
                update_video_status(self.video_id, "cancelled")
                self.status_changed.emit(self.video_id, "cancelled")
                self.finished.emit(self.video_id, False, "任务已取消")
                return
            
            if audio_path is None:
                logger.error(f"[Worker {self.video_id}] Download failed after all retries")
                update_video_status(self.video_id, self.STAGE_FAILED)
                self.status_changed.emit(self.video_id, self.STAGE_FAILED)
                self.finished.emit(self.video_id, False, "下载失败")
                return
            
            self._audio_path = audio_path
            logger.info(f"[Worker {self.video_id}] Download complete: {audio_path}")
            
            # Stage 2: Transcribe
            logger.info(f"[Worker {self.video_id}] Stage 2: Starting transcription")
            update_video_status(self.video_id, self.STAGE_TRANSCRIBE)
            self.status_changed.emit(self.video_id, self.STAGE_TRANSCRIBE)
            self._emit_stage(self.STAGE_TRANSCRIBE)
            
            transcription = self._transcribe_with_retry(audio_path)
            
            if self._is_cancelled:
                logger.info(f"[Worker {self.video_id}] Task cancelled during transcription")
                update_video_status(self.video_id, "cancelled")
                self.status_changed.emit(self.video_id, "cancelled")
                self.finished.emit(self.video_id, False, "任务已取消")
                return
            
            if transcription is None:
                logger.error(f"[Worker {self.video_id}] Transcription returned None")
                update_video_status(self.video_id, self.STAGE_FAILED)
                self.status_changed.emit(self.video_id, self.STAGE_FAILED)
                self.error.emit(self.video_id, "转录返回空结果")
                self.finished.emit(self.video_id, False, "转录失败")
                return
            
            if not transcription.success:
                error_msg = transcription.error_message or "转录失败"
                logger.error(f"[Worker {self.video_id}] Transcription failed: {error_msg}")
                update_video_status(self.video_id, self.STAGE_FAILED)
                self.status_changed.emit(self.video_id, self.STAGE_FAILED)
                self.error.emit(self.video_id, error_msg)
                self.finished.emit(self.video_id, False, error_msg)
                return
            
            logger.info(f"[Worker {self.video_id}] Transcription complete: {len(transcription.segments)} segments, {len(transcription.full_text)} chars")
            
            # Check if summary is enabled
            if config.get('summary.enabled', True):
                # Stage 3: Summarize
                logger.info(f"[Worker {self.video_id}] Stage 3: Starting summarization")
                update_video_status(self.video_id, self.STAGE_SUMMARIZE)
                self.status_changed.emit(self.video_id, self.STAGE_SUMMARIZE)
                self._emit_stage(self.STAGE_SUMMARIZE)
                
                summary_result = None
                try:
                    summary_result = self._summarize_with_retry(transcription.full_text)
                    
                    if self._is_cancelled:
                        logger.info(f"[Worker {self.video_id}] Task cancelled during summarization")
                        update_video_status(self.video_id, "cancelled")
                        self.status_changed.emit(self.video_id, "cancelled")
                        self.finished.emit(self.video_id, False, "任务已取消")
                        return
                    
                    if summary_result:
                        logger.info(f"[Worker {self.video_id}] Summary generated successfully")
                    else:
                        logger.warning(f"[Worker {self.video_id}] Summary generation returned None")
                except Exception as e:
                    logger.error(f"[Worker {self.video_id}] Summary generation failed: {str(e)}")
                    # 摘要失败不阻止转录结果保存
                    summary_result = None
                
                # Save results
                if summary_result and isinstance(summary_result, dict):
                    summary_text = summary_result.get("summary", "")
                    self._save_results(transcription, summary_text, summary_result)
                    logger.info(f"[Worker {self.video_id}] Results saved with summary")
                else:
                    # 摘要失败，只保存转录
                    self._save_results(transcription, "", None)
                    logger.info(f"[Worker {self.video_id}] Results saved without summary")
            else:
                # Summary disabled, save only transcription
                logger.info(f"[Worker {self.video_id}] Summary disabled, saving transcription only")
                self._save_results(transcription, "", None)
                logger.info(f"[Worker {self.video_id}] Results saved successfully")
            
            # Mark as complete
            update_video_status(self.video_id, self.STAGE_COMPLETE)
            self.status_changed.emit(self.video_id, self.STAGE_COMPLETE)
            self._emit_stage(self.STAGE_COMPLETE)
            self.finished.emit(self.video_id, True, "处理完成")
            logger.info(f"[Worker {self.video_id}] Pipeline completed successfully")
            
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            logger.exception(f"[Worker {self.video_id}] Unexpected error: {error_msg}")
            update_video_status(self.video_id, self.STAGE_FAILED)
            self.status_changed.emit(self.video_id, self.STAGE_FAILED)
            self.error.emit(self.video_id, error_msg)
            self.finished.emit(self.video_id, False, error_msg)
            
    def cancel(self):
        """Request the worker to stop processing."""
        self._is_cancelled = True
        
    def _emit_stage(self, stage: str):
        """Emit stage change signal and update progress to 0."""
        self.stage_changed.emit(stage)
        stage_name = self.STAGE_NAMES.get(stage, stage)
        self.progress.emit(stage, 0, f"开始{stage_name}...")
        
    def _stage_name(self, stage: str) -> str:
        """Get Chinese name for a stage."""
        return self.STAGE_NAMES.get(stage, stage)
        
    def _download_with_retry(self) -> Optional[str]:
        """
        Download video/audio with retry logic.
        
        Returns:
            Path to downloaded audio file, or None on failure
        """
        output_path = str(DOWNLOAD_DIR / self.bilibili_id)
        retry_config = RetryConfig(max_retries=self.max_retries)
        
        def progress_callback(info: dict):
            """Handle download progress updates."""
            if self._is_cancelled:
                return
                
            status = info.get("status", "")
            if status == "downloading":
                # Parse percentage from string like "50.5%"
                percent_str = info.get("percent", "0%")
                try:
                    percent = float(percent_str.replace("%", "").strip())
                except ValueError:
                    percent = 0
                self.progress.emit(self.STAGE_DOWNLOAD, int(percent), 
                                   f"下载中... {percent_str}")
            elif status == "finished":
                self.progress.emit(self.STAGE_DOWNLOAD, 100, "下载完成")
            elif status == "retry":
                attempt = info.get("attempt", 1)
                self.progress.emit(self.STAGE_DOWNLOAD, 0, 
                                   f"重试第{attempt}次...")
            elif status == "info_extracted":
                # Update video title and duration if available
                title = info.get("title", self.title)
                duration = info.get("duration", 0)
                from app.database import update_video
                update_video(self.video_id, title=title, duration=duration)
                
        for attempt in range(self.max_retries):
            if self._is_cancelled:
                return None
                
            try:
                result = download_video(
                    url=self.url,
                    output_path=output_path,
                    extract_audio=True,
                    progress_callback=progress_callback,
                    retry_config=retry_config,
                )
                
                if result.success:
                    self.progress.emit(self.STAGE_DOWNLOAD, 100, "下载完成")
                    return result.file_path
                    
                # If failed but not cancelled, retry
                if attempt < self.max_retries - 1:
                    delay = retry_config.initial_delay * (retry_config.backoff_factor ** attempt)
                    self.progress.emit(self.STAGE_DOWNLOAD, 0, 
                                       f"下载失败，{delay}秒后重试...")
                    time.sleep(delay)
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    self.progress.emit(self.STAGE_DOWNLOAD, 0, 
                                       f"下载异常: {str(e)}，重试中...")
                    time.sleep(retry_config.initial_delay)
                else:
                    self.error.emit(self.video_id, f"下载失败: {str(e)}")
                    return None
                    
        self.error.emit(self.video_id, "下载失败，已达最大重试次数")
        return None
        
    def _transcribe_with_retry(self, audio_path: str) -> Optional[TranscriptionResult]:
        """
        Transcribe audio with retry logic.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            TranscriptionResult, or None on failure
        """
        for attempt in range(self.max_retries):
            if self._is_cancelled:
                return None
                
            try:
                # Emit progress updates during transcription
                self.progress.emit(self.STAGE_TRANSCRIBE, 10, f"加载模型 {config.get('transcription.model')} (使用 {config.get('transcription.device')})...")
                
                result = transcribe_audio(
                    audio_path=audio_path,
                    model_name=config.get('transcription.model'),
                    device=config.get('transcription.device'),
                    compute_type=config.get('transcription.compute_type'),
                    language=config.get('transcription.language') if config.get('transcription.language') != 'auto' else None,
                )
                
                if result.success:
                    self.progress.emit(self.STAGE_TRANSCRIBE, 100, 
                                       f"转录完成，共{len(result.segments)}个片段")
                    return result
                    
                # Retry on failure
                if attempt < self.max_retries - 1:
                    self.progress.emit(self.STAGE_TRANSCRIBE, 0, 
                                       f"转录失败，重试中...")
                    time.sleep(2)
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    self.progress.emit(self.STAGE_TRANSCRIBE, 0, 
                                       f"转录异常: {str(e)}，重试中...")
                    time.sleep(2)
                else:
                    self.error.emit(self.video_id, f"转录失败: {str(e)}")
                    return None
                    
        self.error.emit(self.video_id, "转录失败，已达最大重试次数")
        return None
        
    def _summarize_with_retry(self, text: str):
        """
        Generate summary with retry logic.
        
        Args:
            text: Full transcription text
            
        Returns:
            Summary result dict, or None on failure
        """
        if not text or len(text.strip()) == 0:
            logger.warning(f"[Worker {self.video_id}] No text content to summarize")
            self.progress.emit(self.STAGE_SUMMARIZE, 100, "无文本内容，跳过摘要")
            return {"summary": "无转录内容", "key_points": [], "topics": []}
            
        for attempt in range(self.max_retries):
            if self._is_cancelled:
                logger.info(f"[Worker {self.video_id}] Summarization cancelled")
                return None
                
            try:
                logger.info(f"[Worker {self.video_id}] Summarization attempt {attempt + 1}/{self.max_retries}")
                self.progress.emit(self.STAGE_SUMMARIZE, 20, f"生成摘要... (尝试{attempt + 1}/{self.max_retries})")
                
                summary = summarize_text(
                    text=text,
                    max_length=config.get('summary.max_length', 500),
                )
                
                # Validate result
                if isinstance(summary, dict):
                    summary_text = summary.get("summary", "")
                    if not summary_text:
                        logger.warning(f"[Worker {self.video_id}] Summary result has empty text")
                        raise ValueError("摘要结果为空")
                    logger.info(f"[Worker {self.video_id}] Summary generated successfully: {len(summary_text)} chars")
                else:
                    logger.warning(f"[Worker {self.video_id}] Summary returned non-dict type: {type(summary)}")
                    # Convert to dict format
                    summary = {"summary": str(summary), "key_points": [], "topics": []}
                
                self.progress.emit(self.STAGE_SUMMARIZE, 100, "摘要生成完成")
                return summary
                
            except Exception as e:
                logger.error(f"[Worker {self.video_id}] Summarization attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    self.progress.emit(self.STAGE_SUMMARIZE, 0, 
                                       f"摘要生成失败: {str(e)}，重试中...")
                    time.sleep(2)
                else:
                    self.error.emit(self.video_id, f"摘要生成失败: {str(e)}")
                    return None
                    
        logger.error(f"[Worker {self.video_id}] Summarization failed after {self.max_retries} attempts")
        self.error.emit(self.video_id, "摘要生成失败，已达最大重试次数")
        return None
        
    def _save_results(self, transcription: TranscriptionResult, summary_text: str, summary_result = None):
        """
        Save transcription and summary to database.
        
        Args:
            transcription: Transcription result with segments
            summary_text: Summary text string
            summary_result: Optional full summary result dict with key_points
        """
        """
        Save transcription and summary to database.
        
        Args:
            transcription: Transcription result with segments
            summary_text: Summary text string
            summary_result: Optional full summary result dict with key_points
        """
        # Clear existing transcripts first (for retry scenarios)
        delete_transcripts_by_video(self.video_id)
        
        # Save transcript segments
        transcripts = []
        for i, segment in enumerate(transcription.segments):
            transcripts.append({
                "video_id": self.video_id,
                "start_seconds": segment.start,
                "end_seconds": segment.end,
                "text": segment.text,
                "order_index": i,
            })
            
        if transcripts:
            add_transcripts_batch(transcripts)
            
        # Save summary
        # Extract key points from summary result or parse from text
        if summary_result and isinstance(summary_result, dict):
            key_points = summary_result.get("key_points", [])
        else:
            key_points = self._extract_key_points(summary_text)
        add_summary(self.video_id, summary_text, key_points)
        
    def _extract_key_points(self, summary: str) -> list:
        """
        Extract key points from summary text.
        
        Simple heuristic: split by numbered points or bullet points.
        
        Args:
            summary: Summary text
            
        Returns:
            List of key points
        """
        import re
        normalized = summary.replace("\n", " ")
        
        # Try to find numbered points (1. 2. 3. etc)
        numbered = re.findall(r'\d+[.、]\s*([^\d.、]+?)(?=\s*\d+[.、]|$)', normalized)
        if numbered:
            return [point.strip() for point in numbered if point.strip()]
            
        # Try bullet points
        bullets = re.findall(r'[•·]\s*([^\n]+)', normalized)
        if bullets:
            return [point.strip() for point in bullets if point.strip()]
            
        # Split by sentences and take first 3 as key points
        sentences = re.split(r'[。！？\n]', normalized)
        key_points = [s.strip() for s in sentences if s.strip()][:3]
        
        return key_points if key_points else [summary[:100]]


class WorkerManager(QObject):
    """
    Manager for handling multiple worker threads.
    
    Provides centralized management of background workers,
    including cancellation, status tracking, and cleanup.
    """
    
    worker_finished = Signal(int, bool, str)  # (video_id, success, message)
    all_workers_finished = Signal()
    
    def __init__(self):
        super().__init__()
        self._workers: dict[int, ProcessWorker] = {}
        self._active_count = 0
        
    def start_worker(self, video_id: int, url: str, title: str, 
                     bilibili_id: str) -> ProcessWorker:
        """
        Start a new worker for processing a video.
        
        Args:
            video_id: Database ID of the video
            url: Bilibili video URL
            title: Video title
            bilibili_id: Bilibili video ID
            
        Returns:
            The created worker instance
        """
        # Cancel existing worker for same video if exists
        if video_id in self._workers:
            self.cancel_worker(video_id)
            
        worker = ProcessWorker(video_id, url, title, bilibili_id)
        
        # Connect signals
        worker.finished.connect(self._on_worker_finished)
        
        self._workers[video_id] = worker
        self._active_count += 1
        worker.start()
        
        return worker
        
    def cancel_worker(self, video_id: int):
        """
        Cancel a specific worker.
        
        Args:
            video_id: ID of the video whose worker should be cancelled
        """
        if video_id in self._workers:
            worker = self._workers[video_id]
            worker.cancel()
            worker.wait(1000)  # Wait up to 1 second for cleanup
            worker.quit()
            del self._workers[video_id]
            self._active_count -= 1
            
    def cancel_all(self):
        """Cancel all active workers."""
        for video_id in list(self._workers.keys()):
            self.cancel_worker(video_id)
            
    def get_worker(self, video_id: int) -> Optional[ProcessWorker]:
        """
        Get the worker for a specific video.
        
        Args:
            video_id: Video ID
            
        Returns:
            Worker instance or None if not found
        """
        return self._workers.get(video_id)
        
    def has_active_workers(self) -> bool:
        """Check if there are any active workers."""
        return self._active_count > 0
        
    def _on_worker_finished(self, video_id: int, success: bool, message: str):
        """Handle worker completion."""
        self.worker_finished.emit(video_id, success, message)
        
        if video_id in self._workers:
            worker = self._workers[video_id]
            worker.deleteLater()
            del self._workers[video_id]
            self._active_count -= 1
            
        if self._active_count == 0:
            self.all_workers_finished.emit()
