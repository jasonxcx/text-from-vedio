"""
Main window for BiliBili ASR application
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QMessageBox, QProgressBar, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt, Slot
from config import WINDOW_WIDTH, WINDOW_HEIGHT, APP_TITLE
import importlib

VideoListTab = importlib.import_module("ui.video_list_tab").VideoListTab
TranscriptTab = importlib.import_module("ui.transcript_tab").TranscriptTab
SummaryTab = importlib.import_module("ui.summary_tab").SummaryTab
SettingsTab = importlib.import_module("ui.settings_tab").SettingsTab


class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""

    def __init__(self, worker_manager=None):
        super().__init__()
        self.worker_manager = worker_manager or importlib.import_module("app.worker").WorkerManager()
        self._current_worker = None
        self._current_video_id = None
        self._setup_ui()
        self._connect_worker_signals()
        
    def _setup_ui(self):
        """Initialize the user interface"""
        # Window basic settings
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Progress bar at bottom
        self._setup_progress_bar(layout)

        # Create tabs
        self._create_tabs()

    def _setup_progress_bar(self, layout):
        """Create progress bar with status label at the bottom"""
        progress_widget = QWidget()
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(10, 5, 10, 5)
        
        # Status label
        self.progress_label = QLabel("就绪")
        self.progress_label.setMinimumWidth(100)
        progress_layout.addWidget(self.progress_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 3px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
                border-radius: 2px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(progress_widget)

    def _create_tabs(self):
        """Create and add tabs to the tab widget"""
        # Tab 1: Video List
        self.video_list_tab = VideoListTab()
        self.video_list_tab.video_added.connect(self._on_video_added)
        self.video_list_tab.video_deleted.connect(self._on_video_deleted)
        self.video_list_tab.view_transcript.connect(self._view_transcript)
        self.video_list_tab.view_summary.connect(self._view_summary)
        self.video_list_tab.retry_video.connect(self._retry_video)
        self.tab_widget.addTab(self.video_list_tab, "视频列表")

        # Tab 2: Transcription
        self.transcript_tab = TranscriptTab()
        self.tab_widget.addTab(self.transcript_tab, "转录查看")

        # Tab 3: Summary
        self.summary_tab = SummaryTab()
        self.tab_widget.addTab(self.summary_tab, "摘要展示")

        # Tab 4: Settings
        self.settings_tab = SettingsTab()
        self.tab_widget.addTab(self.settings_tab, "设置")
        
    def _view_transcript(self, video_id: int):
        """Jump to transcript tab and load specific video"""
        self.transcript_tab.load_video(video_id)
        self.tab_widget.setCurrentIndex(1)  # Switch to transcript tab
        
    def _view_summary(self, video_id: int):
        """Jump to summary tab and load specific video"""
        self.summary_tab.load_video(video_id)
        self.tab_widget.setCurrentIndex(2)  # Switch to summary tab
        
    def _retry_video(self, video_id: int):
        """Retry processing a video"""
        from app.database import get_video
        video = get_video(video_id)
        if video:
            self.worker_manager.start_worker(
                video_id=video["id"],
                url=video["url"],
                title=video["title"],
                bilibili_id=video["bilibili_id"],
            )

    def _connect_worker_signals(self):
        """Connect worker manager signals to UI updates."""
        self.worker_manager.worker_finished.connect(self._on_worker_finished)

    def _connect_worker_progress(self, worker):
        """Connect a worker's progress signal to the progress bar."""
        worker.progress.connect(self._on_progress_update)
        worker.stage_changed.connect(self._on_stage_changed)
        worker.status_changed.connect(self._on_status_changed)
        self._current_worker = worker
        self._current_video_id = worker.video_id

    @Slot(str, int, str)
    def _on_progress_update(self, stage: str, percent: int, message: str):
        """Update progress bar with current progress."""
        self.progress_bar.setValue(percent)
        # 状态中文映射
        status_cn_map = {
            "pending": "等待中",
            "downloading": "下载中",
            "transcribing": "转录中",
            "summarizing": "整理中",
            "completed": "已完成",
            "failed": "失败",
            "cancelled": "已取消"
        }
        stage_name = status_cn_map.get(stage, stage)
        self.progress_label.setText(f"{stage_name}: {message}")

    @Slot(int, str)
    def _on_status_changed(self, video_id: int, status: str):
        """Update video list when a video's status changes."""
        # 刷新视频列表以显示最新状态
        self.video_list_tab.refresh()
        
    @Slot(str)
    def _on_stage_changed(self, stage: str):
        """Update UI when processing stage changes."""
        status_cn_map = {
            "pending": "等待中",
            "downloading": "下载中",
            "transcribing": "转录中",
            "summarizing": "整理中",
            "completed": "已完成",
            "failed": "失败",
            "cancelled": "已取消"
        }
        stage_name = status_cn_map.get(stage, stage)
        self.statusBar().showMessage(f"当前阶段: {stage_name}", 0)

    def _on_video_added(self, video: dict):
        """Start processing immediately after a video is added."""
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备处理...")
        self.statusBar().showMessage(f"已添加视频 {video['bilibili_id']}，开始处理...", 3000)
        
        worker = self.worker_manager.start_worker(
            video_id=video["id"],
            url=video["url"],
            title=video["title"],
            bilibili_id=video["bilibili_id"],
        )
        self._connect_worker_progress(worker)

    def _on_video_deleted(self, video_id: int):
        """Refresh content tabs when a video is deleted."""
        self.statusBar().showMessage(f"已删除视频 {video_id}", 2000)
        self.transcript_tab.refresh()
        self.summary_tab.refresh()

    @Slot(int, bool, str)
    def _on_worker_finished(self, video_id: int, success: bool, message: str):
        """Handle worker completion and refresh UI."""
        self.video_list_tab.refresh()
        self.transcript_tab.refresh()
        self.summary_tab.refresh()
        
        # Reset progress bar
        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText("完成")
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText("失败")
        
        self.statusBar().showMessage(message, 5000)
        
        if not success:
            QMessageBox.warning(self, "处理失败", message)
