import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import random
import math
from datetime import datetime

# === Google Sheets-koppling ===
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(creds)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit"
sh = gc.open_by_url(SPREADSHEET_URL)

# === Blad för scener och inställningar ===
try:
    scen_sheet = sh.worksheet("Scener")
except:
    scen_sheet = sh.add_worksheet(title="Scener", rows=1000, cols=50)

try:
    inst_sheet = sh.worksheet("Inställningar")
except:
    inst_sheet = sh.add_worksheet(title="Inställningar", rows=100, cols=2)
    inst_sheet.append_row(["Kategori", "Värde"])
    inst_sheet.append_row(["Totalt kompisar", 0])
    inst_sheet.append_row(["Totalt pappans vänner", 0])
    inst_sheet.append_row(["Totalt Nils vänner", 0])
    inst_sheet.append_row(["Totalt Nils familj", 0])
    inst_sheet.append_row(["Startkurs", 1.0])
    inst_sheet.append_row(["Senast kända kurs", 1.0])
    inst_sheet.append_row(["Senaste prenumeranter", 0])
    inst_sheet.append_row(["Senast ändrad", str(datetime.now())])

# === Läs in inställningar som dictionary ===
inst = {}
inst_data = inst_sheet.get_all_values()
for rad in inst_data[1:]:
    if len(rad) >= 2:
        key, val = rad[0], rad[1]
        try:
            inst[key] = float(val) if '.' in val or val.isdigit() else val
        except:
            inst[key] = val

# === Inställningspanel i sidomeny ===
with st.sidebar:
    st.header("⚙️ Inställningar (grunddata)")
    komp = st.number_input("Totalt antal kompisar", value=int(inst.get("Totalt kompisar", 0)))
    pv = st.number_input("Totalt antal pappans vänner", value=int(inst.get("Totalt pappans vänner", 0)))
    nv = st.number_input("Totalt antal Nils vänner", value=int(inst.get("Totalt Nils vänner", 0)))
    nf = st.number_input("Totalt antal Nils familj", value=int(inst.get("Totalt Nils familj", 0)))
    startkurs = st.number_input("Startkurs (USD)", value=float(inst.get("Startkurs", 1.0)))
    spara = st.button("Spara inställningar")

    if spara:
        inst_sheet.update("B2", [[komp], [pv], [nv], [nf], [startkurs], [startkurs], [0], [str(datetime.now())]])
        st.success("Inställningar sparade.")

st.header("🎬 Lägg till ny scen")

with st.form("ny_scen"):
    col1, col2 = st.columns(2)
    with col1:
        datum = st.date_input("Datum för scen")
        tot_man = st.number_input("Totalt antal män", min_value=1, step=1)
        dp = st.number_input("DP (en i vardera hål)", 0, tot_man)
        dpp = st.number_input("DPP (2 i vagina)", 0, tot_man)
        dap = st.number_input("DAP (2 i anus)", 0, tot_man)
        tpa = st.number_input("TPA (2 i fittan + 1 i rumpan eller tvärtom)", 0, tot_man)
        tpp = st.number_input("TPP (3 i vagina)", 0, tot_man)
        tap = st.number_input("TAP (3 i anus)", 0, tot_man)

    with col2:
        enkel_vag = st.number_input("Enkel vaginal (1 man)", 0, tot_man)
        enkel_anal = st.number_input("Enkel anal (1 man)", 0, tot_man)
        dt_tid = st.number_input("Deep throat tid per man (sekunder)", 0, 300)
        tid_min = st.number_input("Tid per man (minuter)", 0, 60)
        tid_sek = st.number_input("Tid per man (sekunder)", 0, 59)

        komp_scen = st.number_input("Kompisar (scen)", 0, int(inst.get("Totalt kompisar", 0)))
        pv_scen = st.number_input("Pappans vänner (scen)", 0, int(inst.get("Totalt pappans vänner", 0)))
        nv_scen = st.number_input("Nils vänner (scen)", 0, int(inst.get("Totalt Nils vänner", 0)))
        nf_scen = st.number_input("Nils familj (scen)", 0, int(inst.get("Totalt Nils familj", 0)))

    st.markdown("#### ❤️ Extra intimitet")
    extra_alskar = st.number_input("Antal som 'älskar med'", 0, 20, value=0)
    extra_sover = st.number_input("Antal som 'sover med'", 0, 5, value=0)

    submit = st.form_submit_button("Beräkna & spara scen")

