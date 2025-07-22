import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import random
import math
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Malin – Filmdata", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=SCOPES
)
gc = gspread.authorize(creds)
sh = gc.open_by_url(SPREADSHEET_URL)

# Initiera blad
try:
    inst_sheet = sh.worksheet("Inställningar")
except:
    inst_sheet = sh.add_worksheet(title="Inställningar", rows="10", cols="3")
    inst_sheet.update("A1:B5", [
        ["Inställning", "Värde"],
        ["Senast kända kurs", 1.0],
        ["Senaste prenumeranter", 0],
        ["Totalt kompisar", 0],
        ["Totalt pappans vänner", 0],
        ["Totalt Nils vänner", 0],
        ["Totalt Nils familj", 0],
        ["Senast ändrad", str(datetime.now())]
    ])

try:
    scen_sheet = sh.worksheet("Scener")
except:
    scen_sheet = sh.add_worksheet(title="Scener", rows="1000", cols="30")
    scen_sheet.append_row([
        "Datum", "Totala män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vagina", "Enkel anal", "DT_tid", "Tid_min", "Tid_sek", "Total_tid",
        "Tid_per_man", "Prenumeranter", "Aktiekurs", "Total intäkt",
        "Kvinnans lön", "Mäns lön", "Kompisars andel", "Kompisar (scen)",
        "Pappans vänner", "Nils vänner", "Nils familj", "Älskar med", "Sover med", "DT_total"
    ])

# Läs in inställningar
inst_data = inst_sheet.get_all_records()
inst = {rad["Inställning"]: float(rad["Värde"]) if rad["Värde"].replace('.', '', 1).isdigit() else rad["Värde"]
        for rad in inst_data}
startkurs = inst.get("Senast kända kurs", 1.0)

st.sidebar.header("⚙️ Inställningar – Grunddata")
inst["Totalt kompisar"] = st.sidebar.number_input("Totalt antal kompisar", min_value=0, step=1,
                                                  value=int(inst.get("Totalt kompisar", 0)))
inst["Totalt pappans vänner"] = st.sidebar.number_input("Totalt antal pappans vänner", min_value=0, step=1,
                                                        value=int(inst.get("Totalt pappans vänner", 0)))
inst["Totalt Nils vänner"] = st.sidebar.number_input("Totalt antal Nils vänner", min_value=0, step=1,
                                                     value=int(inst.get("Totalt Nils vänner", 0)))
inst["Totalt Nils familj"] = st.sidebar.number_input("Totalt antal Nils familj", min_value=0, step=1,
                                                     value=int(inst.get("Totalt Nils familj", 0)))
startkurs = st.sidebar.number_input("Startkurs", value=startkurs, step=0.1)

if st.sidebar.button("💾 Spara inställningar"):
    inst_sheet.update("A2:B7", [
        ["Senast kända kurs", startkurs],
        ["Senaste prenumeranter", inst.get("Senaste prenumeranter", 0)],
        ["Totalt kompisar", inst["Totalt kompisar"]],
        ["Totalt pappans vänner", inst["Totalt pappans vänner"]],
        ["Totalt Nils vänner", inst["Totalt Nils vänner"]],
        ["Totalt Nils familj", inst["Totalt Nils familj"]],
        ["Senast ändrad", str(datetime.now())]
    ])
    st.sidebar.success("Inställningar sparade.")

st.header("🎬 Lägg till ny scen")

