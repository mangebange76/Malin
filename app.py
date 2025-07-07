import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
import gspread

st.set_page_config(page_title="Malins App", layout="wide")

# Funktion för autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# Ladda data från Google Sheets
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# Spara data till Google Sheets
def save_data(worksheet, df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# Hämta högsta värden
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if not df["Jobb"].isna().all() else 0,
        "Grannar 2": df["Grannar"].max() if not df["Grannar"].isna().all() else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if not df["Tjej PojkV"].isna().all() else 0,
        "Nils Fam 2": df["Nils Fam"].max() if not df["Nils Fam"].isna().all() else 0,
    }

# Lägg till ny rad
def add_row(df, new_row):
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Beräkna alla fält
def calculate_fields(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    max_values = get_max_values(df)
    df["Jobb 2"] = max_values["Jobb 2"]
    df["Grannar 2"] = max_values["Grannar 2"]
    df["Tjej PojkV 2"] = max_values["Tjej PojkV 2"]
    df["Nils Fam 2"] = max_values["Nils Fam 2"]
    df["Totalt Män"] = df["Män"] + df["Känner"]

    df["Summa Singel"] = (df["F"] + df["R"]) * df["Tid s"]
    df["Summa Dubbel"] = (df["Dm"] + df["Df"] + df["Dr"]) * df["Tid d"]
    df["Summa Trippel"] = (df["3f"] + df["3r"] + df["3p"]) * df["Tid t"]

    df["Summa Vila"] = (
        df["Totalt Män"] * df["Vila"]
        + (df["Dm"] + df["Df"] + df["Dr"]) * (df["Vila"] + 7)
        + (df["3f"] + df["3r"] + df["3p"]) * (df["Vila"] + 15)
    )

    df["Klockan"] = (
        df["Summa Singel"]
        + df["Summa Dubbel"]
        + df["Summa Dubbel"]
        + df["Summa Trippel"]
        + df["Summa Trippel"]
        + df["Summa Trippel"]
        + df["Summa Vila"]
        + df["Älskar"] * df["Älsk tid"]
    )

    df["Tid Kille"] = round(
        (
            df["Summa Singel"]
            + df["Summa Dubbel"] * 2
            + df["Summa Trippel"] * 3
        )
        / df["Totalt Män"]
        + 0.6 * (df["Summa Singel"] + df["Summa Dubbel"] + df["Summa Trippel"]) / df["Totalt Män"],
        2,
    ) / 60

    df["Filmer"] = (
        df["Män"]
        + df["F"]
        + df["R"]
        + df["R"]
        + df["Dm"]
        + df["Dm"]
        + df["Df"]
        + df["Df"]
        + df["Df"]
        + df["Dr"]
        + df["Dr"]
        + df["Dr"]
        + df["Dr"]
        + df["3f"] * 5
        + df["3r"] * 7
        + df["3p"] * 6
    )

    df["Filmer"] *= 1  # Hårdhet, sätts till 1

    df["Intäkter"] = df["Filmer"] * 19.99
    df["Malin lön"] = df["Intäkter"].apply(lambda x: min(x * 0.15, 1500))

    df["Vänner lön"] = df.apply(
        lambda row: row["Intäkter"] * 0.10 / (
            row["Jobb 2"] + row["Grannar 2"] + row["Tjej PojkV 2"] + row["Nils Fam 2"]
        ) if (
            row["Jobb 2"] + row["Grannar 2"] + row["Tjej PojkV 2"] + row["Nils Fam 2"]
        ) > 0 else 0,
        axis=1,
    )

    return df

# Spara app-koden i fil
with open("/mnt/data/full_app_malin.py", "w") as f:
    f.write(full_app_code)

"/mnt/data/full_app_malin.py"
