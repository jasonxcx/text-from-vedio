"""Test worker save results"""
import sys
import glob
import os
sys.path.insert(0, 'python-service')
from app.database import init_db, add_video, get_video_with_details, delete_transcripts_by_video, add_transcripts_batch, add_summary
from services.transcriber import transcribe_audio
from config import WHISPER_MODEL, DEVICE

init_db()

# 创建一个测试视频
video_id = add_video("test_bv", "Test Video", "https://test.com")
print(f'Created test video ID: {video_id}')

# 找一个音频文件
wav_files = glob.glob('downloads/*.wav')
if not wav_files:
    print('No wav files found')
    sys.exit(1)

audio_path = wav_files[0]
print(f'Found audio: {os.path.basename(audio_path)}')
result = transcribe_audio(
    audio_path=audio_path,
    model_name=WHISPER_MODEL,
    device=DEVICE,
)

print(f'Result: success={result.success}, segments={len(result.segments)}')

if result.success and result.segments:
    # 模拟worker的保存逻辑
    print('\nSaving to database...')
    
    # Clear existing
    delete_transcripts_by_video(video_id)
    
    # Save transcripts
    transcripts = []
    for i, segment in enumerate(result.segments):
        transcripts.append({
            "video_id": video_id,
            "start_seconds": segment.start,
            "end_seconds": segment.end,
            "text": segment.text,
            "order_index": i,
        })
    
    print(f'Prepared {len(transcripts)} transcripts')
    
    if transcripts:
        add_transcripts_batch(transcripts)
        print('Transcripts saved!')
    
    # Save summary
    add_summary(video_id, "Test summary content", ["point 1", "point 2"])
    print('Summary saved!')
    
    # Verify
    video = get_video_with_details(video_id)
    print(f'\nVerification:')
    print(f'  Transcripts in DB: {len(video.get("transcripts", []))}')
    print(f'  Summary in DB: {video.get("summary")}')
