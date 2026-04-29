"""B 站视频下载器 - 使用 yt-dlp"""
import yt_dlp
from pathlib import Path
from typing import Optional, Callable, NamedTuple
import logging
import time
import tempfile

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
    retry_config: Optional[RetryConfig] = None,
    cookies: Optional[str] = None,
    use_custom_headers: bool = True
) -> DownloadResult:
    """下载 B 站视频，提取音频并返回结果
    
    Args:
        url: B 站视频 URL
        output_dir: 输出目录
        output_path: 完整输出路径（可选）
        extract_audio: 是否提取音频（默认 True）
        progress_callback: 进度回调函数，接收 {"status": str, "percent": str, ...}
        retry_config: 重试配置
        cookies: B 站 Cookie 字符串（解决 412 错误）
        use_custom_headers: 是否使用自定义 HTTP 请求头（默认 True）
    
    Returns:
        DownloadResult 对象
    """
    if not url or not isinstance(url, str):
        return DownloadResult(
            success=False,
            file_path=None,
            error_message="URL 不能为空"
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
                # 下载完成时，传递标题和时长信息
                if 'filename' in d:
                    info["filename"] = d['filename']
            
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
    
    # 添加自定义 HTTP 请求头（解决 B 站 412 错误）
    if use_custom_headers:
        ydl_opts['http_headers'] = {
            'Referer': 'https://www.bilibili.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        logger.debug("已添加自定义 HTTP 请求头")
    
    # 添加 Cookie 支持（解决 B 站 412 错误）
    cookie_file = None
    if cookies and cookies.strip():
        # 将 Cookie 字符串写入临时文件（yt-dlp 需要 Netscape 格式）
        try:
            cookie_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            # 将 Cookie 字符串转换为 Netscape 格式
            # 支持两种格式：1) "name=value; name2=value2"  2) Netscape 格式（包含\t制表符）
            if '\t' not in cookies and '\n' not in cookies.strip():
                # 格式 1：简单格式 "name=value; name2=value2"，转换为 Netscape 格式
                logger.info("检测到简单格式 Cookie，转换为 Netscape 格式")
                # Netscape 格式文件需要标题行
                cookie_file.write("# Netscape HTTP Cookie File\n")
                cookie_entries = cookies.split(';')
                for entry in cookie_entries:
                    entry = entry.strip()
                    if '=' in entry:
                        name, value = entry.split('=', 1)
                        # Netscape 格式：domain flag path secure expiry name value
                        cookie_file.write(f'.bilibili.com\tTRUE\t/\tFALSE\t0\t{name.strip()}\t{value.strip()}\n')
            else:
                # 格式 2：已经是 Netscape 格式（包含制表符或换行）
                logger.info("检测到 Netscape 格式 Cookie")
                cookie_file.write(cookies)
            cookie_file.close()
            ydl_opts['cookiefile'] = cookie_file.name
            logger.info(f"已添加 Cookie 配置，临时文件：{cookie_file.name}")
            
            # 读取并记录 Cookie 文件内容（用于调试）
            with open(cookie_file.name, 'r', encoding='utf-8') as f:
                cookie_content = f.read()
                logger.debug(f"Cookie 文件内容 (前 500 字符):\n{cookie_content[:500]}")
        except Exception as e:
            logger.warning(f"Cookie 处理失败：{e}", exc_info=True)
    else:
        logger.info("未配置 Cookie，仅使用默认设置")
    
    # 重试循环
    try:
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
                    
                    title = info.get('title', 'video') or 'video'
                    duration = info.get('duration', 0) or 0
                    
                    # 查找生成的音频文件
                    wav_files = list(out_dir.glob("*.wav"))
                    if wav_files:
                        audio_path = max(wav_files, key=lambda f: f.stat().st_mtime)
                        logger.info(f"音频文件已保存：{audio_path}")
                        
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
                        error_message=f"下载失败：{error_msg}"
                    )
        
        return DownloadResult(
            success=False,
            file_path=None,
            error_message="下载失败：达到最大重试次数"
        )
    finally:
        # 清理临时 Cookie 文件
        if cookie_file and cookie_file.name:
            try:
                import os
                os.unlink(cookie_file.name)
                logger.debug(f"已清理临时 Cookie 文件：{cookie_file.name}")
            except Exception as e:
                logger.warning(f"清理临时 Cookie 文件失败：{e}")


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
