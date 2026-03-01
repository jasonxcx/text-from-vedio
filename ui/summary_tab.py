"""
Summary Tab - Displays video summaries with key points
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QComboBox, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextEdit
from app.database import get_all_videos, get_summary_by_video


class SummaryTab(QWidget):
    """Tab for viewing video summaries and key points"""

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._connect_signals()
        self._load_video_list()

    def _setup_ui(self):
        """Initialize the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Top control bar
        control_layout = QHBoxLayout()
        control_layout.setSpacing(12)

        # Video selector
        control_layout.addWidget(QLabel("选择视频:"))
        self.video_combo = QComboBox()
        self.video_combo.setMinimumWidth(300)
        self.video_combo.addItem("请选择视频...", -1)
        control_layout.addWidget(self.video_combo)

        control_layout.addStretch()

        # Copy summary button
        self.copy_summary_btn = QPushButton("复制摘要")
        self.copy_summary_btn.setEnabled(False)
        control_layout.addWidget(self.copy_summary_btn)

        # Copy key points button
        self.copy_points_btn = QPushButton("复制关键点")
        self.copy_points_btn.setEnabled(False)
        control_layout.addWidget(self.copy_points_btn)

        main_layout.addLayout(control_layout)

        # Progress label (for processing status)
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.progress_label)

        # Content area with summary and key points
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left: Summary text
        summary_group = self._create_summary_group()
        content_layout.addWidget(summary_group, stretch=2)

        # Right: Key points list
        keypoints_group = self._create_keypoints_group()
        content_layout.addWidget(keypoints_group, stretch=1)

        main_layout.addLayout(content_layout)

        # Status bar
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        main_layout.addWidget(self.status_label)

    def _create_summary_group(self) -> QWidget:
        """Create summary display group"""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("摘要内容")
        header.setStyleSheet("font-weight: bold; font-size: 16px; color: #ffffff; background-color: #333333; padding: 8px 12px; border-radius: 4px;")
        layout.addWidget(header)

        # Summary text display
        self.summary_display = QTextEdit()
        self.summary_display.setReadOnly(True)
        self.summary_display.setPlaceholderText("选择视频后显示摘要内容...")
        self.summary_display.setMinimumWidth(400)
        self.summary_display.setMinimumHeight(400)
        self.summary_display.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        # 设置高对比度样式
        self.summary_display.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.summary_display)

        return group

    def _create_keypoints_group(self) -> QWidget:
        """Create key points list group"""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("关键点列表")
        header.setStyleSheet("font-weight: bold; font-size: 16px; color: #ffffff; background-color: #333333; padding: 8px 12px; border-radius: 4px;")
        layout.addWidget(header)

        # Key points list
        self.keypoints_list = QListWidget()
        self.keypoints_list.setMinimumWidth(250)
        self.keypoints_list.setMinimumHeight(400)
        self.keypoints_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #000000;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
                color: #000000;
                font-size: 13px;
                min-height: 40px;
            }
            QListWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
        """)
        layout.addWidget(self.keypoints_list)

        return group

    def _connect_signals(self):
        """Connect widget signals"""
        self.video_combo.currentIndexChanged.connect(self._on_video_changed)
        self.copy_summary_btn.clicked.connect(self._copy_summary)
        self.copy_points_btn.clicked.connect(self._copy_keypoints)

    def _load_video_list(self):
        """Load video list into combo box"""
        self.video_combo.blockSignals(True)
        self.video_combo.clear()
        self.video_combo.addItem("请选择视频...", -1)

        videos = get_all_videos()
        for video in videos:
            display_text = f"{video['title']} ({video['bilibili_id']})"
            self.video_combo.addItem(display_text, video['id'])

        self.video_combo.blockSignals(False)

    def _on_video_changed(self, index: int):
        """Handle video selection change"""
        video_id = self.video_combo.currentData()

        if video_id == -1:
            self.summary_display.clear()
            self.keypoints_list.clear()
            self.progress_label.clear()
            self.copy_summary_btn.setEnabled(False)
            self.copy_points_btn.setEnabled(False)
            self.status_label.setText("就绪")
            return

        self._load_summary(video_id)

    def _load_summary(self, video_id: int):
        """Load and display summary for selected video"""
        # Get video info
        videos = get_all_videos()
        video = next((v for v in videos if v['id'] == video_id), None)

        if not video:
            self.status_label.setText("错误：视频不存在")
            return

        # Check video status
        if video['status'] == 'pending':
            self.progress_label.setText("⏳ 视频等待处理中...")
            self.summary_display.setPlaceholderText("摘要尚未生成，请稍候...")
            self.summary_display.clear()
            self.keypoints_list.clear()
            self.copy_summary_btn.setEnabled(False)
            self.copy_points_btn.setEnabled(False)
            self.status_label.setText("状态：等待处理")
            return
        elif video['status'] == 'processing':
            self.progress_label.setText("⏳ 视频处理中...")
            self.summary_display.setPlaceholderText("摘要正在生成中，请稍候...")
            self.summary_display.clear()
            self.keypoints_list.clear()
            self.copy_summary_btn.setEnabled(False)
            self.copy_points_btn.setEnabled(False)
            self.status_label.setText("状态：处理中")
            return
        elif video['status'] == 'failed':
            self.progress_label.setText("❌ 视频处理失败")
            self.summary_display.setPlaceholderText("摘要生成失败，请检查日志...")
            self.summary_display.clear()
            self.keypoints_list.clear()
            self.copy_summary_btn.setEnabled(False)
            self.copy_points_btn.setEnabled(False)
            self.status_label.setText("状态：失败")
            return

        # Load summary
        summary = get_summary_by_video(video_id)

        if not summary:
            self.progress_label.clear()
            self.summary_display.setPlaceholderText("暂无摘要数据")
            self.keypoints_list.clear()
            self.copy_summary_btn.setEnabled(False)
            self.copy_points_btn.setEnabled(False)
            self.status_label.setText("状态：完成 (无摘要数据)")
            return

        # Display summary
        self._display_summary(summary)
        self.progress_label.clear()
        self.copy_summary_btn.setEnabled(True)
        self.copy_points_btn.setEnabled(True)
        self.status_label.setText(f"状态：完成 | 关键点：{len(summary['key_points'])} 条")

    def _display_summary(self, summary: dict):
        """Display summary text and key points"""
        # Display summary text
        self.summary_display.clear()
        self.summary_display.setPlainText(summary['summary_text'])

        # Display key points
        self.keypoints_list.clear()
        for i, point in enumerate(summary['key_points'], 1):
            item = QListWidgetItem(f"{i}. {point}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.keypoints_list.addItem(item)

    def _copy_summary(self):
        """Copy summary text to clipboard"""
        summary_text = self.summary_display.toPlainText()

        if not summary_text.strip():
            QMessageBox.information(self, "提示", "没有可复制的摘要内容")
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(summary_text)

        self.status_label.setText("✓ 摘要已复制到剪贴板")
        self._show_temp_success()

    def _copy_keypoints(self):
        """Copy key points to clipboard"""
        if self.keypoints_list.count() == 0:
            QMessageBox.information(self, "提示", "没有可复制的关键点")
            return

        # Collect all key points
        key_points = []
        for i in range(self.keypoints_list.count()):
            item = self.keypoints_list.item(i)
            # Remove the numbering prefix
            text = item.text()
            if '. ' in text:
                text = text.split('. ', 1)[1]
            key_points.append(text)

        # Format as bullet list
        formatted_text = '\n'.join([f"• {point}" for point in key_points])

        clipboard = QApplication.clipboard()
        clipboard.setText(formatted_text)

        self.status_label.setText("✓ 关键点已复制到剪贴板")
        self._show_temp_success()

    def _show_temp_success(self):
        """Show temporary success message and reset status"""
        self.status_label.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: bold;")

        # Reset after 2 seconds
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._reset_status())

    def _reset_status(self):
        """Reset status label to default style"""
        self.status_label.setText("就绪")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
    
    def refresh(self):
        """Refresh video list and current summary"""
        current_index = self.video_combo.currentIndex()
        self._load_video_list()
        
        # Restore selection if possible
        if current_index >= 0 and current_index < self.video_combo.count():
            self.video_combo.setCurrentIndex(current_index)
            self._on_video_changed(current_index)
    
    def load_video(self, video_id: int):
        """Load a specific video's summary"""
        # Find and select the video in combo box
        for i in range(self.video_combo.count()):
            if self.video_combo.itemData(i) == video_id:
                self.video_combo.setCurrentIndex(i)
                break
        # Load the summary
        self._load_summary(video_id)
