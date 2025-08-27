# edit_budget.py

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import mimetypes
import json

# =========================
# Small DB helpers
# =========================
def get_dropdown_options(table, label_column, value_column="id", where_clause=None):
    """Return a dict {label -> id} from a table."""
    conn = sqlite3.connect("opex.db")
    query = f"SELECT {value_column}, {label_column} FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    df = pd.read_sql(query, conn)
    conn.close()
    return {row[label_column]: row[value_column] for _, row in df.iterrows()}

def _name_for_id(options_dict: dict, id_val):
    """Reverse-lookup name from {name->id} dict; return None if missing."""
    for name, vid in options_dict.items():
        if int(vid) == int(id_val):
            return name
    return None

def update_record(record_id, form_data):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()

    update_query = """
        UPDATE amc_contracts SET
            pr_number = ?, domain = ?, c_code = ?, expense_type = ?, cost_center = ?,
            approval_amount = ?, approved = ?, contract_reference = ?, line_budget = ?,
            vendor = ?, sub_category = ?, ifrs_16 = ?, email = ?, mobile = ?,
            start_date = ?, end_date = ?, year = ?, type_of_cost = ?, type_of_amc = ?,
            remarks = ?, cvd_status = ?, risk_comment = ?, procurement_comment = ?,
            quotation_received = ?, ref_departments = ?, ref_account = ?, ref_status = ?,
            modified = ?, modified_by = ?
        WHERE id = ?
    """

    cursor.execute(update_query, (
        form_data["pr_number"], form_data["domain"], form_data["c_code"], form_data["expense_type"], form_data["cost_center"],
        form_data["approval_amount"], form_data["approved"], form_data["contract_reference"], form_data["line_budget"],
        form_data["vendor"], form_data["sub_category"], form_data["ifrs_16"], form_data["email"], form_data["mobile"],
        form_data["start_date"], form_data["end_date"], form_data["year"], form_data["type_of_cost"], form_data["type_of_amc"],
        form_data["remarks"], form_data["cvd_status"], form_data["risk_comment"], form_data["procurement_comment"],
        form_data["quotation_received"], form_data["ref_departments"], form_data["ref_account"], form_data["ref_status"],
        datetime.now(), "admin", record_id
    ))

    conn.commit()
    conn.close()

