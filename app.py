import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
WORKSHEET_NAME = "Blad1"

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scope)
    client = gspread.authorize(creds)
    return client

def skapa_rubriker(worksheet):
    rubriker = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
        "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
    ]
    if worksheet.row_count < 1 or worksheet.row_values(1) != rubriker:
        worksheet.clear()
        worksheet.append_row(rubriker)

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    skapa_rubriker(worksheet)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(df.columns.tolist())
    for row in df.itertuples(index=False):
        worksheet.append_row(list(row))

def ny_rad_df(df):
    if df.empty:
        return datetime.today().strftime("%Y-%m-%d")
    sista_datum = pd.to_datetime(df["Dag"], errors='coerce').max()
    nytt_datum = sista_datum + timedelta(days=1) if pd.notnull(sista_datum) else datetime.today()
    return nytt_datum.strftime("%Y-%m-%d")

def skapa_tom_rad():
    return {
        "Män": 0, "F": 0, "R": 0, "Dm": 0, "Df": 0, "Dr": 0,
        "3f": 0, "3r": 0, "3p": 0, "Tid s": 0, "Tid d": 0, "Tid t": 0, "Vila": 0,
        "Älskar": 0, "Älsk tid": 0, "Sover med": 0, "Jobb": 0, "Grannar": 0, "Tjej PojkV": 0,
        "Nils Fam": 0, "Svarta": 0
    }

def main():
    st.title("MalinData App")

    worksheet, df = load_data()

    if not df.empty:
        st.subheader("Nuvarande data")
        st.dataframe(df)

    st.subheader("Lägg till ny rad")

    ny_dag = ny_rad_df(df)
    st.write(f"Dagens datum: **{ny_dag}**")

    with st.form("dataform"):
        ny_data = skapa_tom_rad()
        for kolumn in ny_data:
            ny_data[kolumn] = st.number_input(kolumn, min_value=0, step=1)

        submitted = st.form_submit_button("Lägg till rad")
        if submitted:
            ny_data["Dag"] = ny_dag
            df = pd.concat([df, pd.DataFrame([ny_data])], ignore_index=True)
            save_data(worksheet, df)
            st.success("Raden sparades!")

    st.subheader("Snabbknappar för vilodagar")
    if st.button("Vilodag jobb"):
        if df.empty:
            st.warning("Ingen data finns för att hämta maxvärden.")
        else:
            rad = {
                "Dag": ny_rad_df(df),
                "Jobb": round(df["Jobb"].max() * 0.5),
                "Grannar": round(df["Grannar"].max() * 0.5),
                "Tjej PojkV": round(df["Tjej PojkV"].max() * 0.5),
                "Nils Fam": round(df["Nils Fam"].max() * 0.5),
                "Älskar": 12,
                "Sover med": 1
            }
            for kol in skapa_tom_rad().keys():
                rad.setdefault(kol, 0)
            df = pd.concat([df, pd.DataFrame([rad])], ignore_index=True)
            save_data(worksheet, df)
            st.success("Vilodag jobb sparad!")

    if st.button("Vilodag hemma"):
        rad = {
            "Dag": ny_rad_df(df),
            "Jobb": 3,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils Fam": 3,
            "Älskar": 6
        }
        for kol in skapa_tom_rad().keys():
            rad.setdefault(kol, 0)
        df = pd.concat([df, pd.DataFrame([rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("Vilodag hemma sparad!")

if __name__ == "__main__":
    main()
