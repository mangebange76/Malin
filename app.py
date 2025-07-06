import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="MalinData", layout="wide")

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Ark och blad
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Förväntade kolumner
EXPECTED_COLUMNS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v", "Klockan",
    "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb", "Grannar", "Tjej oj", "Nils kom",
    "Män", "Tid kille", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Känner", "Hårdhet",
    "pv", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    data = worksheet.get_all_records()

    # Säkerställ att rubrikerna är rätt – skapa om nödvändigt
    current_headers = worksheet.row_values(1)
    if current_headers != EXPECTED_COLUMNS:
        worksheet.resize(rows=1)  # ta bort gamla data
        worksheet.insert_row(EXPECTED_COLUMNS, index=1)

    df = pd.DataFrame(data)

    # Säkerställ att alla kolumner finns, även om nya har lagts till
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = 0

    return worksheet, df

def calculate_metrics(df):
    # Summera maxvärden
    max_job = df["Jobb"].max()
    max_grannar = df["Grannar"].max()
    max_pv = df["pv"].max()
    max_nils = df["Nils kom"].max()

    total_känner = max_job + max_grannar + max_pv + max_nils

    # Känner tjänat
    total_intäkt = df["Intäkter"].sum()
    känner_tjänat = total_intäkt / total_känner if total_känner > 0 else 0

    # Älskar snitt
    älskar_snitt = df["Älskar"].sum() / total_känner if total_känner > 0 else 0

    # Sover med snitt (endast max Nils kom)
    sover_snitt = df["Sover med"].sum() / max_nils if max_nils > 0 else 0

    # GB-kolumn: Jobb + Grannar + pv + Nils kom per rad
    df["GB"] = df["Jobb"] + df["Grannar"] + df["pv"] + df["Nils kom"]
    gb_total = df["GB"].sum()
    gb_snitt = gb_total / total_känner if total_känner > 0 else 0

    # Snitt film
    film_rader = df[df["Män"] > 0]
    antal_filmer = len(film_rader)
    snitt_film = ((film_rader["Män"] + film_rader["GB"]).sum()) / antal_filmer if antal_filmer > 0 else 0

    # Malin tjänat = män + GB + älskar + sover med
    malin_tjänat = df["Män"].sum() + df["GB"].sum() + df["Älskar"].sum() + df["Sover med"].sum()

    # Vita / Svarta %
    summa_män = df["Män"].sum()
    summa_gb = df["GB"].sum()
    summa_svarta = df["Svarta"].sum()
    total_vita_svarta = summa_män + summa_gb + summa_svarta

    vita_procent = ((summa_män + summa_gb - summa_svarta) / total_vita_svarta * 100) if total_vita_svarta > 0 else 0
    svarta_procent = (summa_svarta / total_vita_svarta * 100) if total_vita_svarta > 0 else 0

    return {
        "Max Jobb": max_job,
        "Max Grannar": max_grannar,
        "Max pv": max_pv,
        "Max Nils kom": max_nils,
        "Total känner": total_känner,
        "Känner tjänat": round(känner_tjänat, 2),
        "Älskar snitt": round(älskar_snitt, 2),
        "Sover med snitt": round(sover_snitt, 2),
        "GB snitt": round(gb_snitt, 2),
        "Snitt film": round(snitt_film, 2),
        "Malin tjänat": round(malin_tjänat, 2),
        "Vita (%)": round(vita_procent, 2),
        "Svarta (%)": round(svarta_procent, 2)
    }

def main():
    st.title("📊 MalinData Analys")

    worksheet, df = load_data()

    if df.empty:
        st.warning("Ingen data ännu.")
        return

    metrics = calculate_metrics(df)

    # Visa nyckeltal
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Känner tjänat", metrics["Känner tjänat"])
        st.metric("Älskar snitt", metrics["Älskar snitt"])
        st.metric("Sover med snitt", metrics["Sover med snitt"])
    with col2:
        st.metric("GB snitt", metrics["GB snitt"])
        st.metric("Snitt film", metrics["Snitt film"])
        st.metric("Malin tjänat", metrics["Malin tjänat"])
    with col3:
        st.metric("Vita (%)", f"{metrics['Vita (%)']}%")
        st.metric("Svarta (%)", f"{metrics['Svarta (%)']}%")
        st.metric("Total känner", metrics["Total känner"])

    st.subheader("📈 Maxvärden")
    st.write(f"Jobb: {metrics['Max Jobb']} | Grannar: {metrics['Max Grannar']} | pv: {metrics['Max pv']} | Nils kom: {metrics['Max Nils kom']}")

    st.subheader("🧾 Rådata från databasen")
    st.dataframe(df)

if __name__ == "__main__":
    main()
