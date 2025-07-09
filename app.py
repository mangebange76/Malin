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
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Tid trippel",
    "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta", "DeepT",
    "Sekunder", "Vila mun", "Varv", "Känner", "Män", "Summa singel", "Summa dubbel",
    "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille",
    "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar",
    "Aktiekurs", "Kompisar aktievärde"
]

# Maxvärden som uppdateras från Dag = 0
def hamta_maxvarden(df):
    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    rad = dag0.iloc[0]
    return {
        "Jobb": rad.get("Jobb", 0),
        "Grannar": rad.get("Grannar", 0),
        "Tjej PojkV": rad.get("Tjej PojkV", 0),
        "Nils fam": rad.get("Nils fam", 0)
    }

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
    with st.form("Redigera rad", clear_on_submit=False):
        ny_rad = {}
        ny_rad["Dag"] = dag
        ny_rad["Veckodag"] = veckodag_from_dag(dag)
        for kolumn in ALL_COLUMNS:
            if kolumn in ["Dag", "Veckodag", "Känner", "Män", "Summa singel", "Summa dubbel",
                          "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille",
                          "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar",
                          "Kompisar aktievärde"]:
                continue
            typ = float if isinstance(rad[kolumn], float) else int
            ny_rad[kolumn] = st.number_input(
                kolumn,
                value=typ(rad.get(kolumn, 0)),
                step=1.0 if typ == float else 1
            )
        submitted = st.form_submit_button("Spara redigerad rad")
        if submitted:
            return ny_rad
    return None

def lägg_till_rad(df, ny_rad):
    ny_rad = pd.DataFrame([ny_rad])
    df = pd.concat([df, ny_rad], ignore_index=True)
    df = update_calculations(df)
    save_data(df)
    return df

def slumpa_film(df, stor=False):
    dag = get_next_day(df)
    maxvärden = hämta_maxvärden(df)

    if stor:
        nya_killar = random.randint(60, 200)
        fitta = random.randint(10, 30)
        röv = random.randint(10, 30)
        dm = random.randint(50, 100)
        df_ = random.randint(50, 100)
        da = random.randint(50, 100)
        tpp = random.randint(30, 80)
        tap = random.randint(30, 80)
        tp = random.randint(30, 80)
    else:
        nya_killar = random.randint(10, 50)
        fitta = random.randint(3, 12)
        röv = random.randint(3, 12)
        dm = random.randint(10, 25)
        df_ = random.randint(10, 25)
        da = 0
        tpp = 0
        tap = 0
        tp = 0

    ny_rad = {
        "Dag": dag,
        "Veckodag": veckodag_from_dag(dag),
        "Nya killar": nya_killar,
        "Fitta": fitta,
        "Röv": röv,
        "DM": dm,
        "DF": df_,
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
        "Jobb": random.randint(3, maxvärden.get("Jobb", 3)),
        "Grannar": random.randint(3, maxvärden.get("Grannar", 3)),
        "Tjej PojkV": random.randint(3, maxvärden.get("Tjej PojkV", 3)),
        "Nils familj": random.randint(3, maxvärden.get("Nils familj", 3)),
        "Svarta": random.choice([0, nya_killar]),
        "DeepT": 0,
        "Sekunder": 0,
        "Vila mun": 0,
        "Varv": 0,
    }

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
        ny_rad["Vila"] = 7
        ny_rad["Tid S"] = 60
        ny_rad["Tid D"] = 70
        ny_rad["Tid T"] = 80
        ny_rad["Tid mun"] = 0
    elif typ == "jobb":
        ny_rad["Jobb"] = round(maxvärden.get("Jobb", 0) * 0.3)
        ny_rad["Grannar"] = round(maxvärden.get("Grannar", 0) * 0.3)
        ny_rad["Tjej PojkV"] = round(maxvärden.get("Tjej PojkV", 0) * 0.3)
        ny_rad["Nils familj"] = round(maxvärden.get("Nils familj", 0) * 0.3)
    elif typ == "helt":
        pass  # Alla värden är redan nollade ovan

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

def slumpa_film(df, typ):
    dag = get_next_day(df)
    maxvärden = hämta_maxvärden(df)

    ny_rad = {kolumn: 0 for kolumn in ALL_COLUMNS}
    ny_rad["Dag"] = dag
    ny_rad["Veckodag"] = veckodag_from_dag(dag)

    import random

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

def visa_varningar(rad):
    summa_tid = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if summa_tid > 17:
        st.warning(f"⚠️ Summa tid är {summa_tid:.2f} timmar – det kan vara för mycket.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid per kille är {tid_kille:.2f} minuter – utanför rekommenderat intervall (9–15 min).")

