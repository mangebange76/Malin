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
    "DT tid per man (sek)", "DT total tid (sek)",
    "Älskar med", "Sover med", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Nils sex", "Tid per man (min)", "Tid per man (inkl. DT)"
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

def beräkna_killetid_per_penetration(df):
    enkel_tid = 40  # sekunder per tillfälle (1 kille)
    total_tillfällen = 0
    total_vikt = 0

    # Viktning för varje penetrationstyp
    viktning = {
        "Enkel vaginal": (1, enkel_tid),
        "Enkel anal": (1, enkel_tid),
        "DP": (2, None),
        "DPP": (2, None),
        "DAP": (2, None),
        "TPA": (3, None),
        "TPP": (3, None),
        "TAP": (3, None),
    }

    # Räkna antal tillfällen och totalvikt
    for typ, (män, fast_tid) in viktning.items():
        antal = df.get(typ, 0)
        if fast_tid:
            total_tillfällen += antal
        else:
            total_tillfällen += antal
            total_vikt += antal * män

    if total_tillfällen == 0:
        return 0, 0, 0, 0

    # 14 timmar = 50400 sekunder
    vilotid = 15 * (
        int(df.get("DP", 0)) + int(df.get("DPP", 0)) + int(df.get("DAP", 0)) +
        int(df.get("TPA", 0)) + int(df.get("TPP", 0)) + int(df.get("TAP", 0)) +
        int(df.get("Enkel vaginal", 0)) + int(df.get("Enkel anal", 0))
    )
    kvar_tid = 50400 - vilotid  # sekunder kvar för penetrationsmoment

    # Enkel tid är fast (40 sek per tillfälle)
    enkel_total = enkel_tid * (
        int(df.get("Enkel vaginal", 0)) + int(df.get("Enkel anal", 0))
    )

    rest_tid = max(0, kvar_tid - enkel_total)
    dubbel_tid = 0
    trippel_tid = 0

    if total_vikt > 0:
        dubbel_tid = rest_tid * (
            (int(df.get("DP", 0)) + int(df.get("DPP", 0)) + int(df.get("DAP", 0)) * 2) * 2
        ) / total_vikt
        trippel_tid = rest_tid * (
            (int(df.get("TPA", 0)) + int(df.get("TPP", 0)) + int(df.get("TAP", 0)) * 3) * 3
        ) / total_vikt

    enkel_kille = enkel_tid
    dubbel_kille = dubbel_tid
    trippel_kille = trippel_tid

    return enkel_kille, dubbel_kille, trippel_kille, vilotid

def uppdatera_tid_och_intäkt(df, inst):
    tid_per_man = float(inst.get("Tid per man (minuter)", 0))
    dt_tid_per_man = float(inst.get("DT tid per man (sek)", 0))

    for i, rad in df.iterrows():
        typ = rad.get("Typ", "")
        if typ not in ["Scen", "Vila inspelningsplats", "Vilovecka hemma"]:
            continue

        enkel_kille, dubbel_kille, trippel_kille, vila = beräkna_killetid_per_penetration(rad)
        tot_killar = (
            int(rad.get("Enkel vaginal", 0)) +
            int(rad.get("Enkel anal", 0)) +
            2 * (int(rad.get("DP", 0)) + int(rad.get("DPP", 0)) + int(rad.get("DAP", 0))) +
            3 * (int(rad.get("TPA", 0)) + int(rad.get("TPP", 0)) + int(rad.get("TAP", 0)))
        )

        total_tid_kille = (
            enkel_kille * (int(rad.get("Enkel vaginal", 0)) + int(rad.get("Enkel anal", 0))) +
            dubbel_kille * 2 * (int(rad.get("DP", 0)) + int(rad.get("DPP", 0)) + int(rad.get("DAP", 0))) +
            trippel_kille * 3 * (int(rad.get("TPA", 0)) + int(rad.get("TPP", 0)) + int(rad.get("TAP", 0)))
        )

        dt_tid = beräkna_dt_tid(dt_tid_per_man, tot_killar)
        total_tid_kille += dt_tid

        df.at[i, "Total tid (sek)"] = int(total_tid_kille)
        df.at[i, "Total tid (h)"] = round(total_tid_kille / 3600, 2)
        df.at[i, "DT total tid (sek)"] = int(dt_tid)

        # Ekonomi
        if typ == "Scen":
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

    st.subheader("📊 Statistik")

    tot_män = df[["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj", "Övriga män"]].sum().sum()
    tot_rader = len(df)
    kompisar = int(inst.get("Kompisar", 1))
    nils_fam = int(inst.get("Nils familj", 1))

    sista_datum = df["Datum"].max() if not df.empty else inst.get("Startdatum", "2014-03-26")
    ålder = beräkna_ålder(inst.get("Födelsedatum", "1984-03-26"), sista_datum)

    st.write(f"👩 {inst.get('Kvinnans namn')} – Ålder vid sista scen: {ålder} år")
    st.write(f"Totalt antal rader: {tot_rader}")
    st.write(f"Totalt antal män (inkl. alla grupper): {tot_män}")
    st.write(f"Snitt per scen: {round(tot_män / tot_rader, 2) if tot_rader else 0}")
    st.write(f"Älskat: {int(df['Älskar med'].sum())}, Snitt per man: {round(df['Älskar med'].sum() / kompisar, 2) if kompisar else 0}")
    st.write(f"Sovit med: {int(df['Sover med'].sum())}, Snitt per Nils familjemedlem: {round(df['Sover med'].sum() / nils_fam, 2) if nils_fam else 0}")
    st.write(f"💋 Total DT-tid (sek): {int(df['DT total tid (sek)'].sum())}")

    # Prenumeranter senaste 30 dagar
    if not df.empty:
        df["Datum_dt"] = pd.to_datetime(df["Datum"], errors="coerce")
        senast = df["Datum_dt"].max()
        senaste_30_dagar = df[df["Datum_dt"] >= senast - pd.Timedelta(days=30)]
        pren30 = senaste_30_dagar["Prenumeranter"].sum()
        st.write(f"📈 Prenumeranter senaste 30 dagar: {int(pren30)}")
        df = df.drop(columns=["Datum_dt"])

    st.dataframe(df.sort_values("Datum"))

if __name__ == "__main__":
    main()
