-- seed.sql
-- Initial seed data for departments and departmental courses

PRAGMA foreign_keys = ON;

-- Departments (5 academic departments)
INSERT OR IGNORE INTO departments (department_id, name) VALUES
    (1, 'Software Engineering'),
    (2, 'Computer Science'),
    (3, 'Information Technology'),
    (4, 'Cyber Security'),
    (5, 'Data Science');

-- Courses (2 required core courses per department, 10 total)
INSERT OR IGNORE INTO courses (course_id, course_code, title, department_id) VALUES
    (1, 'SEN301', 'Software Design', 1),
    (2, 'SEN302', 'Software Architecture', 1),
    (3, 'CSC301', 'Operating Systems', 2),
    (4, 'CSC307', 'Algorithms', 2),
    (5, 'IFT301', 'Network Administration', 3),
    (6, 'IFT303', 'Database Administration', 3),
    (7, 'CYB301', 'Network Security', 4),
    (8, 'CYB303', 'Digital Forensics', 4),
    (9, 'DSC301', 'Data Mining', 5),
    (10, 'DSC303', 'Machine Learning', 5);
