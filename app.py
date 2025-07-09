import streamlit as st
import pandas as pd
import random
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"])
worksheet = sheet.worksheet("Blad1")

# Kolumner
ALL_COLUMNS = [
    "Veckodag", "Dag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Älskar", "Sover med", "Tid S", "Tid D", "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV",
    "Nils familj", "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv", "Känner", "Män",
    "Summa singel", "Summa dubbel", "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger",
    "Tid kille", "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar", "Aktiekurs"
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

def formulär_maxvärden(df):
    st.subheader("⚙️ Sätt maxvärden för Dag = 0")

    dag0 = df[df["Dag"] == 0]
    if not dag0.empty:
        maxrad = dag0.iloc[0]
    else:
        maxrad = {k: 0 for k in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]}

    with st.form("form_max"):
        jobb = st.number_input("Max Jobb", value=int(maxrad.get("Jobb", 0)), step=1)
        grannar = st.number_input("Max Grannar", value=int(maxrad.get("Grannar", 0)), step=1)
        pojkv = st.number_input("Max Tjej PojkV", value=int(maxrad.get("Tjej PojkV", 0)), step=1)
        nils = st.number_input("Max Nils familj", value=int(maxrad.get("Nils familj", 0)), step=1)
        kurs = st.number_input("Startkurs aktie", value=float(maxrad.get("Aktiekurs", 40.0)))
        submit = st.form_submit_button("💾 Spara maxvärden")

        if submit:
            df = df[df["Dag"] != 0]
            ny_maxrad = {col: 0 for col in ALL_COLUMNS}
            ny_maxrad.update({
                "Dag": 0,
                "Veckodag": "Max",
                "Jobb": jobb,
                "Grannar": grannar,
                "Tjej PojkV": pojkv,
                "Nils familj": nils,
                "Aktiekurs": kurs
            })
            df = pd.concat([pd.DataFrame([ny_maxrad]), df], ignore_index=True)
            save_data(df)
            st.success("Maxvärden uppdaterade.")
    return df

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
    ) / 3600

    df["Suger"] = df.apply(lambda row: 0 if row["Män"] == 0 else 0.6 * ((row["Summa tid"] * 3600) / row["Män"]), axis=1)

    df["Tid kille"] = df.apply(lambda row: 0 if row["Män"] == 0 else (
        row["Summa singel"] +
        2 * row["Summa dubbel"] +
        3 * row["Summa trippel"] +
        row["Suger"] / row["Män"] +
        row["Tid mun"]
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

    # Rader där Känner > 0 men allt annat 0 → 3h tid
    df["Summa tid"] = df.apply(
        lambda row: 3 if (
            row["Känner"] > 0 and
            row[["Nya killar", "Älskar", "Sover med", "Summa singel", "Summa dubbel", "Summa trippel", "Tid mun"]].sum() == 0
        ) else row["Summa tid"], axis=1
    )

    return df

def visa_redigeringsformulär(rad, dagnummer):
    st.subheader("✏️ Redigera värden innan spara")
    ny_rad = {"Dag": dagnummer}

    with st.form("form_redigera_rad"):
        for kolumn in ALL_COLUMNS:
            if kolumn == "Veckodag":
                continue
            elif kolumn == "Dag":
                st.markdown(f"**Dag:** {dagnummer}")
            elif kolumn in rad:
                if isinstance(rad[kolumn], int) or isinstance(rad[kolumn], float):
                    ny_rad[kolumn] = st.number_input(kolumn, value=float(rad[kolumn]), step=1.0 if isinstance(rad[kolumn], float) else 1)
                else:
                    ny_rad[kolumn] = st.text_input(kolumn, value=str(rad[kolumn]))
            else:
                ny_rad[kolumn] = st.number_input(kolumn, value=0, step=1)
        submit = st.form_submit_button("✅ Spara redigerad rad")

    return ny_rad if submit else None

def spara_redigerad_rad(df, ny_rad):
    for key in ALL_COLUMNS:
        if key not in ny_rad:
            ny_rad[key] = 0

    df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    df = update_calculations(df)
    save_data(df)

    timmar = ny_rad.get("Summa tid", 0)
    tid_kille = ny_rad.get("Tid kille", 0)

    if timmar > 17:
        st.warning(f"⚠️ Summa tid är {round(timmar, 2)} timmar – över 17h. Redigera kan vara nödvändigt.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid per kille är {round(tid_kille, 2)} min – ligger utanför 9-15 min. Kontrollera!")

    st.success(f"✅ Raden för Dag {ny_rad['Dag']} sparades.")

    return df

import random

def generera_filmrad(typ, maxvarden):
    if typ == "liten":
        nya_killar = random.randint(10, 50)
        fitta = random.randint(3, 12)
        rov = random.randint(3, 12)
        dm = random.randint(10, 25)
        df = random.randint(10, 25)
        da = 0
        tpp = tap = tp = 0
    else:  # stor
        nya_killar = random.randint(60, 200)
        fitta = random.randint(10, 30)
        rov = random.randint(10, 30)
        dm = random.randint(50, 100)
        df = random.randint(50, 100)
        da = random.randint(50, 100)
        tpp = random.randint(30, 80)
        tap = random.randint(30, 80)
        tp = random.randint(30, 80)

    return {
        "Nya killar": nya_killar,
        "Fitta": fitta,
        "Röv": rov,
        "DM": dm,
        "DF": df,
        "DA": da,
        "TPP": tpp,
        "TAP": tap,
        "TP": tp,
        "Älskar": 12,
        "Sover med": 1,
        "Tid S": 60,
        "Tid D": 70,
        "Tid T": 80,
        "Vila": 7,
        "Jobb": random.randint(3, maxvarden.get("Jobb", 3)),
        "Grannar": random.randint(3, maxvarden.get("Grannar", 3)),
        "Tjej PojkV": random.randint(3, maxvarden.get("Tjej PojkV", 3)),
        "Nils familj": random.randint(3, maxvarden.get("Nils familj", 3)),
        "Svarta": random.choice([0, nya_killar]),
        "DeepT": 0,
        "Sekunder": 0,
        "Vila mun": 0,
        "Varv": 0
    }

def knappfunktioner(df):
    st.subheader("🎬 Filmknappar och viloknappar")
    maxvarden = hamta_maxvarden(df)
    dag = 1 if df[df["Dag"] > 0].empty else df["Dag"].max() + 1

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎲 Slumpa Film liten"):
            rad = generera_filmrad("liten", maxvarden)
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_redigerad_rad(df, ny_rad)

    with col2:
        if st.button("🎲 Slumpa Film stor"):
            rad = generera_filmrad("stor", maxvarden)
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_redigerad_rad(df, ny_rad)

    with col3:
        if st.button("📋 Kopiera största raden (Nya killar)"):
            rader = df[df["Dag"] > 0]
            if not rader.empty:
                rad = rader.loc[rader["Nya killar"].idxmax()].to_dict()
                rad["Dag"] = dag
                ny_rad = visa_redigeringsformulär(rad, dag)
                if ny_rad:
                    df = spara_redigerad_rad(df, ny_rad)

    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💼 Vilodag jobb"):
            rad = {
                "Älskar": 12,
                "Sover med": 1,
                "Jobb": round(0.3 * maxvarden.get("Jobb", 0)),
                "Grannar": round(0.3 * maxvarden.get("Grannar", 0)),
                "Tjej PojkV": round(0.3 * maxvarden.get("Tjej PojkV", 0)),
                "Nils familj": round(0.3 * maxvarden.get("Nils familj", 0))
            }
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_redigerad_rad(df, ny_rad)

    with c2:
        if st.button("🏡 Vilodag hemma"):
            rad = {
                "Älskar": 6,
                "Jobb": 5,
                "Grannar": 3,
                "Tjej PojkV": 3,
                "Nils familj": 5
            }
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_redigerad_rad(df, ny_rad)

    with c3:
        if st.button("🛌 Vila helt"):
            rad = {}
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_redigerad_rad(df, ny_rad)

    return df

def statistikvy(df):
    st.subheader("📊 Statistik")

    dag0 = df[df["Dag"] == 0]
    max_jobb = dag0["Jobb"].sum()
    max_grannar = dag0["Grannar"].sum()
    max_pojkv = dag0["Tjej PojkV"].sum()
    max_nils = dag0["Nils familj"].sum()
    max_vänner = max_jobb + max_grannar + max_pojkv + max_nils

    filmer_df = df[df["Nya killar"] > 0]
    antal_filmer = len(filmer_df)
    sum_män_filmer = filmer_df["Män"].sum()
    snitt_gb = sum_män_filmer / antal_filmer if antal_filmer > 0 else 0

    total_män = df["Nya killar"].sum() + max_vänner
    total_alskar = df["Älskar"].sum()
    total_sover = df["Sover med"].sum()
    total_kanner = df["Känner"].sum()
    total_filmer = df["Filmer"].sum()
    total_intakt = df["Intäkter"].sum()
    total_malin = df["Malin lön"].sum()
    total_kompisar = df["Kompisar"].sum()
    total_svarta = df["Svarta"].sum()
    total_nyakillar = df["Nya killar"].sum()
    total_vita = total_nyakillar - total_svarta

    vänner_gb = total_kanner / max_vänner if max_vänner > 0 else 0
    alskat_snitt = total_alskar / max_vänner if max_vänner > 0 else 0
    sovit_snitt = total_sover / max_nils if max_nils > 0 else 0
    svarta_procent = (total_svarta / total_nyakillar * 100) if total_nyakillar > 0 else 0
    vita_procent = (total_vita / total_nyakillar * 100) if total_nyakillar > 0 else 0

    malin_roi = total_malin / (total_alskar + total_sover + total_nyakillar + total_kanner) if (total_alskar + total_sover + total_nyakillar + total_kanner) > 0 else 0

    aktiekurs = df[df["Dag"] == df["Dag"].max()]["Aktiekurs"].values[0] if not df[df["Dag"] == df["Dag"].max()].empty else 40.0
    aktier = 5000
    aktievarde = aktiekurs * aktier

    # Investerat = 200 000 USD per kompis (maxvärde dag 0)
    investering = max_vänner * 200_000
    justerat_kompisar = total_kompisar - investering

    # Summering
    kompis_sum = alskat_snitt + vänner_gb
    familj_sum = alskat_snitt + vänner_gb + sovit_snitt

    st.markdown(f"**🎬 Antal filmer:** {antal_filmer}")
    st.markdown(f"**👨 Totalt antal män:** {int(total_män)}")
    st.markdown(f"**📈 Snitt GB:** {snitt_gb:.2f}")
    st.markdown(f"**💞 Älskat (summa):** {int(total_alskar)}")
    st.markdown(f"**🛏️ Sovit med (summa):** {int(total_sover)}")
    st.markdown(f"**💼 Jobb:** {int(df['Jobb'].sum())}")
    st.markdown(f"**🏡 Grannar:** {int(df['Grannar'].sum())}")
    st.markdown(f"**💑 Tjej PojkV:** {int(df['Tjej PojkV'].sum())}")
    st.markdown(f"**👪 Nils familj:** {int(df['Nils familj'].sum())}")
    st.markdown(f"**🖤 Svarta:** {int(total_svarta)}")
    st.markdown(f"**🤍 Vita:** {int(total_vita)}")
    st.markdown(f"**🎥 Sålda filmer:** {int(total_filmer)}")
    st.markdown(f"**💵 Intäkter:** {total_intakt:,.2f} USD")
    st.markdown(f"**👩 Malin lön:** {total_malin:,.2f} USD")
    st.markdown(f"**👫 Vänners lön:** {justerat_kompisar:,.2f} USD")
    st.markdown(f"**📊 Malin andel av intäkt:** {total_malin / total_intakt * 100:.2f}%")
    st.markdown(f"**📈 Malin ROI per man:** {malin_roi:.2f} USD")
    st.markdown(f"**💚 Älskat/kompisar:** {alskat_snitt:.2f}")
    st.markdown(f"**💚 Sovit/Nils fam:** {sovit_snitt:.2f}")
    st.markdown(f"**💚 VännerGB:** {vänner_gb:.2f}")
    st.markdown(f"**💯 Svarta %:** {svarta_procent:.1f}%")
    st.markdown(f"**💯 Vita %:** {vita_procent:.1f}%")
    st.markdown(f"**💡 Summering - Sex med kompisar:** {kompis_sum:.2f}")
    st.markdown(f"**💡 Summering - Sex med familj:** {familj_sum:.2f}")
    st.markdown(f"**📊 Kompisars aktievärde:** {aktievarde:,.2f} USD")

def main():
    st.set_page_config(page_title="MalinApp", layout="wide")

    df = load_data()
    df = ensure_columns_exist(df)
    df = update_calculations(df)

    flik = st.sidebar.selectbox("Välj vy", ["📅 Dagar", "📊 Statistik"])

    if flik == "📅 Dagar":
        df = knappfunktioner(df)
    elif flik == "📊 Statistik":
        statistikvy(df)

    st.markdown("---")
    st.caption("MalinApp – version juli 2025")

if __name__ == "__main__":
    main()
