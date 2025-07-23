# app.py – Del 1

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

# app.py – Del 2

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

# app.py – Del 3

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till_form"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        dagar = st.number_input("Antal vilodagar", min_value=1, step=1, key="dagar")
        scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.5, key="scen_tid")
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

        if typ == "Scen":
            total_män = (
                dp * 2 + dpp * 3 + dap * 3 +
                tpp * 3 + tap * 3 + tpa * 3 +
                enkel_vag + enkel_anal +
                komp + pappans + nils_v + nils_f + ov
            )
            penetration_tid = scen_tid * 3600  # i sekunder
            tid_per_man = (penetration_tid / total_män) / 60 if total_män else 0
            dt_total = total_män * dt_tid_per_man
            total_tid = penetration_tid + dt_total
            total_tid_h = round(total_tid / 3600, 2)

            st.markdown(f"**Total tid (inkl DT):** {total_tid_h:.2f} timmar")
            st.markdown(f"**Tid per kille (inkl DT):** {round(tid_per_man + dt_tid_per_man/60, 2)} minuter")
            if total_tid_h > 18:
                st.error("⚠️ Den totala tiden överskrider 18 timmar!")

    if submit:
        from berakningar import process_lägg_till_rader
        nya_rader = process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                                            dp, dpp, dap, tpp, tap, tpa, komp, pappans, nils_v, nils_f,
                                            dt_tid_per_man, älskar, sover)
        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        spara_data(df)

        # Återställ formulärfält
        for key in ["dagar", "scen_tid", "ov", "enkel_vag", "enkel_anal", "dp", "dpp", "dap",
                    "tpp", "tap", "tpa", "komp", "pappans", "nils_v", "nils_f",
                    "dt_tid_per_man", "älskar", "sover"]:
            st.session_state[key] = 0
        st.experimental_rerun()

