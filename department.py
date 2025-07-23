import sqlite3
from datetime import datetime

# --- Insert new department ---
def insert_department(name, category, directorate="Service Assurance & Optimization"):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM departments WHERE name_en = ?", (name,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return None
    cursor.execute("""
        INSERT INTO departments (
            name_en, catogoery, directorate,
            created, created_by, modified, modified_by, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name, category, directorate,
            datetime.now(), "admin", datetime.now(), "admin", 1
        )
    )
    dept_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return dept_id