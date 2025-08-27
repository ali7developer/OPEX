# pages/yearly_budget.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "opex.db"

def ensure_table():
    """Create table if it doesn't exist (safe to keep)."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS yearly_budget (
            id INTEGER PRIMARY KEY,
            year INTEGER,
            VALUE INTEGER,
            created TIMESTAMP,
            created_by TEXT,
            modified TIMESTAMP,
            modified_by TEXT,
            version INTEGER
        )
    """)
    conn.commit()
    conn.close()

def year_exists(year: int) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM yearly_budget WHERE year = ?", (year,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists

def insert_year_budget(year: int, amount: int, created_by: str = "admin"):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("""
        INSERT INTO yearly_budget (year, VALUE, created, created_by, modified, modified_by, version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (year, amount, now, created_by, now, created_by, 1))
    conn.commit()
    conn.close()

def load_table() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    df = pd.read_sql_query(
        'SELECT year AS "Year", "VALUE" AS "Amount", created_by AS "Created By" '
        "FROM yearly_budget ORDER BY year DESC",
        conn
    )
    conn.close()
    return df

def main():
    ensure_table()

    st.title("📅 Yearly Budget")

    # ---------- Top bar with right-aligned button ----------
    left, right = st.columns([9, 1])
    with right:
        if st.button("Add Year Budget", use_container_width=True, key="add_year_btn"):
            st.session_state["show_add_form"] = True

    # ---------- Add form (appears when button clicked) ----------
    if st.session_state.get("show_add_form", False):
        with st.container():
            st.markdown(
                "<div style='background:#f7f9fc;border:1px solid #e6eaf0;border-radius:10px;padding:16px;'>"
                "<h4 style='margin:0 0 12px 0;'>➕ Add Year Budget</h4>",
                unsafe_allow_html=True,
            )
            with st.form("add_year_budget_form", clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    year = st.number_input("Year", min_value=2000, max_value=2100, step=1, value=datetime.now().year)
                with col2:
                    amount = st.number_input("Amount (OMR)", min_value=0, step=1, value=0)

                fcol1, fcol2, _ = st.columns([1, 1, 6])
                with fcol1:
                    submitted = st.form_submit_button("Save")
                with fcol2:
                    cancel = st.form_submit_button("Cancel")

            st.markdown("</div>", unsafe_allow_html=True)

            if cancel:
                st.session_state["show_add_form"] = False
                st.rerun()  # <- immediate refresh

            if submitted:
                errors = []
                if year_exists(year):
                    errors.append("❌ This year already exists.")
                if amount <= 0:
                    errors.append("❌ Amount must be greater than 0.")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    insert_year_budget(int(year), int(amount), created_by="admin")
                    # Hide form and refresh to show updated table without errors/double click
                    st.session_state["show_add_form"] = False
                    st.rerun()  # <- immediate refresh

    # ---------- Data table ----------
    st.subheader("Yearly Budgets")
    df = load_table()
    if df.empty:
        st.info("No yearly budgets found yet.")
    else:
        st.dataframe(df, use_container_width=True)

# Only run when called as a page module
if __name__ == "__main__":
    main()
