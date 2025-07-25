import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader, beräkna_tid_per_kille

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# Ladda data och inställningar
def load_data():
    try:
        ws = sh.worksheet("Data")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=COLUMNS)
        säkerställ_kolumner(df)
        return df
    except Exception as e:
        st.error(f"Fel vid hämtning av data: {e}")
        return pd.DataFrame(columns=COLUMNS)

def load_settings():
    try:
        ws = sh.worksheet("Inställningar")
        settings = ws.get_all_records()
        if not settings:
            return {}
        return settings[0]
    except Exception:
        return {}

def save_settings(settings_dict):
    ws = sh.worksheet("Inställningar")
    df = pd.DataFrame([settings_dict])
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# Inställningsformulär
def inställningsformulär():
    st.subheader("Inställningar")

    inst = load_settings()

    with st.form("instform"):
        namn = st.text_input("Kvinnans namn", value=inst.get("namn", ""))
        födelsedatum = st.date_input(
            "Födelsedatum", 
            value=pd.to_datetime(inst.get("födelsedatum", "2000-01-01")),
            min_value=datetime.date(1970, 1, 1),
            max_value=datetime.date.today()
        )
        startdatum = st.date_input(
            "Startdatum", 
            value=pd.to_datetime(inst.get("startdatum", datetime.date.today())),
            min_value=datetime.date(1990, 1, 1)
        )
        max_kompisar = st.number_input("Max kompisar", min_value=0, value=int(inst.get("kompisar", 0)))
        max_pappans_vänner = st.number_input("Max pappans vänner", min_value=0, value=int(inst.get("pappans_vänner", 0)))
        max_nils_vänner = st.number_input("Max Nils vänner", min_value=0, value=int(inst.get("nils_vänner", 0)))
        max_nils_familj = st.number_input("Max Nils familj", min_value=0, value=int(inst.get("nils_familj", 0)))

        spara = st.form_submit_button("Spara inställningar")

    if spara:
        settings = {
            "namn": namn,
            "födelsedatum": str(födelsedatum),
            "startdatum": str(startdatum),
            "kompisar": int(max_kompisar),
            "pappans_vänner": int(max_pappans_vänner),
            "nils_vänner": int(max_nils_vänner),
            "nils_familj": int(max_nils_familj)
        }
        save_settings(settings)
        st.success("Inställningar sparade!")

# Funktion: Läs tidigare data och hämta senaste datum
def hämta_senaste_datum(df, startdatum):
    if "Datum" in df.columns and not df.empty:
        try:
            df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")
            senaste = df["Datum"].dropna().max()
            return senaste + datetime.timedelta(days=1)
        except Exception:
            return startdatum
    return startdatum

# Funktion: Bestäm nästa datum för ny rad
def bestäm_datum(df):
    inst = load_settings()
    startdatum_str = inst.get("startdatum", str(datetime.date.today()))
    try:
        startdatum = pd.to_datetime(startdatum_str).date()
    except Exception:
        startdatum = datetime.date.today()
    nästa_datum = hämta_senaste_datum(df, startdatum)
    return nästa_datum.strftime("%Y-%m-%d")

# Funktion: Läs in data från Google Sheets
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = sh.worksheet("Data")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df = säkerställ_kolumner(df)
        return df
    except Exception as e:
        st.error(f"Fel vid hämtning av data: {e}")
        return pd.DataFrame(columns=COLUMNS)

