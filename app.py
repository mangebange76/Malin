import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import dummy_beräkningar

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(credentials)

# Hämta kalkylarket
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# Initiera blad
def initiera_blad():
    blad_namn = [ws.title for ws in sh.worksheets()]

    if "Data" not in blad_namn:
        sh.add_worksheet(title="Data", rows=1000, cols=len(COLUMNS))
        sh.worksheet("Data").append_row(COLUMNS)

    if "Inställningar" not in blad_namn:
        inst_ws = sh.add_worksheet(title="Inställningar", rows=100, cols=2)
        inst_ws.append_row(["Fält", "Värde"])
        default_settings = {
            "Startdatum": datetime.today().strftime("%Y-%m-%d"),
            "Födelsedatum": "2000-01-01",
            "Kvinnans namn": "Malin",
            "Kompisar": 10,
            "Pappans vänner": 10,
            "Nils vänner": 10,
            "Nils familj": 10,
        }
        for key, value in default_settings.items():
            inst_ws.append_row([key, value])

initiera_blad()

# Funktion: läs inställningar
def läs_inställningar():
    try:
        inst_df = pd.DataFrame(sh.worksheet("Inställningar").get_all_records())
        if "Fält" not in inst_df.columns or "Värde" not in inst_df.columns:
            raise ValueError("Felaktig struktur i inställningsbladet.")
        return inst_df.set_index("Fält")["Värde"].to_dict()
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar: {e}")
        return {}

# Funktion: spara inställningar
def spara_inställningar(ny_dict):
    ws = sh.worksheet("Inställningar")
    ws.clear()
    ws.append_row(["Fält", "Värde"])
    for key, value in ny_dict.items():
        ws.append_row([key, value])

# Funktion: läs data
def läs_data():
    try:
        data = sh.worksheet("Data").get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
        return säkerställ_kolumner(df)
    except Exception as e:
        st.error(f"Kunde inte läsa data: {e}")
        return pd.DataFrame(columns=COLUMNS)

# Funktion: spara ny rad
def spara_data(rad):
    try:
        ws = sh.worksheet("Data")
        säkerställ_kolumner(pd.DataFrame([rad], columns=COLUMNS))  # säkerställ form
        ws.append_row(rad)
        st.success("Raden har sparats!")
    except Exception as e:
        st.error(f"Fel vid sparande: {e}")

# Funktion: bestäm datum för ny rad
def bestäm_datum(df, inst):
    if df.empty:
        startdatum = inst.get("Startdatum", datetime.today().strftime("%Y-%m-%d"))
        return pd.to_datetime(startdatum).strftime("%Y-%m-%d")
    else:
        senaste = pd.to_datetime(df["Datum"].iloc[-1], errors="coerce")
        if pd.isna(senaste):
            return datetime.today().strftime("%Y-%m-%d")
        return (senaste + timedelta(days=1)).strftime("%Y-%m-%d")

# Gränssnitt
def visa_inställningar():
    inst = läs_inställningar()

    st.subheader("Inställningar")
    with st.form("instform"):
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", datetime.today())), min_value=datetime(1990, 1, 1))
        födelsedatum = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "2000-01-01")), min_value=datetime(1970, 1, 1))
        namn = st.text_input("Kvinnans namn", inst.get("Kvinnans namn", ""))

        kompisar = st.number_input("Kompisar", min_value=0, value=int(inst.get("Kompisar", 10)))
        pvänner = st.number_input("Pappans vänner", min_value=0, value=int(inst.get("Pappans vänner", 10)))
        nvänner = st.number_input("Nils vänner", min_value=0, value=int(inst.get("Nils vänner", 10)))
        nfam = st.number_input("Nils familj", min_value=0, value=int(inst.get("Nils familj", 10)))

        spara = st.form_submit_button("Spara inställningar")
        rensa = st.form_submit_button("Rensa databas")

    if spara:
        ny_dict = {
            "Startdatum": startdatum.strftime("%Y-%m-%d"),
            "Födelsedatum": födelsedatum.strftime("%Y-%m-%d"),
            "Kvinnans namn": namn,
            "Kompisar": kompisar,
            "Pappans vänner": pvänner,
            "Nils vänner": nvänner,
            "Nils familj": nfam,
        }
        spara_inställningar(ny_dict)
        st.success("Inställningar sparade.")

    if rensa:
        sh.worksheet("Data").clear()
        sh.worksheet("Data").append_row(COLUMNS)
        st.success("Databasen har rensats.")

def visa_formulär(df, inst):
    from berakningar import dummy_beräkningar

    st.subheader("Lägg till scen")
    with st.form("scenformulär", clear_on_submit=False):
        datum = bestäm_datum(df, inst)
        st.markdown(f"**Datum för ny rad:** {datum}")

        f = {}
        f["Datum"] = datum
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", value=0)
        f["Nya män"] = st.number_input("Nya män", value=0)
        f["Enkel vaginal"] = st.number_input("Enkel vaginal", value=0)
        f["Enkel anal"] = st.number_input("Enkel anal", value=0)
        f["DP"] = st.number_input("DP", value=0)
        f["DPP"] = st.number_input("DPP", value=0)
        f["DAP"] = st.number_input("DAP", value=0)
        f["TPP"] = st.number_input("TPP", value=0)
        f["TPA"] = st.number_input("TPA", value=0)
        f["TAP"] = st.number_input("TAP", value=0)

        f["Tid enkel"] = st.number_input("Tid enkel (min)", value=0)
        f["Tid dubbel"] = st.number_input("Tid dubbel (min)", value=0)
        f["Tid trippel"] = st.number_input("Tid trippel (min)", value=0)
        f["Vila"] = st.number_input("Vila (min)", value=0)

        for nyckel in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            maxv = int(inst.get(nyckel, 10))
            val = st.number_input(f"{nyckel} (max {maxv})", min_value=0, value=0, key=nyckel)
            if val > maxv:
                st.warning(f"Maxvärde för {nyckel} är {maxv}")
            f[nyckel] = val

        # Dummy-värden för beräkningar
        dummy_resultat = dummy_beräkningar(f)
        f.update(dummy_resultat)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
        submit = st.form_submit_button("Spara scen")

    if submit:
        if not bekräfta:
            st.warning("Du måste bekräfta att du vill lägga till raden.")
            return

        ny_rad = [f.get(k, "") for k in COLUMNS]
        spara_data(ny_rad)

def main():
    st.title("Malin produktionsapp")
    menyval = st.sidebar.selectbox("Välj vy", ["Lägg till scen", "Inställningar"])
    df = läs_data()
    inst = läs_inställningar()

    if menyval == "Inställningar":
        visa_inställningar()
    else:
        visa_formulär(df, inst)

if __name__ == "__main__":
    main()
