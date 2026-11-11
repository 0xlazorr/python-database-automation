#!/usr/bin/env bash
# run_pipeline.sh - Automation Pipeline Runner
# Sequentially executes:
#   1. Student CSV ingestion (ETL)
#   2. Compressed database backup & archive rotation
#   3. Analytical enrolment report generation
#
# Follows fail-fast design (set -e): halts immediately on any stage error.

set -e

# Resolve directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present, else fallback to python3
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    PYTHON_CMD="python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

echo "[1/3] Importing student records"
$PYTHON_CMD import_students.py data/students.csv

echo "[2/3] Backing up the database"
$PYTHON_CMD backup_db.py

echo "[3/3] Generating the enrolment report"
$PYTHON_CMD generate_report.py

echo "Pipeline finished successfully"
