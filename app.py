import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from konstanter import COLUMNS, säkerställ_kolumner, bestäm_datum
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets.get("SHEET_URL")

def init_sheet(sh):
    try:
        sheet = sh.worksheet("Data")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Data", rows="1000", cols="40")
        sheet.update("A1", [COLUMNS])
    df = pd.DataFrame(sheet.get_all_records())
    df = säkerställ_kolumner(df)
    return df

def läs_inställningar(sh):
    try:
        sheet = sh.worksheet("Inställningar")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Inställningar", rows="100", cols="3")
        sheet.update("A1:C1", [["Namn", "Värde", "Senast ändrad"]])
        idag = datetime.today().strftime("%Y-%m-%d")
        standard = [
            ["Startdatum", idag],
            ["Kvinnans namn", "Malin"],
            ["Födelsedatum", "1984-03-26"],
            ["Kompisar", "50"],
            ["Pappans vänner", "25"],
            ["Nils vänner", "15"],
            ["Nils familj", "10"]
        ]
        sheet.update("A2:C8", [[k, v, idag] for k, v in standard])
    df = pd.DataFrame(sheet.get_all_records())
    return {row["Namn"]: tolka_värde(row["Värde"]) for _, row in df.iterrows()}

def tolka_värde(v):
    if isinstance(v, str):
        v = v.replace(",", ".")
    try:
        return float(v) if "." in str(v) else int(v)
    except:
        return str(v)

def spara_inställningar(sh, inst):
    sheet = sh.worksheet("Inställningar")
    idag = datetime.today().strftime("%Y-%m-%d")
    rows = [[k, str(v).replace(".", ","), idag] for k, v in inst.items()]
    sheet.update("A2:C" + str(len(rows) + 1), rows)

def spara_data(sh, df):
    import numpy as np
    df = df[COLUMNS]

    def städa(x):
        if pd.isna(x) or x in [None, np.nan, float("inf"), float("-inf")]:
            return ""
        if isinstance(x, (float, int)):
            return round(float(x), 6)
        return str(x).replace("\n", " ")[:5000]

    df = df.applymap(städa)

    sheet = sh.worksheet("Data")
    sheet.clear()
    sheet.update("A1", [COLUMNS])

    värden = df.values.tolist()
    värden = [rad[:len(COLUMNS)] + [""] * (len(COLUMNS) - len(rad)) for rad in värden]

    for i in range(0, len(värden), 1000):
        start_row = i + 2
        chunk = värden[i:i + 1000]
        try:
            sheet.update(f"A{start_row}", chunk)
        except Exception as e:
            st.error(f"❌ Fel vid skrivning till: A{start_row}")
            st.write("Chunk som skulle skrivas:", chunk)
            st.write("Antal kolumner:", len(chunk[0]) if chunk else 0)
            raise e

def rensa_databasen(sh):
    sheet = sh.worksheet("Data")
    sheet.resize(rows=1)
    sheet.update("A1", [COLUMNS])

def konvertera_typer(df):
    for col in COLUMNS:
        if col in df.columns:
            if "Datum" in col:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
            elif col in ["Typ"]:
                df[col] = df[col].astype(str)
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def scenformulär(df, inst, sh):
    with st.form("lägg_till_scen"):
        f = {}
        f["Datum"] = bestäm_datum(df, inst)
        st.markdown(f"**Datum:** {f['Datum']}")

        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", 0, 30, step=1)
        f["Scenens längd (h)"] = st.number_input("Scenens längd (h)", 0.0, 48.0, step=0.5)
        f["Övriga män"] = st.number_input("Övriga män", 0, 500)

        for nyckel in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP"]:
            f[nyckel] = st.number_input(nyckel, 0, 500)

        for nyckel in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[nyckel] = st.number_input(nyckel, 0, int(inst.get(nyckel, 0)))

        f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", 0, 9999)
        f["Älskar med"] = st.number_input("Antal älskar med", 0, 100)
        f["Sover med"] = st.number_input("Antal sover med", 0, 100)

        tid_kille_min, total_tid_h = beräkna_tid_per_kille(f)
        st.markdown(f"**Minuter per kille (inkl. DT):** {round(tid_kille_min, 2)} min")
        st.markdown(f"**Total tid för scenen:** {round(total_tid_h, 2)} h")

        bekräfta = st.checkbox("✅ Bekräfta att du vill lägga till raden")

        if st.form_submit_button("Lägg till") and bekräfta:
            df = process_lägg_till_rader(df, inst, f)
            df = konvertera_typer(df)
            spara_data(sh, df)
            st.success("✅ Raden tillagd")

def inställningspanel(sh, inst):
    st.sidebar.header("Inställningar")
    with st.sidebar.form("inställningar"):
        f = {}
        f["Startdatum"] = st.text_input("Startdatum (YYYY-MM-DD)", inst.get("Startdatum", "2014-03-26"))
        f["Kvinnans namn"] = st.text_input("Kvinnans namn", inst.get("Kvinnans namn", "Malin"))
        f["Födelsedatum"] = st.text_input("Födelsedatum (YYYY-MM-DD)", inst.get("Födelsedatum", "1984-03-26"))
        for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[grupp] = st.number_input(grupp, 0, 1000, int(inst.get(grupp, 0)))

        if st.form_submit_button("Spara inställningar"):
            spara_inställningar(sh, f)
            st.success("✅ Inställningar sparade")

    if st.sidebar.button("Rensa databasen"):
        rensa_databasen(sh)
        st.sidebar.success("✅ Databasen rensad")

def visa_data(df):
    st.subheader("📊 Databasens innehåll")
    st.dataframe(df)
    if not df.empty:
        senaste = df.iloc[-1]
        st.info(f"Senaste rad: {senaste['Datum']} – {senaste['Typ']}")

def main():
    st.set_page_config(page_title="Malin-produktionsapp", layout="wide")
    st.title("🎬 Malin-produktionsapp")

    sh = gc.open_by_url(SHEET_URL)
    inst = läs_inställningar(sh)
    inställningspanel(sh, inst)

    df = init_sheet(sh)
    df = konvertera_typer(df)

    scenformulär(df, inst, sh)
    visa_data(df)

if __name__ == "__main__":
    main()
