import streamlit as st
import pandas as pd
import datetime
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="MalinApp", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SPREADSHEET_URL)

def get_or_create_worksheet(sh, name, headers):
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows="1000", cols=str(len(headers)))
        ws.append_row(headers)
    return ws

def läs_inställningar():
    inst_ws = get_or_create_worksheet(sh, "Inställningar", ["Inställning", "Värde"])
    inst_data = inst_ws.get_all_records()
    inst = {}
    for rad in inst_data:
        värde_str = str(rad["Värde"]).replace(",", ".")
        try:
            inst[rad["Inställning"]] = float(värde_str)
        except ValueError:
            inst[rad["Inställning"]] = rad["Värde"]
    return inst

def spara_inställningar(inst):
    inst_ws = get_or_create_worksheet(sh, "Inställningar", ["Inställning", "Värde"])
    inst_ws.clear()
    inst_ws.append_row(["Inställning", "Värde"])
    for k, v in inst.items():
        inst_ws.append_row([k, v])

inst = läs_inställningar()

# Sidopanel för inställningar
with st.sidebar:
    st.header("🔧 Inställningar")
    startdatum = st.text_input("Startdatum (ÅÅÅÅ-MM-DD)", value=inst.get("Startdatum", "2014-03-26"))
    namn = st.text_input("Kvinnans namn", value=inst.get("Namn", "Malin"))
    födelse = st.text_input("Födelsedatum (ÅÅÅÅ-MM-DD)", value=inst.get("Födelsedatum", "1984-03-26"))

    kompisar = st.number_input("Totalt antal kompisar", min_value=0, value=int(inst.get("Kompisar", 0)))
    pappans_vänner = st.number_input("Totalt antal pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 0)))
    nils_vänner = st.number_input("Totalt antal Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 0)))
    nils_familj = st.number_input("Totalt antal Nils familj", min_value=0, value=int(inst.get("Nils familj", 0)))

    om_spara = st.button("Spara inställningar")
    if om_spara:
        inst.update({
            "Startdatum": startdatum,
            "Namn": namn,
            "Födelsedatum": födelse,
            "Kompisar": kompisar,
            "Pappans vänner": pappans_vänner,
            "Nils vänner": nils_vänner,
            "Nils familj": nils_familj
        })
        spara_inställningar(inst)
        st.success("Inställningar sparade!")
        st.rerun()

# Skapa huvuddatan vid behov
huvud_headers = [
    "Datum", "Typ", "Män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Vaginal (enkel)", "Anal (enkel)",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "Tid per man (min)", "Tid per man (sek)", "Deep throat (sek)", "DT total tid (sek)",
    "DT vilotid (sek)", "DT män", "Total tid (sek)",
    "Älskar med", "Sover med", "Intäkt bolag", "Intäkt kvinna", "Intäkt män", "Intäkt kompisar", "Prenumeranter", "Aktiekurs"
]
df_ws = get_or_create_worksheet(sh, "Data", huvud_headers)
data = df_ws.get_all_records()
df = pd.DataFrame(data)

st.subheader("🎬 Lägg till ny scen")

today = pd.to_datetime(df["Datum"].max(), errors="coerce") if not df.empty else pd.to_datetime(inst["Startdatum"])
nästa_datum = today + pd.Timedelta(days=1)
st.markdown(f"Nästa datum: **{nästa_datum.strftime('%Y-%m-%d')}**")

med_typ = st.selectbox("Typ av rad", ["Scen", "Vila inspelningsplats", "Vila hem"])
antal_män = st.number_input("Antal män", min_value=0, value=0)
dp = st.number_input("DP", min_value=0, value=0)
dpp = st.number_input("DPP", min_value=0, value=0)
dap = st.number_input("DAP", min_value=0, value=0)
tpa = st.number_input("TPA", min_value=0, value=0)
tpp = st.number_input("TPP", min_value=0, value=0)
tap = st.number_input("TAP", min_value=0, value=0)
vag = st.number_input("Enkel vaginal", min_value=0, value=0)
anal = st.number_input("Enkel anal", min_value=0, value=0)

kompisar_raden = st.number_input("Kompisar (scennivå)", min_value=0, max_value=int(inst["Kompisar"]), value=0)
pappans_raden = st.number_input("Pappans vänner (scennivå)", min_value=0, max_value=int(inst["Pappans vänner"]), value=0)
nils_raden = st.number_input("Nils vänner (scennivå)", min_value=0, max_value=int(inst["Nils vänner"]), value=0)
nilsfam_raden = st.number_input("Nils familj (scennivå)", min_value=0, max_value=int(inst["Nils familj"]), value=0)

tid_man_min = st.number_input("Tid per man (minuter)", min_value=0.0, value=8.0, step=0.5)
dt_tid = st.number_input("Deep throat per man (sek)", min_value=0, value=30)

alskar_med = st.number_input("Älskar med", min_value=0, value=0)
sover_med = st.number_input("Sover med", min_value=0, value=0)

def beräkna_total_tid():
    tid_per_man_sec = tid_man_min * 60
    total_tid_sec = 0

    # Trippelpenetrationer (3 män, 2 min per trio)
    trippel_tid = (tpa + tpp + tap) * (2 * 60 + 15)

    # Dubbelpenetrationer (2 män, 2 min per duo)
    dubbel_tid = (dp + dpp + dap) * (2 * 60 + 15)

    # Enkelpenetrationer (vaginal + anal)
    enkel_tid = (vag + anal) * (2 * 60 + 15)

    total_tid_sec += trippel_tid + dubbel_tid + enkel_tid

    # Deep throat total tid + vila
    tot_män = antal_män + kompisar_raden + pappans_raden + nils_raden + nilsfam_raden
    dt_total = dt_tid * tot_män
    dt_vila = (tot_män - 1) * 2 + (tot_män // 10) * 30

    total_tid_sec += dt_total + dt_vila

    # Älskar med + sover med (vardera 15 min per person)
    extra_tid = (alskar_med + sover_med) * 15 * 60
    total_tid_sec += extra_tid

    return total_tid_sec, tid_per_man_sec, dt_total, dt_vila, tot_män

if st.button("Spara scenrad"):
    total_tid, tid_man_sec, dt_total, dt_vila, dt_män = beräkna_total_tid()
    intakt_kvinna = 800
    intakt_man = (antal_män - kompisar_raden) * 200
    intakt_total = antal_män * 15  # 15 USD per prenumerant

    intakt_kompisar = max(0, intakt_total - intakt_kvinna - intakt_man)
    if inst["Kompisar"] > 0:
        intakt_kompisar = intakt_kompisar / inst["Kompisar"]

    ny_rad = [
        nästa_datum.strftime('%Y-%m-%d'), med_typ, antal_män,
        dp, dpp, dap, tpa, tpp, tap, vag, anal,
        kompisar_raden, pappans_raden, nils_raden, nilsfam_raden,
        tid_man_min, tid_man_sec, dt_tid, dt_total,
        dt_vila, dt_män, total_tid,
        alskar_med, sover_med,
        intakt_total, intakt_kvinna, intakt_man, round(intakt_kompisar, 2),
        antal_män, 0  # aktiekurs sätts senare
    ]
    df_ws.append_row(ny_rad)
    st.success("Rad sparad!")
    st.rerun()

st.header("📊 Statistik")

if not df.empty:
    df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")
    sista_datum = df["Datum"].max()
    ålder = None
    try:
        födelse_dt = pd.to_datetime(inst.get("Födelsedatum"))
        ålder = int((sista_datum - födelse_dt).days / 365.25)
    except:
        ålder = "?"

    st.subheader(f"{inst.get('Namn', 'Kvinnan')} – Ålder {ålder} år")

    total_tid = df["Total tid (sek)"].sum()
    timmar = total_tid // 3600
    minuter = (total_tid % 3600) // 60
    st.markdown(f"**Total inspelad tid:** {int(timmar)} h {int(minuter)} min")

    st.markdown(f"**Totalt antal män:** {df['Män'].sum()}")
    st.markdown(f"**Totala deep throat-män:** {df['DT män'].sum()}")
    st.markdown(f"**Totalt antal älskar med:** {df['Älskar med'].sum()}")
    st.markdown(f"**Totalt antal sover med:** {df['Sover med'].sum()}")

    for kategori in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        st.markdown(f"**{kategori} gangbang-tillfällen:** {df[kategori].sum()}")

else:
    st.info("Ingen data ännu – lägg till en scen först.")
