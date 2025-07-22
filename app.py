import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import random

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# URL till Google Sheets
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Funktion för att initiera blad med kolumner
def init_sheet(name, cols):
    try:
        worksheet = sh.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=name, rows="1000", cols="50")
        worksheet.update("A1", [cols])
    else:
        data = worksheet.get_all_records()
        if not data:
            worksheet.update("A1", [cols])
        else:
            current_cols = worksheet.row_values(1)
            if current_cols != cols:
                all_data = worksheet.get_all_values()
                updated_data = [cols] + all_data[1:] if len(all_data) > 1 else [cols]
                worksheet.update("A1", updated_data)

# Funktion för att läsa inställningar
def läs_inställningar():
    try:
        inst_blad = sh.worksheet("Inställningar")
    except gspread.exceptions.WorksheetNotFound:
        inst_blad = sh.add_worksheet(title="Inställningar", rows="100", cols="5")
        inst_blad.update("A1", [["Inställning", "Värde", "Senast ändrad"]])
    data = inst_blad.get_all_records()
    inst = {
        rad["Inställning"]: float(str(rad["Värde"]).replace(",", "."))
        if str(rad["Värde"]).replace(",", "").replace(".", "", 1).isdigit()
        else str(rad["Värde"])
        for rad in data
    }
    return inst

# Funktion för att spara inställning
def spara_inställning(namn, värde):
    inst_blad = sh.worksheet("Inställningar")
    data = inst_blad.get_all_values()
    inst_dict = {rad[0]: i for i, rad in enumerate(data)}
    idag = datetime.now().strftime("%Y-%m-%d")
    str_värde = str(värde).replace(".", ",") if isinstance(värde, float) else str(värde)
    if namn in inst_dict:
        rad = inst_dict[namn] + 1
        inst_blad.update(f"B{rad}", str_värde)
        inst_blad.update(f"C{rad}", idag)
    else:
        inst_blad.append_row([namn, str_värde, idag])

# Funktion för att initiera databladet
def initiera_datablad():
    kolumner = [
        "Datum", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vaginal", "Enkel anal",
        "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
        "DT tid per man (sek)", "DT total tid (sek)",
        "Antal älskar med", "Antal sover med",
        "Pris per prenumeration (USD)", "Prenumeranter denna scen",
        "Totala prenumeranter", "Intäkt bolag", "Lön kvinna", "Lön män",
        "Lön kompisar", "Aktiekurs", "Typ", "Nils sex", "Summa tid (sek)", "Tid per man (min)"
    ]
    init_sheet("Data", kolumner)

# Funktion för att hämta DataFrame från Google Sheets
def hämta_df():
    try:
        df = pd.DataFrame(sh.worksheet("Data").get_all_records())
        return df
    except:
        return pd.DataFrame()

# Funktion för att uppdatera DataFrame i Google Sheets
def spara_df(df):
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update([df.columns.tolist()] + df.fillna("").astype(str).values.tolist())

# Funktion för att räkna ut prenumeranter för en scen
def beräkna_prenumeranter(rad, inst):
    viktning = {
        "DP": inst.get("Vikt DP", 1),
        "DPP": inst.get("Vikt DPP", 2),
        "DAP": inst.get("Vikt DAP", 2),
        "TPA": inst.get("Vikt TPA", 3),
        "TPP": inst.get("Vikt TPP", 3),
        "TAP": inst.get("Vikt TAP", 4),
        "Enkel vaginal": inst.get("Vikt enkel vaginal", 0.5),
        "Enkel anal": inst.get("Vikt enkel anal", 0.5)
    }
    poäng = sum(rad.get(k, 0) * viktning.get(k, 1) for k in viktning)
    return int(poäng * inst.get("Prenumeranter per poäng", 1))

# Funktion för att uppdatera aktiekurs baserat på prenumeranter
def uppdatera_aktiekurs(df, inst):
    startkurs = float(inst.get("Startkurs", 1.0))
    aktier = float(inst.get("Antal aktier", 100000))
    df = df.copy()
    df["Totala prenumeranter"] = df["Prenumeranter denna scen"].rolling(30, min_periods=1).sum()
    df["Aktiekurs"] = df["Totala prenumeranter"] * 15 / aktier
    df["Aktiekurs"] = df["Aktiekurs"].round(2)
    return df

# Funktion för att beräkna intäkter och löner
def beräkna_ekonomi(rad, inst, antal_kompisar):
    pren = rad.get("Prenumeranter denna scen", 0)
    pris = float(inst.get("Pris per prenumeration (USD)", 15))
    intäkt = pren * pris
    lön_kvinna = float(inst.get("Lön kvinna", 800))
    män = rad.get("Pappans vänner", 0) + rad.get("Nils vänner", 0) + rad.get("Nils familj", 0)
    lön_män = män * float(inst.get("Lön man", 200))
    kvar = intäkt - lön_kvinna - lön_män
    lön_kompisar = kvar / antal_kompisar if antal_kompisar > 0 else 0
    return round(intäkt, 2), round(lön_kvinna, 2), round(lön_män, 2), round(lön_kompisar, 2)

