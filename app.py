import streamlit as st
import pandas as pd
import numpy as np
import toml
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import datetime

st.set_page_config(page_title="Malin Data", layout="wide")

ALL_COLUMNS = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar", "Älskar", "Sover med", "Vila", "Älsk tid",
    "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP", "Tid singel", "Tid dubbel", "Tid trippel",
    "DeepT", "Sekunder", "Vila mun", "Varv", "Tid mun",
    "Svarta", "Intäkter", "Malin lön", "Kompisar lön",
    "Tid kille dt", "Tid kille", "Summa tid", "Filmer", "Hårdhet", "Snitt film",
    "Summa singel", "Summa dubbel", "Summa trippel", "Suger"
]

def las_in_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["GOOGLE_CREDENTIALS"], scope
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.get_worksheet(0)
    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    df = df.dropna(how="all")  # Ta bort tomma rader
    return df, worksheet

def spara_df(df, worksheet):
    worksheet.clear()
    set_with_dataframe(worksheet, df)

def ensure_columns_exist(df, worksheet):
    existing_cols = df.columns.tolist()
    missing_cols = [col for col in ALL_COLUMNS if col not in existing_cols]
    for col in missing_cols:
        df[col] = np.nan
    df = df[ALL_COLUMNS]
    spara_df(df, worksheet)
    return df

def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    return {
        "Jobb": int(maxrad["Jobb"].values[0]),
        "Grannar": int(maxrad["Grannar"].values[0]),
        "Tjej PojkV": int(maxrad["Tjej PojkV"].values[0]),
        "Nils fam": int(maxrad["Nils fam"].values[0]),
    }

def validera_maxvarden(rad, maxvarden):
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if pd.notna(rad.get(fält)) and int(rad[fält]) > int(maxvarden.get(fält, 0)):
            return False, f"{fält} överskrider maxvärdet ({rad[fält]} > {maxvarden.get(fält, 0)})"
    return True, ""

def formulär_maxvärden(df, worksheet):
    st.subheader("1️⃣ Ange maxvärden (Dag = 0)")
    with st.form("maxvärden_form"):
        jobb = st.number_input("Max Jobb", min_value=0, value=int(df[df["Dag"] == 0]["Jobb"].iloc[0]) if (df["Dag"] == 0).any() else 0)
        grannar = st.number_input("Max Grannar", min_value=0, value=int(df[df["Dag"] == 0]["Grannar"].iloc[0]) if (df["Dag"] == 0).any() else 0)
        tjej = st.number_input("Max Tjej PojkV", min_value=0, value=int(df[df["Dag"] == 0]["Tjej PojkV"].iloc[0]) if (df["Dag"] == 0).any() else 0)
        nils = st.number_input("Max Nils fam", min_value=0, value=int(df[df["Dag"] == 0]["Nils fam"].iloc[0]) if (df["Dag"] == 0).any() else 0)
        submitted = st.form_submit_button("💾 Spara maxvärden")
        if submitted:
            ny_rad = {
                "Dag": 0,
                "Jobb": jobb,
                "Grannar": grannar,
                "Tjej PojkV": tjej,
                "Nils fam": nils
            }
            df = df[df["Dag"] != 0]  # Ta bort tidigare maxrad
            df = pd.concat([pd.DataFrame([ny_rad]), df], ignore_index=True)
            df = df[ALL_COLUMNS]
            spara_df(df, worksheet)
            st.success("Maxvärden sparade!")
            st.experimental_rerun()

