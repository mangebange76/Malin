# Del 1: Importer, autentisering, initiering
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample
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

# Initiera blad
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

# Del 2: Ladda/spara data + formulär med tidsinfo i realtid

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

        # TIDSKALKYL
        total_killar = (
            enkel_vag + enkel_anal + 
            2 * (dp + dpp + dap) + 
            3 * (tpa + tpp + tap)
        )
        dt_total = total_killar * dt_tid_per_man
        penetration_tid = scen_tid * 3600 if typ == "Scen" else 0
        total_tid = penetration_tid + dt_total
        total_tid_h = total_tid / 3600
        min_per_kille = total_tid / total_killar / 60 if total_killar > 0 else 0

        st.info(f"**Tid per man inkl. DT:** {min_per_kille:.1f} min")
        st.info(f"**Total tid:** {total_tid_h:.1f} h")

        if total_tid_h > 18 and typ == "Scen":
            st.warning("⚠️ Total tid överstiger 18 timmar!")

        submit = st.form_submit_button("Lägg till")

    if submit:
        process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                                 dp, dpp, dap, tpp, tap, tpa, komp, pappans, nils_v, nils_f,
                                 dt_tid_per_man, älskar, sover)
        st.experimental_rerun()

def process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                             dp, dpp, dap, tpp, tap, tpa, komp, pappans, nils_v, nils_f,
                             dt_tid_per_man, älskar, sover):

    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    nils_sextillfällen = [0] * 7

    nya_rader = []

    if typ == "Vilovecka hemma":
        tillfällen = sorted(sample(range(7), k=min(2, 7)))
        for i in tillfällen:
            nils_sextillfällen[i] = 1

        def fördela(total):
            antal = int(total * 1.5)
            bas = antal // 7
            extra = antal % 7
            return [bas + 1 if i < extra else bas for i in range(7)]

        komp_dagar = fördela(inst.get("Kompisar", 0))
        pappans_dagar = fördela(inst.get("Pappans vänner", 0))
        nils_v_dagar = fördela(inst.get("Nils vänner", 0))
        nils_f_dagar = fördela(inst.get("Nils familj", 0))

        for i in range(7):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0,
                "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": komp_dagar[i],
                "Pappans vänner": pappans_dagar[i],
                "Nils vänner": nils_v_dagar[i],
                "Nils familj": nils_f_dagar[i],
                "Övriga män": 0,
                "Älskar med": 8,
                "Sover med": 1 if i == 6 else 0,
                "Nils sex": nils_sextillfällen[i],
                "DT tid per man (sek)": 0,
                "DT total tid (sek)": 0,
                "Total tid (sek)": 0,
                "Total tid (h)": 0,
                "Prenumeranter": 0,
                "Intäkt ($)": 0,
                "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0,
                "Kompisars lön ($)": 0,
                "Minuter per kille": 0,
                "Scenens längd (h)": 0
            }
            nya_rader.append(rad)

    elif typ == "Vila inspelningsplats":
        for _ in range(dagar):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            def slumpa(värde):
                return int(värde * sample(range(25, 51), 1)[0] / 100)

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0,
                "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": slumpa(inst.get("Kompisar", 0)),
                "Pappans vänner": slumpa(inst.get("Pappans vänner", 0)),
                "Nils vänner": slumpa(inst.get("Nils vänner", 0)),
                "Nils familj": slumpa(inst.get("Nils familj", 0)),
                "Övriga män": 0,
                "Älskar med": 12,
                "Sover med": 1,
                "Nils sex": 0,
                "DT tid per man (sek)": 0,
                "DT total tid (sek)": 0,
                "Total tid (sek)": 0,
                "Total tid (h)": 0,
                "Prenumeranter": 0,
                "Intäkt ($)": 0,
                "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0,
                "Kompisars lön ($)": 0,
                "Minuter per kille": 0,
                "Scenens längd (h)": 0
            }
            nya_rader.append(rad)

    else:
        datum = senaste_datum + timedelta(days=1)

        total_killar = (
            enkel_vag + enkel_anal +
            2 * (dp + dpp + dap) +
            3 * (tpa + tpp + tap)
        )
        dt_total = total_killar * dt_tid_per_man
        penetration_tid = scen_tid * 3600
        total_tid = penetration_tid + dt_total
        min_per_kille = total_tid / total_killar / 60 if total_killar > 0 else 0

        pren = (
            (enkel_vag + enkel_anal) * 1 +
            (dp + dpp + dap) * 5 +
            (tpa + tpp + tap) * 8
        )
        intäkt = pren * 15
        kvinnan_lön = 100
        män_lön = (komp + pappans + nils_v + nils_f + ov) * 200
        komp_lön = intäkt - kvinnan_lön - män_lön if intäkt - kvinnan_lön - män_lön > 0 else 0
        komp_lön = komp_lön / inst.get("Kompisar", 1) if komp > 0 else 0

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
            "Total tid (sek)": total_tid,
            "Total tid (h)": total_tid / 3600,
            "Prenumeranter": pren,
            "Intäkt ($)": intäkt,
            "Kvinnans lön ($)": kvinnan_lön,
            "Mäns lön ($)": män_lön,
            "Kompisars lön ($)": komp_lön,
            "Minuter per kille": min_per_kille,
            "Scenens längd (h)": scen_tid
        }
        nya_rader.append(rad)

    df_new = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
    spara_data(df_new)

def visa_tabell(df):
    st.subheader("📋 Alla scener och vilodagar")

    if df.empty:
        st.info("Ingen data tillgänglig ännu.")
        return

    df_vy = df.copy()
    try:
        df_vy["Datum"] = pd.to_datetime(df_vy["Datum"])
    except:
        pass
    df_vy = df_vy.sort_values("Datum")

    # Formatera kolumnordning
    kolumner = [
        "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
        "Övriga män", "Älskar med", "Sover med", "Nils sex",
        "DT tid per man (sek)", "DT total tid (sek)",
        "Total tid (sek)", "Total tid (h)", "Prenumeranter", "Intäkt ($)",
        "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)", "Minuter per kille",
        "Scenens längd (h)"
    ]
    df_vy = df_vy[kolumner]

    st.dataframe(df_vy, use_container_width=True)

def main():
    # Initiera ark
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()

    # Läs inställningar och data
    inst = läs_inställningar()
    df = ladda_data()

    # Titelsektion
    st.title("🎬 Malin Filmproduktion")

    # Sidopanel – redigerbara inställningar
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

    # Visa tabell med alla rader
    visa_tabell(df)

if __name__ == "__main__":
    main()
