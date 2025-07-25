import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2 import service_account
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Anslut till Google Sheets
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# Hämta eller skapa blad
def get_worksheet(name, columns=None):
    try:
        return sh.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows="1000", cols=str(len(columns or [])))
        if columns:
            ws.append_row(columns)
        return ws

# Säkerställ att 'Data' och 'Inställningar' finns
data_ws = get_worksheet("Data", columns=COLUMNS)
inst_ws = get_worksheet("Inställningar", columns=["Fält", "Värde"])

# Läs inställningar
def läs_inställningar():
    try:
        df = pd.DataFrame(inst_ws.get_all_records())
        return {rad["Fält"]: rad["Värde"] for _, rad in df.iterrows()}
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar: {e}")
        return {}

# Spara inställningar
def spara_inställningar(data):
    inst_ws.clear()
    inst_ws.append_row(["Fält", "Värde"])
    for key, val in data.items():
        inst_ws.append_row([key, val])

# Läs in data
def hämta_data():
    rows = data_ws.get_all_values()
    if not rows or rows[0] != COLUMNS:
        data_ws.clear()
        data_ws.append_row(COLUMNS)
        return pd.DataFrame(columns=COLUMNS)
    return pd.DataFrame(data_ws.get_all_records())

# Spara ny rad
def spara_data(rad):
    df = hämta_data()
    säkerställ_kolumner(df)
    ny_df = pd.DataFrame([rad], columns=COLUMNS)
    df = pd.concat([df, ny_df], ignore_index=True)
    data_ws.clear()
    data_ws.append_row(COLUMNS)
    for _, row in df.iterrows():
        data_ws.append_row([row.get(col, "") for col in COLUMNS])

# Bestäm datum
def bestäm_datum():
    df = hämta_data()
    inst = läs_inställningar()
    if df.empty:
        startdatum = inst.get("Startdatum", datetime.today().strftime("%Y-%m-%d"))
        return pd.to_datetime(startdatum).date()
    else:
        senaste = pd.to_datetime(df["Datum"].iloc[-1]).date()
        return senaste + timedelta(days=1)

# Inställningsformulär
def inställningar():
    st.subheader("Inställningar")
    inst = läs_inställningar()
    with st.form("instform"):
        namn = st.text_input("Kvinnans namn", inst.get("Namn", ""))
        födelse = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "2000-01-01")), min_value=datetime(1970, 1, 1).date())
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", datetime.today().strftime("%Y-%m-%d"))), min_value=datetime(1990, 1, 1).date())
        kompisar = st.number_input("Max kompisar", 0, 999, int(inst.get("Kompisar", 0)))
        pappa = st.number_input("Max pappans vänner", 0, 999, int(inst.get("Pappans vänner", 0)))
        nils = st.number_input("Max Nils vänner", 0, 999, int(inst.get("Nils vänner", 0)))
        familj = st.number_input("Max Nils familj", 0, 999, int(inst.get("Nils familj", 0)))
        submit = st.form_submit_button("Spara")
    if submit:
        spara_inställningar({
            "Namn": namn,
            "Födelsedatum": str(födelse),
            "Startdatum": str(startdatum),
            "Kompisar": kompisar,
            "Pappans vänner": pappa,
            "Nils vänner": nils,
            "Nils familj": familj,
        })
        st.success("Inställningar sparade.")

# Formulär för att lägga till scen
def scenformulär():
    st.subheader("Lägg till scen")
    inst = läs_inställningar()
    datum = bestäm_datum()

    with st.form("scenformulär", clear_on_submit=False):
        st.write(f"Datum för denna rad: **{datum}**")
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        vilodagar = st.number_input("Antal vilodagar", 0, 30, 0)
        nya_män = st.number_input("Nya män", 0, 99, 0)
        enkel_vag = st.number_input("Enkel vaginal", 0, 99, 0)
        enkel_anal = st.number_input("Enkel anal", 0, 99, 0)
        dp = st.number_input("DP", 0, 99, 0)
        dpp = st.number_input("DPP", 0, 99, 0)
        dap = st.number_input("DAP", 0, 99, 0)
        tpp = st.number_input("TPP", 0, 99, 0)
        tpa = st.number_input("TPA", 0, 99, 0)
        tap = st.number_input("TAP", 0, 99, 0)
        tid_enkel = st.number_input("Tid enkel", 0, 999, 0)
        tid_dubbel = st.number_input("Tid dubbel", 0, 999, 0)
        tid_trippel = st.number_input("Tid trippel", 0, 999, 0)
        vila = st.number_input("Vila", 0, 999, 0)
        kompisar = st.number_input(f"Kompisar (max {inst.get('Kompisar', 0)})", 0, 999, 0)
        pappans = st.number_input(f"Pappans vänner (max {inst.get('Pappans vänner', 0)})", 0, 999, 0)
        nils_v = st.number_input(f"Nils vänner (max {inst.get('Nils vänner', 0)})", 0, 999, 0)
        nils_f = st.number_input(f"Nils familj (max {inst.get('Nils familj', 0)})", 0, 999, 0)
        dt_tid_per_man = st.number_input("DT tid per man", 0, 999, 0)
        antal_varv = st.number_input("Antal varv", 0, 999, 0)
        älskar = st.number_input("Älskar med", 0, 99, 0)
        sover = st.number_input("Sover med", 0, 99, 0)
        nils_sex = st.number_input("Nils sex", 0, 99, 0)
        subs = st.number_input("Prenumeranter", 0, 999999, 0)
        kvinna_lön = st.number_input("Kvinnans lön ($)", 0.0, 99999.0, 0.0)
        män_lön = st.number_input("Mäns lön ($)", 0.0, 99999.0, 0.0)
        kompis_lön = st.number_input("Kompisars lön ($)", 0.0, 99999.0, 0.0)
        dt_tid_total = st.number_input("DT total tid (sek)", 0, 999999, 0)
        total_tid_sek = st.number_input("Total tid (sek)", 0, 999999, 0)
        total_tid_h = st.number_input("Total tid (h)", 0.0, 99.0, 0.0)
        minuter_per_kille = st.number_input("Minuter per kille", 0.0, 9999.0, 0.0)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
        submit = st.form_submit_button("Lägg till")

    if submit:
        if not bekräfta:
            st.warning("Du måste bekräfta att du vill lägga till raden.")
            return

        if any([
            kompisar > int(inst.get("Kompisar", 0)),
            pappans > int(inst.get("Pappans vänner", 0)),
            nils_v > int(inst.get("Nils vänner", 0)),
            nils_f > int(inst.get("Nils familj", 0))
        ]):
            st.error("Ett eller flera värden överskrider maxgränserna enligt inställningarna.")
            return

        rad = [
            str(datum), typ, vilodagar, nya_män, enkel_vag, enkel_anal, dp, dpp, dap,
            tpp, tpa, tap, tid_enkel, tid_dubbel, tid_trippel, vila, kompisar, pappans,
            nils_v, nils_f, dt_tid_per_man, antal_varv, älskar, sover, nils_sex,
            subs, 0.0, kvinna_lön, män_lön, kompis_lön, dt_tid_total, total_tid_sek,
            total_tid_h, minuter_per_kille
        ]
        spara_data(rad)
        st.success("Raden har lagts till.")

# Huvudfunktion
def main():
    st.title("Malin-produktionsapp")
    meny = st.sidebar.radio("Välj vy", ["Lägg till scen", "Inställningar"])
    if meny == "Inställningar":
        inställningar()
    else:
        scenformulär()

if __name__ == "__main__":
    main()
