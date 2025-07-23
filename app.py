import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample, randint
import math

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Spreadsheet
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumner
DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "Älskar med", "Sover med", "Nils sex",
    "DT tid per man (sek)", "DT total tid (sek)", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Minuter per kille", "Scenens längd (h)"
]

INST_COLUMNS = ["Inställning", "Värde", "Senast ändrad"]

def init_sheet(name, cols):
    try:
        worksheet = sh.worksheet(name)
    except:
        worksheet = sh.add_worksheet(title=name, rows="1000", cols="30")
        worksheet.update("A1", [cols])
    else:
        existing_cols = worksheet.row_values(1)
        if existing_cols != cols:
            worksheet.resize(rows=1)
            worksheet.update("A1", [cols])

def init_inställningar():
    try:
        worksheet = sh.worksheet("Inställningar")
    except:
        worksheet = sh.add_worksheet(title="Inställningar", rows="100", cols="3")
        worksheet.update("A1", [INST_COLUMNS])
        standard = [
            ["Kvinnans namn", "Malin", datetime.now().strftime("%Y-%m-%d")],
            ["Födelsedatum", "1984-03-26", datetime.now().strftime("%Y-%m-%d")],
            ["Startdatum", "2014-03-26", datetime.now().strftime("%Y-%m-%d")],
            ["Kompisar", "100", datetime.now().strftime("%Y-%m-%d")],
            ["Pappans vänner", "40", datetime.now().strftime("%Y-%m-%d")],
            ["Nils vänner", "30", datetime.now().strftime("%Y-%m-%d")],
            ["Nils familj", "20", datetime.now().strftime("%Y-%m-%d")]
        ]
        worksheet.update(f"A2:C{len(standard)+1}", standard)

def läs_inställningar():
    worksheet = sh.worksheet("Inställningar")
    data = worksheet.get_all_records()
    inst = {}
    for rad in data:
        val = str(rad["Värde"])
        try:
            inst[rad["Inställning"]] = float(val.replace(",", "."))
        except:
            inst[rad["Inställning"]] = val
    return inst

def spara_inställning(nyckel, värde):
    worksheet = sh.worksheet("Inställningar")
    df = pd.DataFrame(worksheet.get_all_records())
    idag = datetime.now().strftime("%Y-%m-%d")
    if nyckel in df["Inställning"].values:
        idx = df[df["Inställning"] == nyckel].index[0]
        worksheet.update_cell(idx + 2, 2, str(värde))
        worksheet.update_cell(idx + 2, 3, idag)
    else:
        worksheet.append_row([nyckel, str(värde), idag])

def säkerställ_kolumner(df):
    for kolumn in DATA_COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = ""
    return df[DATA_COLUMNS]

def spara_data(df):
    df = df.fillna("").astype(str)
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update("A1", [df.columns.tolist()] + df.values.tolist())

def ladda_data():
    try:
        worksheet = sh.worksheet("Data")
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=DATA_COLUMNS)
        df = pd.DataFrame(data)
        return säkerställ_kolumner(df)
    except:
        return pd.DataFrame(columns=DATA_COLUMNS)

def reset_form_fields():
    for fält in [
        "typ", "dp", "dpp", "dap", "tpa", "tpp", "tap",
        "enkel_vag", "enkel_anal", "komp", "pappans", "nils_v", "nils_f", "ov",
        "dt_tid_per_man", "scen_tid", "älskar", "sover", "dagar"
    ]:
        st.session_state[fält] = 0 if "dagar" not in fält else 1

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        dagar = st.number_input("Antal vilodagar", min_value=1, step=1, key="dagar")
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.25, key="scen_tid")
        ov = st.number_input("Övriga män", min_value=0, step=1, key="ov")
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1, key="enkel_vag")
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1, key="enkel_anal")
        dp = st.number_input("DP", min_value=0, step=1, key="dp")
        dpp = st.number_input("DPP", min_value=0, step=1, key="dpp")
        dap = st.number_input("DAP", min_value=0, step=1, key="dap")
        tpp = st.number_input("TPP", min_value=0, step=1, key="tpp")
        tap = st.number_input("TAP", min_value=0, step=1, key="tap")
        tpa = st.number_input("TPA", min_value=0, step=1, key="tpa")
        komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)), key="komp")
        pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)), key="pappans")
        nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)), key="nils_v")
        nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)), key="nils_f")
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1, key="dt_tid_per_man")
        älskar = st.number_input("Antal älskar med", min_value=0, step=1, key="älskar")
        sover = st.number_input("Antal sover med", min_value=0, step=1, key="sover")

        submit = st.form_submit_button("Lägg till")

    if submit:
        df = process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                                     dp, dpp, dap, tpp, tap, tpa, komp, pappans, nils_v, nils_f,
                                     dt_tid_per_man, älskar, sover)
        spara_data(df)
        reset_form_fields()
        st.rerun()

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from random import randint, sample

