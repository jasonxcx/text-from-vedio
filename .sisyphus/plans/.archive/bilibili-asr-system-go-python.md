# B站视频语音识别与摘要系统

## TL;DR

> **快速Summary**: 完整实现B站视频抓取、语音识别转文本（带时间戳）、视频摘要生成的Web系统。Go后端+Gin框架，Python WhisperX语音识别，Ollama+Qwen2.5摘要生成，PostgreSQL存储，React前端。
>
> **核心输出**:
> - Go REST API服务 (Gin框架)
> - Python语音识别微服务 (WhisperX)
> - Python摘要生成服务 (Ollama)
> - React Web管理界面
> - PostgreSQL数据库Schema
> - Docker Compose一键部署
>
> **预估工作量**: 大型 (XL)
> **并行执行**: YES - 4 waves
> **关键路径**: 基础设施 → 核心服务 → 前端 → 集成

---

## Context

### 原始需求
用户要求创建B站视频语音识别与摘要系统，功能包括：
1. 抓取B站视频
2. 语音识别转换为带时间戳文本（第几分第几秒）
3. 录入PostgreSQL数据库
4. 视频内容摘要总结

### 技术选型（已确认）
- **后端语言**: Go
- **Web框架**: Gin
- **前端框架**: React + Vite + Element Plus
- **语音识别**: WhisperX (Python)
- **摘要生成**: Ollama + Qwen2.5 (Python)
- **数据库**: PostgreSQL
- **任务队列**: Redis
- **部署**: Docker Compose

### Metis审查发现的关键改进
1. **任务队列**: 语音识别是耗时操作，需Redis异步队列
2. **GPU调度**: WhisperX和Ollama共享GPU需时间片管理
3. **数据库Schema**: 需定义videos/tasks/segments/summaries表
4. **Cookie管理**: B站下载需要认证Cookie存储

---

## Work Objectives

### 核心目标
实现一个完整的B站视频处理流水线：
- 用户提交B站URL → 后端验证入队 → Python Worker处理 → 结果存储 → 前端展示

### 具体交付物
- [x] Go API服务 (Gin)
- [x] Python WhisperX服务
- [x] Python Ollama摘要服务
- [x] PostgreSQL数据库Schema
- [x] Redis任务队列
- [x] React Web界面
- [x] Docker Compose部署配置
- [x] 进度轮询和状态查询API

### 定义完成
- [ ] Go服务可启动并响应API请求
- [ ] Python WhisperX可处理音频并输出带时间戳JSON
- [ ] Python Ollama可生成文本摘要
- [ ] 前端可查看视频列表、播放进度、查看转录和摘要
- [ ] Docker Compose可一键启动所有服务

### 必须有
- 任务状态跟踪（pending/processing/completed/failed）
- 进度百分比反馈
- 转录结果带词级时间戳
- 摘要可查看

### 禁止有（Guardrails）
- 禁止同步处理长视频（会超时）
- 禁止直接存储原始视频文件（只存元数据）
- 禁止在前端暴露数据库连接信息

---

## Verification Strategy

### 测试决策
- **Infrastructure exists**: NO - Greenfield project
- **Automated tests**: 部分 (Go单元测试 + Python pytest)
- **Framework**: Go: standard library testing; Python: pytest
- **TDD**: NO (new project - tests after implementation)

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

- **Go Backend**: 使用Bash直接调用curl测试API
- **Python Services**: 使用Bash直接调用curl测试HTTP/gRPC
- **Frontend**: 使用Playwright进行浏览器测试
- **Integration**: 使用Bash执行docker-compose测试

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (基础设施 - 并行6个任务):
├── T1: 项目初始化 + Docker配置
├── T2: PostgreSQL Schema设计
├── T3: Redis任务队列设计
├── T4: Go项目结构和基础路由
├── T5: Python服务基础架构 (FastAPI)
└── T6: 前端项目初始化

Wave 2 (核心服务 - 可并行):
├── T7: Go API - 视频提交和状态查询
├── T8: Python - yt-dlp视频下载模块
├── T9: Python - WhisperX语音识别服务
├── T10: Go - 数据库模型 (GORM)
└── T11: Python - Ollama摘要生成服务

