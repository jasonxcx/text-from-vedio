"""语音转文字 - 使用faster-whisper"""
import os

# 强制使用离线模式，避免重复请求huggingface
os.environ["HF_HUB_OFFLINE"] = "1"

from faster_whisper import WhisperModel
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, NamedTuple
import logging

logger = logging.getLogger(__name__)


class TranscriptionSegment(NamedTuple):
    """转录段落"""
    start: float
    end: float
    text: str
    words: List[Dict[str, Any]]


class TranscriptionResult(NamedTuple):
    """转录结果"""
    success: bool
    segments: List[TranscriptionSegment]
    full_text: str
    language: str
    language_probability: float
    error_message: Optional[str] = None


def transcribe_audio(
    audio_path: str,
    model_size: str = "large-v3",
    model_name: Optional[str] = None,  # 兼容旧调用，优先使用此参数
    device: str = "auto",
    compute_type: str = "auto",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> TranscriptionResult:
    """转录音频，返回带时间戳的文本
    
    Args:
        audio_path: 音频文件路径
        model_size: 模型大小，可选: "tiny", "base", "small", "medium", "large-v2", "large-v3"
        model_name: 模型名称（优先使用，兼容旧调用）
        device: 设备类型，可选: "auto", "cuda", "cpu"
        compute_type: 计算类型，可选: "auto", "int8", "float16", "float32"，默认自动选择
        language: 音频语言，如 "zh", "en"，None为自动检测
        progress_callback: 进度回调函数，接收 (进度百分比, 状态消息)
    
    Returns:
        TranscriptionResult对象，包含success, segments, full_text等字段
    """
    # 优先使用model_name参数
    actual_model = model_name if model_name else model_size
    
    # 根据设备自动选择最佳计算类型
    if compute_type == "auto":
        if device == "cuda":
            compute_type = "float16"  # CUDA使用float16，更快
        else:
            compute_type = "float32"  # CPU使用float32，更稳定
    
    # 验证文件存在
    audio_file = Path(audio_path)
    if not audio_file.exists():
        error_msg = f"音频文件不存在: {audio_path}"
        logger.error(error_msg)
        return TranscriptionResult(
            success=False,
            segments=[],
            full_text="",
            language="",
            language_probability=0.0,
            error_message=error_msg
        )
    
    if progress_callback:
        progress_callback(0, f"加载模型 {actual_model} ({device}/{compute_type})...")
    
    try:
        # 初始化模型
        logger.info(f"Loading WhisperModel: model={actual_model}, device={device}, compute_type={compute_type}")
        
        # 首先尝试离线加载（使用本地缓存）
        try:
            model = WhisperModel(
                actual_model,
                device=device,
                compute_type=compute_type,
                download_mode="reuse_if_exists"
            )
            logger.info(f"Model loaded from local cache: {actual_model}")
        except Exception as e:
            # 如果离线加载失败，临时允许在线下载
            logger.warning(f"Offline load failed: {str(e)}, trying online download...")
            os.environ["HF_HUB_OFFLINE"] = "0"
            
            model = WhisperModel(
                actual_model,
                device=device,
                compute_type=compute_type
            )
            
            # 下载成功后恢复离线模式
            os.environ["HF_HUB_OFFLINE"] = "1"
            logger.info(f"Model downloaded successfully: {actual_model}")
        
        if progress_callback:
            progress_callback(10, "模型加载完成，开始转录...")
        
        # 转录音频
        # word_timestamps=True 启用词级时间戳
        segments_generator, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,  # 启用词级时间戳
            vad_filter=True,  # 使用VAD过滤静音
            vad_parameters={
                "min_silence_duration_ms": 500,  # 最小静音时长
                "speech_pad_ms": 200,  # 语音填充
            }
        )
        
        # 收集所有分段
        segments = []
        total_duration = info.duration if info.duration else 1
        
        for i, segment in enumerate(segments_generator):
            segment_data = {
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text.strip(),
                "words": []
            }
            
            # 添加词级时间戳
            if segment.words:
                segment_data["words"] = [
                    {
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "word": word.word,
                        "probability": round(word.probability, 3)
                    }
                    for word in segment.words
                ]
            
            segments.append(segment_data)
            
            # 更新进度
            if progress_callback:
                # 基于当前分段结束时间估算进度
                progress = 10 + (segment.end / total_duration) * 85
                progress_callback(min(progress, 95), f"转录中: {len(segments)} 个分段...")
        
        # Convert segment dicts to TranscriptionSegment objects
        transcription_segments = []
        for seg in segments:
            transcription_segments.append(
                TranscriptionSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                    words=seg.get("words", [])  # 使用get避免KeyError
                )
            )
        
        # Build full text from segments
        full_text = " ".join(seg["text"] for seg in segments)
        
        result = TranscriptionResult(
            success=True,
            segments=transcription_segments,
            full_text=full_text,
            language=info.language,
            language_probability=round(info.language_probability, 3),
            error_message=None
        )
        
        if progress_callback:
            progress_callback(100, f"转录完成，共 {len(segments)} 个分段")
        
        logger.info(f"转录完成: {len(segments)} 个分段, 语言: {info.language}")
        return result
        
    except Exception as e:
        error_msg = f"转录失败: {str(e)}"
        logger.error(error_msg)
        return TranscriptionResult(
            success=False,
            segments=[],
            full_text="",
            language="",
            language_probability=0.0,
            error_message=error_msg
        )


