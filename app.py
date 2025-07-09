import streamlit as st
import pandas as pd
import numpy as np
import random
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe

# === Google Sheets Setup ===
import toml
secrets = toml.load(".streamlit/secrets.toml")
SHEET_URL = secrets["SHEET_URL"]
GOOGLE_CREDENTIALS = secrets["GOOGLE_CREDENTIALS"]

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SHEET_URL)
worksheet = sh.worksheet("Blad1")

# === Kolumnlista ===
ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Älskar", "Sover med", "Tid S", "Tid D", "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
    "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv",
    # Beräknade
    "Känner", "Män", "Summa singel", "Summa dubbel", "Summa trippel",
    "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille", "Hårdhet", "Filmer",
    "Pris", "Intäkter", "Malin lön", "Kompisar", "Aktiekurs"
]

def load_data():
    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    df.fillna(0, inplace=True)

    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0

    df = df[ALL_COLUMNS]  # Säkerställ rätt ordning
    df["Dag"] = df["Dag"].astype(int)
    return df

def update_sheet(df):
    df_to_save = df[ALL_COLUMNS]
    set_with_dataframe(worksheet, df_to_save, include_index=False)

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df

def hamta_maxvarden(df):
    rad_0 = df[df["Dag"] == 0]
    if rad_0.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    rad_0 = rad_0.iloc[0]
    return {
        "Jobb": rad_0.get("Jobb", 0),
        "Grannar": rad_0.get("Grannar", 0),
        "Tjej PojkV": rad_0.get("Tjej PojkV", 0),
        "Nils fam": rad_0.get("Nils fam", 0)
    }

def skapa_basrad(df):
    dag = df["Dag"].max() + 1
    rad = {k: 0 for k in ALL_COLUMNS}
    rad["Dag"] = dag
    return rad, dag

def slumpa_film_liten(maxvärden):
    return {
        "Nya killar": random.randint(10, 50),
        "Fitta": random.randint(3, 12),
        "Röv": random.randint(3, 12),
        "Dm": random.randint(10, 25),
        "Df": random.randint(10, 25),
        "Da": 0,
        "TPP": 0,
        "Tap": 0,
        "TP": 0,
        "Älskar": 12,
        "Sover med": 1,
        "Tid s": 60,
        "Tid d": 70,
        "Tid trippel": 80,
        "Vila": 7,
        "Jobb": random.randint(3, maxvärden["Jobb"]),
        "Grannar": random.randint(3, maxvärden["Grannar"]),
        "Tjej PojkV": random.randint(3, maxvärden["Tjej PojkV"]),
        "Nils fam": random.randint(3, maxvärden["Nils fam"]),
        "Svarta": random.choice([0, random.randint(10, 50)]),
    }

def slumpa_film_stor(maxvärden):
    return {
        "Nya killar": random.randint(60, 200),
        "Fitta": random.randint(10, 30),
        "Röv": random.randint(10, 30),
        "Dm": random.randint(50, 100),
        "Df": random.randint(50, 100),
        "Da": random.randint(50, 100),
        "TPP": random.randint(30, 80),
        "Tap": random.randint(30, 80),
        "TP": random.randint(30, 80),
        "Älskar": 12,
        "Sover med": 1,
        "Tid s": 60,
        "Tid d": 70,
        "Tid trippel": 80,
        "Vila": 7,
        "Jobb": random.randint(3, maxvärden["Jobb"]),
        "Grannar": random.randint(3, maxvärden["Grannar"]),
        "Tjej PojkV": random.randint(3, maxvärden["Tjej PojkV"]),
        "Nils fam": random.randint(3, maxvärden["Nils fam"]),
        "Svarta": random.choice([0, random.randint(60, 200)]),
    }

def vila_jobb(maxvärden):
    return {
        "Älskar": 12,
        "Sover med": 1,
        "Jobb": int(maxvärden["Jobb"] * 0.3),
        "Grannar": int(maxvärden["Grannar"] * 0.3),
        "Tjej PojkV": int(maxvärden["Tjej PojkV"] * 0.3),
        "Nils fam": int(maxvärden["Nils fam"] * 0.3),
    }

def vila_hemma(maxvärden):
    return {
        "Älskar": 6,
        "Jobb": 5,
        "Grannar": 3,
        "Tjej PojkV": 3,
        "Nils fam": 5,
    }

def vila_helt():
    return {}

