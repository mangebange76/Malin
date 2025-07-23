import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample
import math

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
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "Älskar med", "Sover med", "Nils sex",
    "DT tid per man (sek)", "DT total tid (sek)", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Minuter per kille", "Scenens längd (h)"
]

INST_COLUMNS = ["Inställning", "Värde", "Senast ändrad"]

# Initiera blad
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

    if "form_data" not in st.session_state:
        st.session_state.form_data = {
            "Typ": "Scen",
            "DP": 0, "DPP": 0, "DAP": 0,
            "TPA": 0, "TPP": 0, "TAP": 0,
            "Enkel vaginal": 0, "Enkel anal": 0,
            "Kompisar": 0, "Pappans vänner": 0, "Nils vänner": 0, "Nils familj": 0,
            "Övriga män": 0,
            "Älskar med": 0, "Sover med": 0,
            "DT tid per man (sek)": 0,
            "Scenens längd (h)": 0,
            "Antal vilodagar": 1
        }

    with st.form("lägg_till_formulär"):
        f = st.session_state.form_data
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], index=["Scen", "Vila inspelningsplats", "Vilovecka hemma"].index(f["Typ"]))
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", min_value=1, step=1, value=f["Antal vilodagar"])
        f["Scenens längd (h)"] = st.number_input("Scenens längd", min_value=0.0, step=0.25, value=f["Scenens längd (h)"])
        f["Övriga män"] = st.number_input("Övriga män", min_value=0, step=1, value=f["Övriga män"])
        f["Enkel vaginal"] = st.number_input("Enkel vaginal", min_value=0, step=1, value=f["Enkel vaginal"])
        f["Enkel anal"] = st.number_input("Enkel anal", min_value=0, step=1, value=f["Enkel anal"])
        f["DP"] = st.number_input("DP", min_value=0, step=1, value=f["DP"])
        f["DPP"] = st.number_input("DPP", min_value=0, step=1, value=f["DPP"])
        f["DAP"] = st.number_input("DAP", min_value=0, step=1, value=f["DAP"])
        f["TPP"] = st.number_input("TPP", min_value=0, step=1, value=f["TPP"])
        f["TAP"] = st.number_input("TAP", min_value=0, step=1, value=f["TAP"])
        f["TPA"] = st.number_input("TPA", min_value=0, step=1, value=f["TPA"])
        f["Kompisar"] = st.number_input("Kompisar", min_value=0, max_value=int(inst.get("Kompisar", 999)), step=1, value=f["Kompisar"])
        f["Pappans vänner"] = st.number_input("Pappans vänner", min_value=0, max_value=int(inst.get("Pappans vänner", 999)), step=1, value=f["Pappans vänner"])
        f["Nils vänner"] = st.number_input("Nils vänner", min_value=0, max_value=int(inst.get("Nils vänner", 999)), step=1, value=f["Nils vänner"])
        f["Nils familj"] = st.number_input("Nils familj", min_value=0, max_value=int(inst.get("Nils familj", 999)), step=1, value=f["Nils familj"])
        f["DT tid per man (sek)"] = st.number_input("DT tid per man", min_value=0, step=1, value=f["DT tid per man (sek)"])
        f["Älskar med"] = st.number_input("Antal älskar med", min_value=0, step=1, value=f["Älskar med"])
        f["Sover med"] = st.number_input("Antal sover med", min_value=0, step=1, value=f["Sover med"])

        # Visa beräknad tid
        from berakningar import beräkna_tid_per_kille
        tid_min, total_h = beräkna_tid_per_kille(f)
        st.info(f"🕒 Varje kille får {tid_min:.2f} minuter inkl. deep throat")
        if total_h > 18:
            st.warning(f"⚠️ Total tid ({total_h:.2f} timmar) överskrider 18 timmar!")

        submit = st.form_submit_button("Lägg till")

    if submit:
        from berakningar import process_lägg_till_rader
        df = process_lägg_till_rader(df, inst, f)
        spara_data(df)

        # Nollställ fälten
        del st.session_state.form_data
        st.rerun()

import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# Autentisering och initiering
SHEET_URL = "https://docs.google.com/spreadsheets/d/1U7P_f57LqDvm_gBtzBjRWyTuTj-nQlSwgDnN36Yj4cU/edit#gid=0"
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SHEET_URL)
blad = sh.worksheet("Data")

# Standardinställningar
STANDARDINSTÄLLNINGAR = {
    "Startdatum": "2014-03-26",
    "Kvinnans namn": "Malin",
    "Födelsedatum": "1984-03-26",
    "Kompisar": 40,
    "Pappans vänner": 20,
    "Nils vänner": 20,
    "Nils familj": 10
}

def load_data():
    try:
        data = blad.get_all_records()
        return pd.DataFrame(data)
    except:
        blad.update([list(STANDARDINSTÄLLNINGAR.keys())])
        return pd.DataFrame(columns=list(STANDARDINSTÄLLNINGAR.keys()))

def spara_data(df):
    df_str = df.fillna("").astype(str)
    blad.update([df_str.columns.values.tolist()] + df_str.values.tolist())

def visa_inställningar(inst):
    with st.sidebar:
        st.header("Inställningar")
        for nyckel in ["Startdatum", "Kvinnans namn", "Födelsedatum", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            ny_värde = st.text_input(nyckel, str(inst.get(nyckel, "")), key=f"inst_{nyckel}")
            inst[nyckel] = ny_värde if nyckel in ["Startdatum", "Kvinnans namn", "Födelsedatum"] else int(ny_värde)
        if st.button("Spara inställningar"):
            instblad = sh.worksheet("Inställningar")
            instblad.update("A1", [[k, inst[k]] for k in inst])

def läs_inställningar():
    try:
        instblad = sh.worksheet("Inställningar")
        data = instblad.get_all_records()
        return {rad["Inställning"]: rad["Värde"] for rad in data}
    except:
        instblad = sh.add_worksheet(title="Inställningar", rows="100", cols="2")
        instblad.update("A1", [["Inställning", "Värde"]])
        for k, v in STANDARDINSTÄLLNINGAR.items():
            instblad.append_row([k, v])
        return STANDARDINSTÄLLNINGAR.copy()

def main():
    st.title("🎬 Scenplanering – Malin")

    inst = läs_inställningar()
    visa_inställningar(inst)

    df = load_data()
    from berakningar import process_lägg_till_rader
    from berakningar import beräkna_tid_per_kille
    scenformulär(df, inst)

    st.subheader("Alla scener och vilodagar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
