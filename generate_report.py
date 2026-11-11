#!/usr/bin/env python3
"""generate_report.py - Automated Analytical Enrolment Report Generator.

Executes aggregated queries against the v_department_summary view and
course enrolment metrics. Exports results into a dated CSV file,
measures query execution time in milliseconds, and logs the outcome.
"""

import os
import sys
import time
import csv
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    get_db_connection,
    setup_logger,
    DB_PATH,
    REPORTS_DIR
)

logger = setup_logger("generate_report")


def generate_enrolment_report(db_path: str = None, reports_dir: Path = None) -> tuple[Path, int, float]:
    """Generates a dated CSV report summarizing departmental student counts.
    
    Returns:
        (report_file_path, department_count, execution_time_ms)
    """
    path = db_path or DB_PATH
    out_dir = reports_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Auto-initialize database if not yet present
    if not Path(path).exists():
        from common import init_database
        init_database(path)

    conn = get_db_connection(path)

    # Measure execution time of reporting query
    start_time = time.perf_counter()

    query = """
    SELECT department_id,
           department_name,
           total_students
    FROM v_department_summary
    ORDER BY department_id ASC;
    """
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    execution_time_ms = (time.perf_counter() - start_time) * 1000.0

    today_str = datetime.now().strftime("%Y%m%d")
    report_filename = f"enrolment_summary_{today_str}.csv"
    report_file_path = out_dir / report_filename

    with open(report_file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["department_id", "department_name", "total_students"])
        for r in rows:
            writer.writerow([r["department_id"], r["department_name"], r["total_students"]])

    conn.close()

    dept_count = len(rows)
    rel_path = f"reports/{report_filename}"

    logger.info(f"report={rel_path} departments={dept_count} run_time={execution_time_ms:.2f}ms")

    print(f"Report written : {rel_path}")
    print(f"Departments    : {dept_count} | Run time: {execution_time_ms:.2f} ms")

    return report_file_path, dept_count, execution_time_ms


if __name__ == "__main__":
    generate_enrolment_report()