def knappfunktioner(df):
    maxvärden = hamta_maxvarden(df)

    def visa_och_spara(rad, dag):
        rad["Känner"] = rad.get("Jobb", 0) + rad.get("Grannar", 0) + rad.get("Tjej PojkV", 0) + rad.get("Nils fam", 0)
        rad["Män"] = rad.get("Nya killar", 0) + rad["Känner"]
        ny_rad = visa_redigeringsformulär(rad, dag)
        if ny_rad:
            df = spara_redigerad_rad(df, ny_rad)
            df = visa_varningar(df)
        return df

    if st.button("🎲 Slumpa Film liten"):
        rad, dag = skapa_basrad(df)
        rad.update(slumpa_film_liten(maxvärden))
        df = visa_och_spara(rad, dag)

    if st.button("🎲 Slumpa Film stor"):
        rad, dag = skapa_basrad(df)
        rad.update(slumpa_film_stor(maxvärden))
        df = visa_och_spara(rad, dag)

    if st.button("📋 Kopiera största raden (nya killar)"):
        if not df.empty:
            största = df[df["Nya killar"] == df["Nya killar"].max()].iloc[0].to_dict()
            rad, dag = skapa_basrad(df)
            rad.update(största)
            df = visa_och_spara(rad, dag)

    if st.button("🏢 Vila jobb"):
        rad, dag = skapa_basrad(df)
        rad.update(vila_jobb(maxvärden))
        df = visa_och_spara(rad, dag)

    if st.button("🛋️ Vila hemma"):
        rad, dag = skapa_basrad(df)
        rad.update(vila_hemma(maxvärden))
        df = visa_och_spara(rad, dag)

    if st.button("💤 Vila helt"):
        rad, dag = skapa_basrad(df)
        rad.update(vila_helt())
        df = visa_och_spara(rad, dag)

    return df

def visa_redigeringsformulär(rad, dag):
    with st.form(key=f"form_{dag}"):
        ny_rad = {"Dag": dag}
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                continue
            värde = rad.get(kolumn, 0)
            if isinstance(värde, str):
                try:
                    värde = float(värde)
                except ValueError:
                    värde = 0
            step = 1.0 if isinstance(värde, float) else 1
            ny_rad[kolumn] = st.number_input(kolumn, value=float(värde), step=step)
        submitted = st.form_submit_button("Spara redigerad rad")
        if submitted:
            return ny_rad
    return None

def spara_redigerad_rad(df, ny_rad):
    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    update_sheet(df)
    st.success("✅ Raden har sparats!")
    return df

def visa_varningar(df):
    senaste = df.iloc[-1]
    timmar = senaste["Summa tid"]
    tid_kille = senaste["Tid kille"]

    if timmar > 17:
        st.warning(f"⚠️ Summa tid är {hinnar:.2f} timmar – det är mycket!")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid kille är {tid_kille:.2f} min – utanför normalintervall (9–15 min).")
    return df

def validera_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return df
    maxrad = maxrad.iloc[0]
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        maxvärde = maxrad.get(fält, 0)
        övriga = df[df["Dag"] > 0]
        if not övriga.empty:
            över = övriga[övriga[fält] > maxvärde]
            if not över.empty:
                st.error(f"❌ Det finns rader där {fält} överskrider maxvärde ({maxvärde}) – uppdatera Dag = 0 först.")
    return df

def ensure_columns_exist(df):
    for kolumn in ALL_COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = 0
    return df

