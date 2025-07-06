import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# Titeln på sidan
st.set_page_config(page_title="MalinData", layout="wide")
st.title("📊 MalinData")
st.subheader("Analys")

# Autentisering med Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Öppna kalkylblad och blad
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"
spreadsheet = client.open(SHEET_NAME)
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

# Förväntade rubriker (uppdatera vid behov)
HEADERS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v",
    "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb", "Grannar",
    "Tjej oj", "Nils kom", "pv", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Känner 2", "Hårdhet", "Svarta", "GB"
]

def load_data():
    # Kontrollera rubriker i kalkylarket
    current_headers = worksheet.row_values(1)
    if current_headers != HEADERS:
        worksheet.clear()
        worksheet.update("A1", [HEADERS])
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    return df

def save_data(df):
    worksheet.clear()
    worksheet.update("A1", [df.columns.tolist()] + df.values.tolist())

def show_metrics(df):
    if df.empty:
        st.warning("Ingen data ännu.")
        return

    # Sammanställning av nyckeltal
    total_män = df["Män"].sum()
    total_gb = df["GB"].sum()
    total_svarta = df["Svarta"].sum()
    total_filmer = df[df["Män"] > 0].shape[0]

    vita_procent = round((total_män + total_gb - total_svarta) / (total_män + total_gb + total_svarta) * 100, 1) if (total_män + total_gb + total_svarta) > 0 else 0
    svarta_procent = round(total_svarta / (total_män + total_gb + total_svarta) * 100, 1) if (total_män + total_gb + total_svarta) > 0 else 0
    snitt_film = round((total_män + total_gb) / total_filmer, 2) if total_filmer > 0 else 0
    malin_tjanst_snitt = df["Män"].sum() + df["GB"].sum() + df["Älskar"].sum() + df["Sover med"].sum()

    max_job = df["Jobb"].max() if not df["Jobb"].empty else 0
    max_grannar = df["Grannar"].max() if not df["Grannar"].empty else 0
    max_pv = df["pv"].max() if "pv" in df.columns and not df["pv"].empty else 0
    max_nils = df["Nils kom"].max() if not df["Nils kom"].empty else 0
    total_intakt = df["Intäkter"].sum()
    kanner_tjanat = round(total_intakt / (max_job + max_grannar + max_pv + max_nils), 2) if (max_job + max_grannar + max_pv + max_nils) > 0 else 0

    # Visa nyckeltal
    st.metric("Vita (%)", f"{vita_procent}%")
    st.metric("Svarta (%)", f"{svarta_procent}%")
    st.metric("Snitt film", snitt_film)
    st.metric("Malin tjänst snitt", malin_tjanst_snitt)
    st.metric("Känner tjänat", kanner_tjanat)

    with st.expander("Maxvärden (för Känner tjänat)"):
        st.write(f"Max Jobb: {max_job}")
        st.write(f"Max Grannar: {max_grannar}")
        st.write(f"Max pv: {max_pv}")
        st.write(f"Max Nils kom: {max_nils}")

def add_entry():
    st.subheader("Lägg till ny rad")
    with st.form("entry_form"):
        cols = st.columns(len(HEADERS))
        values = [cols[i].text_input(header, "") for i, header in enumerate(HEADERS)]
        submitted = st.form_submit_button("Spara")
        if submitted:
            new_row = pd.DataFrame([values], columns=HEADERS)
            df = load_data()
            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.success("Raden har sparats.")

def main():
    df = load_data()
    show_metrics(df)
    st.divider()
    add_entry()

if __name__ == "__main__":
    main()
