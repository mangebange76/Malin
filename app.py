# app.py
import streamlit as st
import datetime
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Autentisering till Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Ange namn på Google Sheet
SPREADSHEET_NAME = "Din Appdata"
WORKSHEET_NAME = "Data"
sh = gc.open(SPREADSHEET_NAME)
try:
    worksheet = sh.worksheet(WORKSHEET_NAME)
except gspread.WorksheetNotFound:
    worksheet = sh.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

# Definiera kolumner
COLUMNS = [
    "Dag", "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Klockan",
    "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "pv", "Nils kom",
    "Nils natt", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Känner (heta)",
    "GB", "Män", "Tid kille", "Hårdhet", "Svarta"
]

# Ladda data
def load_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    return df[COLUMNS]

# Spara rad
def append_row(row):
    worksheet.append_row(row)

# Töm databas
def clear_data():
    worksheet.resize(rows=1)
    worksheet.update('A1:AJ1', [COLUMNS])

# Räkna maxvärden för känna-snittsberäkningar
def get_max_values(df):
    return {
        "Jobb": df["Jobb"].max(),
        "Grannar": df["Grannar"].max(),
        "pv": df["pv"].max(),
        "Nils kom": df["Nils kom"].max()
    }

# Layout
st.set_page_config(layout="wide")
st.title("📊 Daglig registrering och summering")

df = load_data()

# Toppsummering
if not df.empty:
    total_intakt = df["Intäkter"].sum()
    total_malin = df["Malin"].sum()
    total_killar = df["Killar"].sum()
    total_gb = df["GB"].sum()
    total_svarta = df["Svarta"].sum()
    total_man = df["Män"].sum()
    total_alskar = df["Älskar"].sum()
    total_sover = df["Sover med"].sum()

    max_vals = get_max_values(df)
    max_total = sum(max_vals.values())
    kanner_tjanat = total_intakt / max_total if max_total > 0 else 0
    alskar_snitt = total_alskar / max_total if max_total > 0 else 0
    sover_snitt = total_sover / max_vals["Nils kom"] if max_vals["Nils kom"] > 0 else 0
    gb_snitt = total_gb / max_total if max_total > 0 else 0
    snitt_film = (total_man + total_gb) / df[df["Män"] > 0].shape[0] if df[df["Män"] > 0].shape[0] > 0 else 0
    malin_tjanat_snitt = total_man + total_gb + total_alskar + total_sover
    vita_proc = (total_man + total_gb - total_svarta) / (total_man + total_gb + total_svarta) * 100 if (total_man + total_gb + total_svarta) > 0 else 0
    svarta_proc = total_svarta / (total_man + total_gb + total_svarta) * 100 if (total_man + total_gb + total_svarta) > 0 else 0

    st.markdown("### 📈 Nyckeltal")
    st.write(f"💰 Total Malin tjänat: {total_malin:.2f} kr")
    st.write(f"🔥 Känner tjänat: {kanner_tjanat:.2f} kr")
    st.write(f"💖 Malin tjänat snitt: {malin_tjanat_snitt}")
    st.write(f"🎞️ Snitt film: {snitt_film:.2f}")
    st.write(f"❤️ Älskar-snitt: {alskar_snitt:.2f}")
    st.write(f"😴 Sover med-snitt: {sover_snitt:.2f}")
    st.write(f"📦 Total GB: {total_gb}")
    st.write(f"➗ GB-snitt: {gb_snitt:.2f}")
    st.write(f"⚪ Vita: {vita_proc:.2f} %")
    st.write(f"⚫ Svarta: {svarta_proc:.2f} %")

    st.markdown("### 🧩 Maxvärden")
    for k, v in max_vals.items():
        st.write(f"{k}: {v}")

# Bekräftad tömning
with st.expander("🗑️ Töm databasen"):
    confirm = st.text_input("Skriv exakt: JAG VILL TA BORT ALLT")
    if confirm == "JAG VILL TA BORT ALLT":
        if st.button("⚠️ TÖM NU"):
            clear_data()
            st.success("Databasen är tömd.")
