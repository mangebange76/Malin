import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_URL = st.secrets["SHEET_URL"]

# --- Google Sheets auth ---
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# --- Load data from Google Sheets ---
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(SHEET_URL)
    worksheet = sheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# --- Save row to Google Sheets ---
def append_row(worksheet, row_dict):
    worksheet.append_row(list(row_dict.values()))

# --- Maxvärden för kolumner ---
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
        "Nils Fam 2": df["Nils Fam"].max() if "Nils Fam" in df else 0,
    }

# --- Beräkningar för varje rad ---
def beräkna_rad(rad, maxvärden):
    känner = rad["Jobb"] + rad["Grannar"] + rad["Tjej PojkV"] + rad["Nils Fam"]
    totalt_män = rad["Män"] + känner

    # Summering av relationstyper
    summa_singel = (rad["F"] + rad["R"]) * rad["Tid s"]
    summa_dubbel = (rad["Dm"] + rad["Df"] + rad["Dr"]) * rad["Tid d"]
    summa_trippel = (rad["3f"] + rad["3r"] + rad["3p"]) * rad["Tid t"]

    vila_tid = (
        totalt_män * rad["Vila"] +
        (rad["Dm"] + rad["Df"] + rad["Dr"]) * (rad["Vila"] + 7) +
        (rad["3f"] + rad["3r"] + rad["3p"]) * (rad["Vila"] + 15)
    )

    tid_kille = (summa_singel + 2 * summa_dubbel + 3 * summa_trippel) / totalt_män if totalt_män else 0
    suger = (summa_singel + summa_dubbel + summa_trippel) * 0.6 / totalt_män if totalt_män else 0
    tid_kille += suger
    tid_kille_min = round(tid_kille / 60, 2)

    filmer = (
        (rad["Män"] + rad["F"] + rad["R"] + 2 * rad["Dm"] + 3 * rad["Df"] +
         4 * rad["Dr"] + 5 * rad["3f"] + 7 * rad["3r"] + 6 * rad["3p"]) * rad["Hårdhet"]
    )
    intäkter = round(filmer * 19.99, 2)
    klockslag = datetime(2025, 1, 1, 7, 0) + timedelta(minutes=(tid_kille + rad["Älskar"] * rad["Älsk tid"]) / 60)

    return {
        "Känner": känner,
        "Totalt män": totalt_män,
        "Tid kille": tid_kille_min,
        "Filmer": filmer,
        "Intäkter": intäkter,
        "Klockan": klockslag.strftime("%H:%M")
    }

# --- Presentera huvudvy ---
def huvudvy(df, maxvärden):
    df_beräknad = df.copy()
    summeringar = {"Män": 0, "Känner": 0, "Sover med": 0, "Älskar": 0, "Kompisar": 0, "Svarta": 0}
    for col in summeringar: df_beräknad[col] = df.get(col, 0)

    df_beräknad["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df_beräknad["Totalt män"] = df["Män"] + df_beräknad["Känner"]
    summeringar["Män"] = df_beräknad["Män"].sum()
    summeringar["Känner"] = df_beräknad["Känner"].sum()
    summeringar["Sover med"] = df_beräknad["Sover med"].sum()
    summeringar["Älskar"] = df_beräknad["Älskar"].sum()
    summeringar["Kompisar"] = maxvärden["Jobb 2"] + maxvärden["Grannar 2"] + maxvärden["Tjej PojkV 2"] + maxvärden["Nils Fam 2"]
    summeringar["Svarta"] = df_beräknad["Svarta"].sum()

    snitt_män_känner = (summeringar["Män"] + summeringar["Känner"]) / len(df) if len(df) else 0
    gangb = summeringar["Känner"] / summeringar["Kompisar"] if summeringar["Kompisar"] else 0
    älskat = summeringar["Älskar"] / summeringar["Kompisar"] if summeringar["Kompisar"] else 0
    vita = (summeringar["Män"] - summeringar["Svarta"]) / summeringar["Män"] * 100 if summeringar["Män"] else 0
    svarta = summeringar["Svarta"] / summeringar["Män"] * 100 if summeringar["Män"] else 0
    sover_beräknad = summeringar["Sover med"] / maxvärden["Nils Fam 2"] if maxvärden["Nils Fam 2"] else 0

    st.markdown("### Huvudvy")
    st.write(f"Totalt män: {summeringar['Män']}")
    st.write(f"Malin lön: {min(round(df_beräknad['Intäkter'].sum() * 0.15, 2), 1500)} USD")
    st.write(f"Vänner lön: {round(df_beräknad['Intäkter'].sum() * 0.85 / summeringar['Kompisar'], 2)} USD")
    st.write(f"Snitt Män + Känner: {round(snitt_män_känner, 2)} per rad")
    st.write(f"GangB: {round(gangb, 2)}")
    st.write(f"Älskat: {round(älskat, 2)}")
    st.write(f"Vita: {round(vita, 2)} %")
    st.write(f"Svarta: {round(svarta, 2)} %")
    st.write(f"Sover med (beräknad): {round(sover_beräknad, 2)}")

# --- Appens huvudfunktion ---
def main():
    st.title("Malin-appen")

    worksheet, df = load_data()
    maxvärden = get_max_values(df)

    huvudvy(df, maxvärden)

    if st.button("Slumpa rad"):
        ny_rad = {
            "Dag": datetime.now().date().isoformat(),
            "Män": random.randint(1, df["Män"].max()),
            "F": random.randint(0, df["F"].max()),
            "R": random.randint(0, df["R"].max()),
            "Dm": random.randint(0, df["Dm"].max()),
            "Df": random.randint(0, df["Df"].max()),
            "Dr": random.randint(0, df["Dr"].max
