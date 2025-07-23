import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Öppna kalkylarket
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

INST_COLUMNS = ["Inställning", "Värde", "Senast ändrad"]

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
            ["Nils familj", "20", datetime.now().strftime("%Y-%m-%d")],
            ["DT tid per man (sek)", "15", datetime.now().strftime("%Y-%m-%d")]
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
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    idag = datetime.now().strftime("%Y-%m-%d")
    if nyckel in df["Inställning"].values:
        idx = df[df["Inställning"] == nyckel].index[0]
        worksheet.update_cell(idx + 2, 2, str(värde))
        worksheet.update_cell(idx + 2, 3, idag)
    else:
        worksheet.append_row([nyckel, str(värde), idag])

# Initiera inställningar om de saknas
init_inställningar()
inst = läs_inställningar()

# Sidopanel
with st.sidebar:
    st.header("Inställningar")
    namn = st.text_input("Kvinnans namn", value=str(inst.get("Kvinnans namn", "")))
    född = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1984-03-26")))
    startdatum = st.date_input("Startdatum (första scen)", value=pd.to_datetime(inst.get("Startdatum", "2014-03-26")))

    spara_inställning("Kvinnans namn", namn)
    spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
    spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))

    st.divider()
    for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "DT tid per man (sek)"]:
        val = st.number_input(fält, value=float(inst.get(fält, 0)), min_value=0.0, step=1.0)
        spara_inställning(fält, val)
