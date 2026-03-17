import streamlit as st
import pandas as pd

st.title("Sales in KG Calculator")

st.write("Upload Order file and Master Cost Workbook to calculate kg sold per SKU.")

# Upload files
orders_file = st.file_uploader("Upload Order File (CSV)", type=["csv"])
cost_file = st.file_uploader("Upload Master Cost Workbook (Excel)", type=["xlsx"])

if orders_file and cost_file:

    # Load files
    orders = pd.read_csv(orders_file)
    costs = pd.read_excel(cost_file)

    # --- Clean Orders ---
    orders["Lineitem quantity"] = pd.to_numeric(
        orders["Lineitem quantity"], errors="coerce"
    ).fillna(0)

    orders["Lineitem name"] = orders["Lineitem name"].astype(str)

    # --- Clean Costs ---
    costs.columns = ["sku", "name", "weight"] + list(costs.columns[3:])

    costs["weight"] = pd.to_numeric(costs["weight"], errors="coerce").fillna(0)

    # --- Merge ---
    merged = orders.merge(
        costs[["sku", "weight"]],
        left_on="Lineitem name",
        right_on="sku",
        how="left"
    )

    # --- Calculate KG ---
    merged["kg_sold"] = (
        merged["Lineitem quantity"] * merged["weight"] / 1000
    )

    # --- Group ---
    result = (
        merged.groupby("Lineitem name")["kg_sold"]
        .sum()
        .reset_index()
    )

    result["kg_sold"] = result["kg_sold"].round(3)

    # --- Display ---
    st.subheader("KG Sold per SKU")
    st.dataframe(result)

    total = result["kg_sold"].sum()
    st.metric("Total KG Sold", round(total, 2))

    # --- Export ---
    csv = result.to_csv(index=False)

    st.download_button(
        "Download CSV",
        csv,
        "sales_kg.csv",
        "text/csv"
    )