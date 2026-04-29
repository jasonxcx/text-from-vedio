"""
Settings Tab for configuration management
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QGroupBox, QMessageBox, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, Signal

from config import config
from ui.cookie_dialog import CookieConfigDialog


class SettingsTab(QWidget):
    """Settings tab with form-based interface"""
    
    settings_saved = Signal()
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        """Initialize the settings UI"""
        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        # Main widget inside scroll
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === Transcription Settings ===
        trans_group = QGroupBox("转录设置")
        trans_layout = QFormLayout(trans_group)
        trans_layout.setSpacing(10)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny", "tiny.en",
            "base", "base.en",
            "small", "small.en",
            "medium", "medium.en",
            "large-v1", "large-v2", "large-v3"
        ])
        self.model_combo.setToolTip("faster-whisper模型选择\nlarge-v3最准确但需要更多显存")
        trans_layout.addRow("转录模型:", self.model_combo)
        
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cuda", "cpu"])
        self.device_combo.setToolTip("CUDA使用显卡加速\nCPU速度较慢但无需显卡")
        trans_layout.addRow("运行设备:", self.device_combo)
        
        self.compute_type_combo = QComboBox()
        self.compute_type_combo.addItems(["auto", "float16", "float32", "int8"])
        self.compute_type_combo.setToolTip("auto自动选择\nfloat16适合CUDA\nfloat32适合CPU")
        trans_layout.addRow("计算精度:", self.compute_type_combo)
        
        self.language_combo = QComboBox()
        lang_items = [
            ("自动检测", "auto"),
            ("中文", "zh"),
            ("英文", "en"),
            ("日语", "ja"),
            ("韩语", "ko"),
            ("法语", "fr"),
            ("德语", "de"),
        ]
        for name, code in lang_items:
            self.language_combo.addItem(name, code)
        trans_layout.addRow("转录语言:", self.language_combo)
        
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(60, 3600)
        self.chunk_spin.setSingleStep(60)
        self.chunk_spin.setSuffix(" 秒")
        self.chunk_spin.setToolTip("长音频分段时长，内存不足可减小")
        trans_layout.addRow("分段时长:", self.chunk_spin)
        
        layout.addWidget(trans_group)
        
        # === Summary Settings ===
        summary_group = QGroupBox("摘要设置")
        summary_layout = QFormLayout(summary_group)
        summary_layout.setSpacing(10)
        
        self.summary_enabled = QCheckBox("启用摘要生成")
        self.summary_enabled.stateChanged.connect(self._on_summary_enabled_changed)
        summary_layout.addRow(self.summary_enabled)
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["ollama", "openai", "custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        summary_layout.addRow("AI服务商:", self.provider_combo)
        
        # Provider-specific settings container
        self.provider_widget = QWidget()
        self.provider_layout = QFormLayout(self.provider_widget)
        self.provider_layout.setContentsMargins(0, 0, 0, 0)
        
        # Common fields for all providers
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("API服务地址")
        self.provider_layout.addRow("服务地址:", self.base_url_input)
        
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("模型名称")
        self.provider_layout.addRow("模型名称:", self.model_input)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("API密钥（如需要）")
        self.provider_layout.addRow("API密钥:", self.api_key_input)
        
        summary_layout.addRow(self.provider_widget)
        
        # Generation parameters
        self.max_length_spin = QSpinBox()
        self.max_length_spin.setRange(100, 2000)
        self.max_length_spin.setSingleStep(100)
        self.max_length_spin.setSuffix(" 字符")
        summary_layout.addRow("摘要长度:", self.max_length_spin)
        
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        summary_layout.addRow("随机性:", self.temperature_spin)
        
        layout.addWidget(summary_group)

        # === Download Settings ===
        download_group = QGroupBox("下载设置")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(10)
        
        download_info = QLabel("B站视频下载配置，用于解决 HTTP 412 错误")
        download_info.setStyleSheet("color: #666; font-size: 12px;")
        download_layout.addWidget(download_info)
        
        cookie_btn = QPushButton("配置B站Cookie")
        cookie_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        cookie_btn.clicked.connect(self._open_cookie_dialog)
        download_layout.addWidget(cookie_btn)
        
        # Cookie状态提示
        self.cookie_status_label = QLabel()
        self._update_cookie_status()
        download_layout.addWidget(self.cookie_status_label)
        
        layout.addWidget(download_group)

        # === Task Queue Concurrency Settings ===
        queue_group = QGroupBox("任务并发设置")
        queue_layout = QFormLayout(queue_group)
        queue_layout.setSpacing(10)

        self.download_concurrency_spin = QSpinBox()
        self.download_concurrency_spin.setRange(1, 10)
        self.download_concurrency_spin.setToolTip("同时下载的视频数量\n网络带宽充足时可提高")
        queue_layout.addRow("下载并发数:", self.download_concurrency_spin)

        self.transcribe_concurrency_spin = QSpinBox()
        self.transcribe_concurrency_spin.setRange(1, 1)
        self.transcribe_concurrency_spin.setValue(1)
        self.transcribe_concurrency_spin.setEnabled(False)
        self.transcribe_concurrency_spin.setToolTip("转录必须单线程（GPU显存限制）")
        queue_layout.addRow("转录并发数:", self.transcribe_concurrency_spin)

        self.summary_concurrency_spin = QSpinBox()
        self.summary_concurrency_spin.setRange(1, 10)
        self.summary_concurrency_spin.setToolTip("同时生成摘要的数量\nCPU和内存充足时可提高")
        queue_layout.addRow("摘要并发数:", self.summary_concurrency_spin)

        layout.addWidget(queue_group)

        # === Save Button ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        scroll.setWidget(main_widget)
        
        # Set this tab's layout
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        
    def _on_summary_enabled_changed(self, state):
        """Handle summary enabled checkbox change"""
        enabled = state == Qt.CheckState.Checked.value
        self.provider_widget.setEnabled(enabled)
        self.max_length_spin.setEnabled(enabled)
        self.temperature_spin.setEnabled(enabled)
        
    def _on_provider_changed(self, provider: str):
        """Handle provider combo change - load defaults"""
        # Load default values for the selected provider
        if provider == 'ollama':
            self.base_url_input.setText(config.get('summary.ollama.base_url', 'http://localhost:11434'))
            self.model_input.setText(config.get('summary.ollama.model', 'qwen2.5'))
            self.api_key_input.setText('')
            self.api_key_input.setEnabled(False)
        elif provider == 'openai':
            self.base_url_input.setText(config.get('summary.openai.base_url', 'https://api.openai.com/v1'))
            self.model_input.setText(config.get('summary.openai.model', 'gpt-3.5-turbo'))
            self.api_key_input.setText(config.get('summary.openai.api_key', ''))
            self.api_key_input.setEnabled(True)
        elif provider == 'custom':
            self.base_url_input.setText(config.get('summary.custom.base_url', ''))
            self.model_input.setText(config.get('summary.custom.model', ''))
            self.api_key_input.setText(config.get('summary.custom.api_key', ''))
            self.api_key_input.setEnabled(True)
        
    def _load_settings(self):
        """Load settings from config"""
        # Transcription
        self.model_combo.setCurrentText(config.get('transcription.model', 'large-v3'))
        self.device_combo.setCurrentText(config.get('transcription.device', 'cuda'))
        self.compute_type_combo.setCurrentText(config.get('transcription.compute_type', 'auto'))
        
        lang = config.get('transcription.language', 'auto')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == lang:
                self.language_combo.setCurrentIndex(i)
                break
        
        self.chunk_spin.setValue(config.get('transcription.chunk_duration', 600))
        
        # Summary
        self.summary_enabled.setChecked(config.get('summary.enabled', True))
        self.provider_combo.setCurrentText(config.get('summary.provider', 'ollama'))
        self._on_provider_changed(self.provider_combo.currentText())
        
        self.max_length_spin.setValue(config.get('summary.max_length', 500))
        self.temperature_spin.setValue(config.get('summary.temperature', 0.7))
        
        # Update enabled state
        self._on_summary_enabled_changed(self.summary_enabled.checkState().value)

        # Queue concurrency settings
        self.download_concurrency_spin.setValue(config.get('queue.download.max_concurrency', 3))
        self.summary_concurrency_spin.setValue(config.get('queue.summary.max_concurrency', 3))
        
    def _save_settings(self):
        """Save settings to config"""
        try:
            # Transcription
            config.set('transcription.model', self.model_combo.currentText())
            config.set('transcription.device', self.device_combo.currentText())
            config.set('transcription.compute_type', self.compute_type_combo.currentText())
            config.set('transcription.language', self.language_combo.currentData())
            config.set('transcription.chunk_duration', self.chunk_spin.value())
            
            # Summary
            config.set('summary.enabled', self.summary_enabled.isChecked())
            config.set('summary.provider', self.provider_combo.currentText())
            
            provider = self.provider_combo.currentText()
            config.set(f'summary.{provider}.base_url', self.base_url_input.text())
            config.set(f'summary.{provider}.model', self.model_input.text())
            if provider != 'ollama':
                config.set(f'summary.{provider}.api_key', self.api_key_input.text())
            
            config.set('summary.max_length', self.max_length_spin.value())
            config.set('summary.temperature', self.temperature_spin.value())

            # Queue concurrency settings
            config.set('queue.download.max_concurrency', self.download_concurrency_spin.value())
            config.set('queue.summary.max_concurrency', self.summary_concurrency_spin.value())

            self.settings_saved.emit()
            QMessageBox.information(self, "保存成功", "设置已保存，新设置将在下次处理任务时生效")
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存设置时出错:\n{str(e)}")
            
    def refresh(self):
        """Refresh settings (reload from config)"""
        self._load_settings()
        
    def _open_cookie_dialog(self):
        """打开Cookie配置弹窗"""
        dialog = CookieConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_cookie_status()
            
    def _update_cookie_status(self):
        """更新Cookie状态提示"""
        cookies = config.get('download.cookies', '')
        use_headers = config.get('download.use_custom_headers', True)
        
        if cookies:
            self.cookie_status_label.setText("✓ Cookie已配置")
            self.cookie_status_label.setStyleSheet("color: #28a745;")
        elif use_headers:
            self.cookie_status_label.setText("⚠ 仅使用自定义请求头（可能无法解决412错误）")
            self.cookie_status_label.setStyleSheet("color: #ffc107;")
        else:
            self.cookie_status_label.setText("✗ 未配置Cookie和请求头")
            self.cookie_status_label.setStyleSheet("color: #dc3545;")