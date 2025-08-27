import sqlite3

def insert_account(name_en, account):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()

    # Ensure account number is unique
    cursor.execute("SELECT id FROM accounts WHERE account = ?", (account,))
    existing_account = cursor.fetchone()

    if existing_account:
        conn.close()
        return None  # Account number already exists

    cursor.execute("""
        INSERT INTO accounts (
            name_en, account, created, created_by, modified, modified_by, version
        ) VALUES (?, ?, datetime('now'), 'admin', datetime('now'), 'admin', 1)
    """, (name_en, account))

    conn.commit()
    account_id = cursor.lastrowid
    conn.close()
    return account_id
