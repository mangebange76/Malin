import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# Ladda data från Google Sheet
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    headers = worksheet.row_values(1)
    # Säkerställ att alla kolumner finns
    expected_columns = [  # Här listar vi bara några nyckelkolumner för exempel
        "Datum", "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA", "Älskar", "Sover med",
        "DeepT", "Grabbar", "Sekunder", "Varv", "Tid s", "Tid d", "Tid t", "Vila"
    ]
    for col in expected_columns:
        if col not in headers:
            headers.append(col)
            df[col] = 0
    worksheet.update("A1:1", [headers])  # Fixad syntax
    return worksheet, df

# Huvudfunktion för appen
def main():
    st.set_page_config(layout="wide")
    st.title("MalinData")

    worksheet, df = load_data()

    st.write("## Förhandsvisning av data")
    st.dataframe(df)

    if st.button("Skapa ny rad (test)"):
        new_row = {col: 0 for col in df.columns}
        new_row["Datum"] = datetime.today().strftime("%Y-%m-%d")
        new_row["Älskar"] = 8
        new_row["Sover med"] = 1
        new_row["Vila"] = 7
        new_row["Älsk tid"] = 30
        for col in new_row:
            if col in ["Älskar", "Sover med", "Vila", "Älsk tid", "Datum"]:
                continue
            if df[col].dtype in [int, float] and df[col].max() > 0:
                new_row[col] = random.randint(0, int(df[col].max()))
        worksheet.append_row([new_row.get(col, "") for col in df.columns])
        st.success("Ny rad skapad! Ladda om sidan för att se den.")

if __name__ == "__main__":
    main()
