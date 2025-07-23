import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample
from berakningar import process_lägg_till_rader

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Spreadsheet
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumner
DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "Älskar med", "Sover med", "Nils sex",
    "DT tid per man (sek)", "DT total tid (sek)", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Minuter per kille", "Scenens längd (h)"
]

INST_COLUMNS = ["Inställning", "Värde", "Senast ändrad"]

# Initiera kalkylblad
def init_sheet(name, cols):
    try:
        worksheet = sh.worksheet(name)
    except:
        worksheet = sh.add_worksheet(title=name, rows="1000", cols="30")
        worksheet.update("A1", [cols])
    else:
        existing_cols = worksheet.row_values(1)
        if existing_cols != cols:
            worksheet.resize(rows=1)
            worksheet.update("A1", [cols])

def init_inställningar():
    try:
        worksheet = sh.worksheet("Inställningar")
    except:
        worksheet = sh.add_worksheet(title="Inställningar", rows="100", cols="3")
        worksheet.update("A1", [INST_COLUMNS])
        standard = [
            ["Kvinnans namn", "Malin", datetime.now().strftime("%Y-%m-%d")],
            ["Födelsedatum", "1984-03-26", datetime.now().strftime("%Y-%m-%d")],
            ["Startdatum", "2014-03-26", datetime.now().strftime("%Y-%m-%d")],
            ["Kompisar", "100", datetime.now().strftime("%Y-%m-%d")],
            ["Pappans vänner", "40", datetime.now().strftime("%Y-%m-%d")],
            ["Nils vänner", "30", datetime.now().strftime("%Y-%m-%d")],
            ["Nils familj", "20", datetime.now().strftime("%Y-%m-%d")]
        ]
        worksheet.update(f"A2:C{len(standard)+1}", standard)

def läs_inställningar():
    worksheet = sh.worksheet("Inställningar")
    data = worksheet.get_all_records()
    inst = {}
    for rad in data:
        val = str(rad["Värde"])
        try:
            inst[rad["Inställning"]] = float(val.replace(",", "."))
        except:
            inst[rad["Inställning"]] = val
    return inst

def spara_inställning(nyckel, värde):
    worksheet = sh.worksheet("Inställningar")
    df = pd.DataFrame(worksheet.get_all_records())
    idag = datetime.now().strftime("%Y-%m-%d")
    if nyckel in df["Inställning"].values:
        idx = df[df["Inställning"] == nyckel].index[0]
        worksheet.update_cell(idx + 2, 2, str(värde))
        worksheet.update_cell(idx + 2, 3, idag)
    else:
        worksheet.append_row([nyckel, str(värde), idag])

def säkerställ_kolumner(df):
    for kolumn in DATA_COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = ""
    return df[DATA_COLUMNS]

def spara_data(df):
    df = df.fillna("").astype(str)
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update("A1", [df.columns.tolist()] + df.values.tolist())

def ladda_data():
    try:
        worksheet = sh.worksheet("Data")
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=DATA_COLUMNS)
        df = pd.DataFrame(data)
        return säkerställ_kolumner(df)
    except:
        return pd.DataFrame(columns=DATA_COLUMNS)

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="form_typ")
        dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1, key="form_dagar")
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.25, key="form_scen_tid")
        ov = st.number_input("Övriga män", min_value=0, step=1, key="form_ov")
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1, key="form_enkel_vag")
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1, key="form_enkel_anal")
        dp = st.number_input("DP", min_value=0, step=1, key="form_dp")
        dpp = st.number_input("DPP", min_value=0, step=1, key="form_dpp")
        dap = st.number_input("DAP", min_value=0, step=1, key="form_dap")
        tpp = st.number_input("TPP", min_value=0, step=1, key="form_tpp")
        tap = st.number_input("TAP", min_value=0, step=1, key="form_tap")
        tpa = st.number_input("TPA", min_value=0, step=1, key="form_tpa")
        komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)), key="form_komp")
        pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)), key="form_pappans")
        nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)), key="form_nils_v")
        nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)), key="form_nils_f")
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1, key="form_dt_tid_per_man")
        älskar = st.number_input("Antal älskar med", min_value=0, step=1, key="form_älskar")
        sover = st.number_input("Antal sover med", min_value=0, step=1, key="form_sover")

        # Beräkna och visa info direkt
        total_män = ov + komp + pappans + nils_v + nils_f
        total_deepthroat_tid = dt_tid_per_man * total_män
        scen_tid_i_sek = scen_tid * 3600
        total_tid = scen_tid_i_sek + total_deepthroat_tid
        total_tid_h = round(total_tid / 3600, 2)
        min_per_kille = round((total_tid / 60) / total_män, 2) if total_män > 0 else 0

        st.info(f"Total tid (h): {total_tid_h} timmar\n\nMinuter per kille (inkl. deep throat): {min_per_kille} min")
        if total_tid_h > 18:
            st.warning("⚠️ Scenens totala tid överskrider 18 timmar!")

        submit = st.form_submit_button("Lägg till")

    if submit:
        from berakningar import process_lägg_till_rader
        df = process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                                     dp, dpp, dap, tpp, tap, tpa,
                                     komp, pappans, nils_v, nils_f,
                                     dt_tid_per_man, älskar, sover)
        spara_data(df)
        st.success("Rad(er) tillagda!")

        # Rensa formulärvärden
        for key in st.session_state.keys():
            if key.startswith("form_"):
                st.session_state[key] = 0 if "typ" not in key else "Scen"
        st.rerun()

