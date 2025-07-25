import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2 import service_account
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Autentisering och koppling till kalkylark
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)
try:
    data_worksheet = sh.worksheet("Data")
except:
    data_worksheet = sh.add_worksheet(title="Data", rows="1000", cols="50")

try:
    inställningar_worksheet = sh.worksheet("Inställningar")
except:
    inställningar_worksheet = sh.add_worksheet(title="Inställningar", rows="100", cols="10")

# Läs inställningar från Google Sheets
@st.cache_data(ttl=60)
def läs_inställningar():
    rows = inställningar_worksheet.get_all_records()
    if not rows:
        return {}
    return {rad["Namn"]: rad["Värde"] for rad in rows if "Namn" in rad and "Värde" in rad}

# Spara inställningar till Google Sheets
def spara_inställningar(data):
    inställningar_worksheet.clear()
    inställningar_worksheet.update("A1", [["Namn", "Värde"]])
    inställningar_worksheet.update("A2", [[k, v] for k, v in data.items()])

# Läs och skapa DataFrame från Google Sheets
def läs_data():
    rows = data_worksheet.get_all_records()
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows)
    return säkerställ_kolumner(df)

# Spara ny rad till databasen
def spara_data(rad):
    säkerställ_kolumner(pd.DataFrame([rad]))  # försäkrar rätt kolumner
    data_worksheet.append_row([rad.get(col, "") for col in COLUMNS])

# Funktion för att visa inställningsformulär
def visa_inställningar():
    st.subheader("Inställningar")
    inst = läs_inställningar()

    with st.form("instform"):
        startdatum = st.date_input("Startdatum", value=datetime.date.today(), min_value=datetime.date(1990, 1, 1))
        födelsedatum = st.date_input("Födelsedatum", value=datetime.date(2000, 1, 1), min_value=datetime.date(1970, 1, 1))
        namn = st.text_input("Namn på kvinnan", value=inst.get("Namn", ""))
        kompisar = st.number_input("Max kompisar", 0, 100, int(inst.get("Kompisar", 0)))
        pappans_vänner = st.number_input("Max pappans vänner", 0, 100, int(inst.get("Pappans vänner", 0)))
        nils_vänner = st.number_input("Max Nils vänner", 0, 100, int(inst.get("Nils vänner", 0)))
        nils_familj = st.number_input("Max Nils familj", 0, 100, int(inst.get("Nils familj", 0)))

        skicka = st.form_submit_button("Spara inställningar")

    if skicka:
        inst_data = {
            "Startdatum": str(startdatum),
            "Födelsedatum": str(födelsedatum),
            "Namn": namn,
            "Kompisar": int(kompisar),
            "Pappans vänner": int(pappans_vänner),
            "Nils vänner": int(nils_vänner),
            "Nils familj": int(nils_familj)
        }
        spara_inställningar(inst_data)
        st.success("Inställningar sparade.")

    if st.button("Rensa databasen"):
        data_worksheet.clear()
        data_worksheet.update("A1", [COLUMNS])
        st.success("Databasen har rensats.")

# Hämta nästa datum från inställningar eller tidigare rader
def bestäm_datum(df, inst):
    if df.empty:
        return pd.to_datetime(inst.get("Startdatum", datetime.date.today())).date()
    senaste_datum = pd.to_datetime(df["Datum"].iloc[-1])
    return (senaste_datum + pd.Timedelta(days=1)).date()

