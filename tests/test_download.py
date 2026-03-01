"""测试视频处理流程"""
import sys
import logging

# 启用详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from services.downloader import download_video
from app.database import init_db

def test_download():
    """测试下载功能"""
    url = input("输入B站视频URL: ").strip()
    if not url:
        url = "https://www.bilibili.com/video/BV1xx411c7mD"
    
    print(f"\n开始下载: {url}")
    print("请稍候，这取决于视频大小和网络速度...\n")
    
    try:
        def progress(percent, msg):
            print(f"[{percent:5.1f}%] {msg}")
        
        audio_path = download_video(url, progress_callback=progress)
        print(f"\n✓ 下载成功: {audio_path}")
        
    except Exception as e:
        print(f"\n✗ 下载失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_download()
