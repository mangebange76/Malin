import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

# --- Google Sheets-uppkoppling ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"],
    scopes=scope
)

gc = gspread.authorize(creds)
sh = gc.open_by_url(SHEET_URL)

# --- Standardkolumner ---
COLUMNS = [
    "Datum", "Typ", "Scenens längd (h)", "Övriga män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man (sek)", "Prenumeranter", "Intäkt ($)",
    "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille",
    "Älskar med", "Sover med", "Nils sex"
]

# --- Inställningshantering ---

def läs_inställningar(sheet):
    try:
        ws = sheet.worksheet("Inställningar")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Inställningar", rows="10", cols="2")
        ws.update("A1:B1", [["Namn", "Värde"]])
        ws.update("A2:B10", [
            ["Startdatum", "2014-03-26"],
            ["Kvinnans namn", "Malin"],
            ["Födelsedatum", "1984-03-26"],
            ["Kompisar", "100"],
            ["Pappans vänner", "50"],
            ["Nils vänner", "30"],
            ["Nils familj", "10"]
        ])
    df = pd.DataFrame(ws.get_all_records())
    return {row["Namn"]: tolka_värde(row["Värde"]) for _, row in df.iterrows()}

def tolka_värde(v):
    try:
        return int(v)
    except:
        try:
            return float(str(v).replace(",", "."))
        except:
            return str(v)

def spara_inställningar(sheet, data):
    ws = sheet.worksheet("Inställningar")
    rader = [[k, str(v)] for k, v in data.items()]
    ws.update("A2:B{}".format(1 + len(rader)), rader)

# --- Sidopanel ---
inst = läs_inställningar(sh)

