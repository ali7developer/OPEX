import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

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

def render_edit_page(record_id):
    st.title("✏️ Edit OPEX Budget Record")

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
                st.rerun()
        with col2:
            if st.button("🏠 Go to Home", key="home_after_delete"):
                st.session_state.delete_complete = False
                st.query_params.clear()
                st.switch_page("Home")
        return

    conn = sqlite3.connect("opex.db")
    df = pd.read_sql_query(f"SELECT * FROM amc_contracts WHERE id = {record_id}", conn)
    conn.close()

    if df.empty:
        st.error("Record not found.")
        return

    row = df.iloc[0]
    with st.form("edit_form"):
        pr_number = st.text_input("PR Number", row["pr_number"])
        domain = st.text_input("Domain", row["domain"])
        c_code = st.text_input("C Code", row["c_code"])
        expense_type = st.text_input("Expense Type", row["expense_type"])
        cost_center = st.text_input("Cost Center", row["cost_center"])
        approval_amount = st.number_input("Approval Amount", value=row["approval_amount"])
        approved = st.selectbox("Approved", [0, 1], index=[0, 1].index(row["approved"]))
        contract_reference = st.text_input("Contract Reference", row["contract_reference"])
        line_budget = st.text_input("Line Budget", row["line_budget"])
        vendor = st.text_input("Vendor", row["vendor"])
        sub_category = st.text_input("Sub Category", row["sub_category"])
        ifrs_16 = st.text_input("IFRS 16", row["ifrs_16"])
        email = st.text_input("Email", row["email"])
        mobile = st.text_input("Mobile", row["mobile"])
        start_date = st.date_input("Start Date", pd.to_datetime(row["start_date"]))
        end_date = st.date_input("End Date", pd.to_datetime(row["end_date"]))
        year = st.number_input("Year", value=row["year"], step=1)
        type_of_cost = st.text_input("Type of Cost", row["type_of_cost"])
        type_of_amc = st.text_input("Type of AMC", row["type_of_amc"])
        remarks = st.text_area("Remarks", row["remarks"])
        cvd_status = st.text_input("CVD Status", row["cvd_status"])
        risk_comment = st.text_area("Risk Comment", row["risk_comment"])
        procurement_comment = st.text_area("Procurement Comment", row["procurement_comment"])
        quotation_received = st.selectbox("Quotation Received", [0, 1], index=[0, 1].index(row["quotation_received"]))
        ref_departments = st.number_input("Ref Departments", value=row["ref_departments"], step=1)
        ref_account = st.number_input("Ref Account", value=row["ref_account"], step=1)
        ref_status = st.number_input("Ref Status", value=row["ref_status"], step=1)

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Save Changes")
        with col2:
            delete_clicked = st.form_submit_button("❌ Delete Record")

    if submitted:
        form_data = {
            "pr_number": pr_number,
            "domain": domain,
            "c_code": c_code,
            "expense_type": expense_type,
            "cost_center": cost_center,
            "approval_amount": approval_amount,
            "approved": approved,
            "contract_reference": contract_reference,
            "line_budget": line_budget,
            "vendor": vendor,
            "sub_category": sub_category,
            "ifrs_16": ifrs_16,
            "email": email,
            "mobile": mobile,
            "start_date": start_date,
            "end_date": end_date,
            "year": year,
            "type_of_cost": type_of_cost,
            "type_of_amc": type_of_amc,
            "remarks": remarks,
            "cvd_status": cvd_status,
            "risk_comment": risk_comment,
            "procurement_comment": procurement_comment,
            "quotation_received": quotation_received,
            "ref_departments": ref_departments,
            "ref_account": ref_account,
            "ref_status": ref_status
        }
        update_record(record_id, form_data)
        st.success("Record updated successfully.")
        st.markdown("[🔙 Back to Monitor](/Monitor)", unsafe_allow_html=True)

    if delete_clicked:
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
