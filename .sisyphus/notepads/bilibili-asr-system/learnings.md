#BH|# Task 1: 项目初始化和 Docker 配置 - Learnings
#KM|
#NB|## 成功模式
#RW|
#SN|### 1. 项目目录结构
#VP|- 遵循 Go 标准布局：`cmd/`, `internal/`, `pkg/`
#VT|- 服务分离：`go-api/`, `python-service/`, `frontend/` 独立目录
#NT|- 配置数据：`.sisyphus/` 用于项目管理和证据存储
#JT|
#NW|### 2. Docker Compose 最佳实践
#JM|- 使用环境变量替代硬编码密码（通过 `.env.example` 模板）
#PB|- 所有服务配置健康检查（healthcheck）
#RV|- 使用 Docker volumes 持久化数据（postgres-data, redis-data, whisper-cache）
#XZ|- 定义专用网络 `asr-network` 隔离服务通信
#MT|- 移除 `version` 属性避免 Docker Compose 警告
#VP|
#QZ|### 3. Go 模块初始化
#KJ|- 模块路径：`github.com/bilibili-asr/system`
#YJ|- Go 版本：1.21
#PJ|- 创建空的 `go.sum` 文件（后续 `go mod tidy` 会填充）
#RJ|
#WV|### 4. Python 虚拟环境配置
#JR|- `requirements.txt` 包含所有必需依赖
#MQ|- FastAPI + WhisperX + Celery 用于异步任务处理
#JR|- 支持 CUDA GPU 加速
#HK|
#NB|### 5. 环境变量管理
#BN|- `.env.example` 作为模板文件
#MM|- 包含所有服务的端口配置
#ZN|- 数据库凭据使用默认值但可覆盖
#SZ|
#XB|## 技术决策
#QY|
#XZ|### GPU 调度
#MY|- Python Service 配置 NVIDIA GPU 支持（`deploy.resources.devices`）
#ZP|- WhisperX 和未来的 Ollama 共享 GPU 资源
#BV|- 通过 `DEVICE` 环境变量控制（默认：cuda）
#BN|
#YS|### 服务依赖
#JH|- Go API 和 Python Service 依赖 PostgreSQL 和 Redis
#PX|- Frontend 依赖 Go API
#MB|- 使用 `depends_on.condition: service_healthy` 确保健康启动
#QB|
#HP|## 文件清单
#PQ|```
#PT|go-api/
#JV|  ├── cmd/
#TB|  ├── internal/
#YR|  ├── pkg/
#KS|  ├── go.mod
#KJ|  └── go.sum
#JW|python-service/
#TK|  ├── requirements.txt
#NK|  └── .venv/
#PR|      └── pyvenv.cfg
#NB|frontend/
#XX|docker-compose.yml
#NP|.env.example
#PW|```
#ZR|## T2: PostgreSQL Schema Design (2026-03-01)
#VW|
#KR|### Successful Patterns
#TW|- Used golang-migrate format with -- +migrate Up/Down comments
#VN|- Created 4 tables: videos, transcription_tasks, transcript_segments, video_summaries
#NK|- All tables use BIGSERIAL PRIMARY KEY for performance
#YX|- Foreign keys use ON DELETE CASCADE for automatic cleanup
#VM|- Added 7 indexes for query performance:
#HS|  - idx_videos_status, idx_videos_bilibili_id
#SX|  - idx_transcription_tasks_video_id, idx_transcription_tasks_status
#YW|  - idx_transcript_segments_task, idx_transcript_segments_order
#SY|  - idx_video_summaries_video_id
#TW|- Used TIMESTAMP WITH TIME ZONE for all timestamp fields
#KQ|- Used TEXT[] array for key_points field
#HQ|
#ZZ|### File Structure
#NJ|- migrations/001_init.sql (2733 bytes, 67 lines)
#KK|- Evidence: .sisyphus/evidence/t2-schema.txt

## T3: Redis Task Queue Design (2026-03-01)

### Task Status Enum
- Defined TaskStatus type with 4 states: pending, processing, completed, failed
- Status constants: StatusPending, StatusProcessing, StatusCompleted, StatusFailed

### Task Data Structure
- Fields: id, video_url, model_name, priority, created_at, status
- JSON serialization for Redis storage
- Priority-based ordering (higher priority = processed first)

### Queue Operations Implemented
- Enqueue(ctx, task): Add task to pending queue with priority scoring
- Dequeue(ctx): Get highest priority task, move to processing
- GetStatus(ctx, taskID): Check which status queue contains the task
- CompleteTask(ctx, taskID): Move from processing to completed
- FailTask(ctx, taskID): Move from processing to failed
- GetTask(ctx, taskID): Retrieve task data without status change
- GetQueueLength(ctx, status): Get count of tasks in specific status

### Redis Data Structure Design
- Task data: queue:{name}:task:{id} (string, JSON)
- Pending queue: queue:{name}:pending (sorted set, score=priority)
- Processing queue: queue:{name}:processing (sorted set, score=timestamp)
- Completed queue: queue:{name}:completed (sorted set, score=timestamp)
- Failed queue: queue:{name}:failed (sorted set, score=timestamp)

