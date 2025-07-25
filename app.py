import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Hämta credentials från GOOGLE_CREDENTIALS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"],
    scopes=scope,
)

# Hämta SHEET_URL inifrån GOOGLE_CREDENTIALS
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]

# Initiera gspread
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SHEET_URL)
sheet = sh.sheet1

# Testa att visa något från arket
st.title("Testar koppling till Google Sheet")

try:
    cell_value = sheet.cell(1, 1).value
    st.success(f"Värdet i cell A1: {cell_value}")
except Exception as e:
    st.error(f"Kunde inte läsa från arket: {e}")
