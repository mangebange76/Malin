import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

# Autentisering mot Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope)
client = gspread.authorize(credentials)

# Google Sheets info
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit"
WORKSHEET_NAME = "Blad1"

# Rubrikrader
HEADERS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner",
    "Jobb", "Grannar", "Nils kom", "Pv", "Tid kille", "Filmer", "Pris", "Intäkter", "Malin", "Företag",
    "Vänner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    data = worksheet.get_all_records()

    if not data:
        worksheet.update([HEADERS])
        df = pd.DataFrame(columns=HEADERS)
    else:
        df = pd.DataFrame(data)

        # Säkerställ att alla rubriker finns
        for col in HEADERS:
            if col not in df.columns:
                df[col] = ""

        df = df[HEADERS]

    return worksheet, df

def save_data(worksheet, df):
    df = df.fillna("")
    worksheet.update([df.columns.tolist()] + df.astype(str).values.tolist())

def main():
    st.title("MalinApp")

    worksheet, df = load_data()

    st.subheader("Lägg till ny rad")

    with st.form("inmatning"):
        today = (pd.to_datetime(df["Dag"], errors='coerce').max() + pd.Timedelta(days=1)).date() if not df.empty else datetime.date.today()

        ny_rad = {}
        ny_rad["Dag"] = st.date_input("Dag", today)

        # Inmatningsfält
        for col in [
            "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
            "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "Nils kom", "Pv", "Svarta"
        ]:
            ny_rad[col] = st.number_input(col, value=0)

        submitted = st.form_submit_button("Spara")

    if submitted:
        # Beräkningar
        ny_rad["Summa s"] = ny_rad["Tid s"] * ny_rad["Män"]
        ny_rad["Summa d"] = ny_rad["Tid d"] * ny_rad["F"]
        ny_rad["Summa t"] = ny_rad["Tid t"] * ny_rad["R"]
        ny_rad["Summa v"] = ny_rad["Summa s"] + ny_rad["Summa d"] + ny_rad["Summa t"]
        ny_rad["Klockan"] = "07:00"
        ny_rad["Känner"] = ny_rad["Jobb"] + ny_rad["Grannar"] + ny_rad["Pv"] + ny_rad["Nils kom"]
        ny_rad["Tid kille"] = ny_rad["Män"] * ny_rad["Tid s"]
        ny_rad["GB"] = ny_rad["Älskar"] + ny_rad["Sover med"]
        ny_rad["Filmer"] = ny_rad["Män"] + ny_rad["GB"]
        ny_rad["Pris"] = 19.99
        ny_rad["Intäkter"] = ny_rad["Filmer"] * ny_rad["Pris"]
        ny_rad["Malin"] = ny_rad["Älskar"] + ny_rad["Älsk tid"]
        ny_rad["Företag"] = ny_rad["Jobb"]
        ny_rad["Vänner"] = ny_rad["Känner"]
        ny_rad["Hårdhet"] = ny_rad["GB"] * 2

        for col in HEADERS:
            if col not in ny_rad:
                ny_rad[col] = ""

        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("Raden har sparats!")

    st.subheader("Data i kalkylbladet")
    st.dataframe(df)

if __name__ == "__main__":
    main()
