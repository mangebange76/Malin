import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Test: Anslut till Google Sheets med credentials
def test_google_auth():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(
            st.secrets["GOOGLE_CREDENTIALS"],
            scopes=scope
        )
        gc = gspread.authorize(creds)

        # Test: Öppna ett kalkylark
        SHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit"
        sh = gc.open_by_url(SHEET_URL)
        st.success(f"✅ Lyckades öppna arket: {sh.title}")

        # Test: Läs första bladets rubriker
        worksheet = sh.sheet1
        headers = worksheet.row_values(1)
        st.write("Första radens rubriker:", headers)

    except Exception as e:
        st.error(f"❌ Fel vid autentisering: {e}")

# Kör testet
st.title("Google Sheets Autentiseringstest")
test_google_auth()
