import streamlit as st
from streamlit_option_menu import option_menu
from pages.components import render_footer
import base64
import os


# --- Page Config ---
st.set_page_config(page_title="OPEX Tracker", layout="wide")

# --- Hide Streamlit's default sidebar ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        display: none;
    }
    [data-testid="stSidebarNav"] {
        display: none;
    }
    .css-18e3th9 {
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- Load top-left logo ---
def get_base64_img(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_data = get_base64_img("assets/ooredoo.png")

st.markdown(f"""
    <style>
    .top-left-logo {{
        position: fixed;
        top: 10px;
        left: 15px;
        z-index: 1000;
    }}
    </style>
    <div class="top-left-logo">
        <img src="data:image/png;base64,{logo_data}" width="80">
    </div>
""", unsafe_allow_html=True)

# --- Top Navigation Menu ---
selected = option_menu(
    menu_title=None,
    options=["Home", "Monitor Budget", "Dashboard"],
    icons=["house", "bar-chart", "pie-chart"],
    menu_icon="cast",
    orientation="horizontal"
)

# --- Page Routing ---
if selected == "Home":
    st.title("🏠 OPEX Tracker Home")
    st.markdown("Welcome to the OPEX Tracker app. Use the navigation menu above to explore.")

elif selected == "Monitor Budget":
    import pages.monitor as monitor
    monitor.main()

elif selected == "Dashboard":
    import pages.dashboard as dashboard
    dashboard.main()

# --- Footer ---
render_footer()