Wave 3 (前后端集成):
├── T12: Go - 完整API端点实现
├── T13: React - 视频列表页面
├── T14: React - 视频详情和转录页面
├── T15: React - 摘要展示组件
└── T16: Python - Worker任务处理逻辑

Wave 4 (验证与部署):
├── T17: 端到端集成测试
├── T18: 前端UI优化
├── T19: Docker Compose优化
└── T20: 部署文档
```

### Dependency Matrix

- **T1**: — — T2-T6
- **T2**: T1 — T10, T17
- **T3**: T1 — T7, T16
- **T4**: T1 — T7, T12
- **T5**: T1 — T8, T9, T11
- **T6**: T1 — T13-T15
- **T7**: T3, T4 — T12, T17
- **T8**: T5 — T16
- **T9**: T5 — T16
- **T10**: T2 — T12
- **T11**: T5 — T16
- **T12**: T4, T7, T10 — T17
- **T13**: T6 — T14, T15
- **T14**: T13 — T17
- **T15**: T13 — T17
- **T16**: T8, T9, T11 — T17
- **T17**: T12, T14, T15, T16 — T18, T19
- **T18**: T17 — T20
- **T19**: T17 — T20

### Agent Dispatch Summary

- **Wave 1**: **6** — T1:quick, T2:quick, T3:quick, T4:quick, T5:quick, T6:visual-engineering
- **Wave 2**: **5** — T7:quick, T8:unspecified-high, T9:unspecified-high, T10:quick, T11:unspecified-high
- **Wave 3**: **5** — T12:quick, T13:visual-engineering, T14:visual-engineering, T15:visual-engineering, T16:unspecified-high
- **Wave 4**: **4** — T17:deep, T18:visual-engineering, T19:quick, T20:writing
- **Final**: **4** — F1:oracle, F2:unspecified-high, F3:unspecified-high, F4:deep

---

## TODOs

- [x] 1. 项目初始化和 Docker 配置

  **What to do**:
  - 创建项目目录结构
  - 初始化Go模块 (go mod init)
  - 创建Python虚拟环境
  - 编写 docker-compose.yml (Go/Python/PostgreSQL/Redis/前端)
  - 创建 .env.example 配置文件

  **Must NOT do**:
  - 不在docker-compose中硬编码密码

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 初始化任务，文件创建为主
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - docker: 本地已有compose文件，暂不需要

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2-T6)
  - **Blocks**: T7-T11
  - **Blocked By**: None (can start immediately)

  **References**:
  - Go project structure: `https://github.com/golang-standards/project-layout` - 标准Go项目布局
  - Docker Compose best practices: `https://docs.docker.com/compose/compose-file/` - compose文件规范

  **Acceptance Criteria**:
  - [ ] docker-compose config 验证通过
  - [ ] go mod tidy 无错误
  - [ ] .env.example 包含所有必需环境变量

  **QA Scenarios**:

  Scenario: Docker Compose验证
    Tool: Bash
    Preconditions: docker-compose.yml存在
    Steps:
      1. docker-compose config --quiet
    Expected Result: 无错误输出
    Evidence: .sisyphus/evidence/t1-docker-validate.txt

  Scenario: Go模块初始化
    Tool: Bash
    Preconditions: go.mod不存在
    Steps:
      1. go mod init github.com/bilibili-asr/system
      2. go mod tidy
    Expected Result: go.mod和go.sum创建成功
    Evidence: .sisyphus/evidence/t1-go-mod.txt

- [x] 2. PostgreSQL 数据库 Schema 设计

  **What to do**:
  - 设计并创建数据库Schema (migrations目录)
  - videos表: id, bilibili_id, title, duration, status, created_at
  - transcription_tasks表: id, video_id, status, progress, model_name, error
  - transcript_segments表: id, task_id, start_seconds, end_seconds, text, speaker, order
  - video_summaries表: id, video_id, summary_text, key_points, model_name
  - 使用golang-migrate管理迁移

  **Must NOT do**:
  - 不在代码中存储数据库密码

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 数据库schema定义，DDL为主
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T3-T6)
  - **Blocks**: T10
  - **Blocked By**: T1

  **References**:
  - golang-migrate: `https://github.com/golang-migrate/migrate` - Go数据库迁移工具
  - PostgreSQL best practices: `https://www.postgresql.org/docs/` - 官方文档

  **Acceptance Criteria**:
  - [ ] migrations/001_init.sql 存在
  - [ ] 包含videos, transcription_tasks, transcript_segments, video_summaries表
  - [ ] 包含必要的索引

  **QA Scenarios**:

  Scenario: Schema语法验证
    Tool: Bash
    Preconditions: migrations文件存在
    Steps:
      1. psql -h localhost -U postgres -c "SELECT 1" 2>/dev/null || echo "DB not running - syntax only"
    Expected Result: 连接成功或明确提示仅语法检查
    Evidence: .sisyphus/evidence/t2-schema.txt

