import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, time
import json
from google.oauth2 import service_account

# Autentisering från secrets
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# Google Sheet-info
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

# Rubriker
KOLUMNNAMN = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Älskar",
    "Sover med", "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2", "Tjej PojkV",
    "Tjej PojkV 2", "Nils fam", "Nils fam 2", "Totalt män", "Tid singel",
    "Tid dubbel", "Tid trippel", "Vila", "Summa singel", "Summa dubbel",
    "Summa trippel", "Summa vila", "Summa tid", "Klockan", "Tid kille",
    "Suger", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Vänner", "Hårdhet",
    "Känner 2"
]

# Ladda data och skapa rubrikrad om den saknas
def load_data():
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    if not data:
        worksheet.update([KOLUMNNAMN])
        df = pd.DataFrame(columns=KOLUMNNAMN)
    else:
        df = pd.DataFrame(data)
        if df.columns.tolist() != KOLUMNNAMN:
            worksheet.clear()
            worksheet.update([KOLUMNNAMN])
            df = pd.DataFrame(columns=KOLUMNNAMN)
    return worksheet, df

# Spara DataFrame till Google Sheets
def save_data(worksheet, df):
    worksheet.update([df.columns.tolist()] + df.fillna("").values.tolist())

# Summera maxvärden i vissa kolumner
def maxhistorik(df, kolumn):
    if kolumn in df.columns and not df[kolumn].isnull().all():
        return int(df[kolumn].max())
    return 0

# Huvudfunktion
def main():
    st.title("MalinApp – Inmatning")

    worksheet, df = load_data()

    # Felsökning: visa antal rader
    st.write("🔍 Antal rader i databasen:", len(df))

    with st.form("data_form"):
        today = datetime.today().date()
        datum = st.date_input("Datum", today, format="YYYY-MM-DD")

        män = st.number_input("Män", min_value=0, step=1)
        fi = st.number_input("Fi", min_value=0, step=1)
        rö = st.number_input("Rö", min_value=0, step=1)
        dm = st.number_input("DM", min_value=0, step=1)
        df_ = st.number_input("DF", min_value=0, step=1)
        dr = st.number_input("DR", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        älskar = st.number_input("Älskar", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)

        jobb = st.number_input("Jobb", min_value=0, step=1)
        grannar = st.number_input("Grannar", min_value=0, step=1)
        tjej_pojkv = st.number_input("Tjej PojkV", min_value=0, step=1)
        nils_fam = st.number_input("Nils fam", min_value=0, step=1)

        tid_singel = st.number_input("Tid singel (sekunder)", min_value=0, step=1)
        tid_dubbel = st.number_input("Tid dubbel (sekunder)", min_value=0, step=1)
        tid_trippel = st.number_input("Tid trippel (sekunder)", min_value=0, step=1)
        vila = st.number_input("Vila (sekunder)", min_value=0, step=1)

        submitted = st.form_submit_button("Spara")

    if submitted:
        ny_rad = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Män": män,
            "Fi": fi,
            "Rö": rö,
            "DM": dm,
            "DF": df_,
            "DR": dr,
            "TPP": tpp,
            "TAP": tap,
            "TPA": tpa,
            "Älskar": älskar,
            "Sover med": sover_med,
            "Jobb": jobb,
            "Grannar": grannar,
            "Tjej PojkV": tjej_pojkv,
            "Nils fam": nils_fam,
        }

        # Beräkningar
        ny_rad["Känner"] = jobb + grannar + tjej_pojkv + nils_fam
        ny_rad["Totalt män"] = män + ny_rad["Känner"]
        ny_rad["Tid singel"] = tid_singel
        ny_rad["Tid dubbel"] = tid_dubbel
        ny_rad["Tid trippel"] = tid_trippel
        ny_rad["Vila"] = vila

        ny_rad["Summa singel"] = tid_singel * ny_rad["Totalt män"]
        ny_rad["Summa dubbel"] = tid_dubbel * ny_rad["Totalt män"]
        ny_rad["Summa trippel"] = tid_trippel * ny_rad["Totalt män"]

        ny_rad["Summa vila"] = (
            ny_rad["Totalt män"] * vila +
            dm
