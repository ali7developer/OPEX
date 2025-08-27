# pages/monitor.py
import re
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from pages.edit_budget import render_edit_page
from utils.style import apply_global_styles
from pages.components import render_footer

# =========================================
# Page Config & Global Styles
# =========================================
st.set_page_config(page_title="OPEX Budget Monitor", layout="wide")
apply_global_styles()

# =========================================
# Helpers
# =========================================
def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Lower/strip headers and collapse whitespace once."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str).str.strip().str.lower()
          .str.replace(r"\s+", " ", regex=True)
    )
    return df

ALIASES = {
    "pr_number": ["pr number", "pr_number", "pr no", "pr"],
    "year": ["year"],  # not used directly; years come from header names
    "directorate": ["directorate", "dir", "directorate name"],
    "department": ["department", "dept", "domain"],

    # Account fields (either can be provided)
    "account_no":   ["account no", "account number", "gl code", "gl#", "acc no", "acc#", "gl"],
    "account_name": ["account", "account name", "gl name", "name_en", "account description"],

    "expense_type": ["expense type", "expense", "type of expense"],
    "c_code": ["c code", "c_code", "c-code", "ccode"],

    # Cost center (Excel) -> cost_center
    "cost_center": ["cost center", "cost_center", "costcentre"],

    # Excel: "Sub-Category" -> sub_category
    "sub_category": ["sub-category", "sub category", "subcategory", "sub_category"],

    # Excel: "Risk" -> risk_comment
    "risk_comment": ["risk", "risk comment", "risk_comment"],

    # Excel: "Procueremnt comment" (intentional spelling) -> procueremnt_comment
    "procueremnt_comment": ["procueremnt comment", "procurement comment", "procurement_comment"],

    # Excel: "Other" -> other
    "other": ["other"],

    "line_budget": ["line budget", "line_budget"],
    "vendor": ["vendor", "vendor name"],
    "ifrs_16": ["ifrs 16", "ifrs_16"],
    "email": ["email", "contact email"],
    "mobile": ["mobile", "phone", "contact mobile"],

    # Dates (dd-mm-yyyy / dd/mm/yyyy)
    "start_date": ["start", "start date", "start_date", "contract start date", "contract start", "valid from", "from date", "from"],
    "end_date":   ["end", "end date", "end_date", "contract end date", "contract end", "expiry date", "expiration date", "valid to", "to date", "to"],

    "type_of_cost": ["type of cost", "type_of_cost"],
    "type_of_amc":  ["type of amc", "type_of_amc"],
    "remarks":      ["remarks", "notes", "comment"],
    "cvd_status":   ["cvd status", "cvd_status"],
    "quotation_received": ["quotation received", "quotation_received", "quote received"],

    # No generic "amount" by design
    "unit_cost": ["unit cost", "unit price"],

    # Excel "Case" -> status_master.name_en (category='case')
    "status_name": ["case", "status", "case status"],
}

def _pick(row: dict, key: str, default=None):
    """Pick a value from a row dict using known aliases for key."""
    for name in ALIASES.get(key, []):
        if name in row:
            val = row[name]
            if pd.isna(val):
                return default
            return val
    return default

def _to_float(v, default=None):
    try:
        if v is None or v == "" or pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default

