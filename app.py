from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Autentisering och Google Sheets-anslutning
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumner
DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "DT tid per man (sek)", "DT total tid (sek)",
    "Älskar med", "Sover med", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Nils sex", "Tid per kille (min)"
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
            ["Tid per man (minuter)", "2", datetime.now().strftime("%Y-%m-%d")],
            ["DT tid per man (sek)", "15", datetime.now().strftime("%Y-%m-%d")],
            ["Kvinnans namn", "Malin", datetime.now().strftime("%Y-%m-%d")],
            ["Födelsedatum", "1984-03-26", datetime.now().strftime("%Y-%m-%d")],
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

def nästa_datum(df, startdatum):
    if df.empty:
        return datetime.strptime(startdatum, "%Y-%m-%d").date()
    senaste = max(pd.to_datetime(df["Datum"], errors="coerce").dropna(), default=startdatum)
    return senaste.date() + timedelta(days=1)

def beräkna_dt_tid(dt_tid_per_man, tot_män):
    if tot_män == 0 or dt_tid_per_man == 0:
        return 0
    pauser = (tot_män - 1) * 2
    extrapauser = (tot_män // 10) * 30
    return tot_män * dt_tid_per_man + pauser + extrapauser

def beräkna_ålder(födelsedatum, slutdatum):
    födelsedatum = pd.to_datetime(födelsedatum)
    slutdatum = pd.to_datetime(slutdatum)
    return int((slutdatum - födelsedatum).days / 365.25)

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
    tid_enkel_std = 40  # sekunder per tillfälle (enkel)
    tid_total = 14 * 3600  # 14 timmar i sekunder

    tid_per_man = float(inst.get("Tid per man (minuter)", 0))
    dt_tid_per_man = float(inst.get("DT tid per man (sek)", 0))
    kompisar_total = int(inst.get("Kompisar", 1))

    for i, rad in df.iterrows():
        typ = rad.get("Typ", "")
        if typ == "Scen":
            dp = int(rad.get("DP", 0))
            dpp = int(rad.get("DPP", 0))
            dap = int(rad.get("DAP", 0))
            tpa = int(rad.get("TPA", 0))
            tpp = int(rad.get("TPP", 0))
            tap = int(rad.get("TAP", 0))
            enkel_v = int(rad.get("Enkel vaginal", 0))
            enkel_a = int(rad.get("Enkel anal", 0))

            antal_enkel = enkel_v + enkel_a
            antal_dubbel = dp + dpp + dap
            antal_trippel = tpa + tpp + tap

            vikt_e = 1 * antal_enkel
            vikt_d = 3 * antal_dubbel  # vikt 3x mot enkel
            vikt_t = 6 * antal_trippel  # vikt 6x mot enkel
            vikt_sum = vikt_e + vikt_d + vikt_t

            tid_per_vikt = tid_total / vikt_sum if vikt_sum else 0

            tid_e = tid_per_vikt * 1
            tid_d = tid_per_vikt * 3
            tid_t = tid_per_vikt * 6

            tid_enkel_total = antal_enkel * tid_e
            tid_dubbel_total = antal_dubbel * tid_d
            tid_trippel_total = antal_trippel * tid_t

            # Totalt antal män
            tot_män = (
                antal_enkel * 1 +
                antal_dubbel * 2 +
                antal_trippel * 3 +
                int(rad.get("Kompisar", 0)) +
                int(rad.get("Pappans vänner", 0)) +
                int(rad.get("Nils vänner", 0)) +
                int(rad.get("Nils familj", 0)) +
                int(rad.get("Övriga män", 0))
            )

            # Deep throat-tid
            dt_tid = beräkna_dt_tid(dt_tid_per_man, tot_män)

            df.at[i, "DT total tid (sek)"] = int(dt_tid)
            df.at[i, "Total tid (sek)"] = int(tid_total)
            df.at[i, "Total tid (h)"] = round(tid_total / 3600, 2)

            # Tid per man (enkel/dubbel/trippel)
            total_tid_kille = (
                antal_enkel * tid_e +
                antal_dubbel * tid_d * 2 +
                antal_trippel * tid_t * 3
            )

            total_tid_kille += dt_tid  # lägg till deep throat

            minuter_per_kille = total_tid_kille / tot_män / 60 if tot_män else 0
            df.at[i, "Minuter per kille"] = round(minuter_per_kille, 2)

            # Ekonomi
            pren = beräkna_prenumeranter(rad)
            df.at[i, "Prenumeranter"] = pren
            df.at[i, "Intäkt ($)"] = round(pren * 15, 2)
            df.at[i, "Kvinnans lön ($)"] = 800
            män_lön = 200 * (
                int(rad.get("Pappans vänner", 0)) +
                int(rad.get("Nils vänner", 0)) +
                int(rad.get("Nils familj", 0)) +
                int(rad.get("Övriga män", 0))
            )
            df.at[i, "Mäns lön ($)"] = män_lön
            kvar = max(0, df.at[i, "Intäkt ($)"] - 800 - män_lön)
            df.at[i, "Kompisars lön ($)"] = round(kvar / kompisar_total, 2) if kompisar_total > 0 else 0

        else:
            # Vila
            df.at[i, "DT total tid (sek)"] = 0
            df.at[i, "Total tid (sek)"] = 0
            df.at[i, "Total tid (h)"] = 0
            df.at[i, "Minuter per kille"] = 0
            df.at[i, "Prenumeranter"] = 0
            df.at[i, "Intäkt ($)"] = 0
            df.at[i, "Kvinnans lön ($)"] = 0
            df.at[i, "Mäns lön ($)"] = 0
            df.at[i, "Kompisars lön ($)"] = 0

    return df

def lägg_till_rader(df, inst):
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

        dagar = st.number_input("Antal vilodagar (vid vila)", min_value=1, step=1)
        submit = st.form_submit_button("Lägg till")

    if submit:
        from random import sample
        nya_rader = []

        senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
        antal = 7 if typ == "Vilovecka hemma" else int(dagar)

        nils_sextillfällen = [0] * antal
        if typ == "Vilovecka hemma":
            nils_sex_dagar = sample(range(6), k=min(2, 6))  # max 2 tillfällen av första 6
            for i in nils_sex_dagar:
                nils_sextillfällen[i] = 1

        for i in range(antal):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            älskar_med = 4 if typ == "Scen" else (12 if typ == "Vila inspelningsplats" else 0)
            sover_med = 1 if (typ == "Scen" or typ == "Vila inspelningsplats") else (1 if i == 6 else 0)
            if typ == "Vilovecka hemma":
                älskar_med = 8  # alltid 8 per dag

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
                "Älskar med": älskar_med,
                "Sover med": sover_med,
                "Nils sex": nils_sextillfällen[i] if typ == "Vilovecka hemma" else 0
            }
            nya_rader.append(rad)

        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        spara_data(df)
        st.rerun()

