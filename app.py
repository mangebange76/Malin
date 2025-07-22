import streamlit as st
import pandas as pd
import gspread
import random
from datetime import datetime
import time

st.set_page_config(page_title="Malin Scenplanering", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"

# Autentisering
gc = gspread.service_account_from_dict(st.secrets["GOOGLE_CREDENTIALS"])
sh = gc.open_by_url(SPREADSHEET_URL)

# ░▒▓ Skapa inställningsblad ▓▒░
def skapa_inställningsblad_om_saknas(gc, sh):
    try:
        inst_sheet = sh.worksheet("Inställningar")
    except:
        inst_sheet = sh.add_worksheet(title="Inställningar", rows="20", cols="3")
        inst_sheet.append_row(["Inställning", "Värde"])

    befintliga = {rad["Inställning"]: rad["Värde"] for rad in inst_sheet.get_all_records() if "Inställning" in rad}

    standardinställningar = {
        "Totalt kompisar": 0,
        "Totalt pappans vänner": 0,
        "Totalt Nils vänner": 0,
        "Totalt Nils familj": 0,
        "Senast kända kurs": 100.0,
        "Senaste prenumeranter": 0
    }

    for nyckel, värde in standardinställningar.items():
        if nyckel not in befintliga:
            inst_sheet.append_row([nyckel, värde])

    return sh.worksheet("Inställningar")

inst_sheet = skapa_inställningsblad_om_saknas(gc, sh)

# Läs in inställningar
inst = {}
for rad in inst_sheet.get_all_records():
    if "Inställning" in rad and "Värde" in rad:
        try:
            inst[rad["Inställning"]] = float(str(rad["Värde"]).replace(",", "."))
        except:
            inst[rad["Inställning"]] = rad["Värde"]

# För grunddata (maxgränser)
max_kompisar = int(inst.get("Totalt kompisar", 0))
max_pv = int(inst.get("Totalt pappans vänner", 0))
max_nv = int(inst.get("Totalt Nils vänner", 0))
max_nf = int(inst.get("Totalt Nils familj", 0))
startkurs = float(inst.get("Senast kända kurs", 100.0))

# Scenblad
try:
    scen_sheet = sh.worksheet("Scener")
except:
    scen_sheet = sh.add_worksheet(title="Scener", rows="1000", cols="30")
    scen_sheet.append_row([
        "Datum", "Totala män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vaginal", "Enkel anal", "DT-tid (sek)", "Tid (min)", "Tid (sek)", "Total_tid",
        "Tid/man (min)", "Prenumeranter", "Aktiekurs", "Intäkt ($)", "Kvinnans lön", "Mäns lön",
        "Komp lön", "Kompisar (scen)", "Pappans vänner", "Nils vänner", "Nils familj",
        "Älskar med", "Sover med", "DT total tid (sek)"
    ])

st.header("🎬 Lägg till ny scen")

with st.form("scen_form"):
    datum = st.date_input("Datum för scen", value=datetime.today())

    tot_man = st.number_input("Totalt antal män", min_value=1, value=100)
    dp = st.number_input("DP (2 män)", min_value=0)
    dpp = st.number_input("DPP", min_value=0)
    dap = st.number_input("DAP", min_value=0)
    tpa = st.number_input("TPA", min_value=0)
    tpp = st.number_input("TPP", min_value=0)
    tap = st.number_input("TAP", min_value=0)
    enkel_vag = st.number_input("Enkel vaginal", min_value=0)
    enkel_anal = st.number_input("Enkel anal", min_value=0)

    kompisar = st.number_input("Kompisar (scen)", min_value=0, max_value=max_kompisar)
    pv = st.number_input("Pappans vänner", min_value=0, max_value=max_pv)
    nv = st.number_input("Nils vänner", min_value=0, max_value=max_nv)
    nf = st.number_input("Nils familj", min_value=0, max_value=max_nf)

    alskar = st.number_input("Antal 'älskar med'", min_value=0, value=12)
    sover = st.number_input("Antal 'sover med'", min_value=0, value=1)

    tid_per_man_min = st.number_input("Tid per man (min)", min_value=0, value=8)
    tid_per_man_sek = st.number_input("Tid per man (sekunder)", min_value=0, value=0)
    dt_tid_per_man = st.number_input("Deep throat tid per man (sek)", min_value=0, value=10)
    filmpris = st.number_input("Pris per prenumeration ($)", min_value=0.0, value=15.0)

    submit = st.form_submit_button("Spara scen")

if submit:
    total_tid_min = (tid_per_man_min * tot_man) + (tid_per_man_sek * tot_man / 60)
    dt_total_tid = dt_tid_per_man * tot_man / 60
    total_tid = total_tid_min + dt_total_tid + (alskar + sover) * 15

    # Enkel modell för prenumeranter
    pren = (
        enkel_vag * 0.5 + enkel_anal * 0.5 +
        dp * 1.0 + dpp * 1.2 + dap * 1.2 +
        tpa * 1.6 + tpp * 1.6 + tap * 2.0
    )
    pren = round(pren)

    intakt = pren * filmpris
    kvinnan = 800
    man_loner = (tot_man - kompisar) * 200
    kvar = max(intakt - kvinnan - man_loner, 0)
    komp_lon = kvar / max_kompisar if max_kompisar else 0
    aktiekurs = startkurs + (pren - inst.get("Senaste prenumeranter", 0)) * 0.01

    # Spara till ark
    scen_sheet.append_row([
        str(datum), tot_man, dp, dpp, dap, tpa, tpp, tap,
        enkel_vag, enkel_anal, dt_tid_per_man, tid_per_man_min, tid_per_man_sek, total_tid,
        round(total_tid / tot_man, 2), pren, round(aktiekurs, 2), round(intakt, 2),
        kvinnan, man_loner, round(komp_lon, 2),
        kompisar, pv, nv, nf, alskar, sover, round(dt_tid_per_man * tot_man, 2)
    ])

    # Uppdatera senaste prenumeranter och kurs
    for i, rad in enumerate(inst_sheet.get_all_records(), start=2):
        if rad["Inställning"] == "Senaste prenumeranter":
            inst_sheet.update_cell(i, 2, pren)
        if rad["Inställning"] == "Senast kända kurs":
            inst_sheet.update_cell(i, 2, round(aktiekurs, 2))

    st.success("Scen sparad!")

def beräkna_total_tid(tot_man, tid_per_man_min, tid_per_man_sek, dt_tid_per_man, alskar, sover):
    # Grundläggande penetrationstid
    tid_man_tot = (tid_per_man_min * 60 + tid_per_man_sek) * tot_man

    # Deep throat total tid
    dt_total_tid = dt_tid_per_man * tot_man
    dt_vila = (tot_man - 1) * 2 + (tot_man // 10) * 30
    dt_tid_sum = dt_total_tid + dt_vila

    # Tid för älskar med / sover med (15 min = 900 sek per tillfälle)
    extra_tid = (alskar + sover) * 900

    total_tid_sek = tid_man_tot + dt_tid_sum + extra_tid
    return round(total_tid_sek / 60, 2), dt_total_tid  # i minuter + dt i sekunder

def beräkna_prenumeranter(enkel_vag, enkel_anal, dp, dpp, dap, tpa, tpp, tap):
    return round(
        enkel_vag * 0.5 + enkel_anal * 0.5 +
        dp * 1.0 + dpp * 1.2 + dap * 1.2 +
        tpa * 1.6 + tpp * 1.6 + tap * 2.0
    )

def beräkna_intakter(pren, filmpris, tot_man, kompisar, kvinnan, max_kompisar):
    intakt = pren * filmpris
    man_loner = (tot_man - kompisar) * 200
    kvar = max(intakt - kvinnan - man_loner, 0)
    komp_lon = kvar / max_kompisar if max_kompisar > 0 else 0
    return round(intakt, 2), man_loner, round(komp_lon, 2)

def beräkna_kurs(fg_pren, nya_pren, fg_kurs):
    diff = nya_pren - fg_pren
    ny_kurs = fg_kurs + diff * 0.01
    return round(ny_kurs, 2)

st.header("😴 Vilodagar och slumpmässiga tillfällen")

if "vilodata" not in st.session_state:
    st.session_state.vilodata = []

# Antal vilodagar på inspelningsplats
vilo_dagar = st.number_input("Antal vilodagar under inspelningsplats (max 21)", min_value=0, max_value=21, value=2)

if st.button("Generera slumpdata för vilodagar på inspelningsplats"):
    insp_data = {
        "Kompisar": random.randint(0, int(max_kompisar * 0.6)),
        "Pappans vänner": random.randint(0, int(max_pv * 0.6)),
        "Nils vänner": random.randint(0, int(max_nv * 0.6)),
        "Nils familj": random.randint(0, int(max_nf * 0.6)),
        "Älskar med": 12,
        "Sover med": 1,
        "Typ": "Inspelningsplats",
        "Vilodagar": vilo_dagar
    }
    st.session_state.vilodata.append(insp_data)
    st.success("Slumpad vilodata genererad för inspelningsplats")

if st.button("Generera vilodagar hemma (alltid 7 dagar)"):
    hemma_data = {
        "Kompisar": random.randint(0, int(max_kompisar * 0.1)),
        "Pappans vänner": random.randint(0, int(max_pv * 0.1)),
        "Nils vänner": random.randint(0, int(max_nv * 0.1)),
        "Nils familj": random.randint(0, int(max_nf * 0.1)),
        "Älskar med": 8,
        "Sover med": 0,
        "Typ": "Hemma",
        "Vilodagar": 7,
        "Nils fick sex": random.choice([0, 1, 2])
    }
    st.session_state.vilodata.append(hemma_data)
    st.success("Slumpad vilodata genererad för hemmavistelse")

if st.session_state.vilodata:
    st.subheader("⏱️ Summering av genererad vilodata")
    df_vilo = pd.DataFrame(st.session_state.vilodata)
    st.dataframe(df_vilo)

    # Här kan du spara df_vilo till nytt blad om du vill

st.header("📊 Statistik & summering")

try:
    df = pd.DataFrame(scen_sheet.get_all_records())

    if not df.empty:
        df["Totala män"] = pd.to_numeric(df["Totala män"], errors="coerce").fillna(0)
        df["Kompisar (scen)"] = pd.to_numeric(df["Kompisar (scen)"], errors="coerce").fillna(0)
        df["Pappans vänner"] = pd.to_numeric(df["Pappans vänner"], errors="coerce").fillna(0)
        df["Nils vänner"] = pd.to_numeric(df["Nils vänner"], errors="coerce").fillna(0)
        df["Nils familj"] = pd.to_numeric(df["Nils familj"], errors="coerce").fillna(0)
        df["Älskar med"] = pd.to_numeric(df["Älskar med"], errors="coerce").fillna(0)
        df["Sover med"] = pd.to_numeric(df["Sover med"], errors="coerce").fillna(0)
        df["Total_tid"] = pd.to_numeric(df["Total_tid"], errors="coerce").fillna(0)
        df["DT total tid (sek)"] = pd.to_numeric(df["DT total tid (sek)"], errors="coerce").fillna(0)

        total_man = int(df["Totala män"].sum())
        total_komp = int(df["Kompisar (scen)"].sum())
        total_pv = int(df["Pappans vänner"].sum())
        total_nv = int(df["Nils vänner"].sum())
        total_nf = int(df["Nils familj"].sum())

        total_alskar = int(df["Älskar med"].sum())
        total_sover = int(df["Sover med"].sum())

        total_tid = round(df["Total_tid"].sum(), 2)
        total_dt_tid_min = round(df["DT total tid (sek)"].sum() / 60, 2)

        st.subheader("👥 Deltagare")
        st.write(f"Totalt antal män: **{total_man}**")
        st.write(f"Kompisar: **{total_komp}**")
        st.write(f"Pappans vänner: **{total_pv}**")
        st.write(f"Nils vänner: **{total_nv}**")
        st.write(f"Nils familj: **{total_nf}**")

        st.subheader("💞 Närhet")
        st.write(f"Älskat med: **{total_alskar}** gånger")
        st.write(f"Sovit med: **{total_sover}** gånger (endast Nils familj)")

        st.subheader("⏱️ Total tidsåtgång")
        st.write(f"Total scen-tid: **{total_tid} minuter**")
        st.write(f"Deep throat-tid: **{total_dt_tid_min} minuter**")

    else:
        st.info("Ingen scendata tillgänglig ännu.")

except Exception as e:
    st.error(f"Fel vid hämtning av statistik: {e}")
