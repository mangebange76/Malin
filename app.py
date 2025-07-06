import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import json

# Konstanter
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Autentisering
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=SCOPES
)
client = gspread.authorize(credentials)

# Rubriker i rätt ordning
HEADERS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med",
    "Känner", "Jobb", "Grannar", "Nils kom", "Pv", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Vänner", "Hårdhet", "Svarta", "GB"
]

# Ladda data
def load_data():
    try:
        spreadsheet = client.open(SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Spreadsheet '{SHEET_NAME}' hittades inte.")
        st.stop()

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

    data = worksheet.get_all_records()
    if not data or list(data[0].keys()) != HEADERS:
        worksheet.clear()
        worksheet.append_row(HEADERS)

    df = pd.DataFrame(data)
    return worksheet, df

# Spara data
def save_data(worksheet, df):
    df = df.copy()
    df["Dag"] = df["Dag"].astype(str)  # Fix för JSON-fel
    worksheet.clear()
    worksheet.update([df.columns.tolist()] + df.values.tolist())

# Appens huvudfunktion
def main():
    st.title("MalinApp – Datainmatning & Analys")

    worksheet, df = load_data()

    # Beräkna dagens datum (nästa dag)
    today = (pd.to_datetime(df["Dag"], errors='coerce').max() + pd.Timedelta(days=1)).date() if not df.empty else datetime.date.today()

    with st.form("data_form"):
        ny_rad = {}
        ny_rad["Dag"] = st.date_input("Dag", today)
        ny_rad["Män"] = st.number_input("Män", value=0)
        ny_rad["F"] = st.number_input("F", value=0)
        ny_rad["R"] = st.number_input("R", value=0)
        ny_rad["Dm"] = st.number_input("Dm", value=0)
        ny_rad["Df"] = st.number_input("Df", value=0)
        ny_rad["Dr"] = st.number_input("Dr", value=0)
        ny_rad["3f"] = st.number_input("3f", value=0)
        ny_rad["3r"] = st.number_input("3r", value=0)
        ny_rad["3p"] = st.number_input("3p", value=0)
        ny_rad["Tid s"] = st.number_input("Tid s", value=0)
        ny_rad["Tid d"] = st.number_input("Tid d", value=0)
        ny_rad["Tid t"] = st.number_input("Tid t", value=0)
        ny_rad["Vila"] = st.number_input("Vila", value=0)
        ny_rad["Älskar"] = st.number_input("Älskar", value=0)
        ny_rad["Älsk tid"] = st.number_input("Älsk tid", value=0)
        ny_rad["Sover med"] = st.number_input("Sover med", value=0)
        ny_rad["Jobb"] = st.number_input("Jobb", value=0)
        ny_rad["Grannar"] = st.number_input("Grannar", value=0)
        ny_rad["Nils kom"] = st.number_input("Nils kom", value=0)
        ny_rad["Pv"] = st.number_input("Pv", value=0)
        ny_rad["Svarta"] = st.number_input("Svarta", value=0)

        submitted = st.form_submit_button("Spara rad")

    if submitted:
        ny_rad["Summa s"] = ny_rad["Tid s"]
        ny_rad["Summa d"] = ny_rad["Tid d"]
        ny_rad["Summa t"] = ny_rad["Tid t"]
        ny_rad["Summa v"] = ny_rad["Vila"]
        ny_rad["Klockan"] = "07:00"

        # Beräkningar
        ny_rad["Känner"] = ny_rad["Män"] + ny_rad["F"] + ny_rad["R"]
        ny_rad["Tid kille"] = ny_rad["Tid s"] + ny_rad["Tid d"] + ny_rad["Tid t"]
        ny_rad["GB"] = ny_rad["Älskar"] + ny_rad["Sover med"]
        ny_rad["Filmer"] = ny_rad["Män"] + ny_rad["GB"]
        ny_rad["Pris"] = 19.99
        ny_rad["Intäkter"] = ny_rad["Pris"] * ny_rad["Filmer"]
        ny_rad["Malin"] = ny_rad["Älsk tid"]
        ny_rad["Företag"] = ny_rad["Jobb"]
        ny_rad["Vänner"] = ny_rad["Grannar"]
        ny_rad["Hårdhet"] = ny_rad["Känner"] + ny_rad["Pv"]

        # Fyll i alla fält som kan saknas
        for col in HEADERS:
            if col not in ny_rad:
                ny_rad[col] = 0

        ny_df = pd.DataFrame([ny_rad])[HEADERS]
        df = pd.concat([df, ny_df], ignore_index=True)
        save_data(worksheet, df)
        st.success("✅ Raden har sparats.")

    # Visa nuvarande data
    st.subheader("Senaste data")
    st.dataframe(df.tail(10))

if __name__ == "__main__":
    main()
