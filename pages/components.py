import streamlit as st
import base64
import datetime

LOGO_PATH = "assets/ooredoo.png"

def _b64(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

def render_footer():
    year = datetime.datetime.now().year
    logo_b64 = _b64(LOGO_PATH)  # if None, we'll show text fallback

    # ---- GLOBAL CSS: reserve space so fixed footer won't overlap content ----
    st.markdown("""
<style>
:root { --footer-h: 110px; } /* adjust if you change footer height */

html, body {
  height: 100%;
}
[data-testid="stAppViewContainer"] {
  min-height: 100%;
  padding-bottom: var(--footer-h) !important; /* keep content above fixed footer */
}

/* Full-width hairline across the page (just above footer) */
.footer-separator {
  border: 0;
  border-top: 1px solid #dcdcdc;
  height: 0;
  width: 100vw;
  position: fixed;
  left: 50%;
  bottom: var(--footer-h);
  transform: translateX(-50%);
  margin: 0;
  z-index: 998;
}

/* Fixed footer stuck to bottom spanning the whole viewport width */
.footer-fixed {
  position: fixed;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: 100vw;
  background: #f5f5f5;
  box-shadow: 0 -1px 6px rgba(0,0,0,0.06);
  z-index: 999;
  padding: 14px 16px;
}

/* Inner content max width */
.footer-wrap {
  max-width: 1200px;
  margin: 0 auto;
}

/* Top row: logo left, nav centered */
.footer-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.footer-left img { height: 46px; }
.footer-left b { font-size: 16px; }

.footer-nav {
  flex: 1 1 auto;
  display: flex;
  justify-content: center;
  gap: 28px;
  flex-wrap: wrap;
  font-size: 14px;
  font-weight: 600;
}
.footer-nav a {
  color: #e60000;
  text-decoration: none;
  transition: all .2s ease;
}
.footer-nav a:hover {
  color: #b30000;
  text-decoration: underline;
}

/* Confidential */
.footer-note {
  text-align: center;
  font-size: 12px;
  color: #555;
  line-height: 1.6;
  max-width: 800px;
  margin: 8px auto 0;
}

/* Make sure Streamlit bottom elements don't overlap */
footer, .viewerBadge_container__1QSob { display: none !important; }
</style>
""", unsafe_allow_html=True)

    # ---- HTML (no leading spaces to avoid code blocks) ----
    sep = '<hr class="footer-separator">'
    html = f"""<div class="footer-fixed">
<div class="footer-wrap">
  <div class="footer-top">
    <div class="footer-left">{("<img src='data:image/png;base64," + (logo_b64 or "") + "' alt='Ooredoo Logo'>") if logo_b64 else "<b>Ooredoo Oman</b>"}</div>
    <nav class="footer-nav">
      <a href="?selected=Home">Home</a>
      <a href="?selected=Dashboard">Dashboard</a>
      <a href="?selected=Monitor%20Budget">Monitor</a>
    </nav>
  </div>
  <div class="footer-note">© {year} <b>Ooredoo Oman</b>. All Rights Reserved.<br>
  This system is <b>Confidential &amp; Proprietary</b>. Unauthorized access, reproduction, or distribution is strictly prohibited.</div>
</div>
</div>"""

    # Render separator and footer
    st.markdown(sep + html, unsafe_allow_html=True)
