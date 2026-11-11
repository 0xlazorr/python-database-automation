#!/usr/bin/env python3
"""test_comprehensive_automation.py - Comprehensive Test Suite for Database Automation Suite.

Contains 56 granular, independent test cases covering:
- Schema DDL, constraints & data types (Tests 1-10)
- Referential integrity & cascading rules (Tests 11-16)
- CSV parsing, regex & validation edge cases (Tests 17-26)
- ETL pipeline execution, idempotency & error reporting (Tests 27-35)
- Backup engine, compression & rotation retention (Tests 36-44)
- Disaster recovery restoration & row count parity (Tests 45-50)
- Analytical reports & SQL injection defense (Tests 51-56)
"""

import os
import sys
import time
import gzip
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common import init_database, get_db_connection
from import_students import run_etl, validate_row, auto_enrol_students, MATRIC_REGEX
from backup_db import create_backup
from generate_report import generate_enrolment_report
from verify_restore import verify_latest_backup
from sqli_demo import run_sqli_demo


class ComprehensiveAutomationTests(unittest.TestCase):
    """56 automated test cases verifying database automation and reliability."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="test_auto_full_"))
        cls.db_path = str(cls.test_dir / "records.db")
        cls.backups_dir = cls.test_dir / "backups"
        cls.reports_dir = cls.test_dir / "reports"
        cls.csv_path = str(PROJECT_ROOT / "data" / "students.csv")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        init_database(self.db_path, force_reset=True)
        self.conn = get_db_connection(self.db_path)

    def tearDown(self):
        self.conn.close()

    # =========================================================================
    # 1. Schema DDL & Constraint Tests (Tests 1-10)
    # =========================================================================
    def test_01_departments_primary_key_autoincrements(self):
        """Test 1: Departments table autoincrements primary key."""
        with self.conn:
            c = self.conn.cursor()
            c.execute("INSERT INTO departments (name) VALUES ('Dept Alpha')")
            id1 = c.lastrowid
            c.execute("INSERT INTO departments (name) VALUES ('Dept Beta')")
            id2 = c.lastrowid
        self.assertGreater(id2, id1)

    def test_02_departments_name_is_unique(self):
        """Test 2: Departments table rejects duplicate names."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO departments (name) VALUES ('Software Engineering')")

    def test_03_departments_name_not_null(self):
        """Test 3: Departments table rejects NULL name."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO departments (name) VALUES (NULL)")

    def test_04_students_matric_no_is_unique(self):
        """Test 4: Students table rejects duplicate matriculation number."""
        with self.conn:
            self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0001', 'John Doe', 1, 'john@example.com')")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0001', 'Jane Doe', 1, 'jane@example.com')")

    def test_05_students_full_name_not_null(self):
        """Test 5: Students table rejects NULL full_name."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0002', NULL, 1, 'null@example.com')")

    def test_06_students_valid_foreign_key_department(self):
        """Test 6: Students table accepts valid foreign key department."""
        with self.conn:
            self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0003', 'Valid Dept Student', 2, 'valid@example.com')")
        row = self.conn.execute("SELECT * FROM students WHERE matric_no = 'SEN/22/0003'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["department_id"], 2)

    def test_07_students_invalid_foreign_key_department_rejected(self):
        """Test 7: Students table rejects non-existent department foreign key."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0004', 'Orphan Student', 99, 'orphan@example.com')")

    def test_08_students_email_check_constraint_rejects_no_at(self):
        """Test 8: Students table CHECK constraint rejects email missing '@'."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0005', 'Bad Email Student', 1, 'no-at-sign')")

    def test_09_students_email_check_constraint_accepts_valid_email(self):
        """Test 9: Students table CHECK constraint accepts valid email with '@'."""
        with self.conn:
            self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0006', 'Good Email Student', 1, 'user@example.com')")
        row = self.conn.execute("SELECT * FROM students WHERE matric_no = 'SEN/22/0006'").fetchone()
        self.assertEqual(row["email"], "user@example.com")

    def test_10_students_default_enrolled_on_is_populated(self):
        """Test 10: Students table automatically assigns current date default to enrolled_on."""
        with self.conn:
            self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0007', 'Date Student', 1, 'date@example.com')")
        row = self.conn.execute("SELECT enrolled_on FROM students WHERE matric_no = 'SEN/22/0007'").fetchone()
        self.assertTrue(len(row["enrolled_on"]) >= 10)  # YYYY-MM-DD

    # =========================================================================
    # 2. Referential Integrity & Cascading Actions (Tests 11-16)
    # =========================================================================
    def test_11_courses_foreign_key_department_enforced(self):
        """Test 11: Courses table requires valid department foreign key."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO courses (course_code, title, department_id) VALUES ('BAD999', 'Fake Course', 88)")

    def test_12_courses_course_code_is_unique(self):
        """Test 12: Courses table rejects duplicate course_code."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO courses (course_code, title, department_id) VALUES ('SEN301', 'Duplicate Code', 1)")

    def test_13_enrolments_composite_unique_constraint(self):
        """Test 13: Enrolments table rejects duplicate (student_id, course_id)."""
        with self.conn:
            self.conn.execute("INSERT INTO students (student_id, matric_no, full_name, department_id, email) VALUES (100, 'SEN/22/0100', 'Enrol Student', 1, 'enrol@example.com')")
            self.conn.execute("INSERT INTO enrolments (student_id, course_id) VALUES (100, 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO enrolments (student_id, course_id) VALUES (100, 1)")

    def test_14_enrolments_foreign_key_invalid_student_rejected(self):
        """Test 14: Enrolments table rejects non-existent student_id."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("INSERT INTO enrolments (student_id, course_id) VALUES (9999, 1)")

    def test_15_enrolments_cascade_delete_on_student_removal(self):
        """Test 15: Deleting a student cascades to remove all their enrolments."""
        with self.conn:
            self.conn.execute("INSERT INTO students (student_id, matric_no, full_name, department_id, email) VALUES (200, 'SEN/22/0200', 'Cascade Student', 1, 'casc@example.com')")
            self.conn.execute("INSERT INTO enrolments (student_id, course_id) VALUES (200, 1)")
            self.conn.execute("INSERT INTO enrolments (student_id, course_id) VALUES (200, 2)")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM enrolments WHERE student_id = 200").fetchone()[0], 2)
        with self.conn:
            self.conn.execute("DELETE FROM students WHERE student_id = 200")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM enrolments WHERE student_id = 200").fetchone()[0], 0)

    def test_16_departments_deletion_restricted_when_students_exist(self):
        """Test 16: Deleting a department with active students is strictly restricted."""
        with self.conn:
            self.conn.execute("INSERT INTO students (matric_no, full_name, department_id, email) VALUES ('SEN/22/0300', 'Dept Student', 1, 'dept@example.com')")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("DELETE FROM departments WHERE department_id = 1")

    # =========================================================================
    # 3. CSV Parsing & Validation Edge Cases (Tests 17-26)
    # =========================================================================
    def test_17_matric_regex_matches_standard_format(self):
        """Test 17: MATRIC_REGEX matches standard Nigerian institutional matric formats."""
        self.assertTrue(bool(MATRIC_REGEX.match("SEN/22/1001")))
        self.assertTrue(bool(MATRIC_REGEX.match("CSC/23/9999")))
        self.assertTrue(bool(MATRIC_REGEX.match("IFT/24/0005")))

    def test_18_matric_regex_rejects_hyphens(self):
        """Test 18: MATRIC_REGEX rejects hyphens instead of slashes."""
        self.assertFalse(bool(MATRIC_REGEX.match("SEN-22-1001")))

    def test_19_matric_regex_rejects_lowercase(self):
        """Test 19: MATRIC_REGEX rejects lowercase department prefix."""
        self.assertFalse(bool(MATRIC_REGEX.match("sen/22/1001")))

    def test_20_matric_regex_rejects_four_digit_year(self):
        """Test 20: MATRIC_REGEX rejects 4-digit admission year."""
        self.assertFalse(bool(MATRIC_REGEX.match("SEN/2022/1001")))

    def test_21_matric_regex_rejects_short_sequence(self):
        """Test 21: MATRIC_REGEX rejects sequential IDs shorter than 4 digits."""
        self.assertFalse(bool(MATRIC_REGEX.match("SEN/22/100")))

    def test_22_validate_row_valid_input(self):
        """Test 22: validate_row accepts well-formed student row."""
        row = {"matric_no": "SEN/22/1001", "full_name": "Test User", "department_id": "1", "email": "test@example.com"}
        valid, reason = validate_row(row, {1, 2, 3})
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_23_validate_row_unknown_department(self):
        """Test 23: validate_row rejects non-existent department."""
        row = {"matric_no": "SEN/22/1001", "full_name": "Test User", "department_id": "99", "email": "test@example.com"}
        valid, reason = validate_row(row, {1, 2, 3})
        self.assertFalse(valid)
        self.assertEqual(reason, "unknown department")

    def test_24_validate_row_invalid_email(self):
        """Test 24: validate_row rejects email without '@'."""
        row = {"matric_no": "SEN/22/1001", "full_name": "Test User", "department_id": "1", "email": "test-no-at"}
        valid, reason = validate_row(row, {1, 2, 3})
        self.assertFalse(valid)
        self.assertEqual(reason, "invalid email")

    def test_25_validate_row_missing_name(self):
        """Test 25: validate_row rejects blank full name."""
        row = {"matric_no": "SEN/22/1001", "full_name": "   ", "department_id": "1", "email": "test@example.com"}
        valid, reason = validate_row(row, {1, 2, 3})
        self.assertFalse(valid)
        self.assertEqual(reason, "missing full name")

    def test_26_validate_row_non_numeric_department(self):
        """Test 26: validate_row rejects alphabetic department ID string."""
        row = {"matric_no": "SEN/22/1001", "full_name": "Test User", "department_id": "software", "email": "test@example.com"}
        valid, reason = validate_row(row, {1, 2, 3})
        self.assertFalse(valid)
        self.assertEqual(reason, "unknown department")

    # =========================================================================
    # 4. ETL Pipeline Execution & Idempotency (Tests 27-35)
    # =========================================================================
    def test_27_run_etl_reads_39_rows(self):
        """Test 27: run_etl reads exactly 39 rows from students.csv."""
        res = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res["read"], 39)

    def test_28_run_etl_loads_34_valid_students(self):
        """Test 28: run_etl loads exactly 34 valid student rows."""
        res = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res["loaded"], 34)

    def test_29_run_etl_detects_2_duplicates_in_file(self):
        """Test 29: run_etl flags the 2 duplicate entries in students.csv."""
        res = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res["duplicates"], 2)

    def test_30_run_etl_rejects_3_faulty_records(self):
        """Test 30: run_etl rejects the 3 intentionally faulty records."""
        res = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res["rejected"], 3)
        reasons = {r[0]: r[1] for r in res["rejections"]}
        self.assertIn("invalid matric number", reasons.get("SEN-22-1502", ""))
        self.assertIn("unknown department", reasons.get("CSC/22/1501", ""))
        self.assertIn("invalid email", reasons.get("SEN/22/1500", ""))

    def test_31_run_etl_is_fully_idempotent_on_rerun(self):
        """Test 31: Re-running run_etl loads 0 rows and reports 36 duplicates."""
        run_etl(self.csv_path, self.db_path)
        res2 = run_etl(self.csv_path, self.db_path)
        self.assertEqual(res2["loaded"], 0)
        self.assertEqual(res2["duplicates"], 36)
        self.assertEqual(res2["rejected"], 3)

    def test_32_auto_enrol_creates_68_total_enrolments(self):
        """Test 32: Auto enrol generates 68 enrolments (34 students * 2 courses)."""
        run_etl(self.csv_path, self.db_path)
        count = self.conn.execute("SELECT COUNT(*) FROM enrolments").fetchone()[0]
        self.assertEqual(count, 68)

    def test_33_auto_enrol_is_idempotent(self):
        """Test 33: Calling auto_enrol_students repeatedly does not duplicate enrolments."""
        run_etl(self.csv_path, self.db_path)
        auto_enrol_students(self.conn)
        auto_enrol_students(self.conn)
        count = self.conn.execute("SELECT COUNT(*) FROM enrolments").fetchone()[0]
        self.assertEqual(count, 68)

    def test_34_run_etl_missing_file_raises_error(self):
        """Test 34: run_etl raises FileNotFoundError when target CSV does not exist."""
        with self.assertRaises(FileNotFoundError):
            run_etl("non_existent_file.csv", self.db_path)

    def test_35_run_etl_empty_csv_file(self):
        """Test 35: run_etl safely handles empty CSV file."""
        empty_csv = self.test_dir / "empty.csv"
        empty_csv.write_text("matric_no,full_name,department_id,email\n")
        res = run_etl(str(empty_csv), self.db_path)
        self.assertEqual(res["read"], 0)
        self.assertEqual(res["loaded"], 0)

    # =========================================================================
    # 5. Backup Engine & Rotation Policy (Tests 36-44)
    # =========================================================================
    def test_36_create_backup_creates_sql_gz_file(self):
        """Test 36: create_backup creates a gzipped .sql.gz archive."""
        run_etl(self.csv_path, self.db_path)
        fpath, size, kept = create_backup(self.db_path, self.backups_dir, keep_count=3)
        self.assertTrue(fpath.exists())
        self.assertTrue(fpath.name.endswith(".sql.gz"))
        self.assertGreater(size, 0)

    def test_37_backup_contains_valid_sql_dump(self):
        """Test 37: Uncompressed backup contains valid human-readable SQL dump."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            content = gz.read()
        self.assertIn("CREATE TABLE", content)
        self.assertIn("INSERT INTO", content)

    def test_38_backup_includes_foreign_keys_pragmas(self):
        """Test 38: Backup dump wraps content in PRAGMA foreign_keys = OFF / ON."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            content = gz.read()
        self.assertTrue(content.startswith("PRAGMA foreign_keys = OFF;"))
        self.assertTrue(content.strip().endswith("PRAGMA foreign_keys = ON;"))

    def test_39_backup_rotation_prunes_older_archives_keep_3(self):
        """Test 39: Backup rotation preserves exactly 3 newest archives when keep=3."""
        run_etl(self.csv_path, self.db_path)
        for _ in range(5):
            create_backup(self.db_path, self.backups_dir, keep_count=3)
            time.sleep(1.02)
        archives = list(self.backups_dir.glob("records_*.sql.gz"))
        self.assertEqual(len(archives), 3)

    def test_40_backup_rotation_keep_1(self):
        """Test 40: Backup rotation with keep=1 preserves exactly 1 archive."""
        run_etl(self.csv_path, self.db_path)
        for _ in range(3):
            create_backup(self.db_path, self.backups_dir, keep_count=1)
            time.sleep(1.02)
        archives = list(self.backups_dir.glob("records_*.sql.gz"))
        self.assertEqual(len(archives), 1)

    def test_41_backup_rotation_clamps_negative_keep_to_1(self):
        """Test 41: Backup rotation clamps negative or zero keep count to at least 1."""
        run_etl(self.csv_path, self.db_path)
        create_backup(self.db_path, self.backups_dir, keep_count=-5)
        archives = list(self.backups_dir.glob("records_*.sql.gz"))
        self.assertGreaterEqual(len(archives), 1)

    def test_42_create_backup_non_existent_db_raises_error(self):
        """Test 42: create_backup raises FileNotFoundError if database does not exist."""
        with self.assertRaises(FileNotFoundError):
            create_backup("missing_db.db", self.backups_dir, keep_count=3)

    def test_43_backup_created_on_empty_database(self):
        """Test 43: create_backup operates safely on a newly initialized empty database."""
        fpath, size, kept = create_backup(self.db_path, self.backups_dir, keep_count=3)
        self.assertTrue(fpath.exists())
        self.assertGreater(size, 0)

    def test_44_backup_compression_ratio(self):
        """Test 44: Verifies gzip compression reduces storage size."""
        run_etl(self.csv_path, self.db_path)
        fpath, gz_size, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            raw_sql = gz.read()
        raw_size = len(raw_sql.encode("utf-8"))
        self.assertLess(gz_size, raw_size)

    # =========================================================================
    # 6. Disaster Recovery & Restoration (Tests 45-50)
    # =========================================================================
    def test_45_verify_restore_returns_true_on_clean_backup(self):
        """Test 45: verify_latest_backup returns True when restored counts match live DB."""
        run_etl(self.csv_path, self.db_path)
        create_backup(self.db_path, self.backups_dir, keep_count=3)
        result = verify_latest_backup(self.db_path, self.backups_dir)
        self.assertTrue(result)

    def test_46_verify_restore_departments_count_matches(self):
        """Test 46: Restored database contains exactly 5 departments."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        mconn = sqlite3.connect(":memory:")
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            mconn.executescript(gz.read())
        self.assertEqual(mconn.execute("SELECT COUNT(*) FROM departments").fetchone()[0], 5)
        mconn.close()

    def test_47_verify_restore_students_count_matches(self):
        """Test 47: Restored database contains exactly 34 students."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        mconn = sqlite3.connect(":memory:")
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            mconn.executescript(gz.read())
        self.assertEqual(mconn.execute("SELECT COUNT(*) FROM students").fetchone()[0], 34)
        mconn.close()

    def test_48_verify_restore_courses_count_matches(self):
        """Test 48: Restored database contains exactly 10 courses."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        mconn = sqlite3.connect(":memory:")
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            mconn.executescript(gz.read())
        self.assertEqual(mconn.execute("SELECT COUNT(*) FROM courses").fetchone()[0], 10)
        mconn.close()

    def test_49_verify_restore_enrolments_count_matches(self):
        """Test 49: Restored database contains exactly 68 enrolments."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = create_backup(self.db_path, self.backups_dir, keep_count=3)
        mconn = sqlite3.connect(":memory:")
        with gzip.open(fpath, "rt", encoding="utf-8") as gz:
            mconn.executescript(gz.read())
        self.assertEqual(mconn.execute("SELECT COUNT(*) FROM enrolments").fetchone()[0], 68)
        mconn.close()

    def test_50_verify_restore_fails_gracefully_when_no_archives(self):
        """Test 50: verify_latest_backup returns False when backup directory is empty."""
        empty_dir = self.test_dir / "empty_backups"
        empty_dir.mkdir(exist_ok=True)
        result = verify_latest_backup(self.db_path, empty_dir)
        self.assertFalse(result)

    # =========================================================================
    # 7. Reporting & Security Defense (Tests 51-56)
    # =========================================================================
    def test_51_generate_report_creates_csv_file(self):
        """Test 51: generate_enrolment_report creates dated CSV output file."""
        run_etl(self.csv_path, self.db_path)
        fpath, dept_count, runtime = generate_enrolment_report(self.db_path, self.reports_dir)
        self.assertTrue(fpath.exists())
        self.assertEqual(dept_count, 5)
        self.assertGreater(runtime, 0.0)

    def test_52_generate_report_csv_header(self):
        """Test 52: Generated report CSV starts with correct column headers."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = generate_enrolment_report(self.db_path, self.reports_dir)
        lines = fpath.read_text().strip().split("\n")
        self.assertEqual(lines[0], "department_id,department_name,total_students")

    def test_53_generate_report_fidelity_against_summary_view(self):
        """Test 53: Report student counts per department match expected counts (7,7,7,7,6)."""
        run_etl(self.csv_path, self.db_path)
        fpath, _, _ = generate_enrolment_report(self.db_path, self.reports_dir)
        lines = fpath.read_text().strip().split("\n")[1:]
        counts = [int(line.split(",")[-1]) for line in lines]
        self.assertEqual(sorted(counts), [6, 7, 7, 7, 7])

    def test_54_generate_report_on_empty_students_table(self):
        """Test 54: Report includes departments with 0 students using LEFT JOIN."""
        fpath, dept_count, _ = generate_enrolment_report(self.db_path, self.reports_dir)
        self.assertEqual(dept_count, 5)
        lines = fpath.read_text().strip().split("\n")[1:]
        for line in lines:
            self.assertTrue(line.endswith(",0"))

    def test_55_sqli_demo_runs_without_errors(self):
        """Test 55: run_sqli_demo executes safely and demonstrates parameterization."""
        # Run demo and ensure no uncaught exceptions
        run_sqli_demo()

    def test_56_sqli_parameterized_query_defense(self):
        """Test 56: Parameterized SQL query blocks authentication bypass payload."""
        conn = sqlite3.connect(":memory:")
        with conn:
            conn.execute("CREATE TABLE users (username TEXT, password TEXT, role TEXT);")
            conn.execute("INSERT INTO users VALUES ('admin', 'pass123', 'administrator');")
        payload = "' OR 1=1 --"
        res = conn.execute("SELECT role FROM users WHERE username = ? AND password = ?", (payload, "x")).fetchone()
        self.assertIsNone(res)
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