def ny_rad_manuellt(df, worksheet, maxvarden):
    st.subheader("2️⃣ Lägg till ny rad manuellt")
    with st.form("manuell_inmatning"):
        dag = st.number_input("Dag", min_value=1, step=1)
        rad = {"Dag": dag}
        for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar", "Älskar", "Sover med", "Vila", "Älsk tid",
                     "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP", "Tid singel", "Tid dubbel", "Tid trippel",
                     "DeepT", "Sekunder", "Vila mun", "Varv", "Svarta"]:
            rad[fält] = st.number_input(fält, value=0, step=1, key=f"{fält}_manuell")
        sparaknapp = st.form_submit_button("📥 Spara rad")
        if sparaknapp:
            ok, felmeddelande = validera_maxvarden(rad, maxvarden)
            if not ok:
                st.error(felmeddelande)
            else:
                df = pd.concat([df, pd.DataFrame([rad])], ignore_index=True)
                df = update_calculations(df)
                spara_df(df, worksheet)
                st.success("Rad sparad!")
                kontrollera_varningar(rad)
                st.experimental_rerun()

def validera_maxvarden(rad, maxvarden):
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if rad[fält] > maxvarden.get(fält, 0):
            return False, f"{fält} får inte överstiga maxvärdet ({maxvarden.get(fält, 0)})."
    return True, ""

def kontrollera_varningar(rad):
    timmar = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if timmar > 17:
        st.warning("⚠️ Summa tid överstiger 17 timmar")
    if tid_kille < 9 or tid_kille > 15:
        st.warning("⚠️ Tid kille är utanför normalintervall (9–15 minuter)")

def update_calculations(df):
    df.fillna(0, inplace=True)

    # Hämta maxrad (Dag = 0)
    if (df["Dag"] == 0).any():
        maxrad = df[df["Dag"] == 0].iloc[0]
        vänner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum()
    else:
        vänner = 0

    df["Män"] = df["Nya killar"] + vänner
    df["Snitt"] = df["DeepT"] / df["Män"].replace(0, np.nan)
    df["Tid mun"] = ((df["Snitt"] * df["Sekunder"]).fillna(0) + df["Vila mun"]) * df["Varv"]

    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * (df["Män"] + df["Fitta"] + df["Röv"])
    df["Summa dubbel"] = (df["Tid dubbel"] + df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = (df["Tid trippel"] + df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Suger"] = ((df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) * 0.6) / df["Män"].replace(0, np.nan)
    df["Tid kille dt"] = (df["Snitt"] * df["Sekunder"] * df["Varv"]).replace(0, np.nan)
    df["Tid kille"] = (
        df["Tid singel"] +
        df["Tid dubbel"] * 2 +
        df["Tid trippel"] * 3 +
        df["Suger"] +
        df["Tid kille dt"] +
        df["Tid mun"]
    ) / 60  # minuter

    df["Filmer"] = (
        df["Män"] + df["Fitta"] + df["Röv"] +
        df["DM"] * 2 + df["DF"] * 2 +
        df["DA"] * 3 + df["TPP"] * 4 +
        df["TAP"] * 6 + df["TP"] * 5
    ) * df[["Nya killar", "DM", "DF", "DA", "TPP", "TAP", "TP"]].apply(
        lambda row: (row > 0).sum(), axis=1).clip(lower=1)

    df["Intäkter"] = df["Filmer"] * 39.99
    df["Malin lön"] = np.minimum(df["Intäkter"] * 0.01, 700)

    df["Summa tid"] = (
        df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] +
        df["Tid mun"] + df["Älskar"] * 1800 + df["Sover med"] * 1800
    ) / 3600  # timmar

    return df

def slumpa_värden(variant, maxrad):
    import random

    def slumpa_inom(minval, maxval):
        return random.randint(minval, maxval) if maxval > 0 else 0

    rad = {"Dag": 1}
    fält = ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]
    for f in fält:
        rad[f] = slumpa_inom(0, maxrad.get(f, 0))

    if variant == "liten":
        rad.update({
            "Nya killar": 1,
            "Fitta": 0,
            "Röv": 0,
            "DM": 0,
            "DF": 0,
            "DA": 0,
            "TPP": 0,
            "TAP": 0,
            "TP": 0,
            "Tid singel": 300,
            "Tid dubbel": 0,
            "Tid trippel": 0,
            "Vila": 300,
            "Älskar": 1,
            "Sover med": 0,
            "DeepT": 30,
            "Sekunder": 15,
            "Vila mun": 10,
            "Varv": 1,
            "Svarta": 0,
        })
    elif variant == "stor":
        rad.update({
            "Nya killar": 3,
            "Fitta": 2,
            "Röv": 2,
            "DM": 2,
            "DF": 1,
            "DA": 1,
            "TPP": 1,
            "TAP": 1,
            "TP": 1,
            "Tid singel": 600,
            "Tid dubbel": 400,
            "Tid trippel": 300,
            "Vila": 600,
            "Älskar": 3,
            "Sover med": 2,
            "DeepT": 90,
            "Sekunder": 25,
            "Vila mun": 30,
            "Varv": 2,
            "Svarta": 0,
        })
    return rad


