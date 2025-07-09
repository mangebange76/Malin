import streamlit as st
import pandas as pd
import random
import math
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials

# Autentisering
import toml
secrets = toml.load(".streamlit/secrets.toml")
SHEET_URL = secrets["SHEET_URL"]
credentials_dict = secrets["GOOGLE_CREDENTIALS"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

# Kolumner
ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Tid T",
    "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj", "Svarta", "DeepT",
    "Sekunder", "Vila mun", "Varv", "Känner", "Män", "Summa singel", "Summa dubbel",
    "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille",
    "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar",
    "Aktiekurs", "Kompisar aktievärde"
]

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[ALL_COLUMNS]

def load_data():
    df = get_as_dataframe(worksheet, evaluate_formulas=True).fillna(0)
    df = df if not df.empty else pd.DataFrame(columns=ALL_COLUMNS)
    df = ensure_columns_exist(df)
    df = df.fillna(0)
    return df

def save_data(df):
    worksheet.clear()
    set_with_dataframe(worksheet, df)

def get_next_day(df):
    if df.empty:
        return 1
    return int(df["Dag"].max()) + 1

def veckodag_from_dag(dag):
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    return veckodagar[(dag - 1) % 7]

def visa_redigeringsformulär(rad, dag):
    with st.form(f"redigera_rad_{dag}"):
        ny_rad = rad.copy()
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                st.number_input(kolumn, value=int(ny_rad[kolumn]), disabled=True, key=f"{kolumn}_{dag}")
            elif isinstance(ny_rad[kolumn], (int, float)):
                step = 1.0 if isinstance(ny_rad[kolumn], float) else 1
                ny_rad[kolumn] = st.number_input(kolumn, value=float(ny_rad[kolumn]), step=step, key=f"{kolumn}_{dag}")
            else:
                ny_rad[kolumn] = st.text_input(kolumn, value=str(ny_rad[kolumn]), key=f"{kolumn}_{dag}")

        if st.form_submit_button("Spara redigerad rad"):
            return ny_rad
    return None

def get_next_day(df):
    if df.empty:
        return 1
    return int(df["Dag"].max()) + 1

def veckodag_from_dag(dag):
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    return veckodagar[(dag - 1) % 7]

# Kommentar: Av kompatibilitetsskäl behåller vi bara EN version av redigeringsformuläret
def visa_redigeringsformulär(rad, dag):
    with st.form(f"redigera_rad_{dag}"):
        ny_rad = rad.copy()
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                st.number_input(kolumn, value=int(ny_rad[kolumn]), disabled=True, key=f"{kolumn}_{dag}")
            elif isinstance(ny_rad[kolumn], (int, float)):
                step = 1.0 if isinstance(ny_rad[kolumn], float) else 1
                ny_rad[kolumn] = st.number_input(kolumn, value=float(ny_rad[kolumn]), step=step, key=f"{kolumn}_{dag}")
            else:
                ny_rad[kolumn] = st.text_input(kolumn, value=str(ny_rad[kolumn]), key=f"{kolumn}_{dag}")

        if st.form_submit_button("Spara redigerad rad"):
            return ny_rad
    return None

def lägg_till_rad(df, ny_rad):
    ny_rad = pd.DataFrame([ny_rad])
    df = pd.concat([df, ny_rad], ignore_index=True)
    df = update_calculations(df)
    save_data(df)
    return df