# Funktion: Visa formulär för att lägga till en ny scen
def scenformulär(df, inst):
    st.subheader("Lägg till scen")
    med st.form("scenformulär", clear_on_submit=False):
        dagens_datum = bestäm_datum(df)
        st.markdown(f"**Datum:** {dagens_datum}")

        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, step=1, value=0 if typ != "Vila inspelningsplats" else 1)

        nya_män = st.number_input("Nya män", min_value=0, step=1)
        enkel_vaginal = st.number_input("Enkel vaginal", min_value=0, step=1)
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
        dp = st.number_input("DP", min_value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, step=1)
        dap = st.number_input("DAP", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)

        tid_enkel = st.number_input("Tid enkel", min_value=0, step=1)
        tid_dubbel = st.number_input("Tid dubbel", min_value=0, step=1)
        tid_trippel = st.number_input("Tid trippel", min_value=0, step=1)
        vila = st.number_input("Vila", min_value=0, step=1)

        def begränsad_input(fält, maxvärde):
            värde = st.number_input(fält + f" (Max {maxvärde})", min_value=0, step=1)
            if värde > maxvärde:
                st.warning(f"{fält} får högst vara {maxvärde}")
            return min(värde, maxvärde)

        kompisar = begränsad_input("Kompisar", inst.get("kompisar", 0))
        pappans_vänner = begränsad_input("Pappans vänner", inst.get("pappans_vänner", 0))
        nils_vänner = begränsad_input("Nils vänner", inst.get("nils_vänner", 0))
        nils_familj = begränsad_input("Nils familj", inst.get("nils_familj", 0))

        dt_tid_per_man = st.number_input("DT tid per man", min_value=0, step=1)
        antal_varv = st.number_input("Antal varv", min_value=0, step=1)
        älskar_med = st.number_input("Älskar med", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)
        nils_sex = st.number_input("Nils sex", min_value=0, step=1)
        prenumeranter = st.number_input("Prenumeranter", min_value=0, step=1)

        intakt = st.number_input("Intäkt ($)", min_value=0.0, step=1.0)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=1.0)
        mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=1.0)
        kompisars_lön = st.number_input("Kompisars lön ($)", min_value=0.0, step=1.0)

        dt_total_tid = st.number_input("DT total tid (sek)", min_value=0, step=1)
        total_tid_sek = st.number_input("Total tid (sek)", min_value=0, step=1)
        total_tid_h = st.number_input("Total tid (h)", min_value=0.0, step=0.1)
        minuter_per_kille = st.number_input("Minuter per kille", min_value=0.0, step=0.1)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
        skicka = st.form_submit_button("Lägg till scen")

    if skicka and bekräfta:
        ny_rad = [
            dagens_datum, typ, antal_vilodagar, nya_män, enkel_vaginal, enkel_anal, dp, dpp, dap, tpp, tpa, tap,
            tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans_vänner, nils_vänner, nils_familj,
            dt_tid_per_man, antal_varv, älskar_med, sover_med, nils_sex, prenumeranter, intakt,
            kvinnans_lön, mäns_lön, kompisars_lön, dt_total_tid, total_tid_sek, total_tid_h, minuter_per_kille, vila
        ]

        if len(ny_rad) != len(COLUMNS):
            st.error("Fel: Antal värden matchar inte kolumnerna.")
        else:
            df.loc[len(df)] = ny_rad
            spara_data(df)
            st.success("Scen tillagd!")

    return df

# Inställningsformulär
def inställningsformulär(inst):
    st.subheader("Inställningar")
    with st.form("instform"):
        startdatum = st.date_input("Startdatum för första scen", value=inst.get("startdatum", datetime.date.today()), min_value=datetime.date(1990, 1, 1))
        namn = st.text_input("Kvinnans namn", value=inst.get("namn", ""))
        födelsedatum = st.date_input("Födelsedatum", value=inst.get("födelsedatum", datetime.date(2000, 1, 1)), min_value=datetime.date(1970, 1, 1))

        kompisar = st.number_input("Max antal kompisar", min_value=0, step=1, value=inst.get("kompisar", 0))
        pappans_vänner = st.number_input("Max antal pappans vänner", min_value=0, step=1, value=inst.get("pappans_vänner", 0))
        nils_vänner = st.number_input("Max antal Nils vänner", min_value=0, step=1, value=inst.get("nils_vänner", 0))
        nils_familj = st.number_input("Max antal Nils familj", min_value=0, step=1, value=inst.get("nils_familj", 0))

        spara = st.form_submit_button("Spara inställningar")

    if spara:
        nydata = {
            "startdatum": startdatum,
            "namn": namn,
            "födelsedatum": födelsedatum,
            "kompisar": kompisar,
            "pappans_vänner": pappans_vänner,
            "nils_vänner": nils_vänner,
            "nils_familj": nils_familj
        }
        spara_inställningar(nydata)
        st.success("Inställningar sparade!")


# Main-funktion
def main():
    st.title("Malin - Produktionsapp")
    df = läs_data()
    inst = läs_inställningar()

    meny = st.sidebar.radio("Meny", ["Lägg till scen", "Inställningar"])

    if meny == "Lägg till scen":
        df = scenformulär(df, inst)
    elif meny == "Inställningar":
        inställningsformulär(inst)


# Kör appen
if __name__ == "__main__":
    main()
