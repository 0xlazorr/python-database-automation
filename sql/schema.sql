-- schema.sql
-- Relational database schema for Institutional Records
-- Enforces referential integrity, constraints, indexes, and summary views

PRAGMA foreign_keys = ON;

-- 1. Departments Table
CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- 2. Students Table
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    matric_no TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(department_id),
    email TEXT UNIQUE CHECK (email LIKE '%@%'),
    enrolled_on TEXT NOT NULL DEFAULT (date('now'))
);

-- 3. Courses Table
CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(department_id)
);

-- 4. Enrolments Table (Resolves Many-to-Many between Students and Courses)
CREATE TABLE IF NOT EXISTS enrolments (
    enrolment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(course_id),
    enrolled_on TEXT NOT NULL DEFAULT (date('now')),
    UNIQUE (student_id, course_id)
);

-- Performance Indexes on foreign key join columns
CREATE INDEX IF NOT EXISTS idx_students_department ON students(department_id);
CREATE INDEX IF NOT EXISTS idx_enrolments_course ON enrolments(course_id);

-- Analytical View for Department Enrolment Summaries
DROP VIEW IF EXISTS v_department_summary;
CREATE VIEW v_department_summary AS
SELECT d.department_id,
       d.name AS department_name,
       COUNT(s.student_id) AS total_students
FROM departments d
LEFT JOIN students s ON s.department_id = d.department_id
GROUP BY d.department_id, d.name;