- [x] 3. Redis 任务队列设计

  **What to do**:
  - 设计任务队列结构
  - 定义任务状态: pending, processing, completed, failed
  - 设计任务数据结构: id, video_url, model_name, priority, created_at
  - 创建队列操作封装 (Go Redis客户端)

  **Must NOT do**:
  - 禁止存储敏感信息在队列中

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 队列设计与封装
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T4-T6)
  - **Blocks**: T7
  - **Blocked By**: T1

  **References**:
  - go-redis: `https://github.com/redis/go-redis` - Go Redis客户端
  - Redis Queue patterns: `https://redis.io/docs/data-types/streams/` - Redis流队列

  **Acceptance Criteria**:
  - [ ] pkg/queue/queue.go 封装完成
  - [ ] 包含Enqueue, Dequeue, GetStatus方法
  - [ ] 单元测试覆盖基本功能

  **QA Scenarios**:

  Scenario: Queue包编译
    Tool: Bash
    Preconditions: queue.go存在
    Steps:
      1. cd go-api && go build ./...
    Expected Result: 无编译错误
    Evidence: .sisyphus/evidence/t3-queue-build.txt

- [x] 4. Go 项目结构和基础路由

  **What to do**:
  - 创建标准Go项目结构 (cmd/, internal/, pkg/)
  - 创建Gin基础路由 (main.go, router.go)
  - 实现/health健康检查端点
  - 实现基本的错误处理中间件

  **Must NOT do**:
  - 不在代码中硬编码配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Go基础架构
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T3, T5, T6)
  - **Blocks**: T7
  - **Blocked By**: T1

  **References**:
  - Gin: `https://gin-gonic.com/` - Go Web框架
  - Go project layout: `https://github.com/golang-standards/project-layout`

  **Acceptance Criteria**:
  - [ ] go-api/main.go 可编译运行
  - [ ] GET /health 返回200
  - [ ] 基础中间件已配置 (logger, recovery)

  **QA Scenarios**:

  Scenario: Go服务启动测试
    Tool: Bash
    Preconditions: Go服务代码存在
    Steps:
      1. cd go-api && go build -o server .
      2. timeout 5 ./server || true
    Expected Result: 编译成功，服务尝试启动
    Evidence: .sisyphus/evidence/t4-go-build.txt

- [x] 5. Python 服务基础架构

  **What to do**:
  - 创建Python微服务目录结构
  - 创建FastAPI基础服务
  - 实现/health端点
  - 创建yt-dlp, whisperx, ollama的封装模块

  **Must NOT do**:
  - 不在代码中硬编码API密钥

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Python基础架构搭建
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T4, T6)
  - **Blocks**: T8, T9, T11
  - **Blocked By**: T1

  **References**:
  - FastAPI: `https://fastapi.tiangolo.com/` - Python Web框架
  - WhisperX: `https://github.com/m-bain/whisperX` - 语音识别
  - Ollama Python: `https://github.com/ollama/ollama-python` - Ollama客户端

  **Acceptance Criteria**:
  - [ ] python-service/main.py 可运行
  - [ ] /health 端点返回200
  - [ ] 包含基本依赖 (requirements.txt)

  **QA Scenarios**:

  Scenario: Python服务健康检查
    Tool: Bash
    Preconditions: Python服务代码存在
    Steps:
      1. cd python-service && pip install -r requirements.txt --quiet
      2. python -c "import fastapi, whisperx, ollama; print('OK')"
    Expected Result: 输出OK
    Evidence: .sisyphus/evidence/t5-python-deps.txt

