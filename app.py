import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="Malin App", layout="wide")

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Obligatoriska kolumner
ALL_COLUMNS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t",
    "Vila", "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid",
    "Sover med", "Känner", "Jobb", "Grannar", "Tjej oj", "Nils kom", "Tid kille", "Filmer",
    "Pris", "Intäkter", "Malin", "Företag", "Hårdhet", "Svarta", "GB"
]

# Ladda data från kalkylarket
def load_data():
    spreadsheet = client.open(SHEET_NAME)
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    if df.empty or list(df.columns) != ALL_COLUMNS:
        worksheet.clear()
        worksheet.append_row(ALL_COLUMNS)
        df = pd.DataFrame(columns=ALL_COLUMNS)

    return worksheet, df

# Spara ny rad
def append_row(worksheet, row_data):
    worksheet.append_row(row_data, value_input_option="USER_ENTERED")

# Rensa databasen
def clear_database(worksheet):
    worksheet.clear()
    worksheet.append_row(ALL_COLUMNS)

# Beräkningar
def calculate_metrics(df):
    df_filled = df.fillna(0)
    for col in ["Män", "GB", "Älskar", "Sover med", "Jobb", "Grannar", "Nils kom", "Pris", "Intäkter", "Svarta"]:
        df_filled[col] = pd.to_numeric(df_filled[col], errors='coerce').fillna(0)

    max_job = df_filled["Jobb"].max()
    max_grannar = df_filled["Grannar"].max()
    max_pv = df_filled["Tjej oj"].max()
    max_nils = df_filled["Nils kom"].max()
    total_max_sum = max_job + max_grannar + max_pv + max_nils

    total_income = df_filled["Intäkter"].sum()
    känner_tjänat = total_income / total_max_sum if total_max_sum > 0 else 0

    antal_filmer = (df_filled["Män"] > 0).sum()
    snitt_film = ((df_filled["Män"] + df_filled["GB"]).sum() / antal_filmer) if antal_filmer > 0 else 0

    malin_tjänat = df_filled["Män"].sum() + df_filled["GB"].sum() + df_filled["Älskar"].sum() + df_filled["Sover med"].sum()

    total_män = df_filled["Män"].sum()
    total_gb = df_filled["GB"].sum()
    total_svarta = df_filled["Svarta"].sum()
    total_sum = total_män + total_gb + total_svarta
    vita_pct = ((total_män + total_gb - total_svarta) / total_sum * 100) if total_sum > 0 else 0
    svarta_pct = (total_svarta / total_sum * 100) if total_sum > 0 else 0

    return {
        "Max jobb": max_job,
        "Max grannar": max_grannar,
        "Max pv": max_pv,
        "Max Nils kom": max_nils,
        "Totalt känner": total_max_sum,
        "Känner tjänat": round(känner_tjänat, 2),
        "Snitt film": round(snitt_film, 2),
        "Malin tjänat": malin_tjänat,
        "Vita (%)": round(vita_pct, 1),
        "Svarta (%)": round(svarta_pct, 1)
    }

# Gränssnitt
def main():
    st.title("📊 Malin App")

    worksheet, df = load_data()

    with st.expander("➕ Lägg till ny rad"):
        new_data = {}
        for col in ALL_COLUMNS:
            if col == "Dag":
                new_data[col] = st.date_input("Dag").strftime("%Y-%m-%d")
            else:
                new_data[col] = st.text_input(col, value="0")

        if st.button("Spara rad"):
            row = [new_data.get(col, "") for col in ALL_COLUMNS]
            append_row(worksheet, row)
            st.success("Raden sparades.")

    st.divider()

    if st.button("🧹 Töm databasen"):
        clear_database(worksheet)
        st.warning("Databasen är nu tom.")

    st.divider()

    st.subheader("📈 Nyckeltal")
    metrics = calculate_metrics(df)
    for k, v in metrics.items():
        st.metric(label=k, value=v)

    st.subheader("📋 Databasens innehåll")
    st.dataframe(df)

if __name__ == "__main__":
    main()
