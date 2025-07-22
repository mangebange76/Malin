import streamlit as st
import gspread
import pandas as pd
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
gc = gspread.service_account_from_dict(st.secrets["GOOGLE_CREDENTIALS"])
sh = gc.open_by_url(SPREADSHEET_URL)

def skapa_inställningsblad_om_saknas():
    try:
        inst_sheet = sh.worksheet("Inställningar")
    except:
        inst_sheet = sh.add_worksheet(title="Inställningar", rows="20", cols="2")
        inst_sheet.append_row(["Inställning", "Värde"])

    befintliga = {rad["Inställning"]: rad["Värde"] for rad in inst_sheet.get_all_records() if "Inställning" in rad}

    standardinställningar = {
        "Totalt kompisar": 0,
        "Totalt pappans vänner": 0,
        "Totalt Nils vänner": 0,
        "Totalt Nils familj": 0,
        "Senast kända kurs": 100.0,
        "Senaste prenumeranter": 0,
        "Startdatum": "2014-03-26",
        "Kvinnans namn": "Malin",
        "Kvinnans födelsedatum": "1984-03-26"
    }

    for nyckel, värde in standardinställningar.items():
        if nyckel not in befintliga:
            inst_sheet.append_row([nyckel, värde])

    return inst_sheet

def skapa_scener_blad_om_saknas():
    try:
        sheet = sh.worksheet("Scener")
    except:
        sheet = sh.add_worksheet(title="Scener", rows="1000", cols="40")
        sheet.append_row([])

    obligatoriska_kolumner = [
        "Datum", "Totala män", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
        "Enkel vaginal", "Enkel anal", "DT per man (sek)", "Tid per man (min)",
        "Tid per man (sek)", "Total_tid", "Tid per man (minut)", "Prenumeranter",
        "Aktiekurs", "Intäkt", "Kvinnan", "Mäns lön", "Kompisers lön",
        "Kompisar (scen)", "Pappans vänner", "Nils vänner", "Nils familj",
        "Älskar med", "Sover med", "DT total tid (sek)"
    ]

    befintliga = sheet.row_values(1)
    if not befintliga:
        sheet.insert_row(obligatoriska_kolumner, 1)
    else:
        saknas = [col for col in obligatoriska_kolumner if col not in befintliga]
        if saknas:
            ny_rubrikrad = befintliga + saknas
            sheet.delete_rows(1)
            sheet.insert_row(ny_rubrikrad, index=1)
    return sheet

inst_sheet = skapa_inställningsblad_om_saknas()
scen_sheet = skapa_scener_blad_om_saknas()

inst = {rad["Inställning"]: str(rad["Värde"]) for rad in inst_sheet.get_all_records() if "Inställning" in rad}

# Konvertera vissa till rätt typ
try:
    inst["Totalt kompisar"] = int(inst["Totalt kompisar"])
    inst["Totalt pappans vänner"] = int(inst["Totalt pappans vänner"])
    inst["Totalt Nils vänner"] = int(inst["Totalt Nils vänner"])
    inst["Totalt Nils familj"] = int(inst["Totalt Nils familj"])
    inst["Senast kända kurs"] = float(inst["Senast kända kurs"])
    inst["Senaste prenumeranter"] = int(inst["Senaste prenumeranter"])
    inst["Startdatum"] = datetime.strptime(inst["Startdatum"], "%Y-%m-%d").date()
    inst["Kvinnans födelsedatum"] = datetime.strptime(inst["Kvinnans födelsedatum"], "%Y-%m-%d").date()
except Exception as e:
    st.error(f"Fel i inställningsformat: {e}")