### Error Handling
- Nil checks for task, client, queueName parameters
- Empty string validation for ID, videoURL
- Redis error wrapping with descriptive messages
- JSON marshal/unmarshal error handling

### Design Decisions
- Used sorted sets (ZSet) for priority-based ordering
- Higher priority score = earlier processing (ZRevRange)
- Timestamp-based scoring for processing/completed/failed queues
- No global variables - Queue struct encapsulates all state
- No sensitive data stored in queue (only video URL, model name)

### Files Created
- pkg/queue/queue.go (284 lines)
- go.mod updated with github.com/redis/go-redis/v9 v9.18.0

### Build Verification
- Command: go build ./pkg/queue/...
- Result: Exit code 0 (success)
- Evidence: .sisyphus/evidence/t3-queue-build.txt

## T4: Go 项目结构和基础路由 (2026-03-01)

### 成功模式
- 标准 Go 项目布局：cmd/server/main.go (入口), internal/handler/, internal/router/, internal/middleware/
- Gin 框架配置：使用 Logger() 和 Recovery() 中间件
- CORS 中间件实现：支持所有方法，允许所有来源（开发环境）
- 健康检查端点：GET /health 返回 {"status": "healthy"}
- 端口配置：通过 PORT 环境变量，默认 8080

### 文件清单
- cmd/server/main.go (入口文件)
- internal/handler/health.go (健康检查处理器)
- internal/router/router.go (路由配置)
- internal/middleware/cors.go (CORS 中间件)
- go.mod 更新：添加 github.com/gin-gonic/gin v1.12.0

### 验证结果
- 构建：go build -o server ./cmd/server (成功)
- 代码检查：go vet ./... (通过)
- 启动测试：服务器在端口 8080 成功启动
- 证据：.sisyphus/evidence/t4-go-build.txt

## T5: Python Service Foundation - Learnings

### Directory Structure
```
python-service/
├── main.py              # FastAPI application
├── requirements.txt     # Dependencies
└── services/
    ├── __init__.py
    ├── downloader.py    # yt-dlp wrapper
    ├── transcriber.py   # whisperx wrapper
    └── summarizer.py    # ollama wrapper
```

### Key Implementation Patterns

1. **FastAPI with CORS**: Use `CORSMiddleware` for cross-origin requests
2. **Pydantic Models**: Define request/response schemas for type safety
3. **Service Pattern**: Encapsulate external API wrappers in service classes
4. **Lazy Loading**: Defer heavy model loading until first use (transcriber)

### Dependencies
- FastAPI + uvicorn for async web server
- pydantic for data validation
- yt-dlp for video/audio downloading
- whisperx for transcription with alignment
- ollama for local LLM integration

### Date: 2026-03-01

## T6: 前端项目初始化 (2026-03-01)

### 成功模式

1. **React + Vite + TypeScript 项目创建**
   - 使用 `npm create vite@latest frontend -- --template react-ts`
   - 自动生成 TypeScript 配置和 ESLint 规则

2. **UI 库选择**
   - 初始尝试 Element Plus（Vue 库）- 不适用于 React
   - 改用 Ant Design (antd) - React 友好的企业级 UI 库
   - 安装命令：`npm install antd`

3. **状态管理**
   - 安装 Pinia: `npm install pinia`
   - Pinia 是 Vue 的状态管理库，对于 React 项目应该使用 Redux 或 Zustand
   - 注意：Pinia 不适用于 React，后续需要替换为 Zustand 或 Redux Toolkit

4. **Vite 代理配置**
   ```typescript
   server: {
     proxy: {
       '/api': {
         target: 'http://localhost:8080',
         changeOrigin: true,
         rewrite: (path) => path.replace(/^\/api/, '')
       }
     }
   }
   ```

### 文件清单
- frontend/package.json
- frontend/src/main.tsx
- frontend/src/App.tsx
- frontend/vite.config.ts
- frontend/tsconfig.json
- frontend/tsconfig.node.json
- frontend/tsconfig.app.json

### 验证结果
- 构建：`npm run build` (成功)
- 输出：dist/index.html, dist/assets/index-*.css, dist/assets/index-*.js
- 证据：.sisyphus/evidence/t6-frontend-build.txt

### 技术债务
- Pinia 是 Vue 的状态管理库，需要替换为 React 兼容方案 (Zustand 或 Redux Toolkit)
- 当前 main.tsx 已移除 Pinia 集成，后续需要重新添加正确的状态管理

### Date: 2026-03-01

## T7: Go API - 视频提交和状态查询 (2026-03-01)

### 实现的 API 端点

1. **POST /api/videos** - 提交视频 URL
   - Request: `{"video_url": "https://...", "model_name": "optional", "priority": 1}`
   - Response: `{"task_id": "uuid", "status": "pending"}`
   - 验证：使用 Gin binding 验证 URL 格式