with st.form("ny_scen"):
    col1, col2 = st.columns(2)
    with col1:
        datum = st.date_input("Datum för scen")
        tot_man = st.number_input("Totalt antal män", min_value=1, step=1)
        dp = st.number_input("DP (en i vardera hål)", min_value=0)
        dpp = st.number_input("DPP (2 i vagina)", min_value=0)
        dap = st.number_input("DAP (2 i anus)", min_value=0)
        tpa = st.number_input("TPA (2 i fittan + 1 i rumpan eller tvärtom)", min_value=0)
        tpp = st.number_input("TPP (3 i vagina)", min_value=0)
        tap = st.number_input("TAP (3 i anus)", min_value=0)

    with col2:
        enkel_vag = st.number_input("Enkel vaginal (1 man)", min_value=0)
        enkel_anal = st.number_input("Enkel anal (1 man)", min_value=0)
        dt_tid = st.number_input("Deep throat tid per man (sekunder)", min_value=0, max_value=300)
        tid_min = st.number_input("Tid per man (minuter)", min_value=0, max_value=60)
        tid_sek = st.number_input("Tid per man (sekunder)", min_value=0, max_value=59)

        komp_scen = st.number_input(
            "Kompisar (scen)", 
            min_value=0,
            max_value=int(inst.get("Totalt kompisar", 0))
        )
        pv_scen = st.number_input(
            "Pappans vänner (scen)", 
            min_value=0,
            max_value=int(inst.get("Totalt pappans vänner", 0))
        )
        nv_scen = st.number_input(
            "Nils vänner (scen)", 
            min_value=0,
            max_value=int(inst.get("Totalt Nils vänner", 0))
        )
        nf_scen = st.number_input(
            "Nils familj (scen)", 
            min_value=0,
            max_value=int(inst.get("Totalt Nils familj", 0))
        )

    st.markdown("#### ❤️ Extra intimitet")
    extra_alskar = st.number_input("Antal som 'älskar med'", min_value=0, value=0)
    extra_sover = st.number_input("Antal som 'sover med'", min_value=0, value=0)

    submit = st.form_submit_button("Beräkna & spara scen")

