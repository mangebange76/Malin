import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]

credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)

client = gspread.authorize(credentials)

# Ark-inställningar
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

def ensure_headers(worksheet, expected_headers):
    current_headers = worksheet.row_values(1)
    if current_headers != expected_headers:
        worksheet.update('A1', [expected_headers])

def load_data():
    try:
        spreadsheet = client.open(SHEET_NAME)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except Exception as e:
        st.error(f"Kunde inte öppna kalkylarket: {e}")
        st.stop()

    expected_headers = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
        "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med",
        "Känner", "Jobb", "Grannar", "Tjej oj", "Nils kom", "Tid kille", "Filmer", "Pris",
        "Intäkter", "Malin", "Företag", "Hårdhet", "Svarta", "GB"
    ]
    ensure_headers(worksheet, expected_headers)

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

def save_data(worksheet, df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def calculate_summary(df):
    df = df.copy()

    # Konvertera till numeriska värden där det går
    numeric_cols = ["Män", "GB", "Svarta", "Älskar", "Sover med", "Jobb", "Grannar", "Tjej oj", "Nils kom"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

    max_jobb = df["Jobb"].max()
    max_grannar = df["Grannar"].max()
    max_pv = df["Tjej oj"].max()
    max_nils = df["Nils kom"].max()

    total_känner = max_jobb + max_grannar + max_pv + max_nils
    total_intäkt = df["Intäkter"].sum() if "Intäkter" in df else 0

    känner_tjänat = total_intäkt / total_känner if total_känner > 0 else 0

    film_rows = df[df["Män"] > 0]
    total_film = len(film_rows)
    snitt_film = (df["Män"].sum() + df["GB"].sum()) / total_film if total_film > 0 else 0

    malin_tjänat = df["Män"].sum() + df["GB"].sum() + df["Älskar"].sum() + df["Sover med"].sum()

    sum_män = df["Män"].sum()
    sum_gb = df["GB"].sum()
    sum_svarta = df["Svarta"].sum()
    total_för_vit_svart = sum_män + sum_gb + sum_svarta

    vita_procent = ((sum_män + sum_gb - sum_svarta) / total_för_vit_svart * 100) if total_för_vit_svart > 0 else 0
    svarta_procent = (sum_svarta / total_för_vit_svart * 100) if total_för_vit_svart > 0 else 0

    return {
        "Max jobb": max_jobb,
        "Max grannar": max_grannar,
        "Max pv": max_pv,
        "Max Nils kom": max_nils,
        "Totalt känner": total_känner,
        "Känner tjänat": round(känner_tjänat, 2),
        "Snitt film": round(snitt_film, 2),
        "Malin tjänat": malin_tjänat,
        "Vita (%)": round(vita_procent, 2),
        "Svarta (%)": round(svarta_procent, 2)
    }

def main():
    st.set_page_config(page_title="MalinApp", layout="wide")
    st.title("📊 MalinApp")

    worksheet, df = load_data()

    st.markdown("### ➕ Lägg till ny rad")
    with st.form("add_row_form"):
        cols = st.columns(4)
        new_row = {}
        expected_columns = worksheet.row_values(1)

        for i, col in enumerate(expected_columns):
            if col == "Dag":
                new_row[col] = cols[i % 4].date_input(col, value=datetime.today()).strftime("%Y-%m-%d")
            else:
                new_row[col] = cols[i % 4].text_input(col)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(worksheet, df)
            st.success("Raden har sparats!")

    st.markdown("### 🧮 Beräkningar")
    summary = calculate_summary(df)
    for key, value in summary.items():
        st.metric(label=key, value=value)

    st.markdown("### 📋 Databasen")
    st.dataframe(df)

    if st.button("🗑️ Töm hela databasen"):
        df = df.iloc[0:0]
        save_data(worksheet, df)
        st.success("Databasen har rensats!")

if __name__ == "__main__":
    main()
