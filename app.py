import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import random

# Google Sheets-uppkoppling
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SPREADSHEET_URL)

# Funktion: hämta och skapa ark
def get_or_create_worksheet(sheet, name, cols):
    try:
        ws = sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="50")
        ws.append_row(cols)
    return ws

# Ladda inställningar
def ladda_inställningar():
    inst_ws = get_or_create_worksheet(sh, "Inställningar", ["Inställning", "Värde", "Senast ändrad"])
    df = pd.DataFrame(inst_ws.get_all_records())
    inst = {}
    for _, rad in df.iterrows():
        key = rad["Inställning"]
        value = rad["Värde"]
        if isinstance(value, str) and value.replace('.', '', 1).isdigit():
            inst[key] = float(value)
        else:
            inst[key] = value
    return inst, inst_ws

inst, inst_ws = ladda_inställningar()

# Funktion: uppdatera inställning
def uppdatera_inställning(nyckel, nytt_värde):
    df = pd.DataFrame(inst_ws.get_all_records())
    idx = df.index[df["Inställning"] == nyckel].tolist()
    idag = datetime.today().strftime("%Y-%m-%d")
    if idx:
        inst_ws.update_cell(idx[0]+2, 2, nytt_värde)
        inst_ws.update_cell(idx[0]+2, 3, idag)
    else:
        inst_ws.append_row([nyckel, nytt_värde, idag])

# Sidopanel – inställningar
st.sidebar.header("Inställningar")
startdatum = st.sidebar.date_input("Startdatum", datetime.strptime(inst.get("Startdatum", "2014-03-26"), "%Y-%m-%d"))
namn = st.sidebar.text_input("Kvinnans namn", inst.get("Kvinnans namn", "Malin"))
födelsedatum = st.sidebar.date_input("Födelsedatum", datetime.strptime(inst.get("Kvinnans födelsedatum", "1984-03-26"), "%Y-%m-%d"))

if st.sidebar.button("Spara inställningar"):
    uppdatera_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))
    uppdatera_inställning("Kvinnans namn", namn)
    uppdatera_inställning("Kvinnans födelsedatum", födelsedatum.strftime("%Y-%m-%d"))
    st.success("Inställningar sparade")
    st.rerun()

# Funktion: Hämta senaste datum från Scener
def hämta_senaste_datum():
    try:
        scener_ws = sh.worksheet("Scener")
        df = pd.DataFrame(scener_ws.get_all_records())
        if df.empty or "Datum" not in df.columns:
            return datetime.strptime(inst.get("Startdatum", "2014-03-26"), "%Y-%m-%d")
        else:
            senaste = df["Datum"].dropna().iloc[-1]
            return datetime.strptime(senaste, "%Y-%m-%d")
    except:
        return datetime.strptime(inst.get("Startdatum", "2014-03-26"), "%Y-%m-%d")

# Åldersberäkning
def beräkna_ålder(födelsedatum_str, senast_datum):
    födelsedatum = datetime.strptime(födelsedatum_str, "%Y-%m-%d")
    ålder = senast_datum.year - födelsedatum.year - ((senast_datum.month, senast_datum.day) < (födelsedatum.month, födelsedatum.day))
    return ålder

# Funktion: Skapa kolumner om de saknas
def säkerställ_kolumner(ws, förväntade_kolumner):
    befintliga = ws.row_values(1)
    if befintliga != förväntade_kolumner:
        ws.resize(rows=1)
        ws.update("A1", [förväntade_kolumner])

# Funktion: Skapa databasblad vid behov
def initiera_databasblad():
    kolumner = [
        "Datum", "Män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Vaginal enkel", "Anal enkel",
        "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
        "DT tid (sek)", "Älskar med", "Sover med",
        "Total tid (sek)", "DT total tid (sek)", "Total tid per man (min)",
        "Intäkt ($)", "Kvinnans lön ($)", "Männens lön ($)", "Kompisars lön ($)",
        "Prenumeranter", "Vilodag", "Nils sex hemma"
    ]
    scener_ws = get_or_create_worksheet(sh, "Scener", kolumner)
    säkerställ_kolumner(scener_ws, kolumner)

initiera_databasblad()

# Hämta senaste datum och räkna ut nytt
senaste_datum = hämta_senaste_datum()
nästa_datum = senaste_datum + timedelta(days=1)

# Visa namn och ålder
st.markdown(f"### {namn}, {beräkna_ålder(inst.get('Kvinnans födelsedatum', '1984-03-26'), senaste_datum)} år")
st.markdown(f"Nästa scen planeras: **{nästa_datum.strftime('%Y-%m-%d')}**")