with st.sidebar:
    st.header("Inställningar")
    inst["Startdatum"] = st.text_input("Startdatum (ÅÅÅÅ-MM-DD)", value=str(inst.get("Startdatum", "")))
    inst["Kvinnans namn"] = st.text_input("Kvinnans namn", value=str(inst.get("Kvinnans namn", "")))
    inst["Födelsedatum"] = st.text_input("Födelsedatum (ÅÅÅÅ-MM-DD)", value=str(inst.get("Födelsedatum", "")))
    inst["Kompisar"] = st.number_input("Kompisar", min_value=0, value=int(inst.get("Kompisar", 0)))
    inst["Pappans vänner"] = st.number_input("Pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 0)))
    inst["Nils vänner"] = st.number_input("Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 0)))
    inst["Nils familj"] = st.number_input("Nils familj", min_value=0, value=int(inst.get("Nils familj", 0)))

    if st.button("Spara inställningar"):
        spara_inställningar(sh, inst)
        st.success("Inställningar sparade")

    if st.button("Rensa databas"):
        try:
            ws = sh.worksheet("Data")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Data", rows="1000", cols=str(len(COLUMNS)))
        ws.clear()
        ws.update("A1", [COLUMNS])
        st.success("Databasen rensad")

# --- Formulär för ny rad ---

st.header("Lägg till ny rad")

form = st.form("lägg_till_form")
with form:
    f = {}
    f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
    f["Antal vilodagar"] = st.number_input("Antal vilodagar", min_value=0, value=1, key="vilodagar")

    f["Scenens längd (h)"] = st.number_input("Scenens längd (h)", min_value=0.0, value=14.0, key="scenlängd")
    f["Övriga män"] = st.number_input("Övriga män", min_value=0, value=0)

    f["Enkel vaginal"] = st.number_input("Enkel vaginal", min_value=0, value=0)
    f["Enkel anal"] = st.number_input("Enkel anal", min_value=0, value=0)

    f["DP"] = st.number_input("DP", min_value=0, value=0)
    f["DPP"] = st.number_input("DPP", min_value=0, value=0)
    f["DAP"] = st.number_input("DAP", min_value=0, value=0)

    f["TPP"] = st.number_input("TPP", min_value=0, value=0)
    f["TPA"] = st.number_input("TPA", min_value=0, value=0)
    f["TAP"] = st.number_input("TAP", min_value=0, value=0)

    f["Kompisar"] = st.number_input("Kompisar", min_value=0, max_value=inst.get("Kompisar", 0), value=0)
    f["Pappans vänner"] = st.number_input("Pappans vänner", min_value=0, max_value=inst.get("Pappans vänner", 0), value=0)
    f["Nils vänner"] = st.number_input("Nils vänner", min_value=0, max_value=inst.get("Nils vänner", 0), value=0)
    f["Nils familj"] = st.number_input("Nils familj", min_value=0, max_value=inst.get("Nils familj", 0), value=0)

    f["DT tid per man (sek)"] = st.number_input("DT tid per man (sek)", min_value=0, value=0)

    f["Älskar med"] = st.number_input("Antal älskar med", min_value=0, value=0)
    f["Sover med"] = st.number_input("Antal sover med", min_value=0, value=0)

    per_kille_min, total_tid_h = beräkna_tid_per_kille(f)
    st.markdown(f"**Total tid:** {round(total_tid_h, 2)} h")
    st.markdown(f"**Tid per kille (inkl. DT):** {round(per_kille_min, 2)} min")

    if total_tid_h > 18:
        st.error("Varning: Total tid överstiger 18 timmar!")

    submit = st.form_submit_button("Lägg till")

if submit:
    df = process_lägg_till_rader(df, inst, f)
    spara_data(sh, df)
    st.success("Rad(er) tillagda!")

# --- Visa data och statistik ---

st.header("Alla rader")
st.dataframe(df)

st.header("Statistik")

df_scen = df[df["Typ"] == "Scen"]
if not df_scen.empty:
    total_pren = df_scen["Prenumeranter"].sum()
    total_intäkt = df_scen["Intäkt ($)"].sum()
    total_dt = df_scen["DT total tid (sek)"].sum()
    total_tid = df_scen["Total tid (h)"].sum()
    snitt_tid_kille = df_scen["Minuter per kille"].mean()

    st.markdown(f"- **Totala prenumeranter:** {int(total_pren)}")
    st.markdown(f"- **Total intäkt ($):** {round(total_intäkt, 2)}")
    st.markdown(f"- **Total DT-tid (sek):** {int(total_dt)}")
    st.markdown(f"- **Total tid (h):** {round(total_tid, 2)}")
    st.markdown(f"- **Snitt tid per kille (min):** {round(snitt_tid_kille, 2)}")

# Extra statistik
if not df.empty:
    grupper_summa = sum([inst.get(grupp, 0) for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]])
    nils_fam = inst.get("Nils familj", 1)

    älskat = df["Älskar med"].sum()
    sovit = df["Sover med"].sum()

    st.markdown(f"- **Totalt älskat:** {älskat} (snitt: {round(älskat / grupper_summa, 2)} per person)")
    st.markdown(f"- **Totalt sovit med:** {sovit} (snitt: {round(sovit / nils_fam, 2)} per person)")

    # Nuvarande ålder
    födelsedatum = inst.get("Födelsedatum", "1984-03-26")
    senaste_datum = max(pd.to_datetime(df["Datum"], errors="coerce").dropna())
    född = datetime.strptime(födelsedatum, "%Y-%m-%d")
    ålder = (senaste_datum - född).days // 365
    namn = inst.get("Kvinnans namn", "Malin")

    st.markdown(f"- **{namn}s nuvarande ålder:** {ålder} år")

# --- Main-funktion ---

def main():
    gc = gspread.authorize(Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"]))
    sh = gc.open_by_url(SHEET_URL)

    df = hämta_data(sh)
    inst = läs_inställningar(sh)

    df = init_sheet(sh)
    visa_sidopanel(sh, inst)

    # Återanvänder funktioner
    run_app_logic(sh, df, inst)

# --- Kör appen ---
if __name__ == "__main__":
    main()
