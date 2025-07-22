import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="Malin - Beräkning och statistik", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(SPREADSHEET_URL)

def get_or_create_worksheet(sheet, name, headers=None):
    try:
        return sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=1000, cols=50)
        if headers:
            ws.append_row(headers)
        return ws

# Funktion för att läsa inställningar
def läs_inställningar():
    inst_ws = get_or_create_worksheet(sh, "Inställningar", ["Inställning", "Värde"])
    inst_data = inst_ws.get_all_records()
    inst = {
        rad["Inställning"]: float(rad["Värde"].replace(",", "."))
        if rad["Värde"].replace(",", "").replace(".", "", 1).isdigit()
        else rad["Värde"]
        for rad in inst_data
    }
    return inst

inst = läs_inställningar()

# Skapa nödvändiga blad
scener_headers = [
    "Datum", "Män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man (sek)", "Älskar med", "Sover med",
    "Total penetrationstid (sek)", "DT total tid (sek)", "Total tid per man (min)",
    "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Prenumeranter", "Ack prenumeranter", "Aktiekurs ($)"
]

get_or_create_worksheet(sh, "Scener", scener_headers)

# Inställningspanel
st.sidebar.header("Inställningar")

startdatum = st.sidebar.date_input("Startdatum", value=datetime.today(), format="YYYY-MM-DD")
kv_namn = st.sidebar.text_input("Kvinnans namn", value=inst.get("Namn", "Malin"))
kv_födelse = st.sidebar.date_input("Födelsedatum", value=datetime(1984, 3, 26), format="YYYY-MM-DD")

kompisar = st.sidebar.number_input("Kompisar (totalt)", value=int(inst.get("Kompisar", 0)), min_value=0)
pvänner = st.sidebar.number_input("Pappans vänner (totalt)", value=int(inst.get("Pappans vänner", 0)), min_value=0)
nvänner = st.sidebar.number_input("Nils vänner (totalt)", value=int(inst.get("Nils vänner", 0)), min_value=0)
nfamilj = st.sidebar.number_input("Nils familj (totalt)", value=int(inst.get("Nils familj", 0)), min_value=0)
startkurs = st.sidebar.number_input("Startkurs ($)", value=float(inst.get("Startkurs", 1.00)), format="%.2f")

if st.sidebar.button("Spara inställningar"):
    inst_ws = sh.worksheet("Inställningar")
    inst_lista = [
        ["Startdatum", str(startdatum)],
        ["Namn", kv_namn],
        ["Födelsedatum", str(kv_födelse)],
        ["Kompisar", kompisar],
        ["Pappans vänner", pvänner],
        ["Nils vänner", nvänner],
        ["Nils familj", nfamilj],
        ["Startkurs", round(startkurs, 2)]
    ]
    inst_ws.clear()
    inst_ws.append_row(["Inställning", "Värde"])
    for rad in inst_lista:
        inst_ws.append_row(rad)
    st.success("Inställningar sparade. Starta om appen.")
    st.rerun()

# Funktion för att hämta nästa datum
def hämta_nästa_datum():
    ws = sh.worksheet("Scener")
    data = ws.get_all_values()
    if len(data) > 1:
        sista_datum = data[-1][0]
        try:
            dt = datetime.strptime(sista_datum, "%Y-%m-%d") + timedelta(days=1)
        except:
            dt = datetime.strptime(inst.get("Startdatum"), "%Y-%m-%d")
    else:
        dt = datetime.strptime(inst.get("Startdatum"), "%Y-%m-%d")
    return dt

nästa_datum = hämta_nästa_datum()

def läs_df():
    ws = get_or_create_worksheet(sh, "Scener", [
        "Datum", "Män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
        "DT per man (sek)", "Älskar med", "Sover med", "Total tid (sek)", "DT total tid (sek)",
        "Total tid per man (min)", "Intäkt", "Kvinnans lön", "Mäns lön", "Kompisar lön",
        "Typ", "Nils sex", "Kommentar"
    ])
    data = ws.get_all_records()
    return pd.DataFrame(data)

