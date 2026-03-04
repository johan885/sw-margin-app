import streamlit as st

st.set_page_config(page_title="Swedish Wild – Gross Margin", layout="wide")

st.title("Swedish Wild – Gross Margin Calculator")
st.caption("Use net revenue + orders from Shopify shipping-location report, shipping/packaging from cost workbook, and COGS from orders export.")
st.success("Streamlit is running ✅")

st.write("Go to **Upload** in the left sidebar to load files.")