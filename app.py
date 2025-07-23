# Del 1 – Importer, autentisering, initiering
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample, shuffle
import math

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Spreadsheet
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumner för databladen
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

# Del 2 – Initiera blad, läsa/spara inställningar, hantera data

# Initiera kalkylblad
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

# Initiera inställningsblad med standardvärden
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

# Läs inställningar till dict
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

# Spara inställning
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

# Se till att alla kolumner finns i DataFrame
def säkerställ_kolumner(df):
    for kolumn in DATA_COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = ""
    return df[DATA_COLUMNS]

# Spara DataFrame till Google Sheets
def spara_data(df):
    df = df.fillna("").astype(str)
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update("A1", [df.columns.tolist()] + df.values.tolist())

# Ladda data från Google Sheets
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

# Del 3 – Formulär för att lägga till scen eller vila

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    if "form_values" not in st.session_state:
        st.session_state.form_values = {
            "Typ": "Scen", "DP": 0, "DPP": 0, "DAP": 0,
            "TPA": 0, "TPP": 0, "TAP": 0,
            "Enkel vaginal": 0, "Enkel anal": 0,
            "Kompisar": 0, "Pappans vänner": 0, "Nils vänner": 0, "Nils familj": 0,
            "Övriga män": 0,
            "DT tid per man (sek)": 0, "Scenens längd (h)": 0.0,
            "Älskar med": 0, "Sover med": 0,
            "Antal vilodagar": 1
        }

    with st.form("lägg_till"):
        f = st.session_state.form_values
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ", index=["Scen", "Vila inspelningsplats", "Vilovecka hemma"].index(f["Typ"]))
        dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1, key="dagar", value=f["Antal vilodagar"])
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.25, key="scen_tid", value=f["Scenens längd (h)"])
        ov = st.number_input("Övriga män", min_value=0, step=1, key="ov", value=f["Övriga män"])
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1, key="ev", value=f["Enkel vaginal"])
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1, key="ea", value=f["Enkel anal"])
        dp = st.number_input("DP", min_value=0, step=1, key="dp", value=f["DP"])
        dpp = st.number_input("DPP", min_value=0, step=1, key="dpp", value=f["DPP"])
        dap = st.number_input("DAP", min_value=0, step=1, key="dap", value=f["DAP"])
        tpp = st.number_input("TPP", min_value=0, step=1, key="tpp", value=f["TPP"])
        tap = st.number_input("TAP", min_value=0, step=1, key="tap", value=f["TAP"])
        tpa = st.number_input("TPA", min_value=0, step=1, key="tpa", value=f["TPA"])
        komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)), key="komp", value=f["Kompisar"])
        pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)), key="pappans", value=f["Pappans vänner"])
        nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)), key="nils_v", value=f["Nils vänner"])
        nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)), key="nils_f", value=f["Nils familj"])
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1, key="dt", value=f["DT tid per man (sek)"])
        älskar = st.number_input("Antal älskar med", min_value=0, step=1, key="alskar", value=f["Älskar med"])
        sover = st.number_input("Antal sover med", min_value=0, step=1, key="sover", value=f["Sover med"])
        submit = st.form_submit_button("Lägg till")

    if submit:
        from .berakningar import process_lägg_till_rader  # OBS: Beräkningslogik kommer i Del 4
        nya_rader = process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                                            dp, dpp, dap, tpa, tpp, tap, komp, pappans, nils_v, nils_f,
                                            dt_tid_per_man, älskar, sover)
        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        spara_data(df)

        # Nollställ fält
        st.session_state.form_values = {
            "Typ": "Scen", "DP": 0, "DPP": 0, "DAP": 0,
            "TPA": 0, "TPP": 0, "TAP": 0,
            "Enkel vaginal": 0, "Enkel anal": 0,
            "Kompisar": 0, "Pappans vänner": 0, "Nils vänner": 0, "Nils familj": 0,
            "Övriga män": 0,
            "DT tid per man (sek)": 0, "Scenens längd (h)": 0.0,
            "Älskar med": 0, "Sover med": 0,
            "Antal vilodagar": 1
        }
        st.success("Rad tillagd!")
        st.rerun()

# Del 4 – Beräkningar vid tillägg av rader

