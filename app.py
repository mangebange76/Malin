import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"

def init_sheet(sh):
    try:
        sheet = sh.worksheet("Data")
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Data", rows="1000", cols="40")
        sheet.update("A1:AD1", [list(pd.DataFrame(columns=[
            "Datum", "Typ", "Scenens längd (h)", "Antal vilodagar", "Övriga män",
            "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
            "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
            "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
            "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
            "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
        ]).columns)])

    df = pd.DataFrame(sheet.get_all_records())
    df = df.reindex(columns=COLUMNS, fill_value=0)
    return df

COLUMNS = [
    "Datum", "Typ", "Scenens längd (h)", "Övriga män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP",
    "TPP", "TPA", "TAP", "Kompisar", "Pappans vänner",
    "Nils vänner", "Nils familj", "DT tid per man (sek)",
    "Älskar med", "Sover med", "Nils sex", "Prenumeranter",
    "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)",
    "Kompisars lön ($)", "DT total tid (sek)", "Total tid (sek)",
    "Total tid (h)", "Minuter per kille"
]

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
    if "Namn" not in df.columns or "Värde" not in df.columns:
        st.error("Fel: 'Inställningar'-bladet saknar nödvändiga kolumner.")
        return {}

    return {row["Namn"]: tolka_värde(row["Värde"]) for _, row in df.iterrows()}

def tolka_värde(v):
    if isinstance(v, str):
        v = v.replace(",", ".")
    try:
        return float(v) if "." in str(v) else int(v)
    except:
        return str(v)

def spara_inställningar(sh, nya_inst):
    sheet = sh.worksheet("Inställningar")
    df = pd.DataFrame(sheet.get_all_records())
    idag = datetime.today().strftime("%Y-%m-%d")
    for i, row in df.iterrows():
        namn = row["Namn"]
        if namn in nya_inst:
            df.at[i, "Värde"] = nya_inst[namn]
            df.at[i, "Senast ändrad"] = idag
    sheet.update("A2:C" + str(len(df) + 1), df.values.tolist())