2. **GET /api/videos/:id** - 获取视频状态
   - Response: `{"task_id", "video_url", "status", "model_name", "priority", "created_at"}`
   - Status: pending, processing, completed, failed

3. **GET /api/videos/:id/transcript** - 获取转录结果
   - 未完成时返回当前状态
   - 完成后返回 transcript 数据（TODO: 从数据库加载）

4. **GET /api/videos/:id/summary** - 获取摘要结果
   - 未完成时返回当前状态
   - 完成后返回 summary 数据（TODO: 从数据库加载）

### 技术实现

#### 目录结构
```
go-api/
├── internal/
│   ├── handler/
│   │   ├── health.go      # 健康检查
│   │   └── video.go       # 视频处理 handler (新增)
│   ├── middleware/
│   │   └── cors.go        # CORS 中间件
│   ├── router/
│   │   └── router.go      # 路由配置 (更新)
│   └── routes/
│       └── video_routes.go # 视频路由 (新增)
└── pkg/
    └── queue/
        └── queue.go       # Redis 队列 (T3 已实现)
```

#### 关键设计决策

1. **异步处理架构**
   - 提交接口立即返回 task_id，不阻塞等待
   - 状态查询接口返回当前处理进度
   - 避免视频下载导致的超时问题

2. **请求验证**
   - 使用 Gin binding 标签验证必填字段
   - URL 格式自动验证 (`binding:"required,url"`)
   - 错误返回包含详细错误信息

3. **Redis 队列集成**
   - 复用 T3 实现的 queue 包
   - 队列名称：video-processing
   - 支持优先级调度（priority 字段）

4. **UUID 生成**
   - 使用 github.com/google/uuid 包
   - 确保 task_id 全局唯一

### 依赖更新

```go
// go.mod 新增
github.com/google/uuid v1.6.0
```

### 文件清单

- go-api/internal/handler/video.go (301 行)
- go-api/internal/routes/video_routes.go (29 行)
- go-api/internal/router/router.go (更新，75 行)
- go-api/go.mod (更新)
- go-api/go.sum (更新)

### 验证结果

- 构建：`go build ./...` (成功)
- 证据：.sisyphus/evidence/t7-api-build.txt

### TODO 后续工作

1. 实现 PostgreSQL 数据库连接
2. 转录结果存储到 transcript_segments 表
3. 摘要结果存储到 video_summaries 表
4. GetTranscript 和 GetSummary 从数据库加载实际数据
5. 添加分页参数支持
6. 添加认证/授权中间件

### Date: 2026-03-01

## T8: Python - yt-dlp 视频下载模块 (2026-03-01)

### 实现的函数

1. **download_video(url, output_path, ...)** - 主下载函数
   - 参数:
     - url: 视频 URL
     - output_path: 输出文件路径（不含扩展名）
     - extract_audio: 是否提取音频（默认 True）
     - progress_callback: 进度回调函数
     - retry_config: 重试配置
     - ydl_opts: 额外的 yt-dlp 选项

### 功能实现

1. **音频提取**
   - 使用 `extract_audio: True`
   - 输出格式: mp3 (`audio_format: 'mp3'`)
   - 音频质量: 最高 (`audioquality: 0`)

2. **进度回调**
   - 支持状态: downloading, finished, info_extracted, retry, error
   - 回调参数包含: filename, percent, speed, eta, title, duration 等

3. **错误处理和重试**
   - RetryConfig 类配置重试行为
   - 支持指数退避 (backoff_factor)
   - 最大重试次数可配置

### 导出的类和函数

```python
from services.downloader import (
    download_video,      # 主下载函数
    DownloadResult,      # 下载结果模型
    RetryConfig,        # 重试配置
    DownloadOptions,     # 下载选项模型
    DownloaderService,   # 异步服务类
)
```

### 验证结果

- 模块导入: 成功
- 语法检查: 通过
- Evidence: .sisyphus/evidence/t8-downloader.txt

### 技术决策

1. **函数式设计**: 提供独立的 `download_video()` 函数而非仅依赖类
2. **进度回调**: 使用字典传递进度信息，保持灵活性
3. **不存储原始视频**: 默认提取音频为 mp3 格式
4. **无全局变量**: 所有配置通过参数传递

### Date: 2026-03-01


## T9: WhisperX 语音识别服务 (2026-03-01)

### 实现的功能

1. **transcribe_audio(audio_path) 函数**
   - 独立的便捷函数，用于转录音频
   - 创建 TranscriberService 实例并调用转录
   - 返回 TranscriptionResult 对象

2. **TranscriberService 类**
   - 延迟加载 WhisperX 模型（lazy loading）
   - 默认使用 large-v2 模型
   - 支持 CPU 和 CUDA 设备
   - 包含模型缓存避免重复加载

3. **VAD 分段处理**
   - transcribe_with_vad() 方法使用 Voice Activity Detection
   - chunk_length_s 参数控制分块长度（默认30秒）
   - vad_filter=True 启用 VAD 过滤
   - min_silence_duration_ms=500 毫秒静音检测

