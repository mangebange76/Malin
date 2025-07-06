import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# Inställningar för Google Sheets
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

def ensure_headers(ws, headers):
    if ws.row_count == 0 or ws.row_values(1) != headers:
        ws.clear()
        ws.append_row(headers)

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    headers = [
        "Dag", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
        "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila", "Älskar", "Älsk Tid",
        "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Pv", "Svarta"
    ]
    ensure_headers(worksheet, headers)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

def add_test_data(worksheet):
    if "testdata_lagd" not in st.session_state:
        headers = [
            "Dag", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
            "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila", "Älskar", "Älsk Tid",
            "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Pv", "Svarta"
        ]
        row = [
            "2025-07-07", 55, 10, 10, 5, 6, 7, 4, 3, 2, 120, 180, 240, 60,
            12, 15, 1, 7, 12, 6, 17, 0, 5
        ]
        worksheet.clear()
        worksheet.append_row(headers)
        worksheet.append_row(row)
        st.session_state["testdata_lagd"] = True
        st.success("✅ Testdata har lagts till automatiskt.")

def main():
    st.set_page_config(page_title="MalinData App", layout="wide")
    st.title("📊 MalinData – Daglig inmatning & analys")

    worksheet, df = load_data()
    add_test_data(worksheet)

    st.subheader("✅ Datan är inläst – redo att lägga till ny rad eller testa vilodagar")

    # Enkel kontroll att datan syns
    st.dataframe(df)

    # Här kan resten av funktionaliteten (inmatning, presentation, beräkningar) fyllas på
    # ...

if __name__ == "__main__":
    main()
