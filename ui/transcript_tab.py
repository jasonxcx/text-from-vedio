"""
Transcription view tab with split layout
Features:
- Merge segments to reduce fragmentation
- Edit transcript text inline
- Regenerate AI summary
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QComboBox, QMessageBox, QApplication,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog
)
from PySide6.QtCore import Qt
from app.database import (
    get_all_videos, get_transcripts_by_video, 
    delete_transcripts_by_video, add_transcripts_batch,
    get_summary_by_video, delete_summary, add_summary,
    get_db
)
from services.summarizer import summarize_text
from config import config


class TranscriptTab(QWidget):
    """Tab for viewing video transcriptions with split timestamp/text layout"""
    
    def __init__(self):
        super().__init__()
        self.current_video_id = None
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
        
        # Merge button
        self.merge_button = QPushButton("合并选中片段")
        self.merge_button.setEnabled(False)
        self.merge_button.setToolTip("按住 Ctrl 或 Shift 多选片段，然后点击此按钮合并")
        self.merge_button.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        control_layout.addWidget(self.merge_button)
        
        # Regenerate summary button
        self.regenerate_button = QPushButton("✨ 重新生成摘要")
        self.regenerate_button.setEnabled(False)
        self.regenerate_button.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc6502;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        control_layout.addWidget(self.regenerate_button)
        
        self.copy_button = QPushButton("复制文本")
        self.copy_button.setEnabled(False)
        control_layout.addWidget(self.copy_button)
        
        main_layout.addLayout(control_layout)
        
        # Progress label
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.progress_label)
        
        # Selection hint
        self.selection_hint = QLabel("💡 提示：按住 Ctrl 点击可多选，或按住 Shift 选择连续片段")
        self.selection_hint.setStyleSheet("color: #6f42c1; font-size: 12px; font-weight: bold;")
        self.selection_hint.setVisible(False)
        main_layout.addWidget(self.selection_hint)
        
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
        # 启用多选（Ctrl/Shift + 点击或拖动选择）
        self.transcript_table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.transcript_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # 监听选择变化
        self.transcript_table.itemSelectionChanged.connect(self._on_selection_changed)
        
        main_layout.addWidget(self.transcript_table)
        
        # Status bar
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        main_layout.addWidget(self.status_label)
    
    def _connect_signals(self):
        self.video_combo.currentIndexChanged.connect(self._on_video_changed)
        self.copy_button.clicked.connect(self._copy_transcript)
        self.merge_button.clicked.connect(self._merge_segments)
        self.regenerate_button.clicked.connect(self._regenerate_summary)
        # 监听表格单元格变化，自动保存
        self.transcript_table.itemChanged.connect(self._on_item_changed)
    
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
            self.merge_button.setEnabled(False)
            self.regenerate_button.setEnabled(False)
            self.status_label.setText("就绪")
            self.current_video_id = None
            return
        
        self.current_video_id = video_id
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
            self.merge_button.setEnabled(False)
            self.regenerate_button.setEnabled(False)
            self.status_label.setText("状态：等待处理")
            return
        elif video['status'] in ['failed', 'cancelled']:
            self.progress_label.setText("❌ 视频处理失败")
            self.transcript_table.setRowCount(0)
            self.copy_button.setEnabled(False)
            self.merge_button.setEnabled(False)
            self.regenerate_button.setEnabled(False)
            self.status_label.setText("状态：失败")
            return
        
        transcripts = get_transcripts_by_video(video_id)
        
        if not transcripts:
            self.progress_label.clear()
            self.transcript_table.setRowCount(0)
            self.copy_button.setEnabled(False)
            self.merge_button.setEnabled(False)
            self.regenerate_button.setEnabled(False)
            self.status_label.setText("状态：完成 (无转录数据)")
            return
        
        self._display_transcripts(transcripts)
        self.progress_label.clear()
        self.copy_button.setEnabled(True)
        self.merge_button.setEnabled(True)
        
        # Check if summary exists
        summary = get_summary_by_video(video_id)
        self.regenerate_button.setEnabled(bool(summary))
        
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
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)  # Make time read-only
            self.transcript_table.setItem(i, 0, time_item)
            
            # Text column - make editable
            text_item = QTableWidgetItem(segment['text'])
            self.transcript_table.setItem(i, 1, text_item)
    
    def _format_timestamp(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _on_selection_changed(self):
        """Handle selection changes"""
        selected_indexes = self.transcript_table.selectedIndexes()
        # 提取唯一的行号
        selected_rows = set(index.row() for index in selected_indexes)
        selected_count = len(selected_rows)
        
        if selected_count >= 2:
            self.selection_hint.setText(f"已选中 {selected_count} 个片段，点击\"合并选中片段\"进行合并")
            self.selection_hint.setVisible(True)
        else:
            self.selection_hint.setVisible(False)
    
    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle table item changes and save to database"""
        if not self.current_video_id:
            return
        
        row = item.row()
        col = item.column()
        
        # 只保存文本列的变化（第 2 列，索引 1）
        if col != 1:
            return
        
        # 获取行号对应的 order_index
        # 在当前实现中，表格行号 = order_index
        order_index = row
        
        # 获取新的文本
        new_text = item.text().strip()
        
        # 更新数据库
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE transcripts SET text = ? WHERE video_id = ? AND order_index = ?",
                    (new_text, self.current_video_id, order_index)
                )
                conn.commit()
                
                self.status_label.setText("✓ 已保存")
                self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
                
                # 2 秒后重置状态
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, self._reset_status)
        except Exception as e:
            print(f"保存失败: {e}")
            self.status_label.setText(f"✗ 保存失败: {str(e)}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 12px;")
    
    def _merge_segments(self):
        """Merge selected segments manually"""
        if not self.current_video_id:
            return
        
        # 获取选中的行
        selected_indexes = sorted(set(index.row() for index in self.transcript_table.selectedIndexes()))
        
        if len(selected_indexes) < 2:
            QMessageBox.warning(self, "提示", "请至少选择 2 个片段进行合并\n\n提示：按住 Ctrl 或 Shift 可多选")
            return
        
        # 从数据库获取选中片段的详细信息
        with get_db() as conn:
            cursor = conn.cursor()
            # 使用 IN 查询获取所有选中的片段
            placeholders = ','.join('?' * len(selected_indexes))
            cursor.execute(
                f"SELECT id, start_seconds, end_seconds, text, order_index FROM transcripts WHERE video_id = ? AND order_index IN ({placeholders}) ORDER BY order_index",
                [self.current_video_id] + selected_indexes
            )
            selected_segments = [
                {
                    'id': row[0],
                    'start': row[1],
                    'end': row[2],
                    'text': row[3].strip(),
                    'order_index': row[4]
                }
                for row in cursor.fetchall()
            ]
        
        if len(selected_segments) < 2:
            QMessageBox.warning(self, "提示", "选择的片段不足 2 个")
            return
        
        # 合并片段
        merged_start = selected_segments[0]['start']
        merged_end = selected_segments[-1]['end']
        merged_text = ' '.join(seg['text'] for seg in selected_segments)
        
        # 确认合并
        total_duration = merged_end - merged_start
        reply = QMessageBox.question(
            self,
            "确认合并",
            f"即将合并 {len(selected_segments)} 个片段：\n\n"
            f"时间范围：{self._format_timestamp(merged_start)} - {self._format_timestamp(merged_end)}\n"
            f"总时长：{total_duration:.1f} 秒\n\n"
            f"文本预览：{merged_text[:100]}...\n\n"
            f"确定要合并吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # 删除选中的片段
            with get_db() as conn:
                cursor = conn.cursor()
                selected_ids = [seg['id'] for seg in selected_segments]
                placeholders = ','.join('?' * len(selected_ids))
                cursor.execute(
                    f"DELETE FROM transcripts WHERE id IN ({placeholders})",
                    selected_ids
                )
                
                # 在第一个片段的位置插入合并后的片段
                new_order_index = selected_segments[0]['order_index']
                cursor.execute(
                    """
                    INSERT INTO transcripts (video_id, start_seconds, end_seconds, text, order_index)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.current_video_id, merged_start, merged_end, merged_text, new_order_index)
                )
                
                # 更新后续片段的 order_index
                cursor.execute(
                    """
                    UPDATE transcripts 
                    SET order_index = order_index - ?
                    WHERE video_id = ? AND order_index > ?
                    """,
                    (len(selected_segments) - 1, self.current_video_id, new_order_index)
                )
                
                conn.commit()
            
            # 重新加载数据
            self._load_transcript(self.current_video_id)
            
            self.status_label.setText(f"✓ 已合并 {len(selected_segments)} 个片段")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: bold;")
            
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3000, self._reset_status)
            
        except Exception as e:
            error_msg = str(e)
            self.status_label.setText(f"✗ 合并失败：{error_msg}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 12px;")
            QMessageBox.critical(self, "错误", f"合并失败：\n{error_msg}")
    
    def _regenerate_summary(self):
        """Regenerate AI summary from transcript"""
        if not self.current_video_id:
            return
        
        # Get full transcript text
        full_text = ""
        for i in range(self.transcript_table.rowCount()):
            text_item = self.transcript_table.item(i, 1)
            if text_item:
                full_text += text_item.text() + " "
        
        if not full_text.strip():
            QMessageBox.warning(self, "警告", "没有转录文本，无法生成摘要")
            return
        
        # Confirm regeneration
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要重新生成摘要吗？\n\n这将覆盖现有的摘要内容。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Show progress
        self.status_label.setText("⏳ 正在生成摘要...")
        self.status_label.setStyleSheet("color: #fd7e14; font-size: 12px; font-weight: bold;")
        QApplication.processEvents()
        
        try:
            # Generate summary
            max_length = config.get('summary.max_length', 500)
            result = summarize_text(text=full_text, max_length=max_length)
            
            if not result or not isinstance(result, dict):
                raise ValueError("摘要生成失败：返回结果格式错误")
            
            summary_text = result.get("summary", "")
            key_points = result.get("key_points", [])
            
            if not summary_text:
                raise ValueError("摘要生成失败：返回内容为空")
            
            # Save to database
            delete_summary(self.current_video_id)
            add_summary(self.current_video_id, summary_text, key_points)
            
            self.status_label.setText("✓ 摘要已重新生成")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: bold;")
            
            QMessageBox.information(
                self,
                "成功",
                f"摘要已重新生成！\n\n字数：{len(summary_text)}\n关键点：{len(key_points)} 个"
            )
            
        except Exception as e:
            error_msg = str(e)
            self.status_label.setText(f"❌ 摘要生成失败：{error_msg}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 12px; font-weight: bold;")
            
            QMessageBox.critical(
                self,
                "错误",
                f"摘要生成失败：\n{error_msg}"
            )
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, self._reset_status)
    
    def _copy_transcript(self):
        transcript_text = ""
        for i in range(self.transcript_table.rowCount()):
            time_item = self.transcript_table.item(i, 0)
            text_item = self.transcript_table.item(i, 1)
            
            if time_item and text_item:
                time_text = time_item.text()
                text = text_item.text()
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
        video_id = self.current_video_id
        if video_id:
            transcripts = get_transcripts_by_video(video_id)
            self.status_label.setText(f"状态：完成 | 片段数：{len(transcripts)}")
        else:
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
