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

# Ladda data
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# Lägg till ny rad
def append_row(row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    worksheet.append_row([row_dict.get(col, 0) for col in worksheet.row_values(1)])

# Spara ändrad rad
def update_row(index, row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    worksheet.update(f"A{index + 2}", [[row_dict.get(col, 0) for col in worksheet.row_values(1)]])

# Huvudfunktion
def main():
    st.title("Malin App")

    worksheet, df = load_data()

    if df.empty:
        st.warning("Databladet är tomt.")
        return

    st.subheader("Förhandsvisning av data med beräkningar")

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, 1)
    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]
    df["Suger"] = 0.6 * (df["Summa tid"] / df["Totalt män"].replace(0, 1))
    df["Tid kille"] = df["Tid s"] + (df["Tid d"] * 2) + (df["Tid t"] * 3) + df["Suger"]
    df["Filmer"] = (df["Män"] + df["F"] + df["R"] +
                    df["Dm"] * 2 + df["Df"] * 2 + df["Dr"] * 3 +
                    df["TPP"] * 4 + df["TAP"] * 6 + df["TPA"] * 5) * df["Hårdhet"]
    df["Intäkter"] = df["Filmer"] * 19.99
    df["Malins lön"] = df["Intäkter"].apply(lambda x: min(1500, x * 0.05))
    df["Företagets lön"] = df["Intäkter"] * 0.4
    df["Vänners lön"] = df["Intäkter"] - df["Malins lön"] - df["Företagets lön"]

    def beräkna_hårdhet(row):
        if row["Män"] == 0:
            return 0
        h = 1
        if row["Dm"] > 0: h += 2
        if row["Df"] > 0: h += 2
        if row["Dr"] > 0: h += 4
        if row["TPP"] > 0: h += 4
        if row["TAP"] > 0: h += 6
        if row["TPA"] > 0: h += 5
        return h

    df["Hårdhet"] = df.apply(beräkna_hårdhet, axis=1)

    st.dataframe(df)

if __name__ == "__main__":
    main()