def process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, ev, ea,
                             dp, dpp, dap, tpp, tap, tpa,
                             komp, pappans, nils_v, nils_f,
                             dt_tid_per_man, älskar, sover):
    rows = []
    startdatum = pd.to_datetime(inst.get("Startdatum"), errors="coerce")
    senaste_datum = pd.to_datetime(df["Datum"].max(), errors="coerce") if not df.empty else startdatum
    dagens_datum = senaste_datum + pd.Timedelta(days=1)

    if typ == "Scen":
        total_män = (
            dp * 2 + dpp * 3 + dap * 3 +
            tpp * 3 + tap * 3 + tpa * 3 +
            ev + ea + komp + pappans + nils_v + nils_f + ov
        )
        penetration_tid = scen_tid * 3600
        tid_per_man = (penetration_tid / total_män) if total_män else 0
        dt_total = total_män * dt_tid_per_man
        total_tid = penetration_tid + dt_total
        total_tid_h = total_tid / 3600

        pren = ev * 1 + (dp + ea) * 5 + (dpp + dap + tpp + tap + tpa) * 8
        intäkt = pren * 15
        kvinnor_lön = 100
        män_lön = 200 * (pappans + nils_v + nils_f)
        komp_lön = max(0, intäkt - kvinnor_lön - män_lön)
        komp_lön = komp_lön / inst.get("Kompisar", 1) if inst.get("Kompisar", 1) > 0 else 0
        minuter_per_kille = round((tid_per_man + dt_tid_per_man) / 60, 2)

        rad = {
            "Datum": dagens_datum.strftime("%Y-%m-%d"),
            "Typ": typ,
            "DP": dp, "DPP": dpp, "DAP": dap,
            "TPA": tpa, "TPP": tpp, "TAP": tap,
            "Enkel vaginal": ev, "Enkel anal": ea,
            "Kompisar": komp, "Pappans vänner": pappans,
            "Nils vänner": nils_v, "Nils familj": nils_f,
            "Övriga män": ov,
            "Älskar med": älskar,
            "Sover med": sover,
            "Nils sex": 0,
            "DT tid per man (sek)": dt_tid_per_man,
            "DT total tid (sek)": dt_total,
            "Total tid (sek)": total_tid,
            "Total tid (h)": round(total_tid_h, 2),
            "Prenumeranter": pren,
            "Intäkt ($)": int(round(intäkt)),
            "Kvinnans lön ($)": kvinnor_lön,
            "Mäns lön ($)": män_lön,
            "Kompisars lön ($)": int(round(komp_lön)),
            "Minuter per kille": minuter_per_kille,
            "Scenens längd (h)": scen_tid
        }
        rows.append(rad)

    elif typ == "Vila inspelningsplats":
        for _ in range(dagar):
            dagens_datum += pd.Timedelta(days=1)
            rad = {
                "Datum": dagens_datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0,
                "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": random.randint(int(inst.get("Kompisar", 0) * 0.25), int(inst.get("Kompisar", 0) * 0.5)),
                "Pappans vänner": random.randint(int(inst.get("Pappans vänner", 0) * 0.25), int(inst.get("Pappans vänner", 0) * 0.5)),
                "Nils vänner": random.randint(int(inst.get("Nils vänner", 0) * 0.25), int(inst.get("Nils vänner", 0) * 0.5)),
                "Nils familj": random.randint(int(inst.get("Nils familj", 0) * 0.25), int(inst.get("Nils familj", 0) * 0.5)),
                "Övriga män": 0, "Älskar med": 12, "Sover med": 1,
                "Nils sex": 0, "DT tid per man (sek)": 0,
                "DT total tid (sek)": 0, "Total tid (sek)": 0,
                "Total tid (h)": 0, "Prenumeranter": 0,
                "Intäkt ($)": 0, "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0, "Kompisars lön ($)": 0,
                "Minuter per kille": 0, "Scenens längd (h)": 0
            }
            rows.append(rad)

    elif typ == "Vilovecka hemma":
        tot = {
            "Kompisar": int(round(inst.get("Kompisar", 0) * 1.5)),
            "Pappans vänner": int(round(inst.get("Pappans vänner", 0) * 1.5)),
            "Nils vänner": int(round(inst.get("Nils vänner", 0) * 1.5)),
            "Nils familj": int(round(inst.get("Nils familj", 0) * 1.5)),
        }

        fördelade = {k: [0] * 7 for k in tot}
        for k in tot:
            for _ in range(tot[k]):
                i = random.randint(0, 6)
                fördelade[k][i] += 1

        nils_sex_dagar = random.sample(range(7), min(2, 7))
        for i in range(7):
            dagens_datum += pd.Timedelta(days=1)
            rad = {
                "Datum": dagens_datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0,
                "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": fördelade["Kompisar"][i],
                "Pappans vänner": fördelade["Pappans vänner"][i],
                "Nils vänner": fördelade["Nils vänner"][i],
                "Nils familj": fördelade["Nils familj"][i],
                "Övriga män": 0,
                "Älskar med": 8,
                "Sover med": 0,
                "Nils sex": 1 if i in nils_sex_dagar else 0,
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
            rows.append(rad)

    return rows

import streamlit as st

def main():
    st.title("🎬 Malin Appen – Scenplanering & Statistik")

    # Läs data
    df = load_data()
    inst = läs_inställningar()

    # Sidopanel för inställningar
    visa_inställningar(inst)

    # Rensningsknapp
    if st.sidebar.button("🗑️ Rensa databasen"):
        df = df.iloc[0:0]
        save_data(df)
        st.success("Databasen har rensats.")

    # Formulär
    scenformulär(df, inst)

    # Visa tabell
    st.subheader("📊 Alla rader i databasen")
    df_v = df.copy()
    if not df_v.empty:
        df_v["Datum"] = pd.to_datetime(df_v["Datum"], errors="coerce").dt.strftime("%Y-%m-%d")
        df_v = df_v.sort_values("Datum")
        st.dataframe(df_v.reset_index(drop=True), use_container_width=True)
    else:
        st.info("Inga rader i databasen än.")

if __name__ == "__main__":
    main()