def beräkna_ålder(födelsedatum, slutdatum):
    födelse = pd.to_datetime(födelsedatum)
    slut = pd.to_datetime(slutdatum)
    return int((slut - födelse).days // 365.25)

def visa_statistik(df, inst):
    st.subheader("📊 Statistik")

    tot_män = df[["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män"]].fillna(0).astype(int).sum().sum()
    tot_rader = len(df)
    kompisar = int(inst.get("Kompisar", 1))
    nils_fam = int(inst.get("Nils familj", 1))

    sista_datum = df["Datum"].max() if not df.empty else inst.get("Startdatum", "2014-03-26")
    ålder = beräkna_ålder(inst.get("Födelsedatum", "1984-03-26"), sista_datum)

    st.write(f"👩 {inst.get('Kvinnans namn')} – Ålder vid sista scen: {ålder} år")
    st.write(f"Totalt antal rader: {tot_rader}")
    st.write(f"Totalt antal män (inkl. alla grupper): {tot_män}")
    st.write(f"Snitt antal män per rad: {round(tot_män / tot_rader, 2) if tot_rader else 0}")

    älskat_sum = int(df['Älskar med'].sum())
    sover_sum = int(df['Sover med'].sum())
    st.write(f"❤️ Älskat totalt: {älskat_sum}, Snitt per man (alla grupper): {round(älskat_sum / (kompisar + inst.get('Pappans vänner',0) + inst.get('Nils vänner',0) + inst.get('Nils familj',0)), 2)}")
    st.write(f"🛏️ Sovit med totalt: {sover_sum}, Snitt per Nils familjemedlem: {round(sover_sum / nils_fam, 2) if nils_fam else 0}")

    dt_tid = int(df["DT total tid (sek)"].sum())
    st.write(f"💋 Total Deep Throat-tid: {dt_tid} sekunder ({round(dt_tid/60, 2)} minuter)")

    # Prenumeranter senaste 30 dagar
    if not df.empty:
        df["Datum_dt"] = pd.to_datetime(df["Datum"], errors="coerce")
        senast = df["Datum_dt"].max()
        senaste_30_dagar = df[df["Datum_dt"] >= senast - pd.Timedelta(days=30)]
        pren30 = senaste_30_dagar["Prenumeranter"].sum()
        st.write(f"📈 Prenumeranter senaste 30 dagar: {int(pren30)}")
        df.drop(columns=["Datum_dt"], inplace=True, errors="ignore")

    # Snitt minuter per man (inkl. DT)
    df["Total tid (sek)"] = df["Total tid (sek)"].fillna(0).astype(float)
    df["Total män"] = (
        df["DP"].fillna(0).astype(int) * 2 +
        df["DPP"].fillna(0).astype(int) * 3 +
        df["DAP"].fillna(0).astype(int) * 3 +
        df["TPA"].fillna(0).astype(int) * 3 +
        df["TPP"].fillna(0).astype(int) * 3 +
        df["TAP"].fillna(0).astype(int) * 3 +
        df["Enkel vaginal"].fillna(0).astype(int) +
        df["Enkel anal"].fillna(0).astype(int) +
        df["Kompisar"].fillna(0).astype(int) +
        df["Pappans vänner"].fillna(0).astype(int) +
        df["Nils vänner"].fillna(0).astype(int) +
        df["Nils familj"].fillna(0).astype(int) +
        df["Övriga män"].fillna(0).astype(int)
    )

    df["Minuter per man"] = df.apply(
        lambda rad: round(rad["Total tid (sek)"] / 60 / rad["Total män"], 2) if rad["Total män"] > 0 else 0,
        axis=1
    )

    st.write("🕒 Genomsnittlig tid per man per scen (inkl. DT):")
    st.dataframe(df[["Datum", "Typ", "Total tid (sek)", "Total män", "Minuter per man"]].sort_values("Datum"))
