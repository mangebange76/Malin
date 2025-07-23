import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample
import numpy as np

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

def visa_inställningar(inst):
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
        st.experimental_rerun()

# --------------------- Del 3: Scenformulär och spara till databasen ---------------------

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

        if typ == "Scen":
            total_tid = scen_tid * 3600
            total_killar = (
                dp * 2 + dpp * 2 + dap * 2 +
                tpa * 3 + tpp * 3 + tap * 3 +
                enkel_vag + enkel_anal +
                komp + pappans + nils_v + nils_f + ov
            )
            dt_total = dt_tid_per_man * total_killar
            total_tid_h = (total_tid + dt_total) / 3600
            tid_per_kille_min = (total_tid + dt_total) / 60 / total_killar if total_killar > 0 else 0

            st.info(f"Totalt antal killar: {total_killar}")
            st.info(f"Total tid inkl. DT: {total_tid_h:.2f} h")
            st.info(f"Minuter per kille inkl. DT: {tid_per_kille_min:.2f} min")
            if total_tid_h > 18:
                st.warning("⚠️ Totaltiden överskrider 18 timmar!")

        submit = st.form_submit_button("Lägg till")

    if submit:
        from berakningar import process_lägg_till_rader
        df = process_lägg_till_rader(df, inst)
        spara_data(df)

        # Nollställ formulär
        for key in [
            "dp", "dpp", "dap", "tpa", "tpp", "tap", "enkel_vag", "enkel_anal",
            "komp", "pappans", "nils_v", "nils_f", "ov",
            "älskar", "sover", "dt_tid_per_man", "dagar", "scen_tid"
        ]:
            st.session_state[key] = 0
        st.session_state["typ"] = "Scen"
        st.rerun()

# --------------------- Del 4: berakningar.py – process_lägg_till_rader ---------------------

from datetime import timedelta
import pandas as pd
from random import sample

