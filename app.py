import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"])
worksheet = sheet.worksheet("Blad1")

# Kolumner som alltid ska finnas
ALL_COLUMNS = [
    "Veckodag", "Dag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Tid T",
    "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj", "Svarta",
    "DeepT", "Sekunder", "Vila mun", "Varv",
    "Känner", "Män", "Summa singel", "Summa dubbel", "Summa trippel",
    "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille", "Hårdhet",
    "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar", "Aktiekurs"
]

def load_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df = ensure_columns_exist(df)
    return df

def save_data(df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.fillna("").values.tolist())

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    df = df[ALL_COLUMNS]
    return df

def hamta_maxvarden(df):
    dag0 = df[df["Dag"] == 0]
    return {
        "Jobb": dag0["Jobb"].max(),
        "Grannar": dag0["Grannar"].max(),
        "Tjej PojkV": dag0["Tjej PojkV"].max(),
        "Nils familj": dag0["Nils familj"].max()
    }

def validera_maxvarden(rad, maxvarden):
    fel = []
    for kategori in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
        if rad.get(kategori, 0) > maxvarden.get(kategori, 0):
            fel.append(f"{kategori} överskrider maxvärdet {maxvarden.get(kategori, 0)}! Uppdatera Dag = 0 först.")
    return fel

