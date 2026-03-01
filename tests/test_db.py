"""Test script to check database contents"""
import sys
import sqlite3
sys.path.insert(0, 'python-service')
from app.database import get_video_with_details

# 查找最新完成的视频
conn = sqlite3.connect('bilibili_asr.db')
cursor = conn.cursor()
cursor.execute('SELECT id FROM videos ORDER BY id DESC LIMIT 1')
row = cursor.fetchone()
conn.close()

if row:
    video_id = row[0]
    video = get_video_with_details(video_id)
    print(f'Video ID: {video_id}')
    print(f'Title: {video["title"]}')
    print(f'Status: {video["status"]}')
    print(f'Transcripts count: {len(video.get("transcripts", []))}')
    print(f'Summary: {video.get("summary")}')
    if video.get('transcripts'):
        print(f'\nFirst 3 transcripts:')
        for t in video['transcripts'][:3]:
            print(f"  [{t['start_seconds']:.1f}s - {t['end_seconds']:.1f}s] {t['text'][:50]}...")
else:
    print('No videos found')
