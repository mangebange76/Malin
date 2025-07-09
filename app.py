import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import random

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
    return df[ALL_COLUMNS]

def hamta_maxvarden(df):
    dag0 = df[df["Dag"] == 0]
    return {
        "Jobb": dag0["Jobb"].max(),
        "Grannar": dag0["Grannar"].max(),
        "Tjej PojkV": dag0["Tjej PojkV"].max(),
        "Nils familj": dag0["Nils familj"].max()
    }

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

    # Grundberäkning av summa tid (inkl. älskar och sover med)
    df["Summa tid"] = (
        df["Summa singel"] +
        df["Summa dubbel"] +
        df["Summa trippel"] +
        df["Tid mun"] +
        df["Älskar"] * 1800 +
        df["Sover med"] * 1800
    ) / 3600

    # 3 timmar för rader med bara "Känner" > 0 men övriga 0
    mask_bara_kompisar = (
        (df["Känner"] > 0) &
        (df["Nya killar"] == 0) &
        (df["Älskar"] == 0) &
        (df["Sover med"] == 0) &
        (df["DM"] + df["DF"] + df["DA"] + df["TPP"] + df["TAP"] + df["TP"] == 0)
    )
    df.loc[mask_bara_kompisar, "Summa tid"] = 3

    df["Suger"] = df.apply(
        lambda row: 0 if row["Män"] == 0 else 0.6 * (row["Summa tid"] * 3600) / row["Män"],
        axis=1
    )

    df["Tid kille"] = df.apply(lambda row: 0 if row["Män"] == 0 else (
        row["Summa singel"] +
        2 * row["Summa dubbel"] +
        3 * row["Summa trippel"] +
        row["Suger"] / row["Män"] +
        row["Tid mun"] +
        row["Sover med"] * 1800  # extra tid per sover med
    ) / 60, axis=1)

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

    # Aktiekurs (slumpmässig justering baserat på prestation jämfört med snitt)
    snitt_hardhet = df[df["Dag"] > 0]["Hårdhet"].mean()
    snitt_män = df[df["Dag"] > 0]["Män"].mean()
    snitt_tid_mun = df[df["Dag"] > 0]["Tid mun"].mean()
    snitt_da = df[df["Dag"] > 0]["DA"].mean()
    snitt_tpp = df[df["Dag"] > 0]["TPP"].mean()
    snitt_tap = df[df["Dag"] > 0]["TAP"].mean()
    snitt_tp = df[df["Dag"] > 0]["TP"].mean()

    for i, row in df.iterrows():
        if row["Dag"] == 0:
            df.at[i, "Aktiekurs"] = 40.00
            continue

        faktorer = 0
        if row["Hårdhet"] > snitt_hardhet: faktorer += 1
        if row["Män"] > snitt_män: faktorer += 1
        if row["Tid mun"] > snitt_tid_mun: faktorer += 1
        if row["DA"] > snitt_da: faktorer += 1
        if row["TPP"] > snitt_tpp: faktorer += 1
        if row["TAP"] > snitt_tap: faktorer += 1
        if row["TP"] > snitt_tp: faktorer += 1

        if faktorer >= 4:
            förändring = random.uniform(1.03, 1.10)
        else:
            förändring = random.uniform(0.90, 0.97)

        tidigare_kurs = df.at[i - 1, "Aktiekurs"] if i > 0 else 40.00
        df.at[i, "Aktiekurs"] = round(tidigare_kurs * förändring, 2)

    return df

def formulär_maxvärden(df):
    with st.expander("🎯 Maxvärden (Dag 0)", expanded=False):
        dag0 = df[df["Dag"] == 0]
        if dag0.empty:
            st.info("Inga maxvärden inmatade ännu.")
            maxrad = {k: 0 for k in ALL_COLUMNS}
            maxrad["Dag"] = 0
        else:
            maxrad = dag0.iloc[0].to_dict()

        col1, col2, col3, col4 = st.columns(4)
        maxrad["Jobb"] = col1.number_input("Jobb", value=int(maxrad["Jobb"]), min_value=0)
        maxrad["Grannar"] = col2.number_input("Grannar", value=int(maxrad["Grannar"]), min_value=0)
        maxrad["Tjej PojkV"] = col3.number_input("Tjej PojkV", value=int(maxrad["Tjej PojkV"]), min_value=0)
        maxrad["Nils familj"] = col4.number_input("Nils familj", value=int(maxrad["Nils familj"]), min_value=0)

        if st.button("💾 Spara maxvärden (Dag 0)"):
            df = df[df["Dag"] != 0]
            df = pd.concat([pd.DataFrame([maxrad]), df], ignore_index=True)
            df = update_calculations(df)
            save_data(df)
            st.success("Maxvärden uppdaterade!")

    return df


