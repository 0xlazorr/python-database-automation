"""common.py - Shared database helpers, configuration, and structured logging.

Part of the Database Automation Suite.
Provides connection factory with enforced foreign keys, centralized
configuration from environment variables, and structured logging to
logs/automation.log matching the SIWES report specifications.
"""

import os
import sys
import logging
from pathlib import Path
import sqlite3

# Base directories
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
BACKUPS_DIR = BASE_DIR / "backups"
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"
SQL_DIR = BASE_DIR / "sql"

# Ensure runtime directories exist
for directory in (LOGS_DIR, BACKUPS_DIR, REPORTS_DIR, DATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# Configuration from environment with robust defaults
DEFAULT_DB_PATH = str(BASE_DIR / "records.db")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB_PATH)
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", 3))
LOG_FILE = LOGS_DIR / "automation.log"


class CustomFormatter(logging.Formatter):
    """Custom formatter providing exact millisecond precision: YYYY-MM-DD HH:MM:SS,mmm"""
    def formatTime(self, record, datefmt=None):
        import datetime
        dt = datetime.datetime.fromtimestamp(record.created)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f",{int(record.msecs):03d}"



def setup_logger(name: str, log_to_console: bool = False) -> logging.Logger:
    """Configures and returns a logger instance writing to logs/automation.log.
    
    Format matches: 2026-11-02 07:18:51,859 INFO <name>: <message>
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = CustomFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    """Creates a SQLite connection with foreign keys strictly enabled.
    
    SQLite does not enforce foreign keys by default; setting PRAGMA foreign_keys = ON
    is essential for referential integrity.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str = None, force_reset: bool = False) -> sqlite3.Connection:
    """Initializes the database schema and seed data."""
    path = db_path or DB_PATH
    if force_reset and os.path.exists(path):
        os.remove(path)

    conn = get_db_connection(path)
    schema_file = SQL_DIR / "schema.sql"
    seed_file = SQL_DIR / "seed.sql"

    if schema_file.exists():
        with open(schema_file, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

    if seed_file.exists():
        with open(seed_file, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

    conn.commit()
    return conn
