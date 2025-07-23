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

def reset_form_fields():
    keys = [
        "typ", "dp", "dpp", "dap", "tpa", "tpp", "tap",
        "enkel_vag", "enkel_anal", "komp", "pappans", "nils_v", "nils_f",
        "ov", "dt_tid_per_man", "scen_tid", "älskar", "sover", "dagar"
    ]
    for key in keys:
        st.session_state[key] = 0 if "typ" not in key else "Scen"

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("lägg_till"):
        st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"], key="typ")
        st.number_input("Antal vilodagar (gäller bara vid vila)", min_value=1, step=1, key="dagar")
        st.number_input("Scenens längd (h)", min_value=0.0, step=0.25, key="scen_tid")
        st.number_input("Övriga män", min_value=0, step=1, key="ov")
        st.number_input("Enkel vaginal", min_value=0, step=1, key="enkel_vag")
        st.number_input("Enkel anal", min_value=0, step=1, key="enkel_anal")
        st.number_input("DP", min_value=0, step=1, key="dp")
        st.number_input("DPP", min_value=0, step=1, key="dpp")
        st.number_input("DAP", min_value=0, step=1, key="dap")
        st.number_input("TPP", min_value=0, step=1, key="tpp")
        st.number_input("TAP", min_value=0, step=1, key="tap")
        st.number_input("TPA", min_value=0, step=1, key="tpa")
        st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst.get("Kompisar", 999)), key="komp")
        st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst.get("Pappans vänner", 999)), key="pappans")
        st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst.get("Nils vänner", 999)), key="nils_v")
        st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst.get("Nils familj", 999)), key="nils_f")
        st.number_input("DT tid per man (sek)", min_value=0, step=1, key="dt_tid_per_man")
        st.number_input("Antal älskar med", min_value=0, step=1, key="älskar")
        st.number_input("Antal sover med", min_value=0, step=1, key="sover")
        submit = st.form_submit_button("Lägg till")

    if submit:
        from .del3 import process_lägg_till_rader  # (kommer i del 3)
        df = process_lägg_till_rader(df, inst, st.session_state)
        spara_data(df)
        reset_form_fields()
        st.rerun()

from datetime import timedelta
from random import randint, sample
import pandas as pd

