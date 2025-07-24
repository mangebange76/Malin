import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille
from konstanter import COLUMNS, säkerställ_kolumner, bestäm_datum

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["SHEET_URL"]

def init_sheet(sh):
    try:
        sheet = sh.worksheet("Data")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Data", rows="1000", cols="40")
        sheet.update("A1", [COLUMNS])
    df = pd.DataFrame(sheet.get_all_records())
    df = df.reindex(columns=COLUMNS, fill_value=0)
    return df

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
    return {row["Namn"]: row["Värde"] for _, row in df.iterrows()}

def spara_data(sh, df):
    df = df[COLUMNS]
    sheet = sh.worksheet("Data")
    sheet.clear()
    sheet.update("A1", [df.columns.tolist()])
    if not df.empty:
        sheet.update("A2", df.values.tolist())

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
    with st.form("scenformulär"):
        f = {}
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", 0, 30)
        f["Scenens längd (h)"] = st.number_input("Scenens längd (h)", 0.0, 48.0, step=0.5)
        f["Övriga män"] = st.number_input("Övriga män", 0, 500)
        for nyckel in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP"]:
            f[nyckel] = st.number_input(nyckel, 0, 500)
        for nyckel in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[nyckel] = st.number_input(nyckel, 0, int(inst.get(nyckel, 0)))
        f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", 0, 9999)
        f["Älskar med"] = st.number_input("Antal älskar med", 0, 100)
        f["Sover med"] = st.number_input("Antal sover med", 0, 100)

        tid_min, total_h = beräkna_tid_per_kille(f)
        st.markdown(f"**Minuter per kille:** {round(tid_min, 2)}")
        st.markdown(f"**Total tid (h):** {round(total_h, 2)}")

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
        submitted = st.form_submit_button("Lägg till")

        if submitted and bekräfta:
            f["Datum"] = bestäm_datum(df, inst)
            df = process_lägg_till_rader(df, inst, f)
            df = konvertera_typer(df)
            spara_data(sh, df)
            st.success("✅ Scen tillagd.")

def visa_data(df):
    st.subheader("📊 Databas")
    st.dataframe(df)

def main():
    st.set_page_config("Malin-produktionsapp")
    st.title("🎬 Malin-produktionsapp")

    sh = gc.open_by_url(SHEET_URL)
    inst = läs_inställningar(sh)
    df = init_sheet(sh)
    df = säkerställ_kolumner(df)
    df = konvertera_typer(df)

    scenformulär(df, inst, sh)
    visa_data(df)

if __name__ == "__main__":
    main()