def _to_bool(v, default=0):
    if isinstance(v, (int, float)) and v in (0, 1):
        return int(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("yes", "y", "true", "1"):
            return 1
        if s in ("no", "n", "false", "0"):
            return 0
    return default

def _to_date_str(v):
    """
    Return ISO date string (YYYY-MM-DD) or None.
    Prefers dd/mm/yyyy and dd-mm-yyyy, supports ISO/other formats,
    pandas/py datetimes, and Excel serial numbers.
    """
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    if not isinstance(v, str) and pd.isna(v):
        return None

    if isinstance(v, (pd.Timestamp, datetime)):
        try:
            return pd.to_datetime(v).date().isoformat()
        except Exception:
            pass

    s = str(v).strip()

    # Prefer day-first (covers dd-mm-yyyy, dd/mm/yyyy)
    try:
        dt = pd.to_datetime(s, errors="raise", dayfirst=True, infer_datetime_format=True)
        return dt.date().isoformat()
    except Exception:
        pass

    # Try default
    try:
        dt = pd.to_datetime(s, errors="raise", dayfirst=False)
        return dt.date().isoformat()
    except Exception:
        pass

    # Excel serials
    try:
        if isinstance(v, (int, float)) or s.replace(".", "", 1).isdigit():
            num = float(v)
            if 1 <= num <= 80000:
                dt = pd.to_datetime(num, unit="D", origin="1899-12-30", errors="raise")
                return dt.date().isoformat()
    except Exception:
        pass

    return None

def _find_col(cols, patterns):
    """Return the first column name matching any regex pattern."""
    for c in cols:
        for p in patterns:
            if re.search(p, c):
                return c
    return None

# =========================================
# Excel → DB Import (wide → normalized)
# =========================================
def insert_excel_data(df_in: pd.DataFrame):
    """
    - Detect years from headers.
    - Normalize per (pr_number, year).
    - UPSERT amc_contracts on (pr_number, year).
    - Insert amc_pos rows per (pr_number, year).
    - Department → ref_departments; fallback by directorate.
    - Account number OR name → ref_account.
    - Excel Case/Status → ref_status via status_master (category='case').
    - Maps: cost_center, sub_category, risk_comment, procueremnt_comment, other.
    - Dates parsed day-first; supports dd-mm-yyyy / dd/mm/yyyy / Excel serials.
    - “Approved Budget {YEAR}” → approved_budget; budget_year = {YEAR}; approved flag from approved_budget.
    """
    df = _normalize_headers(df_in)

    conn = sqlite3.connect("opex.db", timeout=10)
    cur = conn.cursor()

    # Reference maps
    dept_map = pd.read_sql("SELECT id, name_en, directorate FROM departments", conn)
    account_map = pd.read_sql("SELECT id, account, name_en FROM accounts", conn)
    try:
        status_map = pd.read_sql("SELECT id, name_en FROM status_master WHERE category='case'", conn)
        status_map["name_fold"] = status_map["name_en"].astype(str).str.strip().str.casefold()
    except Exception:
        status_map = pd.DataFrame(columns=["id", "name_en", "name_fold"])

    # DB cols
    table_info = pd.read_sql("PRAGMA table_info(amc_contracts)", conn)
    valid_cols = set(table_info["name"].tolist())

    cols = df.columns.tolist()

    # Years detected in headers
    detected_years = sorted({int(y) for c in cols for y in re.findall(r"\b(20[0-9]{2})\b", c)})

    # Identify per-year columns
    budget_cols = {}            # e.g., "2025 Budget" or "Budget Approval 2025"
    units_cols = {}
    po_amount_cols = {}
    po_number_cols = {}
    approval_budget_cols = {}   # “Approved Budget 2025” / “Approval Budget 2025”
    unit_cost_col = _find_col(cols, [r"^unit cost$", r"^unit price$"])

    for y in detected_years:
        budget_cols[y] = _find_col(
            cols, [fr"^{y}\s*budget(\s*\(.*\))?$", fr"^budget\s*approval\s*{y}(\s*\(.*\))?$", fr"^{y}.*budget(\s*\(.*\))?$"]
        )
        units_cols[y] = _find_col(cols, [fr"^{y}\s*units$"])
        po_amount_cols[y] = _find_col(cols, [fr"^{y}\s*po.*\(omr\)", fr"^{y}\s*po\s*/\s*pr\(omr\)", fr"^{y}.*po.*\(omr\)"])
        po_number_cols[y] = _find_col(cols, [fr"^{y}\s*po#?$", fr"^{y}\s*po number$", fr"^{y}.*po#"])
        approval_budget_cols[y] = _find_col(
            cols, [
                fr"^approved\s*budget\s*{y}(\s*\(.*\))?$",
                fr"^{y}\s*approved\s*budget(\s*\(.*\))?$",
                fr"^approval\s*budget\s*{y}(\s*\(.*\))?$",
                fr"^{y}\s*approval\s*budget(\s*\(.*\))?$"
            ]
        )

    success_contracts, success_pos = 0, 0

    for i, row in df.iterrows():
        r = row.to_dict()

        # Department by name; fallback directorate
        dept_id = None
        dept_val = _pick(r, "department")
        directorate_val = _pick(r, "directorate")
        if dept_val:
            m = dept_map.loc[
                dept_map["name_en"].astype(str).str.strip().str.lower() == str(dept_val).strip().lower(), "id"
            ]
            if not m.empty:
                dept_id = int(m.iloc[0])
        if dept_id is None and directorate_val:
            m = dept_map.loc[
                dept_map["directorate"].astype(str).str.strip().str.lower() == str(directorate_val).strip().lower(), "id"
            ]
            if not m.empty:
                dept_id = int(m.iloc[0])

        # Account by number or name
        account_id = None
        acc_no   = _pick(r, "account_no")
        acc_name = _pick(r, "account_name")

        acc_df = account_map.copy()
        acc_df["account_str"] = acc_df["account"].astype(str).str.strip()
        acc_df["name_str"]    = acc_df["name_en"].astype(str).str.strip()
        acc_df["name_fold"]   = acc_df["name_str"].str.casefold()

        if acc_no not in (None, ""):
            m = acc_df.loc[acc_df["account_str"] == str(acc_no).strip(), "id"]
            if not m.empty:
                account_id = int(m.iloc[0])
        if account_id is None and acc_name not in (None, ""):
            name_key = str(acc_name).strip().casefold()
            m = acc_df.loc[acc_df["name_fold"] == name_key, "id"]
            if not m.empty:
                account_id = int(m.iloc[0])

        # Case/Status → ref_status
        ref_status_id = None
        case_text = _pick(r, "status_name")
        if case_text and not status_map.empty:
            key = str(case_text).strip().casefold()
            m = status_map.loc[status_map["name_fold"] == key, "id"]
            if not m.empty:
                ref_status_id = int(m.iloc[0])

        pr_number = _pick(r, "pr_number")
        if not pr_number:
            st.error(f"Row {i+1}: Missing PR Number. Skipped.")
            continue

        unit_cost = _to_float(_pick(r, "unit_cost"))

        for y in detected_years:
            # approval_amount for (PR, Year)
            amt = None
            if budget_cols.get(y):
                amt = r.get(budget_cols[y], None)
            if (amt is None or pd.isna(amt)) and (units_cols.get(y)) and unit_cost is not None:
                units_val = r.get(units_cols[y], None)
                if units_val is not None and not pd.isna(units_val):
                    try:
                        amt = float(units_val) * float(unit_cost)
                    except Exception:
                        pass

            # Skip if no signal for this year
            has_signal = (
                (budget_cols.get(y) and pd.notna(r.get(budget_cols[y], None))) or
                (units_cols.get(y) and pd.notna(r.get(units_cols[y], None))) or
                (po_amount_cols.get(y) and pd.notna(r.get(po_amount_cols[y], None))) or
                (po_number_cols.get(y) and pd.notna(r.get(po_number_cols[y], None))) or
                (approval_budget_cols.get(y) and pd.notna(r.get(approval_budget_cols[y], None)))
            )
            if not has_signal:
                continue

            # Approved Budget & Budget Year
            approved_budget_val = None
            budget_year_val = None
            if approval_budget_cols.get(y):
                approved_budget_val = _to_float(r.get(approval_budget_cols[y], None))
                if approved_budget_val is not None:
                    budget_year_val = y

            payload = {
                "pr_number": pr_number,
                "year": y,
                "ref_departments": dept_id,
                "ref_account": account_id,
                "ref_status": ref_status_id,
                "expense_type": _pick(r, "expense_type"),
                "approval_amount": _to_float(amt),
                "c_code": _pick(r, "c_code"),
                "cost_center": _pick(r, "cost_center"),
                "line_budget": _pick(r, "line_budget"),
                "vendor": _pick(r, "vendor"),
                "sub_category": _pick(r, "sub_category"),
                "ifrs_16": _pick(r, "ifrs_16"),
                "email": _pick(r, "email"),
                "mobile": _pick(r, "mobile"),
                "start_date": _to_date_str(_pick(r, "start_date")),
                "end_date": _to_date_str(_pick(r, "end_date")),
                "type_of_cost": _pick(r, "type_of_cost"),
                "type_of_amc": _pick(r, "type_of_amc"),
                "remarks": _pick(r, "remarks"),
                "cvd_status": _pick(r, "cvd_status"),
                "risk_comment": _pick(r, "risk_comment"),
                "procueremnt_comment": _pick(r, "procueremnt_comment"),
                "other": _pick(r, "other"),
                "approved_budget": approved_budget_val,
                "budget_year": budget_year_val,
                "quotation_received": _to_bool(_pick(r, "quotation_received"), default=0),
                "approved": 1 if approved_budget_val is not None else 0,
                "created": datetime.now().isoformat(timespec="seconds"),
                "created_by": "admin",
                "modified": datetime.now().isoformat(timespec="seconds"),
                "modified_by": "admin",
                "version": 1,
            }

            # UPSERT on (pr_number, year)
            upsert_cols = [c for c in payload.keys() if c in valid_cols]
            placeholders = ",".join(["?"] * len(upsert_cols))
            assignments = ", ".join([f"{c}=excluded.{c}" for c in upsert_cols if c not in ("pr_number", "year")])

            sql = f"""
            INSERT INTO amc_contracts ({", ".join(upsert_cols)})
            VALUES ({placeholders})
            ON CONFLICT(pr_number, year) DO UPDATE SET
            {assignments}
            """
            try:
                cur.execute(sql, [payload[c] for c in upsert_cols])
                conn.commit()
                success_contracts += 1
            except Exception as e:
                conn.rollback()
                st.error(f"PR {pr_number} - Year {y}: Contract upsert failed. {e}")

            # Insert PO row for that year if present
            po_no_val = r.get(po_number_cols.get(y, ""), None)
            po_amt_val = r.get(po_amount_cols.get(y, ""), None)
            if (po_no_val is not None and not pd.isna(po_no_val)) or (po_amt_val is not None and not pd.isna(po_amt_val)):
                try:
                    cur.execute("""
                        INSERT INTO amc_pos
                            (pr_number, year, po_number, po_amount, created, created_by, modified, modified_by, version)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pr_number, y,
                        None if pd.isna(po_no_val) else str(po_no_val),
                        None if pd.isna(po_amt_val) else _to_float(po_amt_val),
                        datetime.now().isoformat(timespec="seconds"), "admin",
                        datetime.now().isoformat(timespec="seconds"), "admin", 1
                    ))
                    conn.commit()
                    success_pos += 1
                except Exception as e:
                    conn.rollback()
                    st.error(f"PR {pr_number} - Year {y}: PO insert failed. {e}")

    conn.close()
    st.success(f"✅ Import complete: {success_contracts} contract upserts, {success_pos} PO rows.")

# =========================================
# Main App
# =========================================
def main():
    query_params = st.query_params
    if "id" in query_params:
        try:
            render_edit_page(int(query_params["id"]))
            return
        except Exception:
            try:
                render_edit_page(int(query_params.get("id")[0]))
                return
            except Exception:
                st.error("Invalid edit id")

    st.title("📋 All OPEX Budget Records")

    # --- Top Buttons (Add New) + Excel Uploader ---
    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.markdown("""
        <style>
        .border-btn {
            border: 2px solid #4CAF50;
            border-radius: 6px;
            padding: 10px 16px;
            text-decoration: none;
            color: black;
            font-weight: 600;
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
            st.success("File uploaded successfully! Preview below:")
            st.dataframe(df_excel.head(10), use_container_width=True)
            if st.button("📤 Import to Database"):
                insert_excel_data(df_excel)
        except Exception as e:
            st.error(f"Error reading file: {e}")

    # --- Load data for list view ---
    conn = sqlite3.connect("opex.db", timeout=10)

    df = pd.read_sql_query("""
        SELECT 
            ac.id,
            d.name_en AS Department,
            a.account AS "Account No",
            a.name_en AS Account,
            ac.pr_number,
            ac.year,
            ac.c_code,
            ac.expense_type,
            ac.cost_center,
            ac.approval_amount AS Amount,
            ac.approved_budget,
            ac.budget_year,
            CASE WHEN ac.approved = 1 THEN "Yes" ELSE "No" END AS Approved,
            ac.line_budget,
            ac.vendor,
            ac.sub_category,
            ac.ifrs_16,
            ac.email,
            ac.mobile,
            ac.start_date,
            ac.end_date,
            ac.type_of_cost,
            ac.type_of_amc,
            ac.remarks,
            ac.cvd_status,
            ac.risk_comment AS Comment,
            ac.procueremnt_comment,
            ac.other,
            ac.quotation_received,
            s.name_en AS Status,
            ac.created
        FROM amc_contracts ac 
        LEFT JOIN departments d ON ac.ref_departments = d.id
        LEFT JOIN accounts a ON ac.ref_account = a.id
        LEFT JOIN status_master s ON ac.ref_status = s.id
        ORDER BY ac.pr_number, ac.year
    """, conn)

    # Latest PO PER (pr_number, year)
    po_df = pd.read_sql_query("""
        WITH latest AS (
            SELECT pr_number, year, MAX(id) AS max_id
            FROM amc_pos
            GROUP BY pr_number, year
        )
        SELECT c.id,
               p.po_number AS "PO Number",
               p.po_amount AS "PO Amount"
        FROM amc_contracts c
        LEFT JOIN latest l
          ON l.pr_number = c.pr_number AND l.year = c.year
        LEFT JOIN amc_pos p
          ON p.id = l.max_id
    """, conn)

    # Attachments (optional)
    att_df = pd.read_sql_query("""
        SELECT ref_id AS id,
               COUNT(*) AS attachment_count
        FROM attachment
        WHERE table_name = 'amc_contracts'
        GROUP BY ref_id
    """, conn)

    att_rows = pd.read_sql_query("""
        SELECT ref_id AS id, filename, path
        FROM attachment
        WHERE table_name = 'amc_contracts'
        ORDER BY id, filename, path
    """, conn)
    conn.close()

    # Merge POs and attachments count
    df = df.merge(po_df, on="id", how="left")
    df = df.merge(att_df, on="id", how="left")
    df.rename(columns={"attachment_count": "Attachments"}, inplace=True)
    df["Attachments"] = df["Attachments"].fillna(0).astype(int)

    # Build per-record attachments map (deduped)
    attachments_map = {}
    if not att_rows.empty:
        for rid, sub in att_rows.groupby("id", sort=False):
            seen = set()
            unique = []
            for rec in sub[["filename", "path"]].to_dict("records"):
                key = (rec["filename"], rec["path"])
                if key in seen:
                    continue
                seen.add(key)
                unique.append(rec)
            attachments_map[int(rid)] = unique

    # --- Filters ---
    st.subheader("🔍 Filter Records")
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)
    col7, = st.columns(1)

    with col1:
        pr_search = st.text_input("PR Number")
    with col2:
        dept_search = st.selectbox(
            "Department",
            options=[""] + sorted(df["Department"].dropna().unique().tolist())
        )
    with col3:
        year_search = st.text_input("Year")

    with col4:
        vendor_search = st.text_input("Vendor")
    with col5:
        status_search = st.selectbox(
            "Status",
            options=[""] + sorted(df["Status"].dropna().unique().tolist())
        )
    with col6:
        account_no_search = st.text_input("Account No")

    with col7:
        po_search = st.text_input("PO Number")

    work_df = df.copy()
    if pr_search:
        work_df = work_df[work_df["pr_number"].astype(str).str.contains(pr_search.strip(), case=False)]
    if dept_search:
        work_df = work_df[work_df["Department"] == dept_search]
    if year_search:
        work_df = work_df[work_df["year"].astype(str).str.contains(year_search.strip(), case=False)]
    if vendor_search:
        work_df = work_df[work_df["vendor"].str.contains(vendor_search.strip(), case=False, na=False)]
    if status_search:
        work_df = work_df[work_df["Status"] == status_search]
    if account_no_search:
        work_df = work_df[work_df["Account No"].astype(str).str.contains(account_no_search.strip(), case=False)]

    # PO filter: any PO rows map back to contracts
    if po_search:
        conn = sqlite3.connect("opex.db", timeout=10)
        ids_by_po = pd.read_sql_query("""
            SELECT DISTINCT c.id
            FROM amc_pos p
            JOIN amc_contracts c
              ON c.pr_number = p.pr_number AND c.year = p.year
            WHERE p.po_number LIKE ?
        """, conn, params=(f"%{po_search.strip()}%",))
        conn.close()
        id_set = set(ids_by_po["id"].tolist()) if not ids_by_po.empty else set()
        work_df = work_df[work_df["id"].isin(id_set)]

    # --- Export CSV ---
    csv_data = work_df.drop(columns=["id"]).to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export to CSV",
        data=csv_data,
        file_name="opex_budget_filtered.csv",
        mime="text/csv"
    )

    # --- Pagination (15 per page) ---
    PAGE_SIZE = 15

    # Build a signature of current filters to reset page when filters change
    filter_sig = "|".join([
        str(pr_search or ""), str(dept_search or ""), str(year_search or ""),
        str(vendor_search or ""), str(status_search or ""), str(account_no_search or ""),
        str(po_search or "")
    ])
    if "list_page" not in st.session_state:
        st.session_state["list_page"] = 1
    if "list_sig" not in st.session_state:
        st.session_state["list_sig"] = filter_sig
    if st.session_state["list_sig"] != filter_sig:
        st.session_state["list_sig"] = filter_sig
        st.session_state["list_page"] = 1  # reset to first page on filter change

    total_rows = len(work_df)
    total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)

    # Clamp current page
    cur_page = max(1, min(st.session_state["list_page"], total_pages))
    st.session_state["list_page"] = cur_page

    # Slice dataframe for current page
    start_idx = (cur_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_df = work_df.iloc[start_idx:end_idx].copy()

    # --- Render current page rows ---
    st.divider()
    if page_df.empty:
        st.warning("No matching records found.")
    else:
        display_cols = [
            "Department", "Account No", "Account",
            "pr_number", "year", "PO Number", "PO Amount",
            "c_code", "expense_type", "cost_center",
            "Amount", "approved_budget", "budget_year", "Approved",
            "line_budget", "vendor", "sub_category", "ifrs_16", "email", "mobile",
            "start_date", "end_date", "type_of_cost", "type_of_amc",
            "remarks", "cvd_status", "Comment", "procueremnt_comment", "other",
            "Status", "created"
        ]

        for _, row in page_df.iterrows():
            row_display = row[display_cols].to_frame().T
            with st.container():
                st.dataframe(row_display, hide_index=True, use_container_width=True)

                files = attachments_map.get(int(row["id"]), [])
                with st.expander(f"📎 Attachments ({len(files)})"):
                    if not files:
                        st.caption("No attachments.")
                    else:
                        for i, fmeta in enumerate(files, start=1):
                            fname = fmeta["filename"]
                            fpath = fmeta["path"]
                            cols = st.columns([4, 1])
                            with cols[0]:
                                st.write(fname)
                            with cols[1]:
                                try:
                                    with open(fpath, "rb") as fh:
                                        st.download_button(
                                            label="Download",
                                            data=fh.read(),
                                            file_name=fname,
                                            mime=None,
                                            key=f"dl_{int(row['id'])}_{i}"
                                        )
                                except FileNotFoundError:
                                    st.error("File missing on disk.")

                edit_url = f"?id={row['id']}"
                st.markdown(f"<a href='{edit_url}' target='_self'>✏️ Edit</a>", unsafe_allow_html=True)

    # --- Bottom pager controls ---
    st.divider()
    b1, b2, b3 = st.columns([1, 2, 1])
    with b1:
        if st.button("⬅️ Prev", disabled=(cur_page <= 1), key="btn_prev"):
            st.session_state["list_page"] = cur_page - 1
            st.rerun()
    with b2:
        st.markdown(
            f"<div style='text-align:center; font-weight:600;'>"
            f"Page {cur_page} of {total_pages} • Showing {len(page_df)} of {total_rows} records"
            f"</div>",
            unsafe_allow_html=True
        )
    with b3:
        if st.button("Next ➡️", disabled=(cur_page >= total_pages), key="btn_next"):
            st.session_state["list_page"] = cur_page + 1
            st.rerun()

if __name__ == "__main__":
    main()
    render_footer()
