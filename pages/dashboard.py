import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io
from datetime import datetime

APPROVED_OPTIONS = {
    "Yes": [1],
    "No": [0],
    "All": [0, 1],
}

# ---------- Bigger, consistent sizing & fonts ----------
FIGSIZE = (16, 9.8)        # first 4 charts: identical size
LAST_FIGSIZE = (22, 11.2)  # last chart: larger
DPI = 150                  # crisp text

plt.rcParams.update({
    "figure.dpi": DPI,
    "font.size": 13,
    "axes.titlesize": 18,
    "axes.labelsize": 15,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
})

def _fmt_number(n):
    try:
        return f"{float(n):,.0f}"
    except Exception:
        return str(n)

def _add_bar_labels(ax, rects, fmt=str):
    for r in rects:
        h = r.get_height()
        if h is None:
            continue
        ax.annotate(
            fmt(h),
            xy=(r.get_x() + r.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=12
        )

def _standardize_margins(fig):
    """Force identical margins for the first four charts."""
    fig.subplots_adjust(left=0.08, right=0.97, top=0.90, bottom=0.30)

def _multiselect_with_all(label, options):
    """Multiselect that includes 'All' (default); returns [] when All/no selection (i.e., no filter)."""
    opts = ["All"] + options
    sel = st.multiselect(label, opts, default=["All"])
    if ("All" in sel) or (len(sel) == 0):
        return []
    return sel

def _build_base_cte(selected_years, approved_values, dept_sel, vendor_sel, account_sel, status_sel):
    """
    Build a 'WITH base AS (...)' CTE string and param list that apply all filters.
    Empty lists mean 'no filter' for that field.
    """
    year_ph = ",".join(["?"] * len(selected_years))
    app_ph  = ",".join(["?"] * len(approved_values))

    conditions = [f"ac.year IN ({year_ph})", f"ac.approved IN ({app_ph})"]
    params = list(selected_years) + list(approved_values)

    if dept_sel:
        dept_ph = ",".join(["?"] * len(dept_sel))
        conditions.append(f"d.name_en IN ({dept_ph})")
        params += list(dept_sel)

    if vendor_sel:
        ven_ph = ",".join(["?"] * len(vendor_sel))
        conditions.append(f"ac.vendor IN ({ven_ph})")
        params += list(vendor_sel)

    if account_sel:
        acc_ph = ",".join(["?"] * len(account_sel))
        conditions.append(f"a.name_en IN ({acc_ph})")
        params += list(account_sel)

    if status_sel:
        st_ph = ",".join(["?"] * len(status_sel))
        conditions.append(f"s.name_en IN ({st_ph})")
        params += list(status_sel)

    where_sql = " AND ".join(conditions)

    base_cte = f"""
    WITH base AS (
      SELECT
        ac.id,
        ac.pr_number       AS PRNumber,
        ac.year,
        ac.approval_amount,
        ac.approved        AS ApprovedFlag,
        d.name_en          AS Department,
        ac.vendor          AS VendorName,
        a.name_en          AS AccountName,
        s.name_en          AS StatusName
      FROM amc_contracts ac
      LEFT JOIN departments   d ON d.id = ac.ref_departments
      LEFT JOIN accounts      a ON a.id = ac.ref_account
      LEFT JOIN status_master s ON s.id = ac.ref_status
      WHERE {where_sql}
    )
    """
    return base_cte, params

def main():
    st.title("📊 AMC Contracts – Spending by Department")

    # --- Connect once for options + first query ---
    conn = sqlite3.connect("opex.db")

    # --- Options for filters ---
    years = pd.read_sql_query("SELECT DISTINCT year FROM amc_contracts ORDER BY year DESC", conn)["year"].tolist()
    if not years:
        st.info("No years found in the database.")
        conn.close()
        return

    dept_options = pd.read_sql_query("SELECT name_en FROM departments ORDER BY name_en", conn)["name_en"].tolist()
    vendor_options = pd.read_sql_query(
        "SELECT DISTINCT vendor FROM amc_contracts WHERE vendor IS NOT NULL AND TRIM(vendor) <> '' ORDER BY vendor",
        conn
    )["vendor"].tolist()
    account_options = pd.read_sql_query("SELECT name_en FROM accounts ORDER BY name_en", conn)["name_en"].tolist()
    status_options = pd.read_sql_query(
        "SELECT name_en FROM status_master WHERE category='case' ORDER BY name_en",
        conn
    )["name_en"].tolist()

    # --- Filters: Year + Approved ---
    selected_years = st.multiselect("Select Year(s)", years, default=years)
    if not selected_years:
        st.warning("Please select at least one year.")
        conn.close()
        return

    approved_choice = st.selectbox("Approved", list(APPROVED_OPTIONS.keys()), index=0)
    approved_values = APPROVED_OPTIONS[approved_choice]

    # --- New filters with 'All' as default ---
    c1, c2 = st.columns(2)
    with c1:
        dept_sel   = _multiselect_with_all("Department", dept_options)   # [] => All
        vendor_sel = _multiselect_with_all("Vendor", vendor_options)     # [] => All
    with c2:
        account_sel = _multiselect_with_all("Account", account_options)  # [] => All
        status_sel  = _multiselect_with_all("Status", status_options)    # [] => All

    # --- Base CTE for all queries ---
    base_cte, base_params = _build_base_cte(
        selected_years, approved_values, dept_sel, vendor_sel, account_sel, status_sel
    )

    # ========= Detailed table with extra columns =========
    q_table = base_cte + """
        SELECT
          Department,
          AccountName                 AS Account,
          COALESCE(StatusName,'Unknown') AS Status,
          VendorName                  AS Vendor,
          CASE WHEN ApprovedFlag = 1 THEN 'Yes' ELSE 'No' END AS Approved,
          year                        AS Year,
          approval_amount             AS Approval_OMR
        FROM base
        ORDER BY Year DESC, Department, Account
    """
    table_df = pd.read_sql_query(q_table, conn, params=base_params)

    st.subheader(
        f"Contracts (filtered) | Years: {', '.join(map(str, selected_years))} | Approved: {approved_choice}"
    )
    if table_df.empty:
        st.info("No data matches the selected filters.")
        conn.close()
        return

    st.dataframe(table_df, use_container_width=True)

    # Export this detailed table
    csv_bytes = table_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export table to CSV",
        data=csv_bytes,
        file_name=f"contracts_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

    # ========= Aggregated data for charts 0/1 =========
    q_spend = base_cte + """
        SELECT Department, SUM(approval_amount) AS Spending_OMR, year AS Year
        FROM base
        GROUP BY Department, year
        ORDER BY Spending_OMR DESC, year
    """
    df = pd.read_sql_query(q_spend, conn, params=base_params)

    if df.empty:
        st.warning("No aggregated spending data for the current filters.")
        conn.close()
        return

    # -------------------------
    # Build all figures first
    # -------------------------

    # 0) Total Spending by Department (aggregated across selected years)
    agg = df.groupby("Department", as_index=False)["Spending_OMR"].sum()
    fig0, ax0 = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    if agg.empty:
        bars0 = []
    else:
        bars0 = ax0.bar(agg["Department"], agg["Spending_OMR"])
    ax0.set_xlabel("Department")
    ax0.set_ylabel("Spending (OMR)")
    ax0.set_title("Total Spending by Department")
    plt.xticks(rotation=45, ha="right")
    _add_bar_labels(ax0, bars0, _fmt_number)
    _standardize_margins(fig0)

    # 1) Stacked bar: Spending by Department split by Year (legend INSIDE)
    pivot = df.pivot_table(index="Department", columns="Year", values="Spending_OMR", aggfunc="sum", fill_value=0)
    fig1, ax1 = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    if not pivot.empty:
        pivot = pivot.sort_values(pivot.columns.tolist(), ascending=False)
        years_sorted = sorted(pivot.columns)
        cumulative = None
        for y in years_sorted:
            vals = pivot[y].values
            if cumulative is None:
                ax1.bar(pivot.index, vals, label=str(y))
                cumulative = vals.copy()
            else:
                ax1.bar(pivot.index, vals, bottom=cumulative, label=str(y))
                cumulative = cumulative + vals
        for idx, dept in enumerate(pivot.index):
            ax1.annotate(
                _fmt_number(cumulative[idx]),
                xy=(idx, cumulative[idx]),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=12
            )
    ax1.set_xlabel("Department")
    ax1.set_ylabel("Spending (OMR)")
    ax1.set_title("Total Spending by Department (stacked by Year)")
    plt.xticks(rotation=45, ha="right")
    ax1.legend(title="Year", loc="upper left", frameon=False)
    _standardize_margins(fig1)

    # 2) Contracts by Status (counts) — filtered via base
    q_status = base_cte + """
        SELECT COALESCE(StatusName, 'Unknown') AS Status, COUNT(*) AS Count
        FROM base
        GROUP BY COALESCE(StatusName, 'Unknown')
        ORDER BY Count DESC
    """
    df_status = pd.read_sql_query(q_status, conn, params=base_params)

    fig2, ax2 = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    if not df_status.empty:
        bars2 = ax2.bar(df_status["Status"], df_status["Count"])
        _add_bar_labels(ax2, bars2, _fmt_number)
    ax2.set_xlabel("Status")
    ax2.set_ylabel("Contracts")
    ax2.set_title("Contracts by Status")
    plt.xticks(rotation=45, ha="right")
    _standardize_margins(fig2)

    # 3) PO Coverage by Department — join via PRNumber+year (no ref_amc_contract)
    q_cov = base_cte + """
        , po AS (
            SELECT DISTINCT pr_number, year
            FROM amc_pos
        )
        SELECT b.Department,
               SUM(CASE WHEN po.pr_number IS NOT NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS coverage_ratio
        FROM base b
        LEFT JOIN po
          ON po.pr_number = b.PRNumber AND po.year = b.year
        GROUP BY b.Department
        ORDER BY coverage_ratio DESC
    """
    df_cov = pd.read_sql_query(q_cov, conn, params=base_params)

    fig3, ax3 = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    if not df_cov.empty:
        df_cov["coverage_pct"] = (df_cov["coverage_ratio"] * 100).round(1)
        bars3 = ax3.bar(df_cov["Department"], df_cov["coverage_pct"])
        _add_bar_labels(ax3, bars3, lambda x: f"{x:.1f}%")
    ax3.set_xlabel("Department")
    ax3.set_ylabel("Coverage (%)")
    ax3.set_title("PO Coverage by Department")
    plt.xticks(rotation=45, ha="right")
    _standardize_margins(fig3)

    # 4) Approved vs PO Amount by Department — join via PRNumber+year (no ref_amc_contract)
    q_app = base_cte + """
        SELECT Department, SUM(approval_amount) AS Approved_OMR
        FROM base
        GROUP BY Department
    """
    df_app = pd.read_sql_query(q_app, conn, params=base_params)

    q_po = base_cte + """
        , latest_po AS (
          SELECT ap.*
          FROM amc_pos ap
          JOIN (
            SELECT pr_number, year, MAX(id) AS max_id
            FROM amc_pos
            GROUP BY pr_number, year
          ) t ON ap.id = t.max_id
        )
        SELECT b.Department, SUM(lp.po_amount) AS PO_OMR
        FROM latest_po lp
        JOIN base b
          ON b.PRNumber = lp.pr_number AND b.year = lp.year
        GROUP BY b.Department
    """
    df_po = pd.read_sql_query(q_po, conn, params=base_params)

    # Close connection; we have all data needed
    conn.close()

    df_gap = pd.merge(df_app, df_po, on="Department", how="outer").fillna(0)
    fig4, ax4 = plt.subplots(figsize=LAST_FIGSIZE, dpi=DPI)
    if not df_gap.empty:
        df_gap = df_gap.sort_values("Approved_OMR", ascending=False)
        x = range(len(df_gap))
        width = 0.4
        bars4a = ax4.bar([i - width/2 for i in x], df_gap["Approved_OMR"], width=width, label="Approved")
        bars4b = ax4.bar([i + width/2 for i in x], df_gap["PO_OMR"],       width=width, label="PO")
        ax4.set_xticks(list(x))
        ax4.set_xticklabels(df_gap["Department"], rotation=45, ha="right")
        _add_bar_labels(ax4, bars4a, _fmt_number)
        _add_bar_labels(ax4, bars4b, _fmt_number)
    ax4.set_ylabel("OMR")
    ax4.set_title("Approved vs PO Amount by Department")
    ax4.legend()
    fig4.subplots_adjust(left=0.06, right=0.98, top=0.92, bottom=0.28)

    # -------------------------
    # Layout: 2 charts per row (first four same size)
    # -------------------------
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.pyplot(fig0, use_container_width=True)
    with row1_col2:
        st.pyplot(fig1, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.pyplot(fig2, use_container_width=True)
    with row2_col2:
        st.pyplot(fig3, use_container_width=True)

    # Last chart full width (bigger)
    st.pyplot(fig4, use_container_width=True)

    # -------------------------
    # Export dashboard (PDF)
    # -------------------------
    pdf_buf = io.BytesIO()
    with PdfPages(pdf_buf) as pdf:
        for fig in [fig0, fig1, fig2, fig3, fig4]:
            pdf.savefig(fig, bbox_inches="tight")
    pdf_bytes = pdf_buf.getvalue()
    st.download_button(
        "⬇️ Export dashboard (PDF)",
        data=pdf_bytes,
        file_name=f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf"
    )

if __name__ == "__main__":
    main()