def skapa_rad_form(df, default_values):
    st.subheader("➕ Skapa/redigera ny rad")
    dag = int(df["Dag"].max()) + 1
    st.write(f"Dag: {dag}")
    input_data = {"Dag": dag}

    with st.form("ny_rad_form"):
        cols = st.columns(4)
        for i, kolumn in enumerate([
            "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
            "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D",
            "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
            "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv"
        ]):
            value = default_values.get(kolumn, 0)
            input_data[kolumn] = cols[i % 4].number_input(kolumn, value=int(value), min_value=0)

        submitted = st.form_submit_button("✅ Bekräfta och spara rad")
        if submitted:
            # Validera maxvärden
            maxdata = hamta_maxvarden(df)
            for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
                if input_data[fält] > maxdata.get(fält, 0):
                    st.error(f"{fält} överskrider maxvärde! Uppdatera först i Dag 0.")
                    return df

            for kol in ALL_COLUMNS:
                if kol not in input_data:
                    input_data[kol] = 0
            ny_rad = pd.DataFrame([input_data])
            df = pd.concat([df, ny_rad], ignore_index=True)
            df = update_calculations(df)
            save_data(df)
            st.success("Ny rad sparad!")

    return df

import random

def skapa_redigerbar_rad(df, standardvärden):
    st.subheader("🧪 Förhandsgranska och redigera innan sparande")
    ny_rad = {}
    cols = st.columns(4)
    for i, kolumn in enumerate([
        "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
        "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D",
        "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
        "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv"
    ]):
        ny_rad[kolumn] = cols[i % 4].number_input(
            kolumn, value=int(standardvärden.get(kolumn, 0)), min_value=0, key=f"{kolumn}_{random.randint(0,999999)}"
        )

    if st.button("✅ Spara redigerad rad"):
        maxdata = hamta_maxvarden(df)
        dag = int(df["Dag"].max()) + 1
        ny_rad["Dag"] = dag
        for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
            if ny_rad[fält] > maxdata.get(fält, 0):
                st.error(f"{fält} överskrider maxvärde från Dag 0!")
                return df
        for kol in ALL_COLUMNS:
            if kol not in ny_rad:
                ny_rad[kol] = 0
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)

        tid = df.iloc[-1]["Summa tid"]
        tid_kille = df.iloc[-1]["Tid kille"]
        if tid > 17:
            st.warning("⚠️ Summa tid överstiger 17 timmar.")
        if tid_kille < 9 or tid_kille > 15:
            st.warning("⚠️ Tid per kille ligger utanför 9–15 minuter.")

        save_data(df)
        st.success("Raden har sparats.")
    return df


