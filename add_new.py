import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import re
from pages.department import insert_department  
from pages.accounts import insert_account
import time

# --- Get dropdown values ---
def get_dropdown_options(table, label_column, value_column="id", where_clause=None):
    conn = sqlite3.connect("opex.db")
    query = f"SELECT {value_column}, {label_column} FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    df = pd.read_sql(query, conn)
    conn.close()
    return {row[label_column]: row[value_column] for _, row in df.iterrows()}

# --- Check if PR Number exists ---
def is_pr_number_exists(pr_number):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM amc_contracts WHERE pr_number = ?", (pr_number,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# --- Insert into amc_contracts ---
def insert_amc_contract(data):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO amc_contracts (
            pr_number, domain, c_code, expense_type, cost_center,
            approval_amount, approved, contract_reference, line_budget,
            vendor, sub_category, ifrs_16, email, mobile,
            start_date, end_date, year, type_of_cost, type_of_amc,
            remarks, risk_comment, procurement_comment,
            quotation_received, ref_departments, ref_account, ref_status,
            created, created_by, modified, modified_by, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['pr_number'], data['domain'], data['c_code'], data['expense_type'], data['cost_center'],
        data['approval_amount'], data['approved'], data['contract_reference'], data['line_budget'],
        data['vendor'], data['sub_category'], data['ifrs_16'], data['vendor_email'], data['vendor_mobile'],
        data['start_date'], data['end_date'], data['year'], data['type_of_cost'], data['type_of_amc'],
        data['remarks'],  data['risk_comment'], data['procurement_comment'],
        data['quotation_received'], data['ref_departments'], data['ref_account'], data['ref_status'],
        datetime.now(), "admin", datetime.now(), "admin", 1
    ))

    amc_contract_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return amc_contract_id

# --- Insert into amc_pos ---
def insert_amc_pos(data, ref_amc_contract):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO amc_pos (
            ref_amc_contract, year, po_amount, po_number,
            pr_amount, pr_number,
            created, created_by, modified, modified_by, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ref_amc_contract,
        datetime.now().year,
        None,
        None,
        data['approval_amount'],
        str(data['pr_number']),
        datetime.now(), "admin", datetime.now(), "admin", 1
    ))
    conn.commit()
    conn.close()

# --- Email validator ---
def is_valid_email(email):
    if not email:
        return True
    return re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}", email)