def skapa_vilorad(typ, maxrad):
    rad = {"Dag": 1}
    for f in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if typ == "jobb":
            rad[f] = int(maxrad.get(f, 0) * 0.3)
        elif typ == "hemma":
            rad[f] = 0
        elif typ == "helt":
            rad[f] = 0

    rad.update({
        "Nya killar": 0,
        "Fitta": 0,
        "Röv": 0,
        "DM": 0,
        "DF": 0,
        "DA": 0,
        "TPP": 0,
        "TAP": 0,
        "TP": 0,
        "Tid singel": 0,
        "Tid dubbel": 0,
        "Tid trippel": 0,
        "Vila": 0,
        "Älskar": 0,
        "Sover med": 0,
        "DeepT": 0,
        "Sekunder": 0,
        "Vila mun": 0,
        "Varv": 0,
        "Svarta": 0,
    })
    return rad


def kopiera_storsta_rad(df):
    if df.empty:
        return None
    df_filtered = df[df["Dag"] != 0]
    if df_filtered.empty:
        return None
    rad = df_filtered.loc[df_filtered["Män"].idxmax()]
    return rad.to_dict()


def visa_redigeringsformulär(rad, maxrad):
    st.markdown("### Redigera och spara")
    redigerad = {}
    for key in ALL_COLUMNS:
        if key == "Dag":
            redigerad[key] = st.number_input("Dag", value=int(rad.get(key, 1)), step=1)
        elif key in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            redigerad[key] = st.number_input(key, value=int(rad.get(key, 0)), step=1, max_value=int(maxrad.get(key, 0)))
        else:
            redigerad[key] = st.number_input(key, value=float(rad.get(key, 0)), step=1.0)

    if st.button("💾 Spara redigerad rad"):
        df = las_in_data()
        df = df.append(redigerad, ignore_index=True)
        df = update_calculations(df)
        spara_data(df)
        kontrollera_varningar(redigerad)
        st.success("✅ Raden sparad!")