def process_lägg_till_rader(df, inst):
    import streamlit as st

    typ = st.session_state["typ"]
    dp = st.session_state["dp"]
    dpp = st.session_state["dpp"]
    dap = st.session_state["dap"]
    tpa = st.session_state["tpa"]
    tpp = st.session_state["tpp"]
    tap = st.session_state["tap"]
    enkel_vag = st.session_state["enkel_vag"]
    enkel_anal = st.session_state["enkel_anal"]
    komp = st.session_state["komp"]
    pappans = st.session_state["pappans"]
    nils_v = st.session_state["nils_v"]
    nils_f = st.session_state["nils_f"]
    ov = st.session_state["ov"]
    älskar = st.session_state["älskar"]
    sover = st.session_state["sover"]
    dt_tid_per_man = st.session_state["dt_tid_per_man"]
    scen_tid = st.session_state["scen_tid"]
    dagar = int(st.session_state["dagar"])

    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    rader = []

    if typ == "Vilovecka hemma":
        nils_sex = [0] * 7
        tillfällen = sorted(sample(range(6), k=min(2, 6)))
        for i in tillfällen:
            nils_sex[i] = 1

        for i in range(7):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum
            row = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0, "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0, "Övriga män": 0,
                "Kompisar": 0, "Pappans vänner": 0, "Nils vänner": 0, "Nils familj": 0,
                "Älskar med": 8 if i < 6 else 0,
                "Sover med": 1 if i == 6 else 0,
                "Nils sex": nils_sex[i],
                "DT tid per man (sek)": 0,
                "Scenens längd (h)": 0,
                "DT total tid (sek)": 0,
                "Total tid (sek)": 0,
                "Total tid (h)": 0,
                "Prenumeranter": 0,
                "Intäkt ($)": 0,
                "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0,
                "Kompisars lön ($)": 0,
                "Minuter per kille": 0,
            }
            # fördela 1.5x antalet från inst
            for kategori in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
                total = int(1.5 * float(inst.get(kategori, 0)))
                fördelning = [total // 7] * 7
                for j in range(total % 7):
                    fördelning[j] += 1
                row[kategori] = fördelning[i]
            rader.append(row)

    elif typ == "Vila inspelningsplats":
        for _ in range(dagar):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum
            row = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0, "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": int(0.25 * float(inst.get("Kompisar", 0))) + sample(range(0, int(0.25 * float(inst.get("Kompisar", 0))) + 1), 1)[0],
                "Pappans vänner": int(0.25 * float(inst.get("Pappans vänner", 0))) + sample(range(0, int(0.25 * float(inst.get("Pappans vänner", 0))) + 1), 1)[0],
                "Nils vänner": int(0.25 * float(inst.get("Nils vänner", 0))) + sample(range(0, int(0.25 * float(inst.get("Nils vänner", 0))) + 1), 1)[0],
                "Nils familj": int(0.25 * float(inst.get("Nils familj", 0))) + sample(range(0, int(0.25 * float(inst.get("Nils familj", 0))) + 1), 1)[0],
                "Övriga män": 0,
                "Älskar med": 12,
                "Sover med": 1,
                "Nils sex": 0,
                "DT tid per man (sek)": 0,
                "Scenens längd (h)": 0,
                "DT total tid (sek)": 0,
                "Total tid (sek)": 0,
                "Total tid (h)": 0,
                "Prenumeranter": 0,
                "Intäkt ($)": 0,
                "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0,
                "Kompisars lön ($)": 0,
                "Minuter per kille": 0,
            }
            rader.append(row)

    else:  # typ == "Scen"
        datum = senaste_datum + timedelta(days=1)
        total_tid = scen_tid * 3600
        antal_killar = (
            dp * 2 + dpp * 2 + dap * 2 +
            tpa * 3 + tpp * 3 + tap * 3 +
            enkel_vag + enkel_anal + komp + pappans + nils_v + nils_f + ov
        )
        dt_total = dt_tid_per_man * antal_killar
        total_tid_h = (total_tid + dt_total) / 3600
        tid_per_kille = (total_tid + dt_total) / 60 / antal_killar if antal_killar > 0 else 0

        pren = enkel_vag * 1 + enkel_anal * 1 + (dp + dpp + dap) * 5 + (tpa + tpp + tap) * 8
        intäkt = pren * 15
        kvinnans_lön = 100
        män_lön = (komp + pappans + nils_v + nils_f + ov) * 200
        kompisars_lön = max(0, intäkt - kvinnans_lön - män_lön) if komp > 0 else 0

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
            "DT total tid (sek)": dt_total,
            "Scenens längd (h)": scen_tid,
            "Total tid (sek)": total_tid + dt_total,
            "Total tid (h)": total_tid_h,
            "Prenumeranter": pren,
            "Intäkt ($)": intäkt,
            "Kvinnans lön ($)": kvinnans_lön,
            "Mäns lön ($)": män_lön,
            "Kompisars lön ($)": kompisars_lön,
            "Minuter per kille": tid_per_kille,
        }
        rader.append(rad)

    return pd.concat([df, pd.DataFrame(rader)], ignore_index=True)

# --------------------- Del 5: main() ---------------------

import streamlit as st
from datetime import datetime
import pandas as pd
from gspread_dataframe import set_with_dataframe
from berakningar import process_lägg_till_rader

