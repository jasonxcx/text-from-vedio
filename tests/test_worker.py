"""测试完整处理流程"""
import sys
import os
import logging

# 启用详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread

from app.database import init_db, add_video
from app.worker import ProcessWorker

def test_worker():
    """测试 worker 处理流程"""
    # 初始化数据库
    init_db()
    print("OK: Database initialized\n")
    
    # 添加测试视频
    url = "https://www.bilibili.com/video/BV1DfrdByE2H"
    video_id = add_video(
        bilibili_id="BV1DfrdByE2H",
        title="Test Video",
        url=url,
        duration=0
    )
    print(f"OK: Video added to database, ID: {video_id}\n")
    
    # 创建 worker
    worker = ProcessWorker(
        video_id=video_id,
        url=url,
        title="Test Video",
        bilibili_id="BV1DfrdByE2H"
    )
    
    # 连接信号
    worker.progress.connect(lambda stage, pct, msg: print(f"[Progress] {stage}: {pct}% - {msg}"))
    worker.stage_changed.connect(lambda stage: print(f"[Stage] Enter: {stage}"))
    worker.finished.connect(lambda vid, success, msg: print(f"\n[Finished] ID={vid}, Success={success}, Message={msg}"))
    worker.error.connect(lambda vid, err: print(f"\n[Error] ID={vid}, Error={err}"))
    
    print("Starting processing...\n")
    worker.start()
    
    # 等待完成
    while worker.isRunning():
        QThread.msleep(100)
        app.processEvents()  # 保持UI响应
    
    print("\nOK: Processing completed")

if __name__ == "__main__":
    # 需要 QApplication 因为 worker 使用了 Qt 信号
    app = QApplication(sys.argv)
    test_worker()