def statistikvy(df, maxrad):
    df = df[df["Dag"] != 0]
    if df.empty:
        st.warning("Ingen data att visa ännu.")
        return

    totalt_män = df["Män"].sum()
    tot_tid = df["Summa tid"].sum()
    filmer = df["Filmer"].sum()
    älskar = df["Älskar"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    vänner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()
    kompisars_lön = intäkter / vänner if vänner > 0 else 0
    roi_per_man = malin_lön / (älskar + df["Sover med"].sum() + df["Nya killar"].sum() + vänner) if (älskar + df["Sover med"].sum() + df["Nya killar"].sum() + vänner) > 0 else 0

    sista_kurs = 0
    try:
        sista_kurs = df[df["Ticker"] != ""]['Aktuell kurs'].dropna().iloc[-1]
    except:
        pass
    aktievärde_total = sista_kurs * 5000 if sista_kurs else 0
    aktievärde_per_person = aktievärde_total / vänner if vänner > 0 else 0

    st.subheader("📊 Statistik")
    st.write(f"**Totalt antal män:** {int(totalt_män)}")
    st.write(f"**Totalt antal filmer:** {int(filmer)}")
    st.write(f"**Totalt antal älskat:** {int(älskar)}")
    st.write(f"**Totala intäkter:** {int(intäkter)} USD")
    st.write(f"**Malins totala lön:** {int(malin_lön)} USD")
    st.write(f"**Malin ROI per man:** {roi_per_man:.2f}")
    st.write(f"**Kompisars lön (justerat):** {kompisars_lön:.2f} USD")
    st.write(f"**Kompisars aktievärde:** {aktievärde_total:.2f} USD")
    st.write(f"**Aktievärde per person:** {aktievärde_per_person:.2f} USD")
    st.write(f"**Total tid:** {tot_tid:.1f} timmar")


def main():
    st.title("🎬 Malins DataApp")
    df = las_in_data()
    maxrad = hamta_maxvarden(df)
    ensure_columns_exist(df)

    st.sidebar.header("Navigation")
    vy = st.sidebar.radio("Välj vy", ["📥 Lägg till ny rad", "📈 Statistik", "📄 Data"])

    if vy == "📥 Lägg till ny rad":
        if maxrad.isnull().values.any():
            st.warning("Fyll i maxvärden först")
            visa_maxvärdesformulär(maxrad)
        else:
            visa_maxvärdesformulär(maxrad)
            if st.button("➕ Ny rad manuellt"):
                rad = skapa_tom_rad(maxrad)
                visa_redigeringsformulär(rad, maxrad)
            if st.button("🎲 Slumpa film liten"):
                rad = slumpa_värden("liten", maxrad)
                visa_redigeringsformulär(rad, maxrad)
            if st.button("🎬 Slumpa film stor"):
                rad = slumpa_värden("stor", maxrad)
                visa_redigeringsformulär(rad, maxrad)
            if st.button("😴 Vilodag hemma"):
                rad = skapa_vilorad("hemma", maxrad)
                visa_redigeringsformulär(rad, maxrad)
            if st.button("💼 Vilodag jobb"):
                rad = skapa_vilorad("jobb", maxrad)
                visa_redigeringsformulär(rad, maxrad)
            if st.button("🚫 Vilodag helt"):
                rad = skapa_vilorad("helt", maxrad)
                visa_redigeringsformulär(rad, maxrad)
            if st.button("📋 Kopiera största raden"):
                rad = kopiera_storsta_rad(df)
                if rad:
                    visa_redigeringsformulär(rad, maxrad)

    elif vy == "📈 Statistik":
        statistikvy(df, maxrad)

    elif vy == "📄 Data":
        st.subheader("🔍 Fullständig datatabell")
        st.dataframe(df)

if __name__ == "__main__":
    main()

def ensure_columns_exist(df):
    expected_cols = ALL_COLUMNS
    sheet = client.open_by_url(st.secrets["SHEET_URL"]).worksheet("Blad1")
    existing_cols = sheet.row_values(1)
    missing_cols = [col for col in expected_cols if col not in existing_cols]
    if missing_cols:
        sheet.insert_rows([existing_cols + missing_cols], index=1)

def kontrollera_varningar(rad):
    if rad["Summa tid"] > 17:
        st.warning("⏰ Varning: Summa tid överstiger 17 timmar!")
    tid_kille = rad.get("Tid kille", 0)
    if isinstance(tid_kille, (int, float)) and (tid_kille < 9 or tid_kille > 15):
        st.warning("🕒 Tid kille är under 9 min eller över 15 min – justera vid behov.")

def skapa_tom_rad(maxrad):
    rad = {col: 0 for col in MANUAL_COLUMNS}
    rad["Dag"] = hamta_nasta_dag()
    rad["Ticker"] = ""
    return rad

def skapa_vilorad(typ, maxrad):
    rad = skapa_tom_rad(maxrad)
    if typ == "hemma":
        rad.update({"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0})
    elif typ == "jobb":
        for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            maxv = maxrad.get(fält, 0)
            rad[fält] = int(round(maxv * 0.3)) if pd.notna(maxv) else 0
    elif typ == "helt":
        rad = {col: 0 for col in MANUAL_COLUMNS}
        rad["Dag"] = hamta_nasta_dag()
    return rad

def kopiera_storsta_rad(df):
    if df.empty:
        st.warning("Ingen data att kopiera från.")
        return None
    df = df[df["Dag"] != 0]
    if "Män" not in df.columns:
        st.warning("Kolumnen 'Män' saknas.")
        return None
    största = df.loc[df["Män"].idxmax()]
    rad = största[MANUAL_COLUMNS].to_dict()
    rad["Dag"] = hamta_nasta_dag()
    return rad

def hamta_nasta_dag():
    sheet = client.open_by_url(st.secrets["SHEET_URL"]).worksheet("Blad1")
    dagar = sheet.col_values(1)[1:]  # Skippa rubriken
    dagar_int = [int(d) for d in dagar if d.isdigit()]
    return max(dagar_int + [0]) + 1 if dagar_int else 1

def slumpa_värden(stor=False):
    maxrad = hamta_maxvarden()
    rad = skapa_tom_rad(maxrad)

    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        maxv = maxrad.get(fält, 0)
        rad[fält] = random.randint(0, maxv if stor else max(1, maxv // 3))

    rad["Älskar"] = 8
    rad["Sover med"] = 1
    rad["Vila"] = 7
    rad["Älsk tid"] = 30
    rad["DeepT"] = random.randint(1, 10)
    rad["Varv"] = random.randint(1, 5)
    rad["Sekunder"] = random.randint(100, 500)
    rad["Vila mun"] = random.randint(0, 5)
    rad["DM"] = random.randint(0, 2)
    rad["DF"] = random.randint(0, 2)
    rad["DA"] = random.randint(0, 2)
    rad["TPP"] = random.randint(0, 2)
    rad["TAP"] = random.randint(0, 2)
    rad["TP"] = random.randint(0, 2)
    rad["Fitta"] = random.randint(0, 2)
    rad["Röv"] = random.randint(0, 2)
    rad["Nya killar"] = random.randint(0, 3)
    rad["Svarta"] = random.randint(0, 1)
    rad["Kompisar grabbar"] = random.randint(1, 5)

    return rad

def visa_redigeringsformulär(rad):
    with st.form("Redigera rad", clear_on_submit=False):
        ny_rad = {}
        for fält in MANUAL_COLUMNS:
            if isinstance(rad.get(fält), int):
                ny_rad[fält] = st.number_input(fält, value=int(rad.get(fält, 0)), step=1)
            elif isinstance(rad.get(fält), float):
                ny_rad[fält] = st.number_input(fält, value=float(rad.get(fält, 0)))
            else:
                ny_rad[fält] = st.text_input(fält, value=rad.get(fält, ""))
        submitted = st.form_submit_button("Spara redigerad rad")
        if submitted:
            spara_rad(ny_rad)
            st.success("✅ Raden sparades.")
            kontrollera_varningar(update_calculations(pd.DataFrame([ny_rad])).iloc[0])
            st.stop()

def spara_rad(rad):
    df = pd.DataFrame([rad])
    df = update_calculations(df)
    ensure_columns_exist(df)
    sheet = client.open_by_url(st.secrets["SHEET_URL"]).worksheet("Blad1")
    befintliga_rader = sheet.get_all_values()
    befintliga_data = pd.DataFrame(befintliga_rader[1:], columns=befintliga_rader[0]) if befintliga_rader else pd.DataFrame()
    df = df[[col for col in sheet.row_values(1)]]
    sheet.append_row(df.iloc[0].astype(str).tolist(), value_input_option="USER_ENTERED")
