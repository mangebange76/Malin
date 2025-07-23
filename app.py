import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample, randint

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

def fördela_heltal_slumpmässigt(total, dagar=7):
    delar = [0] * dagar
    for _ in range(int(total)):
        idx = randint(0, dagar - 1)
        delar[idx] += 1
    return delar

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till", clear_on_submit=True):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1)
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.25)
        ov = st.number_input("Övriga män", min_value=0, step=1)
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1)
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
        dp = st.number_input("DP", min_value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, step=1)
        dap = st.number_input("DAP", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)))
        pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)))
        nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)))
        nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)))
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1)
        älskar = st.number_input("Antal älskar med", min_value=0, step=1)
        sover = st.number_input("Antal sover med", min_value=0, step=1)
        submit = st.form_submit_button("Lägg till")

    if submit:
        senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
        nils_sextillfällen = [0] * 7

        if typ == "Vilovecka hemma":
            tillfällen = sorted(sample(range(6), k=min(2, 6)))
            for i in tillfällen:
                nils_sextillfällen[i] = 1

            komp_list = fördela_heltal_slumpmässigt(1.5 * inst.get("Kompisar", 0))
            pappans_list = fördela_heltal_slumpmässigt(1.5 * inst.get("Pappans vänner", 0))
            nils_v_list = fördela_heltal_slumpmässigt(1.5 * inst.get("Nils vänner", 0))
            nils_f_list = fördela_heltal_slumpmässigt(1.5 * inst.get("Nils familj", 0))

        antal = 7 if typ == "Vilovecka hemma" else int(dagar)
        nya_rader = []

        for i in range(antal):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            if typ == "Vilovecka hemma":
                sover_med = 1 if i == 6 else 0
                älskar_med = 8 if i < 6 else 0
                nils_sex = nils_sextillfällen[i]
                komp_i = komp_list[i]
                pappans_i = pappans_list[i]
                nils_v_i = nils_v_list[i]
                nils_f_i = nils_f_list[i]
            elif typ == "Vila inspelningsplats":
                älskar_med = 12
                sover_med = 1
                nils_sex = 0
                komp_i = randint(int(0.25 * inst.get("Kompisar", 0)), int(0.5 * inst.get("Kompisar", 0)))
                pappans_i = randint(int(0.25 * inst.get("Pappans vänner", 0)), int(0.5 * inst.get("Pappans vänner", 0)))
                nils_v_i = randint(int(0.25 * inst.get("Nils vänner", 0)), int(0.5 * inst.get("Nils vänner", 0)))
                nils_f_i = randint(int(0.25 * inst.get("Nils familj", 0)), int(0.5 * inst.get("Nils familj", 0)))
            else:
                älskar_med = älskar
                sover_med = sover
                nils_sex = 0
                komp_i = komp
                pappans_i = pappans
                nils_v_i = nils_v
                nils_f_i = nils_f

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": dp, "DPP": dpp, "DAP": dap,
                "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
                "Kompisar": komp_i, "Pappans vänner": pappans_i,
                "Nils vänner": nils_v_i, "Nils familj": nils_f_i,
                "Övriga män": ov,
                "Älskar med": älskar_med,
                "Sover med": sover_med,
                "Nils sex": nils_sex,
                "DT tid per man (sek)": dt_tid_per_man,
                "Scenens längd (h)": scen_tid
            }
            nya_rader.append(rad)

        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        spara_data(df)
        st.rerun()

def main():
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()
    inst = läs_inställningar()
    df = ladda_data()

    st.title("🎬 Malin Filmproduktion")

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

    scenformulär(df, inst)

if __name__ == "__main__":
    main()
