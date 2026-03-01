import os
import importlib
import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-service"))

import app.database as database
from app.worker import ProcessWorker
from ui.main_window import MainWindow

DownloadResult = importlib.import_module("services.downloader").DownloadResult
_transcriber = importlib.import_module("services.transcriber")
TranscriptionResult = _transcriber.TranscriptionResult
TranscriptionSegment = _transcriber.TranscriptionSegment


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.init_db()
    yield path
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


class FakeWorkerManager(QObject):
    worker_finished = Signal(int, bool, str)

    def __init__(self):
        super().__init__()
        self.calls = []

    def start_worker(self, video_id: int, url: str, title: str, bilibili_id: str):
        self.calls.append((video_id, url, title, bilibili_id))
        database.update_video_status(video_id, "processing")
        database.add_transcript(video_id, 0.0, 3.2, "欢迎观看本视频", 0)
        database.add_transcript(video_id, 3.2, 7.5, "这是一个完整流程测试", 1)
        database.add_summary(
            video_id,
            "本视频演示了添加视频、下载、转录和摘要的完整流程。",
            ["添加视频", "完成转录", "生成摘要"],
        )
        database.update_video_status(video_id, "completed")
        self.worker_finished.emit(video_id, True, "处理完成")


def test_database_roundtrip_and_pipeline_writes_records(qapp, temp_db, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    video_id = database.add_video(
        bilibili_id="BV1TEST12345",
        title="测试视频",
        url="https://www.bilibili.com/video/BV1TEST12345",
        duration=0,
        status="pending",
    )
    assert video_id is not None

    worker = ProcessWorker(
        video_id=video_id,
        url="https://www.bilibili.com/video/BV1TEST12345",
        title="测试视频",
        bilibili_id="BV1TEST12345",
        max_retries=1,
    )

    monkeypatch.setattr(
        "app.worker.download_video",
        lambda **kwargs: DownloadResult(success=True, file_path="C:/tmp/test_audio.mp3"),
    )
    monkeypatch.setattr(
        "app.worker.transcribe_audio",
        lambda **kwargs: TranscriptionResult(
            success=True,
            segments=[
                TranscriptionSegment(start=0.0, end=3.2, text="欢迎观看本视频"),
                TranscriptionSegment(start=3.2, end=7.5, text="这是一个完整流程测试"),
            ],
            full_text="欢迎观看本视频 这是一个完整流程测试",
        ),
    )
    monkeypatch.setattr(
        "app.worker.summarize_text",
        lambda *args, **kwargs: "1. 添加视频 2. 完成转录 3. 生成摘要",
    )

    finished = []
    worker.finished.connect(lambda video_id, success, message: finished.append((video_id, success, message)))

    worker.run()

    details = database.get_video_with_details(video_id)
    assert details is not None
    assert details["status"] == "completed"
    assert len(details["transcripts"]) == 2
    assert details["summary"]["summary_text"] == "1. 添加视频 2. 完成转录 3. 生成摘要"
    assert details["summary"]["key_points"] == ["添加视频", "完成转录", "生成摘要"]
    assert finished == [(video_id, True, "处理完成")]


def test_ui_add_video_triggers_pipeline_and_refreshes_tabs(qapp, temp_db, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    fake_manager = FakeWorkerManager()
    window = MainWindow(worker_manager=fake_manager)

    transcript_refreshed = []
    summary_refreshed = []
    monkeypatch.setattr(window.transcript_tab, "refresh", lambda: transcript_refreshed.append(True))
    monkeypatch.setattr(window.summary_tab, "refresh", lambda: summary_refreshed.append(True))

    url = "https://www.bilibili.com/video/BV1FLOW12345"
    window.video_list_tab.url_input.setText(url)
    window.video_list_tab.add_btn.click()

    details = database.get_video_by_bilibili_id("BV1FLOW12345")
    assert details is not None
    assert details["id"] is not None
    assert details["status"] == "completed"
    assert fake_manager.calls and fake_manager.calls[0][1] == url
    assert transcript_refreshed
    assert summary_refreshed

    all_details = database.get_video_with_details(details["id"])
    assert all_details is not None
    assert len(all_details["transcripts"]) == 2
    assert all_details["summary"]["summary_text"].startswith("本视频演示了")
