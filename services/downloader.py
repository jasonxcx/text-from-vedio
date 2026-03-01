"""B站视频下载器 - 使用yt-dlp"""
import yt_dlp
from pathlib import Path
from typing import Optional, Callable, NamedTuple
import logging
import time

logger = logging.getLogger(__name__)


class RetryConfig(NamedTuple):
    """重试配置"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0


class DownloadResult(NamedTuple):
    """下载结果"""
    success: bool
    file_path: Optional[str]
    error_message: Optional[str] = None
    title: str = ""
    duration: int = 0


def download_video(
    url: str,
    output_dir: str = "downloads",
    output_path: str = None,
    extract_audio: bool = True,
    progress_callback: Optional[Callable[[dict], None]] = None,
    retry_config: Optional[RetryConfig] = None
) -> DownloadResult:
    """下载B站视频，提取音频并返回结果
    
    Args:
        url: B站视频URL
        output_dir: 输出目录
        output_path: 完整输出路径（可选）
        extract_audio: 是否提取音频（默认True）
        progress_callback: 进度回调函数，接收 {"status": str, "percent": str, ...}
        retry_config: 重试配置
    
    Returns:
        DownloadResult 对象
    """
    if not url or not isinstance(url, str):
        return DownloadResult(
            success=False,
            file_path=None,
            error_message="URL不能为空"
        )
    
    # 确定输出目录
    if output_path:
        out_dir = Path(output_path).parent
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 默认重试配置
    retry_cfg = retry_config or RetryConfig()
    
    # 定义进度钩子
    def progress_hook(d: dict) -> None:
        if progress_callback:
            status = d.get('status', '')
            info = {"status": status}
            
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = (downloaded / total) * 100
                    info["percent"] = f"{percent:.1f}%"
                else:
                    info["percent"] = "0%"
            elif status == 'finished':
                info["percent"] = "100%"
            
            progress_callback(info)
    
    # yt-dlp 配置
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(out_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }] if extract_audio else [],
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {
            'bilibili': {
                'prefer_multi_flv': ['false'],
            }
        },
    }
    
    # 重试循环
    for attempt in range(retry_cfg.max_retries):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 获取视频信息并下载
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    if attempt < retry_cfg.max_retries - 1:
                        continue
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        error_message="无法获取视频信息"
                    )
                
                title = info.get('title', 'video')
                duration = info.get('duration', 0)
                
                # 查找生成的音频文件
                wav_files = list(out_dir.glob("*.wav"))
                if wav_files:
                    audio_path = max(wav_files, key=lambda f: f.stat().st_mtime)
                    logger.info(f"音频文件已保存: {audio_path}")
                    
                    if progress_callback:
                        progress_callback({
                            "status": "finished",
                            "percent": "100%",
                            "title": title,
                            "duration": duration
                        })
                    
                    return DownloadResult(
                        success=True,
                        file_path=str(audio_path),
                        title=title,
                        duration=duration
                    )
                else:
                    if attempt < retry_cfg.max_retries - 1:
                        continue
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        error_message="音频文件未生成",
                        title=title,
                        duration=duration
                    )
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"下载失败 (尝试 {attempt+1}/{retry_cfg.max_retries}): {error_msg}")
            
            if attempt < retry_cfg.max_retries - 1:
                delay = min(
                    retry_cfg.initial_delay * (retry_cfg.backoff_factor ** attempt),
                    retry_cfg.max_delay
                )
                if progress_callback:
                    progress_callback({
                        "status": "retry",
                        "attempt": attempt + 1,
                        "max_attempts": retry_cfg.max_retries
                    })
                time.sleep(delay)
            else:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    error_message=f"下载失败: {error_msg}"
                )
    
    return DownloadResult(
        success=False,
        file_path=None,
        error_message="下载失败：达到最大重试次数"
    )


def get_video_info(url: str) -> dict:
    """获取视频信息（不下载）"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', ''),
            'duration': info.get('duration', 0),
            'description': info.get('description', ''),
            'uploader': info.get('uploader', ''),
            'view_count': info.get('view_count', 0),
        }
