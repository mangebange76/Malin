import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)
data_sheet = sh.worksheet("Data")
settings_sheet = sh.worksheet("Inställningar")

def läs_inställningar():
    try:
        df = pd.DataFrame(settings_sheet.get_all_records())
        if df.empty:
            return {}
        return df.iloc[0].to_dict()
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar: {e}")
        return {}

def spara_inställningar(inst):
    settings_sheet.clear()
    settings_sheet.append_row(list(inst.keys()))
    settings_sheet.append_row(list(inst.values()))

def säkerställ_data():
    existerande = data_sheet.get_all_values()
    if not existerande:
        data_sheet.append_row(COLUMNS)

def rensa_databas():
    data_sheet.clear()
    data_sheet.append_row(COLUMNS)

def hämta_nästa_datum():
    values = data_sheet.get_all_values()
    if len(values) <= 1:
        start = läs_inställningar().get("Startdatum")
        return start or datetime.now().strftime("%Y-%m-%d")
    senaste = values[-1][0]
    nästa = datetime.strptime(senaste, "%Y-%m-%d") + pd.Timedelta(days=1)
    return nästa.strftime("%Y-%m-%d")

def huvudvy():
    st.title("Lägg till scen")
    inst = läs_inställningar()

    with st.form("scenformulär", clear_on_submit=True):
        datum = st.text_input("Datum", value=hämta_nästa_datum(), disabled=True)
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, value=0 if typ != "Vila inspelningsplats" else 1)
        nya_män = st.number_input("Nya män", min_value=0, value=0)

        enkel_vaginal = st.number_input("Enkel vaginal", min_value=0, value=0)
        enkel_anal = st.number_input("Enkel anal", min_value=0, value=0)
        dp = st.number_input("DP", min_value=0, value=0)
        dpp = st.number_input("DPP", min_value=0, value=0)
        dap = st.number_input("DAP", min_value=0, value=0)
        tpp = st.number_input("TPP", min_value=0, value=0)
        tpa = st.number_input("TPA", min_value=0, value=0)
        tap = st.number_input("TAP", min_value=0, value=0)

        tid_enkel = st.number_input("Tid enkel (sek)", min_value=0, value=0)
        tid_dubbel = st.number_input("Tid dubbel (sek)", min_value=0, value=0)
        tid_trippel = st.number_input("Tid trippel (sek)", min_value=0, value=0)
        vila = st.number_input("Vila (sek mellan byten)", min_value=0, value=0)

        kompisar = st.number_input(f"Kompisar (max {inst.get('Kompisar', 0)})", min_value=0, value=0)
        pappans_vänner = st.number_input(f"Pappans vänner (max {inst.get('Pappans vänner', 0)})", min_value=0, value=0)
        nils_vänner = st.number_input(f"Nils vänner (max {inst.get('Nils vänner', 0)})", min_value=0, value=0)
        nils_familj = st.number_input(f"Nils familj (max {inst.get('Nils familj', 0)})", min_value=0, value=0)

        dt_tid_per_man = st.number_input("DT tid per man", min_value=0, value=0)
        antal_varv = st.number_input("Antal varv", min_value=0, value=0)
        älskar_med = st.number_input("Älskar med", min_value=0, value=0)
        sover_med = st.number_input("Sover med", min_value=0, value=0)
        nils_sex = st.number_input("Nils sex", min_value=0, value=0)
        prenumeranter = st.number_input("Prenumeranter", min_value=0, value=0)

        intäkt = st.number_input("Intäkt ($)", value=0.0)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", value=0.0)
        mäns_lön = st.number_input("Mäns lön ($)", value=0.0)
        kompisars_lön = st.number_input("Kompisars lön ($)", value=0.0)

        dt_total_tid = st.number_input("DT total tid (sek)", min_value=0, value=0)
        total_tid = st.number_input("Total tid (sek)", min_value=0, value=0)
        total_tid_h = st.number_input("Total tid (h)", value=0.0)
        min_per_kille = st.number_input("Minuter per kille", value=0.0)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        if bekräfta and st.form_submit_button("Lägg till"):
            if (
                kompisar > inst.get("Kompisar", 0)
                or pappans_vänner > inst.get("Pappans vänner", 0)
                or nils_vänner > inst.get("Nils vänner", 0)
                or nils_familj > inst.get("Nils familj", 0)
            ):
                st.error("Ett av fälten överskrider tillåtet maxvärde enligt inställningarna.")
                return

            rad = [
                datum, typ, antal_vilodagar, nya_män, enkel_vaginal, enkel_anal, dp, dpp, dap, tpp, tpa, tap,
                tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans_vänner, nils_vänner, nils_familj,
                dt_tid_per_man, antal_varv, älskar_med, sover_med, nils_sex, prenumeranter,
                intäkt, kvinnans_lön, mäns_lön, kompisars_lön,
                dt_total_tid, total_tid, total_tid_h, min_per_kille, vila
            ]
            data_sheet.append_row(rad)
            st.success("Rad sparad!")

def inställningsvy():
    st.title("Inställningar")
    befintliga = läs_inställningar()
    with st.form("instform"):
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(befintliga.get("Startdatum", datetime.now())))
        namn = st.text_input("Kvinnans namn", value=befintliga.get("Namn", ""))
        födelsedatum = st.date_input("Födelsedatum", value=pd.to_datetime(befintliga.get("Födelsedatum", datetime(2000, 1, 1))))
        kompisar = st.number_input("Kompisar", min_value=0, value=int(befintliga.get("Kompisar", 0)))
        nils_familj = st.number_input("Nils familj", min_value=0, value=int(befintliga.get("Nils familj", 0)))
        pappans_vänner = st.number_input("Pappans vänner", min_value=0, value=int(befintliga.get("Pappans vänner", 0)))
        nils_vänner = st.number_input("Nils vänner", min_value=0, value=int(befintliga.get("Nils vänner", 0)))

        sparaknapp = st.form_submit_button("Spara inställningar")
        rensaknapp = st.form_submit_button("Rensa hela databasen")

        if sparaknapp:
            inst = {
                "Startdatum": startdatum.strftime("%Y-%m-%d"),
                "Namn": namn,
                "Födelsedatum": födelsedatum.strftime("%Y-%m-%d"),
                "Kompisar": kompisar,
                "Nils familj": nils_familj,
                "Pappans vänner": pappans_vänner,
                "Nils vänner": nils_vänner
            }
            spara_inställningar(inst)
            st.success("Inställningar sparade.")

        if rensaknapp:
            rensa_databas()
            st.warning("Databasen är rensad!")

def main():
    säkerställ_data()
    val = st.sidebar.selectbox("Välj läge", ["Lägg till scen", "Inställningar"])
    if val == "Inställningar":
        inställningsvy()
    else:
        huvudvy()

if __name__ == "__main__":
    main()