def process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                             dp, dpp, dap, tpp, tap, tpa, komp, pappans, nils_v, nils_f,
                             dt_tid_per_man, älskar, sover):
    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    nils_sextillfällen = [0] * 7

    if typ == "Vilovecka hemma":
        tillfällen = sorted(sample(range(6), k=min(2, 6)))
        for i in tillfällen:
            nils_sextillfällen[i] = 1

    nya_rader = []

    antal = 7 if typ == "Vilovecka hemma" else int(dagar)

    # Slumpvärden för vila inspelningsplats: 25–50% av inställt värde
    def slumpa_vilotal(inst_värde):
        return randint(int(0.25 * inst_värde), int(0.5 * inst_värde)) if inst_värde > 0 else 0

    # Fördelning av 1.5 × inst_värde över 7 dagar (heltal)
    def fördela_värde(total, dagar=7):
        base = total // dagar
        resterande = total % dagar
        fördelning = [base + 1 if i < resterande else base for i in range(dagar)]
        return fördelning

    if typ == "Vilovecka hemma":
        grupper = ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]
        fördelningar = {}
        for grupp in grupper:
            antal_total = int(round(1.5 * float(inst.get(grupp, 0))))
            fördelningar[grupp] = fördela_värde(antal_total)

    for i in range(antal):
        datum = senaste_datum + timedelta(days=1)
        senaste_datum = datum

        if typ == "Vilovecka hemma":
            sover_med = 1 if i == 6 else 0
            älskar_med = 8 if i < 6 else 0
            nils_sex = nils_sextillfällen[i]
            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0,
                "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": fördelningar["Kompisar"][i],
                "Pappans vänner": fördelningar["Pappans vänner"][i],
                "Nils vänner": fördelningar["Nils vänner"][i],
                "Nils familj": fördelningar["Nils familj"][i],
                "Övriga män": 0,
                "Älskar med": älskar_med,
                "Sover med": sover_med,
                "Nils sex": nils_sex,
                "DT tid per man (sek)": 0,
                "Scenens längd (h)": 0
            }

        elif typ == "Vila inspelningsplats":
            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0,
                "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": slumpa_vilotal(inst.get("Kompisar", 0)),
                "Pappans vänner": slumpa_vilotal(inst.get("Pappans vänner", 0)),
                "Nils vänner": slumpa_vilotal(inst.get("Nils vänner", 0)),
                "Nils familj": slumpa_vilotal(inst.get("Nils familj", 0)),
                "Övriga män": 0,
                "Älskar med": 12,
                "Sover med": 1,
                "Nils sex": 0,
                "DT tid per man (sek)": 0,
                "Scenens längd (h)": 0
            }

        else:  # Typ == Scen
            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": dp, "DPP": dpp, "DAP": dap,
                "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
                "Kompisar": komp, "Pappans vänner": pappans, "Nils vänner": nils_v, "Nils familj": nils_f,
                "Övriga män": ov,
                "Älskar med": älskar,
                "Sover med": sover,
                "Nils sex": 0,
                "DT tid per man (sek)": dt_tid_per_man,
                "Scenens längd (h)": scen_tid
            }

        nya_rader.append(rad)

    return pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)

