import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import toml

# Ladda in secrets
secrets = toml.load(".streamlit/secrets.toml")
SHEET_URL = secrets["SHEET_URL"]
credentials = secrets["GOOGLE_CREDENTIALS"]

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
client = gspread.authorize(creds)

spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.worksheet("Blad1")

ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Tid trippel",
    "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
    "DeepT", "Sekunder", "Vila mun", "Varv",
    "Känner", "Män", "Summa singel", "Summa dubbel", "Summa trippel",
    "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille",
    "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar",
    "Aktiekurs", "Kompisar aktievärde"
]

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df

def load_data():
    df = get_as_dataframe(worksheet, evaluate_formulas=True).fillna(0)
    df = df[ALL_COLUMNS[:len(df.columns)]] if not df.empty else pd.DataFrame(columns=ALL_COLUMNS)
    df = df.fillna(0)
    return df

def save_data(df):
    worksheet.clear()
    set_with_dataframe(worksheet, df)

def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 1, "Grannar": 1, "Tjej PojkV": 1, "Nils fam": 1}
    maxrad = maxrad.iloc[0]
    return {
        "Jobb": maxrad["Jobb"],
        "Grannar": maxrad["Grannar"],
        "Tjej PojkV": maxrad["Tjej PojkV"],
        "Nils fam": maxrad["Nils fam"]
    }

def validera_maxvarden(rad, maxvarden):
    for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if rad[kolumn] > maxvarden[kolumn]:
            st.warning(f"{kolumn} överskrider maxvärdet ({rad[kolumn]} > {maxvarden[kolumn]}). Uppdatera först maxvärdet på Dag = 0.")
            return False
    return True

def visa_redigeringsformulär(rad, dag):
    with st.form("Redigera rad", clear_on_submit=False):
        ny_rad = {}
        st.write(f"**Redigera rad för Dag {dag}**")
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                ny_rad[kolumn] = dag
            elif kolumn == "Veckodag":
                ny_rad[kolumn] = rad.get(kolumn, "")
            elif isinstance(rad[kolumn], (int, float)):
                ny_rad[kolumn] = st.number_input(kolumn, value=float(rad[kolumn]), step=1.0)
            else:
                ny_rad[kolumn] = st.text_input(kolumn, value=str(rad[kolumn]))
        submitted = st.form_submit_button("Spara redigerad rad")
        if submitted:
            return ny_rad
    return None

def spara_rad(df, rad):
    dag = int(rad["Dag"])
    if dag in df["Dag"].values:
        df.loc[df["Dag"] == dag] = pd.DataFrame([rad])
    else:
        df = pd.concat([df, pd.DataFrame([rad])], ignore_index=True)
    df.sort_values("Dag", inplace=True)
    set_with_dataframe(worksheet, df[ALL_COLUMNS], include_index=False, include_column_header=True)
    return df

def skapa_tom_rad(dag):
    return {kol: 0 for kol in ALL_COLUMNS if kol not in ["Dag", "Veckodag"]} | {"Dag": dag, "Veckodag": ""}

def slumpa_filmrad(variant, maxvarden):
    import random

    if variant == "liten":
        ny_killar = random.randint(10, 50)
        fitta = random.randint(3, 12)
        rov = random.randint(3, 12)
        dm = random.randint(10, 25)
        df = random.randint(10, 25)
        da = 0
        tpp = tap = tp = 0
    else:
        ny_killar = random.randint(60, 200)
        fitta = random.randint(10, 30)
        rov = random.randint(10, 30)
        dm = random.randint(50, 100)
        df = random.randint(50, 100)
        da = random.randint(50, 100)
        tpp = random.randint(30, 80)
        tap = random.randint(30, 80)
        tp = random.randint(30, 80)

    rad = {
        "Nya killar": ny_killar,
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
        "Jobb": random.randint(3, maxvarden["Jobb"]),
        "Grannar": random.randint(3, maxvarden["Grannar"]),
        "Tjej PojkV": random.randint(3, maxvarden["Tjej PojkV"]),
        "Nils fam": random.randint(3, maxvarden["Nils fam"]),
        "Svarta": random.choice([0, ny_killar]),
        "DeepT": 0,
        "Sekunder": 0,
        "Vila mun": 0,
        "Varv": 0,
    }
    return rad

