# B站视频语音识别与摘要系统 (纯Python桌面版)

## TL;DR

> **快速Summary**: 纯Python桌面应用，B站视频抓取→WhisperX语音识别(带时间戳)→Ollama摘要→SQLite存储，PySide6界面
>
> **核心输出**:
> - PySide6 桌面界面
> - WhisperX 语音识别服务（带时间戳）
> - Ollama 本地摘要生成
> - SQLite 数据库存储
> - 可打包为 exe
>
> **预估工作量**: 20 个任务
> **并行执行**: YES - 3 waves

---

## Context

### 原始需求
用户要求创建B站视频语音识别与摘要系统，功能包括：
1. 抓取B站视频
2. 语音识别转换为带时间戳文本（第几分第几秒）
3. 视频内容摘要总结
4. 存入数据库

### 技术选型（已确认）
- **UI框架**: PySide6
- **语音识别**: WhisperX (Python)
- **摘要生成**: Ollama + Qwen2.5 (Python)
- **数据库**: SQLite
- **视频下载**: yt-dlp
- **许可**: LGPL (PySide6)

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      PySide6 桌面界面                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  视频列表页   │  │  转录查看页   │  │  摘要展示页   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │    SQLite 数据库       │
                    │  videos, transcripts,  │
                    │  summaries             │
                    └──────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    核心处理模块                              │
│  downloader.py  →  transcriber.py  →  summarizer.py      │
│  (yt-dlp)          (WhisperX)          (Ollama)           │
└─────────────────────────────────────────────────────────────┘
```

### 复用已有代码
- `python-service/services/downloader.py` - 可直接复用
- `python-service/services/transcriber.py` - 可直接复用
- `python-service/services/summarizer.py` - 可直接复用

---

## Work Objectives

### 核心目标
实现一个完整的B站视频处理桌面应用：
- 用户在界面提交B站URL → 点击处理 → WhisperX转录(带时间戳) → Ollama摘要 → SQLite存储 → 界面展示

### 具体交付物
- [x] PySide6 桌面界面
- [x] SQLite 数据库
- [x] 视频下载模块 (yt-dlp)
- [x] 语音识别模块 (WhisperX)
- [x] 摘要生成模块 (Ollama)
- [x] 可打包为 exe

### 定义完成
- [ ] 应用可启动并显示界面
- [ ] 可提交B站视频URL
- [ ] WhisperX可处理音频并输出带时间戳
- [ ] Ollama可生成文本摘要
- [ ] SQLite正确存储数据
- [ ] 界面可显示视频列表、转录、摘要

### 必须有
- 任务状态跟踪（pending/processing/completed/failed）
- 进度百分比反馈
- 转录结果带词级时间戳
- 摘要可查看

### 禁止有（Guardrails）
- 禁止同步处理长视频（会卡界面）
- 禁止直接存储原始视频文件
- 禁止在主线程执行耗时操作

---

## Verification Strategy

### 测试决策
- **Infrastructure exists**: Greenfield project
- **Automated tests**: 部分 (pytest)
- **Framework**: pytest

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (基础架构 - 3个任务):
├── T1: 项目初始化 (目录结构 + PySide6基础)
├── T2: SQLite数据库设计
└── T3: 核心模块复用 (downloader/transcriber/summarizer)

Wave 2 (桌面界面 - 5个任务):
├── T4: 主窗口框架
├── T5: 视频列表页面
├── T6: 转录查看页面
├── T7: 摘要展示页面
└── T8: 任务处理线程

Wave 3 (集成与打包 - 4个任务):
├── T9: 完整流程集成测试
├── T10: 错误处理和重试
├── T11: 打包配置 (PyInstaller)
└── T12: README文档
```

### Agent Dispatch Summary

- **Wave 1**: T1:quick, T2:quick, T3:unspecified-high
- **Wave 2**: T4:visual-engineering, T5:visual-engineering, T6:visual-engineering, T7:visual-engineering, T8:unspecified-high
- **Wave 3**: T9:deep, T10:quick, T11:quick, T12:writing

---

## TODOs

- [x] 1. 项目初始化和目录结构

  **What to do**:
  - 创建项目目录结构
  - 初始化 Python 虚拟环境
  - 安装 PySide6, whisperx, ollama, yt-dlp, sqlite3
  - 创建 pyproject.toml 或 setup.py

  **Must NOT do**:
  - 不创建不必要的文件

  **Acceptance Criteria**:
  - [ ] 目录结构清晰
  - [ ] requirements.txt 包含所有依赖
  - [ ] 可运行 `python main.py` 启动空窗口

  **QA Scenarios**:
  ```bash
  python main.py  # 启动应用，显示空窗口
  ```

- [ ] 2. SQLite 数据库设计

  **What to do**:
  - 设计数据库 Schema
  - videos 表: id, bilibili_id, title, url, duration, status, created_at
  - transcripts 表: id, video_id, start_seconds, end_seconds, text, order_index
  - summaries 表: id, video_id, summary_text, key_points, created_at
  - 实现 CRUD 操作

  **Must NOT do**:
  - 不存储原始视频文件

  **Acceptance Criteria**:
  - [ ] database.py 包含所有表定义
  - [ ] CRUD 操作可用

  **QA Scenarios**:
  ```bash
  python -c "from database import init_db; init_db(); print('OK')"
  ```

