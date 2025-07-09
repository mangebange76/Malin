import streamlit as st
import pandas as pd
import random
import math
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import toml

# Autentisering
secrets = toml.load(".streamlit/secrets.toml")
SHEET_URL = secrets["SHEET_URL"]
credentials_dict = secrets["GOOGLE_CREDENTIALS"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

# Kolumnstruktur
ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Tid T",
    "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj", "Svarta", "DeepT",
    "Sekunder", "Vila mun", "Varv", "Känner", "Män", "Summa singel", "Summa dubbel",
    "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille",
    "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar",
    "Aktiekurs", "Kompisar aktievärde", "Malin ROI"
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

def hämta_maxvärden(df):
    rad0 = df[df["Dag"] == 0]
    if rad0.empty:
        return {}
    return rad0.iloc[0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].to_dict()

def validera_maxvarden(rad, maxv):
    for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
        if rad[kolumn] > maxv.get(kolumn, 9999):
            st.error(f"Värdet för {kolumn} ({rad[kolumn]}) överskrider max ({maxv[kolumn]}).")
            return False
    return True

def visa_varningar(rad):
    summa_tid = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if summa_tid > 17:
        st.warning(f"⚠️ Summa tid är {summa_tid:.2f} timmar – det kan vara för mycket.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid per kille är {tid_kille:.2f} minuter – utanför rekommenderat intervall (9–15 min).")

def update_calculations(df):
    maxvärden = hämta_maxvärden(df)
    for i, rad in df.iterrows():
        dag = int(rad.get("Dag", 0))
        if dag == 0:
            continue  # hoppa över maxvärdesraden

        # Veckodag
        df.at[i, "Veckodag"] = veckodag_from_dag(dag)

        # Känner
        känner = rad["Jobb"] + rad["Grannar"] + rad["Tjej PojkV"] + rad["Nils familj"]
        df.at[i, "Känner"] = känner

        # Män
        män = rad["Nya killar"] + känner
        df.at[i, "Män"] = män if män != 0 else 1  # för att undvika div/0

        # Snitt
        snitt = rad["DeepT"] / df.at[i, "Män"] if df.at[i, "Män"] != 0 else 0
        df.at[i, "Snitt"] = snitt

        # Tid mun
        tid_mun = (snitt * rad["Sekunder"] + rad["Vila mun"]) * rad["Varv"]
        df.at[i, "Tid mun"] = tid_mun

        # Summa singel
        vila_singel = rad["Vila"] * (män + rad["Fitta"] + rad["Röv"])
        summa_singel = rad["Tid S"] * män + vila_singel
        df.at[i, "Summa singel"] = summa_singel

        # Summa dubbel
        dubbel_antal = rad["DM"] + rad["DF"] + rad["DA"]
        vila_dubbel = (rad["Vila"] + 8) * dubbel_antal
        summa_dubbel = rad["Tid D"] * dubbel_antal + vila_dubbel
        df.at[i, "Summa dubbel"] = summa_dubbel

        # Summa trippel
        trippel_antal = rad["TPP"] + rad["TAP"] + rad["TP"]
        vila_trippel = (rad["Vila"] + 15) * trippel_antal
        summa_trippel = rad["Tid T"] * trippel_antal + vila_trippel
        df.at[i, "Summa trippel"] = summa_trippel

        # Summa tid (timmar)
        total_tid = summa_singel + summa_dubbel + summa_trippel + tid_mun + (rad["Älskar"] * 1800) + (rad["Sover med"] * 1800)
        df.at[i, "Summa tid"] = total_tid / 3600

        # Suger
        suger = (summa_singel + summa_dubbel + summa_trippel) * 0.6 / män
        df.at[i, "Suger"] = suger / 60  # till minuter

        # Tid per kille
        tid_kille = (
            rad["Tid S"]
            + rad["Tid D"] * 2
            + rad["Tid T"] * 3
            + suger * 60
            + tid_mun
            + (1800 * rad["Älskar"])
            + (1800 * rad["Sover med"])
        ) / män
        df.at[i, "Tid kille"] = tid_kille / 60  # till minuter

        # Hårdhet
        hårdhet = 0
        if rad["Nya killar"] > 0:
            hårdhet += 1
        if rad["DM"] > 0:
            hårdhet += 2
        if rad["DF"] > 0:
            hårdhet += 3
        if rad["DA"] > 0:
            hårdhet += 4
        if rad["TPP"] > 0:
            hårdhet += 5
        if rad["TAP"] > 0:
            hårdhet += 7
        if rad["TP"] > 0:
            hårdhet += 6
        df.at[i, "Hårdhet"] = hårdhet

        # Filmer
        filmer = (
            män
            + rad["Fitta"]
            + rad["Röv"]
            + rad["DM"] * 2
            + rad["DF"] * 2
            + rad["DA"] * 3
            + rad["TPP"] * 4
            + rad["TAP"] * 6
            + rad["TP"] * 5
        ) * hårdhet
        df.at[i, "Filmer"] = filmer

        # Pris
        pris = 39.99
        df.at[i, "Pris"] = pris

        # Intäkter
        intäkter = filmer * pris
        df.at[i, "Intäkter"] = intäkter

        # Malin lön (1% av intäkter, max 700)
        malin_lön = min(intäkter * 0.01, 700)
        df.at[i, "Malin lön"] = malin_lön

        # Kompisar = (Intäkter - Malin lön) / vänner (från Dag 0)
        vänner = (
            maxvärden.get("Jobb", 0)
            + maxvärden.get("Grannar", 0)
            + maxvärden.get("Tjej PojkV", 0)
            + maxvärden.get("Nils fam", 0)
        )
        kompisar = (intäkter - malin_lön) / vänner if vänner else 0
        df.at[i, "Kompisar"] = kompisar

        # Kompisars aktievärde
        aktiekurs = df[df["Dag"] != 0]["Intäkter"].iloc[-1] / 5000 if not df[df["Dag"] != 0].empty else 0
        df.at[i, "Aktiekurs"] = aktiekurs
        df.at[i, "Kompisar aktievärde"] = round((5000 * aktiekurs) / vänner, 2) if vänner else 0

    return df

def statistikvy(df):
    st.subheader("📊 Statistik")

    if df.empty:
        st.info("Ingen data att visa.")
        return

    df_utan_max = df[df["Dag"] != 0].copy()

    if df_utan_max.empty:
        st.warning("Ingen giltig data (förutom Dag=0) finns ännu.")
        return

    totalt_filmer = df_utan_max["Filmer"].sum()
    totalt_intäkter = df_utan_max["Intäkter"].sum()
    totalt_malin_lön = df_utan_max["Malin lön"].sum()
    totalt_alskar = df_utan_max["Älskar"].sum()
    totalt_sovermed = df_utan_max["Sover med"].sum()
    totalt_nyakillar = df_utan_max["Nya killar"].sum()
    totalt_känner = df_utan_max["Känner"].sum()

    st.metric("🎬 Totalt antal filmer", int(totalt_filmer))
    st.metric("💰 Totala intäkter (USD)", f"${totalt_intäkter:,.2f}")
    st.metric("🧍 Totalt antal män", int(totalt_nyakillar + totalt_känner))
    st.metric("🛏️ Totalt älskar", int(totalt_alskar))
    st.metric("🧸 Totalt sover med", int(totalt_sovermed))

    # Kompisars aktievärde (sista kursen × 5000)
    if not df_utan_max.empty:
        sista_aktiekurs = df_utan_max["Aktiekurs"].iloc[-1]
        totalt_vänner = (
            df[df["Dag"] == 0][["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()
            if not df[df["Dag"] == 0].empty else 0
        )
        totalt_kompisar_aktievärde = round((5000 * sista_aktiekurs), 2)
        per_person = round(totalt_kompisar_aktievärde / totalt_vänner, 2) if totalt_vänner else 0

        st.metric("📈 Kompisars aktievärde (5000 aktier)", f"${totalt_kompisar_aktievärde:,.2f}")
        st.metric("👥 Aktievärde per kompis", f"${per_person:,.2f}")

    # Malin ROI per man
    tot_män = totalt_alskar + totalt_sovermed + totalt_nyakillar + totalt_känner
    roi = totalt_malin_lön / tot_män if tot_män else 0
    st.metric("💡 Malin ROI per man", f"${roi:.2f} USD")

def hämta_maxvärden(df):
    dag_0 = df[df["Dag"] == 0]
    if dag_0.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    rad = dag_0.iloc[0]
    return {
        "Jobb": int(rad.get("Jobb", 0)),
        "Grannar": int(rad.get("Grannar", 0)),
        "Tjej PojkV": int(rad.get("Tjej PojkV", 0)),
        "Nils fam": int(rad.get("Nils fam", 0)),
    }

def update_calculations(df):
    for i, rad in df.iterrows():
        dag = int(rad["Dag"])
        if dag == 0:
            continue  # Hoppa över maxvärdesraden

        # Vänner = dag 0 total
        maxrad = df[df["Dag"] == 0]
        vänner = (
            maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()
            if not maxrad.empty else 0
        )
        känner = (
            rad.get("Jobb", 0)
            + rad.get("Grannar", 0)
            + rad.get("Tjej PojkV", 0)
            + rad.get("Nils fam", 0)
        )
        män = rad.get("Nya killar", 0) + känner

        # Snitt
        snitt = rad["DeepT"] / män if män else 0

        # Tid mun
        tid_mun = ((snitt * rad["Sekunder"]) + rad["Vila mun"]) * rad["Varv"]

        # Summa singel
        vila = rad.get("Vila", 0)
        tid_singel = rad["Tid S"]
        summa_singel = (tid_singel + vila) * (män + rad["Fitta"] + rad["Röv"])

        # Summa dubbel
        tid_dubbel = rad["Tid D"]
        antal_dubbel = rad["DM"] + rad["DF"] + rad["DA"]
        summa_dubbel = (tid_dubbel + vila + 8) * antal_dubbel

        # Summa trippel
        tid_trippel = rad["Tid T"] if "Tid T" in rad else rad.get("Tid trippel", 0)
        antal_trippel = rad["TPP"] + rad["TAP"] + rad["TP"]
        summa_trippel = (tid_trippel + vila + 15) * antal_trippel

        # Älskar och Sover med
        alskar_tid = rad["Älskar"] * 1800  # 30 min
        sover_tid = rad["Sover med"] * 1800

        # Summa tid i sekunder
        total_tid = summa_singel + summa_dubbel + summa_trippel + tid_mun + alskar_tid + sover_tid
        summa_tid_h = total_tid / 3600  # i timmar

        # Suger
        suger = (summa_singel + summa_dubbel + summa_trippel) * 0.6 / män if män else 0

        # Tid kille
        tid_kille = (
            tid_singel + (tid_dubbel * 2) + (tid_trippel * 3) + suger + tid_mun / män + alskar_tid / män + sover_tid / män
            if män else 0
        ) / 60  # i minuter

        # Hårdhet
        hårdhet = 0
        if rad["Nya killar"] > 0:
            hårdhet += 1
        if rad["DM"] > 0:
            hårdhet += 2
        if rad["DF"] > 0:
            hårdhet += 3
        if rad["DA"] > 0:
            hårdhet += 4
        if rad["TPP"] > 0:
            hårdhet += 5
        if rad["TAP"] > 0:
            hårdhet += 7
        if rad["TP"] > 0:
            hårdhet += 6

        # Filmer
        filmer = (
            (män + rad["Fitta"] + rad["Röv"]
             + rad["DM"] * 2 + rad["DF"] * 2 + rad["DA"] * 3
             + rad["TPP"] * 4 + rad["TAP"] * 6 + rad["TP"] * 5)
            * hårdhet
        )

        pris = 39.99
        intäkter = filmer * pris
        malin_lön = min(intäkter * 0.01, 700)

        kompisar_lön = (intäkter - malin_lön) / vänner if vänner else 0

        # Aktiekurs
        aktiekurs = rad.get("Aktiekurs", 0)
        kompisar_aktievärde = 5000 * aktiekurs if aktiekurs else 0

        df.at[i, "Veckodag"] = veckodag_from_dag(dag)
        df.at[i, "Känner"] = känner
        df.at[i, "Män"] = män
        df.at[i, "Snitt"] = snitt
        df.at[i, "Tid mun"] = tid_mun
        df.at[i, "Summa singel"] = summa_singel
        df.at[i, "Summa dubbel"] = summa_dubbel
        df.at[i, "Summa trippel"] = summa_trippel
        df.at[i, "Summa tid"] = summa_tid_h
        df.at[i, "Suger"] = suger
        df.at[i, "Tid kille"] = tid_kille
        df.at[i, "Hårdhet"] = hårdhet
        df.at[i, "Filmer"] = filmer
        df.at[i, "Pris"] = pris
        df.at[i, "Intäkter"] = intäkter
        df.at[i, "Malin lön"] = malin_lön
        df.at[i, "Kompisar"] = kompisar_lön
        df.at[i, "Kompisar aktievärde"] = kompisar_aktievärde

    return df

def statistikvy(df):
    st.subheader("📊 Statistik")

    if df.empty:
        st.info("Ingen data att analysera.")
        return

    filtrerad = df[df["Dag"] > 0].copy()

    tot_malin_lön = filtrerad["Malin lön"].sum()
    tot_älskar = filtrerad["Älskar"].sum()
    tot_sover = filtrerad["Sover med"].sum()
    tot_nyakillar = filtrerad["Nya killar"].sum()
    tot_vänner = filtrerad["Känner"].sum()

    total_män = tot_älskar + tot_sover + tot_nyakillar + tot_vänner
    roi_per_man = (tot_malin_lön / total_män) if total_män > 0 else 0

    sista_kurs = filtrerad["Aktiekurs"].replace(0, pd.NA).dropna().iloc[-1] if not filtrerad["Aktiekurs"].replace(0, pd.NA).dropna().empty else 0
    kompisar = (
        sista_kurs * 5000
        if sista_kurs
        else 0
    )

    dag0 = df[df["Dag"] == 0]
    dag0_summa = dag0[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
    per_kompis = (kompisar / dag0_summa) if dag0_summa > 0 else 0

    st.metric("📈 Total Malin lön", f"{tot_malin_lön:.2f} USD")
    st.metric("🔁 ROI per man", f"{roi_per_man:.2f} USD/person")
    st.metric("📊 Kompisars aktievärde", f"{kompisar:,.0f} USD")
    st.metric("👥 Aktievärde per kompis", f"{per_kompis:.2f} USD")

# Avslutande anrop
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
