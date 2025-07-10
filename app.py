import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Skapa Google Sheets-klient
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(credentials)

# Testa att öppna kalkylarket
try:
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.sheet1  # Första bladet
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    st.success("✅ Anslutning till Google Sheets fungerade!")
    st.dataframe(df)

except Exception as e:
    st.error("❌ Misslyckades med att läsa Google Sheet:")
    st.exception(e)