if submit:
    try:
        # Totaltid för penetrationsdel
        grupper_tid = (
            math.ceil((dp + dpp + dap) / 2) +
            math.ceil((tpa + tpp + tap) / 3) +
            enkel_vag + enkel_anal
        ) * (tid_min * 60 + tid_sek)

        vilotid_grupp = (
            math.ceil((dp + dpp + dap) / 2) +
            math.ceil((tpa + tpp + tap) / 3) +
            enkel_vag + enkel_anal - 1
        ) * 15  # 15 sek vila mellan

        total_pen_tid = grupper_tid + vilotid_grupp

        # Deep throat total
        tot_deltagare = tot_man + komp_scen
        dt_total = (dt_tid + 2) * tot_deltagare + (tot_deltagare // 10) * 30

        # Extra tid för älskar/sover med
        extra_tid = (extra_alskar + extra_sover) * 15 * 60  # i sekunder

        # Total tid
        total_tid = total_pen_tid + dt_total + extra_tid

        # Tid per man
        tid_per_man = round(total_tid / tot_deltagare / 60, 2)  # i minuter

        # Beräkna prenumeranter (vikter kan justeras)
        prenum = int(
            0.5 * enkel_vag +
            0.5 * enkel_anal +
            1.5 * dp +
            2 * dpp + 2 * dap +
            3 * tpa + 3 * tpp + 3.5 * tap
        )

        # Aktiekurslogik
        senaste = inst.get("Senaste prenumeranter", 0)
        kurs = inst.get("Senast kända kurs", startkurs)
        if senaste == 0:
            ny_kurs = kurs
        else:
            ny_kurs = round(kurs * (1 + (prenum - senaste) / max(1, senaste)), 2)

        # Intäktsberäkning
        film_pris = 15
        total_intakt = prenum * film_pris
        kvinna_lon = 800
        man_lon = (tot_deltagare - komp_scen) * 200
        rest = total_intakt - kvinna_lon - man_lon
        komp_lon = round(rest / max(1, inst.get("Totalt kompisar", 1)), 2)

        # Spara scenen
        ny_rad = [
            str(datum), tot_man, dp, dpp, dap, tpa, tpp, tap, enkel_vag, enkel_anal,
            dt_tid, tid_min, tid_sek, total_tid, tid_per_man, prenum, ny_kurs,
            total_intakt, kvinna_lon, man_lon, komp_lon, komp_scen, pv_scen, nv_scen, nf_scen,
            extra_alskar, extra_sover, dt_total
        ]

        kolumnrubriker = [
            "Datum", "Totala män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
            "Enkel vagina", "Enkel anal", "DT_tid", "Tid_min", "Tid_sek", "Total_tid",
            "Tid_per_man", "Prenumeranter", "Aktiekurs", "Total intäkt",
            "Kvinnans lön", "Mäns lön", "Kompisars andel", "Kompisar (scen)",
            "Pappans vänner", "Nils vänner", "Nils familj", "Älskar med", "Sover med", "DT_total"
        ]

        if len(scen_sheet.get_all_values()) == 0:
            scen_sheet.append_row(kolumnrubriker)
        scen_sheet.append_row(ny_rad)

        # Uppdatera inställningar
        inst_sheet.update("G2", [[ny_kurs], [prenum], [str(datetime.now())]])
        st.success(f"Scen sparad! Ny aktiekurs: {ny_kurs} USD")

    except Exception as e:
        st.error(f"Något gick fel vid beräkningen: {e}")

st.header("🛌 Generera vilodagsscen")

with st.form("vila_form"):
    st.markdown("#### 🎥 Inspelningsplats (21 dagar)")
    vilodagar = st.number_input("Antal vilodagar att slumpa fram", 0, 21, 0)
    slump_insp = st.form_submit_button("Generera vilodagar på inspelningsplats")

    st.markdown("---")
    st.markdown("#### 🏡 Hemma (1 vecka)")
    slump_hemma = st.form_submit_button("Generera vilodagar hemma")

if slump_insp and vilodagar > 0:
    tot_kompisar = inst.get("Totalt kompisar", 0)
    tot_pv = inst.get("Totalt pappans vänner", 0)
    tot_nv = inst.get("Totalt Nils vänner", 0)
    tot_nf = inst.get("Totalt Nils familj", 0)

    for _ in range(vilodagar):
        rad = [
            str(datetime.now().date()), 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, inst.get("Senast kända kurs", 1.0), 0, 0, 0, 0,
            random.randint(0, int(tot_kompisar * 0.6)),
            random.randint(0, int(tot_pv * 0.6)),
            random.randint(0, int(tot_nv * 0.6)),
            random.randint(0, int(tot_nf * 0.6)),
            12, 1, 0
        ]
        scen_sheet.append_row(rad)
    st.success(f"{vilodagar} vilodagar på inspelningsplats genererade.")

if slump_hemma:
    rad = [
        str(datetime.now().date()), 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, inst.get("Senast kända kurs", 1.0), 0, 0, 0, 0,
        random.randint(0, int(inst.get("Totalt kompisar", 0) * 0.1)),
        random.randint(0, int(inst.get("Totalt pappans vänner", 0) * 0.1)),
        random.randint(0, int(inst.get("Totalt Nils vänner", 0) * 0.1)),
        random.randint(0, int(inst.get("Totalt Nils familj", 0) * 0.1)),
        8, 0, 0
    ]

    # Slumpa om Nils får sex med fru (0–2 gånger)
    nils_sex = random.randint(0, 2)
    for _ in range(nils_sex):
        scen_sheet.append_row(rad)
    st.success(f"7 vilodagar hemma genererade – Nils fick sex {nils_sex} gång(er).")

st.header("📊 Statistik")

try:
    data = scen_sheet.get_all_records()
    if not data:
        st.info("Inga scener har registrerats ännu.")
    else:
        df = pd.DataFrame(data)

        tot_man = df["Totala män"].sum()
        tot_komp = df["Kompisar (scen)"].sum()
        tot_pv = df["Pappans vänner"].sum()
        tot_nv = df["Nils vänner"].sum()
        tot_nf = df["Nils familj"].sum()

        tot_alskar = df["Älskar med"].sum()
        tot_sover = df["Sover med"].sum()

        tot_prenum = df["Prenumeranter"].sum()
        tot_intakt = df["Total intäkt"].sum()

        st.markdown(f"### 👥 Totalt antal män: `{int(tot_man + tot_komp)}`")
        st.markdown(f"- Kompisar: `{int(tot_komp)}`")
        st.markdown(f"- Pappans vänner: `{int(tot_pv)}`")
        st.markdown(f"- Nils vänner: `{int(tot_nv)}`")
        st.markdown(f"- Nils familj: `{int(tot_nf)}`")

        st.markdown("---")
        st.markdown(f"### ❤️ Totalt antal tillfällen")
        st.markdown(f"- Älskat med: `{int(tot_alskar)}`")
        st.markdown(f"- Sovit med: `{int(tot_sover)}` (endast Nils familj)")

        st.markdown("---")
        st.markdown(f"### 💵 Ekonomi")
        st.markdown(f"- Totala prenumeranter: `{int(tot_prenum)}`")
        st.markdown(f"- Total intäkt (USD): `${int(tot_intakt):,}`")

except Exception as e:
    st.error(f"Fel vid hämtning av statistik: {e}")
