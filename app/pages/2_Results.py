import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


import streamlit as st
import pandas as pd

st.set_page_config(page_title="Results", layout="wide")

st.title("Results")

if "costs" not in st.session_state or "rev" not in st.session_state or "cogs" not in st.session_state:
    st.warning("Go to **Upload** and click **Process files** first.")
    st.stop()

costs = st.session_state["costs"]
rev = st.session_state["rev"]
cogs = st.session_state["cogs"]

# Shipping + packaging totals
ship_se = rev.orders_se * costs.shipping_per_order_se
pack_se = rev.orders_se * costs.packaging_per_order_se

ship_ot = rev.orders_other * costs.shipping_per_order_other
pack_ot = rev.orders_other * costs.packaging_per_order_other

net_total = rev.net_rev_se + rev.net_rev_other
st.divider()
st.subheader("Validation / Reconciliation")

# Revenue checks
st.write("Revenue source columns (from shipping-location report):")
st.code(f"net sales source: {getattr(rev, 'net_sales_source', 'unknown')}\nshipping source: {getattr(rev, 'shipping_source', 'unknown')}")

orders_total = rev.orders_se + rev.orders_other
st.metric("Orders (SE + OTHER)", f"{int(orders_total)}")

# Basic sanity checks
if net_total <= 0:
    st.error("Net revenue is 0 or negative. Check the shipping-location report export.")
else:
    st.success("Net revenue is positive ✅")

# COGS coverage check (already exists, but make it explicit here too)
st.metric("COGS coverage", f"{cogs.coverage_pct:.1f}%")
if cogs.coverage_pct < 99.9:
    st.warning("COGS coverage is below 100%. Some SKUs did not match the cost workbook.")
else:
    st.success("All SKUs matched to costs ✅")

# COGS is calculated only as TOTAL (not split by region)
cogs_total = cogs.cogs_se  # we stored total COGS here

gm_se = rev.net_rev_se - ship_se - pack_se
gm_ot = rev.net_rev_other - ship_ot - pack_ot
gm_total = net_total - (ship_se + ship_ot) - (pack_se + pack_ot) - cogs_total

def pct(a, b):
    return (a / b * 100.0) if b else 0.0

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Sweden (SE)")
    st.metric("Net revenue (ex VAT)", f"{rev.net_rev_se:,.0f} SEK")
    st.metric("Orders", f"{rev.orders_se:,.0f}")
    st.metric("COGS", "—")
    st.metric("Shipping cost", f"{ship_se:,.0f} SEK")
    st.metric("Packaging cost", f"{pack_se:,.0f} SEK")
    st.metric("After shipping+packaging", f"{gm_se:,.0f} SEK")
    st.metric("After ship+pack %", f"{pct(gm_se, rev.net_rev_se):.1f}%")

with col2:
    st.subheader("All other countries (OTHER)")
    st.metric("Net revenue (ex VAT)", f"{rev.net_rev_other:,.0f} SEK")
    st.metric("Orders", f"{rev.orders_other:,.0f}")
    st.metric("COGS", "—")
    st.metric("Shipping cost", f"{ship_ot:,.0f} SEK")
    st.metric("Packaging cost", f"{pack_ot:,.0f} SEK")
    st.metric("After shipping+packaging", f"{gm_se:,.0f} SEK")
st.metric("After ship+pack %", f"{pct(gm_se, rev.net_rev_se):.1f}%")

with col3:
    st.subheader("Total")
    st.metric("Net revenue (ex VAT)", f"{net_total:,.0f} SEK")
    st.metric("COGS (total)", f"{cogs_total:,.0f} SEK")
    st.metric("COGS coverage", f"{cogs.coverage_pct:.1f}%")
    st.metric("Gross margin", f"{gm_total:,.0f} SEK")
    st.metric("GM %", f"{pct(gm_total, net_total):.1f}%")

st.divider()

summary = pd.DataFrame(
    [
        {
            "Region": "SE",
            "Net revenue": rev.net_rev_se,
            "Orders": rev.orders_se,
            "Shipping cost": ship_se,
            "Packaging cost": pack_se,
            "COGS": 0.0,
            "After ship+pack": gm_se,
            "After ship+pack %": pct(gm_se, rev.net_rev_se),
        },
        {
            "Region": "OTHER",
            "Net revenue": rev.net_rev_other,
            "Orders": rev.orders_other,
            "Shipping cost": ship_ot,
            "Packaging cost": pack_ot,
            "COGS": 0.0,
            "After ship+pack": gm_ot,
            "After ship+pack %": pct(gm_ot, rev.net_rev_other),
        },
        {
            "Region": "TOTAL",
            "Net revenue": net_total,
            "Orders": rev.orders_se + rev.orders_other,
            "Shipping cost": ship_se + ship_ot,
            "Packaging cost": pack_se + pack_ot,
            "COGS": cogs_total,
            "Gross margin": gm_total,
            "GM %": pct(gm_total, net_total),
        },
    ]
)
st.divider()
st.subheader("Margin bridge (TOTAL)")

# Totals
net_total = rev.net_rev_se + rev.net_rev_other

# IMPORTANT:
# In your setup, COGS is TOTAL only (not split by region)
cogs_total = cogs.cogs_se  # (this is how we stored total COGS earlier)

total_shipping = ship_se + ship_ot
total_packaging = pack_se + pack_ot

gm_total = net_total - cogs_total - total_shipping - total_packaging
gm_pct_total = (gm_total / net_total) * 100.0 if net_total else 0.0

bridge_rows = [
    ("Adjusted net revenue", net_total),
    ("- COGS (total)", -cogs_total),
    ("- Shipping", -total_shipping),
    ("- Packaging", -total_packaging),
    ("= Gross margin", gm_total),
]

bridge_df = pd.DataFrame(bridge_rows, columns=["Step", "SEK"])

# Add % of adjusted net revenue
if net_total:
    bridge_df["% of revenue"] = (bridge_df["SEK"] / net_total) * 100.0
else:
    bridge_df["% of revenue"] = 0.0

# Formatting for nicer display
bridge_df["SEK"] = bridge_df["SEK"].round(2)
bridge_df["% of revenue"] = bridge_df["% of revenue"].round(1)

st.table(bridge_df)

st.metric("GM % (TOTAL)", f"{gm_pct_total:.1f}%")
st.subheader("Summary table")
st.dataframe(summary, use_container_width=True)

csv = summary.to_csv(index=False).encode("utf-8")
st.download_button("Download region_summary.csv", data=csv, file_name="region_summary.csv", mime="text/csv")