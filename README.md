# Institutional Database Automation Suite

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/database-SQLite3%20%7C%20PostgreSQL-green.svg)](https://www.sqlite.org/)
[![Test Suite](https://img.shields.io/badge/tests-56%20passed%20%7C%20100%25-brightgreen.svg)](tests/)
[![Security](https://img.shields.io/badge/security-parameterized%20%7C%20RBAC-success.svg)](sqli_demo.py)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

An automated database management, ETL ingestion, scheduled backup, and analytical reporting suite implemented in Python and SQL. Designed to enforce declarative data integrity, reliable batch data loading, automated disaster recovery verification, and unattended scheduled reporting.

---

## Table of Contents
1. [System Architecture](#1-system-architecture)
2. [Core Modules & Capabilities](#2-core-modules--capabilities)
3. [Repository Structure](#3-repository-structure)
4. [Installation & Setup](#4-installation--setup)
5. [Usage & Execution Guide](#5-usage--execution-guide)
6. [Engineering Standards: Test Execution Rules](#6-engineering-standards-test-execution-rules)
7. [Automated Test Suite (56 Test Cases)](#7-automated-test-suite-56-test-cases)
8. [Production Scheduling (Crontab)](#8-production-scheduling-crontab)
9. [Adapting for Other Database Workloads](#9-adapting-for-other-database-workloads)

---

## 1. System Architecture

```
                                  +-----------------------+
                                  |   data/students.csv   |
                                  |  (Raw Ingestion File) |
                                  +-----------+-----------+
                                              |
                                              v
+------------------+              +-----------+-----------+
|   crontab.txt    | -----------> |   import_students.py  |  Pre-ingestion Regex & FK Validation
|  (Linux Cron)    |              +-----------+-----------+  Idempotent Batch Loading
+--------+---------+                          |
         |                                    v
         |                        +-----------+-----------+
         +----------------------> |       records.db      |  SQLite (PRAGMA foreign_keys = ON)
         |                        | (Relational 3NF Core) |  schema.sql & seed.sql
         |                        +-----+-----------+-----+
         |                              |           |
         |         +--------------------+           +--------------------+
         |         v                                                     v
         |   +-----+--------------+                                +-----+--------------+
         +-> |   backup_db.py     |                                | generate_report.py |
             +-----+--------------+                                +-----+--------------+
                   | (iterdump + gzip)                                   | (v_department_summary)
                   v                                                     v
             +-----+--------------------------+                    +-----+--------------------------+
             | backups/records_*.sql.gz       |                    | reports/enrolment_summary_*.csv|
             | (Rotation: BACKUP_KEEP=3)      |                    +--------------------------------+
             +-----+--------------------------+
                   |
                   v
             +-----+--------------+
             | verify_restore.py  | In-Memory DB Restore & Parity Check (5, 34, 10, 68)
             +--------------------+
```

---

## 2. Core Modules & Capabilities

### 2.1 Automated CSV ETL Pipeline (`import_students.py`)
* **Pre-Ingestion Validation**:
  * **Matriculation Pattern**: Rejects entries not conforming to `^[A-Z]{3}/\d{2}/\d{4}$` (e.g., `SEN-22-1502`).
  * **Referential Foreign Keys**: Rejects records referencing non-existent departments (e.g., `CSC/22/1501` referencing dept 99).
  * **Email RFC Validation**: Enforces presence of `@` and valid domain formatting.
  * **Header/Field Normalization**: Automatically strips whitespace from CSV keys and values.
* **Transactional Idempotency**:
  * Uses `executemany` inside an atomic transaction block with `INSERT OR IGNORE`.
  * Repeated execution produces `0 loaded, 36 duplicates`, preventing duplicate records or transaction failure.
* **Course Enrolment Synchronization**:
  * Automatically enrols newly inserted students into required departmental courses via relational `INSERT ... SELECT`.

### 2.2 Compressed Backup & Archive Rotation (`backup_db.py`)
* Generates consistent logical SQL dumps using SQLite `iterdump()`.
* Compresses output into timestamped gzip archives (`backups/records_YYYYMMDD_HHMMSS.sql.gz`).
* Injects `PRAGMA foreign_keys = OFF;` at the archive header to guarantee cross-platform restore portability.
* Enforces retention policy (`BACKUP_KEEP=3`), automatically pruning older archives to conserve disk space.

### 2.3 Analytical Report Generator (`generate_report.py`)
* Executes aggregated SQL queries against the `v_department_summary` view.
* Uses `LEFT JOIN` syntax to guarantee departments with zero students appear in management summaries.
* Exports dated spreadsheets (`reports/enrolment_summary_YYYYMMDD.csv`).
* Measures and logs execution duration with microsecond precision.

### 2.4 Disaster Recovery Verifier (`verify_restore.py`)
* Resolves the latest `.sql.gz` archive in `backups/`.
* Replays the dump into an isolated in-memory database instance.
* Audits and cross-checks row counts across `departments` (5), `students` (34), `courses` (10), and `enrolments` (68), asserting `Restore verification: PASS`.

### 2.5 Security & Parameterization Defense (`sqli_demo.py`)
* Demonstrates authentication bypass vulnerabilities in string-concatenated SQL queries versus defense using parameterized queries (`?` placeholders).

---

## 3. Repository Structure

```
python_database_automation/
├── backups/                     # Compressed logical database dumps (*.sql.gz)
├── data/
│   └── students.csv             # 39-row raw ingestion file (34 valid, 2 dupes, 3 faulty)
├── docs/
│   └── data_dictionary.md       # Comprehensive entity-relationship data dictionary
├── logs/
│   └── automation.log           # Millisecond-precision structured event logs
├── reports/
│   └── enrolment_summary_*.csv  # Exported management spreadsheet reports
├── sql/
│   ├── schema.sql               # Normalized DDL, constraints, indexes & summary view
│   └── seed.sql                 # Academic departments & core course catalog
├── tests/
│   └── test_comprehensive_automation.py # 56 automated test cases
├── .env.example                 # Zero-credential environment configuration template
├── .gitignore                   # Excludes databases, dumps, logs, and virtual environments
├── backup_db.py                 # Automated backup engine with gzip compression and rotation
├── common.py                    # Connection factory (PRAGMA foreign_keys = ON) & logger
├── crontab.txt                  # Production crontab scheduling configuration
├── generate_report.py           # Scheduled enrolment analytics exporter
├── import_students.py           # Production CSV-to-DB ETL pipeline with error reporting
├── run_pipeline.sh              # Master pipeline runner (import -> backup -> report)
├── sqli_demo.py                 # Security demonstration: SQL injection vs parameterized queries
├── test_automation_suite.py     # 11 Table 3.2 SIWES requirement test cases
└── verify_restore.py            # Disaster recovery restoration validator
```

---

## 4. Installation & Setup

```bash
# 1. Clone repository
git clone https://github.com/0xlazorr/python-database-automation.git
cd python-database-automation

# 2. Configure environment (optional overrides)
cp .env.example .env

# 3. Ensure scripts have execution permissions
chmod +x *.py *.sh
```

---

## 5. Usage & Execution Guide

```bash
# Execute master automation pipeline (ETL -> Backup -> Report)
./run_pipeline.sh

# Verify disaster recovery restore from newest backup
python3 verify_restore.py

# Run SQL injection demonstration
python3 sqli_demo.py

# Inspect structured millisecond execution logs
tail -n 15 logs/automation.log
```

---

## 6. Engineering Standards: Test Execution Rules

All database components and automated pipelines must adhere to the following test execution rules before deployment:

1. **Declarative Constraint Verification**: Every constraint (`UNIQUE`, `CHECK`, `NOT NULL`, `FOREIGN KEY`) must have corresponding test cases verifying that invalid data is rejected at the storage layer.
2. **Negative Testing & Failure Paths**: Ingestion pipelines must be tested against malformed data, invalid email syntax, invalid foreign keys, and empty files to assert graceful failure without data corruption.
3. **Idempotency Invariance**: Automated ETL jobs must be executed repeatedly within test runs to confirm that repeated ingestion does not create duplicate rows or foreign key collisions.
4. **Disaster Recovery Parity**: Backups must be restored and verified against live table counts to guarantee archive validity.
5. **Pre-Merge Rule**: 100% of automated tests must pass before code is merged into the `main` branch.

---

## 7. Automated Test Suite (56 Test Cases)

The repository includes 56 automated test cases validating all functional requirements, integrity constraints, and error-handling routines:

```bash
# Run comprehensive 56-test suite
python3 tests/test_comprehensive_automation.py

# Run SIWES requirements test suite (TC1 - TC11)
python3 test_automation_suite.py
```

### Test Suite Summary:
| Test Category | Test Count | Scope |
| :--- | :---: | :--- |
| **Schema DDL & Constraints** | 10 Tests | Autoincrement PKs, UNIQUE, NOT NULL, CHECK, default date generation |
| **Referential Integrity** | 6 Tests | Foreign keys, CASCADE deletes (enrolments), RESTRICT deletes (departments) |
| **CSV Parsing & Regex** | 10 Tests | Pattern matching, hyphens, case sensitivity, whitespace stripping |
| **ETL Ingestion & Idempotency** | 9 Tests | 39 read, 34 loaded, 2 duplicates, 3 rejected, idempotency on re-run |
| **Backup Engine & Rotation** | 9 Tests | Gzip creation, dump validity, archive pruning (keep=1, 3, 5), error handling |
| **Disaster Recovery** | 6 Tests | In-memory restoration, table row parity checks (5, 34, 10, 68) |
| **Reporting & Security** | 6 Tests | CSV export, summary view match, runtime metrics, SQLi defense |
| **Total Test Cases** | **56 Tests** | **100% Passing** |

---

## 8. Production Scheduling (Crontab)

To execute the automation suite unattended on a production Linux server:

```bash
# Open crontab editor
crontab -e

# Add scheduled entries (replace /path/to with absolute path to project):
0 1 * * * cd /path/to/python_database_automation && python3 import_students.py data/students.csv >> logs/cron.log 2>&1
0 2 * * * cd /path/to/python_database_automation && python3 backup_db.py >> logs/cron.log 2>&1
0 6 * * 1 cd /path/to/python_database_automation && python3 generate_report.py >> logs/cron.log 2>&1
```

---

## 9. Adapting for Other Database Workloads

The automation framework is domain-agnostic and can be repurposed for other relational database environments:

* **Backing Up Other SQLite Databases**:
  ```bash
  DB_PATH="/path/to/app.db" BACKUP_KEEP=7 python3 backup_db.py
  ```
* **Adapting the ETL Pipeline**:
  Update `validate_row()` in `import_students.py` to match the target schema (e.g., customers, orders, inventory). The transactional batch insertion and duplicate-handling logic remain identical.
* **Custom Reporting**:
  Modify the SQL query in `generate_report.py` to point to any application view or aggregate calculation.
* **Enterprise RDBMS Backups**:
  Wrap `pg_dump` or `mysqldump` within `backup_db.py` to apply the same timestamping, compression, and rotation logic to PostgreSQL or MySQL instances.
