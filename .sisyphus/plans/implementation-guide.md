# 技术实施详细指南

> 每个任务的详细实现代码和步骤
> 与 `.sisyphus/plans/improvement-plan.md` 配合使用

---

## Task 1: 语义分段优化

### 目标
移除 `transcribe_long_audio` 中的固定时长分段，改用faster-whisper的自然语义分段。

### 实现步骤

#### Step 1: 修改 transcriber.py

**文件**: `services/transcriber.py`

**修改内容**:

```python
# 替换现有的 transcribe_long_audio 函数 (第202-382行)

def transcribe_long_audio(
    audio_path: str,
    model_size: str = "large-v3",
    chunk_duration: int = 600,  # 保留参数但不使用，保持API兼容
    device: str = "auto",
    compute_type: str = "auto",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> TranscriptionResult:
    """使用语义分段处理长音频
    
    不再强制按固定时长分段，而是依赖faster-whisper的VAD和自然分段机制。
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
        
        chunk_boundaries = [0]  # 起始点
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
                                        chunk_boundaries.append(time_at_boundary)
                                        break
                            else:
                                # 没找到合适的，强制在10分钟处分段
                                chunk_boundaries.append(last_boundary + 600)
        
        chunk_boundaries.append(audio_duration)  # 结束点
        
        logger.info(f"智能分段：找到 {len(chunk_boundaries)-1} 个分段点")
        for i in range(len(chunk_boundaries)-1):
            logger.info(f"  分段 {i+1}: {chunk_boundaries[i]:.1f}s - {chunk_boundaries[i+1]:.1f}s")
        
    except Exception as e:
        logger.warning(f"智能分段分析失败: {e}，回退到固定分段")
        # 回退到固定分段
        num_chunks = int(np.ceil(audio_duration / 600))
        chunk_boundaries = [i * 600 for i in range(num_chunks)] + [audio_duration]
    
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
    
    full_text = " ".join(seg["text"] for seg in all_segments)
    
    if progress_callback:
        progress_callback(100, f"转录完成，共 {len(all_segments)} 个分段")
    
    return TranscriptionResult(
        success=True,
        segments=transcription_segments,
        full_text=full_text,
        language=detected_language or "",
        language_probability=round(language_probability, 3) if language_probability else 0.0,
        error_message=None
    )
```

### 依赖检查
确保 `requirements.txt` 包含:
```
librosa>=0.10.0
numpy>=1.24.0
```

### 测试验证
```python
# tests/test_semantic_chunking.py
import pytest
from services.transcriber import transcribe_long_audio

def test_short_audio_no_chunking():
    """短音频应该直接转录，不分段"""
    # 使用测试音频
    result = transcribe_long_audio("tests/fixtures/short_audio.mp3")
    assert result.success
    # 验证没有强制600秒分段


def test_long_audio_semantic_chunking():
    """长音频应该使用语义分段"""
    # 使用长测试音频
    result = transcribe_long_audio("tests/fixtures/long_audio.mp3")
    assert result.success
    # 验证分段边界不在固定时间点
```

---

## Task 2: 批量添加UI基础

### 目标
创建批量添加视频对话框，支持多URL粘贴。

### 实现步骤

#### Step 1: 创建批量添加对话框

**新建文件**: `ui/batch_add_dialog.py`

