import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="MalinAppen", layout="wide")

# --- Autentisering ---
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# --- Ladda data ---
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# --- Spara ny rad ---
def append_row(worksheet, row):
    worksheet.append_row(row)

# --- Slumpa ny rad ---
def skapa_slumprad(df):
    def slumpa(kolumn):
        if kolumn in df.columns and pd.api.types.is_numeric_dtype(df[kolumn]):
            if df[kolumn].dropna().empty:
                return 0
            return random.randint(int(df[kolumn].min()), int(df[kolumn].max()))
        return 0

    ny_rad = {
        "MÃ¤n": slumpa("MÃ¤n"),
        "F": slumpa("F"),
        "R": slumpa("R"),
        "Dm": slumpa("Dm"),
        "Df": slumpa("Df"),
        "Dr": slumpa("Dr"),
        "3f": slumpa("3f"),
        "3r": slumpa("3r"),
        "3p": slumpa("3p"),
        "Tid s": slumpa("Tid s"),
        "Tid d": slumpa("Tid d"),
        "Tid t": slumpa("Tid t"),
        "Vila": 7,
        "Ãlskar": 8,
        "Ãlsk tid": 30,
        "Sover med": 1,
        "Jobb": slumpa("Jobb"),
        "Grannar": slumpa("Grannar"),
        "Tjej PojkV": slumpa("Tjej PojkV"),
        "Nils Fam": slumpa("Nils Fam"),
        "Svarta": slumpa("Svarta"),
        "Dag": datetime.today().strftime("%Y-%m-%d")
    }
    return ny_rad

# --- LÃ¤gg till vila jobb ---
def skapa_vilodag_jobbrad(df):
    def maxv(kol):
        return int(df[kol].max()) if kol in df.columns else 0

    return {
        "MÃ¤n": 0, "F": 0, "R": 0, "Dm": 0, "Df": 0, "Dr": 0,
        "3f": 0, "3r": 0, "3p": 0, "Tid s": 0, "Tid d": 0, "Tid t": 0,
        "Vila": 7, "Ãlskar": 12, "Ãlsk tid": 30, "Sover med": 1,
        "Jobb": round(maxv("Jobb") * 0.5), "Grannar": round(maxv("Grannar") * 0.5),
        "Tjej PojkV": round(maxv("Tjej PojkV") * 0.5), "Nils Fam": round(maxv("Nils Fam") * 0.5),
        "Svarta": 0, "Dag": datetime.today().strftime("%Y-%m-%d")
    }

# --- LÃ¤gg till vila hemma ---
def skapa_vilodag_hemma():
    return {
        "MÃ¤n": 0, "F": 0, "R": 0, "Dm": 0, "Df": 0, "Dr": 0,
        "3f": 0, "3r": 0, "3p": 0, "Tid s": 0, "Tid d": 0, "Tid t": 0,
        "Vila": 7, "Ãlskar": 6, "Ãlsk tid": 30, "Sover med": 0,
        "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3,
        "Svarta": 0, "Dag": datetime.today().strftime("%Y-%m-%d")
    }

# --- Streamlit UI ---
def main():
    st.title("MalinAppen â Full Version")

    worksheet, df = load_data()

    st.subheader("LÃ¤gg till ny data manuellt")
    with st.form("lÃ¤gg_till"):
        col1, col2, col3 = st.columns(3)
        ny_post = {
            "MÃ¤n": col1.number_input("MÃ¤n", value=0),
            "F": col1.number_input("F", value=0),
            "R": col1.number_input("R", value=0),
            "Dm": col1.number_input("Dm", value=0),
            "Df": col2.number_input("Df", value=0),
            "Dr": col2.number_input("Dr", value=0),
            "3f": col2.number_input("3f", value=0),
            "3r": col3.number_input("3r", value=0),
            "3p": col3.number_input("3p", value=0),
            "Tid s": col3.number_input("Tid s", value=0),
            "Tid d": col1.number_input("Tid d", value=0),
            "Tid t": col1.number_input("Tid t", value=0),
            "Vila": col1.number_input("Vila", value=7),
            "Ãlskar": col2.number_input("Ãlskar", value=8),
            "Ãlsk tid": col2.number_input("Ãlsk tid", value=30),
            "Sover med": col2.number_input("Sover med", value=1),
            "Jobb": col3.number_input("Jobb", value=0),
            "Grannar": col3.number_input("Grannar", value=0),
            "Tjej PojkV": col3.number_input("Tjej PojkV", value=0),
            "Nils Fam": col3.number_input("Nils Fam", value=0),
            "Svarta": col3.number_input("Svarta", value=0),
            "Dag": datetime.today().strftime("%Y-%m-%d")
        }

        submitted = st.form_submit_button("LÃ¤gg till rad")
        if submitted:
            append_row(worksheet, list(ny_post.values()))
            st.success("Ny rad tillagd!")

    st.subheader("Snabbkommandon")
    if st.button("SlumpmÃ¤ssig rad"):
        ny = skapa_slumprad(df)
        append_row(worksheet, list(ny.values()))
        st.success("Slumprad tillagd!")

    if st.button("Vilodag jobb"):
        ny = skapa_vilodag_jobbrad(df)
        append_row(worksheet, list(ny.values()))
        st.success("Vilodag jobb tillagd!")

    if st.button("Vilodag hemma"):
        ny = skapa_vilodag_hemma()
        append_row(worksheet, list(ny.values()))
        st.success("Vilodag hemma tillagd!")

    st.subheader("Data")
    st.dataframe(df)

if __name__ == "__main__":
    main()
