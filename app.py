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

def beräkna_rad(row):
    if row["Typ"] != "Scen":
        return row

    # Prenumeranter
    enkel = int(row.get("Enkel vaginal", 0)) + int(row.get("Enkel anal", 0))
    dubbel = int(row.get("DP", 0)) + int(row.get("DPP", 0)) + int(row.get("DAP", 0))
    trippel = int(row.get("TPA", 0)) + int(row.get("TPP", 0)) + int(row.get("TAP", 0))
    pren = enkel * 1 + dubbel * 5 + trippel * 8
    row["Prenumeranter"] = pren

    # Intäkter
    intäkt = pren * 15
    row["Intäkt ($)"] = intäkt

    # Kvinnans lön
    row["Kvinnans lön ($)"] = 100

    # Mäns lön (200 USD per man utom kompisar)
    totala_män = (
        int(row.get("Kompisar", 0)) +
        int(row.get("Pappans vänner", 0)) +
        int(row.get("Nils vänner", 0)) +
        int(row.get("Nils familj", 0)) +
        int(row.get("Övriga män", 0))
    )
    icke_kompisar = totala_män - int(row.get("Kompisar", 0))
    row["Mäns lön ($)"] = 200 * icke_kompisar

    # Kompisars lön = det som blir kvar
    komp = int(row.get("Kompisar", 0))
    övrigt = intäkt - row["Kvinnans lön ($)"] - row["Mäns lön ($)"]
    if komp > 0:
        row["Kompisars lön ($)"] = max(övrigt, 0) / komp
    else:
        row["Kompisars lön ($)"] = 0

    # DT total tid
    dt_tid_per_man = int(row.get("DT tid per man (sek)", 0))
    row["DT total tid (sek)"] = dt_tid_per_man * totala_män

    # Total tid
    scen_tid = float(row.get("Scenens längd (h)", 0))
    total_tid_sec = scen_tid * 3600 + row["DT total tid (sek)"]
    row["Total tid (sek)"] = total_tid_sec
    row["Total tid (h)"] = round(total_tid_sec / 3600, 2)

    # Minuter per kille
    if totala_män > 0:
        row["Minuter per kille"] = round(total_tid_sec / 60 / totala_män, 2)
    else:
        row["Minuter per kille"] = 0

    return row

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
        submit = st.form_submit_button("Lägg till")

    if submit:
        senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
        nils_sextillfällen = [0] * 7
        nya_rader = []

        if typ == "Vilovecka hemma":
            tillfällen = sorted(sample(range(6), k=min(2, 6)))
            for i in tillfällen:
                nils_sextillfällen[i] = 1

            def fördela_antal(total, dagar=7):
                extra = int(round(total * 1.5))
                base = extra // dagar
                rest = extra % dagar
                fördelning = [base] * dagar
                for i in range(rest):
                    fördelning[i] += 1
                return fördelning

            komp_list = fördela_antal(inst.get("Kompisar", 0))
            pappans_list = fördela_antal(inst.get("Pappans vänner", 0))
            nils_v_list = fördela_antal(inst.get("Nils vänner", 0))
            nils_f_list = fördela_antal(inst.get("Nils familj", 0))

        for i in range(7 if typ == "Vilovecka hemma" else int(dagar)):
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
                komp_i = int(inst.get("Kompisar", 0) * 0.25) + sample(range(int(inst.get("Kompisar", 0) * 0.25),
                                                                          int(inst.get("Kompisar", 0) * 0.5) + 1), 1)[0] % int(inst.get("Kompisar", 0))
                pappans_i = int(inst.get("Pappans vänner", 0) * 0.25) + sample(range(int(inst.get("Pappans vänner", 0) * 0.25),
                                                                                   int(inst.get("Pappans vänner", 0) * 0.5) + 1), 1)[0] % int(inst.get("Pappans vänner", 0))
                nils_v_i = int(inst.get("Nils vänner", 0) * 0.25) + sample(range(int(inst.get("Nils vänner", 0) * 0.25),
                                                                                 int(inst.get("Nils vänner", 0) * 0.5) + 1), 1)[0] % int(inst.get("Nils vänner", 0))
                nils_f_i = int(inst.get("Nils familj", 0) * 0.25) + sample(range(int(inst.get("Nils familj", 0) * 0.25),
                                                                                 int(inst.get("Nils familj", 0) * 0.5) + 1), 1)[0] % int(inst.get("Nils familj", 0))
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
                "Kompisar": komp_i, "Pappans vänner": pappans_i, "Nils vänner": nils_v_i, "Nils familj": nils_f_i,
                "Övriga män": ov,
                "Älskar med": älskar_med,
                "Sover med": sover_med,
                "Nils sex": nils_sex,
                "DT tid per man (sek)": dt_tid_per_man,
                "Scenens längd (h)": scen_tid
            }

            rad = beräkna_rad(rad)
            nya_rader.append(rad)

        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        spara_data(df)
        st.rerun()