def update_calculations(df):
    maxrad = df[df["Dag"] == 0].copy()
    maxvärden = {
        "Jobb": maxrad["Jobb"].values[0] if not maxrad.empty else 0,
        "Grannar": maxrad["Grannar"].values[0] if not maxrad.empty else 0,
        "Tjej PojkV": maxrad["Tjej PojkV"].values[0] if not maxrad.empty else 0,
        "Nils fam": maxrad["Nils fam"].values[0] if not maxrad.empty else 0
    }
    vänner = sum(maxvärden.values())
    aktiekurs = df["Aktiekurs"].iloc[-1] if "Aktiekurs" in df.columns and not df.empty else 40.0

    for i, rad in df.iterrows():
        if rad["Dag"] == 0:
            continue

        känner = rad.get("Jobb", 0) + rad.get("Grannar", 0) + rad.get("Tjej PojkV", 0) + rad.get("Nils fam", 0)
        män = rad.get("Nya killar", 0) + känner

        rad["Känner"] = känner
        rad["Män"] = män

        # Summa tider
        singel = rad.get("Tid s", 0) * män / 3600
        dubbel = rad.get("Tid d", 0) * (rad.get("Dm", 0) + rad.get("Df", 0) + rad.get("Da", 0)) / 3600
        trippel = rad.get("Tid trippel", 0) * (rad.get("TPP", 0) + rad.get("Tap", 0) + rad.get("TP", 0)) / 3600
        tid_mun = ((rad.get("DeepT", 0) / män) * rad.get("Sekunder", 0) + rad.get("Vila mun", 0)) * rad.get("Varv", 0) / 3600 if män > 0 else 0
        älskar_tid = rad.get("Älskar", 0) * 0.5  # 30 min per älskar
        sover_tid = rad.get("Sover med", 0) * 0.5  # 30 min per person

        # Tid för enbart kompisar
        if män == känner and män > 0 and rad.get("Nya killar", 0) == 0 and rad.get("Älskar", 0) == 0 and rad.get("Sover med", 0) == 0:
            total_tid = 3
        else:
            total_tid = singel + dubbel + trippel + tid_mun + älskar_tid + sover_tid

        rad["Summa singel"] = singel
        rad["Summa dubbel"] = dubbel
        rad["Summa trippel"] = trippel
        rad["Tid mun"] = tid_mun
        rad["Summa tid"] = total_tid

        # Beräkningar
        snitt = (rad["DeepT"] / män) if män > 0 else 0
        hårdhet = 0
        hårdhet += 1 if rad.get("Nya killar", 0) > 0 else 0
        hårdhet += 2 if rad.get("Dm", 0) > 0 else 0
        hårdhet += 3 if rad.get("Df", 0) > 0 else 0
        hårdhet += 4 if rad.get("Da", 0) > 0 else 0
        hårdhet += 5 if rad.get("TPP", 0) > 0 else 0
        hårdhet += 7 if rad.get("Tap", 0) > 0 else 0
        hårdhet += 6 if rad.get("TP", 0) > 0 else 0

        tid_kille_dt = total_tid / män if män > 0 else 0
        runk = (total_tid * 0.6) / män if män > 0 else 0
        suger = 0.6 * (singel + dubbel + trippel) / män if män > 0 else 0

        tid_kille = rad.get("Tid s", 0) + rad.get("Tid d", 0) * 2 + rad.get("Tid trippel", 0) * 3
        tid_kille = tid_kille / 60 + suger + tid_kille_dt + runk + rad.get("Tid mun", 0) * 60 / 60

        filmer = (män + rad.get("Fitta", 0) + rad.get("Röv", 0) +
                  rad.get("Dm", 0) * 2 + rad.get("Df", 0) * 2 + rad.get("Da", 0) * 3 +
                  rad.get("TPP", 0) * 4 + rad.get("Tap", 0) * 6 + rad.get("TP", 0) * 5) * hårdhet

        intäkter = filmer * 39.99
        malin_lön = min(700, intäkter * 0.01)
        kompisar = ((intäkter - malin_lön) / vänner) if vänner > 0 else 0

        rad["Snitt"] = snitt
        rad["Suger"] = suger
        rad["Tid kille dt"] = tid_kille_dt
        rad["Runk"] = runk
        rad["Tid kille"] = tid_kille
        rad["Hårdhet"] = hårdhet
        rad["Filmer"] = filmer
        rad["Intäkter"] = intäkter
        rad["Malin lön"] = malin_lön
        rad["Kompisar"] = kompisar

        df.iloc[i] = rad

    # Uppdatera aktiekurs: beroende på prestation (ex. hårdhet över snitt → upp)
    if "Aktiekurs" not in df.columns:
        df["Aktiekurs"] = 40.0

    historik = df[df["Dag"] > 0]
    if not historik.empty:
        snitt_hårdhet = historik["Hårdhet"].mean()
        snitt_män = historik["Män"].mean()
        senaste = df.iloc[-1]
        prest = 0
        if senaste["Hårdhet"] > snitt_hårdhet:
            prest += 1
        if senaste["Da"] > historik["Da"].mean():
            prest += 1
        if senaste["TPP"] > historik["TPP"].mean():
            prest += 1
        if senaste["Tap"] > historik["Tap"].mean():
            prest += 1
        if senaste["TP"] > historik["TP"].mean():
            prest += 1
        if senaste["Män"] > snitt_män:
            prest += 1
        if senaste["Tid mun"] > historik["Tid mun"].mean():
            prest += 1
        procent = random.randint(3, 10)
        riktning = 1 if prest >= 4 else -1
        ny_kurs = aktiekurs * (1 + riktning * procent / 100)
        df.at[df.index[-1], "Aktiekurs"] = round(ny_kurs, 2)

    return df