st.header("Lägg till ny scen")

with st.form("ny_scen"):
    män = st.number_input("Antal män", min_value=0)
    dp = st.number_input("DP", min_value=0)
    dpp = st.number_input("DPP", min_value=0)
    dap = st.number_input("DAP", min_value=0)
    tpa = st.number_input("TPA", min_value=0)
    tpp = st.number_input("TPP", min_value=0)
    tap = st.number_input("TAP", min_value=0)
    vag = st.number_input("Enkel vaginal", min_value=0)
    anal = st.number_input("Enkel anal", min_value=0)

    komp_total = inst.get("Kompisar", 0)
    komp = st.number_input("Kompisar (i scen)", min_value=0, max_value=int(komp_total or 9999))
    pv_total = inst.get("Pappans vänner", 0)
    pv = st.number_input("Pappans vänner (i scen)", min_value=0, max_value=int(pv_total or 9999))
    nv_total = inst.get("Nils vänner", 0)
    nv = st.number_input("Nils vänner (i scen)", min_value=0, max_value=int(nv_total or 9999))
    nf_total = inst.get("Nils familj", 0)
    nf = st.number_input("Nils familj (i scen)", min_value=0, max_value=int(nf_total or 9999))

    dt_tid = st.number_input("Deep throat-tid per man (sekunder)", min_value=0)
    älskar = st.number_input("Antal 'älskar med'", min_value=0)
    sover = st.number_input("Antal 'sover med'", min_value=0)

    tid_per_man_min = st.number_input("Tid varje man får (minuter)", min_value=0)
    tid_per_man_sek = st.number_input("Tid varje man får (sekunder)", min_value=0, step=15)

    skicka = st.form_submit_button("Spara scen")

if skicka:
    total_män = män + komp + pv + nv + nf
    penetrationstid = ((dp + dpp + dap) * 2 + (tpa + tpp + tap) * 2 + vag + anal) * 120 + (15 * (dp + dpp + dap + tpa + tpp + tap + vag + anal))
    älskartid = (älskar + sover) * 15 * 60
    total_tid = penetrationstid + älskartid

    dt_total = total_män * dt_tid + total_män * 2 + (total_män // 10) * 30
    tid_per_man = (total_tid + dt_total) / total_män / 60

    intakt = int(total_män * 15)
    kvinnan = 800
    man_lön = (män + pv + nv + nf) * 200
    kompisar_lön = max(intakt - kvinnan - man_lön, 0) / max(inst.get("Kompisar", 1), 1)

    data = [
        nästa_datum.strftime("%Y-%m-%d"), män, dp, dpp, dap, tpa, tpp, tap,
        vag, anal, komp, pv, nv, nf, dt_tid, älskar, sover,
        total_tid, dt_total, round(tid_per_man, 2),
        intakt, kvinnan, man_lön, round(kompisar_lön, 2),
        "", "", ""
    ]
    scener_ws = sh.worksheet("Scener")
    scener_ws.append_row(data)
    st.success("Scen sparad")
    st.rerun()

st.header("📊 Statistik")

try:
    df = pd.DataFrame(sh.worksheet("Scener").get_all_records())
    df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")

    total_män = df["Män"].sum() + df["Kompisar"].sum() + df["Pappans vänner"].sum() + df["Nils vänner"].sum() + df["Nils familj"].sum()
    total_dt_tid = df["DT total tid (sek)"].sum()
    total_tid_per_man = df["Total tid per man (min)"].mean()

    st.markdown(f"- **Totalt antal män:** {int(total_män)}")
    st.markdown(f"- **Total DT-tid:** {round(total_dt_tid / 60, 1)} minuter")
    st.markdown(f"- **Genomsnittlig tid per man:** {round(total_tid_per_man, 2)} minuter")

    # Frekvens per vänkategori
    vän_kategorier = ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]
    for kategori in vän_kategorier:
        tot = df[kategori].sum()
        st.markdown(f"- **{kategori} (antal deltaganden):** {int(tot)}")

    # Antal "älskar med" och "sover med"
    st.markdown(f"- **Totalt 'älskar med':** {int(df['Älskar med'].sum())}")
    st.markdown(f"- **Totalt 'sover med' (endast Nils familj):** {int(df['Sover med'].sum())}")

except Exception as e:
    st.error(f"Fel vid hämtning av statistik: {e}")
