import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import dummy_beräkningar
import random

# Autentisering
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SHEET_URL)

def hämta_blad(namn):
    try:
        return sh.worksheet(namn)
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=namn, rows="1000", cols="50")

blad_data = hämta_blad("Data")
blad_inst = hämta_blad("Inställningar")

def skapa_inställningarblad():
    rubriker = ["Fält", "Värde"]
    standard = [
        ["Startdatum", datetime.date.today().isoformat()],
        ["Kvinnans namn", ""],
        ["Födelsedatum", "1990-01-01"],
        ["Kompisar", 0],
        ["Pappans vänner", 0],
        ["Nils vänner", 0],
        ["Nils familj", 0]
    ]
    blad_inst.update("A1:B1", [rubriker])
    blad_inst.update("A2:B8", standard)

def hämta_inställningar():
    try:
        df = pd.DataFrame(blad_inst.get_all_records())
        df = df.set_index("Fält")["Värde"].to_dict()
        return df
    except Exception as e:
        st.warning(f"Kunde inte läsa inställningar: {e}")
        skapa_inställningarblad()
        return hämta_inställningar()

def spara_inställningar(data):
    rows = [[k, v] for k, v in data.items()]
    blad_inst.update("A2", rows)

def initiera_datablad():
    if blad_data.row_count == 0 or blad_data.cell(1, 1).value != COLUMNS[0]:
        blad_data.update("A1", [COLUMNS])

def hämta_data():
    data = blad_data.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df = säkerställ_kolumner(df)
    return df

def spara_rad(rad):
    try:
        säkerställ_kolumner(pd.DataFrame([rad]))
        blad_data.append_row(list(rad))
    except Exception as e:
        st.error(f"Fel vid sparning: {e}")

def bestäm_nästa_datum(df, startdatum):
    if df.empty:
        return startdatum
    senaste = pd.to_datetime(df["Datum"].iloc[-1])
    return (senaste + pd.Timedelta(days=1)).date()

def slumpa_andel(max_värde, min_procent, max_procent):
    procent = random.randint(min_procent, max_procent)
    return round(int(max_värde) * procent / 100)

def scenformulär(df, inst):
    with st.form("scenformulär", clear_on_submit=False):
        st.subheader("Lägg till scen")
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=1, max_value=31, value=1) if typ == "Vila inspelningsplats" else 0

        nästa_datum = bestäm_nästa_datum(df, pd.to_datetime(inst["Startdatum"]).date())

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        if st.form_submit_button("Lägg till rad") and bekräfta:
            rader = []

            if typ == "Vila inspelningsplats":
                for i in range(int(antal_vilodagar)):
                    datum = (nästa_datum + datetime.timedelta(days=i)).isoformat()
                    rad = {
                        "Datum": datum,
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
                        "Kompisar": slumpa_andel(inst["Kompisar"], 10, 60),
                        "Pappans vänner": slumpa_andel(inst["Pappans vänner"], 20, 70),
                        "Nils vänner": slumpa_andel(inst["Nils vänner"], 10, 60),
                        "Nils familj": slumpa_andel(inst["Nils familj"], 30, 80),
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
                    rader.append(rad)

                for rad in rader:
                    spara_rad(rad)
                st.success(f"{len(rader)} vilodag(ar) sparade.")
            else:
                st.warning("Endast 'Vila inspelningsplats' är aktivt just nu.")

def inställningsformulär(inst):
    with st.form("instform"):
        st.subheader("Inställningar")
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", datetime.date.today())), min_value=datetime.date(1990, 1, 1))
        namn = st.text_input("Kvinnans namn", value=inst.get("Kvinnans namn", ""))
        födelsedatum = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1990-01-01")), min_value=datetime.date(1970, 1, 1))
        kompisar = st.number_input("Kompisar", min_value=0, value=int(inst.get("Kompisar", 0)))
        pvänner = st.number_input("Pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 0)))
        nvänner = st.number_input("Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 0)))
        nfamilj = st.number_input("Nils familj", min_value=0, value=int(inst.get("Nils familj", 0)))

        if st.form_submit_button("Spara inställningar"):
            nydata = {
                "Startdatum": startdatum.isoformat(),
                "Kvinnans namn": namn,
                "Födelsedatum": födelsedatum.isoformat(),
                "Kompisar": kompisar,
                "Pappans vänner": pvänner,
                "Nils vänner": nvänner,
                "Nils familj": nfamilj
            }
            spara_inställningar(nydata)
            st.success("Inställningar sparade.")

def main():
    st.title("Malin-produktionsapp")
    initiera_datablad()
    inst = hämta_inställningar()
    df = hämta_data()

    menyval = st.sidebar.radio("Meny", ["Lägg till scen", "Inställningar"])
    if menyval == "Lägg till scen":
        scenformulär(df, inst)
    elif menyval == "Inställningar":
        inställningsformulär(inst)

if __name__ == "__main__":
    main()