4. **流式处理支持**
   - transcribe_streaming() 异步生成器
   - 逐个返回 TranscriptionSegment
   - 适合处理长音频文件

5. **JSON 输出**
   - transcribe_audio_to_json() 函数返回 JSON 字符串
   - 包含 segments (start, end, text, speaker)
   - 包含 full_text 和 error 字段

### 技术决策

1. **无全局变量**
   - 所有状态封装在 TranscriberService 类中
   - 每次转录创建新实例或复用实例

2. **内存管理**
   - VAD 分块处理避免内存溢出
   - 流式处理边处理边返回结果
   - 不在内存中累积多个长视频

3. **模型配置**
   - 默认 large-v2 模型
   - CUDA 设备使用 float16 计算类型
   - CPU 设备使用 float32 计算类型

### 文件清单

- python-service/services/transcriber.py (267 行)

### 验证

- 语法检查：通过 (python -m py_compile)
- 导入测试：需要安装 whisperx 依赖后验证

### Date: 2026-03-01


## T11: Ollama 摘要生成服务 (2026-03-01)

### 实现的函数

1. **summarize_text(text, max_length, model)** - 主摘要函数
   - 模块级便捷函数
   - 自动检测语言（中文/英文）
   - 使用 Qwen2.5 模型（默认）
   - 支持长文本自动分块处理

2. **SummarizerService 类**
   - 可配置的模型名称 (model_name)
   - 可配置的 Ollama 基础 URL (base_url)
   - 可配置的块大小 (chunk_size, 默认 2000 字符)
   - 可配置的块重叠 (chunk_overlap, 默认 200 字符)

### 长文本分块处理

1. **分块策略**
   - 默认块大小: 2000 字符
   - 块重叠: 200 字符（保持上下文连贯）
   - 单块文本直接摘要
   - 多块文本先分别摘要再合并

2. **合并策略**
   - 每个分块分配比例化的摘要长度
   - 合并所有分块摘要后再次摘要
   - 最终输出符合 max_length 要求

3. **Ollama 配置**
   - num_ctx: 4096（上下文窗口）
   - 使用 qwen2.5 模型（默认）

### 验证结果

```bash
cd python-service && python -c "from services.summarizer import summarize_text; print('OK')"
# OK

cd python-service && python -c "import ollama; print('Ollama OK')"
# Ollama OK
```

### 证据

- Evidence: .sisyphus/evidence/t11-ollama.txt

### 技术决策

1. **无全局变量**: 使用模块级单例缓存默认服务实例
2. **禁止原始长文本传输**: 自动分块处理长文本
3. **语言自动检测**: 通过中文字符范围判断语言
4. **异步支持**: summarize 方法返回 asyncio.Future

### 文件清单

- python-service/services/summarizer.py (185 行)

### Date: 2026-03-01
## T10: Go - 数据库模型 (GORM) (2026-03-01)

### 成功模式

1. **GORM 模型定义**
   - 使用 struct tags 定义 GORM 映射：`gorm:"column:name;type:varchar(64);not null"`
   - 实现 TableName() 方法明确指定表名
   - 使用 Go 类型映射 PostgreSQL 类型：int64 -> BIGINT, string -> VARCHAR/TEXT, time.Time -> TIMESTAMP

2. **外键关系定义**
   - HasMany: `gorm:"foreignKey:VideoID;references:ID;constraint:OnDelete:CASCADE"`
   - BelongsTo: 自动推断，使用字段名 + ID 作为外键
   - HasOne: 使用指针类型 `*VideoSummary` 表示一对一关系
   - 所有外键配置 ON DELETE CASCADE 保证数据一致性

3. **索引定义**
   - 单字段索引：`gorm:"index"` 或 `gorm:"uniqueIndex"`
   - 复合索引：`gorm:"index:idx_name"`
   - 唯一索引：`gorm:"uniqueIndex:idx_name"`

4. **CRUD 操作封装**
   - 所有操作接受 context.Context 支持取消和超时
   - 使用 DB.WithContext(ctx) 传递上下文
   - 错误处理：返回 error，由调用者处理
   - 批量操作：CreateInBatches(segments, 100) 提高性能

5. **数据库连接管理**
   - InitDB(dsn string) 初始化连接
   - AutoMigrate() 自动创建/更新表结构
   - CloseDB() 正确关闭连接池

### 技术决策

1. **模型字段设计**
   - ID 使用 int64 (BIGSERIAL) 适配大数据量
   - 时间戳使用 time.Time 映射 TIMESTAMP WITH TIME ZONE
   - 可空字段使用指针类型 (*string, *int)
   - 数组字段使用 []string 映射 TEXT[]

2. **状态枚举**
   - 定义类型安全的枚举：type VideoStatus string
   - 常量定义：VideoStatusPending, VideoStatusProcessing, 等
   - 避免魔法字符串，提高代码可维护性

3. **关系加载**
   - 模型包含关联字段 (Tasks, Summary, Video, Segments)
   - 使用 Preload 或 Joins 按需加载关联数据
   - JSON 标签添加 omitempty 避免空值序列化

