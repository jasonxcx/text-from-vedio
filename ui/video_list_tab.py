"""
Video List Tab - Displays all videos with management functionality
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView, QMessageBox,
    QDialog, QTextEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QColor

from app.database import (
    get_all_videos, add_video, update_video_status,
    delete_video, get_video_by_bilibili_id, get_video_with_details
)


class VideoListTab(QWidget):
    """Video list tab with table view and management controls"""

    video_added = Signal(dict)
    video_deleted = Signal(int)
    view_transcript = Signal(int)  # Request to view transcript for video
    view_summary = Signal(int)  # Request to view summary for video
    retry_video = Signal(int)  # Request to retry processing video

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._connect_signals()
        self._load_videos()

    def _setup_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Top control panel
        control_panel = self._create_control_panel()
        layout.addLayout(control_panel)

        # Video table
        self.table = self._create_video_table()
        layout.addWidget(self.table)

        # Bottom status bar
        status_bar = self._create_status_bar()
        layout.addLayout(status_bar)

    def _create_control_panel(self) -> QHBoxLayout:
        """Create top control panel with add video, filter, and refresh"""
        panel = QHBoxLayout()
        panel.setSpacing(10)

        # URL Input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 B 站视频 URL (如：https://www.bilibili.com/video/BV1xx411c7mD)")
        self.url_input.setMinimumWidth(400)
        panel.addWidget(self.url_input)

        # Add Video Button
        self.add_btn = QPushButton("添加视频")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
        """)
        panel.addWidget(self.add_btn)

        # Spacer
        panel.addStretch()

        # Status Filter
        filter_label = QLabel("状态筛选:")
        filter_label.setStyleSheet("font-weight: bold;")
        panel.addWidget(filter_label)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部", "等待中", "下载中", "转录中", "整理中", "已完成", "失败"])
        self.status_filter.setMinimumWidth(120)
        panel.addWidget(self.status_filter)

        # Refresh Button
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        panel.addWidget(self.refresh_btn)

        return panel

    def _create_video_table(self) -> QTableWidget:
        """Create video table widget"""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["ID", "标题", "B 站 ID", "时长", "状态", "操作"])

        # Header styling
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # Table styling
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
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
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #0066cc;
                font-weight: bold;
                color: #333;
            }
        """)
        
        # 设置行高
        table.verticalHeader().setDefaultSectionSize(45)

        # Enable editing for some columns if needed
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        return table

    def _create_status_bar(self) -> QHBoxLayout:
        """Create bottom status bar"""
        bar = QHBoxLayout()

        self.status_label = QLabel("共 0 个视频")
        self.status_label.setStyleSheet("font-weight: bold; color: #666;")
        bar.addWidget(self.status_label)

        bar.addStretch()

        # Delete button
        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        bar.addWidget(self.delete_btn)

        return bar

    def _connect_signals(self):
        """Connect widget signals to slots"""
        self.add_btn.clicked.connect(self._on_add_video)
        self.refresh_btn.clicked.connect(self._load_videos)
        self.status_filter.currentTextChanged.connect(self._load_videos)
        self.delete_btn.clicked.connect(self._on_delete_selected)

    @Slot()
    def _load_videos(self):
        """Load videos from database and populate table"""
        # Get filter status - 中文映射到英文数据库状态
        filter_text = self.status_filter.currentText()
        status_map = {
            "全部": None,
            "等待中": "pending",
            "下载中": "downloading",
            "转录中": "transcribing",
            "整理中": "summarizing",
            "已完成": "completed",
            "失败": "failed"
        }
        status = status_map.get(filter_text)

        # 状态中文映射（用于显示）
        status_cn_map = {
            "pending": "等待中",
            "downloading": "下载中",
            "transcribing": "转录中",
            "summarizing": "整理中",
            "completed": "已完成",
            "failed": "失败",
            "cancelled": "已取消"
        }

        # 状态颜色映射
        status_colors = {
            "pending": ("#ffc107", "#333"),      # 黄色背景
            "downloading": ("#17a2b8", "#fff"),  # 蓝色
            "transcribing": ("#6f42c1", "#fff"),  # 紫色
            "summarizing": ("#fd7e14", "#fff"),   # 橙色
            "completed": ("#28a745", "#fff"),    # 绿色
            "failed": ("#dc3545", "#fff"),       # 红色
            "cancelled": ("#6c757d", "#fff")     # 灰色
        }

        # Fetch videos
        videos = get_all_videos(status=status)

        # Populate table
        self.table.setRowCount(len(videos))
        for row, video in enumerate(videos):
            # ID
            id_item = QTableWidgetItem(str(video["id"]))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, id_item)

            # Title
            title_item = QTableWidgetItem(video["title"])
            self.table.setItem(row, 1, title_item)

            # Bilibili ID
            bilibili_item = QTableWidgetItem(video["bilibili_id"])
            bilibili_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, bilibili_item)

            # Duration
            duration = video["duration"] or 0
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration > 0 else "未知"
            duration_item = QTableWidgetItem(duration_str)
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, duration_item)

            # Status - 显示中文状态名称
            db_status = video["status"] or "pending"
            cn_status = status_cn_map.get(db_status, db_status)
            status_item = QTableWidgetItem(str(cn_status))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 设置状态颜色
            bg_color, fg_color = status_colors.get(db_status, ("#6c757d", "#fff"))
            status_item.setBackground(Qt.GlobalColor.transparent)
            # 使用委托或直接设置文本颜色和背景
            from PySide6.QtGui import QColor
            status_item.setForeground(QColor(fg_color))
            
            self.table.setItem(row, 4, status_item)

            # Actions - 多个操作按钮
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 3, 5, 3)
            actions_layout.setSpacing(8)

            # 查看详情按钮
            detail_btn = QPushButton("详情")
            detail_btn.setFixedSize(55, 32)
            detail_btn.setStyleSheet("""
                QPushButton {
                    background-color: #17a2b8;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #138496; }
            """)
            detail_btn.clicked.connect(lambda checked, v=video: self._show_video_detail(v))
            actions_layout.addWidget(detail_btn)

            # 根据状态显示不同按钮
            db_status = video["status"]
            
# 转录按钮（有转录内容时显示）
            if db_status == "completed":
                transcript_btn = QPushButton("转录")
                transcript_btn.setFixedSize(55, 32)
                transcript_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #28a745;
                        color: white;
                        border: none;
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #218838; }
                """)
                transcript_btn.clicked.connect(lambda checked, vid=video["id"]: self.view_transcript.emit(vid))
                actions_layout.addWidget(transcript_btn)
                
                # 摘要按钮（有摘要内容时显示）
                summary_btn = QPushButton("摘要")
                summary_btn.setMinimumWidth(50)
                summary_btn.setMinimumHeight(28)
                summary_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #fd7e14;
                        color: white;
                        border: none;
                        padding: 4px 10px;
                        border-radius: 3px;
                        font-size: 12px;
                        min-width: 50px;
                        min-height: 28px;
                    }
                    QPushButton:hover { background-color: #dc6502; }
                """)
                summary_btn.clicked.connect(lambda checked, vid=video["id"]: self.view_summary.emit(vid))
                actions_layout.addWidget(summary_btn)

            # 重试按钮（失败或已完成时显示）
            if db_status in ["failed", "completed"]:
                retry_btn = QPushButton("重试")
                retry_btn.setMinimumWidth(50)
                retry_btn.setMinimumHeight(28)
                retry_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffc107;
                        color: black;
                        border: none;
                        padding: 4px 10px;
                        border-radius: 3px;
                        font-size: 12px;
                        min-width: 50px;
                        min-height: 28px;
                    }
                    QPushButton:hover { background-color: #e0a800; }
                """)
                retry_btn.clicked.connect(lambda checked, vid=video["id"]: self.retry_video.emit(vid))
                actions_layout.addWidget(retry_btn)

            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.setFixedSize(55, 32)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #c82333; }
            """)
            delete_btn.clicked.connect(lambda checked, vid=video["id"]: self._delete_single_video(vid))
            actions_layout.addWidget(delete_btn)

            actions_widget.setLayout(actions_layout)
            self.table.setCellWidget(row, 5, actions_widget)

        # Update status label
        self.status_label.setText(f"共 {len(videos)} 个视频")

    @Slot()
    def _on_add_video(self):
        """Handle add video button click"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入 B 站视频 URL")
            return

        # Extract Bilibili ID from URL
        bilibili_id = self._extract_bilibili_id(url)
        if not bilibili_id:
            QMessageBox.warning(self, "警告", "无效的 B 站视频 URL 格式")
            return

        # Check if video already exists
        existing = get_video_by_bilibili_id(bilibili_id)
        if existing:
            QMessageBox.information(self, "提示", f"视频已存在：{existing['title']}")
            return

        # Add video to database
        try:
            video_id = add_video(
                bilibili_id=bilibili_id,
                title=f"视频 {bilibili_id}",  # Will be updated later
                url=url,
                duration=0,
                status="pending"
            )
            video = get_video_by_bilibili_id(bilibili_id)
            if video:
                self.video_added.emit(video)
            QMessageBox.information(self, "成功", f"视频添加成功！\n视频 ID: {video_id}")
            self.url_input.clear()
            self._load_videos()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加视频失败：{str(e)}")

    @Slot()
    def _show_video_detail(self, video: dict):
        """Show video detail dialog with links to transcript/summary"""
        # Get full video details including transcripts and summary
        video_details = get_video_with_details(video["id"])
        
        if not video_details:
            QMessageBox.warning(self, "错误", "无法获取视频详情")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("视频详情")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Basic info
        info_text = f"""
视频ID: {video['id']}
标题: {video['title']}
B站ID: {video['bilibili_id']}
URL: {video['url']}
时长: {video['duration']}秒
状态: {video['status']}
创建时间: {video['created_at']}
        """.strip()
        
        info_label = QLabel(info_text)
        info_label.setStyleSheet("padding: 10px; background-color: #f5f5f5; border-radius: 4px;")
        layout.addWidget(info_label)
        
        # Transcripts info
        transcripts = video_details.get("transcripts", []) if video_details else []
        transcript_count = len(transcripts)
        
        transcript_info = QLabel(f"转录片段: {transcript_count}个")
        layout.addWidget(transcript_info)
        
        if transcript_count > 0:
            transcript_btn = QPushButton("查看转录详情 →")
            transcript_btn.clicked.connect(lambda: (
                dialog.close(),
                self.view_transcript.emit(video["id"])
            ))
            layout.addWidget(transcript_btn)
        
        # Summary info
        summary = video_details.get("summary") if video_details else None
        
        if summary:
            summary_info = QLabel(f"摘要: 已生成 ({len(summary.get('summary_text', ''))}字符)")
            layout.addWidget(summary_info)
            
            summary_btn = QPushButton("查看摘要详情 →")
            summary_btn.clicked.connect(lambda: (
                dialog.close(),
                self.view_summary.emit(video["id"])
            ))
            layout.addWidget(summary_btn)
            
            # Show summary preview
            preview = QTextEdit()
            preview.setPlainText(summary.get('summary_text', '')[:200] + '...')
            preview.setMaximumHeight(100)
            preview.setReadOnly(True)
            layout.addWidget(QLabel("摘要预览:"))
            layout.addWidget(preview)
        else:
            summary_info = QLabel("摘要: 未生成")
            layout.addWidget(summary_info)
        
        # Close button
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def _delete_single_video(self, video_id: int):
        """Delete a single video with confirmation"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除此视频吗？\n相关转录和摘要数据也将被删除！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_video(video_id):
                self.video_deleted.emit(video_id)
                self._load_videos()
                QMessageBox.information(self, "完成", "视频已删除")

    @Slot()
    def _on_delete_selected(self):
        """Handle delete selected videos"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要删除的视频")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_rows)} 个视频吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        # Delete videos
        deleted_count = 0
        for index in selected_rows:
            row = index.row()
            video_id_item = self.table.item(row, 0)
            if video_id_item:
                try:
                    video_id = int(video_id_item.text())
                    if delete_video(video_id):
                        deleted_count += 1
                        self.video_deleted.emit(video_id)
                except (ValueError, Exception):
                    continue

        QMessageBox.information(self, "完成", f"成功删除 {deleted_count} 个视频")
        self._load_videos()

    def refresh(self):
        """Refresh the video table."""
        self._load_videos()

    def _extract_bilibili_id(self, url: str) -> str:
        """Extract Bilibili video ID from URL"""
        # Support various Bilibili URL formats
        # https://www.bilibili.com/video/BV1xx411c7mD
        # https://b23.tv/BV1xx411c7mD
        import re

        # Pattern for BV ID
        bv_pattern = r'(BV[a-zA-Z0-9]+)'
        match = re.search(bv_pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern for av ID (older format)
        av_pattern = r'av(\d+)'
        match = re.search(av_pattern, url, re.IGNORECASE)
        if match:
            return f"av{match.group(1)}"

        return ""
