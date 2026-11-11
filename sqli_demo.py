#!/usr/bin/env python3
"""sqli_demo.py - Database Security & SQL Injection Defense Demonstration.

Directly demonstrates the vulnerability of string concatenation (f-strings)
versus the robust defense of parameterized queries as documented in Chapter 2.6
and Figure 2.15 of the IT report.
"""

import sqlite3

def run_sqli_demo():
    # In-memory test database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create users authentication table
    cursor.execute("""
    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    );
    """)

    # Populate accounts
    cursor.execute("INSERT INTO users (username, password, role) VALUES ('administrator', 'adminPass99!', 'administrator');")
    cursor.execute("INSERT INTO users (username, password, role) VALUES ('student', 'learn123', 'trainee');")
    conn.commit()

    # 1. Vulnerable login with normal credentials
    user_input = "student"
    pass_input = "learn123"
    query_vulnerable = f"SELECT role FROM users WHERE username = '{user_input}' AND password = '{pass_input}'"
    print("1. Vulnerable login, normal credentials")
    print(f"   query executed: {query_vulnerable}")
    res1 = cursor.execute(query_vulnerable).fetchone()
    print(f"   result: {res1}")

    # 2. Vulnerable login with SQL Injection payload
    injection_user = "' OR 1=1 --"
    injection_pass = "x"
    query_injected = f"SELECT role FROM users WHERE username = '{injection_user}' AND password = '{injection_pass}'"
    print("2. Vulnerable login, injection payload")
    print(f"   query executed: {query_injected}")
    res2 = cursor.execute(query_injected).fetchone()
    print(f"   result: {res2}")

    # 3. Parameterized login with injection payload (Safe Defense)
    safe_query = "SELECT role FROM users WHERE username = ? AND password = ?"
    print("3. Parameterised login, injection payload")
    res3 = cursor.execute(safe_query, (injection_user, injection_pass)).fetchone()
    print(f"   result: {res3}")

    conn.close()

if __name__ == "__main__":
    run_sqli_demo()
