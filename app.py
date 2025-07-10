import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import random
import math

# === AUTENTISERING ===
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit"

credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
sheet = spreadsheet.worksheet("Blad1")

# === KONSTANTER ===
ALL_COLUMNS = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Älskar", "Sover med", "Nya killar",
    "DM", "DF", "DA", "TPP", "TAP", "TP", "Fitta", "Röv", "DeepT", "Sekunder", "Vila",
    "Vila mun", "Varv", "Svarta", "Tid singel", "Tid dubbel", "Tid trippel", "Tid mun",
    "Summa singel", "Summa dubbel", "Summa trippel", "Suger", "Totalt män", "Tid kille dt",
    "Tid kille", "Summa tid", "Intäkter", "Malin lön", "Kompisars lön", "Filmer", "Hårdhet"
]

MANUAL_FIELDS = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Älskar", "Sover med", "Nya killar",
    "DM", "DF", "DA", "TPP", "TAP", "TP", "Fitta", "Röv", "DeepT", "Sekunder", "Vila",
    "Vila mun", "Varv", "Svarta"
]

# === LADDA IN DATA ===
@st.cache_data(ttl=60)
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=ALL_COLUMNS)
    df = df.reindex(columns=ALL_COLUMNS, fill_value=0)
    df[ALL_COLUMNS] = df[ALL_COLUMNS].fillna(0)
    return df.astype({col: int for col in ALL_COLUMNS if col != "Intäkter" and col != "Malin lön" and col != "Kompisars lön"})

df = load_data()

# === HÄMTA MAXVÄRDEN FRÅN DAG = 0 ===
def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    return {
        "Jobb": int(maxrad["Jobb"].iloc[0]),
        "Grannar": int(maxrad["Grannar"].iloc[0]),
        "Tjej PojkV": int(maxrad["Tjej PojkV"].iloc[0]),
        "Nils fam": int(maxrad["Nils fam"].iloc[0])
    }

def formulär_maxvärden(df):
    st.subheader("Ange maxvärden (Dag = 0)")
    with st.form("maxvärden_formulär"):
        jobb = st.number_input("Jobb", min_value=0, value=0)
        grannar = st.number_input("Grannar", min_value=0, value=0)
        tjej = st.number_input("Tjej PojkV", min_value=0, value=0)
        nils = st.number_input("Nils fam", min_value=0, value=0)
        submitted = st.form_submit_button("Spara maxvärden")
        if submitted:
            ny_rad = pd.DataFrame([{
                "Dag": 0, "Jobb": jobb, "Grannar": grannar,
                "Tjej PojkV": tjej, "Nils fam": nils
            }], columns=ALL_COLUMNS).fillna(0)
            df = df[df["Dag"] != 0]
            df = pd.concat([ny_rad, df], ignore_index=True)
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
            st.success("Maxvärden sparade. Starta om appen.")
            st.stop()
    return df

# === VALIDERA MOT MAXVÄRDEN ===
def validera_maxvarden(ny_rad, maxv):
    for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if ny_rad[kolumn] > maxv[kolumn]:
            st.error(f"{kolumn} = {ny_rad[kolumn]} överskrider maxvärde ({maxv[kolumn]}). Uppdatera max först.")
            st.stop()

# === REDIGERA RADER ===
def visa_redigeringsformulär(rad, index, df):
    st.subheader(f"Redigera rad {index} (Dag: {rad['Dag']})")
    with st.form(f"redigera_form_{index}"):
        nya_värden = {}
        for kolumn in MANUAL_FIELDS:
            nya_värden[kolumn] = st.number_input(kolumn, min_value=0, value=int(rad[kolumn]), key=f"{kolumn}_{index}")
        if st.form_submit_button("Spara redigerad rad"):
            for kolumn in MANUAL_FIELDS:
                df.at[index, kolumn] = nya_värden[kolumn]
            return df
    return df

# === KOLLA KOLUMNER ===
def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[ALL_COLUMNS]

# === BERÄKNINGAR ===
def update_calculations(df):
    df = ensure_columns_exist(df)
    df[NUMERISKA_KOL] = df[NUMERISKA_KOL].fillna(0)
    
    maxrad = df[df["Dag"] == 0]
    vänner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()

    df["Män"] = df["Nya killar"] + vänner
    df["Snitt"] = df["DeepT"] / df["Män"].replace(0, 1)
    df["Tid mun"] = ((df["Snitt"] * df["Sekunder"]) + df["Vila mun"]) * df["Varv"]
    
    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * (df["Män"] + df["Fitta"] + df["Röv"])
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"]) + 8) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Suger"] = (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) * 0.6 / df["Män"].replace(0, 1)
    df["Tid kille dt"] = (df["Snitt"] * df["Sekunder"] * df["Varv"]) / df["Män"].replace(0, 1)

    df["Tid kille"] = (
        df["Tid singel"]
        + df["Tid dubbel"] * 2
        + df["Tid trippel"] * 3
        + df["Suger"]
        + df["Tid kille dt"]
        + df["Tid mun"]
    ) / 60

    df["Filmer"] = (
        (df["Män"] + df["Fitta"] + df["Röv"] + df["DM"]*2 + df["DF"]*2 + df["DA"]*3 + df["TPP"]*4 + df["TAP"]*6 + df["TP"]*5)
        * df.apply(lambda r: (
            (1 if r["Nya killar"] > 0 else 0)
            + (2 if r["DM"] > 0 else 0)
            + (3 if r["DF"] > 0 else 0)
            + (4 if r["DA"] > 0 else 0)
            + (5 if r["TPP"] > 0 else 0)
            + (7 if r["TAP"] > 0 else 0)
            + (6 if r["TP"] > 0 else 0)
        ), axis=1)
    )

    df["Intäkter"] = df["Filmer"] * 39.99
    df["Malin lön"] = df["Intäkter"] * 0.01
    df.loc[df["Malin lön"] > 700, "Malin lön"] = 700

    df["Summa tid (sek)"] = (
        df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]
        + df["Tid mun"] + df["Sover med"] * 1800 + df["Älskar"] * 1800
    )
    df["Summa tid (h)"] = df["Summa tid (sek)"] / 3600
    return df

