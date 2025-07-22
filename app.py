import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
import math
import random

# === Autentisering till Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(creds)

# === Fil och bladnamn
SPREADSHEET_NAME = "MalinData2"
SCEN_SHEET = "Scener"
INST_SHEET = "Inställningar"

# === Initiera kalkylark och blad
sh = gc.open(SPREADSHEET_NAME)
try:
    scen_sheet = sh.worksheet(SCEN_SHEET)
except:
    scen_sheet = sh.add_worksheet(title=SCEN_SHEET, rows=1000, cols=50)

try:
    inst_sheet = sh.worksheet(INST_SHEET)
except:
    inst_sheet = sh.add_worksheet(title=INST_SHEET, rows=100, cols=10)

# === Funktion: se till att rätt kolumner finns
HEADERS = [
    "Datum", "Totala män", "Prenumeranter", "Aktiekurs", "Total tid (min)",
    "Aktiv tid", "Deep throat", "Extra älskar/sover",
    "TPA", "TPP", "TAP", "DP", "DPP", "DAP", "Enkel V", "Enkel A",
    "Kompisar (scen)", "Pappans vänner", "Nils vänner", "Nils familj",
    "Älskar med", "Sover med",
    "Vilo_PV", "Vilo_Kompis", "Vilo_NV", "Vilo_NF",
    "Intäkt", "Kvinna lön", "Män lön", "Kompisandel total", "Kompislön per person",
    "Hem_Kompis", "Hem_Älskar", "Hem_Sover", "Nils_fru_sex"
]

def ensure_headers(sheet):
    current = sheet.get_all_values()
    if not current or current[0] != HEADERS:
        sheet.clear()
        sheet.append_row(HEADERS)

ensure_headers(scen_sheet)

# === Läs inställningar eller skapa standard
def load_inställningar():
    try:
        df = pd.DataFrame(inst_sheet.get_all_records())
        if df.empty:
            raise Exception
        return df.set_index("Parameter")["Värde"].to_dict()
    except:
        default = {
            "Vikt enkel": 1,
            "Vikt dubbel": 2,
            "Vikt TPP/TPA": 3,
            "Vikt TAP": 4,
            "Startkurs": 1.0,
            "Antal aktier": 100000,
            "Totalt kompisar": 100,
            "Totalt pappans vänner": 20,
            "Totalt Nils vänner": 10,
            "Totalt Nils familj": 5
        }
        inst_sheet.clear()
        inst_sheet.update([["Parameter", "Värde"]] + [[k, v] for k, v in default.items()])
        return default

inst = load_inställningar()

# === Sidopanel: inställningar
st.sidebar.header("Inställningar")
with st.sidebar.form("inst_form"):
    vikt_enkel = st.number_input("Vikt enkel", value=int(inst["Vikt enkel"]))
    vikt_dubbel = st.number_input("Vikt dubbel", value=int(inst["Vikt dubbel"]))
    vikt_tpp_tpa = st.number_input("Vikt TPP/TPA", value=int(inst["Vikt TPP/TPA"]))
    vikt_tap = st.number_input("Vikt TAP", value=int(inst["Vikt TAP"]))
    startkurs = st.number_input("Startkurs", value=float(inst["Startkurs"]), step=0.1)
    aktier = st.number_input("Antal aktier", value=int(inst["Antal aktier"]))
    tot_kompisar = st.number_input("Totalt kompisar", value=int(inst["Totalt kompisar"]))
    tot_pv = st.number_input("Totalt pappans vänner", value=int(inst["Totalt pappans vänner"]))
    tot_nv = st.number_input("Totalt Nils vänner", value=int(inst["Totalt Nils vänner"]))
    tot_nf = st.number_input("Totalt Nils familj", value=int(inst["Totalt Nils familj"]))
    if st.form_submit_button("Spara inställningar"):
        nydata = {
            "Vikt enkel": vikt_enkel,
            "Vikt dubbel": vikt_dubbel,
            "Vikt TPP/TPA": vikt_tpp_tpa,
            "Vikt TAP": vikt_tap,
            "Startkurs": startkurs,
            "Antal aktier": aktier,
            "Totalt kompisar": tot_kompisar,
            "Totalt pappans vänner": tot_pv,
            "Totalt Nils vänner": tot_nv,
            "Totalt Nils familj": tot_nf
        }
        inst_sheet.clear()
        inst_sheet.update([["Parameter", "Värde"]] + [[k, v] for k, v in nydata.items()])
        st.success("Inställningar sparade. Ladda om sidan.")

