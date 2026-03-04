import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import streamlit as st

st.set_page_config(page_title="Exceptions", layout="wide")
st.title("Exceptions / Data quality")

if "cogs" not in st.session_state:
    st.warning("Go to **Upload** and click **Process files** first.")
    st.stop()

cogs = st.session_state["cogs"]

st.subheader("Unmatched SKUs (not found in cost workbook COGS sheet)")
st.caption("These SKUs are excluded from COGS totals until you add them to the COGS sheet.")
st.dataframe(cogs.unmatched, use_container_width=True)

if not cogs.unmatched.empty:
    st.download_button(
        "Download unmatched_skus.csv",
        data=cogs.unmatched.to_csv(index=False).encode("utf-8"),
        file_name="unmatched_skus.csv",
        mime="text/csv",
    )

st.divider()

st.subheader("Lines with missing shipping country (cannot classify SE vs OTHER)")
if cogs.missing_country is None or cogs.missing_country.empty:
    st.success("None ✅")
else:
    st.warning(f"{len(cogs.missing_country):,} line rows missing shipping country.")
    st.dataframe(cogs.missing_country.head(200), use_container_width=True)

st.divider()

st.subheader("Returns / adjustments (non-positive quantities)")
st.caption("v1 excludes these from COGS totals and shows them here.")
st.dataframe(cogs.returns_adjustments, use_container_width=True)

if not cogs.returns_adjustments.empty:
    st.download_button(
        "Download returns_adjustments.csv",
        data=cogs.returns_adjustments.to_csv(index=False).encode("utf-8"),
        file_name="returns_adjustments.csv",
        mime="text/csv",
    )