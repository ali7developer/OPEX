# add_new.py

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import re
from pages.department import insert_department
from pages.accounts import insert_account
import time
import os
import mimetypes
import json
from typing import Optional

# =========================================================
# NOTE: Assumes the SQLite table `attachment` ALREADY EXISTS
# with this schema:
# CREATE TABLE IF NOT EXISTS attachment (
#   id INTEGER PRIMARY KEY,
#   table_name TEXT NOT NULL,
#   ref_id INTEGER NOT NULL,
#   filename TEXT NOT NULL,
#   path TEXT NOT NULL,
#   mime_type TEXT,
#   size_bytes INTEGER,
#   meta TEXT,
#   created TIMESTAMP NOT NULL,
#   created_by TEXT,
#   modified TIMESTAMP NOT NULL,
#   modified_by TEXT,
#   version INTEGER
# );
# =========================================================

# =========================
# DB Helpers
# =========================
def get_dropdown_options(table, label_column, value_column="id", where_clause=None):
    conn = sqlite3.connect("opex.db")
    query = f"SELECT {value_column}, {label_column} FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    df = pd.read_sql(query, conn)
    conn.close()
    return {row[label_column]: row[value_column] for _, row in df.iterrows()}

def is_pr_number_exists(pr_number):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM amc_contracts WHERE pr_number = ?", (pr_number,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

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

    cursor.execute("""
        INSERT INTO amc_budgets (
            ref_amc_contract, year, units, unit_cost,
            created, created_by, modified, modified_by, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        amc_contract_id,
        data['year'],
        data['units'],
        data['unit_cost'],
        datetime.now(), "admin", datetime.now(), "admin", 1
    ))

    conn.commit()
    conn.close()
    return amc_contract_id

def insert_amc_pos(data, ref_amc_contract):
    """
    data expects:
      year (int), po_amount (float), po_number (str),
      pr_amount (float), pr_number (str)
    """
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO amc_pos (
            id, ref_amc_contract, year, po_amount, po_number,
            pr_amount, pr_number, created, created_by, modified, modified_by, version
        ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ref_amc_contract,
        data['year'],
        data['po_amount'],
        data['po_number'],
        data['pr_amount'],
        data['pr_number'],
        datetime.now(), "admin", datetime.now(), "admin", 1
    ))
    conn.commit()
    conn.close()

# =========================
# Attachment Recording (table already exists)
# =========================
def guess_mime(filename: str) -> Optional[str]:
    mt, _ = mimetypes.guess_type(filename)
    return mt

def record_attachment(
    table_name: str,
    ref_id: int,
    file_path: str,
    filename: str,
    mime_type: Optional[str],
    size_bytes: int,
    meta: Optional[dict] = None,
    user: str = "admin",
    version: int = 1
):
    now = datetime.now()
    conn = sqlite3.connect("opex.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attachment (
          table_name, ref_id, filename, path, mime_type, size_bytes, meta,
          created, created_by, modified, modified_by, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        table_name,
        ref_id,
        filename,
        file_path,
        mime_type,
        size_bytes,
        json.dumps(meta) if meta else None,
        now, user, now, user, version
    ))
    conn.commit()
    conn.close()

def save_uploads_and_record(uploaded_files, dest_dir: str, table_name: str, ref_id: int):
    """
    Saves uploaded files to dest_dir and records each file in 'attachment' table
    with created/modified/version metadata. Returns list of saved paths.
    """
    os.makedirs(dest_dir, exist_ok=True)
    saved_paths = []
    for f in uploaded_files or []:
        path = os.path.join(dest_dir, f.name)
        with open(path, "wb") as out:
            out.write(f.getbuffer())
        saved_paths.append(path)

        mime = guess_mime(f.name)
        size = len(f.getbuffer())
        record_attachment(
            table_name=table_name,
            ref_id=ref_id,
            file_path=path,
            filename=f.name,
            mime_type=mime,
            size_bytes=size,
            meta=None,
            user="admin",
            version=1
        )
    return saved_paths

# =========================
# Misc Helpers
# =========================
def is_valid_email(email):
    if not email:
        return True
    return re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", email)

def go_monitor_page():
    try:
        st.switch_page("pages/monitor.py")
    except Exception:
        st.session_state.page = "monitor"
        st.rerun()

# =========================
# App
# =========================
def main():
    st.title("\u2795 Add New OPEX Budget Record")

    # Top bar (logo only; breadcrumb removed)
    top_c1, _ = st.columns([1, 5])
    with top_c1:
        st.image("assets/ooredoo.png", width=90)

    # Button styles (Submit & Cancel identical)
    st.markdown("""
        <style>
        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
            font-weight: 700 !important;
            color: #B00020 !important;
            border: 2px solid #B00020 !important;
            background: transparent !important;
            min-width: 170px !important;
            padding: 0.6rem 1rem !important;
            border-radius: 10px !important;
        }
        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
            background: rgba(176,0,32,0.08) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # UI state
    if "show_dept_form" not in st.session_state:
        st.session_state.show_dept_form = False
    if "show_account_form" not in st.session_state:
        st.session_state.show_account_form = False
    for key, default in [("approved_flag", False), ("po_number", ""), ("po_amount", 0.0)]:
        st.session_state.setdefault(key, default)

    # Dropdown data
    dept_options = get_dropdown_options("departments", "name_en")
    account_options = get_dropdown_options("accounts", "name_en")
    status_options = get_dropdown_options("status_master", "name_en", where_clause="category = 'case'")

    # Department selector + Add
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

    # Account selector + Add
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

    # ===== Approved? OUTSIDE the form (PO fields appear immediately below) =====
    st.session_state.approved_flag = st.checkbox(
        "Approved?",
        value=st.session_state.approved_flag,
        help="If checked, PO Number and PO Amount will be required."
    )

    if st.session_state.approved_flag:
        st.markdown("**PO Details**")
        st.session_state.po_number = st.text_input(
            "PO Number",
            value=st.session_state.po_number,
            key="po_number_field"
        )
        st.session_state.po_amount = st.number_input(
            "PO Amount (OMR)",
            min_value=0.00, step=0.01, format="%.2f",
            value=float(st.session_state.po_amount) if st.session_state.po_amount else 0.00,
            key="po_amount_field"
        )

    # =============== MAIN FORM ===============
    with st.form("add_pr_form"):
        pr_number = st.number_input("PR Number", min_value=1)
        approval_amount = st.number_input("Approval Amount (OMR)", min_value=0.01, value=0.01, step=0.01, format="%.2f")
        contract_reference = st.text_input("Contract Reference")
        comments = st.text_area("Comments")
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
        line_budget = st.text_input("Line Budget")
        quotation_received = st.checkbox("Quotation Received?")
        c_code = st.text_input("C Code")
        cost_center = st.text_input("Cost Center")
        expense_type = st.text_input("Expense Type")
        vendor = st.text_input("Vendor Name")
        vendor_email = st.text_input("Vendor Email")
        vendor_mobile = st.text_input("Vendor Mobile")
        units = st.number_input("Units", min_value=0, step=1)
        unit_cost = st.number_input("Unit Cost (OMR)", min_value=0.0, step=0.01, format="%.2f")
        status = st.selectbox("PR Status", list(status_options.keys()) if status_options else ["No Status Found"])

        # --------- ATTACHMENTS (Optional) ---------
        with st.expander("📎 Attachments (optional)"):
            att_pdf = st.file_uploader("Add PDF", type=["pdf"], accept_multiple_files=True, key="att_pdf")
            att_excel = st.file_uploader("Add Excel", type=["xlsx", "xls"], accept_multiple_files=True, key="att_excel")
            att_csv = st.file_uploader("Add CSV", type=["csv"], accept_multiple_files=True, key="att_csv")
            att_img = st.file_uploader("Add Images (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="att_img")
            att_doc = st.file_uploader("Add Word Docs", type=["doc", "docx"], accept_multiple_files=True, key="att_doc")

        # ---- Submit & Cancel (side-by-side, centered, identical style) ----
        spacerL, col_submit, spacerM, col_cancel, spacerR = st.columns([1, 1, 0.2, 1, 1])
        with col_submit:
            submitted = st.form_submit_button("Submit")
        with col_cancel:
            cancel_main = st.form_submit_button("Cancel")

    # ---- Handle Cancel first (redirect to monitor.py) ----
    if 'cancel_main' in locals() and cancel_main:
        go_monitor_page()

    # ---- Handle Submit ----
    if 'submitted' in locals() and submitted:
        errors = []
        if is_pr_number_exists(pr_number):
            errors.append("\u274c This PR Number already exists.")
        if approval_amount <= 0:
            errors.append("\u274c Approval Amount must be greater than 0.")
        if not vendor.strip():
            errors.append("\u274c Vendor name is required.")
        if vendor_email and not is_valid_email(vendor_email):
            errors.append("\u274c Invalid email format.")
        if vendor_mobile and not vendor_mobile.isdigit():
            errors.append("\u274c Vendor mobile must be digits only.")
        if start_date >= end_date:
            errors.append("\u274c End Date must be after Start Date.")

        # If approved, require PO number and PO amount > 0
        if st.session_state.approved_flag:
            if not st.session_state.po_number or not str(st.session_state.po_number).strip():
                errors.append("\u274c PO Number is required when Approved is checked.")
            if st.session_state.po_amount is None or float(st.session_state.po_amount) <= 0:
                errors.append("\u274c PO Amount must be greater than 0 when Approved is checked.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            amc_contract_id = insert_amc_contract({
                'pr_number': pr_number,
                'approval_amount': approval_amount,
                'approved': st.session_state.approved_flag,
                'contract_reference': contract_reference,
                'line_budget': line_budget.strip(),
                'vendor': vendor.strip(),
                'sub_category': sub_category,
                'ifrs_16': ifrs_16,
                'vendor_email': vendor_email.strip() if vendor_email else None,
                'vendor_mobile': vendor_mobile.strip() if vendor_mobile else None,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'year': year,
                'type_of_cost': type_of_cost,
                'type_of_amc': type_of_amc,
                'remarks': remarks,
                'risk_comment': risk_comment,
                'procurement_comment': procurement_comment,
                'quotation_received': quotation_received,
                'c_code': c_code,
                'expense_type': expense_type,
                'cost_center': cost_center,
                'ref_departments': dept_options[department_selection],
                'ref_account': account_options[account_selection],
                'ref_status': status_options[status],
                'domain': department_selection,
                'account_name': account_selection,
                'units': units,
                'unit_cost': unit_cost
            })

            # Save & record attachments under ./attachments/amc_<id>/
            dest = os.path.join("attachments", f"amc_{amc_contract_id}")
            saved_paths = []
            for group in [att_pdf, att_excel, att_csv, att_img, att_doc]:
                saved_paths.extend(
                    save_uploads_and_record(
                        uploaded_files=group,
                        dest_dir=dest,
                        table_name="amc_contracts",
                        ref_id=amc_contract_id
                    )
                )

            # If approved, write to amc_pos with the provided PO fields
            if st.session_state.approved_flag:
                insert_amc_pos({
                    'year': int(year),
                    'po_amount': float(st.session_state.po_amount),
                    'po_number': str(st.session_state.po_number).strip(),
                    'pr_amount': float(approval_amount),
                    'pr_number': str(pr_number)
                }, ref_amc_contract=amc_contract_id)

            st.success("\u2705 The data saved successfully." + (f" Saved {len(saved_paths)} attachment(s)." if saved_paths else ""))
            time.sleep(1.2)
            go_monitor_page()

    # ---- Back to Budget View Button ----
    if st.button("\u2b05 Back to Budget View"):
        go_monitor_page()

if __name__ == "__main__":
    main()