def beräkna_fält(df):
    df = df.copy()

    df["DT total tid (sek)"] = 0
    df["Total tid (sek)"] = 0
    df["Total tid (h)"] = 0
    df["Prenumeranter"] = 0
    df["Intäkt ($)"] = 0
    df["Kvinnans lön ($)"] = 0
    df["Mäns lön ($)"] = 0
    df["Kompisars lön ($)"] = 0
    df["Minuter per kille"] = 0

    for i, row in df.iterrows():
        if row["Typ"] != "Scen":
            continue

        # Total penetrationstid (h -> sek)
        total_tid = float(row.get("Scenens längd (h)", 0)) * 3600

        # Antal penetrationstillfällen
        enkel = int(row.get("Enkel vaginal", 0)) + int(row.get("Enkel anal", 0))
        dubbel = int(row.get("DP", 0)) + int(row.get("DPP", 0)) + int(row.get("DAP", 0))
        trippel = int(row.get("TPA", 0)) + int(row.get("TPP", 0)) + int(row.get("TAP", 0))

        # Prenumeranter: enkel x1, dubbel x5, trippel x8
        pren = enkel * 1 + dubbel * 5 + trippel * 8
        df.at[i, "Prenumeranter"] = pren

        # Intäkt
        intäkt = pren * 15  # USD
        df.at[i, "Intäkt ($)"] = intäkt

        # Lön
        df.at[i, "Kvinnans lön ($)"] = 100
        antal_män = (
            enkel * 1 +
            dubbel * 2 +
            trippel * 3 +
            int(row.get("Kompisar", 0)) +
            int(row.get("Pappans vänner", 0)) +
            int(row.get("Nils vänner", 0)) +
            int(row.get("Nils familj", 0)) +
            int(row.get("Övriga män", 0))
        )
        män_lön = (
            (antal_män - int(row.get("Kompisar", 0))) * 200
            if antal_män > 0 else 0
        )
        df.at[i, "Mäns lön ($)"] = män_lön

        # Kompisars lön = det som blir kvar
        kompisar = int(row.get("Kompisar", 0))
        kvar = intäkt - 100 - män_lön
        df.at[i, "Kompisars lön ($)"] = round(kvar / kompisar, 2) if kompisar > 0 and kvar > 0 else 0

        # DT total tid
        dt_tid = int(row.get("DT tid per man (sek)", 0)) * antal_män
        df.at[i, "DT total tid (sek)"] = dt_tid

        # Total tid + deep throat
        total_sec = total_tid + dt_tid
        df.at[i, "Total tid (sek)"] = int(total_sec)
        df.at[i, "Total tid (h)"] = round(total_sec / 3600, 2)

        # Tid per kille (inkl DT)
        if antal_män > 0:
            df.at[i, "Minuter per kille"] = round(total_sec / 60 / antal_män, 2)

    return df

def main():
    # Initiera ark
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()

    # Läs inställningar
    inst = läs_inställningar()
    df = ladda_data()

    # Streamlit-titel
    st.title("🎬 Malin Filmproduktion")

    # Sidopanel: inställningar
    with st.sidebar:
        st.header("Inställningar")
        with st.form("spara_inställningar"):
            namn = st.text_input("Kvinnans namn", value=str(inst.get("Kvinnans namn", "")))
            född = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1984-03-26")))
            startdatum = st.date_input("Startdatum (första scen)", value=pd.to_datetime(inst.get("Startdatum", "2014-03-26")))

            inst_inputs = {}
            for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
                inst_inputs[fält] = st.number_input(fält, value=float(inst.get(fält, 0)), min_value=0.0, step=1.0)

            spara = st.form_submit_button("Spara inställningar")

        if spara:
            spara_inställning("Kvinnans namn", namn)
            spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
            spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))
            for nyckel, värde in inst_inputs.items():
                spara_inställning(nyckel, värde)
            st.success("Inställningar sparade!")

    # Formulär för att lägga till scen eller vila
    scenformulär(df, inst)

    # Uppdatera beräkningar
    df = beräkna_fält(df)

    # Visa hela tabellen
    st.subheader("Alla scener och vilodagar")
    st.dataframe(df, use_container_width=True)