# Redigera inställningar i sidopanel
with st.sidebar:
    st.header("🔧 Grundinställningar")

    ny_kompisar = st.number_input("Totalt antal kompisar", min_value=0, value=inst["Totalt kompisar"])
    ny_pv = st.number_input("Totalt antal pappans vänner", min_value=0, value=inst["Totalt pappans vänner"])
    ny_nv = st.number_input("Totalt antal Nils vänner", min_value=0, value=inst["Totalt Nils vänner"])
    ny_nf = st.number_input("Totalt antal Nils familj", min_value=0, value=inst["Totalt Nils familj"])

    ny_kurs = st.number_input("Senast kända aktiekurs", min_value=0.0, value=inst["Senast kända kurs"], step=0.1)
    ny_pren = st.number_input("Senaste antal prenumeranter", min_value=0, value=inst["Senaste prenumeranter"])

    ny_startdatum = st.date_input("Startdatum (första scen)", value=inst["Startdatum"])
    ny_kvinnonamn = st.text_input("Kvinnans namn", value=inst["Kvinnans namn"])
    ny_födelsedatum = st.date_input("Kvinnans födelsedatum", value=inst["Kvinnans födelsedatum"])

    if st.button("💾 Spara inställningar"):
        inst_sheet.clear()
        inst_sheet.append_row(["Inställning", "Värde"])
        inst_sheet.append_rows([
            ["Totalt kompisar", ny_kompisar],
            ["Totalt pappans vänner", ny_pv],
            ["Totalt Nils vänner", ny_nv],
            ["Totalt Nils familj", ny_nf],
            ["Senast kända kurs", ny_kurs],
            ["Senaste prenumeranter", ny_pren],
            ["Startdatum", ny_startdatum.strftime("%Y-%m-%d")],
            ["Kvinnans namn", ny_kvinnonamn],
            ["Kvinnans födelsedatum", ny_födelsedatum.strftime("%Y-%m-%d")]
        ])
        st.success("Inställningar sparade!")
        st.experimental_rerun()

st.header("🎬 Lägg till ny scen")

df = pd.DataFrame(scen_sheet.get_all_records())
if df.empty or "Datum" not in df.columns or df["Datum"].isnull().all():
    senaste_datum = inst["Startdatum"]
else:
    senaste_datum = max(pd.to_datetime(df["Datum"], errors="coerce").dropna()).date()

scen_datum = senaste_datum + timedelta(days=1)
st.write(f"📅 Nästa scenens datum föreslås bli: **{scen_datum.strftime('%Y-%m-%d')}**")

with st.form("lägg_till_scen"):
    st.subheader("🧑‍🤝‍🧑 Antal män & penetrationstyper")
    col1, col2, col3 = st.columns(3)
    with col1:
        dp = st.number_input("DP", 0)
        dpp = st.number_input("DPP", 0)
        dap = st.number_input("DAP", 0)
    with col2:
        tpa = st.number_input("TPA", 0)
        tpp = st.number_input("TPP", 0)
        tap = st.number_input("TAP", 0)
    with col3:
        enkel_vaginal = st.number_input("Enkel vaginal", 0)
        enkel_anal = st.number_input("Enkel anal", 0)

    st.subheader("👥 Deltagande per grupp (scennivå)")
    col4, col5 = st.columns(2)
    with col4:
        antal_kompisar = st.number_input("Kompisar", min_value=0, max_value=inst["Totalt kompisar"])
        antal_pv = st.number_input("Pappans vänner", min_value=0, max_value=inst["Totalt pappans vänner"])
    with col5:
        antal_nv = st.number_input("Nils vänner", min_value=0, max_value=inst["Totalt Nils vänner"])
        antal_nf = st.number_input("Nils familj", min_value=0, max_value=inst["Totalt Nils familj"])

    st.subheader("⏱️ Tidsinställningar")
    tid_min = st.number_input("Tid per man (minuter)", min_value=0, value=8)
    tid_sek = st.number_input("Tid per man (sekunder)", min_value=0, value=0)
    dt_per_man = st.number_input("Deep throat per man (sekunder)", min_value=0)

    st.subheader("❤️ Närhet & övernattning")
    alskar_med = st.number_input("Antal älskar med", min_value=0, value=0)
    sover_med = st.number_input("Antal sover med", min_value=0, value=0)

    submit = st.form_submit_button("➕ Lägg till scen")