def delete_record(record_id):
    conn = sqlite3.connect("opex.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM amc_contracts WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

def fetch_contract(record_id):
    conn = sqlite3.connect("opex.db")
    df = pd.read_sql_query("SELECT * FROM amc_contracts WHERE id = ?", conn, params=(record_id,))
    conn.close()
    return df

def fetch_pos_for_contract_year(ref_amc_contract: int, year: int):
    conn = sqlite3.connect("opex.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, year, po_amount, po_number, pr_amount, pr_number
        FROM amc_pos
        WHERE ref_amc_contract = ? AND year = ?
        ORDER BY id DESC
        LIMIT 1
    """, (ref_amc_contract, year))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "year": row[1],
        "po_amount": row[2],
        "po_number": row[3],
        "pr_amount": row[4],
        "pr_number": row[5],
    }

def upsert_amc_pos(ref_amc_contract: int, year: int, pr_amount: float, pr_number: str, po_number: str, po_amount: float):
    conn = sqlite3.connect("opex.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM amc_pos
        WHERE ref_amc_contract = ? AND year = ?
        ORDER BY id DESC
        LIMIT 1
    """, (ref_amc_contract, year))
    row = cur.fetchone()
    now = datetime.now()
    if row:
        pos_id = row[0]
        cur.execute("""
            UPDATE amc_pos
               SET po_amount = ?, po_number = ?, pr_amount = ?, pr_number = ?,
                   modified = ?, modified_by = ?, version = COALESCE(version,0) + 1
             WHERE id = ?
        """, (po_amount, po_number, pr_amount, pr_number, now, "admin", pos_id))
    else:
        cur.execute("""
            INSERT INTO amc_pos (
                ref_amc_contract, year, po_amount, po_number,
                pr_amount, pr_number, created, created_by, modified, modified_by, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ref_amc_contract, year, po_amount, po_number, pr_amount, pr_number, now, "admin", now, "admin", 1))
    conn.commit()
    conn.close()

# =========================
# Attachment recording (assumes `attachment` table already exists)
# Schema given by you.
# =========================
def guess_mime(filename: str):
    mt, _ = mimetypes.guess_type(filename)
    return mt

def record_attachment(table_name: str, ref_id: int, file_path: str, filename: str, mime_type: str | None, size_bytes: int, meta: dict | None = None, user: str = "admin", version: int = 1):
    conn = sqlite3.connect("opex.db")
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("""
        INSERT INTO attachment (
          table_name, ref_id, filename, path, mime_type, size_bytes, meta,
          created, created_by, modified, modified_by, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (table_name, ref_id, filename, file_path, mime_type, size_bytes, json.dumps(meta) if meta else None, now, user, now, user, version))
    conn.commit()
    conn.close()

def save_uploads_and_record(uploaded_files, dest_dir: str, table_name: str, ref_id: int):
    os.makedirs(dest_dir, exist_ok=True)
    saved_paths = []
    for f in uploaded_files or []:
        path = os.path.join(dest_dir, f.name)
        with open(path, "wb") as out:
            out.write(f.getbuffer())
        saved_paths.append(path)
        record_attachment(
            table_name=table_name,
            ref_id=ref_id,
            file_path=path,
            filename=f.name,
            mime_type=guess_mime(f.name),
            size_bytes=len(f.getbuffer()),
            meta=None,
            user="admin",
            version=1
        )
    return saved_paths

def go_monitor_page():
    try:
        st.switch_page("pages/monitor.py")
    except Exception:
        st.session_state.page = "monitor"
        st.rerun()

# =========================
# UI
# =========================
def render_edit_page(record_id):
    st.title("✏️ Edit OPEX Budget Record")

    # Delete flow state
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False
    if "delete_complete" not in st.session_state:
        st.session_state.delete_complete = False

    if st.session_state.delete_complete:
        st.success("Record deleted successfully.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔙 Back to Monitor", key="back_after_delete"):
                st.session_state.delete_complete = False
                st.query_params.clear()
                go_monitor_page()
        with col2:
            if st.button("🏠 Go to Home", key="home_after_delete"):
                st.session_state.delete_complete = False
                st.query_params.clear()
                try:
                    st.switch_page("Home")
                except Exception:
                    st.rerun()
        return

    # Fetch current contract row
    df = fetch_contract(record_id)
    if df.empty:
        st.error("Record not found.")
        return
    row = df.iloc[0]

    # Load dropdown options (actual values instead of raw ref IDs)
    dept_options = get_dropdown_options("departments", "name_en")  # {name -> id}
    account_options = get_dropdown_options("accounts", "name_en")  # {name -> id}
    status_options = get_dropdown_options("status_master", "name_en", where_clause="category = 'case'")  # {name -> id}

    # Approved? checkbox OUTSIDE the form (to instantly show PO fields)
    if "approved_flag" not in st.session_state:
        st.session_state.approved_flag = bool(int(row.get("approved", 0)))

    # Load existing PO details for the contract's current year (if any)
    current_year = int(row["year"]) if pd.notna(row["year"]) else datetime.now().year
    if "po_loaded_once" not in st.session_state:
        pos = fetch_pos_for_contract_year(record_id, current_year)
        st.session_state.po_number = (pos["po_number"] if pos and pos["po_number"] is not None else "")
        st.session_state.po_amount = float(pos["po_amount"]) if (pos and pos["po_amount"] not in (None, "")) else 0.0
        st.session_state.po_loaded_once = True

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

    # Determine preselected names for dropdowns based on existing ref_* ids
    current_dept_name = _name_for_id(dept_options, row["ref_departments"]) if pd.notna(row["ref_departments"]) else None
    if not current_dept_name and isinstance(row.get("domain"), str) and row["domain"] in dept_options:
        current_dept_name = row["domain"]
    if not current_dept_name and len(dept_options) > 0:
        current_dept_name = list(dept_options.keys())[0]

    current_account_name = _name_for_id(account_options, row["ref_account"]) if pd.notna(row["ref_account"]) else None
    if not current_account_name and len(account_options) > 0:
        current_account_name = list(account_options.keys())[0]

    current_status_name = _name_for_id(status_options, row["ref_status"]) if pd.notna(row["ref_status"]) else None
    if not current_status_name and len(status_options) > 0:
        current_status_name = list(status_options.keys())[0]

    # ---- Edit form
    with st.form("edit_form"):
        # Domain/Department dropdown (affects amc_contracts.domain and ref_departments)
        dept_names = list(dept_options.keys())
        dept_index = dept_names.index(current_dept_name) if current_dept_name in dept_names else 0
        selected_dept_name = st.selectbox("Department (Domain)", dept_names, index=dept_index)

        # Accounts dropdown (affects ref_account)
        account_names = list(account_options.keys())
        account_index = account_names.index(current_account_name) if current_account_name in account_names else 0
        selected_account_name = st.selectbox("Account", account_names, index=account_index)

        # Status dropdown (replace ref_status numeric with actual value)
        status_names = list(status_options.keys())
        status_index = status_names.index(current_status_name) if current_status_name in status_names else 0
        selected_status_name = st.selectbox("PR Status", status_names, index=status_index)

        # The rest of the fields
        pr_number = st.text_input("PR Number", str(row["pr_number"]) if pd.notna(row["pr_number"]) else "")
        c_code = st.text_input("C Code", row["c_code"] if pd.notna(row["c_code"]) else "")
        expense_type = st.text_input("Expense Type", row["expense_type"] if pd.notna(row["expense_type"]) else "")
        cost_center = st.text_input("Cost Center", row["cost_center"] if pd.notna(row["cost_center"]) else "")
        approval_amount = st.number_input("Approval Amount", value=float(row["approval_amount"]) if pd.notna(row["approval_amount"]) else 0.0)

        contract_reference = st.text_input("Contract Reference", row["contract_reference"] if pd.notna(row["contract_reference"]) else "")
        line_budget = st.text_input("Line Budget", row["line_budget"] if pd.notna(row["line_budget"]) else "")
        vendor = st.text_input("Vendor", row["vendor"] if pd.notna(row["vendor"]) else "")
        sub_category = st.text_input("Sub Category", row["sub_category"] if pd.notna(row["sub_category"]) else "")
        ifrs_16 = st.text_input("IFRS 16", row["ifrs_16"] if pd.notna(row["ifrs_16"]) else "")
        email = st.text_input("Email", row["email"] if pd.notna(row["email"]) else "")
        mobile = st.text_input("Mobile", row["mobile"] if pd.notna(row["mobile"]) else "")

        start_date = st.date_input("Start Date", pd.to_datetime(row["start_date"]).date() if pd.notna(row["start_date"]) else datetime.now().date())
        end_date = st.date_input("End Date", pd.to_datetime(row["end_date"]).date() if pd.notna(row["end_date"]) else datetime.now().date())
        year = st.number_input("Year", value=int(row["year"]) if pd.notna(row["year"]) else datetime.now().year, step=1)
        type_of_cost = st.text_input("Type of Cost", row["type_of_cost"] if pd.notna(row["type_of_cost"]) else "")
        type_of_amc = st.text_input("Type of AMC", row["type_of_amc"] if pd.notna(row["type_of_amc"]) else "")
        remarks = st.text_area("Remarks", row["remarks"] if pd.notna(row["remarks"]) else "")
        cvd_status = st.text_input("CVD Status", row["cvd_status"] if pd.notna(row["cvd_status"]) else "")
        risk_comment = st.text_area("Risk Comment", row["risk_comment"] if pd.notna(row["risk_comment"]) else "")
        procurement_comment = st.text_area("Procurement Comment", row["procurement_comment"] if pd.notna(row["procurement_comment"]) else "")

        quotation_received = st.selectbox("Quotation Received", [0, 1], index=[0, 1].index(int(row["quotation_received"]) if pd.notna(row["quotation_received"]) else 0))

        # --------- ATTACHMENTS (Optional) ---------
        with st.expander("📎 Attachments (optional)"):
            att_pdf = st.file_uploader("Add PDF", type=["pdf"], accept_multiple_files=True, key="att_pdf_edit")
            att_excel = st.file_uploader("Add Excel", type=["xlsx", "xls"], accept_multiple_files=True, key="att_excel_edit")
            att_csv = st.file_uploader("Add CSV", type=["csv"], accept_multiple_files=True, key="att_csv_edit")
            att_img = st.file_uploader("Add Images (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="att_img_edit")
            att_doc = st.file_uploader("Add Word Docs", type=["doc", "docx"], accept_multiple_files=True, key="att_doc_edit")

        # ---- Buttons row: Save | Cancel | Delete ----
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            submitted = st.form_submit_button("Save Changes")
        with c2:
            cancel_clicked = st.form_submit_button("Cancel")
        with c3:
            delete_clicked = st.form_submit_button("❌ Delete Record")

    # Cancel -> back to monitor
    if 'cancel_clicked' in locals() and cancel_clicked:
        go_monitor_page()

    # Submit handling
    if 'submitted' in locals() and submitted:
        errors = []
        if start_date >= end_date:
            errors.append("❌ End Date must be after Start Date.")
        if st.session_state.approved_flag:
            if not st.session_state.po_number or not str(st.session_state.po_number).strip():
                errors.append("❌ PO Number is required when Approved is checked.")
            if st.session_state.po_amount is None or float(st.session_state.po_amount) <= 0:
                errors.append("❌ PO Amount must be greater than 0 when Approved is checked.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            form_data = {
                "pr_number": pr_number,
                # "domain" should store the actual department name
                "domain": selected_dept_name,
                "c_code": c_code,
                "expense_type": expense_type,
                "cost_center": cost_center,
                "approval_amount": float(approval_amount) if approval_amount is not None else 0.0,
                "approved": 1 if st.session_state.approved_flag else 0,
                "contract_reference": contract_reference,
                "line_budget": line_budget,
                "vendor": vendor,
                "sub_category": sub_category,
                "ifrs_16": ifrs_16,
                "email": email,
                "mobile": mobile,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "year": int(year),
                "type_of_cost": type_of_cost,
                "type_of_amc": type_of_amc,
                "remarks": remarks,
                "cvd_status": cvd_status,
                "risk_comment": risk_comment,
                "procurement_comment": procurement_comment,
                "quotation_received": int(quotation_received),
                # Replace raw numeric ref inputs with actual selections -> map back to ids for DB
                "ref_departments": int(dept_options[selected_dept_name]),
                "ref_account": int(account_options[selected_account_name]),
                "ref_status": int(status_options[selected_status_name]),
            }
            update_record(record_id, form_data)

            # Save & record attachments under ./attachments/amc_<id>/
            dest = os.path.join("attachments", f"amc_{record_id}")
            saved_paths = []
            for group in [att_pdf, att_excel, att_csv, att_img, att_doc]:
                saved_paths.extend(
                    save_uploads_and_record(
                        uploaded_files=group,
                        dest_dir=dest,
                        table_name="amc_contracts",
                        ref_id=record_id
                    )
                )

            # If approved, upsert amc_pos for (record_id, year)
            if st.session_state.approved_flag:
                upsert_amc_pos(
                    ref_amc_contract=record_id,
                    year=int(year),
                    pr_amount=float(approval_amount) if approval_amount is not None else 0.0,
                    pr_number=str(pr_number),
                    po_number=str(st.session_state.po_number).strip(),
                    po_amount=float(st.session_state.po_amount)
                )

            st.success("✅ Record updated successfully." + (f" Saved {len(saved_paths)} attachment(s)." if saved_paths else ""))
            go_monitor_page()

    # Delete flow
    if 'delete_clicked' in locals() and delete_clicked:
        st.session_state.confirm_delete = True
        st.rerun()

    if st.session_state.confirm_delete:
        st.warning("Are you sure you want to delete this record?")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("✅ Yes, Delete it"):
                delete_record(record_id)
                st.session_state.delete_complete = True
                st.rerun()
        with col_c2:
            if st.button("❌ No, Cancel"):
                st.session_state.confirm_delete = False
                st.rerun()