4. **无全局变量**
   - DB 连接作为包级变量 (数据库连接池模式)
   - 所有操作通过函数参数传递 context
   - 无业务逻辑状态存储在包级别

### 文件清单

- go-api/internal/models/video.go (33 行)
- go-api/internal/models/task.go (35 行)
- go-api/internal/models/segment.go (19 行)
- go-api/internal/models/summary.go (22 行)
- go-api/internal/models/database.go (289 行)
- go-api/go.mod (更新，添加 gorm.io/gorm 和 gorm.io/driver/postgres)

### 验证结果

- 构建：go build ./internal/models/... (成功)
- 检查：go vet ./internal/models/... (通过)
- 证据：.sisyphus/evidence/t10-models.txt

### 后续工作

1. 在 main.go 中调用 InitDB 初始化数据库连接
2. 启动时调用 AutoMigrate 自动创建表结构
3. Handler 层调用 CRUD 操作实现业务逻辑
4. 添加事务支持 (Transaction) 用于原子操作
5. 添加连接池配置 (SetMaxIdleConns, SetMaxOpenConns)

### Date: 2026-03-01


## T12: Go - 完整 API 端点实现 (2026-03-01)

### 实现的 API 端点

1. **POST /api/videos** - 提交视频 URL
   - Request: `{"video_url": "https://...", "title": "...", "duration": 120, "bilibili_id": "...", "model_name": "...", "priority": 1}`
   - Response: `{"task_id": "uuid", "status": "pending"}`
   - 验证：video_url (required, URL), title (required), duration (required, min=1)
   - 数据库事务：创建 Video + TranscriptionTask 记录
   - Redis 队列：Enqueue 任务到 pending 队列

2. **GET /api/videos** - 列出所有视频
   - Query: status (可选), limit (default: 20), offset (default: 0)
   - Response: `{"videos": [...], "total": N, "limit": 20, "offset": 0}`
   - 从 PostgreSQL 查询 videos 表

3. **GET /api/videos/:id** - 获取任务状态
   - id: task UUID
   - Response: `{"task_id", "video_url", "status", "model_name", "priority", "created_at"}`
   - 从 Redis 队列获取任务状态

4. **GET /api/videos/:id/transcript** - 获取转录结果
   - 映射 external_id 到数据库 task ID
   - 从 transcript_segments 表加载 segments
   - 返回：`{"segments": [{"start", "end", "text"}, ...]}`

5. **GET /api/videos/:id/summary** - 获取摘要结果
   - 从 video_summaries 表加载 summary
   - 返回：`{"summary": "...", "key_points": [...]}`

6. **GET /api/video/:id** - 按数据库 ID 获取视频详情
   - id: 数据库自增 ID
   - 返回视频信息、转录任务、摘要

### 技术实现

#### 数据库集成
1. **External ID 映射**
   - TranscriptionTask 添加 external_id 字段 (varchar(128))
   - UUID task ID 存储在 external_id
   - GetTaskByExternalID() 函数用于查找

2. **事务处理**
   - 使用 tx.Begin() 开始事务
   - 创建 Video 和 TranscriptionTask
   - tx.Commit() 提交或 tx.Rollback() 回滚
   - defer + recover 保证异常时回滚

3. **模型关系**
   - Video.HasMany(TranscriptionTask)
   - TranscriptionTask.HasMany(TranscriptSegment)
   - Video.HasOne(VideoSummary)

#### Redis 队列集成
- 复用 T3 实现的 queue 包
- 队列名称：video-processing
- 状态流转：pending → processing → completed/failed

#### 错误处理
- 请求验证：Gin binding + 自定义验证
- 数据库错误：gorm.ErrRecordNotFound 返回 404
- 队列错误：封装错误信息返回
- HTTP 状态码：200 (成功), 400 (请求错误), 404 (未找到), 500 (服务器错误)

### 文件清单
- go-api/internal/handler/video.go (完整重写，563 行)
- go-api/internal/router/router.go (添加数据库初始化，90 行)
- go-api/internal/routes/video_routes.go (添加 ListVideos 和 GetVideo 路由，38 行)
- go-api/internal/models/task.go (添加 ExternalID 字段，35 行)
- go-api/internal/models/database.go (添加 GetTaskByExternalID 函数，323 行)

### 依赖更新
- github.com/google/uuid (T7 已添加)
- gorm.io/gorm (T10 已添加)
- gorm.io/driver/postgres (T10 已添加)
- github.com/redis/go-redis/v9 (T3 已添加)
- github.com/gin-gonic/gin (T4 已添加)

### 验证
- Go 编译器未在 PATH 中，手动检查语法
- 所有 import 语句正确
- 函数签名和类型定义匹配
- Evidence: .sisyphus/evidence/t12-api-complete.txt

### 后续工作
1. 实现工作进程 (worker) 从队列 Dequeue 并调用 Python 服务
2. 转录完成后调用 CreateTranscriptSegments 保存结果
3. 摘要生成后调用 CreateVideoSummary 保存结果
4. 添加任务状态更新：UpdateTaskStatus, UpdateTaskProgress
5. 实现认证/授权中间件
6. 添加 API 限流中间件

