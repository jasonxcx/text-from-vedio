"""SQLite database module for Bilibili ASR System."""

import sqlite3
import json
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

DATABASE_PATH = "bilibili_asr.db"


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database and create tables if they don't exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bilibili_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                duration INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Transcripts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                start_seconds REAL NOT NULL,
                end_seconds REAL NOT NULL,
                text TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
            )
        """)
        
        # Summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL UNIQUE,
                summary_text TEXT NOT NULL,
                key_points TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_bilibili_id ON videos(bilibili_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(video_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_order ON transcripts(order_index)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_video_id ON summaries(video_id)")
        
        conn.commit()


# ==================== Video CRUD ====================

def add_video(bilibili_id: str, title: str, url: str, duration: int = 0, status: str = "pending") -> Optional[int]:
    """Add a new video to the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO videos (bilibili_id, title, url, duration, status) VALUES (?, ?, ?, ?, ?)",
            (bilibili_id, title, url, duration, status)
        )
        conn.commit()
        return cursor.lastrowid


def get_video(video_id: int) -> Optional[dict]:
    """Get a video by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_video_by_bilibili_id(bilibili_id: str) -> Optional[dict]:
    """Get a video by Bilibili ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE bilibili_id = ?", (bilibili_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_videos(status: Optional[str] = None) -> list:
    """Get all videos, optionally filtered by status."""
    with get_db() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM videos WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM videos ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_video_status(video_id: int, status: str) -> bool:
    """Update video status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE videos SET status = ? WHERE id = ?", (status, video_id))
        conn.commit()
        return cursor.rowcount > 0


def update_video(video_id: int, title: Optional[str] = None, duration: Optional[int] = None, status: Optional[str] = None) -> bool:
    """Update video details."""
    with get_db() as conn:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if duration is not None:
            updates.append("duration = ?")
            params.append(duration)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        
        if not updates:
            return False
        
        params.append(video_id)
        query = f"UPDATE videos SET {', '.join(updates)} WHERE id = ?"
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0


def delete_video(video_id: int) -> bool:
    """Delete a video and its related data."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()
        return cursor.rowcount > 0


# ==================== Transcript CRUD ====================

def add_transcript(video_id: int, start_seconds: float, end_seconds: float, text: str, order_index: int) -> Optional[int]:
    """Add a transcript segment."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transcripts (video_id, start_seconds, end_seconds, text, order_index) VALUES (?, ?, ?, ?, ?)",
            (video_id, start_seconds, end_seconds, text, order_index)
        )
        conn.commit()
        return cursor.lastrowid


def add_transcripts_batch(transcripts: list) -> None:
    """Add multiple transcript segments in batch."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO transcripts (video_id, start_seconds, end_seconds, text, order_index) VALUES (?, ?, ?, ?, ?)",
            [(t["video_id"], t["start_seconds"], t["end_seconds"], t["text"], t["order_index"]) for t in transcripts]
        )
        conn.commit()


def get_transcripts_by_video(video_id: int) -> list:
    """Get all transcripts for a video."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transcripts WHERE video_id = ? ORDER BY order_index", (video_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_transcripts_by_video(video_id: int) -> int:
    """Delete all transcripts for a video."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
        conn.commit()
        return cursor.rowcount


# ==================== Summary CRUD ====================

def add_summary(video_id: int, summary_text: str, key_points: list) -> Optional[int]:
    """Add a summary for a video."""
    with get_db() as conn:
        cursor = conn.cursor()
        key_points_json = json.dumps(key_points, ensure_ascii=False)
        cursor.execute(
            "INSERT OR REPLACE INTO summaries (video_id, summary_text, key_points) VALUES (?, ?, ?)",
            (video_id, summary_text, key_points_json)
        )
        conn.commit()
        return cursor.lastrowid


def get_summary_by_video(video_id: int) -> Optional[dict]:
    """Get summary for a video."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM summaries WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result["key_points"] = json.loads(result["key_points"])
            return result
        return None


def update_summary(video_id: int, summary_text: str, key_points: list) -> bool:
    """Update a summary."""
    with get_db() as conn:
        cursor = conn.cursor()
        key_points_json = json.dumps(key_points, ensure_ascii=False)
        cursor.execute(
            "UPDATE summaries SET summary_text = ?, key_points = ? WHERE video_id = ?",
            (summary_text, key_points_json, video_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_summary(video_id: int) -> bool:
    """Delete a summary."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM summaries WHERE video_id = ?", (video_id,))
        conn.commit()
        return cursor.rowcount > 0


# ==================== Utility Functions ====================

def get_video_with_details(video_id: int) -> Optional[dict]:
    """Get video with its transcripts and summary."""
    video = get_video(video_id)
    if not video:
        return None
    
    video["transcripts"] = get_transcripts_by_video(video_id)
    video["summary"] = get_summary_by_video(video_id)
    return video


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")