- [x] 6. 前端项目初始化

  **What to do**:
  - 使用Vite创建React项目
  - 安装Element Plus和Pinia
  - 创建基础页面结构
  - 配置API代理 (vite.config.ts)

  **Must NOT do**:
  - 不使用复杂的UI库

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 前端初始化和配置
  - **Skills**: ["frontend-ui-ux"]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T5)
  - **Blocks**: T13-T15
  - **Blocked By**: T1

  **References**:
  - Vite: `https://vitejs.dev/` - 构建工具
  - Element Plus: `https://element-plus.org/` - UI组件库
  - React: `https://react.dev/` - 前端框架

  **Acceptance Criteria**:
  - [ ] npm create vite@latest 成功
  - [ ] npm install 完成
  - [ ] npm run dev 可启动

  **QA Scenarios**:

  Scenario: 前端项目构建
    Tool: Bash
    Preconditions: package.json存在
    Steps:
      1. cd frontend && npm install
      2. npm run build
    Expected Result: 构建成功
    Evidence: .sisyphus/evidence/t6-frontend-build.txt

- [x] 7. Go API - 视频提交和状态查询

  **What to do**:
  - POST /api/videos - 提交视频URL，返回task_id
  - GET /api/videos/:id - 获取视频信息和状态
  - GET /api/videos/:id/transcript - 获取转录结果
  - GET /api/videos/:id/summary - 获取摘要结果
  - 与Redis队列集成

  **Must NOT do**:
  - 禁止同步处理视频下载（会超时）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Go API实现
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T8-T11)
  - **Blocks**: T12
  - **Blocked By**: T3, T4

  **References**:
  - Gin routing: `https://gin-gonic.com/docs/examples/routing/` - 路由示例
  - REST API design: `https://restfulapi.net/` - REST最佳实践

  **Acceptance Criteria**:
  - [ ] POST /api/videos 返回task_id
  - [ ] GET /api/videos/:id 返回视频状态
  - [ ] 正确集成Redis队列

  **QA Scenarios**:

  Scenario: API端点测试
    Tool: Bash
    Preconditions: Go服务运行
    Steps:
      1. curl -X POST http://localhost:8080/api/videos -d '{"url":"BV1xx411c7mD"}'
      2. curl http://localhost:8080/api/videos/{id}
    Expected Result: 返回有效JSON响应
    Evidence: .sisyphus/evidence/t7-api-test.txt

- [x] 8. Python - yt-dlp 视频下载模块

  **What to do**:
  - 实现download_video(url, output_path)函数
  - 提取音频流 (--extract-audio)
  - 支持进度回调
  - 处理下载错误和重试

  **Must NOT do**:
  - 禁止存储原始视频文件

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 视频下载模块实现
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T7, T9-T11)
  - **Blocks**: T16
  - **Blocked By**: T5

  **References**:
  - yt-dlp: `https://github.com/yt-dlp/yt-dlp` - 视频下载工具
  - yt-dlp Python: `https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/__init__.py` - Python API

  **Acceptance Criteria**:
  - [ ] download_video函数可下载B站视频
  - [ ] 可提取音频文件
  - [ ] 支持进度回调

  **QA Scenarios**:

  Scenario: 视频下载测试
    Tool: Bash
    Preconditions: ffmpeg已安装
    Steps:
      1. cd python-service && python -c "from services.downloader import download_video; print('OK')"
    Expected Result: 模块导入成功
    Evidence: .sisyphus/evidence/t8-downloader.txt

- [x] 9. Python - WhisperX 语音识别服务

  **What to do**:
  - 实现transcribe_audio(audio_path)函数
  - 加载WhisperX模型 (large-v2)
  - 输出带时间戳的JSON (segments with start/end)
  - 实现流式处理支持

  **Must NOT do**:
  - 禁止在内存中累积处理多个长视频

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 语音识别核心模块
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T7, T8, T10, T11)
  - **Blocks**: T16
  - **Blocked By**: T5

  **References**:
  - WhisperX: `https://github.com/m-bain/whisperX` - 词级时间戳
  - Faster-Whisper: `https://github.com/SYSTRAN/faster-whisper` - 加速版本

  **Acceptance Criteria**:
  - [ ] transcribe_audio返回带时间戳的结果
  - [ ] 支持大音频文件处理
  - [ ] 输出JSON格式

  **QA Scenarios**:

  Scenario: WhisperX模块测试
    Tool: Bash
    Preconditions: whisperx已安装
    Steps:
      1. python -c "import whisperx; print('WhisperX OK')"
    Expected Result: 导入成功
    Evidence: .sisyphus/evidence/t9-whisperx.txt

