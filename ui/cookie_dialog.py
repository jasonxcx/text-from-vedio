"""
Cookie配置弹窗 - 用于设置B站Cookie以解决412错误
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox, QCheckBox, QGroupBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from config import config


class CookieHelpDialog(QDialog):
    """Cookie获取帮助说明弹窗"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("如何获取B站Cookie")
        self.setMinimumSize(600, 500)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("获取B站Cookie详细步骤")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        content_layout.addWidget(title_label)
        
        # 方法一：浏览器插件（推荐）
        group1 = QGroupBox("方法一：使用浏览器插件（推荐）")
        group1_layout = QVBoxLayout(group1)
        
        steps1_text = (
            "1. 安装浏览器插件：Cookie-Editor 或 EditThisCookie\n"
            "   - Chrome: 在扩展商店搜索并安装\n"
            "   - Firefox: 在附加组件商店搜索并安装\n\n"
            "2. 登录 bilibili.com 网站\n\n"
            "3. 点击插件图标，找到以下关键Cookie：\n"
            "   - buvid3（最重要，解决412错误必需）\n"
            "   - SESSDATA（登录用户必需）\n"
            "   - bili_jct（CSRF令牌）\n\n"
            "4. 点击 Export 导出，选择 Netscape 格式\n\n"
            "5. 复制导出的内容，粘贴到Cookie配置框中"
        )
        steps1 = QLabel(steps1_text)
        steps1.setWordWrap(True)
        group1_layout.addWidget(steps1)
        content_layout.addWidget(group1)
        
        # 方法二：开发者工具
        group2 = QGroupBox("方法二：使用浏览器开发者工具")
        group2_layout = QVBoxLayout(group2)
        
        steps2_text = (
            "1. 登录 bilibili.com 网站\n\n"
            "2. 按 F12 打开开发者工具\n\n"
            "3. 切换到 Network(网络)标签\n\n"
            "4. 刷新页面，找到任意请求\n\n"
            "5. 点击请求，查看 Headers(请求头)\n\n"
            "6. 找到 Cookie 字段，复制完整内容\n\n"
            "7. 粘贴到Cookie配置框中\n\n"
            "注意：这种方式获取的是 name=value; name2=value2 格式"
        )
        steps2 = QLabel(steps2_text)
        steps2.setWordWrap(True)
        group2_layout.addWidget(steps2)
        content_layout.addWidget(group2)
        
        # 最小Cookie说明
        group3 = QGroupBox("最小Cookie要求")
        group3_layout = QVBoxLayout(group3)
        
        min_cookie_text = (
            "如果只需要解决412错误（无需登录视频），只需提供 buvid3 Cookie：\n\n"
            "示例格式（Netscape格式）：\n"
            ".bilibili.com\tTRUE\t/\tFALSE\t0\tbuvid3\t你的buvid3值\n\n"
            "示例格式（简单格式）：\n"
            "buvid3=你的buvid3值\n\n"
            "buvid3值类似：3416438-8579-9913-91AE-34EFA613959509732infoc"
        )
        min_cookie = QLabel(min_cookie_text)
        min_cookie.setWordWrap(True)
        group3_layout.addWidget(min_cookie)
        content_layout.addWidget(group3)
        
        # Cookie有效期说明
        group4 = QGroupBox("注意事项")
        group4_layout = QVBoxLayout(group4)
        
        notes_text = (
            "- Cookie有效期通常为30天，过期后需重新获取\n"
            "- 游客Cookie（buvid3）有效期较长\n"
            "- 登录Cookie（SESSDATA）有效期较短，需定期更新\n"
            "- 如果下载仍然失败，可能是IP被封，等待几分钟后重试\n"
            "- 不要分享你的登录Cookie给他人"
        )
        notes = QLabel(notes_text)
        notes.setWordWrap(True)
        group4_layout.addWidget(notes)
        content_layout.addWidget(group4)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class CookieConfigDialog(QDialog):
    """Cookie配置弹窗"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("B站Cookie配置")
        self.setMinimumSize(500, 400)
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 说明文字
        intro_label = QLabel(
            "配置B站Cookie可以解决下载时的 HTTP 412 Precondition Failed 错误。\n"
            "如果不配置，部分视频可能无法下载。"
        )
        intro_label.setWordWrap(True)
        intro_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(intro_label)
        
        # 使用自定义请求头选项
        self.use_headers_cb = QCheckBox("使用自定义HTTP请求头（推荐开启）")
        self.use_headers_cb.setChecked(True)
        self.use_headers_cb.setToolTip(
            "添加 Referer 和 User-Agent 请求头\n"
            "这是解决412错误的基础配置"
        )
        layout.addWidget(self.use_headers_cb)
        
        # Cookie输入区域
        cookie_group = QGroupBox("Cookie配置")
        cookie_layout = QVBoxLayout(cookie_group)
        
        # Cookie文本输入
        self.cookie_input = QTextEdit()
        placeholder_text = (
            "粘贴Cookie内容...\n\n"
            "支持两种格式：\n"
            "1. 简单格式: buvid3=xxx; SESSDATA=xxx\n"
            "2. Netscape格式: .bilibili.com TRUE / FALSE 0 buvid3 xxx"
        )
        self.cookie_input.setPlaceholderText(placeholder_text)
        self.cookie_input.setMinimumHeight(150)
        cookie_layout.addWidget(self.cookie_input)
        
        # 帮助按钮
        help_btn = QPushButton("如何获取Cookie？")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        help_btn.clicked.connect(self._show_help)
        cookie_layout.addWidget(help_btn)
        
        layout.addWidget(cookie_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
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
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
    def _load_settings(self):
        """加载当前配置"""
        cookies = config.get('download.cookies', '')
        if cookies:
            self.cookie_input.setText(cookies)
        use_headers = config.get('download.use_custom_headers', True)
        self.use_headers_cb.setChecked(use_headers)
        
    def _save_settings(self):
        """保存配置"""
        cookies = self.cookie_input.toPlainText().strip()
        use_headers = self.use_headers_cb.isChecked()
        
        config.set('download.cookies', cookies)
        config.set('download.use_custom_headers', use_headers)
        
        QMessageBox.information(
            self, 
            "保存成功", 
            "Cookie配置已保存。\n\n"
            "新配置将在下次下载视频时生效。"
        )
        self.accept()
        
    def _show_help(self):
        """显示帮助弹窗"""
        help_dialog = CookieHelpDialog(self)
        help_dialog.exec()