import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from random import sample, shuffle

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
    st.subheader("Nuvarande inställningar")
    for nyckel in ["Kvinnans namn", "Födelsedatum", "Startdatum", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        st.markdown(f"- **{nyckel}**: {inst.get(nyckel)}")

def beräkna_total_tid_rad(rad):
    total_penetration_tid = 0
    total_killar = 0

    enkel_tid = 40  # sekunder
    dubbel_tid = 60
    trippel_tid = 90

    total_penetration_tid += rad["Enkel vaginal"] * enkel_tid
    total_killar += rad["Enkel vaginal"]
    total_penetration_tid += rad["Enkel anal"] * enkel_tid
    total_killar += rad["Enkel anal"]

    for kol in ["DP", "DPP", "DAP"]:
        total_penetration_tid += rad[kol] * dubbel_tid
        total_killar += rad[kol] * 2

    for kol in ["TPA", "TPP", "TAP"]:
        total_penetration_tid += rad[kol] * trippel_tid
        total_killar += rad[kol] * 3

    dt_total_tid = total_killar * rad["DT tid per man (sek)"]
    total_tid = total_penetration_tid + dt_total_tid
    return total_penetration_tid, dt_total_tid, total_tid, total_killar

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        dp = st.number_input("DP", min_value=0, step=1, key="dp")
        dpp = st.number_input("DPP", min_value=0, step=1, key="dpp")
        dap = st.number_input("DAP", min_value=0, step=1, key="dap")
        tpa = st.number_input("TPA", min_value=0, step=1, key="tpa")
        tpp = st.number_input("TPP", min_value=0, step=1, key="tpp")
        tap = st.number_input("TAP", min_value=0, step=1, key="tap")
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1, key="enkel_vag")
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1, key="enkel_anal")
        komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)), key="komp")
        pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)), key="pappans")
        nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)), key="nils_v")
        nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)), key="nils_f")
        ov = st.number_input("Övriga män", min_value=0, step=1, key="ov")
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1, key="dt_tid")
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.25, key="scen_tid")
        älskar = st.number_input("Antal älskar med", min_value=0, step=1, key="älskar")
        sover = st.number_input("Antal sover med", min_value=0, step=1, key="sover")
        dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1, key="dagar")
        submit = st.form_submit_button("Lägg till")

        # Visa beräkning av total tid och minuter per kille (för feedback innan submit)
        if typ == "Scen":
            rad_tmp = {
                "DP": dp, "DPP": dpp, "DAP": dap,
                "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
                "DT tid per man (sek)": dt_tid_per_man
            }
            penetration, dt, total, killar = beräkna_total_tid_rad(rad_tmp)
            min_per_kille = (total / 60) / killar if killar > 0 else 0
            st.info(f"Total tid: {total/3600:.2f} h – Tid per kille (inkl. DT): {min_per_kille:.2f} minuter")
            if total/3600 > 18:
                st.warning("⚠️ Total tid överskrider 18 timmar!")

    if submit:
        df = process_lägg_till_rader(
            df=df,
            inst=inst,
            typ=typ,
            dp=dp, dpp=dpp, dap=dap,
            tpa=tpa, tpp=tpp, tap=tap,
            enkel_vag=enkel_vag, enkel_anal=enkel_anal,
            komp=komp, pappans=pappans, nils_v=nils_v, nils_f=nils_f, ov=ov,
            dt_tid_per_man=dt_tid_per_man,
            scen_tid=scen_tid,
            älskar=älskar, sover=sover,
            dagar=dagar
        )

        # Rensa formuläret
        for key in st.session_state.keys():
            if key.startswith(("dp", "dpp", "dap", "tpa", "tpp", "tap", "enkel", "komp", "pappans", "nils", "ov", "dt", "scen", "älskar", "sover", "dagar")):
                st.session_state[key] = 0 if isinstance(st.session_state[key], int) else 0.0
        st.session_state["typ"] = "Scen"

        st.success("Raden/raderna har lagts till!")
        st.experimental_rerun()

