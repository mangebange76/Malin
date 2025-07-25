import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader

# --- Google Sheets-autentisering ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# --- Hjälpfunktioner ---
def hämta_inställningar():
    try:
        df = pd.DataFrame(sh.worksheet("Inställningar").get_all_records())
        return df.set_index("Fält")["Värde"].to_dict()
    except:
        return {}

def hämta_data():
    try:
        data = sh.worksheet("Data").get_all_records()
        df = pd.DataFrame(data)
        säkerställ_kolumner(df)
        return df
    except:
        return pd.DataFrame(columns=COLUMNS)

def bestäm_datum(df, inställningar):
    if df.empty:
        start = inställningar.get("Startdatum")
        if start:
            return pd.to_datetime(start).date()
        return datetime.today().date()
    senaste = pd.to_datetime(df["Datum"].iloc[-1]).date()
    return senaste + timedelta(days=1)

def spara_rad(rad):
    ws = sh.worksheet("Data")
    ws.append_row(rad)

def spara_inställningar(data):
    ws = sh.worksheet("Inställningar")
    df = pd.DataFrame(list(data.items()), columns=["Fält", "Värde"])
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

def rensa_databasen():
    ws = sh.worksheet("Data")
    ws.clear()
    ws.append_row(COLUMNS)

# --- Formulär: inställningar ---
def inställningar_form():
    st.subheader("Inställningar")
    with st.form("instform"):
        namn = st.text_input("Namn på kvinnan")
        födelsedatum = st.date_input("Födelsedatum", min_value=datetime(1970, 1, 1))
        startdatum = st.date_input("Startdatum", value=datetime.today(), min_value=datetime(1990, 1, 1))
        kompisar = st.number_input("Max kompisar", min_value=0, step=1)
        pappans_vänner = st.number_input("Max pappans vänner", min_value=0, step=1)
        nils_vänner = st.number_input("Max Nils vänner", min_value=0, step=1)
        nils_familj = st.number_input("Max Nils familj", min_value=0, step=1)
        spara = st.form_submit_button("Spara inställningar")

    if spara:
        data = {
            "Namn": namn,
            "Födelsedatum": födelsedatum.strftime("%Y-%m-%d"),
            "Startdatum": startdatum.strftime("%Y-%m-%d"),
            "Kompisar": int(kompisar),
            "Pappans vänner": int(pappans_vänner),
            "Nils vänner": int(nils_vänner),
            "Nils familj": int(nils_familj)
        }
        spara_inställningar(data)
        st.success("Inställningar sparade.")

    if st.button("Rensa databasen"):
        rensa_databasen()
        st.success("Databasen är nu rensad.")

# --- Formulär: lägg till scen ---
def scenformulär(df, inst):
    st.subheader("Lägg till scen")
    datum = bestäm_datum(df, inst)

    with st.form("scenform"):
        st.markdown(f"**Datum:** {datum}")
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        vilodagar = st.number_input("Antal vilodagar", min_value=0, step=1)
        nya_män = st.number_input("Nya män", min_value=0, step=1)
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1)
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
        dp = st.number_input("DP", min_value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, step=1)
        dap = st.number_input("DAP", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)
        tid_enkel = st.number_input("Tid enkel", min_value=0, step=1)
        tid_dubbel = st.number_input("Tid dubbel", min_value=0, step=1)
        tid_trippel = st.number_input("Tid trippel", min_value=0, step=1)
        vila = st.number_input("Vila", min_value=0, step=1)
        kompisar = st.number_input(f"Kompisar (max {inst.get('Kompisar')})", min_value=0, max_value=int(inst.get("Kompisar", 999)))
        pappans = st.number_input(f"Pappans vänner (max {inst.get('Pappans vänner')})", min_value=0, max_value=int(inst.get("Pappans vänner", 999)))
        nils_v = st.number_input(f"Nils vänner (max {inst.get('Nils vänner')})", min_value=0, max_value=int(inst.get("Nils vänner", 999)))
        nils_fam = st.number_input(f"Nils familj (max {inst.get('Nils familj')})", min_value=0, max_value=int(inst.get("Nils familj", 999)))
        dt_tid_per_man = st.number_input("DT tid per man", min_value=0, step=1)
        antal_varv = st.number_input("Antal varv", min_value=0, step=1)
        älskar_med = st.number_input("Älskar med", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)
        nils_sex = st.number_input("Nils sex", min_value=0, step=1)
        pren = st.number_input("Prenumeranter", min_value=0, step=1)
        intäkt = st.number_input("Intäkt ($)", min_value=0.0, step=1.0)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=1.0)
        mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=1.0)
        kompislön = st.number_input("Kompisars lön ($)", min_value=0.0, step=1.0)
        dt_total_tid = st.number_input("DT total tid (sek)", min_value=0, step=1)
        total_tid_sek = st.number_input("Total tid (sek)", min_value=0, step=1)
        total_tid_h = st.number_input("Total tid (h)", min_value=0.0, step=0.1)
        min_per_kille = st.number_input("Minuter per kille", min_value=0.0, step=0.1)
        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        spara = st.form_submit_button("Spara scen")

    if spara and bekräfta:
        rad = [
            datum.strftime("%Y-%m-%d"), typ, vilodagar, nya_män, enkel_vag, enkel_anal, dp, dpp, dap,
            tpp, tpa, tap, tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans, nils_v, nils_fam,
            dt_tid_per_man, antal_varv, älskar_med, sover_med, nils_sex, pren, intäkt,
            kvinnans_lön, mäns_lön, kompislön, dt_total_tid, total_tid_sek, total_tid_h, min_per_kille, vila
        ]
        spara_rad(rad)
        st.success("Scen sparad!")

# --- Huvudfunktion ---
def main():
    st.title("Malin-produktionsapp")

    meny = st.sidebar.selectbox("Välj läge", ["Lägg till scen", "Inställningar"])
    df = hämta_data()
    inst = hämta_inställningar()

    if meny == "Inställningar":
        inställningar_form()
    else:
        scenformulär(df, inst)

if __name__ == "__main__":
    main()