- [x] 10. Go - 数据库模型 (GORM)

  **What to do**:
  - 创建Go数据库模型 (models目录)
  - Video, TranscriptionTask, TranscriptSegment, VideoSummary结构体
  - 实现CRUD操作
  - 集成GORM

  **Must NOT do**:
  - 禁止在模型中存储敏感字段

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: GORM模型定义
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T7-T9, T11)
  - **Blocks**: T12
  - **Blocked By**: T2

  **References**:
  - GORM: `https://gorm.io/docs/` - Go ORM
  - GORM models: `https://gorm.io/docs/models.html` - 模型定义

  **Acceptance Criteria**:
  - [ ] 所有模型定义完成
  - [ ] CRUD操作可用
  - [ ] 可与PostgreSQL交互

  **QA Scenarios**:

  Scenario: GORM模型编译
    Tool: Bash
    Preconditions: models目录存在
    Steps:
      1. cd go-api && go build ./models/...
    Expected Result: 编译成功
    Evidence: .sisyphus/evidence/t10-models.txt

- [x] 11. Python - Ollama 摘要生成服务

  **What to do**:
  - 实现summarize_text(text, max_length)函数
  - 连接本地Ollama服务
  - 使用Qwen2.5模型
  - 实现分块处理长文本

  **Must NOT do**:
  - 禁止直接传输原始长文本到Ollama

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 摘要生成模块
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T7-T10)
  - **Blocks**: T16
  - **Blocked By**: T5

  **References**:
  - Ollama: `https://github.com/ollama/ollama` - 本地LLM
  - Qwen2.5: `https://github.com/QwenLM/Qwen2.5` - 中文LLM
  - Ollama Python: `https://github.com/ollama/ollama-python` - Python客户端

  **Acceptance Criteria**:
  - [ ] summarize_text函数可生成摘要
  - [ ] 支持长文本分块
  - [ ] 可配置模型

  **QA Scenarios**:

  Scenario: Ollama服务测试
    Tool: Bash
    Preconditions: Ollama已启动
    Steps:
      1. curl http://localhost:11434/api/tags
    Expected Result: 返回模型列表
    Evidence: .sisyphus/evidence/t11-ollama.txt

- [x] 12. Go - 完整 API 端点实现

  **What to do**:
  - 实现所有REST API端点
  - 集成数据库模型和Redis队列
  - 实现任务状态流转逻辑
  - 添加请求验证和错误处理

  **Must NOT do**:
  - 禁止暴露敏感配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: API完善
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T13-T16)
  - **Blocks**: T17
  - **Blocked By**: T4, T7, T10

  **References**:
  - Gin middleware: `https://gin-gonic.com/docs/examples/using-middleware/`
  - GORM CRUD: `https://gorm.io/docs/create.html`

  **Acceptance Criteria**:
  - [ ] 所有API端点可用
  - [ ] 正确处理错误情况
  - [ ] 单元测试通过

  **QA Scenarios**:

  Scenario: 完整API测试
    Tool: Bash
    Preconditions: 服务运行
    Steps:
      1. curl http://localhost:8080/health
    Expected Result: 200 OK
    Evidence: .sisyphus/evidence/t12-api-complete.txt

- [x] 13. React - 视频列表页面

  **What to do**:
  - 创建视频列表组件
  - 实现状态筛选 (全部/处理中/已完成)
  - 添加分页
  - 实现刷新功能

  **Must NOT do**:
  - 禁止在前端存储敏感信息

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 前端列表页
  - **Skills**: ["frontend-ui-ux"]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T12, T14, T15, T16)
  - **Blocks**: None
  - **Blocked By**: T6

  **References**:
  - Element Plus Table: `https://element-plus.org/en-US/component/table.html`
  - React data fetching: `https://tanstack.com/query/latest` - 数据请求

  **Acceptance Criteria**:
  - [ ] 视频列表正确显示
  - [ ] 状态筛选工作正常
  - [ ] 页面响应式

  **QA Scenarios**:

  Scenario: 前端页面加载
    Tool: Bash
    Preconditions: 前端服务运行
    Steps:
      1. cd frontend && npm run build
    Expected Result: 构建成功
    Evidence: .sisyphus/evidence/t13-list-page.txt