# === Huvudformulär
st.header("🎬 Lägg till ny scen")
with st.form("scen_form"):
    datum = st.date_input("Datum")
    antal_man = st.number_input("Antal män", min_value=1)
    tpa = st.number_input("TPA", min_value=0)
    tpp = st.number_input("TPP", min_value=0)
    tap = st.number_input("TAP", min_value=0)
    dp = st.number_input("DP", min_value=0)
    dpp = st.number_input("DPP", min_value=0)
    dap = st.number_input("DAP", min_value=0)
    enkel_v = st.number_input("Enkel vaginal", min_value=0)
    enkel_a = st.number_input("Enkel anal", min_value=0)
    tid_min = st.number_input("Tid per man (min)", min_value=0)
    tid_sek = st.number_input("Tid per man (sek)", min_value=0, max_value=59)
    dt_tid = st.number_input("Deep throat-tid per man (sek)", min_value=0)
    komp = st.number_input("Kompisar", min_value=0, max_value=inst["Totalt kompisar"])
    pv = st.number_input("Pappans vänner", min_value=0, max_value=inst["Totalt pappans vänner"])
    nv = st.number_input("Nils vänner", min_value=0, max_value=inst["Totalt Nils vänner"])
    nf = st.number_input("Nils familj", min_value=0, max_value=inst["Totalt Nils familj"])
    alskar = st.number_input("Älskar med", value=12)
    sover = st.number_input("Sover med", value=1)
    pris = st.number_input("Pris per prenumeration", value=15.0)
    vilo = st.number_input("Vilodagar efter scen", min_value=0, max_value=21)
    submit = st.form_submit_button("Generera slumpdata & spara scen")

if submit:
    tid_per_man = tid_min * 60 + tid_sek
    tot_män = antal_man + komp + pv + nv + nf
    akt_tid = (tpa + tpp + tap) * 120 + (dp + dpp + dap) * 120 + (enkel_v + enkel_a) * 120
    byten = (tpa + tpp + tap + dp + dpp + dap + enkel_v + enkel_a) * 15
    deep_sum = tot_män * dt_tid + (tot_män - 1) * 2 + (tot_män // 10) * 30
    extra = (alskar + sover) * 15 * 60
    total_tid = akt_tid + byten + deep_sum + extra

    vikter = {"enkel": inst["Vikt enkel"], "dubbel": inst["Vikt dubbel"],
              "tpp_tpa": inst["Vikt TPP/TPA"], "tap": inst["Vikt TAP"]}
    score = (enkel_v + enkel_a) * vikter["enkel"] + (dp + dpp + dap) * vikter["dubbel"] + \
            (tpp + tpa) * vikter["tpp_tpa"] + tap * vikter["tap"]
    pren = round(score + tot_män * 0.05)

    intakt = pren * pris
    kvinna = 800
    man = (tot_män - komp) * 200
    kvar = max(0, intakt - kvinna - man)
    komp_lön = kvar / inst["Totalt kompisar"]

    try:
        df = pd.DataFrame(scen_sheet.get_all_records())
        senast = df["Prenumeranter"].iloc[-1]
    except:
        senast = pren
    kurs = round(inst["Startkurs"] * (1 + (pren - senast) / senast), 2) if senast else inst["Startkurs"]

    def slump(maxantal, procent):
        return sum([random.randint(0, 1) for _ in range(vilo * round(maxantal * procent))])

    v_pv = slump(inst["Totalt pappans vänner"], 0.6)
    v_komp = slump(inst["Totalt kompisar"], 0.6)
    v_nv = slump(inst["Totalt Nils vänner"], 0.6)
    v_nf = slump(inst["Totalt Nils familj"], 0.6)

    df = pd.DataFrame(scen_sheet.get_all_records()) if scen_sheet.row_count > 1 else pd.DataFrame()
    hem = len(df) >= 21
    h_komp = random.randint(0, round(inst["Totalt kompisar"] * 0.1)) if hem else 0
    h_alskar = 8 if hem else 0
    h_sover = 0
    nils_fru = random.randint(0, 2) if hem else 0

    rad = [str(datum), tot_män, pren, kurs, round(total_tid / 60, 2),
           akt_tid / 60, deep_sum / 60, extra / 60,
           tpa, tpp, tap, dp, dpp, dap, enkel_v, enkel_a,
           komp, pv, nv, nf, alskar, sover,
           v_pv, v_komp, v_nv, v_nf,
           intakt, kvinna, man, kvar, komp_lön,
           h_komp, h_alskar, h_sover, nils_fru]

    scen_sheet.append_row(rad)
    st.success("Scen sparad.")

# === Statistikpanel
st.header("📊 Statistik")
if st.button("Visa statistik"):
    try:
        df = pd.DataFrame(scen_sheet.get_all_records())
        st.write("👥 Totalt antal män:", df["Totala män"].sum())
        st.write("🔄 Gangbang – Pappans vänner:", df["Pappans vänner"].sum())
        st.write("🔄 Gangbang – Kompisar:", df["Kompisar (scen)"].sum())
        st.write("🔄 Gangbang – Nils vänner:", df["Nils vänner"].sum())
        st.write("🔄 Gangbang – Nils familj:", df["Nils familj"].sum())
        st.write("❤️ Älskat med:", df["Älskar med"].sum() + df["Hem_Älskar"].sum())
        st.write("💤 Sovit med:", df["Sover med"].sum() + df["Hem_Sover"].sum())
        st.write("💏 Nils haft sex med frun:", df["Nils_fru_sex"].sum())
    except Exception as e:
        st.error(f"Fel vid hämtning av statistik: {e}")