def visa_statistik(df):
    st.subheader("📊 Statistik")

    maxrad = df[df["Dag"] == 0]
    max_vänner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum() if not maxrad.empty else 0
    sista_aktiekurs = df["Aktiekurs"].iloc[-1] if "Aktiekurs" in df.columns and not df.empty else 40.0

    filmer = df[df["Nya killar"] > 0]["Filmer"].sum()
    totalt_män = df["Nya killar"].sum() + max_vänner
    älskat = df["Älskar"].sum()
    sovit = df["Sover med"].sum()
    jobb = df["Jobb"].sum()
    grannar = df["Grannar"].sum()
    tjej = df["Tjej PojkV"].sum()
    nils = df["Nils fam"].sum()
    svarta = df["Svarta"].sum()
    vita = df["Nya killar"].sum() - svarta
    sålda_film = df["Filmer"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    vänner_lön = df["Kompisar"].sum()

    snitt_gb = totalt_män / filmer if filmer > 0 else 0
    älskat_snitt = älskat / max_vänner if max_vänner > 0 else 0
    sovit_snitt = sovit / maxrad["Nils fam"].sum() if not maxrad.empty and maxrad["Nils fam"].sum() > 0 else 0
    svarta_procent = (svarta / df["Nya killar"].sum()) * 100 if df["Nya killar"].sum() > 0 else 0
    vita_procent = (vita / df["Nya killar"].sum()) * 100 if df["Nya killar"].sum() > 0 else 0

    rader_med_män = df[(df["Nya killar"] > 0) | (df["Älskar"] > 0) | (df["Sover med"] > 0) | (df["Känner"] > 0)]
    roi_nämnare = df["Nya killar"].sum() + df["Älskar"].sum() + df["Sover med"].sum() + df["Känner"].sum()
    malin_roi = (malin_lön / roi_nämnare) if roi_nämnare > 0 else 0

    kompisar_total = max_vänner
    kompisar_aktievärde_total = 5000 * sista_aktiekurs
    kompisar_aktievärde_per = round(kompisar_aktievärde_total / kompisar_total, 2) if kompisar_total > 0 else 0

    # Extra summeringar
    vänner_gb = df["Känner"].sum() / max_vänner if max_vänner > 0 else 0
    kompisar_sum = älskat + vänner_gb
    familj_sum = kompisar_sum + sovit

    st.metric("🎬 Filmer", int(filmer))
    st.metric("👨 Totalt antal män", totalt_män)
    st.metric("❤️ Älskat", int(älskat))
    st.metric("😴 Sovit med", int(sovit))
    st.metric("💼 Jobb", int(jobb))
    st.metric("🏡 Grannar", int(grannar))
    st.metric("💑 Tjej PojkV", int(tjej))
    st.metric("👨‍👩‍👧‍👦 Nils familj", int(nils))
    st.metric("⚫ Svarta", int(svarta))
    st.metric("⚪ Vita", int(vita))
    st.metric("🎞️ Sålda filmer", int(sålda_film))
    st.metric("💰 Intäkter", f"{intäkter:,.2f} USD")
    st.metric("👩 Malin lön", f"{malin_lön:,.2f} USD")
    st.metric("👬 Vänners lön", f"{vänner_lön:,.2f} USD")
    st.metric("📈 Snitt GB", f"{snitt_gb:.2f}")
    st.metric("📊 Älskat snitt / kompis", f"{älskat_snitt:.2f}")
    st.metric("🛌 Sovit med / Nils fam", f"{sovit_snitt:.2f}")
    st.metric("⚫ Svarta i %", f"{svarta_procent:.2f}%")
    st.metric("⚪ Vita i %", f"{vita_procent:.2f}%")
    st.metric("📈 Malin ROI per man", f"{malin_roi:.2f} USD")
    st.metric("📉 Kompisars aktievärde", f"{kompisar_aktievärde_total:,.2f} USD")
    st.metric("👥 Kompis aktie / person", f"{kompisar_aktievärde_per:,.2f} USD")
    st.metric("🧮 Kompisar (älskat + vännerGB)", f"{kompisar_sum:.2f}")
    st.metric("🏠 Familj (kompisar + sovit)", f"{familj_sum:.2f}")

def main():
    st.set_page_config(layout="wide")
    st.title("🎥 Malins dataspårning")

    df = load_data()
    df = ensure_columns_exist(df)
    df = update_calculations(df)
    update_sheet(df)

    vyval = st.sidebar.radio("Välj vy", ["Ny rad", "Statistik"])

    if vyval == "Ny rad":
        st.subheader("➕ Lägg till ny rad eller använd knapp")
        df = formulär_maxvärden(df)
        df = knappfunktioner(df)
        df = visa_redigeringsform(df)

    elif vyval == "Statistik":
        visa_statistik(df)

if __name__ == "__main__":
    main()
