import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

# Autentisering och Google Sheets-koppling
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Förväntade rubriker
COLUMNS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan",
    "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb", "Grannar",
    "Nils kom", "Pv", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Vänner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    data = worksheet.get_all_records()

    if not data:
        df = pd.DataFrame(columns=COLUMNS)
        worksheet.insert_row(COLUMNS, index=1)
    else:
        df = pd.DataFrame(data)
        missing_cols = [col for col in COLUMNS if col not in df.columns]
        for col in missing_cols:
            df[col] = ""
        df = df[COLUMNS]
        worksheet.resize(rows=len(df) + 1, cols=len(COLUMNS))
        worksheet.update('A1', [COLUMNS])
    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.update([df.columns.tolist()] + df.values.tolist())

def main():
    st.title("Malin-appen 📊")
    worksheet, df = load_data()

    # Hantering av datumfel och startdatum
    if not df.empty:
        parsed_dates = pd.to_datetime(df["Dag"], errors="coerce")
        max_date = parsed_dates.max()
        today = (max_date + pd.Timedelta(days=1)).date() if pd.notnull(max_date) else datetime.date.today()
    else:
        today = datetime.date.today()

    with st.form("dataform"):
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
        ny_rad["Tid s"] = st.number_input("Tid s", value=0.0)
        ny_rad["Tid d"] = st.number_input("Tid d", value=0.0)
        ny_rad["Tid t"] = st.number_input("Tid t", value=0.0)
        ny_rad["Vila"] = st.number_input("Vila", value=0.0)
        ny_rad["Älskar"] = st.number_input("Älskar", value=0)
        ny_rad["Älsk tid"] = st.number_input("Älsk tid", value=0.0)
        ny_rad["Sover med"] = st.number_input("Sover med", value=0)
        ny_rad["Jobb"] = st.number_input("Jobb", value=0)
        ny_rad["Grannar"] = st.number_input("Grannar", value=0)
        ny_rad["Nils kom"] = st.number_input("Nils kom", value=0)
        ny_rad["Pv"] = st.number_input("Pv", value=0)
        ny_rad["Svarta"] = st.number_input("Svarta", value=0)

        submitted = st.form_submit_button("Spara rad")

    if submitted:
        # Beräkningar
        ny_rad["Summa s"] = ny_rad["Tid s"]
        ny_rad["Summa d"] = ny_rad["Tid d"]
        ny_rad["Summa t"] = ny_rad["Tid t"]
        ny_rad["Summa v"] = ny_rad["Vila"]
        ny_rad["Klockan"] = "07:00"

        ny_rad["Känner"] = ny_rad["Män"] + ny_rad["F"] + ny_rad["R"]
        ny_rad["Tid kille"] = ny_rad["Tid s"] + ny_rad["Tid d"]
        ny_rad["GB"] = ny_rad["Grannar"] + ny_rad["Jobb"]
        ny_rad["Filmer"] = ny_rad["Män"] + ny_rad["GB"]
        ny_rad["Pris"] = 19.99
        ny_rad["Intäkter"] = ny_rad["Pris"] * ny_rad["Filmer"]
        ny_rad["Malin"] = ny_rad["Älskar"] + ny_rad["Sover med"]
        ny_rad["Företag"] = ny_rad["Jobb"] + ny_rad["Pv"]
        ny_rad["Vänner"] = ny_rad["Känner"]
        ny_rad["Hårdhet"] = ny_rad["Älskar"] + ny_rad["Jobb"]

        # Fyll ut tomma fält om de saknas
        for col in COLUMNS:
            if col not in ny_rad:
                ny_rad[col] = ""

        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("Raden har sparats!")

    # Visa senaste 5 raderna
    if not df.empty:
        st.subheader("Senaste raderna")
        st.dataframe(df.tail(5), use_container_width=True)

if __name__ == "__main__":
    main()
