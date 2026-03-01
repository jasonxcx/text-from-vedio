"""Logging configuration for the application"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# Create logs directory
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Log file path
LOG_FILE = LOG_DIR / f"bilibili_asr_{datetime.now().strftime('%Y%m%d')}.log"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # File handler -保存所有日志
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        # Console handler - 只显示INFO及以上
        logging.StreamHandler(sys.stdout)
    ]
)

# Set console handler level
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

# Get logger
logger = logging.getLogger(__name__)
logger.info(f"Logging initialized. Log file: {LOG_FILE}")

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name"""
    return logging.getLogger(name)
