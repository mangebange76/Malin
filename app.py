import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Malin App", layout="wide")

# Autentisering och Sheets-anslutning
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(credentials)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Initiera blad
def init_sheet(name, cols):
    try:
        sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows="1000", cols="50")
        ws.update("A1", [cols])

init_sheet("Data", [
    "Datum", "Scen/Vila", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "DT tid (sek)", "Älskar med", "Sover med",
    "Prenumeranter", "Prenumerationsintäkt (USD)",
    "Kvinnans lön", "Mäns lön", "Kompisars andel", "DT total tid (sek)",
    "Total tid (sek)", "Total tid (h)"
])
init_sheet("Inställningar", [["Inställning", "Värde", "Senast ändrad"]])
data_ws = sh.worksheet("Data")
inst_ws = sh.worksheet("Inställningar")

# Spara inställning i bladet
def spara_inställning(nyckel, värde):
    idag = datetime.now().strftime("%Y-%m-%d")
    celler = inst_ws.get_all_records()
    for ix, rad in enumerate(celler):
        if rad["Inställning"] == nyckel:
            inst_ws.update_cell(ix + 2, 2, str(värde))
            inst_ws.update_cell(ix + 2, 3, idag)
            return
    inst_ws.append_row([nyckel, str(värde), idag])

# Läs in inställningar som dict
def läs_inställningar():
    celler = inst_ws.get_all_records()
    inst = {}
    for rad in celler:
        key = rad["Inställning"]
        val = str(rad["Värde"]).replace(",", ".")
        try:
            inst[key] = float(val) if val.replace(".", "", 1).isdigit() else val
        except:
            inst[key] = val
    return inst

# Konvertera datum till datetime-objekt
def str_to_date(datumstr):
    return datetime.strptime(datumstr, "%Y-%m-%d")

# Hämta datum för senaste raden
def senaste_datum(df):
    if df.empty:
        return datetime.strptime(inst.get("Startdatum", "2014-03-26"), "%Y-%m-%d")
    return str_to_date(df["Datum"].iloc[-1])

def spara_data(df):
    worksheet = sh.worksheet("Data")
    df = df.fillna("").astype(str)
    existerande_kolumner = worksheet.row_values(1)
    nödvändiga_kolumner = [
        "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner",
        "Nils vänner", "Nils familj", "Övriga män", "DT tid (sek)", "Älskar med",
        "Sover med", "Nils sex", "Total tid (sek)", "DT total tid (sek)",
        "Total tid (h)", "Prenumeranter", "Intäkt (USD)", "Kvinnans lön (USD)",
        "Mäns lön (USD)", "Kompisar lön (USD)"
    ]

    if existerande_kolumner != nödvändiga_kolumner:
        worksheet.update("A1", [nödvändiga_kolumner])

    rows = df[nödvändiga_kolumner].values.tolist()
    worksheet.update("A2", rows)

def skapa_slumprad_vilodag(datum, inst, hemma=False, nils_sex=False):
    from random import randint, sample
    rad = {"Datum": datum, "Typ": "Vila hemma" if hemma else "Vila inspelning"}
    tot_kompisar = int(inst.get("Kompisar", 0))
    max_proc = 0.10 if hemma else 0.60
    max_antal = int(tot_kompisar * max_proc)
    rad["Kompisar"] = randint(0, max_antal) if max_antal > 0 else 0
    rad["Pappans vänner"] = randint(0, int(inst.get("Pappans vänner", 0) * max_proc)) if not hemma else 0
    rad["Nils vänner"] = randint(0, int(inst.get("Nils vänner", 0) * max_proc)) if not hemma else 0
    rad["Nils familj"] = randint(0, int(inst.get("Nils familj", 0) * max_proc)) if not hemma else 0
    rad["Övriga män"] = 0
    rad["DP"] = rad["DPP"] = rad["DAP"] = rad["TPA"] = rad["TPP"] = rad["TAP"] = 0
    rad["Enkel vaginal"] = rad["Enkel anal"] = 0
    rad["DT tid (sek)"] = 0
    rad["Älskar med"] = 8 if hemma else 12
    rad["Sover med"] = 0 if hemma else 1
    rad["Nils sex"] = 1 if nils_sex else 0
    return rad

