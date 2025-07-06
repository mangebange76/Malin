import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="MalinData Analys", layout="wide")
st.title("📊 MalinData\nAnalys")

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(
        json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
    )
    client = gspread.authorize(credentials)

    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    expected_headers = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s",
        "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v",
        "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb",
        "Grannar", "Tjej oj", "Nils kom", "Tid kille", "Filmer", "Pris",
        "Intäkter", "Malin", "Företag", "Hårdhet", "Svarta"
    ]

    current_values = worksheet.get_all_values()
    if not current_values:
        worksheet.append_row(expected_headers)
        return worksheet, pd.DataFrame(columns=expected_headers)

    headers = current_values[0]
    if headers != expected_headers:
        worksheet.clear()
        worksheet.append_row(expected_headers)
        return worksheet, pd.DataFrame(columns=expected_headers)

    if len(current_values) <= 1:
        return worksheet, pd.DataFrame(columns=expected_headers)

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    return worksheet, df

def calculate_metrics(df):
    try:
        df = df.fillna(0)

        max_jobb = df["Jobb"].max()
        max_grannar = df["Grannar"].max()
        max_pv = df["pv"].max() if "pv" in df.columns else 0
        max_nils_kom = df["Nils kom"].max()

        total_intakt = df["Intäkter"].sum()
        denominator = max_jobb + max_grannar + max_pv + max_nils_kom
        känner_tjänat = total_intakt / denominator if denominator > 0 else 0

        film_rows = df[df["Män"] > 0]
        snitt_film = (df["Män"].sum() + df["GB"].sum()) / len(film_rows) if len(film_rows) > 0 else 0

        malin_tjänat = df[["Män", "GB", "Älskar", "Sover med"]].sum().sum()

        total_män = df["Män"].sum()
        total_gb = df["GB"].sum()
        total_svarta = df["Svarta"].sum()
        total_vit_data = total_män + total_gb + total_svarta

        vita_procent = ((total_män + total_gb - total_svarta) / total_vit_data * 100) if total_vit_data > 0 else 0
        svarta_procent = (total_svarta / total_vit_data * 100) if total_vit_data > 0 else 0

        gb_numerator = df["GB"].sum()
        gb_snitt_denominator = max_jobb + max_grannar + max_pv + max_nils_kom
        gb_snitt = gb_numerator / gb_snitt_denominator if gb_snitt_denominator > 0 else 0

        return {
            "Känner tjänat": round(känner_tjänat, 2),
            "Snitt film": round(snitt_film, 2),
            "Malin tjänat": round(malin_tjänat, 2),
            "Vita (%)": round(vita_procent, 1),
            "Svarta (%)": round(svarta_procent, 1),
            "GB snitt": round(gb_snitt, 2),
            "Max Jobb": max_jobb,
            "Max Grannar": max_grannar,
            "Max pv": max_pv,
            "Max Nils kom": max_nils_kom
        }

    except Exception as e:
        st.error(f"Fel vid beräkning: {e}")
        return {}

def main():
    worksheet, df = load_data()

    if df.empty:
        st.warning("Ingen data ännu.")
        return

    st.subheader("📌 Nyckeltal")
    metrics = calculate_metrics(df)
    cols = st.columns(len(metrics))
    for col, (key, value) in zip(cols, metrics.items()):
        col.metric(label=key, value=value)

    st.subheader("📋 Data")
    st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
