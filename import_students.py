#!/usr/bin/env python3
"""import_students.py - Automated CSV-to-Database ETL Pipeline.

Extracts student data from CSV, transforms and validates each record,
and loads valid records into SQLite using atomic transactions and INSERT OR IGNORE.
Tracks duplicates and rejected rows with reasons, and synchronizes course enrolments.
"""

import sys
import re
import csv
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_db_connection, setup_logger, init_database, DB_PATH

logger = setup_logger("import_students")

# Regex pattern for Nigerian tertiary institution matriculation number:
# e.g., SEN/22/1001 (3 uppercase letters, slash, 2 digits, slash, 4 digits)
MATRIC_REGEX = re.compile(r"^[A-Z]{3}/\d{2}/\d{4}$")


def validate_row(row: dict, valid_dept_ids: set) -> tuple[bool, str]:
    """Validates an input CSV row against business rules.
    
    Returns:
        (is_valid, rejection_reason)
    """
    matric = row.get("matric_no", "").strip()
    full_name = row.get("full_name", "").strip()
    raw_dept = row.get("department_id", "").strip()
    email = row.get("email", "").strip()

    if not MATRIC_REGEX.match(matric):
        return False, "invalid matric number"

    try:
        dept_id = int(raw_dept)
        if dept_id not in valid_dept_ids:
            return False, "unknown department"
    except ValueError:
        return False, "unknown department"

    if "@" not in email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "invalid email"

    if not full_name:
        return False, "missing full name"

    return True, ""


def auto_enrol_students(conn):
    """Enrolls each student into every course offered by that student's department.
    
    Uses INSERT OR IGNORE to guarantee idempotency without duplicate key errors.
    """
    enrol_sql = """
    INSERT OR IGNORE INTO enrolments (student_id, course_id)
    SELECT s.student_id, c.course_id
    FROM students s
    JOIN courses c ON c.department_id = s.department_id;
    """
    conn.execute(enrol_sql)
    conn.commit()


def run_etl(csv_file_path: str, db_path: str = None) -> dict:
    """Executes the complete ETL pipeline."""
    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_file_path}")

    # Ensure schema & seed data exist
    init_database(db_path)
    conn = get_db_connection(db_path)

    # Fetch valid department IDs for foreign key validation
    with conn:
        dept_rows = conn.execute("SELECT department_id FROM departments").fetchall()
        valid_dept_ids = {row["department_id"] for row in dept_rows}

        # Fetch existing matric numbers to distinguish new inserts from duplicates
        existing_matric_rows = conn.execute("SELECT matric_no FROM students").fetchall()
        existing_matrics = {row["matric_no"] for row in existing_matric_rows}

    rows_read = 0
    rows_loaded = 0
    duplicates = 0
    rows_rejected = 0
    rejections = []
    seen_in_batch = set()
    to_insert = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            if not raw_row or not any(raw_row.values()):
                continue
            # Normalize whitespace in keys and values
            row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
            rows_read += 1
            matric = row.get("matric_no", "")

            # Pre-validation
            is_valid, reason = validate_row(row, valid_dept_ids)
            if not is_valid:
                rows_rejected += 1
                rejections.append((matric, reason))
                continue

            # Duplicate detection (either already in DB or duplicate in this file)
            if matric in existing_matrics or matric in seen_in_batch:
                duplicates += 1
                continue

            seen_in_batch.add(matric)
            to_insert.append((
                matric,
                row["full_name"].strip(),
                int(row["department_id"]),
                row["email"].strip()
            ))

    # Transactional batch insert
    if to_insert:
        with conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT OR IGNORE INTO students (matric_no, full_name, department_id, email)
                VALUES (?, ?, ?, ?)
                """,
                to_insert
            )
            rows_loaded = cursor.rowcount

    # Automatically synchronize departmental enrolments
    auto_enrol_students(conn)
    conn.close()

    # Log summary and rejections
    logger.info(f"read={rows_read} loaded={rows_loaded} duplicates={duplicates} rejected={rows_rejected}")
    for matric, reason in rejections:
        logger.warning(f"rejected {matric}: {reason}")

    # Output formatted statistics to console
    print(f"Rows read      : {rows_read}")
    print(f"Rows loaded    : {rows_loaded}")
    print(f"Duplicates     : {duplicates}")
    print(f"Rows rejected  : {rows_rejected}")
    for matric, reason in rejections:
        print(f"  rejected {matric}: {reason}")

    return {
        "read": rows_read,
        "loaded": rows_loaded,
        "duplicates": duplicates,
        "rejected": rows_rejected,
        "rejections": rejections
    }


if __name__ == "__main__":
    target_csv = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "data" / "students.csv")
    run_etl(target_csv)