def beräkna_total_tid_rad(rad):
    # Standardtider (i sekunder) per tillfälle
    tid_enkel = 40  # sek
    tid_dubbel = 120  # sek
    tid_trippel = 180  # sek

    # Antal tillfällen
    enkel = rad.get("Enkel vaginal", 0) + rad.get("Enkel anal", 0)
    dubbel = rad.get("DP", 0) + rad.get("DPP", 0) + rad.get("DAP", 0)
    trippel = rad.get("TPA", 0) + rad.get("TPP", 0) + rad.get("TAP", 0)

    tid_penetration = (enkel * tid_enkel) + (dubbel * tid_dubbel) + (trippel * tid_trippel)
    dt_per_man = rad.get("DT tid per man (sek)", 0)

    # Beräkna antal killar
    antal_killar = (
        enkel * 1 +
        dubbel * 2 +
        trippel * 3
    )

    total_dt_tid = antal_killar * dt_per_man

    total_tid = tid_penetration + total_dt_tid
    total_tid_h = total_tid / 3600
    minuter_per_kille = (total_tid / 60) / antal_killar if antal_killar > 0 else 0

    return tid_penetration, total_dt_tid, total_tid, antal_killar


def beräkna_prenumeranter(rad):
    enkel = rad.get("Enkel vaginal", 0) + rad.get("Enkel anal", 0)
    dubbel = rad.get("DP", 0) + rad.get("DPP", 0) + rad.get("DAP", 0)
    trippel = rad.get("TPA", 0) + rad.get("TPP", 0) + rad.get("TAP", 0)
    return int(enkel * 1 + dubbel * 5 + trippel * 8)


def beräkna_intäkter(prenumeranter):
    return prenumeranter * 15  # USD


def beräkna_löner(rad, inst, total_intäkt):
    kvinna_lön = 100
    män = (
        rad.get("Kompisar", 0)
        + rad.get("Pappans vänner", 0)
        + rad.get("Nils vänner", 0)
        + rad.get("Nils familj", 0)
        + rad.get("Övriga män", 0)
    )
    man_lön = män * 200
    kompisar_total = inst.get("Kompisar", 0)
    kompisar_lön = 0
    if kompisar_total > 0:
        överskott = total_intäkt - kvinna_lön - man_lön
        kompisar_lön = max(0, överskott / kompisar_total)
    return kvinna_lön, man_lön, kompisar_lön


