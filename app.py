# app.py – Del 1: Importer och Google Sheets-anslutning

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="MalinData App", layout="wide")

# Autentisering mot Google Sheets via secrets.toml
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(credentials)

# Öppna kalkylarket
sheet = client.open_by_url(st.secrets["SHEET_URL"])
worksheet = sheet.worksheet("Blad1")

# Läs data till DataFrame
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Säkerställ att vissa kolumner finns (kompletteras i Del 2)

# Del 2: Kolumnhantering och maxvärdeskontroll

def ensure_columns_exist(df):
    required_columns = [
        "Veckodag", "Dag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
        "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Vila",
        "Jobb", "Grannar", "Tjej PojkV", "Nils familj", "Svarta", "Känner", "Män",
        "Summa singel", "Summa dubbel", "Summa trippel", "Summa tid", "Suger",
        "Tid kille", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar", "Hårdhet"
    ]
    for col in required_columns:
        if col not in df.columns:
            df[col] = 0
    return df

def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils familj": 0}
    rad = maxrad.iloc[0]
    return {
        "Jobb": rad.get("Jobb", 0),
        "Grannar": rad.get("Grannar", 0),
        "Tjej PojkV": rad.get("Tjej PojkV", 0),
        "Nils familj": rad.get("Nils familj", 0),
    }

def validera_maxvarden(ny_rad, maxvarden):
    for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
        if ny_rad[kolumn] > maxvarden[kolumn]:
            st.error(f"{kolumn} överskrider maxvärdet {maxvarden[kolumn]}! Uppdatera Dag = 0 först.")
            return False
    return True

# Del 3: Beräkningsfunktion

def update_calculations(df):
    df = ensure_columns_exist(df)

    # Veckodag: Dag 1 = Lördag
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    df["Veckodag"] = df["Dag"].apply(lambda x: veckodagar[(x - 1) % 7] if x > 0 else "")

    # Känner = Jobb + Grannar + Tjej PojkV + Nils familj
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils familj"]

    # Män = Nya killar + Känner
    df["Män"] = df["Nya killar"] + df["Känner"]

    # Summa singel = Tid S × Män
    df["Summa singel"] = df["Tid S"] * df["Män"]

    # Summa dubbel = Tid D × (DM + DF + DA)
    df["Summa dubbel"] = df["Tid D"] * (df["DM"] + df["DF"] + df["DA"])

    # Tid T sätts till 180 sekunder (kan justeras senare)
    df["Tid T"] = 180

    # Summa trippel = Tid T × (TPP + TAP + TP)
    df["Summa trippel"] = df["Tid T"] * (df["TPP"] + df["TAP"] + df["TP"])

    # Summa tid = singel + dubbel + trippel
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    # Suger = 60% av Summa tid / Män (undvik division med 0)
    df["Suger"] = df.apply(lambda row: 0 if row["Män"] == 0 else 0.6 * row["Summa tid"] / row["Män"], axis=1)

    # Tid kille = Tid S + (Tid D * 2 × dubbel) + (Tid T * 3 × trippel) + Suger
    df["Tid kille"] = (
        df["Tid S"] +
        df["Tid D"] * 2 * (df["DM"] + df["DF"] + df["DA"]) +
        df["Tid T"] * 3 * (df["TPP"] + df["TAP"] + df["TP"]) +
        df["Suger"]
    )

    # Filmer = avrundat antal = Män / 2 (exempel, kan justeras)
    df["Filmer"] = (df["Män"] / 2).round().astype(int)

    # Pris = alltid 39.99
    df["Pris"] = 39.99

    # Intäkter = Filmer × Pris
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön = 1% av Intäkter, max 700
    df["Malin lön"] = df["Intäkter"].apply(lambda x: min(x * 0.01, 700))

    # Summering av Dag = 0 för Kompisar-beräkning
    dag0_sum = df[df["Dag"] == 0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
    df["Kompisar"] = df.apply(
        lambda row: 0 if dag0_sum == 0 else (row["Intäkter"] - row["Malin lön"]) / dag0_sum,
        axis=1
    )

    # Hårdhet = (Summa tid + Tid kille) / Män (exempelberäkning)
    df["Hårdhet"] = df.apply(
        lambda row: 0 if row["Män"] == 0 else (row["Summa tid"] + row["Tid kille"]) / row["Män"],
        axis=1
    )

    return df

# Del 4: Inmatningsformulär

st.header("Ny inmatning")

# Tvinga omvandling till heltal för att undvika TypeError
df["Dag"] = pd.to_numeric(df["Dag"], errors="coerce").fillna(0).astype(int)

# Filtrera bort Dag = 0 för att räkna fram nästa dag
dagar = df[df["Dag"] > 0]["Dag"]
ny_dag = 1 if dagar.empty else dagar.max() + 1

with st.form("ny_rad_form"):
    st.subheader(f"Ny rad för Dag {ny_dag}")

    nya_killar = st.number_input("Nya killar", min_value=0, step=1)
    fitta = st.number_input("Fitta", min_value=0, step=1)
    rov = st.number_input("Röv", min_value=0, step=1)
    dm = st.number_input("DM", min_value=0, step=1)
    df_f = st.number_input("DF", min_value=0, step=1)
    da = st.number_input("DA", min_value=0, step=1)
    tpp = st.number_input("TPP", min_value=0, step=1)
    tap = st.number_input("TAP", min_value=0, step=1)
    tp = st.number_input("TP", min_value=0, step=1)
    alskar = st.number_input("Älskar", min_value=0, step=1)
    sover_med = st.number_input("Sover med", min_value=0, step=1)
    tid_s = st.number_input("Tid S (sekunder)", min_value=0, step=1)
    tid_d = st.number_input("Tid D (sekunder)", min_value=0, step=1)
    vila = st.number_input("Vila (sekunder)", min_value=0, step=1)
    jobb = st.number_input("Jobb", min_value=0, step=1)
    grannar = st.number_input("Grannar", min_value=0, step=1)
    pojkv = st.number_input("Tjej PojkV", min_value=0, step=1)
    nils = st.number_input("Nils familj", min_value=0, step=1)
    svarta = st.number_input("Svarta", min_value=0, step=1)

    submitted = st.form_submit_button("Spara rad")

    if submitted:
        ny_rad = {
            "Dag": ny_dag,
            "Nya killar": nya_killar,
            "Fitta": fitta,
            "Röv": rov,
            "DM": dm,
            "DF": df_f,
            "DA": da,
            "TPP": tpp,
            "TAP": tap,
            "TP": tp,
            "Älskar": alskar,
            "Sover med": sover_med,
            "Tid S": tid_s,
            "Tid D": tid_d,
            "Vila": vila,
            "Jobb": jobb,
            "Grannar": grannar,
            "Tjej PojkV": pojkv,
            "Nils familj": nils,
            "Svarta": svarta
        }

        maxvarden = hamta_maxvarden(df)
        if validera_maxvarden(ny_rad, maxvarden):
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            df = update_calculations(df)
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            st.success("Raden sparades!")

# Del 5: Huvudfunktion och appstart

def main():
    global df
    df = ensure_columns_exist(df)
    df = update_calculations(df)

    # Visa senaste raderna (exkludera Dag = 0)
    st.subheader("Senaste inmatningar")
    st.dataframe(df[df["Dag"] > 0].sort_values("Dag", ascending=False), use_container_width=True)

# Kör appen
if __name__ == "__main__":
    main()