```python
"""批量添加视频对话框"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QMessageBox, QSplitter,
    QWidget, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from typing import List, Dict, Optional
import re


class URLParseWorker(QThread):
    """后台解析URL线程"""
    url_parsed = Signal(dict)  # {url, bilibili_id, status, title, duration}
    progress = Signal(int, int)  # (current, total)
    finished = Signal()
    
    def __init__(self, urls: List[str]):
        super().__init__()
        self.urls = urls
        self._is_cancelled = False
    
    def run(self):
        total = len(self.urls)
        for i, url in enumerate(self.urls):
            if self._is_cancelled:
                break
            
            self.progress.emit(i + 1, total)
            result = self._parse_url(url)
            self.url_parsed.emit(result)
        
        self.finished.emit()
    
    def _parse_url(self, url: str) -> dict:
        """解析单个URL"""
        result = {
            "url": url,
            "bilibili_id": None,
            "status": "parsing",
            "title": None,
            "duration": 0,
            "error": None
        }
        
        # 提取BV号
        bv_pattern = r'(BV[a-zA-Z0-9]+)'
        match = re.search(bv_pattern, url, re.IGNORECASE)
        
        if match:
            result["bilibili_id"] = match.group(1)
            result["status"] = "parsed"
        else:
            av_pattern = r'av(\d+)'
            match = re.search(av_pattern, url, re.IGNORECASE)
            if match:
                result["bilibili_id"] = f"av{match.group(1)}"
                result["status"] = "parsed"
            else:
                result["status"] = "error"
                result["error"] = "无法识别视频ID"
        
        return result
    
    def cancel(self):
        self._is_cancelled = True


class BatchAddDialog(QDialog):
    """批量添加视频对话框"""
    
    videos_confirmed = Signal(list)  # 确认添加的视频列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量添加视频")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._parse_worker: Optional[URLParseWorker] = None
        self._parsed_results: List[dict] = []
    
    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 说明标签
        info_label = QLabel("支持以下格式：\n• B站视频URL (https://www.bilibili.com/video/BVxxx)\n• B23短链接 (https://b23.tv/xxxxx)\n• BV号 (BV1xx411c7mD)\n• AV号 (av123456)")
        info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info_label)
        
        # URL输入区
        url_label = QLabel("输入视频URL（每行一个）：")
        url_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(url_label)
        
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("https://www.bilibili.com/video/BV1xx411c7mD\nhttps://www.bilibili.com/video/BV2yy511d8nE\n...")
        self.url_input.setMinimumHeight(120)
        layout.addWidget(self.url_input)
        
        # 解析按钮
        button_layout = QHBoxLayout()
        
        self.parse_btn = QPushButton("解析URL")
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0055aa; }
            QPushButton:disabled { background-color: #999; }
        """)
        self.parse_btn.clicked.connect(self._on_parse)
        button_layout.addWidget(self.parse_btn)
        
        button_layout.addStretch()
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        # 进度条（解析时显示）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)
        
        # 预览表格
        preview_label = QLabel("解析结果预览：")
        preview_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(preview_label)
        
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        self.preview_table.setHorizontalHeaderLabels(["BV号", "标题", "时长", "状态", "操作"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item { padding: 5px; }
        """)
        layout.addWidget(self.preview_table)
        
        # 统计信息
        self.stats_label = QLabel("共 0 个URL，成功 0 个，失败 0 个")
        self.stats_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.stats_label)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_btn)
        
        self.confirm_btn = QPushButton("确认添加")
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #999; }
        """)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._on_confirm)
        bottom_layout.addWidget(self.confirm_btn)
        
        layout.addLayout(bottom_layout)
    
    def _on_parse(self):
        """解析URL按钮点击"""
        text = self.url_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入视频URL")
            return
        
        # 解析多行
        urls = [line.strip() for line in text.split('\n') if line.strip()]
        if not urls:
            QMessageBox.warning(self, "警告", "没有有效的URL")
            return
        
        # 启动解析线程
        self._start_parsing(urls)
    
    def _start_parsing(self, urls: List[str]):
        """开始解析"""
        self._parsed_results = []
        self.preview_table.setRowCount(0)
        
        self.parse_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(urls))
        self.progress_bar.setValue(0)
        
        self._parse_worker = URLParseWorker(urls)
        self._parse_worker.url_parsed.connect(self._on_url_parsed)
        self._parse_worker.progress.connect(self._on_parse_progress)
        self._parse_worker.finished.connect(self._on_parse_finished)
        self._parse_worker.start()
    
    def _on_url_parsed(self, result: dict):
        """单个URL解析完成"""
        self._parsed_results.append(result)
        self._add_result_to_table(result)
    
    def _on_parse_progress(self, current: int, total: int):
        """解析进度更新"""
        self.progress_bar.setValue(current)
    
    def _on_parse_finished(self):
        """解析完成"""
        self.parse_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._update_stats()
        
        # 如果有成功解析的，启用确认按钮
        success_count = sum(1 for r in self._parsed_results if r["status"] == "parsed")
        self.confirm_btn.setEnabled(success_count > 0)
    
    def _add_result_to_table(self, result: dict):
        """添加结果到表格"""
        row = self.preview_table.rowCount()
        self.preview_table.insertRow(row)
        
        # BV号
        bv_item = QTableWidgetItem(result["bilibili_id"] or "-")
        bv_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_table.setItem(row, 0, bv_item)
        
        # 标题（暂时显示"待获取"）
        title_item = QTableWidgetItem("待获取" if result["status"] == "parsed" else "-")
        self.preview_table.setItem(row, 1, title_item)
        
        # 时长
        duration_item = QTableWidgetItem("-")
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_table.setItem(row, 2, duration_item)
        
        # 状态
        if result["status"] == "parsed":
            status_text = "✓ 可添加"
            status_color = QColor("#28a745")
        elif result["status"] == "error":
            status_text = f"✗ {result.get('error', '错误')}"
            status_color = QColor("#dc3545")
        else:
            status_text = "解析中..."
            status_color = QColor("#ffc107")
        
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setForeground(status_color)
        self.preview_table.setItem(row, 3, status_item)
        
        # 操作
        self.preview_table.setItem(row, 4, QTableWidgetItem("-"))
    
    def _update_stats(self):
        """更新统计信息"""
        total = len(self._parsed_results)
        success = sum(1 for r in self._parsed_results if r["status"] == "parsed")
        error = sum(1 for r in self._parsed_results if r["status"] == "error")
        
        self.stats_label.setText(f"共 {total} 个URL，成功 {success} 个，失败 {error} 个")
    
    def _on_clear(self):
        """清空按钮"""
        self.url_input.clear()
        self.preview_table.setRowCount(0)
        self._parsed_results = []
        self.stats_label.setText("共 0 个URL，成功 0 个，失败 0 个")
        self.confirm_btn.setEnabled(False)
    
    def _on_confirm(self):
        """确认添加"""
        # 过滤出成功解析的
        valid_results = [r for r in self._parsed_results if r["status"] == "parsed"]
        
        if not valid_results:
            QMessageBox.warning(self, "警告", "没有可添加的视频")
            return
        
        self.videos_confirmed.emit(valid_results)
        self.accept()
    
    def closeEvent(self, event):
        """关闭事件"""
        if self._parse_worker and self._parse_worker.isRunning():
            self._parse_worker.cancel()
            self._parse_worker.wait(1000)
        super().closeEvent(event)
```

