"""
Batch Add Dialog - Allows adding multiple video URLs at once
"""

import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QWidget, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor


class URLParseWorker(QThread):
    """Worker thread for parsing URLs in background"""
    
    parsing_finished = Signal(list)  # Emits list of parsed video info
    parsing_error = Signal(str)  # Emits error message
    
    def __init__(self, urls_text: str):
        super().__init__()
        self.urls_text = urls_text
    
    def run(self):
        """Parse URLs and extract video IDs"""
        try:
            results = []
            lines = self.urls_text.strip().split('\n')
            
            for line in lines:
                url = line.strip()
                if not url:
                    continue
                
                # Extract Bilibili ID
                bilibili_id = self._extract_bilibili_id(url)
                
                if bilibili_id:
                    results.append({
                        'url': url,
                        'bilibili_id': bilibili_id,
                        'title': f'视频 {bilibili_id}',  # Will be updated later
                        'duration': 0,
                        'status': 'pending',
                        'valid': True
                    })
                else:
                    results.append({
                        'url': url,
                        'bilibili_id': '',
                        'title': '无效 URL',
                        'duration': 0,
                        'status': 'error',
                        'valid': False,
                        'error': '无法解析 B 站视频 ID'
                    })
            
            self.parsing_finished.emit(results)
        except Exception as e:
            self.parsing_error.emit(str(e))
    
    def _extract_bilibili_id(self, url: str) -> str:
        """Extract Bilibili video ID from URL"""
        # Pattern for BV ID
        bv_pattern = r'(BV[a-zA-Z0-9]+)'
        match = re.search(bv_pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern for av ID (older format)
        av_pattern = r'av(\d+)'
        match = re.search(av_pattern, url, re.IGNORECASE)
        if match:
            return f'av{match.group(1)}'
        
        return ''


class BatchAddDialog(QDialog):
    """Dialog for batch adding video URLs"""
    
    videos_confirmed = Signal(list)  # Emits list of valid videos to add
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parsed_videos = []
        self._setup_ui()
        self._setup_worker()
    
    def _setup_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('批量添加视频')
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Input section
        input_label = QLabel('请输入 B 站视频 URL，每行一个：')
        input_label.setStyleSheet('font-weight: bold; font-size: 13px;')
        layout.addWidget(input_label)
        
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            '示例：\n'
            'https://www.bilibili.com/video/BV1xx411c7mD\n'
            'https://b23.tv/BV1yy411c7mD\n'
            'https://www.bilibili.com/video/av12345678'
        )
        self.url_input.setMinimumHeight(120)
        layout.addWidget(self.url_input)
        
        # Parse button
        self.parse_btn = QPushButton('解析 URL')
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        layout.addWidget(self.parse_btn)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)
        
        # Results table
        table_label = QLabel('解析结果预览：')
        table_label.setStyleSheet('font-weight: bold; font-size: 13px;')
        layout.addWidget(table_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['B 站 ID', '标题', '时长', '状态'])
        
        # Header styling
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Table styling
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
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
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        # Status label
        self.status_label = QLabel('共 0 个 URL (0 个有效，0 个无效)')
        self.status_label.setStyleSheet('font-weight: bold; color: #666;')
        layout.addWidget(self.status_label)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.add_btn = QPushButton('确认添加')
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.add_btn.setEnabled(False)
        button_layout.addWidget(self.add_btn)
        
        cancel_btn = QPushButton('取消')
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.parse_btn.clicked.connect(self._start_parsing)
        self.add_btn.clicked.connect(self._on_confirm)
    
    def _setup_worker(self):
        """Setup the URL parse worker"""
        self.worker = None
    
    def _start_parsing(self):
        """Start URL parsing in background thread"""
        urls_text = self.url_input.toPlainText().strip()
        if not urls_text:
            QMessageBox.warning(self, '警告', '请输入至少一个 URL')
            return
        
        # Disable UI during parsing
        self.parse_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Clear previous results
        self.table.setRowCount(0)
        self.parsed_videos = []
        
        # Start worker
        self.worker = URLParseWorker(urls_text)
        self.worker.parsing_finished.connect(self._on_parsing_finished)
        self.worker.parsing_error.connect(self._on_parsing_error)
        self.worker.start()
    
    def _on_parsing_finished(self, results: list):
        """Handle parsing completion"""
        # Restore UI
        self.parse_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # Store results
        self.parsed_videos = results
        
        # Populate table
        valid_count = 0
        invalid_count = 0
        
        for video in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # B 站 ID
            id_item = QTableWidgetItem(video['bilibili_id'])
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, id_item)
            
            # 标题
            title_item = QTableWidgetItem(video['title'])
            self.table.setItem(row, 1, title_item)
            
            # 时长
            duration = video['duration'] or 0
            duration_str = f'{duration // 60}:{duration % 60:02d}' if duration > 0 else '未知'
            duration_item = QTableWidgetItem(duration_str)
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, duration_item)
            
            # 状态
            if video['valid']:
                status_item = QTableWidgetItem('有效')
                status_item.setForeground(QColor('#28a745'))  # Green
                valid_count += 1
            else:
                status_item = QTableWidgetItem('无效')
                status_item.setForeground(QColor('#dc3545'))  # Red
                invalid_count += 1
            
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, status_item)
        
        # Update status label
        self.status_label.setText(f'共 {len(results)} 个 URL ({valid_count} 个有效，{invalid_count} 个无效)')
        
        # Enable add button if there are valid videos
        self.add_btn.setEnabled(valid_count > 0)
    
    def _on_parsing_error(self, error_message: str):
        """Handle parsing error"""
        # Restore UI
        self.parse_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(self, '解析错误', f'URL 解析失败：{error_message}')
    
    def _on_confirm(self):
        """Handle confirm button click"""
        # Filter valid videos
        valid_videos = [v for v in self.parsed_videos if v['valid']]
        
        if not valid_videos:
            QMessageBox.warning(self, '警告', '没有有效的 URL')
            return
        
        # Emit signal with valid videos
        self.videos_confirmed.emit(valid_videos)
        self.accept()
