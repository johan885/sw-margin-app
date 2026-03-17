import streamlit as st
import pandas as pd
import io

st.title("EU CSV to US CSV Converter")

st.write(
    "Upload a European-style CSV file (semicolon separator and comma decimals) "
    "and convert it to a US-style CSV file (comma separator and dot decimals)."
)

uploaded_file = st.file_uploader("Upload EU CSV file", type=["csv"])

if uploaded_file is not None:
    try:
        # Read EU CSV
        df = pd.read_csv(uploaded_file, sep=";", decimal=",")

        st.subheader("Preview")
        st.dataframe(df, use_container_width=True)

        # Convert to US CSV
        csv_us = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download US CSV",
            data=csv_us,
            file_name="converted_us_format.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Something went wrong: {e}")