def update_calculations(df):
    df = ensure_columns_exist(df)
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    df["Veckodag"] = df["Dag"].apply(lambda x: veckodagar[(x - 1) % 7] if x > 0 else "")

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils familj"]
    df["Män"] = df["Nya killar"] + df["Känner"]

    df["Summa singel"] = (df["Tid S"] + df["Vila"]) * df["Män"]
    df["Summa dubbel"] = ((df["Tid D"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = ((df["Tid T"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Snitt"] = df.apply(lambda row: 0 if row["Män"] == 0 else row["DeepT"] / row["Män"], axis=1)
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]

    df["Summa tid"] = (
        df["Summa singel"] +
        df["Summa dubbel"] +
        df["Summa trippel"] +
        df["Tid mun"] +
        df["Älskar"] * 1800 +
        df["Sover med"] * 1800
    ) / 3600  # timmar

    df["Suger"] = df.apply(lambda row: 0 if row["Män"] == 0 else 0.6 * (row["Summa tid"] * 3600) / row["Män"], axis=1)

    df["Tid kille"] = df.apply(lambda row: 0 if row["Män"] == 0 else (
        row["Summa singel"] +
        2 * row["Summa dubbel"] +
        3 * row["Summa trippel"] +
        row["Suger"] / row["Män"] +
        row["Tid mun"]
    ) / 60, axis=1)  # minuter

    df["Hårdhet"] = (
        (df["Nya killar"] > 0).astype(int) * 1 +
        (df["DM"] > 0).astype(int) * 2 +
        (df["DF"] > 0).astype(int) * 3 +
        (df["DA"] > 0).astype(int) * 4 +
        (df["TPP"] > 0).astype(int) * 5 +
        (df["TAP"] > 0).astype(int) * 7 +
        (df["TP"] > 0).astype(int) * 6
    )

    df["Filmer"] = (
        (df["Män"] +
         df["Fitta"] +
         df["Röv"] +
         df["DM"] * 2 +
         df["DF"] * 2 +
         df["DA"] * 3 +
         df["TPP"] * 4 +
         df["TAP"] * 6 +
         df["TP"] * 5) * df["Hårdhet"]
    ).round().astype(int)

    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 700))

    try:
        dag0 = df[df["Dag"] == 0]
        kompisar_total = dag0["Jobb"].sum() + dag0["Grannar"].sum() + dag0["Tjej PojkV"].sum() + dag0["Nils familj"].sum()
        df["Kompisar"] = df.apply(
            lambda row: 0 if kompisar_total == 0 else (row["Intäkter"] - row["Malin lön"]) / kompisar_total,
            axis=1
        )
    except:
        df["Kompisar"] = 0.0

    # Aktiekurs: initiera 40.0 om saknas
    if "Aktiekurs" not in df.columns:
        df["Aktiekurs"] = 40.0
    df["Aktiekurs"] = df["Aktiekurs"].replace("", 40.0).astype(float)

    return df

import random

def visa_redigeringsform(ny_rad, df):
    with st.form("form_redigera_rad"):
        st.warning("⚠️ Kontrollera värden – något sticker ut!")
        for key in ny_rad:
            if key in ["Dag"]:
                continue
            if isinstance(ny_rad[key], int):
                ny_rad[key] = st.number_input(key, value=ny_rad[key], step=1)
            elif isinstance(ny_rad[key], float):
                ny_rad[key] = st.number_input(key, value=ny_rad[key])
        submit = st.form_submit_button("💾 Bekräfta och spara")
        if submit:
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            df = update_calculations(df)
            save_data(df)
            st.success(f"Rad för dag {ny_rad['Dag']} sparad!")
    return df

def kontrollera_och_spara(ny_rad, df):
    df_temp = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    df_temp = update_calculations(df_temp)
    sista = df_temp.iloc[-1]
    summa_tid = sista["Summa tid"]
    tid_kille = sista["Tid kille"]

    if summa_tid > 17 or tid_kille < 9 or tid_kille > 15:
        return visa_redigeringsform(ny_rad, df)
    else:
        df = df_temp
        save_data(df)
        st.success(f"Rad för dag {ny_rad['Dag']} sparad!")
        return df

def slumpa_radfilm(df, stor=False):
    maxvarden = hamta_maxvarden(df)
    dagar = df[df["Dag"] > 0]["Dag"]
    ny_dag = 1 if dagar.empty else dagar.max() + 1

    def mellan(minv, maxv):
        return random.randint(minv, maxv)

    if stor:
        ny_rad = {
            "Dag": ny_dag,
            "Nya killar": mellan(60, 200),
            "Fitta": mellan(10, 30),
            "Röv": mellan(10, 30),
            "DM": mellan(50, 100),
            "DF": mellan(50, 100),
            "DA": mellan(50, 100),
            "TPP": mellan(30, 80),
            "TAP": mellan(30, 80),
            "TP": mellan(30, 80),
        }
    else:
        ny_rad = {
            "Dag": ny_dag,
            "Nya killar": mellan(10, 50),
            "Fitta": mellan(3, 12),
            "Röv": mellan(3, 12),
            "DM": mellan(10, 25),
            "DF": mellan(10, 25),
            "DA": 0,
            "TPP": 0,
            "TAP": 0,
            "TP": 0,
        }

    ny_rad.update({
        "Älskar": 12,
        "Sover med": 1,
        "Tid S": 60,
        "Tid D": 70,
        "Tid T": 80,
        "Vila": 7,
        "Jobb": mellan(3, maxvarden["Jobb"]),
        "Grannar": mellan(3, maxvarden["Grannar"]),
        "Tjej PojkV": mellan(3, maxvarden["Tjej PojkV"]),
        "Nils familj": mellan(3, maxvarden["Nils familj"]),
        "Svarta": random.choice([0, ny_rad["Nya killar"]]),
        "DeepT": 0,
        "Sekunder": 0,
        "Vila mun": 0,
        "Varv": 0,
    })

    for key in ALL_COLUMNS:
        if key not in ny_rad:
            ny_rad[key] = 0

    st.info("🎲 Granskning av slumpad filmrad innan spara")
    return visa_redigeringsform(ny_rad, df)

def knapp_vilodag(df, variant="jobb"):
    dagar = df[df["Dag"] > 0]["Dag"]
    ny_dag = 1 if dagar.empty else dagar.max() + 1
    maxvarden = hamta_maxvarden(df)

    if variant == "jobb":
        rad = {
            "Dag": ny_dag,
            "Älskar": 12,
            "Sover med": 1,
            "Jobb": round(0.3 * maxvarden["Jobb"]),
            "Grannar": round(0.3 * maxvarden["Grannar"]),
            "Tjej PojkV": round(0.3 * maxvarden["Tjej PojkV"]),
            "Nils familj": round(0.3 * maxvarden["Nils familj"]),
        }
    elif variant == "hemma":
        rad = {
            "Dag": ny_dag,
            "Älskar": 6,
            "Jobb": 5,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils familj": 5,
        }
    else:
        rad = {"Dag": ny_dag}

    for key in ALL_COLUMNS:
        if key not in rad:
            rad[key] = 0

    return kontrollera_och_spara(rad, df)

def visa_statistik(df):
    st.subheader("📈 Statistik")

    df_data = df[df["Dag"] > 0]
    dag0 = df[df["Dag"] == 0]
    kompisar_max = dag0["Jobb"].sum() + dag0["Grannar"].sum() + dag0["Tjej PojkV"].sum() + dag0["Nils familj"].sum()
    nils_max = dag0["Nils familj"].sum()

    # Grunddata
    filmer = df_data[df_data["Nya killar"] > 0]["Filmer"].sum()
    sålda_film = df_data["Filmer"].sum()
    män_tot = df_data["Nya killar"].sum() + kompisar_max
    älskat = df_data["Älskar"].sum()
    sovit = df_data["Sover med"].sum()
    jobb = df_data["Jobb"].sum()
    grannar = df_data["Grannar"].sum()
    pojkv = df_data["Tjej PojkV"].sum()
    nils = df_data["Nils familj"].sum()
    svarta = df_data["Svarta"].sum()
    vita = df_data["Nya killar"].sum() - svarta
    intäkter = df_data["Intäkter"].sum()
    malin_lön = df_data["Malin lön"].sum()
    vänners_lön = df_data["Kompisar"].sum()

    # Snitt GB
    df_gb = df_data[df_data["Nya killar"] > 0]
    snitt_gb = (df_gb["Män"] / df_gb["Filmer"].replace(0, 1)).mean()

    # Procentberäkningar
    älskat_snitt = älskat / kompisar_max if kompisar_max > 0 else 0
    sovit_snitt = sovit / nils_max if nils_max > 0 else 0
    svarta_pct = svarta / df_data["Nya killar"].sum() if df_data["Nya killar"].sum() > 0 else 0
    vita_pct = vita / df_data["Nya killar"].sum() if df_data["Nya killar"].sum() > 0 else 0
    malin_roi = malin_lön / (älskat + sovit + df_data["Nya killar"].sum() + df_data["Känner"].sum()) if (älskat + sovit + df_data["Nya killar"].sum() + df_data["Känner"].sum()) > 0 else 0

    # Män per dag
    rader_med_data = df_data[
        (df_data["Nya killar"] > 0) |
        (df_data["Älskar"] > 0) |
        (df_data["Sover med"] > 0) |
        (df_data["Känner"] > 0)
    ]
    män_per_dag = (
        älskat + sovit + df_data["Nya killar"].sum() + df_data["Känner"].sum()
    ) / len(rader_med_data) if len(rader_med_data) > 0 else 0

    # Kompisarnas aktievärde
    sista_kurs = df_data["Kompisar"].iloc[-1] if not df_data.empty else 0
    aktievärde = 5000 * sista_kurs

    # VännerGB (kompisar relation till dag 0)
    vännerGB = df_data["Känner"].sum() / kompisar_max if kompisar_max > 0 else 0

    # Summeringar
    sex_kompisar = älskat / kompisar_max + vännerGB if kompisar_max > 0 else 0
    sex_familj = sex_kompisar + sovit / nils_max if nils_max > 0 else 0

    # Layout
    col1, col2 = st.columns(2)

    with col1:
        st.metric("🎬 Filmer (med killar)", filmer)
        st.metric("🎟 Sålda filmer", sålda_film)
        st.metric("👨 Totalt antal män", män_tot)
        st.metric("💓 Älskat", älskat)
        st.metric("🛏 Sovit med", sovit)
        st.metric("🏢 Jobb", jobb)
        st.metric("🏘 Grannar", grannar)

    with col2:
        st.metric("👫 Tjej PojkV", pojkv)
        st.metric("👨‍👩‍👧‍👦 Nils familj", nils)
        st.metric("🖤 Svarta", svarta)
        st.metric("🤍 Vita", vita)
        st.metric("💰 Intäkter", f"{intäkter:,.2f} USD")
        st.metric("💸 Malin lön", f"{malin_lön:,.2f} USD")
        st.metric("👥 Vänners lön", f"{vänners_lön:,.2f} USD")

    # Procentstatistik
    st.markdown("### 📊 Procent & Snitt")
    st.write(f"**Älskat per kompis:** {älskat_snitt:.2f}")
    st.write(f"**Sovit per Nils fam:** {sovit_snitt:.2f}")
    st.write(f"**Svarta i %:** {svarta_pct:.2%}")
    st.write(f"**Vita i %:** {vita_pct:.2%}")
    st.write(f"**Malin ROI per man:** {malin_roi:.2f}")
    st.write(f"**Malin män per dag:** {män_per_dag:.2f}")
    st.write(f"**Snitt GB (män per film):** {snitt_gb:.2f}")
    st.write(f"**VännerGB:** {vännerGB:.2f}")

    # Summering
    st.markdown("### 🔢 Summering")
    st.write(f"**Sex med kompisar:** {sex_kompisar:.2f}")
    st.write(f"**Sex med familj:** {sex_familj:.2f}")
    st.write(f"**Kompisars aktievärde:** {aktievärde:,.2f} USD")

def main():
    st.set_page_config(layout="wide")
    st.title("📘 MalinData – Daglig inmatning & beräkningar")

    # Sidväljare
    sida = st.sidebar.radio("📂 Välj vy", ["Data", "Statistik"])

    df = load_data()
    df = update_calculations(df)

    # Hantera maxvärden
    df = formulär_maxvärden(df)

    if sida == "Data":
        # Skapa nya rader via formulär och knappar
        df = skapa_ny_radform(df)
        df = knapp_slumpa_film(df)
        df = knapp_vilodagar(df)
        df = knapp_kopiera_storsta(df)

        # Visa tabell
        visa_data(df)

    elif sida == "Statistik":
        visa_statistik(df)

if __name__ == "__main__":
    main()
