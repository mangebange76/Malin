import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)
sheet = sh.sheet1

# Funktion för att initiera databasen med rätt kolumner
def initiera_databas():
    headers = sheet.row_values(1)
    if headers != COLUMNS:
        sheet.clear()
        sheet.insert_row(COLUMNS, index=1)

# Funktion för att hämta inställningar från settings-blad
def läs_inställningar():
    try:
        settings_sheet = sh.worksheet("settings")
        settings_data = settings_sheet.get_all_records()
        return settings_data[0] if settings_data else {}
    except Exception:
        return {}

# Funktion för att spara inställningar till settings-blad
def spara_inställningar(data):
    try:
        settings_sheet = sh.worksheet("settings")
    except Exception:
        settings_sheet = sh.add_worksheet(title="settings", rows="10", cols="10")
    settings_sheet.clear()
    settings_sheet.append_row(list(data.keys()))
    settings_sheet.append_row(list(data.values()))

# Funktion för att rensa databasen
def rensa_databas():
    sheet.clear()
    sheet.insert_row(COLUMNS, index=1)

# Funktion för att hämta befintlig data
def hämta_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        säkerställ_kolumner(df)
        return df
    except Exception as e:
        st.error(f"Fel vid hämtning av data: {e}")
        return pd.DataFrame(columns=COLUMNS)

# Funktion för att spara ny rad till databasen
def spara_data(rad):
    try:
        rad = ["" if v is None else v for v in rad]
        if len(rad) != len(COLUMNS):
            st.error(f"Fel antal kolumner: {len(rad)} ≠ {len(COLUMNS)}")
            return
        sheet.append_row(rad)
        st.success("Raden sparades.")
    except Exception as e:
        st.error(f"Fel vid sparande av data: {e}")

# Visa inställningsformulär
def inställningar():
    st.header("Inställningar")
    data = läs_inställningar()

    namn = st.text_input("Namn", value=data.get("namn", ""))
    födelsedatum = st.date_input("Födelsedatum", value=pd.to_datetime(data.get("födelsedatum", "2000-01-01")))
    kompisar = st.number_input("Max antal kompisar", value=int(data.get("kompisar", 0)), min_value=0)
    pappans_vänner = st.number_input("Max antal pappans vänner", value=int(data.get("pappans_vänner", 0)), min_value=0)
    nils_vänner = st.number_input("Max antal Nils vänner", value=int(data.get("nils_vänner", 0)), min_value=0)
    nils_familj = st.number_input("Max antal Nils familj", value=int(data.get("nils_familj", 0)), min_value=0)

    if st.button("Spara inställningar"):
        data = {
            "namn": namn,
            "födelsedatum": str(födelsedatum),
            "kompisar": kompisar,
            "pappans_vänner": pappans_vänner,
            "nils_vänner": nils_vänner,
            "nils_familj": nils_familj,
        }
        spara_inställningar(data)
        st.success("Inställningarna sparades.")

    if st.button("Rensa databasen"):
        rensa_databas()
        st.success("Databasen har rensats.")

# Visa formulär för att lägga till scen
def scenformulär():
    st.header("Lägg till scen")

    df = hämta_data()
    inst = läs_inställningar()

    with st.form("scenformulär"):
        datum = st.date_input("Datum", value=datetime.date.today())
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", value=0, min_value=0)
        nya_män = st.number_input("Nya män", value=0, min_value=0)
        enkel_vaginal = st.number_input("Enkel vaginal", value=0, min_value=0)
        enkel_anal = st.number_input("Enkel anal", value=0, min_value=0)
        dp = st.number_input("DP", value=0, min_value=0)
        dpp = st.number_input("DPP", value=0, min_value=0)
        dap = st.number_input("DAP", value=0, min_value=0)
        tpp = st.number_input("TPP", value=0, min_value=0)
        tpa = st.number_input("TPA", value=0, min_value=0)
        tap = st.number_input("TAP", value=0, min_value=0)
        tid_enkel = st.number_input("Tid enkel (sek)", value=0, min_value=0)
        tid_dubbel = st.number_input("Tid dubbel (sek)", value=0, min_value=0)
        tid_trippel = st.number_input("Tid trippel (sek)", value=0, min_value=0)
        vila = st.number_input("Vila (sek)", value=0, min_value=0)

        kompisar = st.number_input(f"Kompisar (max {inst.get('kompisar', 0)})", value=0, min_value=0)
        if kompisar > inst.get("kompisar", 0):
            st.warning(f"Överskrider max tillåtna kompisar ({inst.get('kompisar', 0)})")

        pappans_vänner = st.number_input(f"Pappans vänner (max {inst.get('pappans_vänner', 0)})", value=0, min_value=0)
        if pappans_vänner > inst.get("pappans_vänner", 0):
            st.warning(f"Överskrider max tillåtna pappans vänner ({inst.get('pappans_vänner', 0)})")

        nils_vänner = st.number_input(f"Nils vänner (max {inst.get('nils_vänner', 0)})", value=0, min_value=0)
        if nils_vänner > inst.get("nils_vänner", 0):
            st.warning(f"Överskrider max tillåtna Nils vänner ({inst.get('nils_vänner', 0)})")

        nils_familj = st.number_input(f"Nils familj (max {inst.get('nils_familj', 0)})", value=0, min_value=0)
        if nils_familj > inst.get("nils_familj", 0):
            st.warning(f"Överskrider max tillåtna Nils familj ({inst.get('nils_familj', 0)})")

        dt_tid_per_man = st.number_input("DT tid per man", value=0)
        antal_varv = st.number_input("Antal varv", value=0)
        älskar_med = st.number_input("Älskar med", value=0)
        sover_med = st.number_input("Sover med", value=0)
        nils_sex = st.number_input("Nils sex", value=0)
        prenumeranter = st.number_input("Prenumeranter", value=0)
        intakt = st.number_input("Intäkt ($)", value=0.0)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", value=0.0)
        mäns_lön = st.number_input("Mäns lön ($)", value=0.0)
        kompisars_lön = st.number_input("Kompisars lön ($)", value=0.0)
        dt_total_tid = st.number_input("DT total tid (sek)", value=0)
        total_tid_sek = st.number_input("Total tid (sek)", value=0)
        total_tid_h = st.number_input("Total tid (h)", value=0.0)
        min_per_kille = st.number_input("Minuter per kille", value=0.0)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        submitted = st.form_submit_button("Lägg till scen")

        if submitted and bekräfta:
            rad = [
                str(datum), typ, antal_vilodagar, nya_män, enkel_vaginal, enkel_anal, dp, dpp, dap, tpp, tpa, tap,
                tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans_vänner, nils_vänner, nils_familj,
                dt_tid_per_man, antal_varv, älskar_med, sover_med, nils_sex, prenumeranter, intakt,
                kvinnans_lön, mäns_lön, kompisars_lön, dt_total_tid, total_tid_sek, total_tid_h, min_per_kille, vila
            ]
            spara_data(rad)

# Huvudprogram
def main():
    st.title("Malin-produktionsapp")
    initiera_databas()

    menyval = st.sidebar.selectbox("Meny", ["Inställningar", "Lägg till scen"])
    if menyval == "Inställningar":
        inställningar()
    elif menyval == "Lägg till scen":
        scenformulär()

if __name__ == "__main__":
    main()
