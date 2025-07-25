import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import random
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import dummy_beräkningar

# Autentisering
if "GOOGLE_CREDENTIALS" not in st.secrets:
    st.stop()

credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.authorize(credentials)

SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# Initiera blad
def initiera_blad():
    try:
        inst_sheet = sh.worksheet("Inställningar")
    except WorksheetNotFound:
        inst_sheet = sh.add_worksheet(title="Inställningar", rows="100", cols="5")
        inst_sheet.append_row(["Fält", "Värde"])
        inst_sheet.append_row(["Startdatum", str(datetime.today().date())])
        inst_sheet.append_row(["Födelsedatum", "1990-01-01"])
        inst_sheet.append_row(["Kvinnans namn", ""])
        inst_sheet.append_row(["Kompisar", 0])
        inst_sheet.append_row(["Pappans vänner", 0])
        inst_sheet.append_row(["Nils vänner", 0])
        inst_sheet.append_row(["Nils familj", 0])

    try:
        data_sheet = sh.worksheet("Data")
    except WorksheetNotFound:
        data_sheet = sh.add_worksheet(title="Data", rows="1000", cols="50")
        data_sheet.append_row(COLUMNS)

initiera_blad()

# Läs inställningar
def las_instaellningar():
    df = pd.DataFrame(sh.worksheet("Inställningar").get_all_records())
    df = df.set_index("Fält")["Värde"].to_dict()
    return df

# Läs databas
def las_data():
    df = pd.DataFrame(sh.worksheet("Data").get_all_records())
    return df

# Spara data
def spara_rader(rader):
    säkerställ_kolumner(rader)
    ark = sh.worksheet("Data")
    ark.append_rows(rader)

# Skapa nästa datum
def nästa_datum(df, inställningar):
    if df.empty:
        return pd.to_datetime(inställningar.get("Startdatum", datetime.today().date()))
    else:
        senaste = pd.to_datetime(df["Datum"].max())
        return senaste + timedelta(days=1)

# Skapa rad för vilodag
def skapa_vilarad(nytt_datum, inst):
    def slumpintervall(min_procent, max_procent, instvärde):
        return int(round(instvärde * random.uniform(min_procent, max_procent) / 100))

    rad = {
        "Datum": nytt_datum.strftime("%Y-%m-%d"),
        "Typ": "Vila inspelningsplats",
        "Antal vilodagar": 1,
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
        "Kompisar": slumpintervall(10, 60, int(inst.get("Kompisar", 0))),
        "Pappans vänner": slumpintervall(20, 70, int(inst.get("Pappans vänner", 0))),
        "Nils vänner": slumpintervall(10, 60, int(inst.get("Nils vänner", 0))),
        "Nils familj": slumpintervall(30, 80, int(inst.get("Nils familj", 0))),
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
        "Minuter per kille": 0
    }
    return [rad[col] for col in COLUMNS]

# Formulär: lägg till scen
def scenformulär():
    df = las_data()
    inst = las_instaellningar()
    nästa = nästa_datum(df, inst)

    with st.form("scenformulär", clear_on_submit=False):
        st.subheader("Lägg till scen")
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar (vid vila inspelningsplats)", min_value=1, max_value=30, value=1)
        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        submitted = st.form_submit_button("Lägg till")

    if submitted and bekräfta:
        if typ == "Vila inspelningsplats":
            rader = []
            for i in range(antal_vilodagar):
                datum = nästa + timedelta(days=i)
                rad = skapa_vilarad(datum, inst)
                rader.append(rad)
            spara_rader(rader)
            st.success(f"{len(rader)} vilodag(ar) tillagda.")
        else:
            st.warning("Endast 'Vila inspelningsplats' stöds just nu.")

# Inställningsformulär
def inställningar_form():
    inst = las_instaellningar()

    with st.form("instform"):
        st.subheader("Inställningar")
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", datetime.today())), min_value=datetime(1990,1,1).date())
        födelsedatum = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1990-01-01")), min_value=datetime(1970,1,1).date())
        namn = st.text_input("Kvinnans namn", value=inst.get("Kvinnans namn", ""))
        kompisar = st.number_input("Kompisar", min_value=0, value=int(inst.get("Kompisar", 0)))
        pappans = st.number_input("Pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 0)))
        nils_v = st.number_input("Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 0)))
        nils_f = st.number_input("Nils familj", min_value=0, value=int(inst.get("Nils familj", 0)))
        spara = st.form_submit_button("Spara inställningar")

    if spara:
        ark = sh.worksheet("Inställningar")
        nya = {
            "Startdatum": str(startdatum),
            "Födelsedatum": str(födelsedatum),
            "Kvinnans namn": namn,
            "Kompisar": kompisar,
            "Pappans vänner": pappans,
            "Nils vänner": nils_v,
            "Nils familj": nils_f
        }
        rows = [["Fält", "Värde"]] + [[k, v] for k, v in nya.items()]
        ark.clear()
        ark.append_rows(rows)
        st.success("Inställningar sparade.")

# Kör appen
def main():
    st.title("Malin produktionsapp")
    meny = st.sidebar.radio("Meny", ["Lägg till scen", "Inställningar"])

    if meny == "Inställningar":
        inställningar_form()
    else:
        scenformulär()

if __name__ == "__main__":
    main()