df = läs_df()
df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")
senaste_datum = df["Datum"].max() if not df.empty else pd.to_datetime(inst.get("Startdatum", "2014-03-26"))
nästa_datum = senaste_datum + timedelta(days=1)

# Visa kvinnans namn och nuvarande ålder
födelsedatum = pd.to_datetime(inst.get("Födelsedatum", "1984-03-26"), errors="coerce")
namn = inst.get("Namn", "Malin")
ålder = (nästa_datum - födelsedatum).days // 365 if pd.notnull(födelsedatum) else "?"

st.sidebar.markdown(f"👩 **{namn}, {ålder} år**")
st.sidebar.markdown(f"🎬 Nästa datum: {nästa_datum.date()}")

# Vilodagar – inspelningsplats
st.subheader("Lägg till vilodagar (inspelning)")

with st.form("vila_insp"):
    vilodagar = st.number_input("Antal vilodagar", min_value=1, max_value=21)
    gen_knapp = st.form_submit_button("Generera data")

if gen_knapp:
    import random
    nya_rader = []
    for i in range(vilodagar):
        datum = nästa_datum + timedelta(days=i)
        ny_rad = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Män": 0, "DP": 0, "DPP": 0, "DAP": 0, "TPA": 0, "TPP": 0, "TAP": 0,
            "Enkel vaginal": 0, "Enkel anal": 0,
            "Kompisar": random.randint(0, round(inst.get("Kompisar", 0)*0.6)),
            "Pappans vänner": random.randint(0, round(inst.get("Pappans vänner", 0)*0.6)),
            "Nils vänner": random.randint(0, round(inst.get("Nils vänner", 0)*0.6)),
            "Nils familj": random.randint(0, round(inst.get("Nils familj", 0)*0.6)),
            "DT per man (sek)": 0, "Älskar med": 12, "Sover med": 1,
            "Total tid (sek)": 0, "DT total tid (sek)": 0,
            "Total tid per man (min)": 0,
            "Intäkt": 0, "Kvinnans lön": 0, "Mäns lön": 0, "Kompisar lön": 0,
            "Typ": "Vila inspelning", "Nils sex": "", "Kommentar": ""
        }
        nya_rader.append(ny_rad)

    ws = sh.worksheet("Scener")
    for rad in nya_rader:
        ws.append_row(list(rad.values()))
    st.success(f"{vilodagar} vilodagar sparade")
    st.rerun()

st.subheader("➕ Lägg till ny scen")

with st.form("ny_scen"):
    antal_män = st.number_input("Antal män", min_value=0)
    dp = st.number_input("DP", min_value=0)
    dpp = st.number_input("DPP", min_value=0)
    dap = st.number_input("DAP", min_value=0)
    tpa = st.number_input("TPA", min_value=0)
    tpp = st.number_input("TPP", min_value=0)
    tap = st.number_input("TAP", min_value=0)
    enkel_vag = st.number_input("Enkel vaginal", min_value=0)
    enkel_anal = st.number_input("Enkel anal", min_value=0)
    dt_tid = st.number_input("Deep throat per man (sek)", min_value=0)
    älskar_med = st.number_input("Antal 'älskar med'", min_value=0)
    sover_med = st.number_input("Antal 'sover med'", min_value=0)
    nils_sex = st.selectbox("Nils har sex med henne?", ["Ja", "Nej", "Slumpas"])
    kompisar = st.number_input("Kompisar (antal i scen)", min_value=0, max_value=int(inst.get("Kompisar", 0)))
    pappans_vänner = st.number_input("Pappans vänner (antal)", min_value=0, max_value=int(inst.get("Pappans vänner", 0)))
    nils_vänner = st.number_input("Nils vänner (antal)", min_value=0, max_value=int(inst.get("Nils vänner", 0)))
    nils_familj = st.number_input("Nils familj (antal)", min_value=0, max_value=int(inst.get("Nils familj", 0)))
    tid_per_man_min = st.number_input("Tid varje man får – minuter", min_value=0)
    tid_per_man_sek = st.number_input("Tid varje man får – sekunder", min_value=0, max_value=59)
    submit = st.form_submit_button("Spara scen")