def knappfunktioner(df):
    st.subheader("⚙️ Snabbkommandon")

    col1, col2, col3, col4 = st.columns(4)

    # Kopiera raden med flest nya killar
    if col1.button("📋 Kopiera största raden"):
        största = df[df["Dag"] > 0].sort_values("Nya killar", ascending=False).iloc[0]
        data = största[ALL_COLUMNS].to_dict()
        data["Dag"] = int(df["Dag"].max()) + 1
        for k in ["Känner", "Män", "Snitt", "Tid mun", "Summa singel", "Summa dubbel", "Summa trippel",
                  "Summa tid", "Suger", "Tid kille", "Filmer", "Hårdhet", "Intäkter", "Malin lön", "Kompisar"]:
            data[k] = 0
        df = skapa_redigerbar_rad(df, data)

    maxdata = hamta_maxvarden(df)

    # Vila jobb
    if col2.button("😴 Vila jobb"):
        dag = int(df["Dag"].max()) + 1
        rad = {
            "Dag": dag,
            "Älskar": 12,
            "Sover med": 1,
            "Jobb": round(maxdata["Jobb"] * 0.3),
            "Grannar": round(maxdata["Grannar"] * 0.3),
            "Tjej PojkV": round(maxdata["Tjej PojkV"] * 0.3),
            "Nils familj": round(maxdata["Nils familj"] * 0.3)
        }
        df = skapa_redigerbar_rad(df, rad)

    # Vila hemma
    if col3.button("🏡 Vila hemma"):
        dag = int(df["Dag"].max()) + 1
        rad = {
            "Dag": dag,
            "Älskar": 6,
            "Jobb": 5,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils familj": 5
        }
        df = skapa_redigerbar_rad(df, rad)

    # Vila helt
    if col4.button("🚫 Vila helt"):
        dag = int(df["Dag"].max()) + 1
        rad = {"Dag": dag}
        df = skapa_redigerbar_rad(df, rad)

    # Slumpa film liten
    if st.button("🎲 Slumpa Film liten"):
        rad = {
            "Nya killar": random.randint(10, 50),
            "Fitta": random.randint(3, 12),
            "Röv": random.randint(3, 12),
            "DM": random.randint(10, 25),
            "DF": random.randint(10, 25),
            "DA": 0,
            "TPP": 0, "TAP": 0, "TP": 0,
            "Älskar": 12, "Sover med": 1,
            "Tid S": 60, "Tid D": 70, "Tid T": 80, "Vila": 7,
            "Jobb": random.randint(3, maxdata["Jobb"]),
            "Grannar": random.randint(3, maxdata["Grannar"]),
            "Tjej PojkV": random.randint(3, maxdata["Tjej PojkV"]),
            "Nils familj": random.randint(3, maxdata["Nils familj"]),
            "Svarta": random.choice([0, 1])
        }
        rad["Svarta"] = rad["Nya killar"] if rad["Svarta"] == 1 else 0
        df = skapa_redigerbar_rad(df, rad)

    # Slumpa film stor
    if st.button("🎬 Slumpa Film stor"):
        rad = {
            "Nya killar": random.randint(60, 200),
            "Fitta": random.randint(10, 30),
            "Röv": random.randint(10, 30),
            "DM": random.randint(50, 100),
            "DF": random.randint(50, 100),
            "DA": random.randint(50, 100),
            "TPP": random.randint(30, 80),
            "TAP": random.randint(30, 80),
            "TP": random.randint(30, 80),
            "Älskar": 12, "Sover med": 1,
            "Tid S": 60, "Tid D": 70, "Tid T": 80, "Vila": 7,
            "Jobb": random.randint(3, maxdata["Jobb"]),
            "Grannar": random.randint(3, maxdata["Grannar"]),
            "Tjej PojkV": random.randint(3, maxdata["Tjej PojkV"]),
            "Nils familj": random.randint(3, maxdata["Nils familj"]),
            "Svarta": random.choice([0, 1])
        }
        rad["Svarta"] = rad["Nya killar"] if rad["Svarta"] == 1 else 0
        df = skapa_redigerbar_rad(df, rad)

    return df

