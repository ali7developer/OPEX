import streamlit as st
import sqlite3
import pandas as pd
from pages.edit_budget import render_edit_page
from utils.style import apply_global_styles
from pages.components import render_footer

st.set_page_config(page_title="OPEX Budget Monitor", layout="wide")
apply_global_styles()

def insert_excel_data(df):
    conn = sqlite3.connect("opex.db")

    # Load reference mappings
    dept_map = pd.read_sql("SELECT id, name_en, directorate FROM departments", conn)
    account_map = pd.read_sql("SELECT id, account FROM accounts", conn)
    status_map = pd.read_sql("SELECT id, name_en FROM status_master WHERE category='case'", conn)

    success_count = 0
    for _, row in df.iterrows():
        try:
            # Resolve department
            dept_id = dept_map.loc[dept_map['name_en'] == row['Domain'], 'id']
            if dept_id.empty:
                dept_id = dept_map.loc[dept_map['directorate'] == row['Directorate'], 'id']
            dept_id = int(dept_id.iloc[0]) if not dept_id.empty else None

            # Resolve account
            account_id = account_map.loc[account_map['account'] == row['Account No'], 'id']
            account_id = int(account_id.iloc[0]) if not account_id.empty else None

            # Resolve status
            status_id = status_map.loc[status_map['name_en'] == row['case'], 'id']
            status_id = int(status_id.iloc[0]) if not status_id.empty else None

            # Insert
            conn.execute("""
                INSERT INTO amc_contracts (
                    pr_number, ref_departments, ref_account, ref_status,
                    expense_type, approval_amount, year, domain, c_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['pr_number'], dept_id, account_id, status_id,
                row['Expense'], row['Amount'], row['Year'], row['Domain'], row['C Code']
            ))
            success_count += 1
        except Exception as e:
            st.error(f"Failed to insert row: {e}")

    conn.commit()
    conn.close()
    st.success(f"✅ {success_count} rows imported into database.")

def main():
    query_params = st.query_params
    if "id" in query_params:
        render_edit_page(int(query_params["id"]))
        return

    st.title("📋 All OPEX Budget Records")

    # --- Top Buttons ---
    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.markdown("""
        <style>
        .border-btn {
            border: 2px solid #4CAF50;
            border-radius: 5px;
            padding: 8px 16px;
            text-decoration: none;
            color: black;
            font-weight: bold;
            background-color: #f9f9f9;
        }
        .border-btn:hover {
            background-color: #e6ffe6;
        }
        </style>
        <a href="./add_new" class="border-btn">➕ Add New Entry</a>
        """, unsafe_allow_html=True)

    with col_b:
        uploaded_file = st.file_uploader("📥 Import Data (Excel)", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file:
        try:
            df_excel = pd.read_excel(uploaded_file)
            st.success("File uploaded successfully! Here's a preview:")
            st.dataframe(df_excel.head(10))
            if st.button("📤 Import to Database"):
                insert_excel_data(df_excel)
        except Exception as e:
            st.error(f"Error reading file: {e}")

    # --- Load data ---
    conn = sqlite3.connect("opex.db")
    df = pd.read_sql_query("""
        SELECT 
            ac.id,
            d.name_en AS Department,
            a.account AS "Account No",
            a.name_en AS Account,
            ac.pr_number,
            ac.domain,
            ac.c_code,
            ac.expense_type,
            ac.cost_center,
            ac.approval_amount AS Amount,
            CASE WHEN ac.approved = 1 THEN "Yes" ELSE "No" END AS Approved,
            ac.contract_reference,
            ac.line_budget,
            ac.vendor,
            ac.sub_category,
            ac.ifrs_16,
            ac.email,
            ac.mobile,
            ac.start_date,
            ac.end_date,
            ac.year,
            ac.type_of_cost,
            ac.type_of_amc,
            ac.remarks,
            ac.cvd_status,
            ac.risk_comment AS Comment,
            ac.procurement_comment,
            ac.quotation_received,
            s.name_en AS Status,
            ac.created
        FROM amc_contracts ac 
        LEFT JOIN departments d ON ac.ref_departments = d.id
        LEFT JOIN accounts a ON ac.ref_account = a.id
        LEFT JOIN status_master s ON ac.ref_status = s.id
    """, conn)

    conn.close()

    # --- Filters ---
    st.subheader("🔍 Filter Records")
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    with col1:
        pr_search = st.text_input("PR Number")
    with col2:
        dept_search = st.selectbox("Department", options=[""] + sorted(df["Department"].dropna().unique().tolist()))
    with col3:
        year_search = st.text_input("Year")

    with col4:
        vendor_search = st.text_input("Vendor")
    with col5:
        status_search = st.selectbox("Status", options=[""] + sorted(df["Status"].dropna().unique().tolist()))
    with col6:
        account_no_search = st.text_input("Account No")

    if pr_search:
        df = df[df["pr_number"].astype(str).str.contains(pr_search.strip(), case=False)]
    if dept_search:
        df = df[df["Department"] == dept_search]
    if year_search:
        df = df[df["year"].astype(str).str.contains(year_search.strip(), case=False)]
    if vendor_search:
        df = df[df["vendor"].str.contains(vendor_search.strip(), case=False, na=False)]
    if status_search:
        df = df[df["Status"] == status_search]
    if account_no_search:
        df = df[df["Account No"].astype(str).str.contains(account_no_search.strip(), case=False)]

    # --- Export filtered data ---
    csv_data = df.drop(columns=["id"]).to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Export to CSV", data=csv_data, file_name='opex_budget_filtered.csv', mime='text/csv')

    # --- Display records ---
    if df.empty:
        st.warning("No matching records found.")
    else:
        for _, row in df.iterrows():
            row_display = row.to_frame().T.drop(columns=["id"])
            with st.container():
                st.dataframe(row_display, hide_index=True, use_container_width=True)
                edit_url = f"?id={row['id']}"
                st.markdown(f"<a href='{edit_url}' target='_self'>✏️ Edit</a>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    render_footer()