if submit:
    total_män = antal_män + kompisar + pappans_vänner + nils_vänner + nils_familj
    tid_per_man = tid_per_man_min * 60 + tid_per_man_sek
    tid_total = (total_män * tid_per_man) + (max(0, total_män - 1) * 15)
    dt_total = total_män * dt_tid + max(0, total_män - 1) * 2 + (total_män // 10) * 30
    älskar_tid = (älskar_med + sover_med) * 15 * 60
    summa_tid = tid_total + dt_total + älskar_tid
    tid_per_man_total = summa_tid / total_män / 60 if total_män > 0 else 0

    # Intäkter
    pris = 15  # prenumeration
    multiplikator = (1 * (dp + dpp + dap) + 2 * (tpa + tpp) + 3 * tap + 0.5 * (enkel_vag + enkel_anal))
    subs = int(multiplikator * total_män)
    intäkt = subs * pris
    kvinnans_lön = 800
    män_lön = (total_män - kompisar) * 200
    kompis_lön = max(0, intäkt - kvinnans_lön - män_lön) / inst.get("Kompisar", 1)

    # Nils sex slump
    if nils_sex == "Slumpas":
        nils_sex = "Ja" if random.random() < 0.5 else "Nej"

    ny_rad = {
        "Datum": nästa_datum.strftime("%Y-%m-%d"),
        "Män": antal_män, "DP": dp, "DPP": dpp, "DAP": dap, "TPA": tpa, "TPP": tpp, "TAP": tap,
        "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
        "Kompisar": kompisar, "Pappans vänner": pappans_vänner, "Nils vänner": nils_vänner, "Nils familj": nils_familj,
        "DT per man (sek)": dt_tid, "Älskar med": älskar_med, "Sover med": sover_med,
        "Total tid (sek)": round(summa_tid), "DT total tid (sek)": round(dt_total),
        "Total tid per man (min)": round(tid_per_man_total, 2),
        "Intäkt": round(intäkt), "Kvinnans lön": kvinnans_lön,
        "Mäns lön": män_lön, "Kompisar lön": round(kompis_lön),
        "Typ": "Scen", "Nils sex": nils_sex, "Kommentar": ""
    }

    ws = sh.worksheet("Scener")
    ws.append_row(list(ny_rad.values()))
    st.success("Scen sparad")
    st.rerun()

st.subheader("📊 Statistik")

if df.empty:
    st.info("Ingen data ännu.")
else:
    df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")

    total_män = df["Män"].sum() + df["Kompisar"].sum() + df["Pappans vänner"].sum() + df["Nils vänner"].sum() + df["Nils familj"].sum()
    total_älskat = df["Älskar med"].sum()
    total_sovit = df[df["Typ"] != "Vila hem"].get("Sover med", pd.Series(0)).sum()

    def summera_ggr(df, kolumn):
        return df[kolumn][df[kolumn] > 0].count()

    stats = {
        "Totalt antal män": total_män,
        "Totalt antal scener": df[df["Typ"] == "Scen"].shape[0],
        "Totalt antal vilodagar": df[df["Typ"].str.startswith("Vila")].shape[0],
        "Totalt antal 'älskar med'": total_älskat,
        "Totalt antal 'sover med' (Nils familj)": total_sovit,
        "Gånger pappans vänner deltagit": summera_ggr(df, "Pappans vänner"),
        "Gånger kompisar deltagit": summera_ggr(df, "Kompisar"),
        "Gånger Nils vänner deltagit": summera_ggr(df, "Nils vänner"),
        "Gånger Nils familj deltagit": summera_ggr(df, "Nils familj")
    }

    for k, v in stats.items():
        st.markdown(f"**{k}:** {v}")

    # Visa datatabell
    with st.expander("Visa rådata"):
        st.dataframe(df)