def visa_statistik(df):
    st.subheader("📊 Statistik")

    df_data = df[df["Dag"] > 0].copy()
    dag0 = df[df["Dag"] == 0]
    maxvärden = hamta_maxvarden(df)

    # Grundläggande summeringar
    antal_rader = len(df_data)
    antal_män = df_data["Nya killar"].sum() + maxvärden["Jobb"] + maxvärden["Grannar"] + maxvärden["Tjej PojkV"] + maxvärden["Nils familj"]
    filmer = df_data[df_data["Nya killar"] > 0]["Filmer"].sum()
    snitt_gb = (df_data[df_data["Nya killar"] > 0]["Män"].sum() / filmer) if filmer > 0 else 0

    älskat = df_data["Älskar"].sum()
    sovit = df_data["Sover med"].sum()
    svarta = df_data["Svarta"].sum()
    vita = df_data["Nya killar"].sum() - svarta
    sålda_filmer = df_data["Filmer"].sum()
    intäkter = df_data["Intäkter"].sum()
    malin_lön = df_data["Malin lön"].sum()
    vänners_lön = df_data["Kompisar"].sum()

    # ROI
    män_total = df_data["Nya killar"].sum() + df_data["Älskar"].sum() + df_data["Sover med"].sum() + df_data["Känner"].sum()
    malin_roi = malin_lön / män_total if män_total > 0 else 0

    # Kompisars aktievärde
    sista_kurs = df_data.iloc[-1]["Aktiekurs"] if "Aktiekurs" in df_data.columns else 40.0
    aktievärde_kompisar = 5000 * sista_kurs

    # Investerat värde i kompisar
    investerat_värde = 200_000 * (maxvärden["Jobb"] + maxvärden["Grannar"] + maxvärden["Tjej PojkV"] + maxvärden["Nils familj"])

    # Vänners lön justerat
    justerad_vänners_lön = vänners_lön - investerat_värde

    # Snittvärden
    snitt_älskat = älskat / (maxvärden["Jobb"] + maxvärden["Grannar"] + maxvärden["Tjej PojkV"]) if (maxvärden["Jobb"] + maxvärden["Grannar"] + maxvärden["Tjej PojkV"]) > 0 else 0
    snitt_sovit = sovit / maxvärden["Nils familj"] if maxvärden["Nils familj"] > 0 else 0
    procent_svarta = svarta / df_data["Nya killar"].sum() if df_data["Nya killar"].sum() > 0 else 0
    procent_vita = vita / df_data["Nya killar"].sum() if df_data["Nya killar"].sum() > 0 else 0

    # VännerGB
    vänner_gb = df_data["Känner"].sum() / maxvärden["Jobb"] if maxvärden["Jobb"] > 0 else 0

    # Summeringar
    sex_kompisar = snitt_älskat + vänner_gb
    sex_familj = snitt_älskat + vänner_gb + snitt_sovit

    # Visa statistiken
    st.markdown("### Sammanställning")
    st.markdown(f"- 📽️ **Filmer (med killar):** {filmer}")
    st.markdown(f"- 🎬 **Sålda filmer:** {sålda_filmer}")
    st.markdown(f"- 👨‍👦‍👦 **Totalt antal män:** {antal_män}")
    st.markdown(f"- 💾 **Snitt GB (män/film):** {snitt_gb:.2f}")
    st.markdown("---")
    st.markdown(f"- ❤️ **Älskat:** {älskat}")
    st.markdown(f"- 🛏️ **Sovit med:** {sovit}")
    st.markdown(f"- 👥 **Jobb:** {df_data['Jobb'].sum()}")
    st.markdown(f"- 🏡 **Grannar:** {df_data['Grannar'].sum()}")
    st.markdown(f"- 💑 **Tjej PojkV:** {df_data['Tjej PojkV'].sum()}")
    st.markdown(f"- 👨‍👩‍👧 **Nils familj:** {df_data['Nils familj'].sum()}")
    st.markdown("---")
    st.markdown(f"- ⚫ **Svarta:** {svarta}")
    st.markdown(f"- ⚪ **Vita:** {vita}")
    st.markdown(f"- 💰 **Intäkter:** {intäkter:,.2f} USD")
    st.markdown(f"- 👩 **Malin lön:** {malin_lön:,.2f} USD")
    st.markdown(f"- 🧠 **Vänners lön (justerat):** {justerad_vänners_lön:,.2f} USD")
    st.markdown(f"- 📈 **Kompisars aktievärde (5000 st):** {aktievärde_kompisar:,.2f} USD")
    st.markdown("---")
    st.markdown(f"- 📊 **Malin ROI per man:** {malin_roi:.2f} USD")
    st.markdown(f"- 🧮 **Älskat snitt / kompis:** {snitt_älskat:.2f}")
    st.markdown(f"- 🛏️ **Sovit snitt / familj:** {snitt_sovit:.2f}")
    st.markdown(f"- ⚫ **Svarta (%):** {procent_svarta:.2%}")
    st.markdown(f"- ⚪ **Vita (%):** {procent_vita:.2%}")
    st.markdown(f"- 🤝 **VännerGB:** {vänner_gb:.2f}")
    st.markdown("---")
    st.markdown(f"- 💞 **Sex med kompisar:** {sex_kompisar:.2f}")
    st.markdown(f"- 💞 **Sex med familj:** {sex_familj:.2f}")

def main():
    st.set_page_config(page_title="MalinData", layout="wide")
    st.title("🎬 MalinData")

    df = load_data()

    vy = st.sidebar.radio("Välj vy", ["📋 Huvudformulär", "📊 Statistik"])

    if vy == "📋 Huvudformulär":
        df = formulär_maxvärden(df)
        df = knappfunktioner(df)

    elif vy == "📊 Statistik":
        df = update_calculations(df)
        visa_statistik(df)


if __name__ == "__main__":
    main()