# Funktion för att beräkna total tid
def beräkna_tid(rad):
    antal_män = (
        rad.get("DP", 0) * 2 +
        rad.get("DPP", 0) * 2 +
        rad.get("DAP", 0) * 2 +
        rad.get("TPA", 0) * 3 +
        rad.get("TPP", 0) * 3 +
        rad.get("TAP", 0) * 3 +
        rad.get("Enkel vaginal", 0) +
        rad.get("Enkel anal", 0)
    )
    tid_akt = (
        (rad.get("DP", 0) +
         rad.get("DPP", 0) +
         rad.get("DAP", 0) +
         rad.get("TPA", 0) +
         rad.get("TPP", 0) +
         rad.get("TAP", 0)) * 120 +
        (rad.get("Enkel vaginal", 0) +
         rad.get("Enkel anal", 0)) * 135
    )
    dt_tid_per_man = rad.get("DT tid per man (sek)", 0)
    dt_total = dt_tid_per_man * antal_män + max((antal_män - 1), 0) * 2 + ((antal_män - 1) // 10) * 30
    summa_tid = tid_akt + dt_total + (rad.get("Antal älskar med", 0) * 900) + (rad.get("Antal sover med", 0) * 900)
    tid_per_man = (summa_tid / antal_män / 60) if antal_män > 0 else 0
    return dt_total, summa_tid, tid_per_man

# Funktion för att lägga till en ny rad i databasen
def lägg_till_rad(df, ny_rad):
    df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    return df

# Funktion för att räkna ut ålder
def räkna_ålder(födelsedatum, dagens_datum):
    födelsedatum = pd.to_datetime(födelsedatum)
    dagens_datum = pd.to_datetime(dagens_datum)
    return dagens_datum.year - födelsedatum.year - ((dagens_datum.month, dagens_datum.day) < (födelsedatum.month, födelsedatum.day))

# Funktion för att visa statistik
def visa_statistik(df, inst):
    if df.empty:
        st.info("Ingen data tillgänglig.")
        return

    namn = inst.get("Kvinnans namn", "Kvinnan")
    född = inst.get("Kvinnans födelsedatum", "1990-01-01")
    senaste_datum = pd.to_datetime(df["Datum"].iloc[-1])
    ålder = räkna_ålder(född, senaste_datum)

    st.subheader(f"Statistik för {namn}, ålder {ålder} år")

    total_män = df[["DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Enkel vaginal", "Enkel anal"]].sum().sum()
    total_älskat = df["Antal älskar med"].sum()
    total_sovit = df["Antal sover med"].sum()

    grupper = ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]
    gangbangs = {grupp: df[grupp].sum() for grupp in grupper}

    st.markdown(f"- Totalt antal män som haft sex: **{int(total_män)}**")
    for grupp, antal in gangbangs.items():
        st.markdown(f"- {grupp}: **{int(antal)}** tillfällen")

    st.markdown(f"- Totalt antal älskat med: **{int(total_älskat)}**")
    st.markdown(f"- Totalt antal sovit med: **{int(total_sovit)}** (endast Nils familj)")

# Funktion för att generera nästa datum
def generera_nytt_datum(df, inst, dagar_vila=0):
    if df.empty:
        return pd.to_datetime(inst.get("Startdatum", "2020-01-01")) + pd.Timedelta(days=0)
    senaste = pd.to_datetime(df["Datum"].iloc[-1])
    return senaste + pd.Timedelta(days=dagar_vila if dagar_vila else 1)

# Funktion för att slumpa vilodag på inspelningsplats
def slumpa_vilodag_insp(inst, df):
    max60 = lambda x: max(0, int(inst.get(x, 0) * 0.6))
    ny_rad = {
        "Datum": generera_nytt_datum(df, inst, dagar_vila=1).strftime("%Y-%m-%d"),
        "Kompisar": random.randint(0, max60("Kompisar")),
        "Pappans vänner": random.randint(0, max60("Pappans vänner")),
        "Nils vänner": random.randint(0, max60("Nils vänner")),
        "Nils familj": random.randint(0, max60("Nils familj")),
        "Antal älskar med": 12,
        "Antal sover med": 1
    }
    ny_rad.update({k: 0 for k in ["DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Enkel vaginal", "Enkel anal", "DT tid per man (sek)", "Pris per scen (USD)"]})
    ny_rad["Nils sex"] = ""
    dt_total, summa_tid, tid_per_man = beräkna_tid(ny_rad)
    ny_rad["DT total tid (sek)"] = dt_total
    ny_rad["Summa tid (sek)"] = summa_tid
    ny_rad["Tid per man (min)"] = tid_per_man
    return ny_rad

