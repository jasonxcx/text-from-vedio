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
    chunk_duration: int = 600,  # 已废弃，保留参数仅用于API兼容
    device: str = "auto",
    compute_type: str = "auto",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> TranscriptionResult:
    """使用语义分段处理长音频
    
    不再强制按固定时长分段，而是依赖faster-whisper的VAD和自然语义分段机制。
    对于超长音频(>30分钟)，仅在内存压力下进行智能分段。
    
    Args:
        audio_path: 音频文件路径
        model_size: 模型大小
        chunk_duration: 已废弃，保留参数仅用于API兼容
        device: 设备类型
        compute_type: 计算类型
        language: 音频语言
        progress_callback: 进度回调函数
    
    Returns:
        TranscriptionResult对象
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
        audio_duration = librosa.get_duration(path=audio_path)
    except ImportError:
        # 如果没有librosa，直接使用普通转录
        logger.warning("librosa 未安装，使用普通转录模式")
        return transcribe_audio(
            audio_path=audio_path,
            model_name=model_size,
            device=device,
            compute_type=compute_type,
            language=language,
            progress_callback=progress_callback
        )
    except Exception as e:
        logger.warning(f"获取音频时长失败: {e}，使用普通转录")
        return transcribe_audio(
            audio_path=audio_path,
            model_name=model_size,
            device=device,
            compute_type=compute_type,
            language=language,
            progress_callback=progress_callback
        )
    
    # 如果音频较短(<30分钟)，直接处理
    if audio_duration <= 1800:  # 30分钟
        logger.info(f"音频时长{audio_duration:.0f}秒，使用直接转录")
        return transcribe_audio(
            audio_path=audio_path,
            model_name=model_size,
            device=device,
            compute_type=compute_type,
            language=language,
            progress_callback=progress_callback
        )
    
    # 超长音频：仅在内存压力下分段
    # 使用智能分段策略：在静音处分段，每段约10-15分钟
    logger.info(f"音频时长{audio_duration:.0f}秒，使用智能分段转录")
    return _transcribe_with_smart_chunking(
        audio_path=audio_path,
        model_size=model_size,
        device=device,
        compute_type=compute_type,
        language=language,
        progress_callback=progress_callback,
        audio_duration=audio_duration
    )


def _transcribe_with_smart_chunking(
    audio_path: str,
    model_size: str,
    device: str,
    compute_type: str,
    language: Optional[str],
    progress_callback: Optional[Callable],
    audio_duration: float
) -> TranscriptionResult:
    """智能分段转录 - 在语义边界处分段"""
    
    if progress_callback:
        progress_callback(0, f"分析音频结构，寻找分段点...")
    
    try:
        import librosa
        import numpy as np
        
        # 加载音频进行VAD分析
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        
        # 使用librosa的VAD检测静音点
        # 将音频分成小段，检测能量
        frame_length = int(sr * 0.5)  # 500ms帧
        hop_length = int(sr * 0.25)   # 250ms步长
        
        # 计算每帧的能量
        energy = np.array([
            np.sum(y[i:i+frame_length]**2) 
            for i in range(0, len(y) - frame_length, hop_length)
        ])
        
        # 找到低能量区域（静音）
        energy_threshold = np.mean(energy) * 0.1  # 平均能量的10%
        silence_frames = energy < energy_threshold
        
        # 寻找持续时间>500ms的静音段
        min_silence_duration = int(0.5 * sr / hop_length)  # 500ms对应的帧数
        
        chunk_boundaries: list = [0.0]  # 起始点
        silence_start = None
        
        for i, is_silence in enumerate(silence_frames):
            if is_silence and silence_start is None:
                silence_start = i
            elif not is_silence and silence_start is not None:
                silence_duration = i - silence_start
                if silence_duration >= min_silence_duration:
                    # 找到合适的分段点
                    time_at_boundary = silence_start * hop_length / sr
                    # 确保分段不会太短或太长（10-15分钟）
                    if len(chunk_boundaries) == 0:
                        if time_at_boundary > 600:  # 至少10分钟
                            chunk_boundaries.append(time_at_boundary)
                    else:
                        last_boundary = chunk_boundaries[-1]
                        if time_at_boundary - last_boundary > 900:  # 最大15分钟
                            # 回溯找一个较近的点
                            for j in range(i-1, silence_start, -1):
                                if silence_frames[j]:
                                    time_at_boundary = j * hop_length / sr
                                    if time_at_boundary - last_boundary >= 600:
                                        chunk_boundaries.append(float(time_at_boundary))
                                        break
                            else:
                                # 没找到合适的，强制在10分钟处分段
                                chunk_boundaries.append(last_boundary + 600)
        
        chunk_boundaries.append(audio_duration)  # 结束点
        
        logger.info(f"智能分段：找到 {len(chunk_boundaries)-1} 个分段点")
        for i in range(len(chunk_boundaries)-1):
            logger.info(f"  分段 {i+1}: {chunk_boundaries[i]:.1f}s - {chunk_boundaries[i+1]:.1f}s")
        
    except Exception as e:
        import numpy as np
        logger.warning(f"智能分段分析失败: {e}，回退到固定分段")
        # 回退到固定分段
        num_chunks = int(np.ceil(audio_duration / 600))
        chunk_boundaries = [float(i * 600) for i in range(num_chunks)] + [float(audio_duration)]
    
    # 使用分段边界进行转录
    return _transcribe_with_boundaries(
        audio_path=audio_path,
        model_size=model_size,
        device=device,
        compute_type=compute_type,
        language=language,
        progress_callback=progress_callback,
        chunk_boundaries=chunk_boundaries
    )


def _transcribe_with_boundaries(
    audio_path: str,
    model_size: str,
    device: str,
    compute_type: str,
    language: Optional[str],
    progress_callback: Optional[Callable],
    chunk_boundaries: list
) -> TranscriptionResult:
    """使用预定义边界分段转录"""
    
    if progress_callback:
        progress_callback(5, f"加载模型 {model_size}...")
    
    # 初始化模型
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type
    )
    
    all_segments = []
    detected_language = None
    language_probability = 0
    
    num_chunks = len(chunk_boundaries) - 1
    
    for chunk_idx in range(num_chunks):
        start_time = chunk_boundaries[chunk_idx]
        end_time = chunk_boundaries[chunk_idx + 1]
        
        if progress_callback:
            progress_base = 10 + (chunk_idx / num_chunks) * 85
            progress_callback(
                progress_base,
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
        
        # 收集分段结果，只保留在当前时间范围内的
        for segment in segments_generator:
            segment_start = segment.start + start_time
            segment_end = segment.end + start_time
            
            # 只添加在当前分段范围内的片段
            if segment_start >= start_time and segment_end <= end_time + 1:  # +1秒容差
                segment_data = {
                    "start": round(segment_start, 3),
                    "end": round(segment_end, 3),
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
    
    # 转换为结果对象
    transcription_segments = [
        TranscriptionSegment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"],
            words=seg["words"]
        )
        for seg in all_segments
    ]
    
    # 构建完整文本
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
    
    logger.info(f"智能分段转录完成: {len(all_segments)} 个���段, 语言: {detected_language}")
    return result


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