def slumpa_film(df, typ):
    dag = get_next_day(df)
    maxvärden = hämta_maxvärden(df)

    ny_rad = {kolumn: 0 for kolumn in ALL_COLUMNS}
    ny_rad["Dag"] = dag
    ny_rad["Veckodag"] = veckodag_from_dag(dag)

    if typ == "liten":
        ny_rad["Nya killar"] = random.randint(5, 20)
        ny_rad["Fitta"] = random.randint(2, 6)
        ny_rad["Röv"] = random.randint(2, 6)
        ny_rad["DM"] = random.randint(10, 20)
        ny_rad["DF"] = random.randint(10, 20)
        ny_rad["DA"] = random.randint(10, 20)
        ny_rad["TPP"] = random.randint(5, 10)
        ny_rad["TAP"] = random.randint(5, 10)
        ny_rad["TP"] = random.randint(5, 10)
    elif typ == "stor":
        ny_rad["Nya killar"] = random.randint(60, 200)
        ny_rad["Fitta"] = random.randint(10, 30)
        ny_rad["Röv"] = random.randint(10, 30)
        ny_rad["DM"] = random.randint(50, 100)
        ny_rad["DF"] = random.randint(50, 100)
        ny_rad["DA"] = random.randint(50, 100)
        ny_rad["TPP"] = random.randint(30, 80)
        ny_rad["TAP"] = random.randint(30, 80)
        ny_rad["TP"] = random.randint(30, 80)

    ny_rad["Älskar"] = 12
    ny_rad["Sover med"] = 1
    ny_rad["Tid S"] = 60
    ny_rad["Tid D"] = 70
    ny_rad["Tid trippel"] = 80
    ny_rad["Vila"] = 7

    ny_rad["Jobb"] = random.randint(3, maxvärden.get("Jobb", 3))
    ny_rad["Grannar"] = random.randint(3, maxvärden.get("Grannar", 3))
    ny_rad["Tjej PojkV"] = random.randint(3, maxvärden.get("Tjej PojkV", 3))
    ny_rad["Nils fam"] = random.randint(3, maxvärden.get("Nils fam", 3))

    ny_rad["Svarta"] = random.choice([0, ny_rad["Nya killar"]])
    ny_rad["DeepT"] = 0
    ny_rad["Sekunder"] = 0
    ny_rad["Vila mun"] = 0
    ny_rad["Varv"] = 0

    rad = visa_redigeringsformulär(ny_rad, dag)
    if rad:
        df = lägg_till_rad(df, rad)
        visa_varningar(rad)
    return df

def slumpa_vilodag(df, typ):
    dag = get_next_day(df)
    maxvärden = hämta_maxvärden(df)

    ny_rad = {kolumn: 0 for kolumn in ALL_COLUMNS}
    ny_rad["Dag"] = dag
    ny_rad["Veckodag"] = veckodag_from_dag(dag)
    ny_rad["Vila"] = 7

    if typ == "hemma":
        ny_rad["Älskar"] = 8
        ny_rad["Sover med"] = 1
        ny_rad["Tid S"] = 60
        ny_rad["Tid D"] = 70
        ny_rad["Tid trippel"] = 80
    elif typ == "jobb":
        ny_rad["Jobb"] = round(maxvärden.get("Jobb", 0) * 0.3)
        ny_rad["Grannar"] = round(maxvärden.get("Grannar", 0) * 0.3)
        ny_rad["Tjej PojkV"] = round(maxvärden.get("Tjej PojkV", 0) * 0.3)
        ny_rad["Nils fam"] = round(maxvärden.get("Nils fam", 0) * 0.3)
    elif typ == "helt":
        pass  # Redan nollor

    rad = visa_redigeringsformulär(ny_rad, dag)
    if rad:
        df = lägg_till_rad(df, rad)
        visa_varningar(rad)
    return df

def kopiera_största_raden(df):
    dag = get_next_day(df)
    if df.empty:
        return df
    största = df[df["Män"] == df["Män"].max()].iloc[0].copy()
    största["Dag"] = dag
    största["Veckodag"] = veckodag_from_dag(dag)

    rad = visa_redigeringsformulär(största, dag)
    if rad:
        df = lägg_till_rad(df, rad)
        visa_varningar(rad)
    return df

def visa_varningar(rad):
    summa_tid = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if summa_tid > 17:
        st.warning(f"⚠️ Summa tid är {summa_tid:.2f} timmar – det kan vara för mycket.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid per kille är {tid_kille:.2f} minuter – utanför rekommenderat intervall (9–15 min).")

