"""Test transcription directly"""
import sys
sys.path.insert(0, 'python-service')
from services.transcriber import transcribe_audio
from config import WHISPER_MODEL, DEVICE
import os

# 找一个下载的音频文件
downloads_dir = 'downloads'
audio_files = []
for root, dirs, files in os.walk(downloads_dir):
    for f in files:
        if f.endswith(('.wav', '.mp3', '.m4a')):
            audio_files.append(os.path.join(root, f))

if not audio_files:
    print(f'No audio files found in {downloads_dir}')
else:
    audio_path = audio_files[0]
    print(f'Testing transcription with: {audio_path}')
    print(f'Model: {WHISPER_MODEL}, Device: {DEVICE}')
    
    def progress_cb(percent, msg):
        print(f'  [{percent}%] {msg}')
    
    result = transcribe_audio(
        audio_path=audio_path,
        model_name=WHISPER_MODEL,
        device=DEVICE,
        progress_callback=progress_cb
    )
    
    print(f'\nResult:')
    print(f'  Success: {result.success}')
    print(f'  Segments count: {len(result.segments)}')
    print(f'  Full text length: {len(result.full_text)}')
    print(f'  Language: {result.language}')
    if result.error_message:
        print(f'  Error: {result.error_message}')
    if result.segments:
        print(f'\n  First segment: {result.segments[0].text[:100]}...')