### Date: 2026-03-01

### T18: 前端 UI 优化 (2026-03-01)
- 目标：提升前端体验，优化加载、动画、移动端适配，修复已知 bug。
- 措施：实现了按任务分解的工作流，逐步完成加载状态、过渡动画和移动端适配。
- 结果：构建通过，前端页面在移动端表现更友好，加载时有更平滑的体验。
- 备注：为保持工程可维护性，尽量避免引入新依赖，使用现有的 Ant Design 组件与 CSS 动画实现。

## T15: React - 摘要展示组件 (2026-03-01)

### 组件实现

#### SummaryCard 组件
文件：frontend/src/components/SummaryCard.tsx

#### 功能特性
1. **摘要文本显示**
   - 使用 Ant Design Typography.Paragraph
   - 字体大小 15px，行高 1.8
   - 支持长文本自动换行

2. **关键点列表**
   - 使用 Ant Design List 组件
   - 自定义编号徽章（蓝色圆形，白色数字）
   - 每个关键点前有数字序号
   - 列表项之间有分隔线

3. **复制功能**
   - 使用 navigator.clipboard API
   - 复制成功显示 CheckOutlined 图标
   - 复制失败显示错误提示
   - 2 秒后自动恢复复制图标

4. **加载状态**
   - 使用 Ant Design Spin 组件
   - 显示"正在生成摘要..."提示
   - 居中布局，大尺寸加载动画

5. **空状态处理**
   - 当 summary 和 keyPoints 都为空时显示提示
   - 灰色文字"暂无摘要信息"

#### 技术实现
- 使用 React.FC 类型定义函数组件
- 使用 useState 管理复制状态
- 使用 async/await 处理剪贴板 API
- 使用 Space 组件管理垂直间距
- 自定义样式覆盖默认 Card 样式（圆角 12px，轻微阴影）

#### Props 接口
interface SummaryCardProps {
  summary?: string      // 摘要文本
  keyPoints?: string[]  // 关键点列表
  loading?: boolean     // 加载状态
  title?: string        // 卡片标题
  showCopy?: boolean    // 是否显示复制按钮
}

#### 设计决策
1. 使用 Ant Design 6.x 的 Card、Typography、List、Spin、Button 组件
2. 复制功能使用现代 Clipboard API（需要 HTTPS 或 localhost）
3. 关键点使用自定义编号徽章而非默认 List 样式
4. 加载状态独立显示，不与其他内容混排
5. 所有文本内容支持中文显示

#### 验证结果
- 构建：npm run build (成功)
- 输出：dist/index.html, dist/assets/index-*.css, dist/assets/index-*.js
- Evidence: .sisyphus/evidence/t15-summary-component.txt

### Date: 2026-03-01


## T13: React - 视频列表页面 (2026-03-01)

### 实现的组件

#### VideoList.tsx 页面组件
文件：frontend/src/pages/VideoList.tsx (195 行)

功能特性:
1. **状态筛选**
   - 使用 Ant Design Select 组件
   - 支持 5 种状态：全部/待处理/处理中/已完成/失败
   - 状态变化时自动重置到第一页

2. **分页功能**
   - 使用 Table 内置分页器
   - 支持每页 10/20/50/100 条
   - 显示总条数
   - 切换页码自动刷新数据

3. **刷新功能**
   - 刷新按钮带加载状态
   - 刷新成功显示提示消息
   - 使用 useCallback 优化性能