if submit:
    total_tid = 0
    antal_grupper = dp + dpp + dap + tpa + tpp + tap
    tid_per_3m = 120  # 2 minuter
    vila_per_byte = 15  # sekunder
    vila_per_60min = 120  # 2 minuters vila per 60 min

    tid_grupper = antal_grupper * (tid_per_3m + vila_per_byte)
    tid_enkel = (enkel_vag + enkel_anal) * 120 + max(0, (enkel_vag + enkel_anal - 1)) * vila_per_byte
    tid_enkel_total = tid_enkel / max(1, tot_man)

    dt_total_tid = dt_tid * tot_man + (tot_man - 1) * 2 + (tot_man // 10) * 30

    extra_tid = (extra_alskar + extra_sover) * 15 * 60  # konverterat till sekunder

    total_tid = tid_grupper + tid_enkel + dt_total_tid + extra_tid

    tid_per_man = total_tid / tot_man if tot_man > 0 else 0
    tid_per_man_min = round(tid_per_man / 60, 2)
    total_tid_min = round(total_tid / 60, 2)

    # Prenumeranter – viktat
    pren_score = (
        dp * 3 + dpp * 4 + dap * 4 +
        tpa * 6 + tpp * 6 + tap * 7 +
        enkel_vag * 1.2 + enkel_anal * 1.5
    )
    prenumeranter = int(pren_score * 1.5)

    # Ekonomi
    intakt = prenumeranter * 15
    kvinnan_lon = 800
    man_lon = (tot_man - komp_scen) * 200
    komp_andel = max(0, intakt - kvinnan_lon - man_lon)
    aktiekurs = round(startkurs * (1 + (prenumeranter - inst.get("Senaste prenumeranter", 0)) / 1000), 2)

    # Spara till ark
    scen_sheet.append_row([
        str(datum), tot_man, dp, dpp, dap, tpa, tpp, tap,
        enkel_vag, enkel_anal, dt_tid, tid_min, tid_sek, total_tid_min,
        tid_per_man_min, prenumeranter, aktiekurs, intakt,
        kvinnan_lon, man_lon, komp_andel, komp_scen,
        pv_scen, nv_scen, nf_scen, extra_alskar, extra_sover, dt_total_tid
    ])

    inst["Senast kända kurs"] = aktiekurs
    inst["Senaste prenumeranter"] = prenumeranter
    inst_sheet.update("A2:B3", [
        ["Senast kända kurs", aktiekurs],
        ["Senaste prenumeranter", prenumeranter]
    ])

    st.success(f"Scen sparad. Ny aktiekurs: ${aktiekurs} – Prenumeranter: {prenumeranter}")

st.header("🛌 Vilodagar & slump")

with st.form("vilodag_form"):
    insp_vilodagar = st.number_input("Antal vilodagar på inspelningsplats", min_value=0, max_value=21, value=2)
    hem_vilodagar = 7  # alltid 7
    generera = st.form_submit_button("Generera vilodagstillfällen")

if generera:
    # Slumpa under inspelningsplats (max 60 % av grupperna)
    insp_resultat = {
        "kompisar": random.randint(0, round(inst["Totalt kompisar"] * 0.6)),
        "pv": random.randint(0, round(inst["Totalt pappans vänner"] * 0.6)),
        "nv": random.randint(0, round(inst["Totalt Nils vänner"] * 0.6)),
        "nf": random.randint(0, round(inst["Totalt Nils familj"] * 0.6)),
        "alskar": 12,
        "sover": 1,
    }

    # Slumpa under hemvila (kompisar 10 %, övriga 0)
    hem_resultat = {
        "kompisar": random.randint(0, round(inst["Totalt kompisar"] * 0.1)),
        "pv": 0, "nv": 0, "nf": 0,
        "alskar": 8,
        "sover": 0,
    }

    # Slumpa om Nils får sex med sin fru under 7 dagars vila
    nils_sex_med_fru = random.randint(0, 2)

    # Lägg in 1 rad per block
    scen_sheet.append_row([
        str(datetime.now().date()), "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "vilodag_insp",
        "-", "-", "-", "-", "-", "-", "-", insp_resultat["kompisar"],
        insp_resultat["pv"], insp_resultat["nv"], insp_resultat["nf"],
        insp_resultat["alskar"], insp_resultat["sover"], "-"
    ])
    scen_sheet.append_row([
        str(datetime.now().date()), "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "vilodag_hem",
        "-", "-", "-", "-", "-", "-", "-", hem_resultat["kompisar"],
        hem_resultat["pv"], hem_resultat["nv"], hem_resultat["nf"],
        hem_resultat["alskar"], hem_resultat["sover"], "-"
    ])
    scen_sheet.append_row([
        str(datetime.now().date()), "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "nils_fru",
        "-", "-", "-", "-", "-", "-", "-", 0, 0, 0, 0, nils_sex_med_fru, 0, "-"
    ])

    st.success("Vilodagar och tillfällen genererade och sparade.")

st.header("📊 Statistik")

df = pd.DataFrame(scen_sheet.get_all_records())

def safe_sum(col):
    return df[col].apply(lambda x: pd.to_numeric(x, errors='coerce')).sum()

tot_man = safe_sum("Totala män")
tot_kompisar = safe_sum("Kompisar (scen)")
tot_pv = safe_sum("Pappans vänner")
tot_nv = safe_sum("Nils vänner")
tot_nf = safe_sum("Nils familj")
alskar = safe_sum("Älskar med")
sover = safe_sum("Sover med")
nilsfru = df[df["Total_tid"] == "nils_fru"]["Sover med"].astype(float).sum()

col1, col2 = st.columns(2)
with col1:
    st.metric("Totalt antal män", int(tot_man))
    st.metric("Totalt 'älskar med'", int(alskar))
    st.metric("Totalt 'sover med'", int(sover))
with col2:
    st.metric("Kompisar i gangbang", int(tot_kompisar))
    st.metric("Pappans vänner i gangbang", int(tot_pv))
    st.metric("Nils vänner i gangbang", int(tot_nv))
    st.metric("Nils familj i gangbang", int(tot_nf))

st.info(f"Nils har haft sex med sin fru totalt **{int(nilsfru)}** gång(er).")
