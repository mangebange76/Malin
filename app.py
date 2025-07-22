import streamlit as st
import pandas as pd
import datetime
from google.oauth2.service_account import Credentials
import gspread
import time

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Hjälpfunktion: initiera blad med kolumner
def init_sheet(name, cols):
    try:
        worksheet = sh.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=name, rows="1000", cols="50")
    existing = worksheet.get_all_values()
    if not existing:
        worksheet.update("A1", [cols])

# Kolumner till databladet
SCENE_COLS = [
    "Datum", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Vaginal (enkel)", "Anal (enkel)", "DT tid per man (sek)",
    "Pappans vänner", "Kompisar", "Nils vänner", "Nils familj",
    "Älskar med", "Sover med", "Vilodagar", "Kommentar"
]

# Initiera blad
init_sheet("Scener", SCENE_COLS)
init_sheet("Inställningar", ["Inställning", "Värde", "Senast ändrad"])
init_sheet("Data", ["Datum", "Typ", "Pappans vänner", "Kompisar", "Nils vänner", "Nils familj"])

# Läs inställningar från Google Sheets
def läs_inställningar():
    sheet = sh.worksheet("Inställningar")
    data = sheet.get_all_records()
    inst = {
        rad["Inställning"]: float(str(rad["Värde"]).replace(",", "").replace(".", "", 1))
        if str(rad["Värde"]).replace(",", "").replace(".", "", 1).isdigit()
        else str(rad["Värde"])
        for rad in data
    }
    return inst

# Skriv inställning till Google Sheets
def spara_inställning(inställning, värde):
    sheet = sh.worksheet("Inställningar")
    data = sheet.get_all_records()
    idag = datetime.datetime.today().strftime("%Y-%m-%d")
    uppdaterad = False
    for ix, rad in enumerate(data):
        if rad["Inställning"] == inställning:
            sheet.update_cell(ix + 2, 2, värde)
            sheet.update_cell(ix + 2, 3, idag)
            uppdaterad = True
            break
    if not uppdaterad:
        sheet.append_row([inställning, värde, idag])

# Räkna ut ålder från födelsedatum till ett visst datum
def beräkna_ålder(födelsedatum: str, till_datum: str) -> int:
    födelsedatum = datetime.datetime.strptime(födelsedatum, "%Y-%m-%d").date()
    till_datum = datetime.datetime.strptime(till_datum, "%Y-%m-%d").date()
    år = till_datum.year - födelsedatum.year
    if (till_datum.month, till_datum.day) < (födelsedatum.month, födelsedatum.day):
        år -= 1
    return år

# Hämta datumet på senaste raden
def hämta_senaste_datum():
    df = pd.DataFrame(sh.worksheet("Scener").get_all_records())
    if not df.empty and "Datum" in df.columns:
        return pd.to_datetime(df["Datum"]).max().date()
    else:
        return datetime.datetime.strptime(inställningar.get("Startdatum", "2014-03-26"), "%Y-%m-%d").date()

# Säkerställ att ett blad har rätt kolumner
def init_sheet(name, cols):
    try:
        worksheet = sh.worksheet(name)
        befintliga = worksheet.row_values(1)
        if befintliga != cols:
            worksheet.clear()
            worksheet.append_row(cols)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=name, rows="1000", cols=str(len(cols)))
        worksheet.append_row(cols)

# Ladda data från Google Sheets till DataFrame
def ladda_data(namn):
    try:
        data = sh.worksheet(namn).get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# Spara DataFrame till Google Sheets
def spara_data(namn, df):
    df = df.copy()
    df = df.fillna("")
    df = df.astype(str)
    worksheet = sh.worksheet(namn)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# Initiera alla blad
init_sheet("Inställningar", ["Inställning", "Värde", "Senast ändrad"])
init_sheet("Scener", [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal", "Pappans vänner", "Kompisar", "Nils vänner", "Nils familj",
    "Älskar med", "Sover med", "DT tid per man (sek)", "DT total tid (sek)",
    "Total aktiv tid (sek)", "Vilotid (sek)", "Summa tid (sek)", "Tid per man (min)",
    "Prenumeranter", "Intäkt (USD)", "Till kvinna (USD)", "Till män (USD)", "Till kompisar (USD)",
    "Aktiekurs (USD)", "Vilodagar"
])

