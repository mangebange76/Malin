import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(credentials)

# Hämta URL
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]

# Öppna kalkylarket
try:
    sh = gc.open_by_url(SHEET_URL)
except Exception as e:
    st.error(f"Kunde inte öppna kalkylarket: {e}")
    st.stop()

# Kontrollera om bladet 'Data' finns, annars skapa det
try:
    worksheet = sh.worksheet("Data")
except gspread.exceptions.WorksheetNotFound:
    worksheet = sh.add_worksheet(title="Data", rows="100", cols="10")
    worksheet.update("A1", "Testvärde")

# Hämta värde i A1
try:
    värde = worksheet.acell("A1").value
    st.success(f"Innehåll i cell A1: {värde}")
except Exception as e:
    st.error(f"Kunde inte läsa från cell A1: {e}")
