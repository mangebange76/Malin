import streamlit as st
import pandas as pd
import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# Autentisering till Google Sheets via secrets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Öppna kalkylbladet
SHEET_NAME = "Malin"
WORKSHEET_NAME = "Data"
spreadsheet = client.open(SHEET_NAME)
try:
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

# Lista över kolumner
COLUMNS = [
    "Dag", "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
    "Jobb", "Grannar", "pv", "Nils kom", "Nils natt", "Filmer", "Pris", "Svarta"
]

# Ladda data
def load_data():
    rows = worksheet.get_all_records()
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows)
    return df

# Skriv en ny rad
def append_row(row):
    worksheet.append_row(row)

# Töm hela databasen
def clear_sheet():
    worksheet.clear()
    worksheet.append_row(COLUMNS)

# Sätt app-layout
st.set_page_config(layout="wide")
st.title("📋 Daglig registrering – Malin")

# Ladda data
df = load_data()

# Visa nyckeltal om data finns
if not df.empty:
    df["GB"] = df["Jobb"] + df["Grannar"] + df["pv"] + df["Nils kom"]
    df["Män"] = df["Killar"] + df["Jobb"] + df["Grannar"] + df["pv"] + df["Nils kom"]
    df["Summa s"] = (df["Killar"] + df["F"] + df["R"]) * df["Tid s"] + df["Vila"]
    df["Summa d"] = ((df["Dm"] + df["Df"] + df["Dr"]) * df["Tid d"] + df["Vila"]) * 2
    df["Summa t"] = ((df["3f"] + df["3r"] + df["3p"]) * df["Tid t"] + df["Vila"]) * 3
    df["Totaltid"] = df["Summa s"] + df["Summa d"] + df["Summa t"] + (df["Älskar"] * df["Älsk tid"] * 60)
    df["Tid kille"] = (df["Summa s"] + df["Summa d"] + df["Summa t"]) / df["Män"].replace(0, 1) / 60
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin"] = df["Intäkter"] * 0.01
    df["Företag"] = df["Intäkter"] * 0.40
    df["Känner (heta)"] = df["Intäkter"] * 0.59
    df["Hårdhet"] = (
        (df["R"] > 0).astype(int) +
        (df["Dm"] > 0).astype(int) +
        (df["Df"] > 0).astype(int) +
        (df["Dr"] > 0).astype(int)*2 +
        (df["3f"] > 0).astype(int)*3 +
        (df["3r"] > 0).astype(int)*5 +
        (df["3p"] > 0).astype(int)*4
    )

    # Sammanställningar
    total_intakt = df["Intäkter"].sum()
    total_malin = df["Malin"].sum()
    total_gb = df["GB"].sum()
    total_man = df["Män"].sum()
    total_svarta = df["Svarta"].sum()
    total_alskar = df["Älskar"].sum()
    total_sover = df["Sover med"].sum()

    max_jobb = df["Jobb"].max()
    max_grannar = df["Grannar"].max()
    max_pv = df["pv"].max()
    max_nils = df["Nils kom"].max()
    max_total = max_jobb + max_grannar + max_pv + max_nils

    kanner_tjanat = total_intakt / max_total if max_total else 0
    alskar_snitt = total_alskar / max_total if max_total else 0
    sover_snitt = total_sover / max_nils if max_nils else 0
    gb_snitt = total_gb / max_total if max_total else 0
    film_rows = df[df["Män"] > 0].shape[0]
    snitt_film = (total_man + total_gb) / film_rows if film_rows else 0
    malin_tjanat_snitt = total_man + total_gb + total_alskar + total_sover
    total_sum = total_man + total_gb + total_svarta
    vita_proc = (total_man + total_gb - total_svarta) / total_sum * 100 if total_sum else 0
    svarta_proc = total_svarta / total_sum * 100 if total_sum else 0

    # Visa nyckeltal
    st.markdown("## 📊 Summering")
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
    st.write(f"👷 Jobb: {max_jobb}")
    st.write(f"🏘️ Grannar: {max_grannar}")
    st.write(f"❤️ pv: {max_pv}")
    st.write(f"🧍 Nils kom: {max_nils}")
    st.write(f"🔢 Totalt känner: {max_total}")

# Töm databasen
with st.expander("🗑️ Töm databasen"):
    confirm = st.text_input("Skriv: JAG VILL TA BORT ALLT")
    if confirm == "JAG VILL TA BORT ALLT":
        if st.button("⚠️ Töm nu"):
            clear_sheet()
            st.success("Databasen har rensats.")
