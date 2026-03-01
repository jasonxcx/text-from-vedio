# AGENTS.md - B站视频语音识别与摘要系统

## 项目概述

**项目类型**: 纯Python桌面应用  
**主要功能**: B站视频下载 → 语音识别转录(带时间戳) → AI摘要生成  
**技术栈**: PySide6(Qt) + faster-whisper + SQLite

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     PySide6 桌面界面                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │ 视频列表页  │  │ 转录查看页  │  │ 摘要展示页  │       │
│  └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   SQLite 数据库                            │
│           videos / transcripts / summaries                │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   核心处理模块                            │
│  downloader.py  →  transcriber.py  →  summarizer.py    │
│  (yt-dlp)         (faster-whisper)   (Ollama/OpenAI)    │
└─────────────────────────────────────────────────────────┘
```

## 模块说明

### UI层 (ui/)

| 文件 | 功能 |
|------|------|
| main_window.py | 主窗口，Tab切换，进度条，菜单 |
| video_list_tab.py | 视频列表、添加、删除、操作按钮 |
| transcript_tab.py | 转录查看（时间戳+文本两列） |
| summary_tab.py | 摘要展示（摘要+关键点） |
| settings_tab.py | 配置界面（转录+摘要设置） |

### 服务层 (services/)

| 文件 | 功能 | 外部依赖 |
|------|------|----------|
| downloader.py | 视频下载 | yt-dlp |
| transcriber.py | 语音识别转录 | faster-whisper |
| summarizer.py | 文本摘要 | ollama/httpx |

### 数据层 (app/)

| 文件 | 功能 |
|------|------|
| database.py | SQLite数据库操作 |
| worker.py | QThread后台处理 |
| logger_config.py | 日志配置 |

### 配置 (config.py)

- 使用 `config.json` 存储用户配置
- 支持环境变量覆盖
- 自动创建默认配置

## 处理流程

### 完整流程

```
1. 用户添加视频URL
   ↓
2. 保存到videos表（状态：pending）
   ↓
3. 启动Worker线程
   ↓
4. 下载视频（状态：downloading）
   ↓
5. 语音识别（状态：transcribing）
   - 保存到transcripts表
   ↓
6. 生成摘要（状态：summarizing，可选）
   - 保存到summaries表
   ↓
7. 完成（状态：completed）
```

### 状态流转

```
pending → downloading → transcribing → summarizing → completed
                                          ↓
                                        failed（任何步骤失败）
```

## 数据库Schema

### videos表

```sql
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bilibili_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### transcripts表

```sql
CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    text TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);
```

### summaries表

```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    summary_text TEXT NOT NULL,
    key_points TEXT,  -- JSON数组
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);
```

## 配置说明

### 配置文件位置

`config.json` - 自动创建在项目根目录

### 配置项

#### 转录配置

```json
{
  "transcription": {
    "model": "large-v3",      // 模型大小
    "device": "cuda",         // cuda或cpu
    "compute_type": "auto",   // auto/float16/float32/int8
    "language": "auto",       // auto/zh/en/ja/...
    "chunk_duration": 600     // 分段时长（秒）
  }
}
```

#### 摘要配置

```json
{
  "summary": {
    "enabled": true,
    "provider": "ollama",     // ollama/openai/custom
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "qwen2.5"
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

## 开发规范

### 代码风格

- 使用类型注解
- 使用f-string格式化
- 异常处理使用try-except
- 日志使用logging模块

### 文件组织

```
项目根目录/
├── app/              # 应用核心
├── services/         # 服务模块
├── ui/               # 界面
├── tests/            # 测试文件
├── logs/             # 日志（gitignore）
├── downloads/        # 下载（gitignore）
├── config.py         # 配置管理
├── config.json       # 用户配置
├── main.py           # 入口
└── requirements.txt  # 依赖
```

### 依赖管理

所有依赖在 `requirements.txt`：

```
PySide6>=6.5.0
faster-whisper>=1.0.0
yt-dlp>=2024.1.0
ollama>=0.1.0
```

## 注意事项

### 模型下载

faster-whisper模型自动下载到：`~/.cache/huggingface/`

### 离线模式

已配置 `HF_HUB_OFFLINE=1`，优先使用本地模型

### 线程安全

所有耗时操作在QThread中执行，通过信号与主线程通信

## 更新记录

### v1.0.0
- 初版发布
- PySide6桌面界面
- faster-whisper语音识别
- 支持Ollama/OpenAI摘要
- SQLite本地存储