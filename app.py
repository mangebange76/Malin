import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import gspread
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumner för databasen
DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner",
    "Nils vänner", "Nils familj", "Övriga män", "DT tid per man (sek)",
    "Älskar med", "Sover med", "Nils sex", "Tid total (sek)", 
    "DT total tid (sek)", "Summa tid (sek)", "Summa tid (h)",
    "Prenumeranter", "Intäkt total", "Intäkt kvinna", 
    "Intäkt män", "Intäkt kompisar"
]

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

def ladda_data():
    try:
        worksheet = sh.worksheet("Data")
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=DATA_COLUMNS)
    return df

def spara_data(df):
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update("A1", [df.columns.tolist()] + df.fillna("").astype(str).values.tolist())

INST_COLUMNS = ["Inställning", "Värde", "Senast ändrad"]

def init_inställningar():
    try:
        worksheet = sh.worksheet("Inställningar")
    except:
        worksheet = sh.add_worksheet(title="Inställningar", rows="100", cols="3")
        worksheet.update("A1", [INST_COLUMNS])
        standard = [
            ["Val per man (minuter)", "2", datetime.now().strftime("%Y-%m-%d")],
            ["DT tid per man (sek)", "15", datetime.now().strftime("%Y-%m-%d")],
            ["Kvinnans namn", "Malin", datetime.now().strftime("%Y-%m-%d")],
            ["Kvinnans födelsedatum", "1984-03-26", datetime.now().strftime("%Y-%m-%d")],
            ["Startdatum", "2014-03-26", datetime.now().strftime("%Y-%m-%d")],
            ["Kompisar", "100", datetime.now().strftime("%Y-%m-%d")],
            ["Pappans vänner", "40", datetime.now().strftime("%Y-%m-%d")],
            ["Nils vänner", "30", datetime.now().strftime("%Y-%m-%d")],
            ["Nils familj", "20", datetime.now().strftime("%Y-%m-%d")],
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
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    idag = datetime.now().strftime("%Y-%m-%d")
    if nyckel in df["Inställning"].values:
        idx = df[df["Inställning"] == nyckel].index[0]
        worksheet.update_cell(idx + 2, 2, str(värde))
        worksheet.update_cell(idx + 2, 3, idag)
    else:
        worksheet.append_row([nyckel, str(värde), idag])

def beräkna_ålder(födelsedatum, referensdatum):
    född = datetime.strptime(födelsedatum, "%Y-%m-%d")
    ref = datetime.strptime(referensdatum, "%Y-%m-%d")
    return ref.year - född.year - ((ref.month, ref.day) < (född.month, född.day))

DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "DT tid per man (sek)", "DT total tid (sek)",
    "Älskar med", "Sover med", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Nils sex"
]

def säkerställ_kolumner(df):
    for kolumn in DATA_COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = ""
    return df[DATA_COLUMNS]

def spara_data(df):
    df = df.fillna("").astype(str)
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

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

def nästa_datum(df, startdatum):
    if df.empty:
        return datetime.strptime(startdatum, "%Y-%m-%d").date()
    senaste = max(pd.to_datetime(df["Datum"], errors="coerce").dropna(), default=startdatum)
    return senaste.date() + timedelta(days=1)

def beräkna_tid_per_man(antal_män, tid_per_man_min):
    return antal_män * tid_per_man_min * 60  # sekunder