#### Step 2: 在 video_list_tab.py 中集成

**修改**: `ui/video_list_tab.py`

**添加导入**（在第13行后）:
```python
from ui.batch_add_dialog import BatchAddDialog
```

**修改控制面板创建**（在 `_create_control_panel` 方法中，第81行后添加）:
```python
# 批量添加按钮
self.batch_add_btn = QPushButton("批量添加")
self.batch_add_btn.setStyleSheet("""
    QPushButton {
        background-color: #17a2b8;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #138496; }
""")
panel.addWidget(self.batch_add_btn)
```

**添加信号连接**（在 `_connect_signals` 方法中，第192行后添加）:
```python
self.batch_add_btn.clicked.connect(self._on_batch_add)
```

**添加批量添加处理方法**（在 `_on_add_video` 方法后添加）:
```python
@Slot()
def _on_batch_add(self):
    """打开批量添加对话框"""
    dialog = BatchAddDialog(self)
    dialog.videos_confirmed.connect(self._on_batch_videos_confirmed)
    dialog.exec()

@Slot(list)
def _on_batch_videos_confirmed(self, videos: list):
    """处理批量添加确认"""
    from app.database import add_video, get_video_by_bilibili_id
    
    added_count = 0
    skipped_count = 0
    error_count = 0
    
    for video_info in videos:
        bilibili_id = video_info.get("bilibili_id")
        url = video_info.get("url")
        
        if not bilibili_id or not url:
            error_count += 1
            continue
        
        # 检查是否已存在
        existing = get_video_by_bilibili_id(bilibili_id)
        if existing:
            skipped_count += 1
            continue
        
        # 添加到数据库
        try:
            video_id = add_video(
                bilibili_id=bilibili_id,
                title=f"视频 {bilibili_id}",  # 稍后下载时会更新
                url=url,
                duration=0,
                status="pending"
            )
            
            video = get_video_by_bilibili_id(bilibili_id)
            if video:
                self.video_added.emit(video)
            
            added_count += 1
        except Exception as e:
            error_count += 1
    
    # 显示结果
    msg = f"批量添加完成！\n成功: {added_count} 个\n跳过(已存在): {skipped_count} 个\n失败: {error_count} 个"
    QMessageBox.information(self, "完成", msg)
    
    # 刷新列表
    self._load_videos()
```

