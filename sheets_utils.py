# sheets_utils.py
import json
import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

def get_client():
    """
    Returnerar ett gspread Spreadsheet-objekt öppnat via st.secrets:
    - st.secrets["GOOGLE_CREDENTIALS"]  (JSON-sträng eller dict/AttrDict)
    - st.secrets["SHEET_URL"]           (Google Sheets URL)
    """
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets saknas: GOOGLE_CREDENTIALS och/eller SHEET_URL.")

    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        # AttrDict/dict → vanlig dict
        creds_info = json.loads(json.dumps(dict(creds_raw)))

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(st.secrets["SHEET_URL"])
    return spreadsheet

def ensure_ws(ss, title: str, rows: int = 4000, cols: int = 100):
    """
    Säkerställ att ett kalkylblad (worksheet) med namnet 'title' finns.
    Returnerar worksheet-objektet (skapar om det saknas).
    """
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)