- [x] 3. 核心模块复用

  **What to do**:
  - 复用 python-service/services/downloader.py
  - 复用 python-service/services/transcriber.py
  - 复用 python-service/services/summarizer.py
  - 适配 SQLite 存储

  **Must NOT do**:
  - 不破坏原模块功能

  **Acceptance Criteria**:
  - [ ] downloader 可下载视频
  - [ ] transcriber 可转录音频(带时间戳)
  - [ ] summarizer 可生成摘要

  **QA Scenarios**:
  ```bash
  python -c "from services.downloader import download_video"
  python -c "from services.transcriber import transcribe_audio"
  python -c "from services.summarizer import summarize_text"
  ```

- [x] 4. 主窗口框架

  **What to do**:
  - 创建 PySide6 主窗口
  - 实现 Tab 切换 (列表/转录/摘要)
  - 配置窗口大小和标题

  **Must NOT do**:
  - 不在主线程执行耗时操作

  **Acceptance Criteria**:
  - [ ] 窗口可显示
  - [ ] Tab 切换正常

  **QA Scenarios**:
  ```bash
  python main.py  # 显示主窗口
  ```

- [ ] 5. 视频列表页面

  **What to do**:
  - 显示所有视频列表
  - 状态筛选 (全部/处理中/已完成)
  - 添加视频按钮
  - 刷新功能

  **Must NOT do**:
  - 不存储敏感信息

  **Acceptance Criteria**:
  - [ ] 列表正确显示
  - [ ] 可添加视频URL

  **QA Scenarios**:
  ```bash
  python main.py  # 测试添加视频
  ```

- [x] 6. 转录查看页面

  **What to do**:
  - 显示转录文本 (带时间戳)
  - 时间戳点击功能
  - 复制文本功能

  **Must NOT do**:
  - 不加载过大的转录文本

  **Acceptance Criteria**:
  - [ ] 转录文本正确显示
  - [ ] 时间戳可点击

  **QA Scenarios**:
  ```bash
  python main.py  # 测试查看转录
  ```

- [x] 7. 摘要展示页面

  **What to do**:
  - 显示摘要文本
  - 显示关键点
  - 复制功能

  **Must NOT do**:
  - 不截断过长的摘要

  **Acceptance Criteria**:
  - [ ] 摘要正确显示
  - [ ] 关键点列表可用

  **QA Scenarios**:
  ```bash
  python main.py  # 测试查看摘要
  ```

- [x] 8. 任务处理线程

  **What to do**:
  - 使用 QThread 处理耗时任务
  - 实现下载→转录→摘要流程
  - 进度更新信号
  - 错误处理

  **Must NOT do**:
  - 不在主线程处理

  **Acceptance Criteria**:
  - [ ] 任务在后台线程执行
  - [ ] 进度正确更新

  **QA Scenarios**:
  ```bash
  python main.py  # 测试完整流程
  ```

- [x] 9. 完整流程集成测试

  **What to do**:
  - 测试完整处理流程
  - 测试错误处理
  - 测试数据库存储

  **Must NOT do**:
  - 不在生产环境测试

  **Acceptance Criteria**:
  - [ ] 端到端流程可运行
  - [ ] 数据正确存储

  **QA Scenarios**:
  ```bash
  python main.py  # 提交测试视频
  ```

- [x] 10. 错误处理和重试

  **What to do**:
  - 实现重试机制
  - 友好的错误提示
  - 日志记录

  **Must NOT do**:
  - 不静默失败

  **Acceptance Criteria**:
  - [ ] 错误有提示
  - [ ] 可重试失败任务

  **QA Scenarios**:
  ```bash
  python main.py  # 测试错误处理
  ```

- [x] 12. README 文档

  **What to do**:
  - 创建打包配置
  - 包含必要资源文件
  - 测试 exe 生成

  **Must NOT do**:
  - 不包含不必要的文件

  **Acceptance Criteria**:
  - [ ] 可生成 exe
  - [ ] exe 可独立运行

  **QA Scenarios**:
  ```bash
  pyinstaller main.spec
  ./dist/main.exe
  ```

- [x] 12. README 文档

  **What to do**:
  - 编写使用说明
  - 包含安装步骤
  - 包含常见问题

  **Must NOT do**:
  - 不暴露敏感信息

  **Acceptance Criteria**:
  - [ ] README.md 完整

  **QA Scenarios**:
  ```bash
  cat README.md
  ```

---

## Success Criteria

### 验证命令
```bash
# 启动应用
python main.py

# 测试添加视频
# 1. 点击添加视频
# 2. 输入B站URL
# 3. 点击处理
# 4. 等待完成
# 5. 查看转录和摘要
```

### 最终检查清单
- [ ] 应用可启动并显示界面
- [ ] 可提交B站视频进行处理
- [ ] WhisperX正确转录音频(带时间戳)
- [ ] Ollama正确生成摘要
- [ ] SQLite正确存储数据
- [ ] 界面可显示所有结果
- [ ] 可打包为exe独立运行