# Funktion för att slumpa vilovecka hemma
def slumpa_vilovecka_hem(inst, df):
    max10 = lambda x: max(0, int(inst.get(x, 0) * 0.1))
    ny_rad = {
        "Datum": generera_nytt_datum(df, inst, dagar_vila=7).strftime("%Y-%m-%d"),
        "Kompisar": random.randint(0, max10("Kompisar")),
        "Pappans vänner": 0,
        "Nils vänner": 0,
        "Nils familj": 0,
        "Antal älskar med": 8,
        "Antal sover med": 0
    }
    ny_rad["Nils sex"] = "Ja" if random.randint(0, 2) > 0 else "Nej"
    ny_rad.update({k: 0 for k in ["DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Enkel vaginal", "Enkel anal", "DT tid per man (sek)", "Pris per scen (USD)"]})
    dt_total, summa_tid, tid_per_man = beräkna_tid(ny_rad)
    ny_rad["DT total tid (sek)"] = dt_total
    ny_rad["Summa tid (sek)"] = summa_tid
    ny_rad["Tid per man (min)"] = tid_per_man
    return ny_rad

# Funktion för att uppdatera DataFrame med inställningar
def uppdatera_inställningar_df(df):
    for col in KOLUMNER:
        if col not in df.columns:
            df[col] = 0 if "tid" in col.lower() or "pris" in col.lower() else ""
    return df[KOLUMNER]

# Huvudfunktion
def main():
    st.title("Malin-produktionsdata")
    df = ladda_data()
    inst = läs_inställningar()

    with st.sidebar:
        st.header("Inställningar")
        namn = st.text_input("Kvinnans namn", value=inst.get("Kvinnans namn", ""))
        född = st.date_input("Födelsedatum", pd.to_datetime(inst.get("Födelsedatum", "1990-01-01")))
        startdatum = st.date_input("Startdatum (första scen)", pd.to_datetime(inst.get("Startdatum", "2020-01-01")))

        if st.button("Spara inställningar"):
            spara_inställning("Kvinnans namn", namn)
            spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
            spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))
            st.success("Inställningar sparade")
            st.rerun()

        st.divider()
        st.subheader("Grunddata (antal personer)")
        for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            antal = st.number_input(fält, value=int(inst.get(fält, 0)), min_value=0)
            if st.button(f"Spara {fält}"):
                spara_inställning(fält, antal)
                st.rerun()

    st.header("Lägg till scen")
    with st.form("ny_scen"):
        ny_rad = {}
        ny_rad["Datum"] = generera_nytt_datum(df, inst).strftime("%Y-%m-%d")
        for fält in ["DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Enkel vaginal", "Enkel anal"]:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1)
        for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1, max_value=int(inst.get(fält, 0)))
        ny_rad["Antal älskar med"] = st.number_input("Antal älskar med", min_value=0)
        ny_rad["Antal sover med"] = st.number_input("Antal sover med", min_value=0)
        ny_rad["DT tid per man (sek)"] = st.number_input("Deep throat tid/man (sek)", min_value=0)
        ny_rad["Pris per scen (USD)"] = st.number_input("Pris per scen (USD)", min_value=0.0, step=0.01)
        submit = st.form_submit_button("Spara scen")

    if submit:
        dt_total, summa_tid, tid_per_man = beräkna_tid(ny_rad)
        ny_rad["DT total tid (sek)"] = dt_total
        ny_rad["Summa tid (sek)"] = summa_tid
        ny_rad["Tid per man (min)"] = tid_per_man
        ny_rad["Nils sex"] = ""
        ny_rad = {k: ny_rad.get(k, "") for k in KOLUMNER}
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(df)
        st.success("Scen sparad")
        st.rerun()

    st.header("Lägg till vilodagar")
    antal_vilodagar = st.number_input("Antal vilodagar (inspelningsplats)", min_value=1, max_value=21, value=1)
    if st.button("Lägg till vilodagar på inspelningsplats"):
        for _ in range(antal_vilodagar):
            ny_rad = slumpa_vilodag_insp(inst, df)
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(df)
        st.success("Vilodagar tillagda")
        st.rerun()

    if st.button("Lägg till vilovecka hemma (7 dagar)"):
        ny_rad = slumpa_vilovecka_hem(inst, df)
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(df)
        st.success("Vilovecka tillagd")
        st.rerun()

    st.header("Statistik")
    if not df.empty:
        df["Datum"] = pd.to_datetime(df["Datum"])
        sista = df["Datum"].max()
        ålder = (sista - pd.to_datetime(inst.get("Födelsedatum"))).days // 365
        st.write(f"**{inst.get('Kvinnans namn', '')}** är nu **{ålder} år gammal** (senaste datum: {sista.date()})")

        totalt_män = df[["DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Enkel vaginal", "Enkel anal"]].sum().sum()
        st.metric("Totalt antal män i alla scener", int(totalt_män))

        for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            antal = df[fält].sum()
            st.write(f"{fält}: {antal} tillfällen")

        st.write("Antal gånger älskat:", df["Antal älskar med"].sum())
        st.write("Antal gånger sovit med:", df["Antal sover med"].sum())

    st.header("Databas")
    st.dataframe(df)

if __name__ == "__main__":
    main()
