import streamlit as st
import base64
import os

def render_footer():
      st.markdown("""
        <style>
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #f0f0f0;
            text-align: center;
            padding: 10px;
            color: #555;
            font-size: 14px;
            z-index: 999;
        }
        </style>

        <div class="footer">
            All copy rights are reserved for OO, 2025
        </div>
    """, unsafe_allow_html=True)

