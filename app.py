import streamlit as st
import pandas as pd
import random
import math
from datetime import datetime
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import toml

secrets = toml.load(".streamlit/secrets.toml")
SHEET_URL = secrets["SHEET_URL"]
credentials_dict = secrets["GOOGLE_CREDENTIALS"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP", "Älskar",
    "Sover med", "Tid S", "Tid D", "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
    "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv", "Känner", "Män", "Summa singel", "Summa dubbel",
    "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille", "Hårdhet", "Filmer",
    "Pris", "Intäkter", "Malin lön", "Kompisar", "Aktiekurs", "Kompisar aktievärde"
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
    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils familj": 0}
    return dag0.iloc[0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].to_dict()

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

def visa_varningar(rad):
    summa_tid = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if summa_tid > 17:
        st.warning(f"⚠️ Summa tid är {summa_tid:.2f} timmar – det kan vara för mycket.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid per kille är {tid_kille:.2f} minuter – utanför rekommenderat intervall (9–15 min).")

def statistikvy(df):
    st.subheader("📊 Statistik")

    total_intakt = df["Intäkter"].sum()
    total_lön = df["Malin lön"].sum()
    total_kompisar = df["Kompisar"].sum()
    män = df["Män"].sum()
    älskar = df["Älskar"].sum()
    sover_med = df["Sover med"].sum()
    nya = df["Nya killar"].sum()
    känner = df["Känner"].sum()

    roi_per_man = total_lön / (älskar + sover_med + nya + känner) if (älskar + sover_med + nya + känner) > 0 else 0
    kurs = df["Aktiekurs"].iloc[-1] if not df.empty else 0
    dag0 = df[df["Dag"] == 0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
    aktievärde = kurs * 5000
    aktievärde_per_kompis = aktievärde / dag0 if dag0 else 0

    st.metric("Totala intäkter", f"${total_intakt:,.2f}")
    st.metric("Malin lön", f"${total_lön:,.2f}")
    st.metric("ROI per man", f"${roi_per_man:,.2f}")
    st.metric("Kompisars aktievärde", f"${aktievärde:,.2f}")
    st.metric("Per kompis", f"${aktievärde_per_kompis:.2f}")

def update_calculations(df):
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum(axis=1)
    df["Män"] = df["Nya killar"] + df["Känner"]

    df["Summa singel"] = (
        df["Tid S"] + df["Vila"]
    ) * (df["Män"] + df["Fitta"] + df["Röv"])

    df["Summa dubbel"] = (
        (df["Tid D"] + df["Vila"] + 8)
    ) * (df["DM"] + df["DF"] + df["DA"])

    df["Summa trippel"] = (
        (df["Tid T"] + df["Vila"] + 15)
    ) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Snitt"] = df.apply(
        lambda row: row["DeepT"] / row["Män"] if row["Män"] > 0 else 0,
        axis=1
    )
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]

    df["Summa tid"] = (
        df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]
        + df["Tid mun"] + (df["Älskar"] * 30 * 60) + (df["Sover med"] * 30 * 60)
    ) / 3600  # konvertera till timmar

    df["Suger"] = df.apply(
        lambda row: (row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"]) * 0.6 / row["Män"]
        if row["Män"] > 0 else 0,
        axis=1
    )

    df["Tid kille"] = (
        df["Tid S"]
        + df["Tid D"] * 2
        + df["Tid T"] * 3
        + df["Suger"]
        + df["Tid mun"]
        + (df["Sover med"] * 30 * 60 / df["Män"]).fillna(0)
        + (df["Älskar"] * 30 * 60 / df["Män"]).fillna(0)
    ) / 60  # minuter

    df["Hårdhet"] = (
        (df["Nya killar"] > 0).astype(int)
        + (df["DM"] > 0).astype(int) * 2
        + (df["DF"] > 0).astype(int) * 3
        + (df["DA"] > 0).astype(int) * 4
        + (df["TPP"] > 0).astype(int) * 5
        + (df["TAP"] > 0).astype(int) * 7
        + (df["TP"] > 0).astype(int) * 6
    )

    df["Filmer"] = (
        df["Män"] + df["Fitta"] + df["Röv"]
        + df["DM"] * 2 + df["DF"] * 2 + df["DA"] * 3
        + df["TPP"] * 4 + df["TAP"] * 6 + df["TP"] * 5
    ) * df["Hårdhet"]

    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = df["Intäkter"] * 0.01
    df.loc[df["Malin lön"] > 700, "Malin lön"] = 700

    maxrad = df[df["Dag"] == 0]
    if not maxrad.empty:
        kompisar = (
            maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
        )
        df["Kompisar"] = df["Intäkter"] - df["Malin lön"]
        df["Kompisar"] = df["Kompisar"] / kompisar if kompisar > 0 else 0
    else:
        df["Kompisar"] = 0

    df["Aktiekurs"] = df["Aktiekurs"].replace(0, method="ffill")
    df["Kompisar aktievärde"] = df["Aktiekurs"].fillna(0) * 5000

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
    ny_rad["Tid T"] = 80
    ny_rad["Vila"] = 7

    ny_rad["Jobb"] = random.randint(3, maxvärden.get("Jobb", 3))
    ny_rad["Grannar"] = random.randint(3, maxvärden.get("Grannar", 3))
    ny_rad["Tjej PojkV"] = random.randint(3, maxvärden.get("Tjej PojkV", 3))
    ny_rad["Nils familj"] = random.randint(3, maxvärden.get("Nils familj", 3))

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

def statistikvy(df):
    st.subheader("📊 Statistik")

    if df.empty:
        st.info("Ingen data tillgänglig.")
        return

    df = df[df["Dag"] != 0]

    totalt_malin_lön = df["Malin lön"].sum()
    totalt_alskar = df["Älskar"].sum()
    totalt_sovermed = df["Sover med"].sum()
    totalt_killar = df["Nya killar"].sum()
    totalt_känner = df["Känner"].sum()
    totalt_män = df["Män"].sum()

    if totalt_män > 0:
        snitt_tid_kille = df["Tid kille"].mean()
    else:
        snitt_tid_kille = 0

    if totalt_alskar + totalt_sovermed + totalt_killar + totalt_känner > 0:
        malin_roi = totalt_malin_lön / (totalt_alskar + totalt_sovermed + totalt_killar + totalt_känner)
    else:
        malin_roi = 0

    aktiekurs = df["Aktiekurs"].replace(0, method="ffill").iloc[-1]
    dag0 = df[df["Dag"] == 0]
    kompisar = dag0[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()

    st.metric("👥 Totalt antal män", totalt_män)
    st.metric("🎥 Totalt antal filmer", df["Filmer"].sum())
    st.metric("💰 Totala intäkter (USD)", f"{df['Intäkter'].sum():,.2f}")
    st.metric("🧍‍♀️ Malin total lön (USD)", f"{totalt_malin_lön:,.2f}")
    st.metric("🕐 Genomsnittlig tid per kille (minuter)", f"{snitt_tid_kille:.2f}")
    st.metric("📈 Malin ROI per man", f"{malin_roi:.4f}")
    if kompisar > 0:
        st.metric("📊 Aktievärde (kompisar)", f"{aktiekurs * 5000:,.2f} USD")
        st.metric("💵 Aktievärde per kompis", f"{(aktiekurs * 5000 / kompisar):.2f} USD")

def hämta_maxvärden(df):
    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils familj": 0}
    return dag0.iloc[0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].to_dict()

def lägg_till_rad(df, ny_rad):
    ny_rad = pd.DataFrame([ny_rad])
    df = pd.concat([df, ny_rad], ignore_index=True)
    df = ensure_columns_exist(df)
    df = update_calculations(df)
    save_data(df)
    return df

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