def transcribe_long_audio(
    audio_path: str,
    model_size: str = "large-v3",
    chunk_duration: int = 600,  # 10分钟一个分段
    device: str = "auto",
    compute_type: str = "auto",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> TranscriptionResult:
    """分段处理长音频
    
    对于超长音频（如超过1小时），分段处理可以：
    1. 减少内存占用
    2. 提供更细粒度的进度反馈
    3. 避免单次处理超时
    
    Args:
        audio_path: 音频文件路径
        model_size: 模型大小
        chunk_duration: 每段时长（秒），默认600秒（10分钟）
        device: 设备类型
        compute_type: 计算类型
        language: 音频语言
        progress_callback: 进度回调
    
    Returns:
        与 transcribe_audio 相同格式的结果
    """
    # 验证文件存在
    audio_file = Path(audio_path)
    if not audio_file.exists():
        error_msg = f"音频文件不存在: {audio_path}"
        logger.error(error_msg)
        return TranscriptionResult(
            success=False,
            segments=[],
            full_text="",
            language="",
            language_probability=0.0,
            error_message=error_msg
        )
    
    try:
        import librosa
    except ImportError:
        # 如果没有 librosa，回退到普通转录
        logger.warning("librosa 未安装，使用普通转录模式")
        return transcribe_audio(
            audio_path=audio_path,
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            language=language,
            progress_callback=progress_callback
        )
    
    if progress_callback:
        progress_callback(0, f"加载模型 {model_size}...")
    
    try:
        # 获取音频时长
        duration = librosa.get_duration(path=audio_path)
        
        # 如果音频较短，直接使用普通转录
        if duration <= chunk_duration:
            return transcribe_audio(
                audio_path=audio_path,
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                language=language,
                progress_callback=progress_callback
            )
        
        # 初始化模型
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )
        
        if progress_callback:
            progress_callback(5, "模型加载完成，开始分段转录...")
        
        # 计算分段数
        num_chunks = int((duration + chunk_duration - 1) // chunk_duration)
        all_segments = []
        detected_language = None
        language_probability = 0
        
        for chunk_idx in range(num_chunks):
            start_time = chunk_idx * chunk_duration
            end_time = min((chunk_idx + 1) * chunk_duration, duration)
            
            if progress_callback:
                chunk_progress = 5 + (chunk_idx / num_chunks) * 90
                progress_callback(
                    chunk_progress,
                    f"处理分段 {chunk_idx + 1}/{num_chunks} ({start_time:.0f}s - {end_time:.0f}s)"
                )
            
            # 转录当前分段
            segments_generator, info = model.transcribe(
                audio_path,
                language=language,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 200,
                }
            )
            
            # 收集分段结果
            for segment in segments_generator:
                # 调整时间戳（加上分段偏移）
                segment_data = {
                    "start": round(segment.start + start_time, 3),
                    "end": round(segment.end + start_time, 3),
                    "text": segment.text.strip(),
                    "words": []
                }
                
                if segment.words:
                    segment_data["words"] = [
                        {
                            "start": round(word.start + start_time, 3),
                            "end": round(word.end + start_time, 3),
                            "word": word.word,
                            "probability": round(word.probability, 3)
                        }
                        for word in segment.words
                    ]
                
                all_segments.append(segment_data)
            
            # 记录检测到的语言
            if detected_language is None:
                detected_language = info.language
                language_probability = info.language_probability
        
        # Convert segment dicts to TranscriptionSegment objects
        transcription_segments = [
            TranscriptionSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
                words=seg["words"]
            )
            for seg in all_segments
        ]
        
        # Build full text from segments
        full_text = " ".join(seg["text"] for seg in all_segments)
        
        result = TranscriptionResult(
            success=True,
            segments=transcription_segments,
            full_text=full_text,
            language=detected_language or "",
            language_probability=round(language_probability, 3) if language_probability else 0.0,
            error_message=None
        )
        
        if progress_callback:
            progress_callback(100, f"转录完成，共 {len(all_segments)} 个分段")
        
        logger.info(f"分段转录完成: {len(all_segments)} 个分段, 语言: {detected_language}")
        return result
        
    except Exception as e:
        error_msg = f"分段转录失败: {str(e)}"
        logger.error(error_msg)
        return TranscriptionResult(
            success=False,
            segments=[],
            full_text="",
            language="",
            language_probability=0.0,
            error_message=error_msg
        )


def get_transcript_text(result: TranscriptionResult) -> str:
    """从转录结果中提取纯文本
    
    Args:
        result: transcribe_audio 返回的结果
    
    Returns:
        合并后的纯文本
    """
    return result.full_text


def get_transcript_with_timestamps(result: TranscriptionResult) -> str:
    """生成带时间戳的文本
    
    Args:
        result: transcribe_audio 返回的结果
    
    Returns:
        带时间戳的文本，格式: [00:00:00] 文本内容
    """
    lines = []
    for seg in result.segments:
        start_time = _format_timestamp(seg.start)
        lines.append(f"[{start_time}] {seg.text}")
    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """将秒数转换为时间戳格式 HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"