def visa_inställningar(inst):
    st.sidebar.header("Inställningar")
    ändrad = False
    for nyckel in ["Startdatum", "Kvinnans namn", "Födelsedatum", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        if "datum" in nyckel.lower():
            nytt_värde = st.sidebar.date_input(nyckel, pd.to_datetime(inst.get(nyckel)), key=nyckel)
        else:
            nytt_värde = st.sidebar.text_input(nyckel, str(inst.get(nyckel)), key=nyckel)
        if str(nytt_värde) != str(inst.get(nyckel)):
            inst[nyckel] = str(nytt_värde)
            ändrad = True

    if ändrad:
        sheet = st.session_state.sheet
        data = [[k, v] for k, v in inst.items()]
        sheet.worksheet("Inställningar").update("A2", data)

def scenformulär(df, inst):
    with st.form("Lägg till scen eller vila"):
        st.markdown("## Lägg till scen eller vila")
        st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        st.number_input("Antal vilodagar", min_value=0, max_value=30, step=1, key="dagar")
        st.number_input("Scenens längd (h)", min_value=0.0, max_value=48.0, step=0.5, key="scen_tid")
        st.number_input("Övriga män", min_value=0, step=1, key="ov")
        st.number_input("Enkel vaginal", min_value=0, step=1, key="enkel_vag")
        st.number_input("Enkel anal", min_value=0, step=1, key="enkel_anal")
        st.number_input("DP", min_value=0, step=1, key="dp")
        st.number_input("DPP", min_value=0, step=1, key="dpp")
        st.number_input("DAP", min_value=0, step=1, key="dap")
        st.number_input("TPP", min_value=0, step=1, key="tpp")
        st.number_input("TAP", min_value=0, step=1, key="tap")
        st.number_input("TPA", min_value=0, step=1, key="tpa")
        st.number_input("Kompisar", min_value=0, step=1, key="komp")
        st.number_input("Pappans vänner", min_value=0, step=1, key="pappans")
        st.number_input("Nils vänner", min_value=0, step=1, key="nils_v")
        st.number_input("Nils familj", min_value=0, step=1, key="nils_f")
        st.number_input("DT tid per man (sek)", min_value=0, step=1, key="dt_tid_per_man")
        st.number_input("Antal älskar med", min_value=0, step=1, key="älskar")
        st.number_input("Antal sover med", min_value=0, step=1, key="sover")

        # Visning av beräknad tid
        try:
            antal_killar = (
                st.session_state["dp"] * 2 + st.session_state["dpp"] * 2 + st.session_state["dap"] * 2 +
                st.session_state["tpa"] * 3 + st.session_state["tpp"] * 3 + st.session_state["tap"] * 3 +
                st.session_state["enkel_vag"] + st.session_state["enkel_anal"] +
                st.session_state["komp"] + st.session_state["pappans"] +
                st.session_state["nils_v"] + st.session_state["nils_f"] +
                st.session_state["ov"]
            )
            total_tid = st.session_state["scen_tid"] * 3600
            dt_total = st.session_state["dt_tid_per_man"] * antal_killar
            total_tid_h = round((total_tid + dt_total) / 3600, 2)
            tid_per_kille = round((total_tid + dt_total) / 60 / antal_killar, 2) if antal_killar > 0 else 0

            st.markdown(f"**Totalt antal killar:** {antal_killar}")
            st.markdown(f"**Total tid inkl. deep throat (h):** {total_tid_h}")
            st.markdown(f"**Minuter per kille inkl. deep throat:** {tid_per_kille:.2f} min")

            if total_tid_h > 18:
                st.error("⚠️ Scenens totala tid överstiger 18 timmar!")
        except:
            pass

        submit = st.form_submit_button("Lägg till")
        if submit:
            df = process_lägg_till_rader(df, inst)
            worksheet = st.session_state.sheet.worksheet("Data")
            worksheet.clear()
            set_with_dataframe(worksheet, df)
            st.success("Rad(er) tillagda!")
            st.experimental_rerun()

def main():
    st.set_page_config(page_title="Malin App", layout="wide")
    st.title("🎬 Malin – inspelningslogg & beräkningar")
    inst = st.session_state.inst
    df = st.session_state.df

    visa_inställningar(inst)
    scenformulär(df, inst)

    st.markdown("## Samtliga rader i databasen")
    st.dataframe(df)

if __name__ == "__main__":
    main()
