import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS
import random

# Autentisering och initiering av kalkylark
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# Säkerställ ark
def säkerställ_ark():
    try:
        sh.worksheet("Data")
    except:
        sh.add_worksheet(title="Data", rows="1000", cols="50")
        sh.worksheet("Data").append_row(COLUMNS)

    try:
        ws = sh.worksheet("Inställningar")
        if ws.row_count < 2 or ws.cell(1, 1).value != "Fält":
            raise Exception("Felaktig struktur")
    except:
        sh.add_worksheet(title="Inställningar", rows="100", cols="2")
        inst = sh.worksheet("Inställningar")
        inst.update("A1:B8", [
            ["Fält", "Värde"],
            ["Startdatum", datetime.today().strftime("%Y-%m-%d")],
            ["Födelsedatum", "2000-01-01"],
            ["Kvinnans namn", "Anna"],
            ["Kompisar", "20"],
            ["Pappans vänner", "15"],
            ["Nils vänner", "10"],
            ["Nils familj", "5"],
        ])

säkerställ_ark()

# Läs inställningar
def läs_inställningar():
    ws = sh.worksheet("Inställningar")
    df = pd.DataFrame(ws.get_all_records())
    return {rad["Fält"]: rad["Värde"] for _, rad in df.iterrows()}

inst = läs_inställningar()

# Läs data
def läs_data():
    data_ws = sh.worksheet("Data")
    df = pd.DataFrame(data_ws.get_all_records())
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    return df[COLUMNS] if all(col in df.columns for col in COLUMNS) else pd.DataFrame(columns=COLUMNS)

# Nästa datum
def nästa_datum(df):
    if df.empty:
        return datetime.strptime(inst["Startdatum"], "%Y-%m-%d")
    senaste = max(pd.to_datetime(df["Datum"]))
    return senaste + timedelta(days=1)

# Slumpfunktion
def slumpa_procentsats(maxvärde, minp, maxp):
    procent = random.randint(minp, maxp)
    return round((int(maxvärde) * procent) / 100)

# App
st.title("Malin-produktionsapp")
val = st.radio("Välj läge", ["Lägg till scen", "Inställningar"])

# Inställningar
if val == "Inställningar":
    with st.form("instform"):
        startdatum = st.date_input("Startdatum", value=datetime.today(), min_value=datetime(1990, 1, 1))
        födelsedatum = st.date_input("Födelsedatum", value=datetime(2000, 1, 1), min_value=datetime(1970, 1, 1))
        namn = st.text_input("Kvinnans namn", value=inst.get("Kvinnans namn", "Anna"))
        kompisar = st.number_input("Kompisar", min_value=0, value=int(inst.get("Kompisar", 20)))
        pappans = st.number_input("Pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 15)))
        nils = st.number_input("Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 10)))
        familj = st.number_input("Nils familj", min_value=0, value=int(inst.get("Nils familj", 5)))
        submit = st.form_submit_button("Spara inställningar")

        if submit:
            nydata = [
                ["Fält", "Värde"],
                ["Startdatum", startdatum.strftime("%Y-%m-%d")],
                ["Födelsedatum", födelsedatum.strftime("%Y-%m-%d")],
                ["Kvinnans namn", namn],
                ["Kompisar", str(kompisar)],
                ["Pappans vänner", str(pappans)],
                ["Nils vänner", str(nils)],
                ["Nils familj", str(familj)],
            ]
            ws = sh.worksheet("Inställningar")
            ws.clear()
            ws.update("A1", nydata)
            st.success("Inställningar sparade.")

# Lägg till scen
if val == "Lägg till scen":
    df = läs_data()
    med st.form("scenformulär", clear_on_submit=False):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=1, value=1 if typ == "Vila inspelningsplats" else 0)
        bekräfta = st.checkbox("Bekräfta att du vill lägga till")

        skicka = st.form_submit_button("Lägg till")

        if skicka and bekräfta and typ == "Vila inspelningsplats":
            nya_rader = []
            datum = nästa_datum(df)

            for i in range(int(antal_vilodagar)):
                rad = {
                    "Datum": (datum + timedelta(days=i)).strftime("%Y-%m-%d"),
                    "Typ": typ,
                    "Antal vilodagar": antal_vilodagar,
                    "Nya män": 0,
                    "Enkel vaginal": 0,
                    "Enkel anal": 0,
                    "DP": 0,
                    "DPP": 0,
                    "DAP": 0,
                    "TPP": 0,
                    "TPA": 0,
                    "TAP": 0,
                    "Tid enkel": 0,
                    "Tid dubbel": 0,
                    "Tid trippel": 0,
                    "Vila": 0,
                    "Kompisar": slumpa_procentsats(inst["Kompisar"], 10, 60),
                    "Pappans vänner": slumpa_procentsats(inst["Pappans vänner"], 20, 70),
                    "Nils vänner": slumpa_procentsats(inst["Nils vänner"], 10, 60),
                    "Nils familj": slumpa_procentsats(inst["Nils familj"], 30, 80),
                    "DT tid per man": 0,
                    "Antal varv": 0,
                    "Älskar med": 12,
                    "Sover med": 1,
                    "Nils sex": 0,
                    "Prenumeranter": 0,
                    "Intäkt ($)": 0,
                    "Kvinnans lön ($)": 0,
                    "Mäns lön ($)": 0,
                    "Kompisars lön ($)": 0,
                    "DT total tid (sek)": 0,
                    "Total tid (sek)": 0,
                    "Total tid (h)": 0,
                    "Minuter per kille": 0,
                }
                nya_rader.append([rad[k] for k in COLUMNS])

            # Lägg till i databladet
            ws = sh.worksheet("Data")
            ws.append_rows(nya_rader, value_input_option="USER_ENTERED")
            st.success(f"{len(nya_rader)} vilodag(ar) tillagda.")
