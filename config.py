"""
Configuration module for BiliBili ASR System

All settings can be configured via:
1. Environment variables
2. config.json file (auto-created if not exists)
3. GUI settings panel
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

# Project paths
BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_FILE = BASE_DIR / "config.json"

# Ensure directories exist
DOWNLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Default configuration
DEFAULT_CONFIG = {
    # Transcription Settings
    "transcription": {
        "model": "large-v3",  # faster-whisper model: tiny, base, small, medium, large-v1/v2/v3
        "device": "cuda",  # cuda or cpu
        "compute_type": "auto",  # auto, float16, float32, int8
        "language": "auto",  # auto, zh, en, ja, etc.
        "chunk_duration": 600,  # seconds, for long audio segmentation
    },
    # Summary Settings - Multiple providers supported
    "summary": {
        "enabled": True,  # Whether to enable summary generation
        "provider": "ollama",  # ollama, openai, custom
        # Provider-specific settings
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5",
            "api_key": "",  # Ollama usually doesn't need API key
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "api_key": "",
        },
        "custom": {
            "base_url": "",
            "model": "",
            "api_key": "",
        },
        # Generation parameters
        "max_length": 500,
        "temperature": 0.7,
    },
    # App Settings
    "app": {
        "window_width": 800,
        "window_height": 650,
        "title": "BiliBili ASR",
        "theme": "dark",  # dark, light
    }
}


class Config:
    """Configuration manager with persistent storage"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _load(self):
        """Load configuration from file or create default"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                self._config = self._merge_config(DEFAULT_CONFIG, saved_config)
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()
    
    def _merge_config(self, default: Dict, saved: Dict) -> Dict:
        """Merge saved config with defaults (for backward compatibility)"""
        result = default.copy()
        for key, value in saved.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    result[key] = self._merge_config(result[key], value)
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    
    def save(self):
        """Save current configuration to file"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default=None):
        """Get config value by dot notation (e.g., 'transcription.model')"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Set config value by dot notation"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save()
    
    @property
    def transcription(self) -> Dict:
        """Get transcription settings"""
        return self._config.get("transcription", {})
    
    @property
    def summary(self) -> Dict:
        """Get summary settings"""
        return self._config.get("summary", {})
    
    @property
    def app(self) -> Dict:
        """Get app settings"""
        return self._config.get("app", {})
    
    # Convenience properties for backward compatibility
    @property
    def WHISPER_MODEL(self) -> str:
        return self.get('transcription.model', 'large-v3')
    
    @property
    def DEVICE(self) -> str:
        return self.get('transcription.device', 'cuda')
    
    @property
    def OLLAMA_MODEL(self) -> str:
        return self.get('summary.ollama.model', 'qwen2.5')
    
    @property
    def OLLAMA_HOST(self) -> str:
        return self.get('summary.ollama.base_url', 'http://localhost:11434')


# Create global config instance
_config = Config()

# Export for backward compatibility
WHISPER_MODEL = _config.WHISPER_MODEL
DEVICE = _config.DEVICE
OLLAMA_MODEL = _config.OLLAMA_MODEL
OLLAMA_HOST = _config.OLLAMA_HOST
WINDOW_WIDTH = _config.get('app.window_width', 800)
WINDOW_HEIGHT = _config.get('app.window_height', 650)
APP_TITLE = _config.get('app.title', 'BiliBili ASR')

# Export config instance for advanced usage
config: Config = _config