def formulär_maxvärden(df):
    st.subheader("⚙️ Justera maxvärden (Dag = 0)")

    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        st.info("Ingen rad med Dag = 0 finns. Skapar ny.")
        ny_rad = {kol: 0 for kol in ALL_COLUMNS}
        ny_rad["Dag"] = 0
        ny_rad["Veckodag"] = "Maxvärden"
        dag0 = pd.DataFrame([ny_rad])
        df = pd.concat([dag0, df], ignore_index=True)

    rad = df[df["Dag"] == 0].iloc[0].to_dict()
    with st.form("maxvärden"):
        for kol in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            rad[kol] = st.number_input(f"Max {kol}", min_value=0, value=int(rad.get(kol, 0)))
        if st.form_submit_button("Spara maxvärden"):
            df.loc[df["Dag"] == 0, ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]] = (
                rad["Jobb"], rad["Grannar"], rad["Tjej PojkV"], rad["Nils fam"]
            )
            save_data(df)
            st.success("Maxvärden uppdaterade.")
    return df

def knappfunktioner(df):
    st.sidebar.subheader("➕ Lägg till rad")

    if st.sidebar.button("🎲 Slumpa film liten"):
        df = slumpa_film(df, "liten")
    if st.sidebar.button("🎲 Slumpa film stor"):
        df = slumpa_film(df, "stor")
    if st.sidebar.button("💤 Vilodag hemma"):
        df = slumpa_vilodag(df, "hemma")
    if st.sidebar.button("💼 Vilodag jobb"):
        df = slumpa_vilodag(df, "jobb")
    if st.sidebar.button("🛌 Vilodag helt"):
        df = slumpa_vilodag(df, "helt")
    if st.sidebar.button("📋 Kopiera största raden"):
        df = kopiera_största_raden(df)

    return df

def visa_huvudvy(df):
    st.subheader("📅 Alla dagar")
    if df.empty:
        st.info("Ingen data att visa ännu.")
        return

    visnings_df = df.copy()
    visnings_df = visnings_df[ALL_COLUMNS]

    # Tidsformat
    visnings_df["Summa tid"] = visnings_df["Summa tid"].round(2).astype(str) + " h"
    visnings_df["Tid kille"] = visnings_df["Tid kille"].round(2).astype(str) + " min"

    st.dataframe(visnings_df, use_container_width=True)

def main():
    st.set_page_config(page_title="MalinData", layout="wide")
    st.title("🧾 MalinData")

    df = load_data()
    df = ensure_columns_exist(df)
    df = update_calculations(df)

    menyval = st.sidebar.radio("Navigera", ["📅 Huvudvy", "📈 Statistik", "⚙️ Redigera maxvärden"])

    if menyval == "📅 Huvudvy":
        visa_huvudvy(df)
        df = knappfunktioner(df)
    elif menyval == "📈 Statistik":
        statistikvy(df)
    elif menyval == "⚙️ Redigera maxvärden":
        df = formulär_maxvärden(df)

    save_data(df)

if __name__ == "__main__":
    main()

def formulär_maxvärden(df):
    st.subheader("⚙️ Ange maxvärden för vänner (Dag = 0)")

    dag_0 = df[df["Dag"] == 0]
    if not dag_0.empty:
        rad = dag_0.iloc[0].copy()
    else:
        rad = {kol: 0 for kol in ALL_COLUMNS}
        rad["Dag"] = 0
        rad["Veckodag"] = "Max"

    with st.form("Maxvärden"):
        for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            rad[kolumn] = st.number_input(kolumn, value=int(rad.get(kolumn, 0)), step=1)

        submitted = st.form_submit_button("Spara maxvärden")
        if submitted:
            # Ta bort ev. befintlig rad med Dag = 0
            df = df[df["Dag"] != 0]
            ny_rad = pd.DataFrame([rad])
            df = pd.concat([ny_rad, df], ignore_index=True)
            df = update_calculations(df)
            save_data(df)
            st.success("Maxvärden sparade.")
    return df

def knappfunktioner(df):
    st.subheader("🧮 Funktioner")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎲 Slumpa film liten"):
            df = slumpa_film(df, typ="liten")
        if st.button("💤 Vilodag hemma"):
            df = slumpa_vilodag(df, "hemma")
    with col2:
        if st.button("🎲 Slumpa film stor"):
            df = slumpa_film(df, typ="stor")
        if st.button("🏢 Vilodag jobb"):
            df = slumpa_vilodag(df, "jobb")
    with col3:
        if st.button("📋 Kopiera största raden"):
            df = kopiera_största_raden(df)
        if st.button("😴 Vilodag helt"):
            df = slumpa_vilodag(df, "helt")

    return df