# Formulär för att lägga till scen
def scenformulär(df, inst):
    st.subheader("Lägg till scen")
    dagens_datum = bestäm_datum(df, inst)

    with st.form("scenformulär"):
        st.markdown(f"**Datum:** {dagens_datum}")
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", 0, 30, 0)
        nya_män = st.number_input("Nya män", 0, 100, 0)
        enkel_vaginal = st.number_input("Enkel vaginal", 0, 100, 0)
        enkel_anal = st.number_input("Enkel anal", 0, 100, 0)
        dp = st.number_input("DP", 0, 100, 0)
        dpp = st.number_input("DPP", 0, 100, 0)
        dap = st.number_input("DAP", 0, 100, 0)
        tpp = st.number_input("TPP", 0, 100, 0)
        tpa = st.number_input("TPA", 0, 100, 0)
        tap = st.number_input("TAP", 0, 100, 0)
        tid_enkel = st.number_input("Tid enkel", 0, 1000, 0)
        tid_dubbel = st.number_input("Tid dubbel", 0, 1000, 0)
        tid_trippel = st.number_input("Tid trippel", 0, 1000, 0)
        vila = st.number_input("Vila", 0, 3600, 0)
        kompisar = st.number_input(f"Kompisar (max {inst.get('Kompisar', 0)})", 0, 100, 0)
        pappans_vänner = st.number_input(f"Pappans vänner (max {inst.get('Pappans vänner', 0)})", 0, 100, 0)
        nils_vänner = st.number_input(f"Nils vänner (max {inst.get('Nils vänner', 0)})", 0, 100, 0)
        nils_familj = st.number_input(f"Nils familj (max {inst.get('Nils familj', 0)})", 0, 100, 0)
        dt_tid_per_man = st.number_input("DT tid per man", 0, 1000, 0)
        antal_varv = st.number_input("Antal varv", 0, 100, 0)
        älskar_med = st.number_input("Älskar med", 0, 100, 0)
        sover_med = st.number_input("Sover med", 0, 100, 0)
        nils_sex = st.number_input("Nils sex", 0, 100, 0)
        prenumeranter = st.number_input("Prenumeranter", 0, 100000, 0)
        intäkt = st.number_input("Intäkt ($)", 0.0, 1000000.0, 0.0)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", 0.0, 1000000.0, 0.0)
        mäns_lön = st.number_input("Mäns lön ($)", 0.0, 1000000.0, 0.0)
        kompisars_lön = st.number_input("Kompisars lön ($)", 0.0, 1000000.0, 0.0)
        dt_total_tid = st.number_input("DT total tid (sek)", 0, 1000000, 0)
        total_tid_sek = st.number_input("Total tid (sek)", 0, 1000000, 0)
        total_tid_h = st.number_input("Total tid (h)", 0.0, 1000.0, 0.0)
        minuter_per_kille = st.number_input("Minuter per kille", 0.0, 1000.0, 0.0)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
        skicka = st.form_submit_button("Spara scen")

    if skicka:
        maxkontroller = {
            "Kompisar": kompisar,
            "Pappans vänner": pappans_vänner,
            "Nils vänner": nils_vänner,
            "Nils familj": nils_familj,
        }
        för_max = False
        for fält, värde in maxkontroller.items():
            if int(värde) > int(inst.get(fält, 0)):
                st.error(f"{fält} överskrider maxgränsen ({inst.get(fält)})")
                för_max = True
        if not bekräfta:
            st.warning("Du måste bekräfta att du vill lägga till raden.")
        elif not för_max:
            ny_rad = {
                "Datum": str(dagens_datum),
                "Typ": typ,
                "Antal vilodagar": antal_vilodagar,
                "Nya män": nya_män,
                "Enkel vaginal": enkel_vaginal,
                "Enkel anal": enkel_anal,
                "DP": dp,
                "DPP": dpp,
                "DAP": dap,
                "TPP": tpp,
                "TPA": tpa,
                "TAP": tap,
                "Tid enkel": tid_enkel,
                "Tid dubbel": tid_dubbel,
                "Tid trippel": tid_trippel,
                "Vila": vila,
                "Kompisar": kompisar,
                "Pappans vänner": pappans_vänner,
                "Nils vänner": nils_vänner,
                "Nils familj": nils_familj,
                "DT tid per man": dt_tid_per_man,
                "Antal varv": antal_varv,
                "Älskar med": älskar_med,
                "Sover med": sover_med,
                "Nils sex": nils_sex,
                "Prenumeranter": prenumeranter,
                "Intäkt ($)": intäkt,
                "Kvinnans lön ($)": kvinnans_lön,
                "Mäns lön ($)": mäns_lön,
                "Kompisars lön ($)": kompisars_lön,
                "DT total tid (sek)": dt_total_tid,
                "Total tid (sek)": total_tid_sek,
                "Total tid (h)": total_tid_h,
                "Minuter per kille": minuter_per_kille
            }
            spara_data(ny_rad)
            st.success("Raden har sparats i databasen.")

# Huvudprogram
def main():
    st.set_page_config(page_title="Malin-produktionsapp", layout="wide")
    st.title("Malin-produktionsapp")

    menyval = st.sidebar.radio("Navigering", ["Lägg till scen", "Inställningar"])

    df = läs_data()
    inst = läs_inställningar()

    if menyval == "Lägg till scen":
        scenformulär(df, inst)
    elif menyval == "Inställningar":
        visa_inställningar()

if __name__ == "__main__":
    main()