def visa_inställningar(inst, sh):
    st.sidebar.subheader("Inställningar")
    nya = {}
    for key in ["Startdatum", "Kvinnans namn", "Födelsedatum", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        if "datum" in key.lower():
            nya[key] = st.sidebar.text_input(key, value=str(inst.get(key, "")))
        else:
            nya[key] = st.sidebar.number_input(key, min_value=0, value=int(inst.get(key, 0)), step=1)
    if st.sidebar.button("Spara inställningar"):
        spara_inställningar(sh, nya)
        st.experimental_rerun()

def ensure_columns_exist(df):
    kolumner = [
        "Datum", "Typ", "Scenens längd (h)", "Antal vilodagar", "Övriga män",
        "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
        "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
        "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
        "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
        "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
    ]
    for kolumn in kolumner:
        if kolumn not in df.columns:
            df[kolumn] = 0
    return df[kolumner]

def konvertera_typer(df):
    for kol in df.columns:
        if kol == "Datum":
            df[kol] = pd.to_datetime(df[kol], errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            df[kol] = pd.to_numeric(df[kol], errors="coerce").fillna(0)
    return df

def rensa_data(sh):
    sheet = sh.worksheet("Data")
    sheet.resize(rows=1)
    kolumner = [
        "Datum", "Typ", "Scenens längd (h)", "Antal vilodagar", "Övriga män",
        "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
        "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
        "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
        "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
        "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
    ]
    sheet.update("A1:AD1", [kolumner])

def save_data(sh, df):
    df = ensure_columns_exist(df)
    df = konvertera_typer(df)
    sheet = sh.worksheet("Data")
    sheet.resize(rows=1)
    sheet.update("A1", [df.columns.tolist()] + df.astype(str).values.tolist())

def scenformulär(df, inst, sh):
    with st.form("Lägg till ny rad"):
        f = {}
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", min_value=0, value=0, key="vilodagar")
        f["Scenens längd (h)"] = st.number_input("Scenens längd (h)", min_value=0.0, value=0.0, key="scenlängd")
        f["Övriga män"] = st.number_input("Övriga män", min_value=0, value=0, key="övriga")
        f["Enkel vaginal"] = st.number_input("Enkel vaginal", min_value=0, value=0, key="ev")
        f["Enkel anal"] = st.number_input("Enkel anal", min_value=0, value=0, key="ea")
        f["DP"] = st.number_input("DP", min_value=0, value=0, key="dp")
        f["DPP"] = st.number_input("DPP", min_value=0, value=0, key="dpp")
        f["DAP"] = st.number_input("DAP", min_value=0, value=0, key="dap")
        f["TPP"] = st.number_input("TPP", min_value=0, value=0, key="tpp")
        f["TAP"] = st.number_input("TAP", min_value=0, value=0, key="tap")
        f["TPA"] = st.number_input("TPA", min_value=0, value=0, key="tpa")
        f["Kompisar"] = st.number_input("Kompisar", min_value=0, value=0, max_value=inst.get("Kompisar", 0), key="kompisar")
        f["Pappans vänner"] = st.number_input("Pappans vänner", min_value=0, value=0, max_value=inst.get("Pappans vänner", 0), key="pappans")
        f["Nils vänner"] = st.number_input("Nils vänner", min_value=0, value=0, max_value=inst.get("Nils vänner", 0), key="nilsvänner")
        f["Nils familj"] = st.number_input("Nils familj", min_value=0, value=0, max_value=inst.get("Nils familj", 0), key="nilsfamilj")
        f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", min_value=0, value=0, key="dttid")
        f["Älskar med"] = st.number_input("Antal älskar med", min_value=0, value=0, key="älskar")
        f["Sover med"] = st.number_input("Antal sover med", min_value=0, value=0, key="sover")

        per_kille_min, total_h = beräkna_tid_per_kille(f)
        st.markdown(f"**Total tid per kille (inkl. deep throat): {per_kille_min:.2f} minuter**")
        st.markdown(f"**Total tid: {total_h:.2f} timmar**")
        if total_h > 18:
            st.error("⚠️ Totaltiden överskrider 18 timmar!")

        submit = st.form_submit_button("Lägg till")

    if submit:
        df = process_lägg_till_rader(df, inst, f)
        save_data(sh, df)
        st.success("Raden har lagts till!")
        st.experimental_rerun()

def visa_data(df):
    st.subheader("Databas")
    st.dataframe(df)

    if not df.empty:
        totaltid = df["Total tid (h)"].sum()
        dttid = df["DT total tid (sek)"].sum() / 3600
        per_kille = df["Minuter per kille"].mean()
        st.markdown(f"**Total tid (h):** {totaltid:.2f}")
        st.markdown(f"**Deep throat-tid (h):** {dttid:.2f}")
        st.markdown(f"**Snitt tid per kille (min):** {per_kille:.2f}")

        max_tid = df["Total tid (h)"].max()
        if max_tid > 18:
            st.warning("⚠️ Minst en rad har total tid över 18 timmar!")

def visa_inställningar(inst, sh):
    st.sidebar.subheader("Inställningar")
    nya = {}
    for nyckel in ["Startdatum", "Kvinnans namn", "Födelsedatum", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        if isinstance(inst.get(nyckel), (int, float)):
            nya[nyckel] = st.sidebar.number_input(nyckel, value=inst.get(nyckel, 0))
        else:
            nya[nyckel] = st.sidebar.text_input(nyckel, value=inst.get(nyckel, ""))
    if st.sidebar.button("Spara inställningar"):
        spara_inställningar(sh, nya)
        st.sidebar.success("Inställningar sparade. Ladda om sidan för att se ändringar.")

    if st.sidebar.button("Rensa databas"):
        rensa_data(sh)
        st.sidebar.warning("Databasen har rensats.")

def main():
    st.set_page_config(page_title="Malin-produktionsapp", layout="wide")
    st.title("Malin-produktionsapp 🎬")
    try:
        gc = autentisera()
        sh = gc.open_by_url(SHEET_URL)
        df = init_sheet(sh)
        inst = läs_inställningar(sh)

        visa_inställningar(inst, sh)
        scenformulär(df, inst, sh)
        visa_data(df)
    except Exception as e:
        st.error(f"🚨 Fel vid laddning: {e}")

if __name__ == "__main__":
    main()
