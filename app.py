import streamlit as st
from ui.layout import render_layout

st.set_page_config(
    page_title="faby - 株式ダッシュボード",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_layout()