def skapa_vilarad(typ, maxvarden):
    rad = skapa_tom_rad(dag=0)
    if typ == "jobb":
        rad["Älskar"] = 12
        rad["Sover med"] = 1
        rad["Jobb"] = int(0.3 * maxvarden["Jobb"])
        rad["Grannar"] = int(0.3 * maxvarden["Grannar"])
        rad["Tjej PojkV"] = int(0.3 * maxvarden["Tjej PojkV"])
        rad["Nils fam"] = int(0.3 * maxvarden["Nils fam"])
    elif typ == "hemma":
        rad["Älskar"] = 6
        rad["Jobb"] = 5
        rad["Grannar"] = 3
        rad["Tjej PojkV"] = 3
        rad["Nils fam"] = 5
    elif typ == "helt":
        pass  # Alla värden är redan 0
    return rad

def kopiera_storsta_rad(df):
    if "Nya killar" not in df.columns or df.empty:
        return skapa_tom_rad(dag=1)
    idx = df["Nya killar"].idxmax()
    rad = df.loc[idx].to_dict()
    rad["Dag"] = df["Dag"].max() + 1
    return rad

def visa_redigeringsformulär(rad, dag):
    with st.form("redigeringsformulär"):
        st.write("Redigera värden innan du sparar:")
        ny_rad = {}
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                ny_rad[kolumn] = dag
            elif kolumn == "Veckodag":
                ny_rad[kolumn] = ""
            else:
                try:
                    val = float(rad.get(kolumn, 0))
                    ny_rad[kolumn] = st.number_input(kolumn, value=val, step=1.0)
                except:
                    ny_rad[kolumn] = st.number_input(kolumn, value=0.0, step=1.0)
        submitted = st.form_submit_button("Spara redigerad rad")
        if submitted:
            return ny_rad
    return None

def spara_rad(df, ny_rad):
    ny_rad["Veckodag"] = hamta_veckodag(ny_rad["Dag"])
    df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    df = update_calculations(df)
    spara_data(df)
    visa_varningar(ny_rad)
    return df