import streamlit as st
import pandas as pd
from datetime import datetime
from berakningar import process_lägg_till_rader
from google.oauth2.service_account import Credentials
import gspread

# === Google Sheets Setup ===
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-5JSJpqBB0j7sm3cgEGZmnFoBL_oJDPMpLdleggL0HQ/edit?usp=drivesdk"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url(SPREADSHEET_URL)

def init_sheet():
    try:
        sheet = sh.worksheet("Data")
    except gspread.exceptions.WorksheetNotFound:
        sheet = sh.add_worksheet(title="Data", rows="1000", cols="30")
        sheet.append_row([
            "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
            "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner",
            "Nils vänner", "Nils familj", "Övriga män",
            "Älskar med", "Sover med", "Nils sex",
            "DT tid per man (sek)", "DT total tid (sek)",
            "Total tid (sek)", "Total tid (h)",
            "Prenumeranter", "Intäkt ($)",
            "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
            "Minuter per kille", "Scenens längd (h)"
        ])
    return sheet

def load_data():
    sheet = init_sheet()
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def save_data(df):
    sheet = init_sheet()
    sheet.clear()
    sheet.append_row(list(df.columns))
    rows = df.fillna("").astype(str).values.tolist()
    sheet.append_rows(rows)

def visa_inställningar(inst):
    st.sidebar.header("Inställningar")
    with st.sidebar.form("inst_form"):
        namn = st.text_input("Kvinnans namn", value=inst.get("Kvinnans namn", "Malin"))
        född = st.text_input("Födelsedatum (YYYY-MM-DD)", value=inst.get("Födelsedatum", "1984-03-26"))
        start = st.text_input("Startdatum", value=inst.get("Startdatum", "2014-03-26"))

        komp = st.number_input("Kompisar", min_value=0, value=int(inst.get("Kompisar", 40)))
        papp = st.number_input("Pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 20)))
        nv = st.number_input("Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 20)))
        nf = st.number_input("Nils familj", min_value=0, value=int(inst.get("Nils familj", 20)))

        submit = st.form_submit_button("Spara inställningar")

    if submit:
        blad = sh.worksheet("Inställningar")
        blad.update("A1:B8", [
            ["Kvinnans namn", namn],
            ["Födelsedatum", född],
            ["Startdatum", start],
            ["Kompisar", komp],
            ["Pappans vänner", papp],
            ["Nils vänner", nv],
            ["Nils familj", nf],
            ["Senast ändrad", datetime.today().strftime("%Y-%m-%d")]
        ])
        st.success("Inställningar uppdaterade!")

def läs_inställningar():
    try:
        blad = sh.worksheet("Inställningar")
    except gspread.exceptions.WorksheetNotFound:
        blad = sh.add_worksheet(title="Inställningar", rows="10", cols="2")
        blad.update("A1:B8", [
            ["Kvinnans namn", "Malin"],
            ["Födelsedatum", "1984-03-26"],
            ["Startdatum", "2014-03-26"],
            ["Kompisar", "40"],
            ["Pappans vänner", "20"],
            ["Nils vänner", "20"],
            ["Nils familj", "20"],
            ["Senast ändrad", datetime.today().strftime("%Y-%m-%d")]
        ])
    data = blad.get_all_values()
    return {rad[0]: rad[1] for rad in data if len(rad) >= 2}

# === UI för formulär ===
def scenformulär(df, inst):
    st.header("Lägg till scen eller vila")

    with st.form("formulär"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        dagar = st.number_input("Antal vilodagar", min_value=0, value=1, step=1)
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, value=14.0)

        ov = st.number_input("Övriga män", min_value=0, value=0)
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, value=0)
        enkel_anal = st.number_input("Enkel anal", min_value=0, value=0)
        dp = st.number_input("DP", min_value=0, value=0)
        dpp = st.number_input("DPP", min_value=0, value=0)
        dap = st.number_input("DAP", min_value=0, value=0)
        tpp = st.number_input("TPP", min_value=0, value=0)
        tap = st.number_input("TAP", min_value=0, value=0)
        tpa = st.number_input("TPA", min_value=0, value=0)

        komp = st.number_input("Kompisar", min_value=0, value=0)
        pappans = st.number_input("Pappans vänner", min_value=0, value=0)
        nils_v = st.number_input("Nils vänner", min_value=0, value=0)
        nils_f = st.number_input("Nils familj", min_value=0, value=0)

        dt_tid = st.number_input("DT tid per man (sek)", min_value=0, value=0)
        älskar = st.number_input("Antal älskar med", min_value=0, value=0)
        sover = st.number_input("Antal sover med", min_value=0, value=0)

        submit = st.form_submit_button("Lägg till")

    if submit:
        df = process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                                     dp, dpp, dap, tpp, tap, tpa,
                                     komp, pappans, nils_v, nils_f,
                                     dt_tid, älskar, sover)
        save_data(df)
        st.success("Rad tillagd!")

    st.subheader("Databas")
    st.dataframe(df)

# === MAIN ===
def main():
    st.set_page_config(page_title="Malin App", layout="wide")
    inst = läs_inställningar()
    visa_inställningar(inst)
    df = load_data()
    scenformulär(df, inst)

if __name__ == "__main__":
    main()
