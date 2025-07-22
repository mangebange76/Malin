import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Fil och blad
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
SPREADSHEET_NAME = "MalinData2"
sh = gc.open_by_url(SPREADSHEET_URL)

# Initiera blad
def init_sheet(name, cols):
    try:
        sh.worksheet(name)
    except:
        sh.add_worksheet(title=name, rows="1000", cols="30")
        sh.values_update(name, {"range": "A1", "majorDimension": "ROWS", "values": [cols]})

init_sheet("Data", [
    "Datum", "Typ", "Män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP", "Vaginal", "Anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "Tid per man (min)", "DT tid (sek)", "DT män", "DT total tid (sek)",
    "Älskar med", "Sover med", "Total tid (sek)", "Intäkt (USD)",
    "Kvinna lön", "Män lön", "Kompis lön", "Prenumeranter", "Kurs"
])

init_sheet("Inställningar", [
    "Inställning", "Värde", "Senast ändrad"
])

# Funktion: Läs inställningar från bladet
def läs_inställningar():
    inst_df = pd.DataFrame(sh.worksheet("Inställningar").get_all_records())
    inst = {
        rad["Inställning"]: float(str(rad["Värde"]).replace(",", "."))
        if str(rad["Värde"]).replace(",", "").replace(".", "", 1).isdigit()
        else rad["Värde"]
        for _, rad in inst_df.iterrows()
    }
    return inst

# Funktion: Spara inställning
def spara_inställning(namn, värde):
    inst_df = pd.DataFrame(sh.worksheet("Inställningar").get_all_records())
    if namn in inst_df["Inställning"].values:
        idx = inst_df[inst_df["Inställning"] == namn].index[0]
        inst_df.at[idx, "Värde"] = värde
        inst_df.at[idx, "Senast ändrad"] = datetime.now().strftime("%Y-%m-%d")
    else:
        inst_df = inst_df.append({
            "Inställning": namn,
            "Värde": värde,
            "Senast ändrad": datetime.now().strftime("%Y-%m-%d")
        }, ignore_index=True)
    sh.worksheet("Inställningar").update([inst_df.columns.values.tolist()] + inst_df.values.tolist())

# Läser inställningar in i appen
inst = läs_inställningar()

# Sidopanel: Grundinställningar
st.sidebar.header("⚙️ Inställningar")

startdatum = st.sidebar.text_input("Startdatum (t.ex. 2014-03-26)", value=inst.get("Startdatum", "2014-03-26"))
spara_inställning("Startdatum", startdatum)

namn = st.sidebar.text_input("Namn", value=inst.get("Namn", "Malin"))
spara_inställning("Namn", namn)

födelsedatum = st.sidebar.text_input("Födelsedatum (t.ex. 1984-03-26)", value=inst.get("Födelsedatum", "1984-03-26"))
spara_inställning("Födelsedatum", födelsedatum)

for kategori in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
    antal = int(st.sidebar.number_input(f"Antal {kategori}", min_value=0, value=int(inst.get(kategori, 0))))
    spara_inställning(kategori, antal)

# Prenumerationsvikter
st.sidebar.subheader("📈 Prenumerationsvikter")
for typ in ["Vaginal", "Anal", "DP", "DPP", "DAP", "TPA", "TPP", "TAP"]:
    vikt = float(st.sidebar.number_input(f"Vikt {typ}", value=float(inst.get(f"Vikt_{typ}", 1.0)), step=0.1))
    spara_inställning(f"Vikt_{typ}", vikt)

# Startkurs
startkurs = float(st.sidebar.number_input("Startkurs", value=float(inst.get("Startkurs", 1.0)), step=0.01))
spara_inställning("Startkurs", startkurs)

# Funktion: Hämta DataFrame från databladet
def hämta_data():
    data = sh.worksheet("Data").get_all_records()
    return pd.DataFrame(data)

df = hämta_data()

def sista_datum(df):
    if not df.empty:
        return pd.to_datetime(df["Datum"].iloc[-1])
    else:
        return pd.to_datetime(inst["Startdatum"])

