import streamlit as st
import pandas as pd

st.title("Inventory KG Calculator")

st.write(
    "Upload a Shopify product export CSV. "
    "The app calculates total inventory weight (kg) per handle."
)

uploaded_file = st.file_uploader("Upload inventory CSV", type=["csv"])

if uploaded_file:

    df = pd.read_csv(uploaded_file)

    required_columns = [
        "Handle",
        "Variant Grams",
        "Variant Inventory Qty"
    ]

    missing = [c for c in required_columns if c not in df.columns]

    if missing:
        st.error(f"Missing columns: {missing}")
        st.stop()

    df["Variant Grams"] = pd.to_numeric(df["Variant Grams"], errors="coerce").fillna(0)
    df["Variant Inventory Qty"] = pd.to_numeric(df["Variant Inventory Qty"], errors="coerce").fillna(0)

    df["inventory_kg"] = (
        df["Variant Grams"] *
        df["Variant Inventory Qty"] / 1000
    )

    result = (
        df.groupby("Handle")["inventory_kg"]
        .sum()
        .reset_index()
    )

    result["inventory_kg"] = result["inventory_kg"].round(3)

    st.subheader("Inventory per handle")

    st.dataframe(result)

    total = result["inventory_kg"].sum()

    st.metric("Total inventory (kg)", round(total,2))

    csv = result.to_csv(index=False)

    st.download_button(
        "Download CSV",
        csv,
        "inventory_by_handle_kg.csv",
        "text/csv"
    )