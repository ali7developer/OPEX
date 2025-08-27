import streamlit as st
from pages.components import render_footer
import base64
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt  # charts

# =========================
# Page Config
# =========================
st.set_page_config(page_title="Budget Tracker", layout="wide")

# =========================
# Helpers
# =========================
def get_base64_img(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def _fmt_num(x):
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return "N/A"

def _fmt_pct(x):
    try:
        return f"{x:.1f}%"
    except Exception:
        return "N/A"

# Top-level routes
NAV_OPTIONS = ["Home", "Monitor Budget", "Dashboard", "Administration"]

# =========================
# State & Query Params sync
# =========================
if "selected" not in st.session_state:
    st.session_state["selected"] = "Home"
if "admin_sub" not in st.session_state:
    st.session_state["admin_sub"] = "Budget"  # default subpage

qp = st.query_params
if "selected" in qp and qp["selected"] in NAV_OPTIONS:
    st.session_state["selected"] = qp["selected"]
if "admin_sub" in qp and qp["admin_sub"] in ["Budget", "Role"]:
    st.session_state["admin_sub"] = qp["admin_sub"]

# Initialize capex toast flag
if "capex_clicked" not in st.session_state:
    st.session_state["capex_clicked"] = False

# =========================
# Global Styles + Topbar (logo + navbar on same level, GRAY)
# =========================
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarNav"] { display: none; }
    .css-18e3th9 { padding-left: 1rem; padding-right: 1rem; }

    /* --- Unified top bar with logo + nav (GRAY) --- */
    .topbar {
        width: 100%;
        background-color: #f2f2f2;
        border-bottom: 1px solid #d9d9d9;
        padding: 8px 12px;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 16px;
        position: sticky;
        top: 0;
        z-index: 999;
    }
    .brand { display: flex; align-items: center; gap: 10px; }
    .brand img { width: 80px; height: auto; display: block; }

    .topnav { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .topnav a, .dropbtn {
        color: #111; text-decoration: none; font-weight: 600;
        padding: 8px 14px; border-radius: 8px; display: inline-block;
    }
    .topnav a:hover, .dropbtn:hover { background-color: #e6e6e6; border: 1px solid #bfbfbf; }

    .dropdown { position: relative; display: inline-block; }
    .dropdown-content {
        display: none; position: absolute; background-color: #ffffff; min-width: 200px;
        border: 1px solid #eee; border-radius: 10px; box-shadow: 0 8px 16px rgba(0,0,0,0.08);
        padding: 8px; z-index: 1000;
    }
    .dropdown-content a {
        color: #111; padding: 8px 12px; text-decoration: none; display: block; border-radius: 6px;
    }
    .dropdown-content a:hover { background-color: #f7f7f7; }
    .dropdown:hover .dropdown-content { display: block; } /* show on hover */

    /* Hide accidental duplicate headers */
    #app-topbar ~ #app-topbar { display: none !important; }

    /* Centered button container */
    .centered-buttons {
        display: flex; justify-content: center; align-items: center; height: 10vh; gap: 1800px;
    }
    .stButton > button {
        width: 200px; height: 80px; font-size: 40px !important; font-weight: bold !important;
        border: 3px solid red !important; border-radius: 10px !important;
        background-color: white !important; color: black !important;
    }
    .stButton > button:hover { background-color: #ffe5e5 !important; border: 3px solid red !important; }

    /* KPI cards */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        text-align: center;
        height: 100%;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .kpi-value {
        font-size: 1.4rem;
        font-weight: 800;
        color: #111;
    }
    </style>
""", unsafe_allow_html=True)

# =========================
# Unified Topbar (logo + navbar together) with unique ID
# =========================
logo_data = get_base64_img("assets/ooredoo.png")
topbar_html = f"""
<div id="app-topbar" class="topbar">
  <div class="brand">
    <img src="data:image/png;base64,{logo_data}" alt="logo" />
  </div>
  <div class="topnav">
    <a href="?selected=Home" target="_self">Home</a>
    <a href="?selected=Monitor%20Budget" target="_self">Monitor Budget</a>
    <a href="?selected=Dashboard" target="_self">Dashboard</a>
    <div class="dropdown">
      <a class="dropbtn" href="?selected=Administration" target="_self">Administration ▾</a>
      <div class="dropdown-content">
        <a href="?selected=Administration&admin_sub=Budget" target="_self">Budget</a>
        <a href="?selected=Administration&admin_sub=Role" target="_self">Role</a>
      </div>
    </div>
  </div>
</div>
"""
st.markdown(topbar_html, unsafe_allow_html=True)

# =========================
# Handle CAPEX toast message
# =========================
if st.session_state.get("capex_clicked", False):
    st.toast("This option not available now, coming soon", icon="⏳")
    st.session_state["capex_clicked"] = False

# =========================
# Routing
# =========================
current = st.session_state["selected"]

if current == "Home":
    st.title("🏠 Budget Tracker Home")
    st.markdown("Welcome to the budget Tracker app. Use the navigation menu above to explore.")

    # =========================
    # OPEX/CAPEX buttons BEFORE Year Selector
    # =========================
    st.markdown('<div class="centered-buttons">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        st.write("")
    with col2:
        if st.button("OPEX", key="home_opex_btn"):
            st.session_state["selected"] = "Monitor Budget"
            st.query_params["selected"] = "Monitor Budget"
            st.rerun()
    with col3:
        if st.button("CAPEX", key="home_capex_btn"):
            st.session_state["capex_clicked"] = True
            st.rerun()
    with col4:
        st.write("")
    st.markdown('</div>', unsafe_allow_html=True)

    # =========================
    # 📅 Year Selector (after buttons)
    # =========================
    try:
        conn = sqlite3.connect("opex.db", timeout=10)
        years_df = pd.read_sql_query("SELECT DISTINCT year FROM amc_contracts ORDER BY year DESC", conn)
        conn.close()
        available_years = years_df["year"].dropna().astype(int).tolist()
    except Exception:
        available_years = []

    current_year_default = datetime.now().year
    if current_year_default not in available_years:
        available_years.append(current_year_default)
    available_years = sorted(set(available_years), reverse=True)

    selected_year = st.selectbox(
        "📅 Select Budget Year",
        options=available_years,
        index=available_years.index(current_year_default) if current_year_default in available_years else 0
    )
    current_year = selected_year  # use selected year everywhere below

    # =========================
    # KPI Cards (Selected Year)
    # Budget = yearly_budget.value (selected year)
    # Consumed = SUM(approved_budget) WHERE budget_year=selected year
    # Remaining = Budget - Consumed
    # =========================
    try:
        conn = sqlite3.connect("opex.db", timeout=10)
        cur = conn.cursor()

        # Total Approved Budget (from yearly_budget)
        cur.execute('SELECT "VALUE" FROM yearly_budget WHERE year = ? ORDER BY id DESC LIMIT 1', (current_year,))
        row_b = cur.fetchone()
        budget = float(row_b[0]) if row_b and row_b[0] is not None else 0.0

        # Consumed = sum(approved_budget) for budget_year = selected year
        cur.execute(
            "SELECT COALESCE(SUM(approved_budget), 0) FROM amc_contracts WHERE budget_year = ?",
            (current_year,)
        )
        consumed = float(cur.fetchone()[0] or 0.0)

        remaining = budget - consumed
        utilization = (consumed / budget * 100) if budget > 0 else None

        # Approval rate — based on approved flag for contract 'year' (operational year)
        cur.execute('SELECT COUNT(*) FROM amc_contracts WHERE year = ?', (current_year,))
        total_contracts = cur.fetchone()[0] or 0
        cur.execute('SELECT COUNT(*) FROM amc_contracts WHERE year = ? AND approved = 1', (current_year,))
        approved_cnt = cur.fetchone()[0] or 0
        approval_rate = (approved_cnt / total_contracts * 100) if total_contracts > 0 else None

        # PO Coverage % among approved contracts (join by PR+year)
        cur.execute("""
            SELECT COUNT(DISTINCT c.id)
            FROM amc_contracts c
            JOIN amc_pos p
              ON p.pr_number = c.pr_number AND p.year = c.year
            WHERE c.year = ? AND c.approved = 1
        """, (current_year,))
        with_po = cur.fetchone()[0] or 0
        po_coverage = (with_po / approved_cnt * 100) if approved_cnt > 0 else None

        # Render KPI cards (3 x 2)
        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>Total Approved Budget ({current_year})</div>"
                f"<div class='kpi-value'>{_fmt_num(budget)}</div></div>",
                unsafe_allow_html=True
            )
        with k2:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>Consumed</div>"
                f"<div class='kpi-value'>{_fmt_num(consumed)}</div></div>",
                unsafe_allow_html=True
            )
        with k3:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>Remaining</div>"
                f"<div class='kpi-value'>{_fmt_num(remaining)}</div></div>",
                unsafe_allow_html=True
            )

        k4, k5, k6 = st.columns(3)
        with k4:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>Utilization %</div>"
                f"<div class='kpi-value'>{_fmt_pct(utilization) if utilization is not None else 'N/A'}</div></div>",
                unsafe_allow_html=True
            )
        with k5:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>Approval Rate</div>"
                f"<div class='kpi-value'>{_fmt_pct(approval_rate) if approval_rate is not None else 'N/A'}</div></div>",
                unsafe_allow_html=True
            )
        with k6:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>PO Coverage %</div>"
                f"<div class='kpi-value'>{_fmt_pct(po_coverage) if po_coverage is not None else 'N/A'}</div></div>",
                unsafe_allow_html=True
            )

    except Exception as e:
        st.error(f"Failed to compute KPI metrics: {e}")

    # =========================
    # Contracts expiring in next 90 days — DISTINCT pr_number (earliest end_date per PR)
    # =========================
    st.divider()
    st.write("")
    st.subheader("📅 Contracts Expiring in Next 90 Days")
    try:
        if 'conn' not in locals():
            conn = sqlite3.connect("opex.db", timeout=10)
        today = datetime.now().date()
        horizon = today + timedelta(days=90)

        q_exp = """
            WITH per_pr AS (
                SELECT
                    pr_number,
                    MIN(date(end_date)) AS min_end_date
                FROM amc_contracts
                WHERE end_date IS NOT NULL
                  AND date(end_date) >= date(?)
                  AND date(end_date) <= date(?)
                GROUP BY pr_number
            )
            SELECT
                distinct ac.pr_number,
                d.name_en AS Department,
                ac.vendor,
                ac.end_date
            FROM per_pr pp
            JOIN amc_contracts ac
              ON ac.pr_number = pp.pr_number
             AND date(ac.end_date) = pp.min_end_date
            LEFT JOIN departments d
              ON d.id = ac.ref_departments
            ORDER BY date(ac.end_date) ASC
        """
        df_exp = pd.read_sql_query(q_exp, conn, params=[str(today), str(horizon)])

        if df_exp.empty:
            st.info("No contracts expiring in the next 90 days.")
        else:
            df_exp["End Date"] = pd.to_datetime(df_exp["end_date"]).dt.date
            df_exp["Days Left"] = (pd.to_datetime(df_exp["End Date"]) - pd.to_datetime(today)).dt.days
            show_cols = ["pr_number", "Department", "vendor", "End Date", "Days Left"]
            st.dataframe(
                df_exp[show_cols].rename(columns={"pr_number": "PR Number", "vendor": "Vendor"}),
                use_container_width=True
            )
    except Exception as e:
        st.error(f"Failed to load expiring contracts: {e}")

    # =========================
    # Mini trend sparkline (Selected Year): cumulative CONSUMED vs linear BUDGET burn
    # - Consumed = sum(approved_budget) for budget_year=selected year, grouped by created month
    # - Budget = yearly_budget.value
    # =========================
    st.divider()
    st.write("")
    st.write("")

    try:
        if 'conn' not in locals():
            conn = sqlite3.connect("opex.db", timeout=10)

        # Pull approved_budget with created timestamps for the selected budget_year
        df_cons = pd.read_sql_query(
            """
            SELECT approved_budget, created
            FROM amc_contracts
            WHERE budget_year = ? AND approved_budget IS NOT NULL
            """,
            conn,
            params=[current_year]
        )

        # Budget line from yearly_budget
        df_bud = pd.read_sql_query(
            'SELECT "VALUE" AS total FROM yearly_budget WHERE year = ? ORDER BY id DESC LIMIT 1',
            conn,
            params=[current_year]
        )
        conn.close()

        budget_for_line = float(df_bud.iloc[0]["total"]) if not df_bud.empty and df_bud.iloc[0]["total"] is not None else 0.0

        # Prepare monthly cumulative consumed (based on approved budgets’ created date)
        if not df_cons.empty and "created" in df_cons.columns:
            df_cons["created"] = pd.to_datetime(df_cons["created"], errors="coerce")
            df_cons = df_cons.dropna(subset=["created"])
            df_cons = df_cons[df_cons["created"].dt.year == current_year]
            df_cons["month"] = df_cons["created"].dt.month
            monthly = df_cons.groupby("month")["approved_budget"].sum().reindex(
                range(1, datetime.now().month + 1),
                fill_value=0.0
            )
            cum_consumed = monthly.cumsum().astype(float)
        else:
            cum_consumed = pd.Series([0.0] * datetime.now().month, index=range(1, datetime.now().month + 1))

        # Linear budget burn line
        months = list(range(1, datetime.now().month + 1))
        if budget_for_line <= 0:
            burn_line = pd.Series([0.0] * len(months), index=months)
        else:
            per_month = budget_for_line / 12.0
            burn_line = pd.Series([per_month * m for m in months], index=months)

        # Draw sparkline: small + clean
        s_left, s_center, s_right = st.columns([1, 2, 1])
        with s_center:
            fig2, ax2 = plt.subplots(figsize=(6.0, 2.0))
            ax2.plot(months, cum_consumed.values, label="Cumulative Consumed", linewidth=2)
            ax2.plot(months, burn_line.values, label="Linear Approved Budget Burn", linewidth=2)
            ax2.set_xlim(1, months[-1])
            ax2.set_xticks(months)
            ax2.set_xticklabels([datetime(2000, m, 1).strftime("%b") for m in months], rotation=0, fontsize=8)
            ax2.tick_params(axis='y', labelsize=8)
            ax2.grid(alpha=0.2)
            for spine in ["top", "right"]:
                ax2.spines[spine].set_visible(False)
            ax2.legend(fontsize=8, loc="upper left")
            st.pyplot(fig2, use_container_width=False)

    except Exception as e:
        st.error(f"Failed to render YTD sparkline: {e}")

    # =========================
    # Donut: Consumed vs Total Approved Budget (Selected Year) — centered
    # =========================
    st.divider()
    st.write("")
    st.write("")
    try:
        # Recompute quickly in case earlier block errored
        conn = sqlite3.connect("opex.db", timeout=10)
        cur = conn.cursor()
        cur.execute('SELECT "VALUE" FROM yearly_budget WHERE year = ? ORDER BY id DESC LIMIT 1', (current_year,))
        row_b = cur.fetchone()
        budget2 = float(row_b[0]) if row_b and row_b[0] is not None else 0.0
        cur.execute(
            "SELECT COALESCE(SUM(approved_budget), 0) FROM amc_contracts WHERE budget_year = ?",
            (current_year,)
        )
        consumed2 = float(cur.fetchone()[0] or 0.0)
        conn.close()

        st.subheader(f"🟢 Consumed vs Total Approved Budget – {current_year}")
        if budget2 <= 0:
            st.info(f"No total approved budget set for {current_year} in table 'yearly_budget'.")
        else:
            if consumed2 <= budget2:
                labels = ["Consumed", "Remaining"]
                sizes = [consumed2, max(budget2 - consumed2, 0)]
            else:
                labels = ["Budget", "Overrun"]
                sizes = [budget2, consumed2 - budget2]

            fig, ax = plt.subplots(figsize=(3.6, 3.6))  # reduced size
            ax.pie(
                sizes,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                wedgeprops={"width": 0.40, "edgecolor": "white"}
            )
            ax.axis("equal")
            ax.text(0, 0, f"{_fmt_num(consumed2)} / {_fmt_num(budget2)}\nOMR",
                    ha="center", va="center", fontsize=11, weight="bold")

            d_left, d_center, d_right = st.columns([1, 2, 1])  # centered horizontally
            with d_center:
                st.pyplot(fig, use_container_width=False)

    except Exception as e:
        st.error(f"Failed to render consuming donut: {e}")

elif current == "Monitor Budget":
    try:
        import pages.monitor as monitor
        monitor.main()
    except Exception as e:
        st.error(f"Failed to load Monitor Budget page: {e}")

elif current == "Dashboard":
    try:
        import pages.dashboard as dashboard
        dashboard.main()
    except Exception as e:
        st.error(f"Failed to load Dashboard page: {e}")

elif current == "Administration":
    sub = st.session_state.get("admin_sub", "Budget")
    if sub == "Budget":
        try:
            import pages.yearly_budget as yearly_budget
            yearly_budget.main()
        except Exception as e:
            st.error(f"Failed to load Budget administration page: {e}")
    elif sub == "Role":
        try:
            import pages.role as role
            role.main()
        except Exception as e:
            st.error(f"Failed to load Role administration page: {e}")

# =========================
# Footer
# =========================
render_footer()