def process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                             dp, dpp, dap, tpa, tpp, tap, komp, pappans, nils_v, nils_f,
                             dt_tid_per_man, älskar, sover):

    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    rader = []

    if typ == "Vilovecka hemma":
        nils_sextillfällen = [0] * 7
        from random import sample
        tillfällen = sorted(sample(range(6), k=min(2, 6)))
        for i in tillfällen:
            nils_sextillfällen[i] = 1

        antal_dagar = 7
        # Fördela 1.5× antal över 7 dagar
        def fördela(grupp_namn):
            total = int(inst.get(grupp_namn, 0) * 1.5)
            per_dag = [total // 7] * 7
            for i in range(total % 7):
                per_dag[i] += 1
            return per_dag

        komp_lista = fördela("Kompisar")
        pappans_lista = fördela("Pappans vänner")
        nilsv_lista = fördela("Nils vänner")
        nilsf_lista = fördela("Nils familj")

    elif typ == "Vila inspelningsplats":
        antal_dagar = dagar
        from random import randint
        def slumpa(grupp_namn):
            maxval = int(inst.get(grupp_namn, 0))
            return [randint(max(1, maxval // 4), maxval // 2) for _ in range(antal_dagar)]

        komp_lista = slumpa("Kompisar")
        pappans_lista = slumpa("Pappans vänner")
        nilsv_lista = slumpa("Nils vänner")
        nilsf_lista = slumpa("Nils familj")

    else:
        antal_dagar = 1
        komp_lista = [komp]
        pappans_lista = [pappans]
        nilsv_lista = [nils_v]
        nilsf_lista = [nils_f]

    for i in range(antal_dagar):
        datum = senaste_datum + timedelta(days=1)
        senaste_datum = datum

        if typ == "Vilovecka hemma":
            älskar_med = 8
            sover_med = 0
            nils_sex = nils_sextillfällen[i]
        elif typ == "Vila inspelningsplats":
            älskar_med = 12
            sover_med = 1
            nils_sex = 0
        else:
            älskar_med = älskar
            sover_med = sover
            nils_sex = 0

        komp_i = komp_lista[i]
        pappans_i = pappans_lista[i]
        nilsv_i = nilsv_lista[i]
        nilsf_i = nilsf_lista[i]

        total_män = dp*2 + dpp*2 + dap*2 + tpa*3 + tpp*3 + tap*3 + enkel_vag + enkel_anal + komp_i + pappans_i + nilsv_i + nilsf_i + ov

        # Prenumeranter
        pren = enkel_vag * 1 + enkel_anal * 1 + (dp + dpp + dap) * 5 + (tpa + tpp + tap) * 8 if typ == "Scen" else 0

        # Total tid (sek)
        total_tid = scen_tid * 3600 if typ == "Scen" else 0
        dt_total = dt_tid_per_man * total_män if typ == "Scen" else 0
        total_tid_h = total_tid / 3600 if total_tid else 0
        minuter_per_kille = round((total_tid + dt_total) / total_män / 60, 2) if total_män > 0 and typ == "Scen" else 0

        # Intäkter/löner
        intakt = pren * 15 if typ == "Scen" else 0
        kvinna_lön = 100 if typ == "Scen" else 0
        man_lön_total = (dp + dpp + dap + tpa + tpp + tap + enkel_vag + enkel_anal + ov + pappans_i + nilsv_i + nilsf_i) * 200 if typ == "Scen" else 0
        kompis_lön = intakt - kvinna_lön - man_lön_total if typ == "Scen" else 0
        if komp_i > 0 and kompis_lön > 0:
            kompis_lön = round(kompis_lön / int(inst.get("Kompisar", 1)), 2)
        else:
            kompis_lön = 0

        rad = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Typ": typ,
            "DP": dp, "DPP": dpp, "DAP": dap,
            "TPA": tpa, "TPP": tpp, "TAP": tap,
            "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
            "Kompisar": komp_i, "Pappans vänner": pappans_i,
            "Nils vänner": nilsv_i, "Nils familj": nilsf_i, "Övriga män": ov,
            "Älskar med": älskar_med, "Sover med": sover_med, "Nils sex": nils_sex,
            "DT tid per man (sek)": dt_tid_per_man,
            "DT total tid (sek)": dt_total,
            "Total tid (sek)": total_tid + dt_total,
            "Total tid (h)": round((total_tid + dt_total) / 3600, 2),
            "Prenumeranter": pren,
            "Intäkt ($)": intakt,
            "Kvinnans lön ($)": kvinna_lön,
            "Mäns lön ($)": man_lön_total,
            "Kompisars lön ($)": kompis_lön,
            "Minuter per kille": minuter_per_kille,
            "Scenens längd (h)": scen_tid
        }
        rader.append(rad)

    return rader

# Del 5 – Main-funktion och tabellvisning

def main():
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()
    inst = läs_inställningar()
    df = ladda_data()

    st.title("🎬 Malin Filmproduktion")

    # Sidopanel för inställningar
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

    # Visa hela databasen
    st.subheader("📋 Databas – alla rader")
    if df.empty:
        st.info("Inga rader har lagts till ännu.")
    else:
        st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