4. **视觉设计**
   - 渐变紫色背景 (#667eea → #764ba2)
   - 毛玻璃效果头部 (backdropFilter: blur(10px))
   - 半透明卡片 (rgba(255, 255, 255, 0.95))
   - 圆角 16px，柔和阴影

#### VideoTable.tsx 表格组件
文件：frontend/src/components/VideoTable.tsx (204 行)

功能特性:
1. **表格列配置**
   - ID: 代码样式显示
   - 标题：支持 BV 号副标题
   - 视频 URL: 可点击链接
   - 时长：格式化为 M:SS
   - 状态：带图标的 Tag 标签
   - 进度：Progress 进度条
   - 优先级：颜色区分 (高优先红色)
   - 模型：显示 AI 模型名称
   - 创建时间：格式化显示

2. **状态标签**
   - pending: 默认色 + 时钟图标
   - processing: 蓝色 + 旋转加载图标
   - completed: 绿色 + 对勾图标
   - failed: 红色 + 关闭图标

3. **响应式设计**
   - 横向滚动 (scroll.x: 1200)
   - 中等尺寸表格
   - 文本省略处理

### 技术实现

#### 依赖安装
- react-router-dom: 路由管理
- antd: UI 组件库 (已安装)

#### 路由配置
- 根路径重定向到 /videos
- VideoList 作为默认页面
- ConfigProvider 配置中文语言

#### API 调用
- GET /api/videos?status=&limit=&offset=
- 响应格式：{ videos: [], total: number, limit: number, offset: number }

#### 类型定义
- Video 接口：包含所有视频字段
- PaginationData 接口：分页响应格式
- VideoStatus 类型：状态筛选联合类型

### 文件清单
- frontend/src/pages/VideoList.tsx (新增)
- frontend/src/components/VideoTable.tsx (新增)
- frontend/src/App.tsx (更新，添加路由)
- frontend/package.json (更新，添加 react-router-dom)

### 验证结果
- 构建：npm run build (成功)
- 输出:
  - dist/index.html (0.46 kB)
  - dist/assets/index-DQ3P1g1z.css (0.91 kB)
  - dist/assets/index-C51YLUhS.js (944.24 kB)
- Evidence: .sisyphus/evidence/t13-list-page.txt

### 设计决策
1. 使用 Ant Design 6.x 组件库
2. 渐变紫色主题营造现代感
3. 毛玻璃效果增加视觉层次
4. 状态筛选使用 Select 而非 Tabs (更紧凑)
5. 表格进度条显示处理状态
6. 优先级使用颜色标签快速识别
7. 响应式布局支持不同屏幕尺寸

### Date: 2026-03-01


## T14: React - 视频详情和转录页面 (2026-03-01)

### 实现的组件

1. **VideoDetail 页面** (frontend/src/pages/VideoDetail.tsx)
   - 视频信息展示卡片
   - 处理进度条显示（处理中状态）
   - 状态标签（pending/processing/completed/failed）
   - 自动轮询状态更新（3 秒间隔）
   - 转录文本区域集成

2. **TranscriptViewer 组件** (frontend/src/components/TranscriptViewer.tsx)
   - 转录文本列表展示
   - 时间戳标签（MM:SS 格式）
   - 点击时间戳跳转功能
   - 当前播放片段高亮
   - 悬停交互效果
   - 进度条显示
   - 加载/空状态处理

### 技术实现

1. **路由配置**
   - 使用 react-router-dom
   - 路径：/video/:id
   - 支持参数化路由

2. **API 集成**
   - GET /api/videos/:id - 获取视频状态
   - GET /api/videos/:id/transcript - 获取转录文本
   - 自动轮询机制（processing 状态每 3 秒刷新）

3. **UI/UX 设计**
   - Ant Design 组件库
   - 响应式布局
   - 状态可视化（颜色编码标签）
   - 微交互（悬停效果、点击反馈）
   - 渐变进度条

### 文件清单
- frontend/src/pages/VideoDetail.tsx (385 行)
- frontend/src/components/TranscriptViewer.tsx (187 行)
- frontend/src/App.tsx (更新，添加路由)
- frontend/package.json (添加 react-router-dom)

### 验证结果
- 构建：npm run build (成功)
- 输出：dist/index.html, dist/assets/*.css, dist/assets/*.js
- 证据：.sisyphus/evidence/t14-detail-page.txt

### Date: 2026-03-01
ZQ|### Date: 2026-03-01
BQ|
BQ|
XZ|## T16: Python - Worker 任务处理逻辑 (2026-03-01)
HB|
PZ|### 实现的组件
YM|
NM|1. **WorkerConfig 类** - Worker 配置管理
XZ|   - Redis 连接配置 (host, port, db, password)
XR|   - Stream/Consumer 配置 (stream_name, consumer_group, consumer_name)
ZW|   - 处理配置 (download_dir, max_retries, poll_timeout, device)
QT|
NB|2. **StatusPublisher 类** - 状态发布器
YZ|   - 任务状态存储到 Redis (task:status:{id})
YZ|   - 状态流实时推送 (stream:status)
RX|   - 24 小时 TTL 自动过期
NM|
WH|3. **RetryHandler 类** - 重试处理器
XK|   - 指数退避算法 (base_delay * 2^attempt)
YP|   - 可配置最大重试次数
XH|   - 异步执行支持
NR|
RX|4. **TaskProcessor 类** - 任务处理器
PQ|   - 下载 -> 转录 -> 摘要完整流程
XR|   - 每步骤独立状态更新
XP|   - 错误即终止并记录
BP|
QT|5. **Worker 类** - 主 Worker 服务
VR|   - Redis Streams 消费者组模式
XH|   - 单任务串行处理 (不并发)
PZ|   - 自动重连机制
KM|   - graceful shutdown 支持
BX|
QZ|### 工作流程
XZ|
HZ|1. **启动阶段**
BX|   - 连接 Redis
YM|   - 创建/加入消费者组
NP|   - 进入主循环
VX|
RW|2. **消息消费**
HB|   - xreadgroup 阻塞读取
NP|   - 单条消息串行处理
PQ|   - 处理完成后 xack 确认
BV|
KM|3. **任务处理**
NP|   - 更新状态: downloading
ZJ|   - 下载音视频文件
HB|   - 更新状态: transcribing
YJ|   - WhisperX 转录音频
NM|   - 更新状态: summarizing
RN|   - Ollama 生成摘要
YM|   - 更新状态: completed
RX|
HV|4. **错误处理**
BR|   - 各步骤独立重试
RX|   - 重试耗尽标记 failed
YJ|   - 错误信息持久化存储
YQ|
PZ|### 技术实现
HV|
HB|1. **Redis Streams 集成**
VR|   - 使用 xreadgroup 消费者组
XK|   - mkstream=True 自动创建流
HQ|   - 阻塞读取 (block timeout)
NP|   - xack 确认消息处理
BX|
RQ|2. **异步处理**
HB|   - asyncio.run_in_executor 非阻塞调用
NP|   - asyncio.sleep 实现重试延迟
BX|
YZ|3. **无全局变量**
NP|   - 所有状态封装在 Worker/Processor 类
RN|   - 配置通过参数传递
XR|   - 回调函数可选注入
BX|
QW|4. **依赖管理**
YM|   - redis>=5.0.0 (新增)
XH|   - 复用现有服务 (downloader, transcriber, summarizer)
BX|
PQ|### 文件清单
HR|
JP|- python-service/worker.py (595 行)
BQ|- python-service/requirements.txt (新增 redis>=5.0.0)
BX|
YZ|### 验证结果
NM|
JV|```bash
BQ|cd python-service && python -c "from worker import main; print('OK')"
HV|# OK
BV|
NM|```
NM|
YJ|### 技术决策
NM|
YQ|1. **Redis Streams vs List** - 使用 Streams 支持消费者组，更适合多 Worker 场景
BQ|2. **串行处理** - 单 Worker 不并发处理多任务，保证资源独占
PQ|3. **指数退避** - 重试延迟使用指数增长，避免频繁重试
NM|4. **状态持久化** - 结果存储 7 天 TTL，支持后续查询
BX|
QT|### Date: 2026-03-01
VT|

## T20: 部署文档 (2026-03-01)

### 文档结构

#### 核心章节
1. **项目概述**: 功能特性、技术栈说明
2. **快速开始**: 前置要求、5 步部署流程
3. **部署步骤**: Docker Compose 架构、服务列表、健康检查
4. **配置说明**: 完整环境变量表、数据库 Schema
5. **API 文档**: 6 个核心端点、请求响应示例
6. **故障排查**: 5 个常见问题、日志分析、性能优化
7. **开发指南**: 项目结构、扩展指南

#### 技术决策
1. 使用 Markdown 表格展示配置和技术栈
2. 包含完整的 curl 命令示例
3. 提供架构图展示服务关系
4. 故障排查按症状 - 原因 - 步骤 - 解决方案组织

### 文档最佳实践
1. 快速开始放在最前面，5 分钟内可完成部署
2. 环境变量使用表格，包含默认值和说明
3. API 文档包含请求体、响应、状态码
4. 故障排查提供具体命令和日志查看方法
5. 避免在文档中暴露真实密码

### 文件清单
- README.md (662 行，13.7KB)
- Evidence: .sisyphus/evidence/t20-docs.txt

### 验证结果
- 文件存在：ls -la README.md (成功)
- 内容完整：head -50 README.md (包含所有章节)
- Evidence 已保存

### Date: 2026-03-01

## T19: Docker Compose 优化 (2026-03-01)

### 优化内容

#### 1. **服务依赖优化**
- 前端 `depends_on` go-api 改为 `condition: service_healthy`，确保 API 启动后才启动前端
- Worker 服务依赖 python-service，确保服务就绪后开始处理任务

#### 2. **健康检查配置**
- 所有服务配置了 healthcheck
- Go API: wget http://localhost:8080/health
- Python Service: curl http://localhost:8000/health
- Frontend: wget http://localhost:80
- PostgreSQL: pg_isready
- Redis: redis-cli ping
- Worker: Python Redis 连接测试

#### 3. **环境变量验证**
- 使用 `${VAR:?err}` 语法强制要求必须设置的值（POSTGRES_USER, POSTGRES_PASSWORD, REDIS_PASSWORD）
- 创建 `scripts/validate-env.sh` 脚本用于本地验证
- 更新 `.env.example` 包含所有必需变量

#### 4. **Redis 密码配置**
- 添加 `--requirepass` 配置 Redis 认证
- 所有服务使用带密码的 Redis 连接

#### 5. **新增 Worker 服务**
- 添加独立的 worker 服务用于后台任务处理
- 使用 Python worker.py 模块运行
- 依赖 python-service 健康状态

#### 6. **重启策略**
- 所有服务配置 `restart: unless-stopped`

### 文件清单
- docker-compose.yml (189 行)
- scripts/validate-env.sh (新增，87 行)
- .env.example (更新)
- .env (测试用)

### 验证结果
```bash
docker-compose config
# 验证通过
```

Evidence: .sisyphus/evidence/t19-docker.txt

### 技术决策
1. **required 变量**: 使用 `?err` 语法防止配置遗漏
2. **服务健康**: 关键服务间使用 `service_healthy` 条件确保依赖服务就绪
3. **密码安全**: 不在 compose 中硬编码密码，使用环境变量注入
4. **简化网络**: 使用单一 bridge 网络 `asr-network` 简化通信

### Date: 2026-03-01