---

## Task 3: 并发队列架构设计

### 目标
设计阶段分离的任务队列系统。

### 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    TaskQueueManager                      │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ DownloadQueue│  │TranscribeQueue│  │ SummaryQueue │  │
│  │   (可并发)    │  │   (单线程)    │  │   (可并发)   │  │
│  │   max: 3     │  │   max: 1     │  │   max: N    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                  │                  │          │
│         ▼                  ▼                  ▼          │
│    ┌─────────┐        ┌─────────┐        ┌─────────┐  │
│    │ Thread  │        │ Thread  │        │ Thread  │  │
│    │  Pool   │        │ (单线程) │        │  Pool   │  │
│    └─────────┘        └─────────┘        └─────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 状态流转

```
pending → queued_download → downloading → queued_transcribe → transcribing 
                                                                    ↓
                                                          queued_summary → summarizing → completed
```

### 实现代码

**新建文件**: `app/task_queue.py`

```python
"""阶段分离的任务队列系统"""
from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable, QThread
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import logging
import time
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class TaskStage(Enum):
    """任务阶段"""
    PENDING = auto()
    QUEUED_DOWNLOAD = auto()
    DOWNLOADING = auto()
    QUEUED_TRANSCRIBE = auto()
    TRANSCRIBING = auto()
    QUEUED_SUMMARY = auto()
    SUMMARIZING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class Task:
    """任务对象"""
    video_id: int
    url: str
    title: str
    bilibili_id: str
    stage: TaskStage = TaskStage.PENDING
    result: Any = None
    error: Optional[str] = None
    retry_count: Dict[TaskStage, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        # 初始化各阶段重试计数
        for stage in TaskStage:
            if stage not in self.retry_count:
                self.retry_count[stage] = 0


class StageQueue:
    """阶段队列"""
    
    def __init__(self, name: str, max_workers: int):
        self.name = name
        self.max_workers = max_workers
        self.queue: Queue[Task] = Queue()
        self.active_tasks: Dict[int, Task] = {}
        self.worker_pool = QThreadPool()
        self.worker_pool.setMaxThreadCount(max_workers)
        self._shutdown = False
    
    def submit(self, task: Task) -> bool:
        """提交任务到队列"""
        if self._shutdown:
            return False
        
        self.queue.put(task)
        self._process_queue()
        return True
    
    def _process_queue(self):
        """处理队列中的任务"""
        while (not self.queue.empty() and 
               len(self.active_tasks) < self.max_workers and 
               not self._shutdown):
            try:
                task = self.queue.get_nowait()
                self.active_tasks[task.video_id] = task
                self._execute_task(task)
            except Empty:
                break
    
    def _execute_task(self, task: Task):
        """执行任务（由子类实现）"""
        raise NotImplementedError
    
    def _on_task_finished(self, task: Task):
        """任务完成回调"""
        self.active_tasks.pop(task.video_id, None)
        self._process_queue()
    
    def get_active_count(self) -> int:
        """获取活跃任务数"""
        return len(self.active_tasks)
    
    def get_queued_count(self) -> int:
        """获取队列中任务数"""
        return self.queue.qsize()
    
    def shutdown(self):
        """关闭队列"""
        self._shutdown = True
        self.worker_pool.clear()
        self.worker_pool.waitForDone(5000)


class TaskQueueManager(QObject):
    """任务队列管理器"""
    
    # 信号
    task_stage_changed = Signal(int, str)  # (video_id, stage_name)
    task_progress = Signal(int, int, str)  # (video_id, percent, message)
    task_completed = Signal(int, bool, str)  # (video_id, success, message)
    
    def __init__(self, 
                 download_concurrency: int = 3,
                 transcribe_concurrency: int = 1,
                 summary_concurrency: int = 3):
        super().__init__()
        
        self.download_concurrency = download_concurrency
        self.transcribe_concurrency = transcribe_concurrency
        self.summary_concurrency = summary_concurrency
        
        # 创建阶段队列
        self.queues: Dict[TaskStage, StageQueue] = {}
        self._setup_queues()
        
        # 任务存储
        self.tasks: Dict[int, Task] = {}
        self._lock = QThread()
    
    def _setup_queues(self):
        """设置各阶段队列"""
        # 将在Task 5中实现具体的队列类
        pass
    
    def submit_task(self, video_id: int, url: str, title: str, bilibili_id: str):
        """提交新任务"""
        task = Task(
            video_id=video_id,
            url=url,
            title=title,
            bilibili_id=bilibili_id,
            stage=TaskStage.PENDING
        )
        
        self.tasks[video_id] = task
        self._transition_task(task, TaskStage.QUEUED_DOWNLOAD)
    
    def _transition_task(self, task: Task, new_stage: TaskStage):
        """任务阶段转换"""
        old_stage = task.stage
        task.stage = new_stage
        
        logger.info(f"任务 {task.video_id} 阶段转换: {old_stage.name} -> {new_stage.name}")
        
        self.task_stage_changed.emit(task.video_id, new_stage.name.lower())
        
        # 根据新阶段分发到对应队列
        if new_stage in self.queues:
            self.queues[new_stage].submit(task)
    
    def cancel_task(self, video_id: int) -> bool:
        """取消任务"""
        if video_id in self.tasks:
            task = self.tasks[video_id]
            # 如果还在队列中，从队列移除
            # 如果正在执行，需要发送取消信号
            task.stage = TaskStage.FAILED
            task.error = "用户取消"
            return True
        return False
    
    def get_task_status(self, video_id: int) -> Optional[Dict]:
        """获取任务状态"""
        if video_id not in self.tasks:
            return None
        
        task = self.tasks[video_id]
        return {
            "video_id": task.video_id,
            "stage": task.stage.name,
            "progress": task.result if isinstance(task.result, dict) else {},
            "error": task.error,
            "created_at": task.created_at
        }
    
    def get_queue_status(self) -> Dict[str, Dict]:
        """获取所有队列状态"""
        return {
            stage.name.lower(): {
                "queued": queue.get_queued_count(),
                "active": queue.get_active_count(),
                "max_workers": queue.max_workers
            }
            for stage, queue in self.queues.items()
        }
    
    def shutdown(self):
        """关闭所有队列"""
        for queue in self.queues.values():
            queue.shutdown()
```