def visa_varningar(rad):
    summa_tid = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if summa_tid > 17:
        st.warning("⚠️ Summa tid överstiger 17 timmar – överväg att justera raden.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning("⚠️ Tid per kille är utanför normalt intervall (9–15 min) – kontrollera värden.")

def knappfunktioner(df):
    maxvarden = hamta_maxvarden(df)
    dag = df["Dag"].max() + 1 if not df.empty else 1

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Slumpa Film liten"):
            rad = slumpa_filmrad("liten", maxvarden)
            rad["Dag"] = dag
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_rad(df, ny_rad)
    with col2:
        if st.button("Slumpa Film stor"):
            rad = slumpa_filmrad("stor", maxvarden)
            rad["Dag"] = dag
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_rad(df, ny_rad)
    with col3:
        if st.button("Kopiera största raden"):
            rad = kopiera_storsta_rad(df)
            rad["Dag"] = dag
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_rad(df, ny_rad)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Vilodag jobb"):
            rad = skapa_vilarad("jobb", maxvarden)
            rad["Dag"] = dag
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_rad(df, ny_rad)
    with col2:
        if st.button("Vilodag hemma"):
            rad = skapa_vilarad("hemma", maxvarden)
            rad["Dag"] = dag
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_rad(df, ny_rad)
    with col3:
        if st.button("Vilodag helt"):
            rad = skapa_vilarad("helt", maxvarden)
            rad["Dag"] = dag
            ny_rad = visa_redigeringsformulär(rad, dag)
            if ny_rad:
                df = spara_rad(df, ny_rad)

    return df

def visa_statistik(df):
    st.subheader("📊 Statistik")
    if df.empty:
        st.info("Ingen data tillgänglig.")
        return

    maxrad = df[df["Dag"] == 0]
    max_job = maxrad["Jobb"].values[0] if "Jobb" in maxrad.columns else 1
    max_grannar = maxrad["Grannar"].values[0] if "Grannar" in maxrad.columns else 1
    max_tjej = maxrad["Tjej PojkV"].values[0] if "Tjej PojkV" in maxrad.columns else 1
    max_nils = maxrad["Nils fam"].values[0] if "Nils fam" in maxrad.columns else 1
    max_kompisar = max_job + max_grannar + max_tjej + max_nils

    df_med_killar = df[df["Nya killar"] > 0]
    filmer = len(df_med_killar)
    totalt_man = df["Nya killar"].sum() + max_kompisar
    snitt_gb = round(totalt_man / filmer, 2) if filmer > 0 else 0

    antal_rader = len(df[df["Känner"] > 0])
    antal_rader_med_timmar = df[(df["Känner"] > 0) & (df["Summa tid"] > 0)]
    antal_rader_endast_kompisar = antal_rader - len(antal_rader_med_timmar)

    df["justerad_tid"] = df["Summa tid"]
    df.loc[(df["Summa tid"] == 0) & (df["Känner"] > 0), "justerad_tid"] = 3

    data = {
        "Filmer (med killar)": filmer,
        "Totalt antal män": totalt_man,
        "Snitt GB": snitt_gb,
        "Älskat": int(df["Älskar"].sum()),
        "Sovit med": int(df["Sover med"].sum()),
        "Jobb": int(df["Jobb"].sum()),
        "Grannar": int(df["Grannar"].sum()),
        "Tjej PojkV": int(df["Tjej PojkV"].sum()),
        "Nils familj": int(df["Nils fam"].sum()),
        "Svarta": int(df["Svarta"].sum()),
        "Vita": int(df["Nya killar"].sum() - df["Svarta"].sum()),
        "Sålda filmer": int(df["Filmer"].sum()),
        "Intäkter": round(df["Intäkter"].sum(), 2),
        "Malin lön": round(df["Malin lön"].sum(), 2),
        "Vänners lön": round(df["Kompisar"].sum(), 2),
    }

    st.table(pd.DataFrame.from_dict(data, orient="index", columns=["Värde"]))

    # Extra statistik
    älskat_snitt = round(df["Älskar"].sum() / max_kompisar, 2) if max_kompisar else 0
    sovit_snitt = round(df["Sover med"].sum() / max_nils, 2) if max_nils else 0
    svarta_proc = round(df["Svarta"].sum() / df["Nya killar"].sum() * 100, 2) if df["Nya killar"].sum() else 0
    vita_proc = round((df["Nya killar"].sum() - df["Svarta"].sum()) / df["Nya killar"].sum() * 100, 2) if df["Nya killar"].sum() else 0

    totalt_killar = df["Älskar"].sum() + df["Sover med"].sum() + df["Nya killar"].sum() + df["Känner"].sum()
    malin_roi = round(df["Malin lön"].sum() / totalt_killar, 2) if totalt_killar else 0

    vänner_gb = round(df["Känner"].sum() / max_kompisar, 2) if max_kompisar else 0
    snitt_sovit = round(df["Sover med"].sum() / antal_rader, 2) if antal_rader else 0
    snitt_älskat = round(df["Älskar"].sum() / max_kompisar, 2) if max_kompisar else 0

    kompis_summa = snitt_älskat + vänner_gb
    familj_summa = snitt_älskat + vänner_gb + snitt_sovit

    # Aktievärde
    sista_kurs = df.iloc[-1]["Aktiekurs"] if "Aktiekurs" in df.columns else 40
    aktievarde_total = 5000 * sista_kurs
    justerat_varde_per_kompis = aktievarde_total / max_kompisar if max_kompisar else 0

    st.markdown("### 🔍 Fördjupad statistik")
    extra = {
        "Älskat/kompis": snitt_älskat,
        "Sovit/Nils fam": sovit_snitt,
        "Svarta i %": svarta_proc,
        "Vita i %": vita_proc,
        "Malin ROI per man": malin_roi,
        "Vänner GB": vänner_gb,
        "Sex med kompisar": kompis_summa,
        "Sex med familj": familj_summa,
        "Kompisars aktievärde (totalt)": round(aktievarde_total, 2),
        "Per kompis (2 dec)": round(justerat_varde_per_kompis, 2)
    }
    st.table(pd.DataFrame.from_dict(extra, orient="index", columns=["Värde"]))

def main():
    st.set_page_config(layout="wide")
    st.title("🎬 Malins filmstatistik")

    df = load_data()
    df = ensure_columns_exist(df)
    df = update_calculations(df)

    sidval = st.sidebar.radio("Välj vy", ["Huvudvy", "Statistik", "Redigera maxvärden"])

    if sidval == "Huvudvy":
        visa_huvudvy(df)
        df = knappfunktioner(df)
        df = spara_ny_rad(df)
    elif sidval == "Statistik":
        visa_statistik(df)
    elif sidval == "Redigera maxvärden":
        df = formulär_maxvärden(df)

    save_data(df)

if __name__ == "__main__":
    main()
