"""Test full worker flow"""
import sys
sys.path.insert(0, 'python-service')
import glob
from app.database import init_db, add_video, get_video_with_details, delete_video
from app.worker import ProcessWorker
from PySide6.QtCore import QCoreApplication

# 需要Qt应用
app = QCoreApplication(sys.argv)

init_db()

# 找一个已存在的视频ID
import sqlite3
conn = sqlite3.connect('bilibili_asr.db')
cursor = conn.cursor()
cursor.execute('SELECT id, bilibili_id, title, url FROM videos WHERE status = \"completed\" ORDER BY id DESC LIMIT 1')
row = cursor.fetchone()
conn.close()

if row:
    video_id, bilibili_id, title, url = row
    print(f'Testing with video ID: {video_id}')
    
    # 删除旧的转录和摘要
    from app.database import delete_transcripts_by_video, delete_summary
    delete_transcripts_by_video(video_id)
    delete_summary(video_id)
    
    # 创建worker
    worker = ProcessWorker(video_id, url, title, bilibili_id)
    
    # 连接信号来观察流程
    def on_progress(stage, percent, msg):
        print(f'  [{stage}] {percent}%: {msg}')
    
    def on_finished(vid, success, msg):
        print(f'\nFinished: video={vid}, success={success}, msg={msg}')
        
        # 检查结果
        video = get_video_with_details(vid)
        print(f'  Transcripts: {len(video.get("transcripts", []))}')
        print(f'  Summary: {video.get("summary")}')
        
        app.quit()
    
    def on_error(vid, msg):
        print(f'\nError: video={vid}, msg={msg}')
    
    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    
    print('Starting worker...')
    worker.start()
    
    # 运行事件循环
    sys.exit(app.exec())
else:
    print('No completed videos found')
