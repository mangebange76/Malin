import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample

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

def rensa_data():
    worksheet = sh.worksheet("Data")
    worksheet.resize(rows=1)
    worksheet.update("A1", [DATA_COLUMNS])

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    if "form_state" not in st.session_state:
        st.session_state.form_state = {
            "typ": "Scen", "dagar": 1, "scen_tid": 0.0, "ov": 0, "enkel_vag": 0, "enkel_anal": 0,
            "dp": 0, "dpp": 0, "dap": 0, "tpp": 0, "tap": 0, "tpa": 0,
            "komp": 0, "pappans": 0, "nils_v": 0, "nils_f": 0,
            "dt_tid_per_man": 0, "älskar": 0, "sover": 0
        }

    with st.form("lägg_till"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1, key="dagar")
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
        senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
        nils_sextillfällen = [0] * 7

        if typ == "Vilovecka hemma":
            tillfällen = sorted(sample(range(6), k=min(2, 6)))
            for i in tillfällen:
                nils_sextillfällen[i] = 1

            # fördela 1,5× totalt antal
            def fördela(total):
                mål = int(round(total * 1.5))
                bas = mål // 7
                rest = mål % 7
                return [bas + 1 if i < rest else bas for i in range(7)]

            komp_lista = fördela(inst.get("Kompisar", 0))
            pappans_lista = fördela(inst.get("Pappans vänner", 0))
            nilsv_lista = fördela(inst.get("Nils vänner", 0))
            nilsf_lista = fördela(inst.get("Nils familj", 0))

        antal = 7 if typ == "Vilovecka hemma" else int(dagar)
        nya_rader = []

        for i in range(antal):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            if typ == "Vilovecka hemma":
                sover_med = 1 if i == 6 else 0
                älskar_med = 8 if i < 6 else 0
                nils_sex = nils_sextillfällen[i]
                rad_komp = komp_lista[i]
                rad_pappans = pappans_lista[i]
                rad_nils_v = nilsv_lista[i]
                rad_nils_f = nilsf_lista[i]

            elif typ == "Vila inspelningsplats":
                älskar_med = 12
                sover_med = 1
                nils_sex = 0
                rad_komp = int(inst.get("Kompisar", 0) * (0.25 + 0.25 * sample([0, 1], 1)[0]))
                rad_pappans = int(inst.get("Pappans vänner", 0) * (0.25 + 0.25 * sample([0, 1], 1)[0]))
                rad_nils_v = int(inst.get("Nils vänner", 0) * (0.25 + 0.25 * sample([0, 1], 1)[0]))
                rad_nils_f = int(inst.get("Nils familj", 0) * (0.25 + 0.25 * sample([0, 1], 1)[0]))

            else:
                älskar_med = älskar
                sover_med = sover
                nils_sex = 0
                rad_komp = komp
                rad_pappans = pappans
                rad_nils_v = nils_v
                rad_nils_f = nils_f

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": dp, "DPP": dpp, "DAP": dap,
                "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
                "Kompisar": rad_komp, "Pappans vänner": rad_pappans, "Nils vänner": rad_nils_v, "Nils familj": rad_nils_f,
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

        # återställ fält
        for key in st.session_state.form_state:
            st.session_state[key] = st.session_state.form_state[key]

        st.rerun()

