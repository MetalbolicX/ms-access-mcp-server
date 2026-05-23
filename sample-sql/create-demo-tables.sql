-- ============================================================
-- Access ANSI-92 SQL Demo Script
-- Tests: CREATE TABLE with CHECK constraints, subqueries,
--        FOREIGN KEY, AUTOINCREMENT, VARCHAR, DATETIME, etc.
--
-- Run against: D:\JMS\Limbo\excel-and-sql-book\data\db\helper.accdb
-- Engine: ADO (CurrentProject.Connection) — ANSI-92 SQL mode
--
-- IMPORTANT: Requires Access ANSI-92 Query Mode enabled:
--   Options > Object Designers > SQL Server Compatible Syntax (ANSI-92)
--
-- To execute via MCP server:
--   Set ACCESS_MCP_API_KEY and ACCESS_MCP_ALLOWED_DIRS
--   then call execute_sql_script with path to this file
-- ============================================================

-- -------------------------------------------------------
-- Step 1: Create parent table (no dependencies)
-- -------------------------------------------------------
CREATE TABLE departments (
    department_id AUTOINCREMENT PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL,
    department_created_at DATETIME NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------
-- Step 2: Create child table with constraints
-- -------------------------------------------------------
CREATE TABLE employees (
    employee_id AUTOINCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    department_id INTEGER NOT NULL,
    birthday DATETIME NOT NULL,
    email VARCHAR(100) NOT NULL,
    employee_created_at DATETIME NOT NULL DEFAULT NOW(),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON UPDATE CASCADE,
    CONSTRAINT employee_per_department CHECK((
        SELECT COUNT(*)
        FROM employees AS e
        WHERE e.department_id = employees.department_id
    ) <= 2),
    CONSTRAINT valid_adult_age CHECK(
        Int(DateDiff("d", birthday, Date()) / 365.2425) >= 18
    ),
    CONSTRAINT verify_email CHECK(
        Len(email) >= 3
        AND email LIKE "?*@?*.?*"
        AND email NOT LIKE "*[ ,;]*"
    )
);

-- -------------------------------------------------------
-- Step 3: Insert sample data into departments
-- -------------------------------------------------------
INSERT INTO departments (department_name) VALUES ('Engineering');
INSERT INTO departments (department_name) VALUES ('Marketing');
INSERT INTO departments (department_name) VALUES ('Sales');

-- -------------------------------------------------------
-- Step 4: Insert sample data into employees
-- Note: Each department max 2 employees enforced by CHECK
-- -------------------------------------------------------
INSERT INTO employees (employee_name, department_id, birthday, email)
VALUES ('Alice Smith', 1, #1990-05-15#, 'alice@example.com');

INSERT INTO employees (employee_name, department_id, birthday, email)
VALUES ('Bob Jones', 1, #1988-08-20#, 'bob@example.com');

INSERT INTO employees (employee_name, department_id, birthday, email)
VALUES ('Carol White', 2, #1992-03-10#, 'carol@example.com');

-- -------------------------------------------------------
-- Step 5: Verify data
-- -------------------------------------------------------
SELECT 'Departments created:' AS msg, COUNT(*) AS cnt FROM departments;
SELECT 'Employees created:' AS msg, COUNT(*) AS cnt FROM employees;
SELECT 'Departments with employees:' AS msg, department_id, COUNT(*) AS emp_count FROM employees GROUP BY department_id;