def beräkna_dt_tid(dt_tid_per_man, tot_män):
    if tot_män == 0 or dt_tid_per_man == 0:
        return 0
    pauser = (tot_män - 1) * 2
    extrapauser = (tot_män // 10) * 30
    return tot_män * dt_tid_per_man + pauser + extrapauser

def beräkna_prenumeranter(rad):
    score = (
        int(rad.get("DP", 0)) * 1 +
        int(rad.get("DPP", 0)) * 2 +
        int(rad.get("DAP", 0)) * 2 +
        int(rad.get("TPA", 0)) * 4 +
        int(rad.get("TPP", 0)) * 4 +
        int(rad.get("TAP", 0)) * 6 +
        int(rad.get("Enkel vaginal", 0)) * 0.5 +
        int(rad.get("Enkel anal", 0)) * 0.5
    )
    return int(score)

def uppdatera_tid_och_intäkt(df, inst):
    tid_per_man = float(inst.get("Tid per man (minuter)", 0))
    dt_tid_per_man = float(inst.get("DT tid per man (sek)", 0))
    start_index = 0

    for i, rad in df.iterrows():
        typ = rad.get("Typ", "")
        omgång = df.loc[i]

        tot_män = (
            int(omgång.get("DP", 0)) * 2 +
            int(omgång.get("DPP", 0)) * 3 +
            int(omgång.get("DAP", 0)) * 3 +
            int(omgång.get("TPA", 0)) * 3 +
            int(omgång.get("TPP", 0)) * 3 +
            int(omgång.get("TAP", 0)) * 3 +
            int(omgång.get("Enkel vaginal", 0)) +
            int(omgång.get("Enkel anal", 0)) +
            int(omgång.get("Kompisar", 0)) +
            int(omgång.get("Pappans vänner", 0)) +
            int(omgång.get("Nils vänner", 0)) +
            int(omgång.get("Nils familj", 0)) +
            int(omgång.get("Övriga män", 0))
        )

        total_tid = beräkna_tid_per_man(tot_män, tid_per_man)
        dt_tid = beräkna_dt_tid(dt_tid_per_man, tot_män)
        total_tid += dt_tid

        df.at[i, "DT total tid (sek)"] = int(dt_tid)
        df.at[i, "Total tid (sek)"] = int(total_tid)
        df.at[i, "Total tid (h)"] = round(total_tid / 3600, 2)

        if typ == "Scen":
            pren = beräkna_prenumeranter(omgång)
            df.at[i, "Prenumeranter"] = pren
            df.at[i, "Intäkt ($)"] = round(pren * 15, 2)
            df.at[i, "Kvinnans lön ($)"] = 800
            män_lön = 200 * (
                int(omgång.get("Pappans vänner", 0)) +
                int(omgång.get("Nils vänner", 0)) +
                int(omgång.get("Nils familj", 0)) +
                int(omgång.get("Övriga män", 0))
            )
            df.at[i, "Mäns lön ($)"] = män_lön

            kompisar_total = int(inst.get("Kompisar", 1))
            kvar = max(0, df.at[i, "Intäkt ($)"] - 800 - män_lön)
            df.at[i, "Kompisars lön ($)"] = round(kvar / kompisar_total, 2) if kompisar_total > 0 else 0
        else:
            df.at[i, "Prenumeranter"] = 0
            df.at[i, "Intäkt ($)"] = 0
            df.at[i, "Kvinnans lön ($)"] = 0
            df.at[i, "Mäns lön ($)"] = 0
            df.at[i, "Kompisars lön ($)"] = 0

    return df

def main():
    df = ladda_data()
    inst = läs_inställningar()

    df = säkerställ_kolumner(df)
    df = lägg_till_datum(df, inst)
    df = uppdatera_tid_och_intäkt(df, inst)

    st.title("🎬 Malin Filmproduktion – Scenplanering")

    with st.sidebar:
        st.header("Inställningar")
        namn = st.text_input("Kvinnans namn", value=str(inst.get("Kvinnans namn", "")))
        född = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1984-03-26")))
        startdatum = st.date_input("Startdatum (första scen)", value=pd.to_datetime(inst.get("Startdatum", "2014-03-26")))

        spara_inställning("Kvinnans namn", namn)
        spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
        spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))

        st.divider()
        for fält in [
            "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
            "Tid per man (minuter)", "DT tid per man (sek)"
        ]:
            val = st.number_input(fält, value=float(inst.get(fält, 0)), min_value=0.0, step=1.0)
            spara_inställning(fält, val)

    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        dp = st.number_input("DP", min_value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, step=1)
        dap = st.number_input("DAP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)
        enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1)
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)

        komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)))
        pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)))
        nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)))
        nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)))
        ov = st.number_input("Övriga män", min_value=0, step=1)

        älskar = st.number_input("Antal älskar med", min_value=0, step=1)
        sover = st.number_input("Antal sover med", min_value=0, step=1)

        dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1)
        submit = st.form_submit_button("Lägg till")

    if submit:
        from random import randint

        nya_rader = []
        senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
        nils_maxsex = 2 if typ == "Vilovecka hemma" else 0
        nils_sextillfällen = [0] * 7
        if typ == "Vilovecka hemma":
            tillfällen = sorted(randint(0, 6) for _ in range(nils_maxsex))
            for i in tillfällen:
                nils_sextillfällen[i] = 1

        antal = 7 if typ == "Vilovecka hemma" else int(dagar)

        for i in range(antal):
            datum = senaste_datum + pd.Timedelta(days=1)
            senaste_datum = datum
            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": dp,
                "DPP": dpp,
                "DAP": dap,
                "TPA": tpa,
                "TPP": tpp,
                "TAP": tap,
                "Enkel vaginal": enkel_vag,
                "Enkel anal": enkel_anal,
                "Kompisar": komp,
                "Pappans vänner": pappans,
                "Nils vänner": nils_v,
                "Nils familj": nils_f,
                "Övriga män": ov,
                "Antal älskar med": älskar * 7 if typ == "Vilovecka hemma" else älskar,
                "Antal sover med": sover * 7 if typ == "Vilovecka hemma" else sover,
                "Nils sex": nils_sextillfällen[i] if typ == "Vilovecka hemma" else 0
            }
            nya_rader.append(rad)

        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        spara_data(df)
        st.rerun()

    st.subheader("📊 Statistik")

    tot_män = df[["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män"]].sum().sum()
    tot_rader = len(df)
    kompisar = int(inst.get("Kompisar", 1))
    nils_fam = int(inst.get("Nils familj", 1))

    st.write(f"👩 {inst.get('Kvinnans namn')} – Ålder vid sista scen: {beräkna_ålder(inst)} år")
    st.write(f"Totalt antal rader: {tot_rader}")
    st.write(f"Totalt antal män (inkl. alla grupper): {tot_män}")
    st.write(f"Snitt per scen: {round(tot_män / tot_rader, 2) if tot_rader else 0}")
    st.write(f"Älskat: {int(df['Antal älskar med'].sum())}, Snitt per man: {round(df['Antal älskar med'].sum() / kompisar, 2) if kompisar else 0}")
    st.write(f"Sovit med: {int(df['Antal sover med'].sum())}, Snitt per Nils familjemedlem: {round(df['Antal sover med'].sum() / nils_fam, 2) if nils_fam else 0}")

    st.dataframe(df.sort_values("Datum"))