def process_lägg_till_rader(df, inst, typ, dp, dpp, dap, tpa, tpp, tap,
                             enkel_vag, enkel_anal, komp, pappans, nils_v, nils_f, ov,
                             dt_tid_per_man, scen_tid, älskar, sover, dagar):
    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    nils_sextillfällen = [0] * 7

    if typ == "Vilovecka hemma":
        from random import sample
        tillfällen = sorted(sample(range(6), k=min(2, 6)))
        for i in tillfällen:
            nils_sextillfällen[i] = 1

    antal = 7 if typ == "Vilovecka hemma" else int(dagar)
    nya_rader = []

    for i in range(antal):
        datum = senaste_datum + timedelta(days=1)
        senaste_datum = datum

        # Standardvärden per rad
        komp_i, pappans_i, nils_v_i, nils_f_i = komp, pappans, nils_v, nils_f
        if typ == "Vilovecka hemma":
            total_k = int(inst.get("Kompisar", 0) * 1.5)
            komp_i = fördelningshjälp(i, antal, total_k)
            total_p = int(inst.get("Pappans vänner", 0) * 1.5)
            pappans_i = fördelningshjälp(i, antal, total_p)
            total_nv = int(inst.get("Nils vänner", 0) * 1.5)
            nils_v_i = fördelningshjälp(i, antal, total_nv)
            total_nf = int(inst.get("Nils familj", 0) * 1.5)
            nils_f_i = fördelningshjälp(i, antal, total_nf)
            älskar_med = 8 if i < 6 else 0
            sover_med = 1 if i == 6 else 0
            nils_sex = nils_sextillfällen[i]
        elif typ == "Vila inspelningsplats":
            komp_i = slumpandel(inst.get("Kompisar", 0))
            pappans_i = slumpandel(inst.get("Pappans vänner", 0))
            nils_v_i = slumpandel(inst.get("Nils vänner", 0))
            nils_f_i = slumpandel(inst.get("Nils familj", 0))
            älskar_med = 12
            sover_med = 1
            nils_sex = 0
        else:
            älskar_med = älskar
            sover_med = sover
            nils_sex = 0

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

        if typ == "Scen":
            pen_tid, dt_tid, tot_tid, antal_killar = beräkna_total_tid_rad(rad)
            pren = beräkna_prenumeranter(rad)
            intäkt = beräkna_intäkter(pren)
            kvinna, man, komp_lön = beräkna_löner(rad, inst, intäkt)
            min_per_kille = (tot_tid / 60) / antal_killar if antal_killar > 0 else 0

            rad.update({
                "DT total tid (sek)": dt_tid,
                "Total tid (sek)": tot_tid,
                "Total tid (h)": round(tot_tid / 3600, 2),
                "Prenumeranter": pren,
                "Intäkt ($)": intäkt,
                "Kvinnans lön ($)": kvinna,
                "Mäns lön ($)": man,
                "Kompisars lön ($)": komp_lön,
                "Minuter per kille": round(min_per_kille, 2)
            })
        else:
            rad.update({
                "DT total tid (sek)": "",
                "Total tid (sek)": "",
                "Total tid (h)": "",
                "Prenumeranter": "",
                "Intäkt ($)": "",
                "Kvinnans lön ($)": "",
                "Mäns lön ($)": "",
                "Kompisars lön ($)": "",
                "Minuter per kille": ""
            })

        nya_rader.append(rad)

    return pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)


def slumpandel(maxvärde):
    from random import randint
    return randint(int(maxvärde * 0.25), int(maxvärde * 0.5)) if maxvärde > 0 else 0


def fördelningshjälp(index, antal, total):
    per_dag = total // antal
    extra = total % antal
    return per_dag + 1 if index < extra else per_dag

def main():
    st.set_page_config(page_title="Malin Produktion", layout="wide")

    # Autentisering och initiering
    client = auth_gsheets()
    sh = client.open_by_url(SPREADSHEET_URL)
    ws_data = sh.worksheet("Data")
    ws_inst = sh.worksheet("Inställningar")

    # Läs data och inställningar
    df = load_data()
    inst = läs_inställningar(ws_inst)

    # Sidopanel för inställningar
    st.sidebar.title("Inställningar")
    inst_keys = ["Startdatum", "Kvinnans namn", "Födelsedatum", "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]
    inst_inputs = {}

    for key in inst_keys:
        if "datum" in key.lower():
            inst_inputs[key] = st.sidebar.text_input(key, value=str(inst.get(key, "")))
        else:
            inst_inputs[key] = st.sidebar.number_input(key, min_value=0, step=1, value=int(inst.get(key, 0)))

    if st.sidebar.button("Spara inställningar"):
        ny_inst = pd.DataFrame({
            "Inställning": inst_keys,
            "Värde": [inst_inputs[k] for k in inst_keys],
            "Senast ändrad": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        ws_inst.clear()
        ws_inst.update([ny_inst.columns.values.tolist()] + ny_inst.values.tolist())
        st.experimental_rerun()

    st.title(f"Malin Produktion – {inst.get('Kvinnans namn', 'Malin')}")
    visa_inställningar(inst)

    scenformulär(df, inst)

    # Visa hela databasen
    st.subheader("Alla scener och vilodagar")
    st.dataframe(df, use_container_width=True)

    # Spara ändrad data
    if st.button("Spara till databasen"):
        save_data(df)
