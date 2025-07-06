import streamlit as st
import pandas as pd
import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Öppna kalkylblad
SHEET_NAME = "Malin"
WORKSHEET_NAME = "Data"
spreadsheet = client.open(SHEET_NAME)
try:
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

# Kolumnrubriker
COLUMNS = [
    "Dag", "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
    "Jobb", "Grannar", "pv", "Nils kom", "Nils natt", "Filmer", "Pris", "Svarta"
]

# Säkerställ rubriker
def ensure_headers():
    current_headers = worksheet.row_values(1)
    if current_headers != COLUMNS:
        worksheet.resize(rows=1)
        worksheet.insert_row(COLUMNS, 1)

# Ladda data
def load_data():
    ensure_headers()
    rows = worksheet.get_all_records()
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df

# Lägg till rad
def append_row(row):
    worksheet.append_row(row)

# Töm databasen
def clear_sheet():
    worksheet.clear()
    worksheet.append_row(COLUMNS)

# Gränssnitt
st.set_page_config(layout="wide")
st.title("📝 Daglig registrering – Malin")

df = load_data()

# Välj startdatum
if "start_date" not in st.session_state:
    st.session_state.start_date = datetime.date(2014, 5, 6)

start_date = st.date_input("Startdatum", st.session_state.start_date)
st.session_state.start_date = start_date

# Beräkna nästa dag
next_day = start_date + datetime.timedelta(days=len(df))

with st.form("input_form"):
    st.subheader(f"Registrering för: {next_day}")

    data = {
        "Dag": str(next_day),
        "Killar": st.number_input("Killar", 0),
        "F": st.number_input("F", 0),
        "R": st.number_input("R", 0),
        "Dm": st.number_input("Dm", 0),
        "Df": st.number_input("Df", 0),
        "Dr": st.number_input("Dr", 0),
        "3f": st.number_input("3f", 0),
        "3r": st.number_input("3r", 0),
        "3p": st.number_input("3p", 0),
        "Tid s": st.number_input("Tid s (sek)", 0),
        "Tid d": st.number_input("Tid d (sek)", 0),
        "Tid t": st.number_input("Tid t (sek)", 0),
        "Vila": st.number_input("Vila (sek)", 0),
        "Älskar": st.number_input("Älskar", 0),
        "Älsk tid": st.number_input("Älsk tid (min)", 0),
        "Sover med": st.number_input("Sover med", 0),
        "Jobb": st.number_input("Jobb", 0),
        "Grannar": st.number_input("Grannar", 0),
        "pv": st.number_input("pv", 0),
        "Nils kom": st.number_input("Nils kom", 0),
        "Nils natt": st.number_input("Nils natt (0/1)", 0),
        "Filmer": st.number_input("Filmer", 0),
        "Pris": st.number_input("Pris", 0),
        "Svarta": st.number_input("Svarta", 0),
    }

    submitted = st.form_submit_button("✅ Lägg till")
    if submitted:
        append_row([data[col] for col in COLUMNS])
        st.success("Raden har lagts till. Ladda om sidan för att se uppdaterade beräkningar.")

# Töm databasen
if st.button("🗑️ Töm databasen"):
    clear_sheet()
    st.warning("Databasen har tömts.")

# --- Beräkningar och presentation ---
if not df.empty:
    df["GB"] = df["Jobb"] + df["Grannar"] + df["pv"] + df["Nils kom"]
    df["Män"] = df["Killar"] + df["GB"]

    # Summor
    total_män = df["Killar"].sum()
    total_gb = df["GB"].sum()
    total_svarta = df["Svarta"].sum()

    vita_pct = round((total_män + total_gb - total_svarta) / (total_män + total_gb + total_svarta) * 100, 1) if (total_män + total_gb + total_svarta) else 0
    svarta_pct = round(total_svarta / (total_män + total_gb + total_svarta) * 100, 1) if (total_män + total_gb + total_svarta) else 0

    # Snitt film
    film_rows = df[df["Killar"] > 0]
    antal_filmer = len(film_rows)
    snitt_film = round((df["Killar"].sum() + df["GB"].sum()) / antal_filmer, 2) if antal_filmer else 0

    # Malin tjänat
    malin_tjänat = df["Killar"].sum() + df["GB"].sum() + df["Älskar"].sum() + df["Sover med"].sum()

    # Max-värden
    max_jobb = df["Jobb"].max()
    max_grannar = df["Grannar"].max()
    max_pv = df["pv"].max()
    max_nils = df["Nils kom"].max()
    känner_totalt = max_jobb + max_grannar + max_pv + max_nils
    känner_tjänat = round(malin_tjänat / känner_totalt, 2) if känner_totalt else 0

    gb_snitt = round(df["GB"].sum() / känner_totalt, 2) if känner_totalt else 0

    # Presentation
    st.subheader("📊 Nyckeltal")
    st.metric("Malin tjänat", malin_tjänat)
    st.metric("Snitt film", snitt_film)
    st.metric("GB snitt", gb_snitt)
    st.metric("Känner tjänat", känner_tjänat)
    st.metric("Vita (%)", f"{vita_pct}%")
    st.metric("Svarta (%)", f"{svarta_pct}%")

    st.caption(f"Max jobb: {max_jobb}, Max grannar: {max_grannar}, Max pv: {max_pv}, Max Nils kom: {max_nils}")
