import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Konfigurera och autentisera
scope = ["https://spreadsheets.google.com/feeds", 
         "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets.get("SHEET_URL", "")

# Konstanter
COLUMNS = [
    "Datum", "Typ", "Antal vilodagar", "Nya män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP",
    "TPP", "TPA", "TAP",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
]

def init_sheet(sh):
    try:
        sheet = sh.worksheet("Data")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Data", rows="2000", cols=str(len(COLUMNS)))
        sheet.update("A1", [COLUMNS])
    df = pd.DataFrame(sh.worksheet("Data").get_all_records())
    df = df.reindex(columns=COLUMNS, fill_value=0)
    return df

def säkerställ_kolumner(df):
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[COLUMNS]

def läs_inställningar(sh):
    try:
        sheet = sh.worksheet("Inställningar")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Inställningar", rows="100", cols="3")
        sheet.update("A1:C1", [["Namn", "Värde", "Senast ändrad"]])
        default = [
            ["Startdatum", datetime.today().strftime("%Y-%m-%d")],
            ["Kvinnans namn", "Malin"],
            ["Födelsedatum", "1984-03-26"],
            ["Kompisar", 50],
            ["Pappans vänner", 25],
            ["Nils vänner", 15],
            ["Nils familj", 10],
        ]
        sheet.update("A2:C8", [[k, v, datetime.today().strftime("%Y-%m-%d")] for k,v in default])
    df = pd.DataFrame(sheet.get_all_records())
    inst = {}
    for _, row in df.iterrows():
        inst[row["Namn"]] = float(row["Värde"]) if isinstance(row["Värde"], (int,float,str)) and str(row["Värde"]).replace('.', '',1).isdigit() else row["Värde"]
    return inst

def spara_inställningar(sh, inst):
    sheet = sh.worksheet("Inställningar")
    idag = datetime.today().strftime("%Y-%m-%d")
    rows = [[k, inst[k], idag] for k in inst]
    sheet.update("A2:C" + str(len(rows)+1), rows)

def spara_data(sh, df):
    df = df[COLUMNS]
    import numpy as np
    def städa(x):
        if pd.isna(x) or x in [None, np.nan, float("inf"), float("-inf")]:
            return ""
        return x
    df = df.applymap(städa)
    sheet = sh.worksheet("Data")
    sheet.clear()
    sheet.update("A1", [COLUMNS])
    if df.empty: return
    vals = df.values.tolist()
    max_chunk = 1000
    for i in range(0, len(vals), max_chunk):
        r = i + 2
        chunk = vals[i:i+max_chunk]
        try:
            sheet.update(f"A{r}", chunk)
        except Exception as e:
            st.error(f"❌ Fel vid skrivning till A{r}")
            st.write(chunk)
            raise

def inställningspanel(sh, inst):
    st.sidebar.header("Inställningar")
    with st.sidebar.form("inställningar"):
        f = {}
        f["Startdatum"] = st.text_input("Startdatum (YYYY‑MM‑DD)", inst.get("Startdatum", ""))
        f["Kvinnans namn"] = st.text_input("Kvinnans namn", inst.get("Kvinnans namn", ""))
        f["Födelsedatum"] = st.text_input("Födelsedatum (YYYY‑MM‑DD)", inst.get("Födelsedatum", ""))
        for grp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[grp] = st.number_input(grp, 0, 10000, int(inst.get(grp, 0)))
        if st.form_submit_button("Spara inställningar"):
            spara_inställningar(sh, f)
            st.success("Inställningar sparade")
    if st.sidebar.button("Rensa databas"):
        sh.worksheet("Data").resize(rows=1)
        sh.worksheet("Data").update("A1", [COLUMNS])
        st.sidebar.success("Databasen rensad")

def scenformulär(df, inst, sh):
    st.subheader("Lägg till scen / vila")
    with st.form("scenform", clear_on_submit=False):
        f = {}
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", 0, 30, step=1)
        f["Nya män"] = st.number_input("Nya män", 0, 500, step=1)
        for key in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP"]:
            f[key] = st.number_input(key, 0, 500, step=1)
        for grp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            f[grp] = st.number_input(grp, 0, int(inst.get(grp, 0)), step=1)
        f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", 0, 9999, step=1)
        f["Älskar med"] = st.number_input("Älskar med", 0, 100, step=1)
        f["Sover med"] = st.number_input("Sover med", 0, 100, step=1)
        st.write("✔ Jag bekräftar att uppgifterna är korrekta")
        confirmed = st.checkbox("Bekräfta inför sparande")
        tid_min, total_h = beräkna_tid_per_kille(f)
        st.markdown(f"**Total tid:** {total_h:.2f} h  •  **Minuter per kille:** {tid_min:.2f} min")
        if total_h > 18:
            st.warning("⚠️ Total tid överstiger 18 timmar! Redigera innan sparande.")
        ok = st.form_submit_button("Lägg till i databas")
        if ok:
            if not confirmed:
                st.error("Du måste bekräfta data innan sparning.")
            elif total_h > 18:
                st.error("Total tid över 18 timmar. Justera värden först.")
            else:
                df = process_lägg_till_rader(df, inst, f)
                df = säkerställ_kolumner(df)
                spara_data(sh, df)
                st.success("✅ Data sparad")
    return df

def visa_data(df):
    st.subheader("Databas")
    st.dataframe(df)
    if not df.empty:
        rng = df.iloc[-1]
        st.info(f"Senaste: {rng['Datum']} – {rng['Typ']}")

def main():
    st.set_page_config(page_title="Malin-produktionsapp", layout="wide")
    st.title("🎬 Malin-produktionsapp")
    if not SHEET_URL:
        st.error("SHEET_URL saknas i secrets")
        return
    sh = gc.open_by_url(SHEET_URL)
    inst = läs_inställningar(sh)
    inställningspanel(sh, inst)
    df = init_sheet(sh)
    df = säkerställ_kolumner(df)
    df = konvertera_typer(df) if 'konvertera_typer' in globals() else df
    df = scenformulär(df, inst, sh)
    visa_data(df)

if __name__ == "__main__":
    main()
