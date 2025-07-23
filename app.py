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

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        dagar = st.number_input("Antal vilodagar", min_value=1, step=1)
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
        nya_rader = []

        if typ == "Vilovecka hemma":
            tillfällen = sorted(sample(range(7), k=min(2, 7)))
            for i in tillfällen:
                nils_sextillfällen[i] = 1

            tot_antal = {
                "Kompisar": int(inst.get("Kompisar", 0) * 1.5),
                "Pappans vänner": int(inst.get("Pappans vänner", 0) * 1.5),
                "Nils vänner": int(inst.get("Nils vänner", 0) * 1.5),
                "Nils familj": int(inst.get("Nils familj", 0) * 1.5)
            }

            fördelning = {k: [tot_antal[k] // 7] * 7 for k in tot_antal}
            for k in tot_antal:
                for i in range(tot_antal[k] % 7):
                    fördelning[k][i] += 1
        else:
            fördelning = {k: [randint(int(inst[k]*0.25), int(inst[k]*0.5)) for _ in range(int(dagar))] for k in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]}

        antal = 7 if typ == "Vilovecka hemma" else int(dagar)

        for i in range(antal):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": dp, "DPP": dpp, "DAP": dap,
                "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
                "Kompisar": fördelning["Kompisar"][i] if typ != "Scen" else komp,
                "Pappans vänner": fördelning["Pappans vänner"][i] if typ != "Scen" else pappans,
                "Nils vänner": fördelning["Nils vänner"][i] if typ != "Scen" else nils_v,
                "Nils familj": fördelning["Nils familj"][i] if typ != "Scen" else nils_f,
                "Övriga män": ov,
                "Älskar med": 12 if typ == "Vila inspelningsplats" else (8 if typ == "Vilovecka hemma" else älskar),
                "Sover med": 1 if typ == "Vila inspelningsplats" else (1 if typ == "Vilovecka hemma" and i == 6 else sover),
                "Nils sex": nils_sextillfällen[i] if typ == "Vilovecka hemma" else 0,
                "DT tid per man (sek)": dt_tid_per_man,
                "Scenens längd (h)": scen_tid
            }

            nya_rader.append(rad)

        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        df = beräkna_fält(df)
        spara_data(df)
        st.success("Tillagt!")
        st.experimental_rerun()

def beräkna_fält(df):
    df = df.copy()
    for i, row in df.iterrows():
        if row["Typ"] == "Scen":
            dt_total = row["DT tid per man (sek)"] * (
                row["Kompisar"] + row["Pappans vänner"] + row["Nils vänner"] + row["Nils familj"] + row["Övriga män"]
            )
            total_tid = row["Scenens längd (h)"] * 3600 + dt_total
            pren = (
                row["Enkel vaginal"] * 1 +
                row["Enkel anal"] * 1 +
                (row["DP"] + row["DPP"] + row["DAP"]) * 5 +
                (row["TPA"] + row["TPP"] + row["TAP"]) * 8
            )
            intakt = pren * 15
            mans_lön = (
                (row["Kompisar"] + row["Pappans vänner"] + row["Nils vänner"] + row["Nils familj"] + row["Övriga män"]) * 200
            )
            komp_lön = max(0, intakt - 100 - mans_lön) if row["Kompisar"] > 0 else 0
            df.at[i, "DT total tid (sek)"] = dt_total
            df.at[i, "Total tid (sek)"] = total_tid
            df.at[i, "Total tid (h)"] = round(total_tid / 3600, 2)
            df.at[i, "Prenumeranter"] = pren
            df.at[i, "Intäkt ($)"] = intakt
            df.at[i, "Kvinnans lön ($)"] = 100
            df.at[i, "Mäns lön ($)"] = mans_lön
            df.at[i, "Kompisars lön ($)"] = komp_lön
            df.at[i, "Minuter per kille"] = round(total_tid / 60 / max(1, row["Kompisar"] + row["Pappans vänner"] + row["Nils vänner"] + row["Nils familj"] + row["Övriga män"]), 2)
    return df

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

    st.subheader("Alla scener och vilodagar")
    st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
