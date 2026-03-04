
import sys
from pathlib import Path

# Add project root to Python path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import streamlit as st
from src.swmargin.core import load_costs_workbook, compute_revenue_orders, compute_cogs_from_orders_export

st.set_page_config(page_title="Upload", layout="wide")

st.title("Upload files")

st.markdown(
    """
Upload these 3 files:

1. **Orders export (CSV)** – used for COGS (SKU × quantity)
2. **Total sales by shipping location (CSV)** – used for **Net sales** (ex VAT) + **Orders**
3. **Cost workbook (XLSX)** – contains:
   - a COGS sheet (SKU + cost per unit)
   - a Shipping/Packaging sheet (region SE/OTHER + shipping/packaging per order)
"""
)

orders_file = st.file_uploader("1) Orders export (CSV)", type=["csv"], key="orders_export")
sales_file = st.file_uploader("2) Total sales by shipping location (CSV)", type=["csv"], key="sales_by_location")
costs_file = st.file_uploader("3) Cost workbook (XLSX)", type=["xlsx"], key="cost_workbook")

if st.button("Process files", type="primary"):
    if not orders_file or not sales_file or not costs_file:
        st.error("Please upload all 3 files first.")
        st.stop()

    with st.spinner("Loading cost workbook…"):
        costs = load_costs_workbook(costs_file.getvalue())

    with st.spinner("Reading revenue + orders…"):
        rev = compute_revenue_orders(sales_file.getvalue())

    with st.spinner("Calculating COGS from orders export…"):
        cogs = compute_cogs_from_orders_export(orders_file.getvalue(), costs)

    st.session_state["costs"] = costs
    st.session_state["rev"] = rev
    st.session_state["cogs"] = cogs

    st.success("Processed ✅ Go to **Results** in the sidebar.")

st.divider()

if "costs" in st.session_state:
    costs = st.session_state["costs"]
    st.subheader("Detected cost workbook structure")
    st.write(costs.meta)
    st.write(
        {
            "shipping_per_order_SE": costs.shipping_per_order_se,
            "packaging_per_order_SE": costs.packaging_per_order_se,
            "shipping_per_order_OTHER": costs.shipping_per_order_other,
            "packaging_per_order_OTHER": costs.packaging_per_order_other,
        }
    )

if "rev" in st.session_state:
    rev = st.session_state["rev"]
    st.subheader("Revenue + Orders (from shipping-location report)")
    st.write(rev.meta)
    st.write(
        {
            "NetRevenue_SE": rev.net_rev_se,
            "Orders_SE": rev.orders_se,
            "NetRevenue_OTHER": rev.net_rev_other,
            "Orders_OTHER": rev.orders_other,
        }
    )

if "cogs" in st.session_state:
    c = st.session_state["cogs"]
    st.subheader("COGS result (from orders export)")
    st.write(c.meta)
    st.metric("COGS coverage (%)", f"{c.coverage_pct:.1f}%")