def beräkna_tid(man_tid_min, dt_tid_sek, antal_män):
    dt_total = dt_tid_sek * antal_män + (antal_män * 2) + (antal_män // 10 * 30)
    total = (man_tid_min * 60 * antal_män) + dt_total
    return total, dt_total

def beräkna_prenumeranter(rad, inst):
    pren = 0
    for typ in ["Vaginal", "Anal", "DP", "DPP", "DAP", "TPA", "TPP", "TAP"]:
        pren += rad[typ] * inst.get(f"Vikt_{typ}", 1.0)
    return round(pren)

st.header("➕ Lägg till scen")

med_sc = st.checkbox("Ny scen")
med_vila = st.checkbox("Lägg till vilodagar")

if med_sc:
    st.subheader("Ny scen")

    datum = (sista_datum(df) + timedelta(days=1)).strftime("%Y-%m-%d")
    män = st.number_input("Totalt antal män", min_value=0)
    dp = st.number_input("DP", min_value=0)
    dpp = st.number_input("DPP", min_value=0)
    dap = st.number_input("DAP", min_value=0)
    tpa = st.number_input("TPA", min_value=0)
    tpp = st.number_input("TPP", min_value=0)
    tap = st.number_input("TAP", min_value=0)
    vaginal = st.number_input("Enkel vaginal", min_value=0)
    anal = st.number_input("Enkel anal", min_value=0)

    kompisar = st.number_input("Kompisar (scennivå)", min_value=0, max_value=int(inst["Kompisar"]))
    pappans = st.number_input("Pappans vänner (scennivå)", min_value=0, max_value=int(inst["Pappans vänner"]))
    nils_vänner = st.number_input("Nils vänner", min_value=0, max_value=int(inst["Nils vänner"]))
    nils_familj = st.number_input("Nils familj", min_value=0, max_value=int(inst["Nils familj"]))

    tid_per_man = st.number_input("Tid per man (minuter)", min_value=0.0)
    dt_tid = st.number_input("Deep throat-tid per man (sek)", min_value=0.0)

    älskar_med = st.number_input("Antal 'älskar med'", min_value=0)
    sover_med = st.number_input("Antal 'sover med'", min_value=0)

    # Summering
    totalt_antal_män = män + kompisar + pappans + nils_vänner + nils_familj
    total_tid, dt_total_tid = beräkna_tid(tid_per_man, dt_tid, totalt_antal_män)
    totalt_tid_m_älskar = total_tid + ((älskar_med + sover_med) * 15 * 60)

    intakt = beräkna_prenumeranter({
        "Vaginal": vaginal, "Anal": anal,
        "DP": dp, "DPP": dpp, "DAP": dap,
        "TPA": tpa, "TPP": tpp, "TAP": tap
    }, inst) * 15

    kvinnolön = 800
    mänlön = män * 200
    kompislön = max(0, intakt - kvinnolön - mänlön) / max(1, int(inst["Kompisar"]))

    ny_rad = {
        "Datum": datum, "Typ": "Scen", "Män": män, "DP": dp, "DPP": dpp, "DAP": dap,
        "TPA": tpa, "TPP": tpp, "TAP": tap, "Vaginal": vaginal, "Anal": anal,
        "Kompisar": kompisar, "Pappans vänner": pappans, "Nils vänner": nils_vänner, "Nils familj": nils_familj,
        "Tid per man (min)": tid_per_man, "DT tid (sek)": dt_tid, "DT män": totalt_antal_män,
        "DT total tid (sek)": dt_total_tid, "Älskar med": älskar_med, "Sover med": sover_med,
        "Total tid (sek)": totalt_tid_m_älskar,
        "Intäkt (USD)": intakt, "Kvinna lön": kvinnolön, "Män lön": mänlön,
        "Kompis lön": kompislön, "Prenumeranter": beräkna_prenumeranter({
            "Vaginal": vaginal, "Anal": anal, "DP": dp, "DPP": dpp, "DAP": dap,
            "TPA": tpa, "TPP": tpp, "TAP": tap
        }, inst),
        "Kurs": 0
    }

    if st.button("Spara scen"):
        df = df.append(ny_rad, ignore_index=True)
        sh.worksheet("Data").update([df.columns.tolist()] + df.values.tolist())
        st.rerun()

if med_vila:
    st.subheader("Vilodagar")

    dagar = st.number_input("Antal vilodagar", min_value=1)
    plats = st.radio("Plats", ["Inspelningsplats (21 dagar)", "Hem (7 dagar)"])

    datum = (sista_datum(df) + timedelta(days=1)).strftime("%Y-%m-%d")

    if plats == "Inspelningsplats (21 dagar)":
        max_procent = 0.6
        älskar_med = 12
        sover_med = 1
    else:
        max_procent = 0.1
        älskar_med = 8
        sover_med = 0

    totaler = {
        "Kompisar": inst["Kompisar"],
        "Pappans vänner": inst["Pappans vänner"],
        "Nils vänner": inst["Nils vänner"],
        "Nils familj": inst["Nils familj"]
    }

    import random
    nils_sex = 0
    if plats == "Hem (7 dagar)":
        nils_sex = random.randint(0, 2)

    if st.button("Generera vilodata"):
        for i in range(dagar):
            rand_rad = {
                "Datum": (pd.to_datetime(datum) + timedelta(days=i)).strftime("%Y-%m-%d"),
                "Typ": "Vila",
                "Män": 0, "DP": 0, "DPP": 0, "DAP": 0, "TPA": 0, "TPP": 0, "TAP": 0,
                "Vaginal": 0, "Anal": 0,
                "Kompisar": random.randint(0, int(totaler["Kompisar"] * max_procent)),
                "Pappans vänner": random.randint(0, int(totaler["Pappans vänner"] * max_procent)),
                "Nils vänner": random.randint(0, int(totaler["Nils vänner"] * max_procent)),
                "Nils familj": random.randint(0, int(totaler["Nils familj"] * max_procent)),
                "Tid per man (min)": 0, "DT tid (sek)": 0, "DT män": 0, "DT total tid (sek)": 0,
                "Älskar med": älskar_med,
                "Sover med": sover_med,
                "Total tid (sek)": 0,
                "Intäkt (USD)": 0, "Kvinna lön": 0, "Män lön": 0, "Kompis lön": 0,
                "Prenumeranter": 0, "Kurs": 0,
                "Nils sex hemma": nils_sex if i == 0 else 0
            }
            df = df.append(rand_rad, ignore_index=True)

        sh.worksheet("Data").update([df.columns.tolist()] + df.values.tolist())
        st.rerun()

# 🔍 Statistik
st.header("📊 Statistik")

antal_män = df["Män"].sum()
antal_älskar = df["Älskar med"].sum()
antal_sover = df["Sover med"].sum()

vänner = {
    "Kompisar": df["Kompisar"].sum(),
    "Pappans vänner": df["Pappans vänner"].sum(),
    "Nils vänner": df["Nils vänner"].sum(),
    "Nils familj": df["Nils familj"].sum(),
}

st.markdown(f"""
- 👩 Namn: **{inst['Namn']}**
- 🎂 Nuvarande ålder: **{(pd.to_datetime(df['Datum'].iloc[-1]) - pd.to_datetime(inst['Födelsedatum'])).days // 365} år**
- 📅 Senaste datum: **{df['Datum'].iloc[-1]}**
- 🔢 Totalt antal män: **{antal_män}**
- ❤️ Älskat med: **{antal_älskar}**
- 💤 Sovit med: **{antal_sover}**
""")

for kategori, värde in vänner.items():
    st.markdown(f"- 👥 {kategori}: **{värde} gånger**")

# 🧮 Funktion för kursuppdatering
def uppdatera_kurs(df, inst):
    df = df.copy()
    df["Kurs"] = 0.0
    kurs = inst.get("Startkurs", 1.0)
    total_aktier = 100000

    for i, rad in df.iterrows():
        if i == 0:
            df.at[i, "Kurs"] = kurs
            continue
        pren_idag = rad["Prenumeranter"]
        pren_igår = df.at[i - 1, "Prenumeranter"]
        if pren_igår == 0:
            df.at[i, "Kurs"] = kurs
        else:
            kurs *= (pren_idag / pren_igår)
            df.at[i, "Kurs"] = kurs
    return df

# 💾 Spara kursuppdatering
if st.button("🔄 Uppdatera aktiekurs & prenumeranter"):
    df = uppdatera_kurs(df, inst)
    sh.worksheet("Data").update([df.columns.tolist()] + df.values.tolist())
    st.success("Kurs och prenumeranter uppdaterade.")
    st.rerun()

# 🗃️ Export eller inspektion av data
st.subheader("📄 Rådata")
st.dataframe(df)
