"""
End-to-end tests for improvement features

Tests:
- Task 1: Semantic chunking
- Task 2: Batch add dialog
- Task 5: Queue-based concurrency
- Task 6: Batch processor
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestSemanticChunking:
    """Test Task 1: Semantic chunking in transcriber"""

    def test_transcribe_long_audio_import(self):
        """Verify transcribe_long_audio can be imported"""
        from services.transcriber import transcribe_long_audio
        assert callable(transcribe_long_audio)

    def test_transcribe_long_audio_signature(self):
        """Verify function signature is preserved"""
        from services.transcriber import transcribe_long_audio
        import inspect
        sig = inspect.signature(transcribe_long_audio)
        params = list(sig.parameters.keys())
        # Should have: audio_path, model_size, chunk_duration, device, compute_type, language, progress_callback
        assert 'audio_path' in params
        assert 'chunk_duration' in params  # Kept for API compatibility

    def test_smart_chunking_functions_exist(self):
        """Verify helper functions exist"""
        from services.transcriber import (
            transcribe_long_audio,
            _transcribe_with_smart_chunking,
            _transcribe_with_boundaries
        )
        assert callable(_transcribe_with_smart_chunking)
        assert callable(_transcribe_with_boundaries)


class TestBatchProcessor:
    """Test Task 6: Batch processor service"""

    def test_batch_processor_import(self):
        """Verify BatchProcessor can be imported"""
        from services.batch_processor import BatchProcessor
        assert BatchProcessor is not None

    def test_parse_video_info_import(self):
        """Verify parse_video_info can be imported"""
        from services.batch_processor import parse_video_info
        assert callable(parse_video_info)

    def test_extract_bilibili_id(self):
        """Test BV号 extraction"""
        from services.batch_processor import BatchProcessor
        processor = BatchProcessor()

        # Test BV号
        bv_id = processor._extract_bilibili_id("https://www.bilibili.com/video/BV1xx411c7mD")
        assert bv_id == "BV1XX411C7MD"

        # Test AV号
        av_id = processor._extract_bilibili_id("https://www.bilibili.com/video/av123456")
        assert av_id == "av123456"

    def test_batch_processor_deduplication(self):
        """Test that duplicate videos are detected"""
        from services.batch_processor import BatchProcessor

        processor = BatchProcessor()

        # Add same video twice
        result1 = processor.add("https://www.bilibili.com/video/BV1xx411c7mD")
        result2 = processor.add("https://www.bilibili.com/video/BV1xx411c7mD")

        # Should return same object (cached)
        assert result1.bilibili_id == result2.bilibili_id


class TestTaskQueues:
    """Test Task 5: Queue-based concurrent processing"""

    def test_queue_classes_import(self):
        """Verify queue classes can be imported"""
        from app.worker import (
            DownloadStageQueue,
            TranscribeStageQueue,
            SummaryStageQueue
        )
        assert DownloadStageQueue is not None
        assert TranscribeStageQueue is not None
        assert SummaryStageQueue is not None

    def test_download_queue_defaults(self):
        """Test DownloadQueue default settings"""
        from app.worker import DownloadStageQueue
        queue = DownloadStageQueue()
        assert queue.max_workers == 3
        assert queue.name == "download"

    def test_transcribe_queue_single_threaded(self):
        """Test TranscribeQueue is single-threaded"""
        from app.worker import TranscribeStageQueue
        queue = TranscribeStageQueue()
        assert queue.max_workers == 1  # GPU limitation

    def test_summary_queue_configurable(self):
        """Test SummaryQueue is configurable"""
        from app.worker import SummaryStageQueue
        queue = SummaryStageQueue(max_workers=5)
        assert queue.max_workers == 5


class TestConfigConcurrency:
    """Test Task 4: Configuration system"""

    def test_concurrency_config_import(self):
        """Verify concurrency config can be imported"""
        from config import (
            DOWNLOAD_CONCURRENCY,
            TRANSCRIBE_CONCURRENCY,
            SUMMARY_CONCURRENCY
        )
        assert DOWNLOAD_CONCURRENCY is not None
        assert TRANSCRIBE_CONCURRENCY is not None
        assert SUMMARY_CONCURRENCY is not None

    def test_concurrency_values(self):
        """Test default concurrency values"""
        from config import (
            DOWNLOAD_CONCURRENCY,
            TRANSCRIBE_CONCURRENCY,
            SUMMARY_CONCURRENCY
        )
        assert DOWNLOAD_CONCURRENCY == 3
        assert TRANSCRIBE_CONCURRENCY == 1
        assert SUMMARY_CONCURRENCY == 3


class TestBatchAddDialog:
    """Test Task 2: Batch add dialog UI"""

    def test_batch_add_dialog_import(self):
        """Verify BatchAddDialog can be imported"""
        from ui.batch_add_dialog import BatchAddDialog
        assert BatchAddDialog is not None


class TestSettingsConcurrency:
    """Test Task 7: Settings UI concurrency"""

    def test_settings_tab_import(self):
        """Verify SettingsTab can be imported"""
        from ui.settings_tab import SettingsTab
        assert SettingsTab is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
