# B站视频语音识别与摘要系统

纯Python桌面应用，支持B站视频抓取、Whisper语音识别（带时间戳）、AI摘要生成。

## 功能特性

- **视频提交**: 支持B站视频URL提交
- **语音识别**: 使用faster-whisper进行高精度语音转文本，带词级时间戳
- **内容摘要**: 支持多种AI提供商（Ollama/OpenAI/自定义API）生成视频摘要
- **桌面界面**: PySide6 Qt界面，视频列表、转录查看、摘要展示、设置配置
- **数据库存储**: SQLite本地存储，无需额外数据库服务
- **可配置**: 转录模型、设备、语言、AI摘要提供商等均可配置

## 技术栈

| 组件 | 技术 |
|------|------|
| UI框架 | PySide6 (Qt) |
| 语音识别 | faster-whisper |
| 摘要生成 | Ollama/OpenAI/自定义API |
| 数据库 | SQLite |
| 视频下载 | yt-dlp |

## 快速开始

### 前置要求

- Python 3.10+
- NVIDIA GPU（可选，用于CUDA加速）
- Ollama（可选，用于本地摘要）

### 1. 克隆项目

```bash
git clone <repository-url>
cd stock
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- PySide6 - 桌面界面
- faster-whisper - 语音识别
- yt-dlp - 视频下载
- ollama - 本地AI（可选）

### 3. 启动应用

```bash
# Windows
run.bat

# 或直接用Python
python main.py
```

### 4. 配置设置

点击"设置"Tab可配置：
- **转录设置**: 模型大小、设备(CUDA/CPU)、计算精度、语言
- **摘要设置**: 启用/禁用摘要、AI提供商、API配置

## 使用指南

### 添加视频

1. 在"视频列表"Tab输入B站视频URL
2. 点击"添加视频"按钮
3. 系统自动下载、转录、生成摘要

### 查看转录

1. 视频处理完成后，点击操作列的"转录"按钮
2. 或切换到"转录查看"Tab选择视频
3. 显示时间戳和文本两列，可复制完整文本

### 查看摘要

1. 点击操作列的"摘要"按钮
2. 或切换到"摘要展示"Tab选择视频
3. 显示摘要内容和关键点列表

### 配置AI摘要

支持三种AI提供商：

**Ollama（本地，免费）**
- baseUrl: `http://localhost:11434`
- model: `qwen2.5` 或其他
- apiKey: 留空

**OpenAI**
- baseUrl: `https://api.openai.com/v1`
- model: `gpt-3.5-turbo` 或其他
- apiKey: 你的OpenAI API密钥

**自定义API（兼容OpenAI格式）**
- baseUrl: 你的API地址
- model: 模型名称
- apiKey: API密钥

## 项目结构

```
stock/
├── app/
│   ├── database.py         # SQLite数据库操作
│   ├── worker.py           # 后台处理线程
│   └── logger_config.py    # 日志配置
├── services/
│   ├── downloader.py       # 视频下载(yt-dlp)
│   ├── transcriber.py      # 语音识别(faster-whisper)
│   └── summarizer.py       # 摘要生成
├── ui/
│   ├── main_window.py      # 主窗口
│   ├── video_list_tab.py   # 视频列表页
│   ├── transcript_tab.py   # 转录查看页
│   ├── summary_tab.py      # 摘要展示页
│   └── settings_tab.py     # 设置页
├── tests/                  # 测试文件
├── config.py               # 配置管理
├── config.json             # 用户配置文件
├── main.py                 # 入口文件
├── requirements.txt        # Python依赖
└── run.bat                 # Windows启动脚本
```

## 配置说明

配置文件自动创建在 `config.json`，包含：

### 转录配置

```jsonc
{
  "transcription": {
    "model": "large-v3",      // tiny/base/small/medium/large-v1/v2/v3
    "device": "cuda",         // cuda或cpu
    "compute_type": "auto",   // auto/float16/float32/int8
    "language": "auto",       // auto/zh/en/ja/...
    "chunk_duration": 600     // 分段时长(秒)
  }
}
```

### 摘要配置

```jsonc
{
  "summary": {
    "enabled": true,
    "provider": "ollama",     // ollama/openai/custom
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "qwen2.5",
      "api_key": ""
    },
    "openai": {
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-3.5-turbo",
      "api_key": "your-key"
    },
    "max_length": 500,
    "temperature": 0.7
  }
}
```

## 故障排查

### 常见问题

#### 1. 应用无法启动

**排查步骤**:

```bash
# 检查Python版本
python --version

# 检查依赖
pip list | grep -E "PySide6|faster-whisper|yt-dlp"

# 查看日志
cat logs/bilibili_asr_*.log
```

#### 2. 转录失败

**症状**: 任务状态显示"失败"

**可能原因**:
- CUDA驱动问题
- 模型文件未下载
- 内存不足

**解决方案**:
- 无GPU时将device改为`cpu`
- 使用更小的模型如`base`或`small`
- 查看日志`logs/`目录

#### 3. 摘要生成失败

**症状**: 转录成功但摘要为空

**排查步骤**:
- 检查设置Tab中的摘要配置
- 确认Ollama已运行（如使用本地）
- 检查API密钥（如使用OpenAI）
- 查看日志中的错误信息

#### 4. 视频下载失败

**症状**: 卡在"下载中"状态

**可能原因**:
- 网络问题
- 视频区域限制
- B站反爬

**解决方案**:
- 检查网络连接
- 尝试其他视频

### 日志查看

日志保存在 `logs/bilibili_asr_YYYYMMDD_HHMMSS.log`

```bash
# 查看最新日志
ls -lt logs/ | head -1

# Windows
type logs\bilibili_asr_*.log
```

### 性能优化

#### GPU内存不足

改用更小的模型或CPU：
```json
{
  "transcription": {
    "model": "base",
    "device": "cpu"
  }
}
```

#### 减少显存占用

使用int8量化：
```json
{
  "transcription": {
    "compute_type": "int8"
  }
}
```

## 开发指南

### 添加新功能

1. 修改 `services/` 下的服务模块
2. 更新 `ui/` 下的界面
3. 修改 `app/worker.py` 处理流程

### 运行测试

```bash
python tests/test_download.py
python tests/test_transcription.py
python tests/test_worker.py
```

## 许可证

MIT License

## 更新记录

### v1.0.0
- 纯Python桌面版初版
- 支持B站视频下载、转录、摘要
- PySide6界面
- SQLite数据库存储
- 支持多种AI摘要提供商