# === SPARA NY RAD ===
def spara_ny_rad(df, ny_rad_dict):
    maxv = hamta_maxvarden(df)
    validera_maxvarden(ny_rad_dict, maxv)
    ny_rad = pd.DataFrame([ny_rad_dict], columns=ALL_COLUMNS).fillna(0)
    df = pd.concat([df, ny_rad], ignore_index=True)
    df = update_calculations(df)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
    return df

# === HÄMTA MAXVÄRDEN ===
def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    return maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].iloc[0].to_dict()

def validera_maxvarden(rad, maxv):
    for nyckel in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if rad.get(nyckel, 0) > maxv.get(nyckel, 0):
            raise ValueError(f"{nyckel} överskrider maxvärdet ({rad[nyckel]} > {maxv[nyckel]}). Uppdatera maxvärden först.")

# === FORMULÄR FÖR MAXVÄRDEN ===
def formulär_maxvärden():
    st.subheader("⚙️ Ange maxvärden (Dag = 0)")
    med = {"Dag": 0}
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        med[fält] = st.number_input(fält, step=1, value=0, key=f"max_{fält}")
    if st.button("Spara maxvärden"):
        df = ladda_data()
        df = df[df["Dag"] != 0]
        ny = pd.DataFrame([med], columns=ALL_COLUMNS).fillna(0)
        df = pd.concat([ny, df], ignore_index=True)
        df = update_calculations(df)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
        st.success("Maxvärden sparade.")

# === NY RAD MANUELLT ===
def ny_rad_manuellt_form(df):
    st.subheader("➕ Lägg till ny rad manuellt")
    maxv = hamta_maxvarden(df)
    ny = {"Dag": st.number_input("Dag", min_value=1, step=1, key="man_dag")}
    for kol in ALL_COLUMNS:
        if kol == "Dag" or kol not in NUMERISKA_KOL:
            continue
        ny[kol] = st.number_input(kol, step=1, value=0, key=f"man_{kol}")
    if st.button("Spara rad"):
        try:
            df = spara_ny_rad(df, ny)
            st.success("Rad sparad.")
            visa_varningar(df.iloc[-1])
        except Exception as e:
            st.error(str(e))
    return df

# === KOPIERA STÖRSTA RADEN ===
def kopiera_storsta_raden(df):
    if df.empty: return {}
    rad = df[df["Dag"] != 0].sort_values("Män", ascending=False).iloc[0].to_dict()
    rad["Dag"] = st.number_input("Dag", min_value=1, step=1, key="copy_dag")
    for k in NUMERISKA_KOL:
        rad[k] = st.number_input(k, step=1, value=int(rad.get(k, 0)), key=f"copy_{k}")
    if st.button("Spara kopierad rad"):
        try:
            df = spara_ny_rad(df, rad)
            st.success("Rad kopierad.")
            visa_varningar(df.iloc[-1])
        except Exception as e:
            st.error(str(e))
    return df

# === SLUMPA FILM ===
def slumpa_film(liten=True):
    rad = {"Dag": st.number_input("Dag", min_value=1, step=1, key="slump_dag")}
    intervall = INTERVALL_LITEN if liten else INTERVALL_STOR
    for kol, (botten, toppen) in intervall.items():
        rad[kol] = random.randint(botten, toppen)
    rad["Vila"] = 7
    rad["Sover med"] = 1
    rad["Älskar"] = 8
    rad["Älsk tid"] = 30
    return rad

# === VILA-KNAPPAR ===
def vilodag_knapp(df, typ):
    st.subheader(f"🛏️ Vilodag: {typ}")
    dag = st.number_input("Dag", min_value=1, step=1, key=f"vila_dag_{typ}")
    rad = {"Dag": dag}
    maxv = hamta_maxvarden(df)
    for nyckel in maxv:
        if typ == "jobb":
            rad[nyckel] = int(maxv[nyckel] * 0.3)
        elif typ == "hemma":
            rad[nyckel] = maxv[nyckel]
        elif typ == "helt":
            rad[nyckel] = 0
    for kol in NUMERISKA_KOL:
        if kol not in rad:
            rad[kol] = 0
    rad["Vila"] = 24
    if st.button(f"Spara vilodag ({typ})"):
        try:
            df = spara_ny_rad(df, rad)
            st.success("Vilodag sparad.")
            visa_varningar(df.iloc[-1])
        except Exception as e:
            st.error(str(e))
    return df

