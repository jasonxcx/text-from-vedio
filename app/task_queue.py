"""
阶段分离的任务队列系统

实现基于阶段的任务队列管理，支持：
- 下载队列：可并发（默认max_workers=3）
- 转录队列：单线程（max_workers=1，GPU限制）
- 摘要队列：可并发（默认max_workers=N）

状态流转：
pending → queued_download → downloading → queued_transcribe → transcribing 
                                                              ↓
                                                    queued_summary → summarizing → completed
"""

from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import logging
import time
from queue import Queue, Empty
from threading import Lock

logger = logging.getLogger(__name__)


class TaskStage(Enum):
    """任务阶段枚举"""
    PENDING = auto()
    QUEUED_DOWNLOAD = auto()
    DOWNLOADING = auto()
    QUEUED_TRANSCRIBE = auto()
    TRANSCRIBING = auto()
    QUEUED_SUMMARY = auto()
    SUMMARIZING = auto()
    COMPLETED = auto()
    FAILED = auto()
    
    @classmethod
    def to_status_string(cls, stage: 'TaskStage') -> str:
        """转换为数据库状态字符串"""
        mapping = {
            cls.PENDING: "pending",
            cls.QUEUED_DOWNLOAD: "queued_download",
            cls.DOWNLOADING: "downloading",
            cls.QUEUED_TRANSCRIBE: "queued_transcribe",
            cls.TRANSCRIBING: "transcribing",
            cls.QUEUED_SUMMARY: "queued_summary",
            cls.SUMMARIZING: "summarizing",
            cls.COMPLETED: "completed",
            cls.FAILED: "failed",
        }
        return mapping.get(stage, "unknown")
    
    @classmethod
    def to_display_name(cls, stage: 'TaskStage') -> str:
        """转换为中文显示名称"""
        mapping = {
            cls.PENDING: "等待中",
            cls.QUEUED_DOWNLOAD: "排队下载",
            cls.DOWNLOADING: "下载中",
            cls.QUEUED_TRANSCRIBE: "排队转录",
            cls.TRANSCRIBING: "转录中",
            cls.QUEUED_SUMMARY: "排队摘要",
            cls.SUMMARIZING: "整理中",
            cls.COMPLETED: "已完成",
            cls.FAILED: "失败",
        }
        return mapping.get(stage, "未知")


