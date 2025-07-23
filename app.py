import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Spreadsheet-URL
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
sh = gc.open_by_url(SPREADSHEET_URL)

# Kolumner
DATA_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män",
    "Älskar med", "Sover med", "Nils sex",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Tid per man (minuter)", "DT tid per man (sek)", "Minuter per kille"
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

def lägg_till_datum(df, inst):
    if df.empty:
        startdatum = inst.get("Startdatum", "2014-03-26")
        return df.assign(Datum=startdatum)
    return df

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

def beräkna_penetration_tid(rad, total_pen_tid=14 * 3600):
    # Standardvärde för enkel = 40 sekunder, viktning:
    # Enkel = 1x, Dubbel = 2x, Trippel = 3x
    enkel = int(rad.get("Enkel vaginal", 0)) + int(rad.get("Enkel anal", 0))
    dubbel = int(rad.get("DP", 0)) + int(rad.get("DPP", 0)) + int(rad.get("DAP", 0))
    trippel = int(rad.get("TPA", 0)) + int(rad.get("TPP", 0)) + int(rad.get("TAP", 0))

    vikt_enkel = enkel * 1
    vikt_dubbel = dubbel * 2
    vikt_trippel = trippel * 3

    total_vikt = vikt_enkel + vikt_dubbel + vikt_trippel
    if total_vikt == 0:
        return 0, 0, 0

    sek_per_vikt = total_pen_tid / total_vikt

    tid_enkel = vikt_enkel * sek_per_vikt
    tid_dubbel = vikt_dubbel * sek_per_vikt
    tid_trippel = vikt_trippel * sek_per_vikt

    return tid_enkel, tid_dubbel, tid_trippel

def beräkna_tid_per_kille(rad, tid_enkel, tid_dubbel, tid_trippel, dt_tid_per_kille):
    enkel_män = int(rad.get("Enkel vaginal", 0)) + int(rad.get("Enkel anal", 0))
    dubbel_män = (int(rad.get("DP", 0)) + int(rad.get("DPP", 0)) + int(rad.get("DAP", 0))) * 2
    trippel_män = (int(rad.get("TPA", 0)) + int(rad.get("TPP", 0)) + int(rad.get("TAP", 0))) * 3

    total_män = enkel_män + dubbel_män + trippel_män
    if total_män == 0:
        return 0

    total_tid_kille = (
        tid_enkel +
        tid_dubbel * 2 +  # varje dubbel ger två killar samma tid
        tid_trippel * 3   # varje trippel ger tre killar samma tid
    )

    # Summerad penetrationstid per man
    tid_per_kille = (total_tid_kille / total_män) if total_män > 0 else 0

    # Lägg till deep throat
    return round((tid_per_kille + dt_tid_per_kille) / 60, 2)  # minuter

def uppdatera_tid_och_intäkt(df, inst):
    tid_per_man = float(inst.get("Tid per man (minuter)", 0))
    dt_tid_per_man = float(inst.get("DT tid per man (sek)", 0))
    dt_tid_per_kille = dt_tid_per_man

    for i, rad in df.iterrows():
        typ = rad.get("Typ", "")

        tot_män = (
            int(rad.get("DP", 0)) * 2 +
            int(rad.get("DPP", 0)) * 3 +
            int(rad.get("DAP", 0)) * 3 +
            int(rad.get("TPA", 0)) * 3 +
            int(rad.get("TPP", 0)) * 3 +
            int(rad.get("TAP", 0)) * 3 +
            int(rad.get("Enkel vaginal", 0)) +
            int(rad.get("Enkel anal", 0)) +
            int(rad.get("Kompisar", 0)) +
            int(rad.get("Pappans vänner", 0)) +
            int(rad.get("Nils vänner", 0)) +
            int(rad.get("Nils familj", 0)) +
            int(rad.get("Övriga män", 0))
        )

        dt_tid = beräkna_dt_tid(dt_tid_per_man, tot_män)
        df.at[i, "DT total tid (sek)"] = int(dt_tid)

        if typ == "Scen":
            tid_enkel, tid_dubbel, tid_trippel = beräkna_penetration_tid(rad)
            tid_kille_min = beräkna_tid_per_kille(rad, tid_enkel, tid_dubbel, tid_trippel, dt_tid_per_kille)
            df.at[i, "Total tid (h)"] = round((tid_enkel + tid_dubbel + tid_trippel + dt_tid) / 3600, 2)
            df.at[i, "Total tid (sek)"] = int(tid_enkel + tid_dubbel + tid_trippel + dt_tid)
            df.at[i, "Tid per man (min)"] = tid_kille_min

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

            kompisar_total = int(inst.get("Kompisar", 1))
            kvar = max(0, df.at[i, "Intäkt ($)"] - 800 - män_lön)
            df.at[i, "Kompisars lön ($)"] = round(kvar / kompisar_total, 2) if kompisar_total > 0 else 0
        else:
            df.at[i, "Prenumeranter"] = 0
            df.at[i, "Intäkt ($)"] = 0
            df.at[i, "Kvinnans lön ($)"] = 0
            df.at[i, "Mäns lön ($)"] = 0
            df.at[i, "Kompisars lön ($)"] = 0
            df.at[i, "Total tid (sek)"] = 0
            df.at[i, "Total tid (h)"] = 0
            df.at[i, "Tid per man (min)"] = 0

    return df