def beräkna_tider(df, inst):
    rader = []
    for _, rad in df.iterrows():
        totalt_tid = 0
        paustid = 15  # sekunder
        dt_tid = int(rad["DT tid (sek)"])
        dt_vila = 2  # sek vila mellan varje
        dt_extra = 30 * ((int(rad["Kompisar"]) + int(rad["Pappans vänner"]) +
                          int(rad["Nils vänner"]) + int(rad["Nils familj"]) +
                          int(rad["Övriga män"])) // 10)
        dt_total = dt_tid * (int(rad["Kompisar"]) + int(rad["Pappans vänner"]) +
                             int(rad["Nils vänner"]) + int(rad["Nils familj"]) +
                             int(rad["Övriga män"])) + dt_vila * (
                             int(rad["Kompisar"]) + int(rad["Pappans vänner"]) +
                             int(rad["Nils vänner"]) + int(rad["Nils familj"]) +
                             int(rad["Övriga män"])) + dt_extra

        for kategori in ["DP", "DPP", "DAP"]:
            totalt_tid += (int(rad[kategori]) * 2 * 60) + (15 if int(rad[kategori]) > 0 else 0)

        for kategori in ["TPA", "TPP", "TAP"]:
            totalt_tid += (int(rad[kategori]) * 2 * 60) + (15 if int(rad[kategori]) > 0 else 0)

        for kategori in ["Enkel vaginal", "Enkel anal"]:
            totalt_tid += (int(rad[kategori]) * 2 * 60) + (15 if int(rad[kategori]) > 0 else 0)

        tid_per_man = float(inst.get("Tid per man (minuter)", 0))
        antal_män = sum([
            int(rad["Kompisar"]), int(rad["Pappans vänner"]),
            int(rad["Nils vänner"]), int(rad["Nils familj"]), int(rad["Övriga män"])
        ])
        totalt_tid += int(tid_per_man * antal_män * 60)

        älsk_tid = int(rad["Älskar med"]) * 15 * 60
        sov_tid = int(rad["Sover med"]) * 15 * 60
        totalt_tid += älsk_tid + sov_tid

        rad["Total tid (sek)"] = totalt_tid
        rad["DT total tid (sek)"] = dt_total
        rad["Total tid (h)"] = round((totalt_tid + dt_total) / 3600, 2)

        rader.append(rad)
    return pd.DataFrame(rader)

def beräkna_prenumeranter(df):
    resultat = []
    for _, rad in df.iterrows():
        score = (
            int(rad["DP"]) * 1 +
            int(rad["DPP"]) * 2 +
            int(rad["DAP"]) * 2 +
            int(rad["TPA"]) * 4 +
            int(rad["TPP"]) * 4 +
            int(rad["TAP"]) * 5 +
            int(rad["Enkel vaginal"]) * 0.5 +
            int(rad["Enkel anal"]) * 0.5
        )
        subs = int(score * 2)
        rad["Prenumeranter"] = subs
        rad["Intäkt (USD)"] = round(subs * 15, 2)
        rad["Kvinnans lön (USD)"] = 800
        tot_män = int(rad["Kompisar"]) + int(rad["Pappans vänner"]) + int(rad["Nils vänner"]) + int(rad["Nils familj"]) + int(rad["Övriga män"])
        rad["Mäns lön (USD)"] = 200 * (tot_män - int(rad["Kompisar"]))
        kompisar_totalt = int(rad["Kompisar"])
        kvar = rad["Intäkt (USD)"] - rad["Kvinnans lön (USD)"] - rad["Mäns lön (USD)"]
        rad["Kompisar lön (USD)"] = round(kvar / kompisar_totalt, 2) if kompisar_totalt > 0 else 0
        resultat.append(rad)
    return pd.DataFrame(resultat)

def uppdatera_statistik(df, inst):
    st.subheader("📊 Statistik")
    totalt_antal = 0
    totalt_rader = len(df)
    totala_män = 0
    for _, rad in df.iterrows():
        totala_män += sum([
            int(rad["Kompisar"]), int(rad["Pappans vänner"]),
            int(rad["Nils vänner"]), int(rad["Nils familj"]), int(rad["Övriga män"])
        ])
    st.write(f"Totalt antal rader (scener/vilodagar): {totalt_rader}")
    st.write(f"Totalt antal män (inkl alla grupper): {totala_män}")
    st.write(f"Snitt per rad: {round(totala_män / totalt_rader, 2)}")

    for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        totalt = df[grupp].astype(int).sum()
        inst_total = int(inst.get(grupp, 1))
        snitt = round(totalt / inst_total, 2) if inst_total else 0
        st.write(f"{grupp}: totalt {totalt} / {inst_total} → snitt per person: {snitt}")

    # Älskar med
    älskar_sum = df["Älskar med"].astype(int).sum()
    total_personer = sum([int(inst.get(grupp, 0)) for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]])
    älskar_snitt = round(älskar_sum / total_personer, 2) if total_personer else 0
    st.write(f"Antal gånger älskat: {älskar_sum} → snitt per person: {älskar_snitt}")

    # Sover med
    sover_sum = df["Sover med"].astype(int).sum()
    familj_total = int(inst.get("Nils familj", 1))
    sover_snitt = round(sover_sum / familj_total, 2) if familj_total else 0
    st.write(f"Antal gånger sovit med: {sover_sum} → snitt per familjemedlem: {sover_snitt}")

    # Kvinnans ålder
    namn = inst.get("Kvinnans namn", "N/A")
    född = inst.get("Kvinnans födelsedatum", "1900-01-01")
    try:
        senaste_datum = pd.to_datetime(df["Datum"].iloc[-1])
        födelsedatum = pd.to_datetime(född)
        ålder = (senaste_datum - födelsedatum).days // 365
        st.write(f"{namn} är {ålder} år gammal vid senaste scenen.")
    except:
        st.warning("Kunde inte beräkna ålder.")

    # Sammanfattning intäkter
    total_intäkt = df["Intäkt (USD)"].astype(float).sum()
    total_kvinna = df["Kvinnans lön (USD)"].astype(float).sum()
    total_män = df["Mäns lön (USD)"].astype(float).sum()
    total_kompisar = df["Kompisar lön (USD)"].astype(float).sum()
    st.write(f"Total intäkt: {total_intäkt} USD")
    st.write(f"Kvinnans lön totalt: {total_kvinna} USD")
    st.write(f"Mäns lön totalt: {total_män} USD")
    st.write(f"Kompisar lön totalt: {total_kompisar} USD")

