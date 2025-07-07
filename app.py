import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import random

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# Laddar in data
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# Skriver rubriker + data om de saknas
def update_sheet_if_needed(worksheet, df, expected_columns):
    current_cols = worksheet.row_values(1)
    if current_cols != expected_columns:
        worksheet.update("A1", [expected_columns])
    if df.empty:
        return pd.DataFrame(columns=expected_columns)
    return df

# Spara ny rad till Google Sheet
def save_new_row(worksheet, new_row):
    worksheet.append_row(new_row)

# UI-komponent för att lägga till ny rad
def add_row_ui(worksheet, df, columns):
    st.subheader("➕ Lägg till ny rad")

    new_data = {}
    for col in columns:
        if col == "Dag":
            new_data[col] = st.date_input("Datum", datetime.today()).strftime("%Y-%m-%d")
        elif col in ["Älskar"]:
            new_data[col] = 8
        elif col in ["Sover med"]:
            new_data[col] = 1
        elif col == "Vila":
            new_data[col] = 7
        elif col == "Älsk tid":
            new_data[col] = 30
        elif col in ["Snitt"]:
            new_data[col] = 0.0
        else:
            new_data[col] = st.number_input(col, value=0, step=1)

    if st.button("💾 Spara rad"):
        new_row = [new_data[col] for col in columns]
        save_new_row(worksheet, new_row)
        st.success("✅ Ny rad tillagd! Ladda om sidan för att se den.")
        st.stop()

def main():
    st.set_page_config(page_title="MalinData", layout="wide")
    st.title("📊 MalinData")

    # Definiera alla kolumner som ska finnas
    expected_columns = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Tid s", "Tid d", "Tid t", "Vila", "Älsk tid", "DeepT", "Grabbar",
        "Sekunder", "Varv"
    ]

    worksheet, df = load_data()
    df = update_sheet_if_needed(worksheet, df, expected_columns)

    if df.empty:
        st.warning("🔹 Inga data ännu – fyll i nedan för att börja!")
        add_row_ui(worksheet, df, expected_columns)
    else:
        st.success("✅ Data inläst!")
        st.dataframe(df)
        add_row_ui(worksheet, df, expected_columns)

if __name__ == "__main__":
    main()
