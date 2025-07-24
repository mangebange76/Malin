import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Konfiguration
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"

COLUMNS = [
    "Datum", "Typ", "Scenens längd (h)", "Antal vilodagar", "Övriga män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
]

def ensure_columns_exist(df):
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = 0
    df = df[COLUMNS]
    return df

def init_sheet(sh):
    try:
        sheet = sh.worksheet("Data")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Data", rows="1000", cols="40")
        sheet.update("A1", [COLUMNS])
    df = pd.DataFrame(sheet.get_all_records())
    return ensure_columns_exist(df)

def läs_inställningar(sh):
    try:
        sheet = sh.worksheet("Inställningar")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Inställningar", rows="100", cols="3")
        sheet.update("A1:C1", [["Namn", "Värde", "Senast ändrad"]])
        standard = [
            ["Startdatum", "2014-03-26"],
            ["Kvinnans namn", "Malin"],
            ["Födelsedatum", "1984-03-26"],
            ["Kompisar", "50"],
            ["Pappans vänner", "25"],
            ["Nils vänner", "15"],
            ["Nils familj", "10"]
        ]
        idag = datetime.today().strftime("%Y-%m-%d")
        sheet.update("A2:C8", [[namn, värde, idag] for namn, värde in standard])
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
    rows = []
    for k, v in inst.items():
        v_str = str(v).replace(".", ",") if isinstance(v, float) else str(v)
        rows.append([k, v_str, idag])
    sheet.update("A2:C" + str(len(rows) + 1), rows)

def spara_data(sh, df):
    import numpy as np
    df = ensure_columns_exist(df)

    def städa_värde(x):
        if pd.isna(x) or x in [None, np.nan, float("inf"), float("-inf")]:
            return ""
        if isinstance(x, (float, int)):
            return x
        s = str(x).replace("\n", " ").strip()
        return s[:5000]

    df = df.applymap(städa_värde)

    sheet = sh.worksheet("Data")
    sheet.clear()
    sheet.update("A1", [df.columns.tolist()])

    if df.empty:
        return

    värden = df.values.tolist()
    max_rader_per_update = 1000

    for i in range(0, len(värden), max_rader_per_update):
        start_row = i + 2
        cell_range = f"A{start_row}"
        chunk = värden[i:i + max_rader_per_update]
        try:
            sheet.update(cell_range, chunk)
        except Exception as e:
            st.error(f"❌ Fel vid skrivning till: {cell_range}")
            st.write("Chunk som skulle skrivas:", chunk)
            st.write("Antal kolumner:", len(chunk[0]) if chunk else 0)
            raise e

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

def rensa_databasen(sh):
    sheet = sh.worksheet("Data")
    sheet.resize(rows=1)
    sheet.update("A1", [COLUMNS])

def scenformulär(df, inst, sh):
    with st.form("lägg_till_scen"):
        f = {}
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", 0, 30, step=1, key="antal_vilodagar")
        f["Scenens längd (h)"] = st.number_input("Scenens längd (h)", 0.0, 48.0, step=0.5, key="scen_längd")
        f["Övriga män"] = st.number_input("Övriga män", 0, 500, step=1, key="övriga")

        for nyckel in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP"]:
            f[nyckel] = st.number_input(nyckel, 0, 500, step=1, key=nyckel)

        for nyckel in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[nyckel] = st.number_input(nyckel, 0, int(inst.get(nyckel, 0)), step=1, key=nyckel + "_grupp")

        f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", 0, 9999, step=1, key="dt_tid")

        f["Älskar med"] = st.number_input("Antal älskar med", 0, 100, step=1, key="alskar")
        f["Sover med"] = st.number_input("Antal sover med", 0, 100, step=1, key="sover")

        tid_per_kille_min, total_tid_h = beräkna_tid_per_kille(f)
        st.markdown(f"**Minuter per kille (inkl. DT):** {round(tid_per_kille_min, 2)} min")
        st.markdown(f"**Total tid för scenen:** {round(total_tid_h, 2)} h")

        if total_tid_h > 18:
            st.warning("⚠️ Total tid överstiger 18 timmar!")

        submitted = st.form_submit_button("Lägg till")
        if submitted:
            df = process_lägg_till_rader(df, inst, f)
            df = ensure_columns_exist(df)
            df = konvertera_typer(df)
            spara_data(sh, df)
            st.success("✅ Raden tillagd")

            nycklar_att_rensa = list(f.keys()) + [
                "typ", "antal_vilodagar", "scen_längd", "övriga", "dt_tid", "alskar", "sover"
            ]
            for k in nycklar_att_rensa:
                if k in st.session_state:
                    if isinstance(st.session_state[k], (int, float)):
                        st.session_state[k] = 0
                    elif isinstance(st.session_state[k], str):
                        st.session_state[k] = ""

def inställningspanel(sh, inst):
    st.sidebar.header("Inställningar")
    with st.sidebar.form("inställningar"):
        f = {}
        f["Startdatum"] = st.text_input("Startdatum (YYYY-MM-DD)", inst.get("Startdatum", "2014-03-26"))
        f["Kvinnans namn"] = st.text_input("Kvinnans namn", inst.get("Kvinnans namn", "Malin"))
        f["Födelsedatum"] = st.text_input("Födelsedatum (YYYY-MM-DD)", inst.get("Födelsedatum", "1984-03-26"))
        for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[grupp] = st.number_input(grupp, 0, 1000, int(inst.get(grupp, 0)))

        submitted = st.form_submit_button("Spara inställningar")
        if submitted:
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
    df = ensure_columns_exist(df)
    df = konvertera_typer(df)

    scenformulär(df, inst, sh)
    visa_data(df)

if __name__ == "__main__":
    main()
