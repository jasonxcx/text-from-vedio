# Task Queue Architecture Design

## Overview

This document describes the stage-separated task queue system implemented in `app/task_queue.py`.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      TaskQueueManager (QObject)                  │
│  Signals: task_stage_changed, task_progress, task_completed     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│
│  │   DownloadQueue  │  │  TranscribeQueue │  │   SummaryQueue   ││
│  │   (StageQueue)   │  │   (StageQueue)   │  │   (StageQueue)   ││
│  │                  │  │                  │  │                  ││
│  │  max_workers: 3  │  │  max_workers: 1  │  │  max_workers: N  ││
│  │  (concurrent)    │  │  (single-thread) │  │  (concurrent)    ││
│  │                  │  │                  │  │                  ││
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  ││
│  │  │ QThreadPool│  │  │  │ QThreadPool│  │  │  │ QThreadPool│  ││
│  │  │  (3 threads)│ │  │  │  (1 thread) │  │  │  │  (N threads)│ ││
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  ││
│  └──────────────────┘  └──────────────────┘  └──────────────────┘│
│           │                     │                     │          │
│           ▼                     ▼                     ▼          │
│  TaskRunnable          TaskRunnable          TaskRunnable        │
│  (QRunnable)           (QRunnable)           (QRunnable)         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Task Dataclass                           │
│  video_id, url, title, bilibili_id, stage, result, error        │
│  retry_count, audio_path, transcription_result, summary_result  │
└─────────────────────────────────────────────────────────────────┘
```

## State Machine

### TaskStage Enum

```python
class TaskStage(Enum):
    PENDING = auto()              # 初始状态
    QUEUED_DOWNLOAD = auto()      # 等待下载
    DOWNLOADING = auto()          # 正在下载
    QUEUED_TRANSCRIBE = auto()    # 等待转录
    TRANSCRIBING = auto()         # 正在转录
    QUEUED_SUMMARY = auto()       # 等待摘要
    SUMMARIZING = auto()          # 正在摘要
    COMPLETED = auto()            # 完成
    FAILED = auto()               # 失败
```

### State Flow Diagram

```
                    ┌─────────┐
                    │ PENDING │
                    └────┬────┘
                         │ submit_task()
                         ▼
               ┌───────────────────┐
               │  QUEUED_DOWNLOAD  │
               └─────────┬─────────┘
                         │ download_queue.submit()
                         ▼
                 ┌───────────────┐
                 │  DOWNLOADING  │◄──── retry loop (max_retries)
                 └───────┬───────┘
                         │ success
                         ▼
            ┌───────────────────────┐
            │   QUEUED_TRANSCRIBE   │
            └───────────┬───────────┘
                        │ transcribe_queue.submit()
                        ▼
                ┌───────────────┐
                │ TRANSCRIBING  │◄──── retry loop (max_retries)
                └───────┬───────┘
                        │ success
                        ▼
           ┌───────────────────────┐
           │    QUEUED_SUMMARY     │ (if summary.enabled)
           └───────────┬───────────┘
                       │ summary_queue.submit()
                       ▼
               ┌───────────────┐
               │  SUMMARIZING  │
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │   COMPLETED   │
               └───────────────┘

    Any stage ─────► FAILED (on error or max retries exceeded)
```

## Key Classes

### Task (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| video_id | int | Database ID |
| url | str | Bilibili URL |
| title | str | Video title |
| bilibili_id | str | BV号 |
| stage | TaskStage | Current stage |
| result | Any | Stage execution result |
| error | Optional[str] | Error message |
| retry_count | Dict[TaskStage, int] | Retry count per stage |
| audio_path | Optional[str] | Downloaded audio path |
| transcription_result | Any | Transcription result |
| summary_result | Any | Summary result |
| _is_cancelled | bool | Cancel flag |

### StageQueue

Base class for managing a single stage's task queue.

**Key Methods:**
- `submit(task)` - Submit task to queue
- `_process_queue()` - Process queued tasks
- `_execute_task(task)` - Execute task in thread pool
- `_run_task(task)` - Actual execution logic (subclass implements)
- `_on_task_finished(task)` - Completion callback
- `get_active_count()` - Count active tasks
- `get_queued_count()` - Count queued tasks
- `shutdown()` - Stop queue

### TaskQueueManager (QObject)

Central manager coordinating all queues.

**Signals:**
- `task_stage_changed(int, str)` - Stage transition
- `task_progress(int, int, str)` - Progress update
- `task_completed(int, bool, str)` - Task finished
- `task_error(int, str)` - Error occurred
- `all_tasks_finished()` - All tasks done

**Key Methods:**
- `submit_task()` - Create and start new task
- `_transition_task()` - Move task to new stage
- `cancel_task()` - Cancel specific task
- `cancel_all()` - Cancel all tasks
- `get_task_status()` - Get task info
- `get_queue_status()` - Get all queue stats
- `shutdown()` - Stop everything

## Concurrency Control

### Download Queue
- **max_workers**: 3 (configurable)
- **Strategy**: Concurrent downloads
- **Reason**: Network I/O can be parallelized

### Transcribe Queue
- **max_workers**: 1 (fixed)
- **Strategy**: Single-threaded
- **Reason**: GPU memory constraint, Whisper model needs exclusive GPU access

### Summary Queue
- **max_workers**: N (configurable, default 3)
- **Strategy**: Concurrent API calls
- **Reason**: CPU-based, can parallelize LLM requests

## Thread Safety

- Uses `threading.Lock` for critical sections
- `active_tasks` dict protected by lock
- Queue operations are atomic (Queue class is thread-safe)
- QThreadPool handles thread management

## Integration Points (Task 5)

The `StageQueue._run_task()` method needs to be implemented by subclasses:

```python
class DownloadQueue(StageQueue):
    def _run_task(self, task: Task):
        # Call existing download logic
        # Update task.audio_path on success
        # Set task.error on failure

class TranscribeQueue(StageQueue):
    def _run_task(self, task: Task):
        # Call existing transcribe logic
        # Update task.transcription_result on success

class SummaryQueue(StageQueue):
    def _run_task(self, task: Task):
        # Call existing summarize logic
        # Update task.summary_result on success
```

## Design Decisions

1. **No External Queues**: Uses Python's built-in `Queue` and Qt's `QThreadPool`
   - Keeps architecture simple
   - No Redis/RabbitMQ dependency
   - Qt-native threading

2. **Stage Separation**: Each stage has its own queue
   - Independent concurrency control
   - Clear state transitions
   - Easy to monitor per-stage progress

3. **Retry Per Stage**: Each stage tracks its own retry count
   - Download failures don't affect transcription retries
   - Configurable max_retries per stage

4. **Graceful Degradation**: Summary failure doesn't block completion
   - Transcription success is primary goal
   - Summary is optional enhancement

## File Structure

```
app/
├── task_queue.py      # New file (this implementation)
├── worker.py          # Will be refactored in Task 5
└── database.py        # Existing, unchanged
```

## Testing Strategy

1. **Unit Tests**: Test each class independently
2. **Integration Tests**: Test state transitions
3. **Concurrency Tests**: Verify max_workers limits
4. **Edge Cases**: Cancel, retry, failure handling

---

Created: 2026-04-19
Task: Task 3 - 并发队列架构设计