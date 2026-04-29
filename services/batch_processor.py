"""批量视频处理服务

提供批量解析视频信息和去重功能。
"""

import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)

# Try to import yt_dlp for metadata extraction
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logger.warning("yt_dlp not available, video metadata extraction disabled")


@dataclass
class VideoInfo:
    """视频信息数据类"""
    bilibili_id: str
    url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None and self.bilibili_id is not None


class BatchProcessor:
    """
    批量视频处理器

    支持：
    - 批量解析视频URL
    - 提取视频标题和时长
    - 自动去重
    - 异步处理
    """

    def __init__(self):
        self._processed_ids: Dict[str, VideoInfo] = {}
        self._lock = threading.Lock()

    def add(self, url: str) -> VideoInfo:
        """
        添加一个URL进行处理

        Args:
            url: 视频URL

        Returns:
            VideoInfo对象
        """
        # 提取bilibili_id
        bilibili_id = self._extract_bilibili_id(url)
        if not bilibili_id:
            return VideoInfo(
                bilibili_id=None,
                url=url,
                error="无法识别视频ID"
            )

        # 检查去重
        with self._lock:
            if bilibili_id in self._processed_ids:
                logger.info(f"Duplicate video ID detected: {bilibili_id}")
                return self._processed_ids[bilibili_id]

        # 解析视频信息
        video_info = self._fetch_video_info(url, bilibili_id)

        # 缓存结果
        with self._lock:
            self._processed_ids[bilibili_id] = video_info

        return video_info

    def process_batch(self, urls: List[str]) -> List[VideoInfo]:
        """
        批量处理URL列表

        Args:
            urls: URL列表

        Returns:
            VideoInfo对象列表
        """
        results = []
        for url in urls:
            video_info = self.add(url)
            results.append(video_info)
        return results

    def get_valid(self) -> List[VideoInfo]:
        """获取所有有效视频信息"""
        with self._lock:
            return [v for v in self._processed_ids.values() if v.is_valid]

    def get_errors(self) -> List[VideoInfo]:
        """获取所有错误视频信息"""
        with self._lock:
            return [v for v in self._processed_ids.values() if not v.is_valid]

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._processed_ids.clear()

    @staticmethod
    def _extract_bilibili_id(url: str) -> Optional[str]:
        """
        从URL提取B站视频ID

        支持格式：
        - https://www.bilibili.com/video/BVxxxxxx
        - https://b23.tv/xxxxxx
        - BVxxxxxx
        - av123456
        """
        # BV号
        bv_match = re.search(r'(BV[a-zA-Z0-9]+)', url, re.IGNORECASE)
        if bv_match:
            return bv_match.group(1).upper()

        # AV号
        av_match = re.search(r'av(\d+)', url, re.IGNORECASE)
        if av_match:
            return f"av{av_match.group(1)}"

        # B23短链接 - 需要额外解析
        if 'b23.tv' in url.lower():
            # 短链接需要先解析，这里返回原链接供参考
            return None

        return None

    def _fetch_video_info(self, url: str, bilibili_id: str) -> VideoInfo:
        """
        获取视频信息（标题、时长）

        Args:
            url: 视频URL
            bilibili_id: 视频ID

        Returns:
            VideoInfo对象
        """
        if not YT_DLP_AVAILABLE:
            return VideoInfo(
                bilibili_id=bilibili_id,
                url=url,
                title=None,
                duration=None,
                error=None  # 不算错误，只是没有额外信息
            )

        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)

                return VideoInfo(
                    bilibili_id=bilibili_id,
                    url=url,
                    title=info.get('title'),
                    duration=info.get('duration'),
                    error=None
                )

        except Exception as e:
            logger.warning(f"Failed to fetch video info for {bilibili_id}: {e}")
            return VideoInfo(
                bilibili_id=bilibili_id,
                url=url,
                title=None,
                duration=None,
                error=str(e)
            )


def parse_video_info(url: str) -> VideoInfo:
    """
    便捷函数：解析单个视频信息

    Args:
        url: 视频URL

    Returns:
        VideoInfo对象
    """
    processor = BatchProcessor()
    return processor.add(url)