def main():
    try:
        init_sheet("Data", DATA_COLUMNS)
        init_inställningar()

        df = ladda_data()
        inst = läs_inställningar()
        df = säkerställ_kolumner(df)
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
            dagar = st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1)
            submit = st.form_submit_button("Lägg till")

        if submit:
            from random import randint, sample

            nya_rader = []
            senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
            nils_sextillfällen = [0] * 7

            if typ == "Vilovecka hemma":
                tillfällen = sorted(sample(range(6), k=min(2, 6)))  # max 2 tillfällen, ej sista dagen
                for i in tillfällen:
                    nils_sextillfällen[i] = 1

            antal = 7 if typ == "Vilovecka hemma" else int(dagar)

            for i in range(antal):
                datum = senaste_datum + timedelta(days=1)
                senaste_datum = datum

                if typ == "Vilovecka hemma":
                    sover = 1 if i == 6 else 0
                    älskar_med = 8 if i < 6 else 0
                    nils_sex = nils_sextillfällen[i]
                elif typ == "Vila inspelningsplats":
                    älskar_med = 12
                    sover = 1
                    nils_sex = 0
                else:  # Scen
                    älskar_med = 4
                    sover = 1
                    nils_sex = 0

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
                    "Sover med": sover,
                    "Nils sex": nils_sex
                }
                nya_rader.append(rad)

            df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
            spara_data(df)
            st.rerun()

        # Statistikdelen etc. kommer efter detta i del 5

    except Exception as e:
        st.exception(e)

    st.subheader("📊 Statistik")

    tot_män = df[["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män"]].sum().sum()
    tot_rader = len(df)
    kompisar = int(inst.get("Kompisar", 1))
    nils_fam = int(inst.get("Nils familj", 1))

    # Ålder vid sista scen
    sista_datum = df["Datum"].max() if not df.empty else inst.get("Startdatum", "2014-03-26")
    ålder = beräkna_ålder(str(inst.get("Födelsedatum", "1984-03-26")), sista_datum)

    st.write(f"👩 {inst.get('Kvinnans namn')} – Ålder vid sista scen: {ålder} år")
    st.write(f"Totalt antal rader: {tot_rader}")
    st.write(f"Totalt antal män (inkl. alla grupper): {tot_män}")
    st.write(f"Snitt per rad: {round(tot_män / tot_rader, 2) if tot_rader else 0}")
    st.write(f"Älskat: {int(df['Älskar med'].sum())}, Snitt per man (alla grupper): {round(df['Älskar med'].sum() / (kompisar + int(inst.get('Pappans vänner', 0)) + int(inst.get('Nils vänner', 0)) + nils_fam), 2)}")
    st.write(f"Sovit med: {int(df['Sover med'].sum())}, Snitt per Nils familjemedlem: {round(df['Sover med'].sum() / nils_fam, 2)}")

    # Deep throat-tid
    dt_summa = int(df["DT total tid (sek)"].sum())
    st.write(f"💋 Total deep throat-tid (sek): {dt_summa}")

    # Prenumeranter senaste 30 dagar
    if not df.empty:
        df["Datum_dt"] = pd.to_datetime(df["Datum"], errors="coerce")
        senast = df["Datum_dt"].max()
        senaste_30_dagar = df[df["Datum_dt"] >= senast - timedelta(days=30)]
        pren30 = senaste_30_dagar["Prenumeranter"].sum()
        st.write(f"📈 Prenumeranter senaste 30 dagar: {int(pren30)}")
        df = df.drop(columns=["Datum_dt"])

    # Visar minuter varje man får per rad (inkl. DT)
    df["Minuter per man"] = (df["Total tid (sek)"].astype(float) + df["DT total tid (sek)"].astype(float)) / (
        df[["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män"]].sum(axis=1).replace(0, 1)
    ) / 60
    df["Minuter per man"] = df["Minuter per man"].round(2)

    st.dataframe(df.sort_values("Datum"))