if submit:
    total_tid_per_man = tid_min * 60 + tid_sek
    tot_män = dp*2 + dpp*2 + dap*2 + tpa*3 + tpp*3 + tap*3 + enkel_vaginal + enkel_anal + antal_kompisar + antal_pv + antal_nv + antal_nf

    dt_total = dt_per_man * tot_män + (tot_män * 2) + (tot_män // 10 * 30)
    alskar_tid = alskar_med * 15 * 60
    sover_tid = sover_med * 15 * 60
    total_tid = (tot_män * total_tid_per_man) + (15 * (tot_män - 1)) + dt_total + alskar_tid + sover_tid

    ny_rad = {
        "Datum": scen_datum.strftime("%Y-%m-%d"),
        "Totala män": tot_män,
        "DP": dp, "DPP": dpp, "DAP": dap,
        "TPA": tpa, "TPP": tpp, "TAP": tap,
        "Enkel vaginal": enkel_vaginal, "Enkel anal": enkel_anal,
        "DT per man (sek)": dt_per_man,
        "Tid per man (min)": tid_min,
        "Tid per man (sek)": tid_sek,
        "Total_tid": total_tid,
        "Kompisar (scen)": antal_kompisar,
        "Pappans vänner": antal_pv,
        "Nils vänner": antal_nv,
        "Nils familj": antal_nf,
        "Älskar med": alskar_med,
        "Sover med": sover_med,
        "DT total tid (sek)": dt_total
    }

    scen_sheet.append_row([ny_rad.get(k, "") for k in scen_sheet.row_values(1)])
    st.success("Scen tillagd!")
    st.experimental_rerun()

st.header("🛏️ Vilodagar")

df = pd.DataFrame(scen_sheet.get_all_records())
if df.empty or "Datum" not in df.columns or df["Datum"].isnull().all():
    senaste_datum = inst["Startdatum"]
else:
    senaste_datum = max(pd.to_datetime(df["Datum"], errors="coerce").dropna()).date()

# 📌 1. Vilodagar på inspelningsplats
st.subheader("🎬 Vilodagar på inspelningsplats (max 21 dagar)")
vilodagar_ip = st.number_input("Antal vilodagar att lägga till (inspelningsplats)", min_value=0, max_value=21, step=1)
if st.button("➕ Lägg till vilodagar (inspelningsplats)"):
    for i in range(vilodagar_ip):
        dagens_datum = senaste_datum + timedelta(days=1)
        senaste_datum = dagens_datum

        tillfällen = {
            "Datum": dagens_datum.strftime("%Y-%m-%d"),
            "Totala män": 0,
            "DP": 0, "DPP": 0, "DAP": 0,
            "TPA": 0, "TPP": 0, "TAP": 0,
            "Enkel vaginal": 0, "Enkel anal": 0,
            "DT per man (sek)": 0,
            "Tid per man (min)": 0,
            "Tid per man (sek)": 0,
            "Total_tid": 0,
            "Kompisar (scen)": random.randint(0, int(inst["Totalt kompisar"] * 0.6)),
            "Pappans vänner": random.randint(0, int(inst["Totalt pappans vänner"] * 0.6)),
            "Nils vänner": random.randint(0, int(inst["Totalt Nils vänner"] * 0.6)),
            "Nils familj": random.randint(0, int(inst["Totalt Nils familj"] * 0.6)),
            "Älskar med": 12,
            "Sover med": 1,
            "DT total tid (sek)": 0
        }

        scen_sheet.append_row([tillfällen.get(k, "") for k in scen_sheet.row_values(1)])

    st.success(f"{vilodagar_ip} vilodagar på inspelningsplats tillagda!")

# 📌 2. Vilodagar i hemmet (alltid 7 dagar)
if st.button("🏠 Lägg till vilodagar hemma (7 dagar)"):
    for i in range(7):
        dagens_datum = senaste_datum + timedelta(days=1)
        senaste_datum = dagens_datum

        nils_sex = random.choices([0, 1, 2], weights=[0.4, 0.4, 0.2])[0] if i == 0 else 0

        tillfällen = {
            "Datum": dagens_datum.strftime("%Y-%m-%d"),
            "Totala män": 0,
            "DP": 0, "DPP": 0, "DAP": 0,
            "TPA": 0, "TPP": 0, "TAP": 0,
            "Enkel vaginal": 0, "Enkel anal": 0,
            "DT per man (sek)": 0,
            "Tid per man (min)": 0,
            "Tid per man (sek)": 0,
            "Total_tid": 0,
            "Kompisar (scen)": random.randint(0, int(inst["Totalt kompisar"] * 0.1)),
            "Pappans vänner": 0,
            "Nils vänner": 0,
            "Nils familj": 0,
            "Älskar med": 8,
            "Sover med": 0,
            "DT total tid (sek)": 0
        }

        scen_sheet.append_row([tillfällen.get(k, "") for k in scen_sheet.row_values(1)])

    st.success("7 vilodagar hemma tillagda!")

st.header("📊 Statistik och summering")

df = pd.DataFrame(scen_sheet.get_all_records())
if df.empty:
    st.info("Ingen data ännu.")
else:
    df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")
    df = df.sort_values("Datum")

    sista_datum = df["Datum"].max().date()
    födelsedatum = inst.get("Födelsedatum")
    namn = inst.get("Namn", "Okänd")

    if isinstance(födelsedatum, str):
        födelsedatum = datetime.strptime(födelsedatum, "%Y-%m-%d").date()

    nuvarande_ålder = (sista_datum - födelsedatum).days // 365

    st.subheader(f"👩 Kvinnan: {namn}")
    st.write(f"🎂 Ålder vid senaste inspelning: **{nuvarande_ålder} år**")
    st.write(f"📆 Totalt antal scener: **{len(df)}**")
    st.write(f"👨 Totalt antal män: **{df['Totala män'].sum()}**")

    st.divider()
    st.subheader("👥 Antal tillfällen per grupp (gangbang)")

    grupper = ["Kompisar (scen)", "Pappans vänner", "Nils vänner", "Nils familj"]
    for grupp in grupper:
        st.write(f"📌 **{grupp}** deltagit i: {df[df[grupp] > 0].shape[0]} scener")

    st.divider()
    st.subheader("💞 Närhet och övernattning")
    st.write(f"❤️ Antal gånger 'älskat med': {df['Älskar med'].sum()}")
    st.write(f"🛏️ Antal gånger 'sovit med': {df['Sover med'].sum()} (endast Nils familj)")

st.header("💰 Intäkter & 📈 Aktiekurs")

df = pd.DataFrame(scen_sheet.get_all_records())
if df.empty:
    st.info("Ingen scendata ännu.")
else:
    df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")
    df = df.sort_values("Datum")

    # Prenumerantviktning
    vikt = {
        "Enkel vaginal": inst.get("Vikt enkel", 1),
        "Enkel anal": inst.get("Vikt enkel", 1),
        "DP": inst.get("Vikt DP", 2),
        "DPP": inst.get("Vikt DPP", 2),
        "DAP": inst.get("Vikt DAP", 2),
        "TPA": inst.get("Vikt TPA", 3),
        "TPP": inst.get("Vikt TPP", 3),
        "TAP": inst.get("Vikt TAP", 4),
    }

    df["Prenumeranter"] = (
        df["Enkel vaginal"] * vikt["Enkel vaginal"] +
        df["Enkel anal"] * vikt["Enkel anal"] +
        df["DP"] * vikt["DP"] +
        df["DPP"] * vikt["DPP"] +
        df["DAP"] * vikt["DAP"] +
        df["TPA"] * vikt["TPA"] +
        df["TPP"] * vikt["TPP"] +
        df["TAP"] * vikt["TAP"]
    ).astype(int)

    df["Intäkt ($)"] = df["Prenumeranter"] * 15
    df["Kvinnans lön ($)"] = 800
    df["Mäns lön ($)"] = (df["Totala män"] - df["Kompisar (scen)"]) * 200
    df["Till kompisar ($)"] = (
        df["Intäkt ($)"] - df["Kvinnans lön ($)"] - df["Mäns lön ($)"]
    ) / inst.get("Totalt kompisar", 1)

    # Rolling 30-dagars prenumeranter
    df["Aktiva prenumeranter"] = 0
    for i in range(len(df)):
        datum = df.iloc[i]["Datum"]
        mask = (df["Datum"] >= datum - timedelta(days=29)) & (df["Datum"] <= datum)
        df.at[df.index[i], "Aktiva prenumeranter"] = df.loc[mask, "Prenumeranter"].sum()

    # Aktiekurs
    aktier = 100_000
    kurs = [inst.get("Startkurs", 1.0)]
    for i in range(1, len(df)):
        p1 = df.iloc[i - 1]["Aktiva prenumeranter"]
        p2 = df.iloc[i]["Aktiva prenumeranter"]
        if p1 == 0:
            kurs.append(kurs[-1])
        else:
            kurs.append(round(kurs[-1] * (p2 / p1), 2))
    df["Aktiekurs"] = kurs
    df["Värde familj ($)"] = df["Aktiekurs"] * aktier

    st.subheader("📈 Nuvarande kurs och värde")
    st.write(f"💵 Senaste aktiekurs: **{kurs[-1]} USD**")
    st.write(f"📊 Aktiva prenumeranter: {df.iloc[-1]['Aktiva prenumeranter']}")
    st.write(f"🏦 Nils familjs värde (100 000 aktier): **{df.iloc[-1]['Värde familj ($)']:.0f} USD**")

    with st.expander("🔍 Visa detaljerad tabell"):
        st.dataframe(df[[
            "Datum", "Prenumeranter", "Aktiva prenumeranter", "Intäkt ($)",
            "Kvinnans lön ($)", "Mäns lön ($)", "Till kompisar ($)",
            "Aktiekurs", "Värde familj ($)"
        ]].round(2), use_container_width=True)

with st.sidebar:
    st.subheader("⚙️ Justera vikter (prenumeranter)")

    vikt_enkel = st.number_input("Vikt för enkel penetration", min_value=0.0, step=0.1, value=float(inst.get("Vikt enkel", 1)))
    vikt_dp = st.number_input("Vikt för DP", min_value=0.0, step=0.1, value=float(inst.get("Vikt DP", 2)))
    vikt_dpp = st.number_input("Vikt för DPP", min_value=0.0, step=0.1, value=float(inst.get("Vikt DPP", 2)))
    vikt_dap = st.number_input("Vikt för DAP", min_value=0.0, step=0.1, value=float(inst.get("Vikt DAP", 2)))
    vikt_tpa = st.number_input("Vikt för TPA", min_value=0.0, step=0.1, value=float(inst.get("Vikt TPA", 3)))
    vikt_tpp = st.number_input("Vikt för TPP", min_value=0.0, step=0.1, value=float(inst.get("Vikt TPP", 3)))
    vikt_tap = st.number_input("Vikt för TAP", min_value=0.0, step=0.1, value=float(inst.get("Vikt TAP", 4)))

    if st.button("💾 Spara vikter"):
        viktdata = {
            "Vikt enkel": vikt_enkel,
            "Vikt DP": vikt_dp,
            "Vikt DPP": vikt_dpp,
            "Vikt DAP": vikt_dap,
            "Vikt TPA": vikt_tpa,
            "Vikt TPP": vikt_tpp,
            "Vikt TAP": vikt_tap
        }

        for nyckel, värde in viktdata.items():
            index = next((i for i, rad in enumerate(inst_sheet.get_all_records()) if rad["Inställning"] == nyckel), None)
            if index is not None:
                inst_sheet.update_cell(index + 2, 2, str(värde).replace(",", "."))
                inst_sheet.update_cell(index + 2, 3, datetime.today().strftime("%Y-%m-%d"))
            else:
                inst_sheet.append_row([nyckel, str(värde).replace(",", "."), datetime.today().strftime("%Y-%m-%d")])

        st.success("Vikter uppdaterade! Ladda om sidan för att se nya resultat.")