@dataclass
class Task:
    """任务数据类"""
    video_id: int
    url: str
    title: str
    bilibili_id: str
    stage: TaskStage = TaskStage.PENDING
    result: Any = None  # 存储阶段执行结果
    error: Optional[str] = None
    retry_count: Dict[TaskStage, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    audio_path: Optional[str] = None  # 下载后的音频路径
    transcription_result: Any = None  # 转录结果
    summary_result: Any = None  # 摘要结果
    _is_cancelled: bool = False
    
    def __post_init__(self):
        """初始化各阶段重试计数"""
        for stage in TaskStage:
            if stage not in self.retry_count:
                self.retry_count[stage] = 0
    
    def cancel(self):
        """取消任务"""
        self._is_cancelled = True
    
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._is_cancelled
    
    def increment_retry(self, stage: TaskStage) -> int:
        """增加指定阶段的重试计数"""
        self.retry_count[stage] = self.retry_count.get(stage, 0) + 1
        return self.retry_count[stage]
    
    def get_retry_count(self, stage: TaskStage) -> int:
        """获取指定阶段的重试计数"""
        return self.retry_count.get(stage, 0)


class TaskRunnable(QRunnable):
    """可执行的任务包装器"""
    
    def __init__(self, task: Task, executor: Callable[[Task], None], 
                 on_finished: Callable[[Task], None]):
        super().__init__()
        self.task = task
        self.executor = executor
        self.on_finished = on_finished
        self.setAutoDelete(True)
    
    def run(self):
        """在线程池中执行"""
        try:
            if not self.task.is_cancelled():
                self.executor(self.task)
        except Exception as e:
            logger.exception(f"Task {self.task.video_id} execution error: {e}")
            self.task.error = str(e)
            self.task.stage = TaskStage.FAILED
        finally:
            self.on_finished(self.task)


class StageQueue:
    """阶段队列基类
    
    管理特定阶段的任务队列，支持并发控制。
    """
    
    def __init__(self, name: str, max_workers: int, 
                 stage: TaskStage, next_stage: Optional[TaskStage]):
        """
        初始化阶段队列
        
        Args:
            name: 队列名称
            max_workers: 最大并发数
            stage: 当前阶段
            next_stage: 完成后转换到的下一阶段
        """
        self.name = name
        self.max_workers = max_workers
        self.stage = stage
        self.next_stage = next_stage
        self.queue: Queue[Task] = Queue()
        self.active_tasks: Dict[int, Task] = {}
        self.worker_pool = QThreadPool()
        self.worker_pool.setMaxThreadCount(max_workers)
        self._shutdown = False
        self._lock = Lock()
        self._on_task_finished_callback: Optional[Callable[[Task, bool], None]] = None
    
    def set_on_task_finished(self, callback: Callable[[Task, bool], None]):
        """设置任务完成回调"""
        self._on_task_finished_callback = callback
    
    def submit(self, task: Task) -> bool:
        """
        提交任务到队列
        
        Args:
            task: 要提交的任务
            
        Returns:
            是否成功提交
        """
        if self._shutdown:
            logger.warning(f"Queue {self.name} is shutdown, cannot submit task")
            return False
        
        with self._lock:
            self.queue.put(task)
            logger.info(f"Task {task.video_id} submitted to {self.name} queue")
        
        self._process_queue()
        return True
    
    def _process_queue(self):
        """处理队列中的任务"""
        while True:
            with self._lock:
                if self._shutdown:
                    break
                if len(self.active_tasks) >= self.max_workers:
                    break
                try:
                    task = self.queue.get_nowait()
                    self.active_tasks[task.video_id] = task
                except Empty:
                    break
            
            # 在锁外执行任务提交
            self._execute_task(task)
    
    def _execute_task(self, task: Task):
        """
        执行任务
        
        创建TaskRunnable并提交到线程池。
        """
        runnable = TaskRunnable(
            task=task,
            executor=self._run_task,
            on_finished=self._on_task_finished
        )
        self.worker_pool.start(runnable)
        logger.info(f"Task {task.video_id} started in {self.name} queue")
    
    def _run_task(self, task: Task):
        """
        执行任务的具体逻辑
        
        子类需要重写此方法实现具体的处理逻辑。
        """
        raise NotImplementedError("Subclass must implement _run_task")
    
    def _on_task_finished(self, task: Task):
        """
        任务完成回调
        
        Args:
            task: 完成的任务
        """
        success = task.stage != TaskStage.FAILED and not task.is_cancelled()
        
        with self._lock:
            self.active_tasks.pop(task.video_id, None)
        
        logger.info(f"Task {task.video_id} finished in {self.name} queue, success={success}")
        
        # 调用外部回调
        if self._on_task_finished_callback:
            self._on_task_finished_callback(task, success)
        
        # 继续处理队列
        self._process_queue()
    
    def get_active_count(self) -> int:
        """获取活跃任务数"""
        with self._lock:
            return len(self.active_tasks)
    
    def get_queued_count(self) -> int:
        """获取队列中等待的任务数"""
        return self.queue.qsize()
    
    def cancel_task(self, video_id: int) -> bool:
        """
        取消任务
        
        Args:
            video_id: 视频ID
            
        Returns:
            是否成功取消
        """
        with self._lock:
            # 如果任务正在执行
            if video_id in self.active_tasks:
                task = self.active_tasks[video_id]
                task.cancel()
                return True
        
        # 尝试从队列中移除（需要遍历）
        # 由于Queue不支持直接移除，标记为取消即可
        return False
    
    def shutdown(self):
        """关闭队列"""
        self._shutdown = True
        self.worker_pool.clear()
        self.worker_pool.waitForDone(5000)
        logger.info(f"Queue {self.name} shutdown complete")
    
    def is_empty(self) -> bool:
        """检查队列是否为空（无活跃和等待任务）"""
        return self.get_active_count() == 0 and self.get_queued_count() == 0


class TaskQueueManager(QObject):
    """
    任务队列管理器
    
    管理三个阶段队列：下载、转录、摘要
    处理任务状态流转和信号发射
    """
    
    # 信号定义
    task_stage_changed = Signal(int, str)  # (video_id, stage_name)
    task_progress = Signal(int, int, str)  # (video_id, percent, message)
    task_completed = Signal(int, bool, str)  # (video_id, success, message)
    task_error = Signal(int, str)  # (video_id, error_message)
    all_tasks_finished = Signal()  # 所有任务完成
    
    # 阶段中文映射（兼容现有UI）
    STAGE_NAMES = {
        "pending": "等待中",
        "queued_download": "排队下载",
        "downloading": "下载中",
        "queued_transcribe": "排队转录",
        "transcribing": "转录中",
        "queued_summary": "排队摘要",
        "summarizing": "整理中",
        "completed": "已完成",
        "failed": "失败",
        "cancelled": "已取消"
    }
    
    def __init__(self, 
                 download_concurrency: int = 3,
                 transcribe_concurrency: int = 1,
                 summary_concurrency: int = 3,
                 max_retries: int = 3):
        """
        初始化任务队列管理器
        
        Args:
            download_concurrency: 下载并发数
            transcribe_concurrency: 转录并发数（建议为1，GPU限制）
            summary_concurrency: 摘要并发数
            max_retries: 每阶段最大重试次数
        """
        super().__init__()
        
        self.download_concurrency = download_concurrency
        self.transcribe_concurrency = transcribe_concurrency
        self.summary_concurrency = summary_concurrency
        self.max_retries = max_retries
        
        # 任务存储
        self.tasks: Dict[int, Task] = {}
        self._lock = Lock()
        
        # 阶段队列（将在集成时由子类或外部设置）
        self.download_queue: Optional[StageQueue] = None
        self.transcribe_queue: Optional[StageQueue] = None
        self.summary_queue: Optional[StageQueue] = None
        
        self._setup_queues()
        
        logger.info(f"TaskQueueManager initialized: download={download_concurrency}, "
                    f"transcribe={transcribe_concurrency}, summary={summary_concurrency}")
    
    def _setup_queues(self):
        """
        设置各阶段队列
        
        创建基础队列实例。具体的执行逻辑将在Task 5集成时实现。
        """
        # 创建下载队列
        self.download_queue = StageQueue(
            name="download",
            max_workers=self.download_concurrency,
            stage=TaskStage.DOWNLOADING,
            next_stage=TaskStage.QUEUED_TRANSCRIBE
        )
        self.download_queue.set_on_task_finished(self._on_download_finished)
        
        # 创建转录队列
        self.transcribe_queue = StageQueue(
            name="transcribe",
            max_workers=self.transcribe_concurrency,
            stage=TaskStage.TRANSCRIBING,
            next_stage=TaskStage.QUEUED_SUMMARY
        )
        self.transcribe_queue.set_on_task_finished(self._on_transcribe_finished)
        
        # 创建摘要队列
        self.summary_queue = StageQueue(
            name="summary",
            max_workers=self.summary_concurrency,
            stage=TaskStage.SUMMARIZING,
            next_stage=TaskStage.COMPLETED
        )
        self.summary_queue.set_on_task_finished(self._on_summary_finished)
    
    def submit_task(self, video_id: int, url: str, title: str, bilibili_id: str) -> Task:
        """
        提交新任务
        
        Args:
            video_id: 视频数据库ID
            url: B站视频URL
            title: 视频标题
            bilibili_id: BV号
            
        Returns:
            创建的任务对象
        """
        task = Task(
            video_id=video_id,
            url=url,
            title=title,
            bilibili_id=bilibili_id,
            stage=TaskStage.PENDING
        )
        
        with self._lock:
            self.tasks[video_id] = task
        
        logger.info(f"Task {video_id} created for {bilibili_id}")
        
        # 立即转换到下载队列
        self._transition_task(task, TaskStage.QUEUED_DOWNLOAD)
        
        return task
    
    def _transition_task(self, task: Task, new_stage: TaskStage):
        """
        任务阶段转换
        
        Args:
            task: 要转换的任务
            new_stage: 新阶段
        """
        old_stage = task.stage
        task.stage = new_stage
        
        stage_name = new_stage.name.lower()
        logger.info(f"Task {task.video_id} stage transition: {old_stage.name} -> {new_stage.name}")
        
        # 发射状态变更信号
        self.task_stage_changed.emit(task.video_id, stage_name)
        
        # 根据新阶段分发到对应队列
        if new_stage == TaskStage.QUEUED_DOWNLOAD:
            if self.download_queue:
                self.download_queue.submit(task)
        elif new_stage == TaskStage.QUEUED_TRANSCRIBE:
            if self.transcribe_queue:
                self.transcribe_queue.submit(task)
        elif new_stage == TaskStage.QUEUED_SUMMARY:
            if self.summary_queue:
                self.summary_queue.submit(task)
        elif new_stage == TaskStage.COMPLETED:
            self.task_completed.emit(task.video_id, True, "处理完成")
            self._check_all_finished()
        elif new_stage == TaskStage.FAILED:
            self.task_completed.emit(task.video_id, False, task.error or "处理失败")
            self._check_all_finished()
    
    def _on_download_finished(self, task: Task, success: bool):
        """
        下载完成回调
        
        Args:
            task: 完成的任务
            success: 是否成功
        """
        if task.is_cancelled():
            task.stage = TaskStage.FAILED
            task.error = "用户取消"
            self._transition_task(task, TaskStage.FAILED)
            return
        
        if success and task.audio_path:
            # 下载成功，进入转录队列
            self._transition_task(task, TaskStage.QUEUED_TRANSCRIBE)
        else:
            # 下载失败
            retry_count = task.get_retry_count(TaskStage.DOWNLOADING)
            if retry_count < self.max_retries:
                task.increment_retry(TaskStage.DOWNLOADING)
                logger.info(f"Task {task.video_id} download retry {retry_count + 1}/{self.max_retries}")
                # 重新提交到下载队列
                self._transition_task(task, TaskStage.QUEUED_DOWNLOAD)
            else:
                task.stage = TaskStage.FAILED
                task.error = task.error or "下载失败"
                self._transition_task(task, TaskStage.FAILED)
    
    def _on_transcribe_finished(self, task: Task, success: bool):
        """
        转录完成回调
        
        Args:
            task: 完成的任务
            success: 是否成功
        """
        if task.is_cancelled():
            task.stage = TaskStage.FAILED
            task.error = "用户取消"
            self._transition_task(task, TaskStage.FAILED)
            return
        
        if success and task.transcription_result:
            # 转录成功，进入摘要队列（如果启用）
            from config import config
            if config.get('summary.enabled', True):
                self._transition_task(task, TaskStage.QUEUED_SUMMARY)
            else:
                # 摘要未启用，直接完成
                self._transition_task(task, TaskStage.COMPLETED)
        else:
            # 转录失败
            retry_count = task.get_retry_count(TaskStage.TRANSCRIBING)
            if retry_count < self.max_retries:
                task.increment_retry(TaskStage.TRANSCRIBING)
                logger.info(f"Task {task.video_id} transcribe retry {retry_count + 1}/{self.max_retries}")
                self._transition_task(task, TaskStage.QUEUED_TRANSCRIBE)
            else:
                task.stage = TaskStage.FAILED
                task.error = task.error or "转录失败"
                self._transition_task(task, TaskStage.FAILED)
    
    def _on_summary_finished(self, task: Task, success: bool):
        """
        摘要完成回调
        
        Args:
            task: 完成的任务
            success: 是否成功
        """
        if task.is_cancelled():
            task.stage = TaskStage.FAILED
            task.error = "用户取消"
            self._transition_task(task, TaskStage.FAILED)
            return
        
        # 摘要失败不影响整体完成（转录已成功）
        if success:
            self._transition_task(task, TaskStage.COMPLETED)
        else:
            # 摘要失败但转录成功，仍标记为完成
            logger.warning(f"Task {task.video_id} summary failed but transcription succeeded")
            self._transition_task(task, TaskStage.COMPLETED)
    
    def _check_all_finished(self):
        """检查是否所有任务都已完成"""
        with self._lock:
            for task in self.tasks.values():
                if task.stage not in (TaskStage.COMPLETED, TaskStage.FAILED):
                    return
        
        self.all_tasks_finished.emit()
        logger.info("All tasks finished")
    
    def cancel_task(self, video_id: int) -> bool:
        """
        取消任务
        
        Args:
            video_id: 视频ID
            
        Returns:
            是否成功取消
        """
        with self._lock:
            if video_id not in self.tasks:
                return False
            
            task = self.tasks[video_id]
            task.cancel()
        
        # 尝试从各队列取消
        if self.download_queue:
            self.download_queue.cancel_task(video_id)
        if self.transcribe_queue:
            self.transcribe_queue.cancel_task(video_id)
        if self.summary_queue:
            self.summary_queue.cancel_task(video_id)
        
        logger.info(f"Task {video_id} cancelled")
        return True
    
    def cancel_all(self):
        """取消所有任务"""
        with self._lock:
            for video_id in list(self.tasks.keys()):
                self.cancel_task(video_id)
        
        logger.info("All tasks cancelled")
    
    def get_task(self, video_id: int) -> Optional[Task]:
        """
        获取任务
        
        Args:
            video_id: 视频ID
            
        Returns:
            任务对象或None
        """
        with self._lock:
            return self.tasks.get(video_id)
    
    def get_task_status(self, video_id: int) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            video_id: 视频ID
            
        Returns:
            状态字典或None
        """
        task = self.get_task(video_id)
        if not task:
            return None
        
        return {
            "video_id": task.video_id,
            "stage": task.stage.name,
            "stage_display": TaskStage.to_display_name(task.stage),
            "status": TaskStage.to_status_string(task.stage),
            "error": task.error,
            "created_at": task.created_at,
            "is_cancelled": task.is_cancelled(),
        }
    
    def get_queue_status(self) -> Dict[str, Dict]:
        """
        获取所有队列状态
        
        Returns:
            队列状态字典
        """
        return {
            "download": {
                "queued": self.download_queue.get_queued_count() if self.download_queue else 0,
                "active": self.download_queue.get_active_count() if self.download_queue else 0,
                "max_workers": self.download_concurrency,
            },
            "transcribe": {
                "queued": self.transcribe_queue.get_queued_count() if self.transcribe_queue else 0,
                "active": self.transcribe_queue.get_active_count() if self.transcribe_queue else 0,
                "max_workers": self.transcribe_concurrency,
            },
            "summary": {
                "queued": self.summary_queue.get_queued_count() if self.summary_queue else 0,
                "active": self.summary_queue.get_active_count() if self.summary_queue else 0,
                "max_workers": self.summary_concurrency,
            },
        }
    
    def has_active_tasks(self) -> bool:
        """检查是否有活跃任务"""
        status = self.get_queue_status()
        return any(q["active"] > 0 or q["queued"] > 0 for q in status.values())
    
    def shutdown(self):
        """关闭所有队列"""
        if self.download_queue:
            self.download_queue.shutdown()
        if self.transcribe_queue:
            self.transcribe_queue.shutdown()
        if self.summary_queue:
            self.summary_queue.shutdown()
        
        logger.info("TaskQueueManager shutdown complete")
    
    def get_stage_name(self, stage: str) -> str:
        """获取阶段的中文显示名称"""
        return self.STAGE_NAMES.get(stage, stage)