---

## Task 4: 配置系统更新

### 目标
添加并发配置项。

### 实现步骤

#### Step 1: 修改 config.py

**修改**: `config.py:26-66`

```python
DEFAULT_CONFIG = {
    # Transcription Settings
    "transcription": {
        "model": "large-v3",
        "device": "cuda",
        "compute_type": "auto",
        "language": "auto",
        "chunk_duration": 600,  # 保留但标记为已废弃
    },
    # Summary Settings
    "summary": {
        "enabled": True,
        "provider": "ollama",
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5",
            "api_key": "",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "api_key": "",
        },
        "custom": {
            "base_url": "",
            "model": "",
            "api_key": "",
        },
        "max_length": 500,
        "temperature": 0.7,
    },
    # 新增：任务队列配置
    "queue": {
        "download": {
            "max_concurrency": 3,  # 同时下载的最大数量
            "max_retries": 3,
            "retry_delay": 5,  # 秒
        },
        "transcribe": {
            "max_concurrency": 1,  # 转录必须单线程（GPU限制）
            "max_retries": 3,
            "retry_delay": 10,
        },
        "summary": {
            "max_concurrency": 3,  # 摘要可并发（用户可配置）
            "max_retries": 3,
            "retry_delay": 5,
        },
    },
    # App Settings
    "app": {
        "window_width": 800,
        "window_height": 650,
        "title": "BiliBili ASR",
        "theme": "dark",
    }
}
```

**添加便捷属性**（在 `config.py:165` 后添加）:

```python
# 队列配置便捷访问
@property
def DOWNLOAD_CONCURRENCY(self) -> int:
    return self.get('queue.download.max_concurrency', 3)

@property
def TRANSCRIBE_CONCURRENCY(self) -> int:
    return self.get('queue.transcribe.max_concurrency', 1)

@property
def SUMMARY_CONCURRENCY(self) -> int:
    return self.get('queue.summary.max_concurrency', 3)
```

**更新导出**（在 `config.py:179` 后添加）:

```python
# 导出队列配置
DOWNLOAD_CONCURRENCY = _config.DOWNLOAD_CONCURRENCY
TRANSCRIBE_CONCURRENCY = _config.TRANSCRIBE_CONCURRENCY
SUMMARY_CONCURRENCY = _config.SUMMARY_CONCURRENCY
```

---

（由于篇幅限制，Task 5-11和F1-F3的详细实现在下一个文件中继续...）

---

## Task 5: Worker重构集成（详细实现）

由于内容较长，这里提供核心实现思路：

### 核心要点

1. **继承TaskQueueManager**
2. **实现三个具体的StageQueue子类**
3. **处理阶段间信号传递**
4. **保持与现有UI的信号兼容**

### 关键代码框架

```python
# app/worker.py 重构
from app.task_queue import TaskQueueManager, StageQueue, Task, TaskStage
from app.database import update_video_status

class DownloadQueue(StageQueue):
    def _execute_task(self, task: Task):
        # 调用现有下载逻辑
        pass

class TranscribeQueue(StageQueue):
    def _execute_task(self, task: Task):
        # 调用现有转录逻辑
        pass

class SummaryQueue(StageQueue):
    def _execute_task(self, task: Task):
        # 调用现有摘要逻辑
        pass

class WorkerManager(TaskQueueManager):
    """重构后的WorkerManager"""
    def __init__(self):
        super().__init__(
            download_concurrency=config.DOWNLOAD_CONCURRENCY,
            transcribe_concurrency=config.TRANSCRIBE_CONCURRENCY,
            summary_concurrency=config.SUMMARY_CONCURRENCY
        )
    
    def _setup_queues(self):
        """初始化队列"""
        self.queues[TaskStage.QUEUED_DOWNLOAD] = DownloadQueue(
            "download", self.download_concurrency
        )
        self.queues[TaskStage.QUEUED_TRANSCRIBE] = TranscribeQueue(
            "transcribe", self.transcribe_concurrency
        )
        self.queues[TaskStage.QUEUED_SUMMARY] = SummaryQueue(
            "summary", self.summary_concurrency
        )
```

---

## Task 6-11 快速参考

| 任务 | 核心文件 | 关键修改 | 测试重点 |
|------|---------|---------|---------|
| Task 6 | `services/batch_processor.py` | 异步批量视频信息获取 | 去重逻辑、错误处理 |
| Task 7 | `ui/settings_tab.py` | 添加QSpinBox控件 | 配置持久化 |
| Task 8 | `app/worker.py`, `ui/video_list_tab.py` | 新增排队状态 | 状态流转 |
| Task 9 | `tests/test_e2e_improvements.py` | 完整流程Mock测试 | 全链路覆盖 |
| Task 10 | `tests/test_performance.py` | 内存/并发基准测试 | 内存<4GB |
| Task 11 | `tests/test_edge_cases.py` | 异常场景测试 | 降级处理 |

---

## 快速开始命令

```bash
# 1. 安装新增依赖
pip install librosa numpy

# 2. 按顺序执行关键任务
# Task 1: 语义分段
# Task 4: 配置更新  
# Task 2+3: UI和架构并行
# Task 5: Worker重构
# Task 6-8: 集成实现
# Task 9-11: 测试

# 3. 运行完整测试
python -m pytest tests/ -v --tb=short

# 4. 启动应用验证
python main.py
```

---

## 重要提示

1. **Task 1** 和 **Task 4** 可以最先开始（无依赖）
2. **Task 5** 必须在 **Task 3** 完成后开始
3. **Task 6** 依赖 **Task 2** 的UI
4. 所有测试任务（9-11）必须在功能完成后进行
5. 每个Task完成后运行对应测试确保质量