def statistikvy(df):
    st.header("📊 Statistik")

    if df.empty:
        st.info("Ingen data tillgänglig ännu.")
        return

    dag_0 = df[df["Dag"] == 0]
    max_kompisar = dag_0[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
    max_nils = dag_0["Nils familj"].sum()

    filmer_med_killar = df[df["Nya killar"] > 0]
    filmer = len(filmer_med_killar)
    totalt_män = df["Nya killar"].sum() + max_kompisar
    snitt_gb = totalt_män / filmer if filmer > 0 else 0

    älskat = df["Älskar"].sum()
    sovit = df["Sover med"].sum()
    känner = df[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum()
    känner_summa = känner.sum()
    svarta = df["Svarta"].sum()
    vita = df["Nya killar"].sum() - svarta
    sålda_filmer = df["Filmer"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    kompisars_lön = df["Kompisar"].sum()

    älskat_snitt = älskat / max_kompisar if max_kompisar else 0
    sovit_snitt = sovit / max_nils if max_nils else 0
    svarta_procent = svarta / df["Nya killar"].sum() if df["Nya killar"].sum() else 0
    vita_procent = vita / df["Nya killar"].sum() if df["Nya killar"].sum() else 0

    roi = malin_lön / (älskat + sovit + df["Nya killar"].sum() + känner_summa) if (älskat + sovit + df["Nya killar"].sum() + känner_summa) else 0
    rader_med_kontakt = df[(df["Nya killar"] > 0) | (df["Älskar"] > 0) | (df["Sover med"] > 0) | (df["Känner"] > 0)]
    malin_män_per_dag = (älskat + sovit + df["Nya killar"].sum() + känner_summa) / len(rader_med_kontakt) if len(rader_med_kontakt) > 0 else 0

    # Kompisars aktievärde per person
    sista_kurs = df["Aktiekurs"].iloc[-1] if "Aktiekurs" in df.columns and not df["Aktiekurs"].isnull().all() else 40.0
    aktievärde_total = 5000 * sista_kurs
    antal_kompisar = max_kompisar
    aktievärde_per_kompis = aktievärde_total / antal_kompisar if antal_kompisar else 0

    vänner_gb = df["Känner"].sum() / max_kompisar if max_kompisar else 0
    sex_kompisar = älskat + vänner_gb
    sex_familj = älskat + vänner_gb + sovit_snitt

    st.subheader("🎬 Produktion")
    st.write(f"**Filmer (med killar):** {filmer}")
    st.write(f"**Sålda filmer:** {sålda_filmer}")
    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Snitt GB:** {snitt_gb:.2f}")

    st.subheader("🧮 Händelser")
    st.write(f"**Älskat:** {älskat}")
    st.write(f"**Sovit med:** {sovit}")
    st.write(f"**Jobb:** {känner['Jobb']}")
    st.write(f"**Grannar:** {känner['Grannar']}")
    st.write(f"**Tjej PojkV:** {känner['Tjej PojkV']}")
    st.write(f"**Nils familj:** {känner['Nils familj']}")
    st.write(f"**Svarta:** {svarta}")
    st.write(f"**Vita:** {vita}")

    st.subheader("💰 Ekonomi")
    st.write(f"**Intäkter:** {intäkter:.2f} USD")
    st.write(f"**Malin lön:** {malin_lön:.2f} USD")
    st.write(f"**Vänners lön:** {kompisars_lön:.2f} USD")
    st.write(f"**Malin andel av intäkt:** {malin_lön / intäkter * 100:.2f}%") if intäkter else None

    st.subheader("📈 Nyckeltal")
    st.write(f"**Älskat per kompis:** {älskat_snitt:.2f}")
    st.write(f"**Sovit med per Nils fam:** {sovit_snitt:.2f}")
    st.write(f"**Svarta i %:** {svarta_procent*100:.2f}%")
    st.write(f"**Vita i %:** {vita_procent*100:.2f}%")
    st.write(f"**Malin ROI per man:** {roi:.4f}")
    st.write(f"**Malin män per dag:** {malin_män_per_dag:.2f}")

    st.subheader("📊 Kompisars aktievärde")
    st.write(f"**Totalt värde (5000 aktier × {sista_kurs:.2f} USD):** {aktievärde_total:.2f} USD")
    st.write(f"**Per kompis ({antal_kompisar} st):** {aktievärde_per_kompis:.2f} USD")

    st.subheader("❤️ Summering")
    st.write(f"**Sex med kompisar:** {sex_kompisar:.2f}")
    st.write(f"**Sex med familj:** {sex_familj:.2f}")

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

    spara_data(df)

if __name__ == "__main__":
    main()