# --- Main ---
def main():
    st.title("\u2795 Add New OPEX Budget Record")

    if "show_dept_form" not in st.session_state:
        st.session_state.show_dept_form = False
    if "show_account_form" not in st.session_state:
        st.session_state.show_account_form = False

    dept_options = get_dropdown_options("departments", "name_en")
    account_options = get_dropdown_options("accounts", "name_en")
    status_options = get_dropdown_options("status_master", "name_en", where_clause="category = 'case'")

    errors = []

    col1, col2 = st.columns([3, 1])
    with col1:
        department_selection = st.selectbox("Department", list(dept_options.keys()))
    with col2:
        if st.button("\u2795 Add Department"):
            st.session_state.show_dept_form = not st.session_state.show_dept_form

    if st.session_state.get("show_dept_form"):
        with st.container():
            st.markdown("""
                <div style='background-color: #f0f8ff; padding: 15px; border: 2px solid #1f77b4; border-radius: 10px;'>
                    <h4 style='color: #1f77b4;'>📌 Add New Department</h4>
            """, unsafe_allow_html=True)
            with st.form("add_dept_form", clear_on_submit=True):
                new_dept = st.text_input("New Department Name")
                new_cat = st.selectbox("Category", ["IT", "NW"])
                new_dir = st.text_input("Directorate", value="Service Assurance & Optimization")
                col_save, col_cancel = st.columns(2)
                with col_save:
                    submitted_new_dept = st.form_submit_button("Save Department")
                with col_cancel:
                    cancel_dept = st.form_submit_button("Cancel")

                if submitted_new_dept:
                    if new_dept.strip():
                        dept_id = insert_department(new_dept.strip(), new_cat, new_dir.strip())
                        if dept_id:
                            st.success("\u2705 Department added successfully.")
                            st.session_state.show_dept_form = False
                            st.rerun()
                        else:
                            st.error("\u274c This department already exists. Please enter a unique name.")
                    else:
                        st.error("\u274c Department name cannot be empty.")
                elif cancel_dept:
                    st.session_state.show_dept_form = False
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns([3, 1])
    with col3:
        account_selection = st.selectbox("Account", list(account_options.keys()))
    with col4:
        if st.button("\u2795 Add Account"):
            st.session_state.show_account_form = not st.session_state.show_account_form

    if st.session_state.get("show_account_form"):
        with st.container():
            st.markdown("""
                <div style='background-color: #fff8dc; padding: 15px; border: 2px solid #d2691e; border-radius: 10px;'>
                    <h4 style='color: #d2691e;'>📘 Add New Account</h4>
            """, unsafe_allow_html=True)
            with st.form("add_account_form", clear_on_submit=True):
                new_account_name = st.text_input("Account Name")
                new_account_number = st.text_input("Account Number")
                col_save, col_cancel = st.columns(2)
                with col_save:
                    submit_account = st.form_submit_button("Save Account")
                with col_cancel:
                    cancel_account = st.form_submit_button("Cancel")

                if submit_account:
                    if not new_account_name.strip() or not new_account_number.strip():
                        st.error("\u274c All account fields must be filled.")
                    elif not new_account_number.isdigit():
                        st.error("\u274c Account number must contain digits only.")
                    else:
                        result = insert_account(new_account_name.strip(), int(new_account_number))
                        if result:
                            st.success("\u2705 Account added successfully.")
                            st.session_state.show_account_form = False
                            st.rerun()
                        else:
                            st.error("\u274c This account already exists. Please enter a unique one.")
                elif cancel_account:
                    st.session_state.show_account_form = False
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with st.form("add_pr_form"):
        pr_number = st.number_input("PR Number", min_value=1)
        approval_amount = st.number_input("Approval Amount (OMR) - Not less than 0", min_value=0.01, value=0.01, step=0.01, format="%.2f")
        approved = st.checkbox("Approved?")
        contract_reference = st.text_input("Contract Reference")
        comments = st.text_area("Comments")
        domain = st.text_input("Domain")

        ref_departments = dept_options.get(department_selection)
        ref_account = account_options[account_selection]

        status = st.selectbox("PR Status", list(status_options.keys()) if status_options else ["No Status Found"])

        year = st.number_input("Year", min_value=2000, max_value=2100, value=datetime.now().year)
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")
        type_of_amc = st.text_input("Type of AMC")
        type_of_cost = st.text_input("Type of Cost")
        remarks = st.text_area("Remarks")
        risk_comment = st.text_area("Risk Comment")
        procurement_comment = st.text_area("Procurement Comment")
        sub_category = st.text_input("Sub Category")
        ifrs_16 = st.text_input("IFRS")
        line_budget = st.text_input("Line Budget (Mandatory)")
        quotation_received = st.checkbox("Quotation Received?")
        c_code = st.text_input("C Code")
        cost_center = st.text_input("Cost Center")
        expense_type = st.text_input("Expense type")
        vendor = st.text_input("Vendor Name (Mandatory)")
        vendor_email = st.text_input("Vendor Email (Optional)")
        vendor_mobile = st.text_input("Vendor Mobile (Optional)", key='vendor_mobile')

        submitted = st.form_submit_button("Submit")

    if submitted:
        if is_pr_number_exists(pr_number):
            errors.append("\u274c This PR Number already exists. Please enter a unique PR Number.")

        if approval_amount <= 0:
            errors.append("\u274c Approval Amount must be greater than 0.")
        if not vendor.strip():
            errors.append("\u274c Vendor name is required.")
        if vendor_email and not is_valid_email(vendor_email):
            errors.append("\u274c Vendor email format is invalid.")
        if vendor_mobile and not vendor_mobile.isdigit():
            errors.append("\u274c Vendor mobile must contain digits only.")
        if not line_budget.strip():
            errors.append("\u274c Line Budget is required.")
        if start_date >= end_date:
            errors.append("\u274c End Date must be later than Start Date.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            amc_contract_id = insert_amc_contract({
                'pr_number': pr_number,
                'approval_amount': approval_amount,
                'approved': approved,
                'domain': domain,
                'type_of_amc': type_of_amc,
                'remarks': remarks,
                'contract_reference': contract_reference,
                'risk_comment': comments,
                'ref_departments': ref_departments,
                'ref_account': ref_account,
                'ref_status': status_options[status],
                'vendor': vendor.strip(),
                'vendor_email': vendor_email.strip() if vendor_email else None,
                'vendor_mobile': vendor_mobile.strip() if vendor_mobile else None,
                'year': year,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'type_of_cost': type_of_cost,
                'procurement_comment': procurement_comment,
                'sub_category': sub_category,
                'ifrs_16': ifrs_16,
                'line_budget': line_budget.strip(),
                'quotation_received': quotation_received,
                'c_code': c_code,
                'expense_type': expense_type,
                'cost_center': cost_center
            })

            if approved:
                insert_amc_pos({
                    'pr_number': pr_number,
                    'approval_amount': approval_amount
                }, ref_amc_contract=amc_contract_id)

        st.success("✅ The data saved successfully.")
        time.sleep(2)  # Wait for 2 seconds so user sees the message
        st.session_state.page = "monitor"
        st.rerun()

    if st.button("\u2b05 Back to Budget View"):
        st.session_state.page = "monitor"
        st.rerun()

if __name__ == "__main__":
    main()