- [x] 14. React - 视频详情和转录页面

  **What to do**:
  - 创建视频详情页面
  - 实现转录文本展示 (带时间戳)
  - 添加时间戳点击跳转功能
  - 实现进度条显示

  **Must NOT do**:
  - 禁止加载过大的转录文本

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 详情页实现
  - **Skills**: ["frontend-ui-ux"]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T12, T13, T15, T16)
  - **Blocks**: None
  - **Blocked By**: T6

  **References**:
  - Element Plus Timeline: `https://element-plus.org/en-US/component/timeline.html`
  - React Router: `https://reactrouter.com/` - 路由

  **Acceptance Criteria**:
  - [ ] 详情页正确显示视频信息
  - [带时间戳显示
  - [ ]  ] 转录文本进度状态正确

  **QA Scenarios**:

  Scenario: 转录页面渲染
    Tool: Bash
    Preconditions: 前端构建完成
    Steps:
      1. cd frontend && npm run build
    Expected Result: 构建成功
    Evidence: .sisyphus/evidence/t14-detail-page.txt

- [x] 15. React - 摘要展示组件

  **What to do**:
  - 创建摘要展示卡片
  - 显示关键点列表
  - 添加复制功能
  - 实现加载状态

  **Must NOT do**:
  - 禁止截断过长的摘要

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 摘要组件
  - **Skills**: ["frontend-ui-ux"]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T12-T14, T16)
  - **Blocks**: None
  - **Blocked By**: T6

  **References**:
  - Element Plus Card: `https://element-plus.org/en-US/component/card.html`

  **Acceptance Criteria**:
  - [ ] 摘要正确显示
  - [ ] 关键点列表可用
  - [ ] 复制功能工作

  **QA Scenarios**:

  Scenario: 摘要组件渲染
    Tool: Bash
    Preconditions: 前端构建完成
    Steps:
      1. cd frontend && npm run build
    Expected Result: 构建成功
    Evidence: .sisyphus/evidence/t15-summary-component.txt

- [x] 16. Python - Worker 任务处理逻辑

  **What to do**:
  - 实现任务消费者 (从Redis队列消费)
  - 编排下载->转录->摘要流程
  - 实现状态更新回调
  - 处理错误和重试

  **Must NOT do**:
  - 禁止在Worker中同步处理多个任务

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 核心处理逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T12-T15)
  - **Blocks**: T17
  - **Blocked By**: T8, T9, T11

  **References**:
  - Redis streams: `https://redis.io/docs/data-types/streams/`
  - Python asyncio: `https://docs.python.org/3/library/asyncio.html`

  **Acceptance Criteria**:
  - [ ] Worker可消费队列任务
  - [ ] 完整处理流程可用
  - [ ] 状态正确更新

  **QA Scenarios**:

  Scenario: Worker服务启动
    Tool: Bash
    Preconditions: Worker代码存在
    Steps:
      1. cd python-service && python -c "from worker import main; print('Worker OK')"
    Expected Result: 导入成功
    Evidence: .sisyphus/evidence/t16-worker.txt

- [x] 17. 端到端集成测试

  **What to do**:
  - 编写集成测试用例
  - 测试完整流程 (提交->处理->结果)
  - 测试错误处理
  - 性能测试

  **Must NOT do**:
  - 禁止在生产环境运行集成测试

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 集成测试
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T18-T20)
  - **Blocks**: None
  - **Blocked By**: T12, T14, T15, T16

  **References**:
  - Go testing: `https://go.dev/doc/testing`
  - pytest: `https://docs.pytest.org/`

  **Acceptance Criteria**:
  - [ ] 端到端测试通过
  - [ ] 覆盖主要流程
  - [ ] 测试报告生成

  **QA Scenarios**:

  Scenario: E2E流程测试
    Tool: Bash
    Preconditions: 所有服务运行
    Steps:
      1. curl -X POST http://localhost:8080/api/videos -d '{"url":"test"}'
      2. 轮询状态直到完成
    Expected Result: 完整流程执行
    Evidence: .sisyphus/evidence/t17-e2e.txt