def beräkna_alla_fält(df, inst):
    df = df.copy()

    # Initiera kolumner
    df["DT total tid (sek)"] = 0
    df["Total tid (sek)"] = 0
    df["Total tid (h)"] = 0
    df["Prenumeranter"] = 0
    df["Intäkt ($)"] = 0
    df["Kvinnans lön ($)"] = 0
    df["Mäns lön ($)"] = 0
    df["Kompisars lön ($)"] = 0
    df["Minuter per kille"] = 0

    antal_kompisar = float(inst.get("Kompisar", 1))
    antal_pappans = float(inst.get("Pappans vänner", 1))
    antal_nils_v = float(inst.get("Nils vänner", 1))
    antal_nils_f = float(inst.get("Nils familj", 1))

    for ix, rad in df.iterrows():
        if rad["Typ"] != "Scen":
            continue

        # Summera penetrationstillfällen
        enkel = int(rad.get("Enkel vaginal", 0)) + int(rad.get("Enkel anal", 0))
        dubbel = int(rad.get("DP", 0)) + int(rad.get("DPP", 0)) + int(rad.get("DAP", 0))
        trippel = int(rad.get("TPA", 0)) + int(rad.get("TPP", 0)) + int(rad.get("TAP", 0))

        # Deep throat
        dt_tid_per_man = int(rad.get("DT tid per man (sek)", 0))
        dt_total = dt_tid_per_man * (
            int(rad.get("Kompisar", 0))
            + int(rad.get("Pappans vänner", 0))
            + int(rad.get("Nils vänner", 0))
            + int(rad.get("Nils familj", 0))
            + int(rad.get("Övriga män", 0))
        )
        df.at[ix, "DT total tid (sek)"] = dt_total

        # Total penetrationstid (i sekunder)
        scen_tid_h = float(rad.get("Scenens längd (h)", 0))
        scen_tid_s = scen_tid_h * 3600
        total_tid = scen_tid_s + dt_total
        df.at[ix, "Total tid (sek)"] = total_tid
        df.at[ix, "Total tid (h)"] = round(total_tid / 3600, 2)

        # Prenumeranter
        pren = enkel * 1 + dubbel * 5 + trippel * 8
        df.at[ix, "Prenumeranter"] = pren
        df.at[ix, "Intäkt ($)"] = round(pren * 15, 2)

        # Lön
        df.at[ix, "Kvinnans lön ($)"] = 100
        antal_män = (
            int(rad.get("Kompisar", 0))
            + int(rad.get("Pappans vänner", 0))
            + int(rad.get("Nils vänner", 0))
            + int(rad.get("Nils familj", 0))
            + int(rad.get("Övriga män", 0))
        )
        lön_män = (
            int(rad.get("Pappans vänner", 0)) * 200
            + int(rad.get("Nils vänner", 0)) * 200
            + int(rad.get("Nils familj", 0)) * 200
        )
        df.at[ix, "Mäns lön ($)"] = lön_män

        # Kompisars lön: resterande delas på inställningens antal
        intäkt = df.at[ix, "Intäkt ($)"]
        lön_kvar = intäkt - 100 - lön_män
        if antal_kompisar > 0:
            komp_lön = round(max(0, lön_kvar) / antal_kompisar, 2)
        else:
            komp_lön = 0
        df.at[ix, "Kompisars lön ($)"] = komp_lön

        # Tid per kille (i minuter)
        if antal_män > 0:
            df.at[ix, "Minuter per kille"] = round(total_tid / 60 / antal_män, 1)

    return df

def main():
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()
    inst = läs_inställningar()
    df = ladda_data()

    st.title("🎬 Malin Filmproduktion")

    # Sidopanel – inställningar
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
            st.rerun()

    # Formulär för att lägga till scen/vila
    scenformulär(df, inst)

    # Gör beräkningar
    df = beräkna_alla_fält(df, inst)

    # Visa statistik
    st.subheader("📊 Statistik")
    st.dataframe(df.sort_values("Datum", ascending=False), use_container_width=True)

    # Visa total summering
    if not df.empty:
        totaltid = df["Total tid (h)"].astype(float).sum()
        intäkter = df["Intäkt ($)"].astype(float).sum()
        pren = df["Prenumeranter"].astype(int).sum()
        st.markdown(f"""
        **Total tid:** {totaltid:.1f} timmar  
        **Totala intäkter:** ${intäkter:,.2f}  
        **Totalt antal prenumeranter:** {pren:,}
        """)

if __name__ == "__main__":
    main()
