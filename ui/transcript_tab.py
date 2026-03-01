"""
Transcription view tab with split layout
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QComboBox, QMessageBox, QApplication,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from app.database import get_all_videos, get_transcripts_by_video


class TranscriptTab(QWidget):
    """Tab for viewing video transcriptions with split timestamp/text layout"""
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._connect_signals()
        self._load_video_list()
    
    def _setup_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Top control bar
        control_layout = QHBoxLayout()
        control_layout.setSpacing(12)
        
        control_layout.addWidget(QLabel("选择视频:"))
        self.video_combo = QComboBox()
        self.video_combo.setMinimumWidth(300)
        self.video_combo.addItem("请选择视频...", -1)
        control_layout.addWidget(self.video_combo)
        
        control_layout.addStretch()
        
        self.copy_button = QPushButton("复制文本")
        self.copy_button.setEnabled(False)
        control_layout.addWidget(self.copy_button)
        
        main_layout.addLayout(control_layout)
        
        # Progress label
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.progress_label)
        
        # Transcript table with two columns
        self.transcript_table = QTableWidget()
        self.transcript_table.setColumnCount(2)
        self.transcript_table.setHorizontalHeaderLabels(["时间", "转录内容"])
        self.transcript_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.transcript_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.transcript_table.setMinimumHeight(400)
        self.transcript_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #0066cc;
                font-weight: bold;
                color: #333;
            }
        """)
        self.transcript_table.verticalHeader().setVisible(False)
        main_layout.addWidget(self.transcript_table)
        
        # Status bar
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        main_layout.addWidget(self.status_label)
    
    def _connect_signals(self):
        self.video_combo.currentIndexChanged.connect(self._on_video_changed)
        self.copy_button.clicked.connect(self._copy_transcript)
    
    def _load_video_list(self):
        self.video_combo.blockSignals(True)
        self.video_combo.clear()
        self.video_combo.addItem("请选择视频...", -1)
        
        videos = get_all_videos()
        for video in videos:
            display_text = f"{video['title']} ({video['bilibili_id']})"
            self.video_combo.addItem(display_text, video['id'])
        
        self.video_combo.blockSignals(False)
    
    def _on_video_changed(self, index: int):
        video_id = self.video_combo.currentData()
        
        if video_id == -1:
            self.transcript_table.setRowCount(0)
            self.progress_label.clear()
            self.copy_button.setEnabled(False)
            self.status_label.setText("就绪")
            return
        
        self._load_transcript(video_id)
    
    def _load_transcript(self, video_id: int):
        videos = get_all_videos()
        video = next((v for v in videos if v['id'] == video_id), None)
        
        if not video:
            self.status_label.setText("错误：视频不存在")
            return
        
        if video['status'] == 'pending':
            self.progress_label.setText("⏳ 视频等待处理中...")
            self.transcript_table.setRowCount(0)
            self.copy_button.setEnabled(False)
            self.status_label.setText("状态：等待处理")
            return
        elif video['status'] == 'processing':
            self.progress_label.setText("⏳ 视频处理中...")
            self.transcript_table.setRowCount(0)
            self.copy_button.setEnabled(False)
            self.status_label.setText("状态：处理中")
            return
        elif video['status'] == 'failed':
            self.progress_label.setText("❌ 视频处理失败")
            self.transcript_table.setRowCount(0)
            self.copy_button.setEnabled(False)
            self.status_label.setText("状态：失败")
            return
        
        transcripts = get_transcripts_by_video(video_id)
        
        if not transcripts:
            self.progress_label.clear()
            self.transcript_table.setRowCount(0)
            self.copy_button.setEnabled(False)
            self.status_label.setText("状态：完成 (无转录数据)")
            return
        
        self._display_transcripts(transcripts)
        self.progress_label.clear()
        self.copy_button.setEnabled(True)
        self.status_label.setText(f"状态：完成 | 片段数：{len(transcripts)}")
    
    def _display_transcripts(self, transcripts: list):
        self.transcript_table.setRowCount(len(transcripts))
        
        for i, segment in enumerate(transcripts):
            # Time column
            start_time = self._format_timestamp(segment['start_seconds'])
            end_time = self._format_timestamp(segment['end_seconds'])
            time_item = QTableWidgetItem(f"{start_time} - {end_time}")
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setForeground(Qt.GlobalColor.blue)
            self.transcript_table.setItem(i, 0, time_item)
            
            # Text column
            text_item = QTableWidgetItem(segment['text'])
            self.transcript_table.setItem(i, 1, text_item)
    
    def _format_timestamp(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _copy_transcript(self):
        transcript_text = ""
        for i in range(self.transcript_table.rowCount()):
            time_text = self.transcript_table.item(i, 0).text()
            text = self.transcript_table.item(i, 1).text()
            transcript_text += f"[{time_text}] {text}\n"
        
        if not transcript_text.strip():
            QMessageBox.information(self, "提示", "没有可复制的文本")
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText(transcript_text)
        
        self.status_label.setText("✓ 已复制到剪贴板")
        self.status_label.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: bold;")
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, self._reset_status)
    
    def _reset_status(self):
        self.status_label.setText("就绪")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
    
    def refresh(self):
        current_index = self.video_combo.currentIndex()
        self._load_video_list()
        
        if current_index >= 0 and current_index < self.video_combo.count():
            self.video_combo.setCurrentIndex(current_index)
            self._on_video_changed(current_index)
    
    def load_video(self, video_id: int):
        for i in range(self.video_combo.count()):
            if self.video_combo.itemData(i) == video_id:
                self.video_combo.setCurrentIndex(i)
                break
        self._load_transcript(video_id)