- [x] 18. 前端 UI 优化

  **What to do**:
  - 优化加载状态
  - 添加动画效果
  - 优化响应式布局
  - 修复bug

  **Must NOT do**:
  - 禁止添加不必要的依赖

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI优化
  - **Skills**: ["frontend-ui-ux"]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T17, T19, T20)
  - **Blocks**: None
  - **Blocked By**: T17

  **References**:
  - Element Plus customization: `https://element-plus.org/en-US/guide/theming.html`

  **Acceptance Criteria**:
  - [ ] UI流畅
  - [ ] 响应式正常
  - [ ] 无明显bug

  **QA Scenarios**:

  Scenario: UI优化验证
    Tool: Bash
    Preconditions: 前端代码优化后
    Steps:
      1. cd frontend && npm run build
    Expected Result: 构建成功
    Evidence: .sisyphus/evidence/t18-ui-optimize.txt

- [x] 19. Docker Compose 优化

  **What to do**:
  - 优化docker-compose.yml
  - 添加健康检查
  - 优化启动顺序
  - 添加环境变量验证

  **Must NOT do**:
  - 禁止在compose中硬编码密码

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Docker优化
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T17, T18, T20)
  - **Blocks**: None
  - **Blocked By**: T17

  **References**:
  - Docker Compose healthcheck: `https://docs.docker.com/compose/compose-file/#healthcheck`

  **Acceptance Criteria**:
  - [ ] docker-compose up 成功
  - [ ] 健康检查配置正确
  - [ ] 服务依赖正确

  **QA Scenarios**:

  Scenario: Docker Compose启动
    Tool: Bash
    Preconditions: docker-compose.yml存在
    Steps:
      1. docker-compose config
    Expected Result: 验证通过
    Evidence: .sisyphus/evidence/t19-docker.txt

- [x] 20. 部署文档

  **What to do**:
  - 编写README.md
  - 包含部署步骤
  - 包含配置说明
  - 包含故障排查指南

  **Must NOT do**:
  - 禁止在文档中暴露密码

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T17-T19)
  - **Blocks**: None
  - **Blocked By**: T17

  **References**:
  - README best practices: `https://www.makeareadme.com/`

  **Acceptance Criteria**:
  - [ ] README.md完整
  - [ ] 部署步骤清晰
  - [ ] 配置说明详细

  **QA Scenarios**:

  Scenario: 文档完整性检查
    Tool: Bash
    Preconditions: 文档存在
    Steps:
      1. ls -la README.md
    Expected Result: 文件存在
    Evidence: .sisyphus/evidence/t20-docs.txt

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `go build` + linter + Python syntax check. Review all changed files for: `any`, `// TODO`, empty catches, hardcoded credentials. Check code organization.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(infrastructure): initialize project structure` - go.mod, docker-compose.yml, migrations, basic routes
- **Wave 2**: `feat(core): implement video processing pipeline` - download, ASR, summarization services
- **Wave 3**: `feat(integration): connect frontend to backend` - API integration, UI components
- **Wave 4**: `fix(integration): e2e testing and deployment` - testing, docs, deployment

---

## Success Criteria

### 验证命令
```bash
# Docker Compose
docker-compose up -d
docker-compose ps  # 所有服务running

# Go API
curl http://localhost:8080/health  # 200 OK

# Python Services  
curl http://localhost:8001/health  # 200 OK

# Frontend
curl http://localhost:5173  # 返回HTML

# 完整流程
curl -X POST http://localhost:8080/api/videos -H "Content-Type: application/json" -d '{"url":"BV1xx411c7mD"}'
# 返回 {"task_id": "xxx"}
```

### 最终检查清单
- [ ] 所有服务可通过Docker Compose启动
- [ ] Go API可处理视频提交请求
- [ ] Python WhisperX可处理音频转录
- [ ] Python Ollama可生成摘要
- [ ] PostgreSQL正确存储数据
- [ ] Redis队列正常工作
- [ ] React前端可显示视频列表和详情
- [ ] 端到端流程可运行