# === REDIGERA FORMULÄR (för alla knappar) ===
def visa_redigeringsformulär(rad):
    st.subheader("✏️ Redigera före spara")
    ny = {"Dag": rad.get("Dag", 1)}
    for kol in ALL_COLUMNS:
        if kol == "Dag": continue
        ny[kol] = st.number_input(kol, step=1, value=int(rad.get(kol, 0)), key=f"edit_{kol}")
    if st.button("Spara redigerad rad"):
        try:
            df = ladda_data()
            df = spara_ny_rad(df, ny)
            st.success("Redigerad rad sparad.")
            visa_varningar(df.iloc[-1])
            return df
        except Exception as e:
            st.error(str(e))
    return None

# === STATISTIKVY ===
def statistikvy(df):
    st.subheader("📊 Statistik")
    df = df.copy()
    df = df[df["Dag"] != 0]
    df = update_calculations(df)

    totalt_tid = df["Summa tid"].sum()
    antal_män = df["Män"].sum()
    antal_filmer = df["Filmer"].sum()
    totalt_intakt = df["Totala intäkter"].sum()
    totalt_malin = df["Malin lön"].sum()
    totalt_alskar = df["Älskar"].sum()
    totalt_sover = df["Sover med"].sum()
    totalt_killar = df["Nya killar"].sum()
    totalt_kompisar = df["Känner"].sum()
    roi_denominator = totalt_alskar + totalt_sover + totalt_killar + totalt_kompisar
    roi_per_man = totalt_malin / roi_denominator if roi_denominator > 0 else 0

    st.write(f"**⏱️ Total tid:** {round(totalt_tid, 2)} timmar")
    st.write(f"**👨 Antal män:** {antal_män}")
    st.write(f"**🎬 Filmer:** {antal_filmer}")
    st.write(f"**💰 Intäkter totalt:** {round(totalt_intakt, 2)} USD")
    st.write(f"**💸 Malin lön:** {round(totalt_malin, 2)} USD")
    st.write(f"**📈 ROI per man:** {round(roi_per_man, 2)} USD")

    maxv = hamta_maxvarden(df)
    sista_kurs = df["Aktuell kurs"].dropna().iloc[-1] if "Aktuell kurs" in df and not df["Aktuell kurs"].isna().all() else 0
    antal_kompisar = maxv.sum()
    totalt_varde = 5000 * sista_kurs
    varde_per_person = totalt_varde / antal_kompisar if antal_kompisar > 0 else 0
    st.write(f"**📦 Kompisars aktievärde totalt:** {round(totalt_varde, 2)} USD")
    st.write(f"**👤 Aktievärde per kompis:** {round(varde_per_person, 2)} USD")

# === VARNINGAR EFTER SPARAD RAD ===
def visa_varningar(rad):
    if rad.get("Summa tid", 0) > 17:
        st.warning("⚠️ Summa tid överstiger 17 timmar!")
    if rad.get("Tid kille", 0) < 9 or rad.get("Tid kille", 0) > 15:
        st.warning("⚠️ Tid kille ligger utanför 9–15 min!")

# === MENY OCH MAIN ===
def main():
    st.title("📒 MalinApp")
    df = ladda_data()
    menyval = st.sidebar.selectbox("Meny", ["Ny rad manuellt", "Slumpa film liten", "Slumpa film stor", "Vilodag hemma", "Vilodag jobb", "Vilodag helt", "Kopiera största raden", "Statistik"])

    if kontrollera_om_maxraden_finns(df):
        df = formulär_maxvärden(df)

    if menyval == "Ny rad manuellt":
        df = formulär_ny_rad(df)
    elif menyval == "Slumpa film liten":
        rad = slumpa_film(liten=True)
        df_ny = visa_redigeringsformulär(rad)
        if df_ny is not None:
            df = df_ny
    elif menyval == "Slumpa film stor":
        rad = slumpa_film(liten=False)
        df_ny = visa_redigeringsformulär(rad)
        if df_ny is not None:
            df = df_ny
    elif menyval == "Vilodag hemma":
        df = vilodag_knapp(df, "hemma")
    elif menyval == "Vilodag jobb":
        df = vilodag_knapp(df, "jobb")
    elif menyval == "Vilodag helt":
        df = vilodag_knapp(df, "helt")
    elif menyval == "Kopiera största raden":
        rad = df[df["Män"] == df["Män"].max()].iloc[-1].to_dict()
        rad["Dag"] = st.number_input("Dag", min_value=1, step=1, key="kopiera_dag")
        df_ny = visa_redigeringsformulär(rad)
        if df_ny is not None:
            df = df_ny
    elif menyval == "Statistik":
        statistikvy(df)

if __name__ == "__main__":
    main()