def beräkna_och_uppdatera(df):
    df["Prenumeranter"] = 0
    df["DT total tid (sek)"] = 0
    df["Total tid (sek)"] = 0
    df["Total tid (h)"] = 0
    df["Kvinnans lön ($)"] = 0
    df["Intäkt ($)"] = 0
    df["Mäns lön ($)"] = 0
    df["Kompisars lön ($)"] = 0
    df["Minuter per kille"] = 0

    for i, row in df.iterrows():
        if row["Typ"] != "Scen":
            continue

        enkel = int(row["Enkel vaginal"]) + int(row["Enkel anal"])
        dubbel = int(row["DP"]) + int(row["DPP"]) + int(row["DAP"])
        trippel = int(row["TPA"]) + int(row["TPP"]) + int(row["TAP"])

        pren = enkel * 1 + dubbel * 5 + trippel * 8
        kvinna = 100
        total = pren * 15

        övriga_män = (
            int(row["Kompisar"])
            + int(row["Pappans vänner"])
            + int(row["Nils vänner"])
            + int(row["Nils familj"])
            + int(row["Övriga män"])
        )
        man_lön = (övriga_män - int(row["Kompisar"])) * 200
        kvar = total - kvinna - man_lön
        komp_lön = kvar / inst.get("Kompisar", 1)

        dt_total = int(row["DT tid per man (sek)"]) * övriga_män
        tid_total = row["Scenens längd (h)"] * 3600 + dt_total

        df.at[i, "Prenumeranter"] = pren
        df.at[i, "Intäkt ($)"] = round(total, 2)
        df.at[i, "Kvinnans lön ($)"] = kvinna
        df.at[i, "Mäns lön ($)"] = round(man_lön, 2)
        df.at[i, "Kompisars lön ($)"] = round(komp_lön, 2)
        df.at[i, "DT total tid (sek)"] = dt_total
        df.at[i, "Total tid (sek)"] = tid_total
        df.at[i, "Total tid (h)"] = round(tid_total / 3600, 2)
        df.at[i, "Minuter per kille"] = round(tid_total / övriga_män / 60, 1) if övriga_män else 0

    return df


def statistikruta(df, inst):
    st.subheader("Statistik")

    df["Datum"] = pd.to_datetime(df["Datum"])
    df = df.sort_values("Datum")
    df_scener = df[df["Typ"] == "Scen"]

    total_tid = df_scener["Total tid (h)"].sum()
    total_pren = df_scener["Prenumeranter"].sum()
    intäkter = df_scener["Intäkt ($)"].sum()
    dt_tid = df_scener["DT total tid (sek)"].sum()

    älskat = df["Älskar med"].sum()
    sovit = df["Sover med"].sum()

    snitt_älskat = älskat / (
        inst.get("Kompisar", 1) + inst.get("Pappans vänner", 1) + inst.get("Nils vänner", 1) + inst.get("Nils familj", 1)
    )
    snitt_sovit = sovit / inst.get("Nils familj", 1)

    st.write(f"👩 **{inst.get('Kvinnans namn', '')}** – ålder: {round((df['Datum'].max() - pd.to_datetime(inst['Födelsedatum'])).days / 365.25)} år")
    st.write(f"🎬 Totalt antal scener: {len(df_scener)}")
    st.write(f"🕒 Total filmtid: {round(total_tid, 1)} h")
    st.write(f"💰 Totala intäkter: ${round(intäkter):,}")
    st.write(f"📈 Totalt antal prenumeranter: {int(total_pren)}")
    st.write(f"🤿 Deep throat-tid totalt: {int(dt_tid)} sek")
    st.write(f"❤️ Snitt 'älskat': {snitt_älskat:.2f} gånger")
    st.write(f"🛏️ Snitt 'sovit med': {snitt_sovit:.2f} gånger")


def main():
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()

    global inst
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

            rensa = st.form_submit_button("Rensa databas")
            spara = st.form_submit_button("Spara inställningar")

        if rensa:
            rensa_data()
            st.success("Databasen rensad!")

        if spara:
            spara_inställning("Kvinnans namn", namn)
            spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
            spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))
            for nyckel, värde in inst_inputs.items():
                spara_inställning(nyckel, värde)
            st.success("Inställningar sparade!")

    scenformulär(df, inst)
    df = beräkna_och_uppdatera(df)
    statistikruta(df, inst)

    st.subheader("Databas")
    st.dataframe(df)

if __name__ == "__main__":
    main()
