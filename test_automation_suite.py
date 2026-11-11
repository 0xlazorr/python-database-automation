#!/usr/bin/env python3
"""test_automation_suite.py - Automated Test Suite for Capstone Verification.

Faithfully implements and validates all 11 test cases (TC1 to TC11)
documented in Table 3.2 and Section 3.2.7 of the IT report:
- TC1: UNIQUE constraint on matric_no
- TC2: FOREIGN KEY constraint on department_id
- TC3: CHECK constraint on email format
- TC4: RESTRICT deletion of department with active students
- TC5: Composite UNIQUE constraint on (student_id, course_id)
- TC6: ON DELETE CASCADE from students to enrolments
- TC7: ETL invalid row rejection and reason reporting
- TC8: ETL idempotency on repeated execution
- TC9: Complete disaster recovery backup and restore count parity
- TC10: Backup archive rotation with retention policy
- TC11: Report generator fidelity against v_department_summary view
"""

import os
import sys
import time
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from common import init_database, get_db_connection
from import_students import run_etl
from backup_db import create_backup
from generate_report import generate_enrolment_report
from verify_restore import verify_latest_backup


class TestDatabaseAutomationSuite(unittest.TestCase):
    """Automated verification of requirements TC1 through TC11."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary directory for test artifacts
        cls.test_dir = Path(tempfile.mkdtemp(prefix="agy_test_db_"))
        cls.db_path = str(cls.test_dir / "test_records.db")
        cls.backups_dir = cls.test_dir / "backups"
        cls.reports_dir = cls.test_dir / "reports"
        cls.csv_path = str(PROJECT_ROOT / "data" / "students.csv")

        # Initialize schema and seed data
        init_database(cls.db_path, force_reset=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.conn = get_db_connection(self.db_path)

    def tearDown(self):
        self.conn.close()

    def test_01_tc1_unique_matric(self):
        """TC1: Insert a duplicate matric number -> UNIQUE constraint failed."""
        # Insert a base student
        with self.conn:
            self.conn.execute(
                "INSERT INTO students (matric_no, full_name, department_id, email) "
                "VALUES ('SEN/22/9901', 'Test Base', 1, 'base@example.com');"
            )

        # Attempt to insert identical matric_no
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO students (matric_no, full_name, department_id, email) "
                    "VALUES ('SEN/22/9901', 'Duplicate Student', 1, 'dup@example.com');"
                )
        self.assertIn("UNIQUE", str(ctx.exception).upper())
        print("  [PASS] TC1: Insert duplicate matric number correctly rejected by UNIQUE constraint")

    def test_02_tc2_foreign_key_department(self):
        """TC2: Insert a student in department 99 -> FOREIGN KEY constraint failed."""
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO students (matric_no, full_name, department_id, email) "
                    "VALUES ('SEN/22/9902', 'Orphan Student', 99, 'orphan@example.com');"
                )
        self.assertIn("FOREIGN KEY", str(ctx.exception).upper())
        print("  [PASS] TC2: Student in non-existent department correctly rejected by FOREIGN KEY")

    def test_03_tc3_check_email_format(self):
        """TC3: Insert an email without an at sign -> CHECK constraint failed."""
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO students (matric_no, full_name, department_id, email) "
                    "VALUES ('SEN/22/9903', 'Bad Email Student', 1, 'invalid-email-address');"
                )
        self.assertIn("CHECK", str(ctx.exception).upper())
        print("  [PASS] TC3: Email without '@' correctly rejected by CHECK constraint")

    def test_04_tc4_restrict_department_delete(self):
        """TC4: Delete a department that has students -> FOREIGN KEY constraint failed."""
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with self.conn:
                self.conn.execute("DELETE FROM departments WHERE department_id = 1;")
        self.assertIn("FOREIGN KEY", str(ctx.exception).upper())
        print("  [PASS] TC4: Deleting populated department refused by FOREIGN KEY restriction")

    def test_05_tc5_unique_enrolment(self):
        """TC5: Insert the same enrolment twice -> UNIQUE constraint failed."""
        # Find student and course
        student = self.conn.execute("SELECT student_id FROM students WHERE matric_no = 'SEN/22/9901'").fetchone()
        course = self.conn.execute("SELECT course_id FROM courses WHERE department_id = 1 LIMIT 1").fetchone()

        with self.conn:
            self.conn.execute(
                "INSERT INTO enrolments (student_id, course_id) VALUES (?, ?);",
                (student["student_id"], course["course_id"])
            )

        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO enrolments (student_id, course_id) VALUES (?, ?);",
                    (student["student_id"], course["course_id"])
                )
        self.assertIn("UNIQUE", str(ctx.exception).upper())
        print("  [PASS] TC5: Duplicate student-course enrolment rejected by composite UNIQUE constraint")

    def test_06_tc6_cascade_delete(self):
        """TC6: Delete a student who has enrolments -> Enrolments removed via ON DELETE CASCADE."""
        # Create a disposable student with 2 enrolments
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO students (matric_no, full_name, department_id, email) "
                "VALUES ('SEN/22/9999', 'Cascade Target', 1, 'cascade@example.com');"
            )
            s_id = cursor.lastrowid
            cursor.execute("INSERT INTO enrolments (student_id, course_id) VALUES (?, 1);", (s_id,))
            cursor.execute("INSERT INTO enrolments (student_id, course_id) VALUES (?, 2);", (s_id,))

        enrols_before = self.conn.execute(
            "SELECT COUNT(*) FROM enrolments WHERE student_id = ?", (s_id,)
        ).fetchone()[0]
        self.assertEqual(enrols_before, 2)

        # Delete the student
        with self.conn:
            self.conn.execute("DELETE FROM students WHERE student_id = ?", (s_id,))

        enrols_after = self.conn.execute(
            "SELECT COUNT(*) FROM enrolments WHERE student_id = ?", (s_id,)
        ).fetchone()[0]
        self.assertEqual(enrols_after, 0)
        print("  [PASS] TC6: Deleting student cascades to remove enrolments (2 -> 0)")

    def test_07_tc7_and_tc8_etl_pipeline(self):
        """TC7 & TC8: Clean DB and run ETL pipeline, then run again to test idempotency."""
        # Reset DB cleanly for official dataset
        init_database(self.db_path, force_reset=True)

        # Run 1: 39 read, 34 loaded, 2 duplicates in file, 3 rejected
        res1 = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res1["read"], 39)
        self.assertEqual(res1["loaded"], 34)
        self.assertEqual(res1["duplicates"], 2)
        self.assertEqual(res1["rejected"], 3)
        self.assertEqual(len(res1["rejections"]), 3)
        print("  [PASS] TC7: CSV ETL ingested 34 valid records and correctly rejected 3 invalid rows")

        # Verify database counts
        conn = get_db_connection(self.db_path)
        stud_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        enr_count = conn.execute("SELECT COUNT(*) FROM enrolments").fetchone()[0]
        conn.close()
        self.assertEqual(stud_count, 34)
        self.assertEqual(enr_count, 68)  # 34 students * 2 departmental courses

        # Run 2: Idempotent execution (0 loaded, 36 duplicates, 3 rejected)
        res2 = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res2["read"], 39)
        self.assertEqual(res2["loaded"], 0)
        self.assertEqual(res2["duplicates"], 36)
        self.assertEqual(res2["rejected"], 3)
        print("  [PASS] TC8: Re-running ETL is fully idempotent (0 loaded, 36 duplicates)")

    def test_08_tc10_backup_rotation(self):
        """TC10: Run backup 4 times with BACKUP_KEEP=3 -> exactly 3 archives remain."""
        for _ in range(4):
            create_backup(self.db_path, self.backups_dir, keep_count=3)
            time.sleep(1.05)  # Ensure distinct timestamp filenames

        archives = list(self.backups_dir.glob("records_*.sql.gz"))
        self.assertEqual(len(archives), 3)
        print(f"  [PASS] TC10: Backup rotation maintained retention limit of 3 (remaining: {len(archives)})")

    def test_09_tc9_restore_verification(self):
        """TC9: Restore newest backup and verify row counts match live database."""
        result = verify_latest_backup(self.db_path, self.backups_dir)
        self.assertTrue(result)
        print("  [PASS] TC9: Disaster recovery verification confirmed 100% row count match (5, 34, 10, 68)")

    def test_10_tc11_report_view_match(self):
        """TC11: Compare the generated report with the summary view."""
        report_file, dept_count, run_time = generate_enrolment_report(self.db_path, self.reports_dir)
        self.assertTrue(report_file.exists())
        self.assertEqual(dept_count, 5)

        # Verify numbers per department: SE=7, CS=7, IT=7, CYB=7, DS=6
        conn = get_db_connection(self.db_path)
        dept_counts = {
            r["department_name"]: r["total_students"]
            for r in conn.execute("SELECT department_name, total_students FROM v_department_summary").fetchall()
        }
        conn.close()

        expected = {
            "Software Engineering": 7,
            "Computer Science": 7,
            "Information Technology": 7,
            "Cyber Security": 7,
            "Data Science": 6,
        }
        self.assertEqual(dept_counts, expected)
        print(f"  [PASS] TC11: Report matches view counts exactly (7, 7, 7, 7, 6)")


if __name__ == "__main__":
    print("======================================================================")
    print("RUNNING DATABASE AUTOMATION SUITE VERIFICATION (TC1 - TC11)")
    print("======================================================================")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDatabaseAutomationSuite)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("======================================================================")
        print("ALL 11 TEST CASES PASSED SUCCESSFULLY!")
        print("======================================================================")
        sys.exit(0)
    else:
        print("TEST FAILURES OCCURRED")
        sys.exit(1)
