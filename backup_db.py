#!/usr/bin/env python3
"""backup_db.py - Automated Database Backup Utility with Compression and Rotation.

Creates a consistent logical SQL dump using SQLite's iterdump(), compresses
it into a gzip archive (.sql.gz) with timestamped naming, rotates older archives
to respect the BACKUP_KEEP retention limit, and logs all operations.
"""

import os
import sys
import gzip
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    get_db_connection,
    setup_logger,
    DB_PATH,
    BACKUPS_DIR,
    BACKUP_KEEP
)

logger = setup_logger("backup_db")


def create_backup(db_path: str = None, backup_dir: Path = None, keep_count: int = None) -> tuple[Path, int, int]:
    """Generates a compressed database backup and rotates old archives.
    
    Returns:
        (backup_file_path, file_size_bytes, archives_kept_count)
    """
    path = db_path or DB_PATH
    out_dir = backup_dir or BACKUPS_DIR
    raw_keep = keep_count if keep_count is not None else int(os.environ.get("BACKUP_KEEP", BACKUP_KEEP))
    keep = max(1, raw_keep)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Verify database exists before attempting backup
    if not Path(path).exists():
        logger.error(f"Database file not found: {path}")
        raise FileNotFoundError(f"Database file not found: {path}")

    # Connect to database and dump SQL
    conn = get_db_connection(path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"records_{timestamp}.sql.gz"
    backup_file_path = out_dir / backup_filename

    # Write gzipped SQL dump with temporary foreign_keys=OFF pragma
    # to guarantee seamless table creation order upon restore
    with gzip.open(backup_file_path, "wt", encoding="utf-8") as gz_file:
        gz_file.write("PRAGMA foreign_keys = OFF;\n")
        for line in conn.iterdump():
            gz_file.write(f"{line}\n")
        gz_file.write("PRAGMA foreign_keys = ON;\n")
    conn.close()

    file_size = backup_file_path.stat().st_size

    # Archive Rotation: keep newest `keep` archives, delete older ones
    archives = sorted(
        out_dir.glob("records_*.sql.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    deleted_count = 0
    if len(archives) > keep:
        to_delete = archives[keep:]
        for old_file in to_delete:
            try:
                old_file.unlink()
                deleted_count += 1
            except OSError as e:
                logger.error(f"Failed to prune old archive {old_file}: {e}")

    # Re-evaluate remaining archives
    remaining_archives = sorted(out_dir.glob("records_*.sql.gz"))
    archives_kept = len(remaining_archives)

    # Relative display path
    rel_path = f"backups/{backup_filename}"
    logger.info(f"backup created: {rel_path} size={file_size} bytes kept={archives_kept} deleted={deleted_count}")

    print(f"Backup created : {rel_path} ({file_size} bytes)")
    print(f"Archives kept  : {archives_kept}")

    return backup_file_path, file_size, archives_kept


if __name__ == "__main__":
    create_backup()
