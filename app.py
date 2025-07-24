import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
from konstanter import COLUMNS, säkerställ_kolumner, bestäm_datum
from berakningar import process_lägg_till_rader, konvertera_typer

# Autentisering mot Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["SHEET_URL"]

# Ladda Google Sheet
@st.cache_resource
def load_sheet():
    return gc.open_by_url(SHEET_URL)

# Läs data
def read_data(sheet):
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df = säkerställ_kolumner(df)
        return konvertera_typer(df)
    except Exception as e:
        st.error(f"Fel vid läsning från Google Sheet: {e}")
        return pd.DataFrame(columns=COLUMNS)

# Spara data till Google Sheet
def spara_data(sh, df):
    from gspread.utils import rowcol_to_a1

    df = df[COLUMNS]

    def städa_värde(x):
        if pd.isna(x) or x in [None, np.nan, float("inf"), float("-inf")]:
            return ""
        if isinstance(x, (float, int)):
            return round(float(x), 6)
        s = str(x).replace("\n", " ").strip()
        return s[:5000]

    df = df.applymap(städa_värde)
    sheet = sh.worksheet("Data")

    try:
        sheet.clear()
        sheet.update("A1", [df.columns.tolist()])
    except Exception as e:
        st.error(f"Fel vid uppdatering av header: {e}")
        return

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
            st.error(f"❌ Fel vid skrivning till: {cell_range}\nChunk som skulle skrivas:\n{chunk}\nAntal kolumner: {len(chunk[0])}\n\n{e}")
            raise e

# Ladda och spara inställningar från bladet Inställningar
def läs_inställningar(sh):
    try:
        sheet = sh.worksheet("Inställningar")
        data = sheet.get_all_values()
        inst = {rad[0]: rad[1] for rad in data if len(rad) >= 2}
        return inst
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar: {e}")
        return {}

def spara_inställningar(sh, inst):
    try:
        sheet = sh.worksheet("Inställningar")
        sheet.clear()
        sheet.update("A1", [[k, v] for k, v in inst.items()])
    except Exception as e:
        st.error(f"Kunde inte spara inställningar: {e}")

# Formulär för att lägga till scen
def scenformulär(df, inst, sh):
    st.subheader("Lägg till scenrad")

    with st.form("scenformulär", clear_on_submit=False):
        f = {}
        f["Typ"] = st.selectbox("Typ av rad", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        f["Scenens längd (h)"] = st.number_input("Scenens längd (h)", 0.0, 24.0, 0.0, step=0.5)
        f["Antal vilodagar"] = st.number_input("Antal vilodagar (endast för 'Vila inspelningsplats')", 0, 7, 0)
        f["Övriga män"] = st.number_input("Övriga män", 0, 50, 0)
        f["Enkel vaginal"] = st.number_input("Enkel vaginal", 0, 50, 0)
        f["Enkel anal"] = st.number_input("Enkel anal", 0, 50, 0)
        f["DP"] = st.number_input("DP", 0, 50, 0)
        f["DPP"] = st.number_input("DPP", 0, 50, 0)
        f["DAP"] = st.number_input("DAP", 0, 50, 0)
        f["TPP"] = st.number_input("TPP", 0, 50, 0)
        f["TPA"] = st.number_input("TPA", 0, 50, 0)
        f["TAP"] = st.number_input("TAP", 0, 50, 0)
        f["Kompisar"] = st.number_input("Kompisar", 0, 50, 0)
        f["Pappans vänner"] = st.number_input("Pappans vänner", 0, 50, 0)
        f["Nils vänner"] = st.number_input("Nils vänner", 0, 50, 0)
        f["Nils familj"] = st.number_input("Nils familj", 0, 50, 0)
        f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", 0, 3600, 0)
        f["Älskar med"] = st.number_input("Älskar med", 0, 10, 0)
        f["Sover med"] = st.number_input("Sover med", 0, 10, 0)
        f["Nils sex"] = st.number_input("Nils sex", 0, 10, 0)
        f["Prenumeranter"] = st.number_input("Prenumeranter", 0, 1_000_000, 0)
        f["Bekräfta"] = st.checkbox("Bekräfta att du vill lägga till raden")

        submitted = st.form_submit_button("Lägg till")

    if submitted and f["Bekräfta"]:
        f["Datum"] = bestäm_datum(df, inst)
        f["Minuter per kille"] = 0  # Placeholder, räknas ut i beräkningar

        df = process_lägg_till_rader(df, inst, f)
        spara_data(sh, df)
        st.success("Rad tillagd.")
    elif submitted:
        st.warning("Du måste bekräfta att du vill lägga till raden.")

# Huvudfunktion
def main():
    st.title("Malin-produktionsapp")

    # Autentisering och initiering
    credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    gc = gspread.authorize(credentials)
    SHEET_URL = st.secrets["SHEET_URL"]
    sh = gc.open_by_url(SHEET_URL)

    # Läs in data
    df = läs_data(sh)
    inst = läs_inställningar(sh)
    df = säkerställ_kolumner(df)
    df = konvertera_typer(df)
    df = uppdatera_beräkningar(df)

    # Visa formulär och data
    scenformulär(df, inst, sh)

    with st.expander("Visa data"):
        st.dataframe(df)

if __name__ == "__main__":
    main()
