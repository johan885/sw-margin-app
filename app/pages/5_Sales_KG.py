import streamlit as st
import pandas as pd

st.title("Sales in KG Calculator")

st.write(
    "Upload Order file and Master Cost Workbook to calculate kg sold per product."
)

orders_file = st.file_uploader("Upload Order File (CSV)", type=["csv"])
cost_file = st.file_uploader("Upload Master Cost Workbook (Excel)", type=["xlsx"])

if orders_file and cost_file:
    try:
        orders = pd.read_csv(orders_file)
        costs = pd.read_excel(cost_file)

        required_order_columns = ["Lineitem quantity", "Lineitem sku", "Lineitem name"]
        required_cost_columns = ["sku", "weight", "name"]

        missing_orders = [c for c in required_order_columns if c not in orders.columns]
        missing_costs = [c for c in required_cost_columns if c not in costs.columns]

        if missing_orders:
            st.error(f"Missing columns in Order file: {missing_orders}")
            st.stop()

        if missing_costs:
            st.error(f"Missing columns in Master Cost Workbook: {missing_costs}")
            st.stop()

        orders["Lineitem quantity"] = pd.to_numeric(
            orders["Lineitem quantity"], errors="coerce"
        ).fillna(0)

        orders["Lineitem sku"] = orders["Lineitem sku"].astype(str).str.strip()
        orders["Lineitem name"] = orders["Lineitem name"].astype(str).str.strip()

        costs["sku"] = costs["sku"].astype(str).str.strip()
        costs["weight"] = pd.to_numeric(costs["weight"], errors="coerce").fillna(0)
        costs["name"] = costs["name"].astype(str).str.strip()

        merged = orders.merge(
            costs[["sku", "weight", "name"]],
            left_on="Lineitem sku",
            right_on="sku",
            how="left"
        )

        merged["kg_sold"] = (
            merged["Lineitem quantity"] * merged["weight"] / 1000
        )

        result = (
            merged.groupby(["Lineitem sku", "name"], dropna=False)["kg_sold"]
            .sum()
            .reset_index()
        )

        result["kg_sold"] = result["kg_sold"].round(3)

        result = result.rename(
            columns={
                "Lineitem sku": "SKU",
                "name": "Product name"
            }
        )

        result = result.sort_values("kg_sold", ascending=False)

        st.subheader("KG Sold per Product")
        st.dataframe(result, use_container_width=True)

        total = result["kg_sold"].sum()
        st.metric("Total KG Sold", round(total, 2))

        missing_matches = merged[merged["weight"].isna() | (merged["weight"] == 0)][
            ["Lineitem sku", "Lineitem name"]
        ].drop_duplicates()

        if len(missing_matches) > 0:
            st.warning("Some SKUs were not found in the Master Cost Workbook.")
            st.dataframe(missing_matches, use_container_width=True)

        csv = result.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download CSV",
            csv,
            "sales_kg.csv",
            "text/csv"
        )

    except Exception as e:
        st.error(f"Something went wrong: {e}")