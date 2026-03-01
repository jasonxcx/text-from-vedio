import sys
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import QApplication
from app.database import init_db
from ui import MainWindow


def setup_logging():
    """Setup application logging"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"bilibili_asr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"=" * 60)
    logger.info(f"Application started")
    logger.info(f"Log file: {log_file}")
    logger.info(f"=" * 60)
    
    return log_file


def main():
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")
        
        logger.info("Creating Qt application...")
        app = QApplication(sys.argv)
        
        logger.info("Creating main window...")
        window = MainWindow()
        window.show()
        
        logger.info("Application ready")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main()