def process_lägg_till_rader(df, inst, form_data):
    typ = form_data["typ"]
    dagar = form_data["dagar"]
    scen_tid = form_data["scen_tid"]
    ov = form_data["ov"]
    enkel_vag = form_data["enkel_vag"]
    enkel_anal = form_data["enkel_anal"]
    dp = form_data["dp"]
    dpp = form_data["dpp"]
    dap = form_data["dap"]
    tpp = form_data["tpp"]
    tap = form_data["tap"]
    tpa = form_data["tpa"]
    komp = form_data["komp"]
    pappans = form_data["pappans"]
    nils_v = form_data["nils_v"]
    nils_f = form_data["nils_f"]
    dt_tid_per_man = form_data["dt_tid_per_man"]
    älskar = form_data["älskar"]
    sover = form_data["sover"]

    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    nils_sextillfällen = [0] * 7

    if typ == "Vilovecka hemma":
        tillfällen = sorted(sample(range(7), k=min(2, 7)))
        for i in tillfällen:
            nils_sextillfällen[i] = 1

    antal = 7 if typ == "Vilovecka hemma" else int(dagar)
    nya_rader = []

    # För Vilovecka: fördela 1.5x av inst totalt på 7 dagar
    def fördela_värde(gruppnamn):
        totalt = int(inst.get(gruppnamn, 0))
        mål = int(totalt * 1.5)
        per_dag = [mål // 7] * 7
        for i in range(mål % 7):
            per_dag[i] += 1
        return per_dag

    komp_distr = fördela_värde("Kompisar") if typ == "Vilovecka hemma" else []
    pappans_distr = fördela_värde("Pappans vänner") if typ == "Vilovecka hemma" else []
    nils_v_distr = fördela_värde("Nils vänner") if typ == "Vilovecka hemma" else []
    nils_f_distr = fördela_värde("Nils familj") if typ == "Vilovecka hemma" else []

    for i in range(antal):
        datum = senaste_datum + timedelta(days=1)
        senaste_datum = datum

        if typ == "Vilovecka hemma":
            rad_komp = komp_distr[i]
            rad_pappans = pappans_distr[i]
            rad_nils_v = nils_v_distr[i]
            rad_nils_f = nils_f_distr[i]
            sover_med = 0
            älskar_med = 8
            nils_sex = nils_sextillfällen[i]
        elif typ == "Vila inspelningsplats":
            rad_komp = randint(inst.get("Kompisar", 0) * 25 // 100, inst.get("Kompisar", 0) * 50 // 100)
            rad_pappans = randint(inst.get("Pappans vänner", 0) * 25 // 100, inst.get("Pappans vänner", 0) * 50 // 100)
            rad_nils_v = randint(inst.get("Nils vänner", 0) * 25 // 100

Här är **Del 3** igen – uppdaterad funktion `process_lägg_till_rader(...)` som:

- Skapar nya rader baserat på formulärdata
- Genererar rätt datum
- Slumpar antal från grupper vid vila
- Fördelar 1,5× gruppstorlek vid vilovecka
- Gör alla beräkningar: deep throat-tid, total tid, prenumeranter, intäkter, löner
- Returnerar uppdaterad DataFrame

---

### 📄 Del 3 – `process_lägg_till_rader(df, inst, form_data)`

```python
from datetime import timedelta
from random import randint, sample
import pandas as pd

def process_lägg_till_rader(df, inst, form_data):
    typ = form_data["typ"]
    dagar = form_data["dagar"]
    scen_tid = form_data["scen_tid"]
    ov = form_data["ov"]
    enkel_vag = form_data["enkel_vag"]
    enkel_anal = form_data["enkel_anal"]
    dp = form_data["dp"]
    dpp = form_data["dpp"]
    dap = form_data["dap"]
    tpp = form_data["tpp"]
    tap = form_data["tap"]
    tpa = form_data["tpa"]
    komp = form_data["komp"]
    pappans = form_data["pappans"]
    nils_v = form_data["nils_v"]
    nils_f = form_data["nils_f"]
    dt_tid_per_man = form_data["dt_tid_per_man"]
    älskar = form_data["älskar"]
    sover = form_data["sover"]

    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum"))
    nils_sextillfällen = [0] * 7

    if typ == "Vilovecka hemma":
        tillfällen = sorted(sample(range(7), k=min(2, 7)))
        for i in tillfällen:
            nils_sextillfällen[i] = 1

    antal = 7 if typ == "Vilovecka hemma" else int(dagar)
    nya_rader = []

    def fördela_värde(gruppnamn):
        totalt = int(inst.get(gruppnamn, 0))
        mål = int(totalt * 1.5)
        per_dag = [mål // 7] * 7
        for i in range(mål % 7):
            per_dag[i] += 1
        return per_dag

    komp_distr = fördela_värde("Kompisar") if typ == "Vilovecka hemma" else []
    pappans_distr = fördela_värde("Pappans vänner") if typ == "Vilovecka hemma" else []
    nils_v_distr = fördela_värde("Nils vänner") if typ == "Vilovecka hemma" else []
    nils_f_distr = fördela_värde("Nils familj") if typ == "Vilovecka hemma" else []

    for i in range(antal):
        datum = senaste_datum + timedelta(days=1)
        senaste_datum = datum

        if typ == "Vilovecka hemma":
            rad_komp = komp_distr[i]
            rad_pappans = pappans_distr[i]
            rad_nils_v = nils_v_distr[i]
            rad_nils_f = nils_f_distr[i]
            sover_med = 0
            älskar_med = 8
            nils_sex = nils_sextillfällen[i]
        elif typ == "Vila inspelningsplats":
            rad_komp = randint(int(inst.get("Kompisar", 0) * 0.25), int(inst.get("Kompisar

import streamlit as st

def main():
    st.set_page_config(page_title="Malin App", layout="wide")

    st.title("📊 Malins statistik- och scenplaneringsapp")

    # Ladda in data
    df = ladda_data()
    inst = läs_inställningar()

    # Sidopanel: inställningar
    st.sidebar.header("Inställningar")
    with st.sidebar.form("inställningar_form"):
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", "2020-01-01")))
        namn = st.text_input("Kvinnans namn", value=inst.get("Namn", "Malin"))
        födelse = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1984-01-01")))
        kompisar = st.number_input("Kompisar", value=int(inst.get("Kompisar", 0)), step=1)
        pappans = st.number_input("Pappans vänner", value=int(inst.get("Pappans vänner", 0)), step=1)
        nils_v = st.number_input("Nils vänner", value=int(inst.get("Nils vänner", 0)), step=1)
        nils_f = st.number_input("Nils familj", value=int(inst.get("Nils familj", 0)), step=1)
        sparaknapp = st.form_submit_button("Spara inställningar")

    if sparaknapp:
        inst.update({
            "Startdatum": str(startdatum),
            "Namn": namn,
            "Födelsedatum": str(födelse),
            "Kompisar": kompisar,
            "Pappans vänner": pappans,
            "Nils vänner": nils_v,
            "Nils familj": nils_f
        })
        spara_inställningar(inst)
        st.success("Inställningar uppdaterade.")

    # Visa formulär
    st.header("➕ Lägg till scen eller vilodag")
    df = scenformulär(df, inst)

    # Visa data
    st.header("📋 Samtliga rader")
    st.dataframe(df, use_container_width=True)

    # Spara tillbaka till Google Sheets
    spara_data(df)

def scenformulär(df, inst):
    with st.form("lägg_till_formulär", clear_on_submit=True):
        kol1, kol2, kol3 = st.columns(3)
        with kol1:
            typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
            dagar = st.number_input("Antal vilodagar", min_value=1, step=1)
            scen_tid = st.number_input("Scenens längd (h)", min_value=0.0, step=0.25)
            ov = st.number_input("Övriga män", min_value=0, step=1)
            enkel_vag = st.number_input("Enkel vaginal", min_value=0, step=1)
            enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
        with kol2:
            dp = st.number_input("DP", min_value=0, step=1)
            dpp = st.number_input("DPP", min_value=0, step=1)
            dap = st.number_input("DAP", min_value=0, step=1)
            tpp = st.number_input("TPP", min_value=0, step=1)
            tap = st.number_input("TAP", min_value=0, step=1)
            tpa = st.number_input("TPA", min_value=0, step=1)
        with kol3:
            komp = st.number_input("Kompisar", min_value=0, step=1, max_value=int(inst["Kompisar"]))
            pappans = st.number_input("Pappans vänner", min_value=0, step=1, max_value=int(inst["Pappans vänner"]))
            nils_v = st.number_input("Nils vänner", min_value=0, step=1, max_value=int(inst["Nils vänner"]))
            nils_f = st.number_input("Nils familj", min_value=0, step=1, max_value=int(inst["Nils familj"]))
            dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1)
            älskar = st.number_input("Antal älskar med", min_value=0, step=1)
            sover = st.number_input("Antal sover med", min_value=0, step=1)

        submit = st.form_submit_button("Lägg till")

    if submit:
        senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst["Startdatum"])
        nils_sexveckan = [0]*7
        antal_rader = 7 if typ == "Vilovecka hemma" else int(dagar)
        nya_rader = []

        if typ == "Vilovecka hemma":
            # Slumpa två tillfällen för sex
            tillfällen = sample(range(6), min(2, 6))
            for i in tillfällen:
                nils_sexveckan[i] = 1
            # Fördela 1.5x grupper på 7 dagar
            def fördela_grupp(värde):
                total = round(1.5 * värde)
                bas = total // 7
                extra = total % 7
                return [bas + 1 if i < extra else bas for i in range(7)]

            komp_vecka = fördela_grupp(inst["Kompisar"])
            pappans_vecka = fördela_grupp(inst["Pappans vänner"])
            nils_v_vecka = fördela_grupp(inst["Nils vänner"])
            nils_f_vecka = fördela_grupp(inst["Nils familj"])

        for i in range(antal_rader):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            if typ == "Vila inspelningsplats":
                älskar_med = 12
                sover_med = 1
                nils_sex = 0
                # Slumpa grupper 25–50%
                def slumpa(x): return int(round(x * (0.25 + random() * 0.25)))
                komp_i = slumpa(inst["Kompisar"])
                pappans_i = slumpa(inst["Pappans vänner"])
                nils_v_i = slumpa(inst["Nils vänner"])
                nils_f_i = slumpa(inst["Nils familj"])
            elif typ == "Vilovecka hemma":
                älskar_med = 8 if i < 6 else 0
                sover_med = 1 if i == 6 else 0
                nils_sex = nils_sexveckan[i]
                komp_i = komp_vecka[i]
                pappans_i = pappans_vecka[i]
                nils_v_i = nils_v_vecka[i]
                nils_f_i = nils_f_vecka[i]
            else:
                älskar_med = älskar
                sover_med = sover
                nils_sex = 0
                komp_i = komp
                pappans_i = pappans
                nils_v_i = nils_v
                nils_f_i = nils_f

            # Endast Scen ger beräkningar
            if typ == "Scen":
                pren = (enkel_vag + enkel_anal) * 1 + (dp + dpp + dap) * 5 + (tpa + tpp + tap) * 8
                intäkt = pren * 15
                kvinna_lön = 100
                man_lön = (komp_i + pappans_i + nils_v_i + nils_f_i + ov) * 200
                kvar = intäkt - kvinna_lön - man_lön
                komp_lön = max(0, kvar / inst["Kompisar"]) if inst["Kompisar"] else 0
                dt_total = dt_tid_per_man * (komp_i + pappans_i + nils_v_i + nils_f_i + ov)
                total_tid = scen_tid * 3600 + dt_total
                tid_per_man = total_tid / max(1, komp_i + pappans_i + nils_v_i + nils_f_i + ov)
            else:
                pren = intäkt = kvinna_lön = man_lön = komp_lön = dt_total = total_tid = tid_per_man = 0

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": dp, "DPP": dpp, "DAP": dap,
                "TPA": tpa, "TPP": tpp, "TAP": tap,
                "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
                "Kompisar": komp_i, "Pappans vänner": pappans_i, "Nils vänner": nils_v_i, "Nils familj": nils_f_i,
                "Övriga män": ov, "Älskar med": älskar_med, "Sover med": sover_med, "Nils sex": nils_sex,
                "DT tid per man (sek)": dt_tid_per_man, "DT total tid (sek)": round(dt_total),
                "Total tid (sek)": round(total_tid), "Total tid (h)": round(total_tid / 3600, 2),
                "Prenumeranter": int(pren), "Intäkt ($)": round(intäkt, 2),
                "Kvinnans lön ($)": kvinna_lön, "Mäns lön ($)": man_lön, "Kompisars lön ($)": round(komp_lön, 2),
                "Minuter per kille": round(tid_per_man / 60, 2), "Scenens längd (h)": scen_tid
            }
            nya_rader.append(rad)

        df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
        st.success(f"{antal_rader} rader tillagda.")
    return df
