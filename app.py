import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample, randint
from berakningar import process_lägg_till_rader

# Autentisering och Google Sheets-koppling
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumnnamn
DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "Älskar med", "Sover med", "Nils sex",
    "DT tid per man (sek)", "DT total tid (sek)",
    "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Minuter per kille", "Scenens längd (h)"
]

INST_COLUMNS = ["Inställning", "Värde", "Senast ändrad"]

# Initiera datablad
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

# Initiera inställningar
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

# Läs inställningar från Google Sheets
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

# Spara enskild inställning
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

# Säkerställ att alla kolumner finns
def säkerställ_kolumner(df):
    for kolumn in DATA_COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = ""
    return df[DATA_COLUMNS]

# Spara data till Google Sheets
def spara_data(df):
    df = df.fillna("").astype(str)
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update("A1", [df.columns.tolist()] + df.values.tolist())

# Ladda data från Google Sheets
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

from berakningar import process_lägg_till_rader  # Importerar beräkningslogik

def scenformulär(df, inst):
    st.subheader("📋 Lägg till scen eller vila")

    with st.form("lägg_till"):
        kolumner = [
            ("Antal vilodagar", "vilodagar", 1, 1),
            ("Scenens längd (h)", "scen_tid", 14.0, 0.25),
            ("Övriga män", "ov", 0, 1),
            ("Enkel vaginal", "enkel_vag", 0, 1),
            ("Enkel anal", "enkel_anal", 0, 1),
            ("DP", "dp", 0, 1),
            ("DPP", "dpp", 0, 1),
            ("DAP", "dap", 0, 1),
            ("TPP", "tpp", 0, 1),
            ("TAP", "tap", 0, 1),
            ("TPA", "tpa", 0, 1),
            ("Kompisar", "komp", 0, 1, int(inst.get("Kompisar", 999))),
            ("Pappans vänner", "pappans", 0, 1, int(inst.get("Pappans vänner", 999))),
            ("Nils vänner", "nils_v", 0, 1, int(inst.get("Nils vänner", 999))),
            ("Nils familj", "nils_f", 0, 1, int(inst.get("Nils familj", 999))),
            ("DT tid per man (sek)", "dt_tid_per_man", 0, 1),
            ("Antal älskar med", "alskar", 0, 1),
            ("Antal sover med", "sover", 0, 1),
        ]

        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")

        # Skapa formulärfält dynamiskt med keys
        for namn, key, min_v, step, *max_v in kolumner:
            kwargs = {"min_value": min_v, "step": step, "key": key}
            if max_v:
                kwargs["max_value"] = max_v[0]
            st.number_input(namn, **kwargs)

        submit = st.form_submit_button("✅ Lägg till rad")

    if submit:
        värden = {key: st.session_state[key] for _, key, *_ in kolumner}
        värden["typ"] = typ

        df = process_lägg_till_rader(df, inst, värden)
        spara_data(df)

        # Återställ formulärfält
        for _, key, *_ in kolumner:
            st.session_state[key] = 0
        st.session_state["scen_tid"] = 14.0
        st.session_state["vilodagar"] = 1
        st.experimental_rerun()

# Visa befintlig data i tabell
def visa_data(df):
    st.subheader("📊 Samtliga scener och vilodagar")
    if df.empty:
        st.info("Ingen data tillgänglig ännu.")
    else:
        st.dataframe(df, use_container_width=True)

# Visa och redigera inställningar i sidopanel
def visa_inställningar(inst):
    with st.sidebar:
        st.header("⚙️ Inställningar")
        with st.form("inst_form"):
            namn = st.text_input("Kvinnans namn", value=str(inst.get("Kvinnans namn", "")))
            född = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1984-03-26")))
            startdatum = st.date_input("Startdatum (första scen)", value=pd.to_datetime(inst.get("Startdatum", "2014-03-26")))

            inst_inputs = {}
            for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
                inst_inputs[fält] = st.number_input(fält, value=float(inst.get(fält, 0)), min_value=0.0, step=1.0)

            spara = st.form_submit_button("💾 Spara inställningar")

        if spara:
            spara_inställning("Kvinnans namn", namn)
            spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
            spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))
            for nyckel, värde in inst_inputs.items():
                spara_inställning(nyckel, värde)
            st.success("Inställningar sparade!")

def main():
    st.set_page_config(page_title="Malin Filmproduktion", layout="wide")
    st.title("🎬 Malin Filmproduktion")

    # Initiera blad & ladda inställningar
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()
    inst = läs_inställningar()
    df = ladda_data()

    # Visa sidopanel
    visa_inställningar(inst)

    # Formulär för att lägga till scen/vila
    df = scenformulär(df, inst)

    # Visa befintlig data
    visa_data(df)

if __name__ == "__main__":
    main()