def huvudvy(df, inst):
    st.subheader("📅 Skapa ny scen eller vila")
    med_scen = st.radio("Vad vill du lägga till?", ["Ny scen", "Vila på inspelningsplats", "Vilovecka hemma"])

    if med_scen == "Ny scen":
        antal = st.number_input("Antal övriga män", 0, 999, step=1)
        dp = st.number_input("DP", 0, 999)
        dpp = st.number_input("DPP", 0, 999)
        dap = st.number_input("DAP", 0, 999)
        tpa = st.number_input("TPA", 0, 999)
        tpp = st.number_input("TPP", 0, 999)
        tap = st.number_input("TAP", 0, 999)
        enkel_v = st.number_input("Enkel vaginal", 0, 999)
        enkel_a = st.number_input("Enkel anal", 0, 999)

        grupper = {}
        for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            max_val = int(inst.get(grupp, 0))
            grupper[grupp] = st.number_input(f"{grupp} (max {max_val})", 0, max_val)

        dt_tid = st.number_input("Deep throat per man (sek)", 0, 600, value=10)
        älskar = st.number_input("Antal älskar med", 0, 50, value=12)
        sover = st.number_input("Antal sover med", 0, 20, value=1)

        if st.button("Lägg till scen"):
            ny_rad = {
                "Datum": nästa_datum(df, 1),
                "Typ": "Scen",
                "DP": dp, "DPP": dpp, "DAP": dap, "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_v, "Enkel anal": enkel_a,
                "Kompisar": grupper["Kompisar"],
                "Pappans vänner": grupper["Pappans vänner"],
                "Nils vänner": grupper["Nils vänner"],
                "Nils familj": grupper["Nils familj"],
                "Övriga män": antal,
                "DT tid per man (sek)": dt_tid,
                "Älskar med": älskar,
                "Sover med": sover,
                "Nils sex": 0
            }
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            spara_data(df)
            st.rerun()

    elif med_scen == "Vila på inspelningsplats":
        dagar = st.number_input("Antal vilodagar", 1, 30, value=2)
        maxprocent = 0.6
        for _ in range(dagar):
            ny_rad = generera_vilarad(df, inst, plats="inspelningsplats", max_procent=maxprocent)
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(df)
        st.rerun()

    elif med_scen == "Vilovecka hemma":
        # Max två gånger sex med Nils
        antal_nils = random.sample(range(7), min(2, 7))
        for dag in range(7):
            ny_rad = generera_vilarad(df, inst, plats="hemma", max_procent=0.1)
            ny_rad["Datum"] = nästa_datum(df, 1)
            ny_rad["Älskar med"] *= 7
            ny_rad["Sover med"] = 0
            ny_rad["Nils sex"] = 1 if dag in antal_nils else 0
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(df)
        st.rerun()

def main():
    df = ladda_data()
    inst = läs_inställningar()
    df = säkerställ_kolumner(df)
    df = uppdatera_tid_och_intäkt(df, inst)
    huvudvy(df, inst)
    uppdatera_statistik(df, inst)

if __name__ == "__main__":
    main()
