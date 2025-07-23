import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

def main():
    st.title("📊 AMC Contracts – Spending by Department")

    # --- Connect to the database ---
    conn = sqlite3.connect("opex.db")

    # --- Fetch available years ---
    years_query = "SELECT DISTINCT year FROM amc_contracts WHERE approved = 1 ORDER BY year DESC"
    years = pd.read_sql_query(years_query, conn)['year'].tolist()

    # --- Year multiselect (all selected by default) ---
    selected_years = st.multiselect("Select Year(s)", years, default=years)

    # --- Fetch filtered data from DB ---
    query = f"""
    SELECT 
        d.name_en AS Department,
        SUM(ac.approval_amount) AS Spending_OMR
    FROM amc_contracts ac
    INNER JOIN departments d ON d.id = ac.ref_departments
    WHERE ac.approved = 1 AND ac.year IN ({','.join(['?']*len(selected_years))})
    GROUP BY d.name_en
    ORDER BY Spending_OMR DESC
    """
    df = pd.read_sql_query(query, conn, params=selected_years)
    conn.close()

    # --- Display data ---
    st.subheader(f"Spending Summary for Years: {', '.join(map(str, selected_years))}")
    st.dataframe(df)

    # --- Bar chart ---
    st.subheader("Spending by Department (OMR)")
    fig, ax = plt.subplots()
    ax.bar(df['Department'], df['Spending_OMR'], color="#E60000")
    ax.set_xlabel("Department")
    ax.set_ylabel("Spending (OMR)")
    ax.set_title("Total Spending by Department")
    plt.xticks(rotation=45)
    st.pyplot(fig)