# Läs inställningar och konvertera värden
def läs_inställningar():
    df = ladda_data("Inställningar")
    inst = {}
    for rad in df.to_dict("records"):
        värde = str(rad["Värde"]).replace(",", ".")
        try:
            värde = float(värde)
        except:
            pass
        inst[rad["Inställning"]] = värde
    return inst

# Spara uppdaterade inställningar
def spara_inställning(namn, värde):
    df = ladda_data("Inställningar")
    idag = datetime.now().strftime("%Y-%m-%d")
    hittad = False
    for i, rad in df.iterrows():
        if rad["Inställning"] == namn:
            df.at[i, "Värde"] = värde
            df.at[i, "Senast ändrad"] = idag
            hittad = True
    if not hittad:
        df = pd.concat([df, pd.DataFrame([{"Inställning": namn, "Värde": värde, "Senast ändrad": idag}])], ignore_index=True)
    spara_data("Inställningar", df)

# Funktion för att beräkna ålder
def beräkna_ålder(födelsedatum, referensdatum):
    född = datetime.strptime(födelsedatum, "%Y-%m-%d")
    nu = datetime.strptime(referensdatum, "%Y-%m-%d")
    return nu.year - född.year - ((nu.month, nu.day) < (född.month, född.day))

# Slumpa antal från en grupp baserat på procent
def slumpa_antal(max_antal, procent):
    return random.randint(0, int(max_antal * procent))

# Räkna prenumeranter utifrån scenens data
def räkna_prenumeranter(rad, vikter):
    total = (
        rad["DP"] * vikter["DP"] +
        rad["DPP"] * vikter["DPP"] +
        rad["DAP"] * vikter["DAP"] +
        rad["TPA"] * vikter["TPA"] +
        rad["TPP"] * vikter["TPP"] +
        rad["TAP"] * vikter["TAP"] +
        rad["Enkel vaginal"] * vikter["Enkel vaginal"] +
        rad["Enkel anal"] * vikter["Enkel anal"]
    )
    return int(total)

def main():
    st.title("🎬 Malin – Inspelningsplan och statistik")

    inst = läs_inställningar()
    blad = "Data"
    df = ladda_data(blad)

    # Sidopanel – inställningar
    with st.sidebar:
        st.header("⚙️ Inställningar")
        namn = st.text_input("Kvinnans namn", inst.get("Kvinnans namn", "Malin"))
        född = st.text_input("Födelsedatum (ÅÅÅÅ-MM-DD)", inst.get("Födelsedatum", "1984-03-26"))
        startdatum = st.text_input("Startdatum första scen (ÅÅÅÅ-MM-DD)", inst.get("Startdatum", "2014-03-26"))

        spara_inställning("Kvinnans namn", namn)
        spara_inställning("Födelsedatum", född)
        spara_inställning("Startdatum", startdatum)

        st.divider()
        for kategori in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            värde = st.number_input(f"Totalt antal: {kategori}", min_value=0, value=int(inst.get(kategori, 0)), step=1)
            spara_inställning(kategori, värde)

        st.divider()
        st.subheader("📈 Prenumerant-vikter")
        for fält in ["DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Enkel vaginal", "Enkel anal"]:
            v = st.number_input(f"{fält}", min_value=0.0, value=float(inst.get(fält, 1.0)))
            spara_inställning(fält, v)

    # Huvudvy – statistik
    if not df.empty:
        senaste_datum = df["Datum"].max()
        ålder = beräkna_ålder(född, senaste_datum)
        st.subheader(f"{namn}, {ålder} år (senaste inspelning: {senaste_datum})")

        st.write("📊 Statistik och sammanställning kommer i nästa version.")

    # Funktioner som lägg till scen, vilodagar, statistik etc. integreras i nästa steg.

if __name__ == "__main__":
    main()
