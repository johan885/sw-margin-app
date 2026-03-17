import streamlit as st
import pandas as pd
import io

st.title("EU CSV to US Format Converter")

st.write(
    "Upload a European-style CSV file (semicolon separator and comma decimals). "
    "Download it as US CSV or Excel."
)

uploaded_file = st.file_uploader("Upload EU CSV file", type=["csv"])

if uploaded_file is not None:
    try:
        # Read EU CSV correctly
        df = pd.read_csv(uploaded_file, sep=";", decimal=",")

        st.subheader("Preview")
        st.dataframe(df, use_container_width=True)

        # US CSV output
        csv_us = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download US CSV",
            data=csv_us,
            file_name="converted_us_format.csv",
            mime="text/csv",
        )

        # Excel output
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Converted")
        excel_buffer.seek(0)

        st.download_button(
            label="Download Excel (.xlsx)",
            data=excel_buffer,
            file_name="converted_us_format.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"Something went wrong: {e}")