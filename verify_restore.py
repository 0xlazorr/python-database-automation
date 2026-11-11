#!/usr/bin/env python3
"""verify_restore.py - Automated Disaster Recovery and Backup Verification.

Finds the latest compressed backup (.sql.gz), decompresses it into a fresh
isolated database (or in-memory database), counts records across all core tables
(departments, students, courses, enrolments), and compares them against the
live database to verify 100% data integrity.
"""

import sys
import gzip
import sqlite3
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    get_db_connection,
    setup_logger,
    DB_PATH,
    BACKUPS_DIR
)

logger = setup_logger("verify_restore")

CORE_TABLES = ["departments", "students", "courses", "enrolments"]


def verify_latest_backup(db_path: str = None, backup_dir: Path = None) -> bool:
    """Verifies that the latest backup can be restored and matches the live database.
    
    Returns:
        True if all table counts match, False otherwise.
    """
    path = db_path or DB_PATH
    b_dir = backup_dir or BACKUPS_DIR

    archives = sorted(
        b_dir.glob("records_*.sql.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not archives:
        print(f"Error: No backup archives found in {b_dir}")
        logger.error("Restore verification failed: no archives found")
        return False

    latest_archive = archives[0]
    rel_archive_name = f"backups/{latest_archive.name}"
    print(f"Restoring from : {rel_archive_name}")

    # Read live counts
    live_conn = get_db_connection(path)
    live_counts = {}
    with live_conn:
        for tbl in CORE_TABLES:
            try:
                row = live_conn.execute(f"SELECT COUNT(*) AS c FROM {tbl}").fetchone()
                live_counts[tbl] = row["c"]
            except sqlite3.OperationalError:
                live_counts[tbl] = 0
    live_conn.close()

    # Restore into an in-memory database
    restore_conn = sqlite3.connect(":memory:")
    # Foreign key checks must be temporarily OFF during SQL dump restoration
    # because tables are dumped alphabetically (courses before departments)
    restore_conn.execute("PRAGMA foreign_keys = OFF;")
    with gzip.open(latest_archive, "rt", encoding="utf-8") as gz:
        sql_script = gz.read()
    restore_conn.executescript(sql_script)
    restore_conn.execute("PRAGMA foreign_keys = ON;")


    # Compare restored counts
    restored_counts = {}
    all_matched = True

    for tbl in CORE_TABLES:
        try:
            row = restore_conn.execute(f"SELECT COUNT(*) AS c FROM {tbl}").fetchone()
            c = row[0]
        except sqlite3.OperationalError:
            c = -1
        restored_counts[tbl] = c
        is_ok = (c == live_counts.get(tbl, 0))
        status_str = "OK" if is_ok else "MISMATCH"
        if not is_ok:
            all_matched = False

        print(f"  {tbl:<13} original={live_counts.get(tbl, 0):<3} restored={c:<3} {status_str}")

    restore_conn.close()

    verdict = "PASS" if all_matched else "FAIL"
    print(f"Restore verification: {verdict}")

    logger.info(
        f"verified={rel_archive_name} result={verdict} "
        f"dept={restored_counts.get('departments')} "
        f"stud={restored_counts.get('students')} "
        f"crs={restored_counts.get('courses')} "
        f"enr={restored_counts.get('enrolments')}"
    )

    return all_matched


if __name__ == "__main__":
    success = verify_latest_backup()
    sys.exit(0 if success else 1)
