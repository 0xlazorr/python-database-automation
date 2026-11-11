# Data Dictionary: Institutional Records Database

This document details the schema, column definitions, constraints, data types, and referential rules of the Institutional Records Database, implementing the normalised 3NF architecture from Chapter 3.2.5 of the SIWES Industrial Training report.

---

## 1. Table: `departments`
Stores academic departments within the institution.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `department_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Surrogate primary key uniquely identifying the department |
| `name` | `TEXT` | `NOT NULL UNIQUE` | Official name of the department (e.g., Software Engineering) |

### Referential Actions:
- Referenced by `students.department_id` (RESTRICT deletion).
- Referenced by `courses.department_id` (RESTRICT deletion).

---

## 2. Table: `students`
Stores individual registered students.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `student_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Surrogate primary key uniquely identifying the student record |
| `matric_no` | `TEXT` | `NOT NULL UNIQUE` | Institutional matriculation number (format: `[A-Z]{3}/\d{2}/\d{4}`) |
| `full_name` | `TEXT` | `NOT NULL` | Student full legal name |
| `department_id` | `INTEGER` | `NOT NULL REFERENCES departments(department_id)` | Foreign key linking student to their parent academic department |
| `email` | `TEXT` | `UNIQUE CHECK (email LIKE '%@%')` | Verified email address ensuring presence of at sign |
| `enrolled_on` | `TEXT` | `NOT NULL DEFAULT (date('now'))` | ISO-8601 registration date |

### Referential Actions:
- Cascades on delete: Deleting a student automatically removes all associated rows in `enrolments`.
- Foreign key restricts: Deleting a referenced department is refused while students are assigned to it.

---

## 3. Table: `courses`
Stores academic courses offered across departments.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `course_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Surrogate primary key uniquely identifying the course |
| `course_code` | `TEXT` | `NOT NULL UNIQUE` | Natural course identifier (e.g., `SEN301`, `CSC301`) |
| `title` | `TEXT` | `NOT NULL` | Descriptive title of the course curriculum |
| `department_id` | `INTEGER` | `NOT NULL REFERENCES departments(department_id)` | Foreign key identifying the administering department |

### Referential Actions:
- Referenced by `enrolments.course_id` (RESTRICT deletion).

---

## 4. Table: `enrolments`
Resolves the many-to-many relationship between `students` and `courses`.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `enrolment_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Surrogate primary key for the enrolment event |
| `student_id` | `INTEGER` | `NOT NULL REFERENCES students(student_id) ON DELETE CASCADE` | Foreign key referencing the enrolled student |
| `course_id` | `INTEGER` | `NOT NULL REFERENCES courses(course_id)` | Foreign key referencing the course |
| `enrolled_on` | `TEXT` | `NOT NULL DEFAULT (date('now'))` | Timestamp/date of course enrolment |

### Integrity Constraints:
- `UNIQUE (student_id, course_id)`: Prevents duplicate enrolments of the same student in the same course.
- `ON DELETE CASCADE`: Removing a student cleanly removes all of their course enrolments without orphan rows.

---

## 5. Indexes
Optimizes common join and filtering operations.

| Index Name | Target Table | Target Column(s) | Type | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `idx_students_department` | `students` | `department_id` | B-tree | Accelerates department joins and summary aggregations |
| `idx_enrolments_course` | `enrolments` | `course_id` | B-tree | Accelerates course ranking and headcount aggregation |

---

## 6. View: `v_department_summary`
Encapsulates join and aggregation logic for management reports.

```sql
CREATE VIEW v_department_summary AS
SELECT d.department_id,
       d.name AS department_name,
       COUNT(s.student_id) AS total_students
FROM departments d
LEFT JOIN students s ON s.department_id = d.department_id
GROUP BY d.department_id, d.name;
```
