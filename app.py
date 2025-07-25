import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from konstanter import COLUMNS, säkerställ_kolumner

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gc = gspread.service_account_from_dict(st.secrets["GOOGLE_CREDENTIALS"])

# Hämta kalkylark
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"].get("SHEET_URL", None)
if not SHEET_URL:
    st.error("SHEET_URL saknas i secrets.")
    st.stop()

sh = gc.open_by_url(SHEET_URL)
data_sheet = sh.worksheet("Data")
inst_sheet = sh.worksheet("Inställningar")

# Läs in data
@st.cache_data(ttl=60)
def läs_data():
    data = data_sheet.get_all_records()
    df = pd.DataFrame(data)
    df = säkerställ_kolumner(df)
    return df

df = läs_data()

# Funktion för att läsa inställningar från arket
def läs_inställningar():
    inställningar = {}
    rows = inst_sheet.get_all_records()
    for rad in rows:
        inställningar[rad['Namn']] = rad['Värde']
    return inställningar

# Funktion för att spara inställning
def spara_inställning(namn, värde):
    cell = inst_sheet.find(namn)
    if cell:
        inst_sheet.update_cell(cell.row, cell.col + 1, värde)
    else:
        inst_sheet.append_row([namn, värde])

# Visa och redigera inställningar
with st.expander("🔧 Inställningar"):
    inst = läs_inställningar()

    startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", datetime.today().date())))
    senaste_datum = st.date_input("Senaste datum", value=pd.to_datetime(inst.get("Senaste datum", datetime.today().date())))

    if st.button("Spara inställningar"):
        spara_inställning("Startdatum", str(startdatum))
        spara_inställning("Senaste datum", str(senaste_datum))
        st.success("Inställningar sparade")

# Läser inställningar igen
inst = läs_inställningar()
startdatum = inst.get("Startdatum", str(datetime.today().date()))

# Ladda nuvarande data
@st.cache_data(ttl=60)
def ladda_data():
    data = data_sheet.get_all_records()
    return pd.DataFrame(data)

df = ladda_data()
nästa_datum = pd.to_datetime(startdatum)
if not df.empty and "Datum" in df.columns:
    senaste = pd.to_datetime(df["Datum"]).max()
    nästa_datum = senaste + pd.Timedelta(days=1)

# --- FORMULÄR ---
st.markdown("## ➕ Lägg till scen")
with st.form("scenformulär", clear_on_submit=False):
    st.markdown(f"**Datum som används:** `{nästa_datum.date()}`")
    typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
    antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, value=0)
    nya_män = st.number_input("Nya män", min_value=0, step=1)
    enkel_vaginal = st.number_input("Enkel vaginal", min_value=0, step=1)
    enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
    dp = st.number_input("DP", min_value=0, step=1)
    dpp = st.number_input("DPP", min_value=0, step=1)
    dap = st.number_input("DAP", min_value=0, step=1)
    tpp = st.number_input("TPP", min_value=0, step=1)
    tpa = st.number_input("TPA", min_value=0, step=1)
    tap = st.number_input("TAP", min_value=0, step=1)

    tid_enkel = st.number_input("Tid enkel (sek)", min_value=0, step=1)
    tid_dubbel = st.number_input("Tid dubbel (sek)", min_value=0, step=1)
    tid_trippel = st.number_input("Tid trippel (sek)", min_value=0, step=1)
    vila = st.number_input("Vila (sek mellan varje)", min_value=0, step=1)

    kompisar = st.number_input("Kompisar", min_value=0, step=1)
    pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1)
    nils_vänner = st.number_input("Nils vänner", min_value=0, step=1)
    nils_familj = st.number_input("Nils familj", min_value=0, step=1)
    dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1)
    antal_varv = st.number_input("Antal varv", min_value=0, step=1)
    älskar_med = st.number_input("Älskar med", min_value=0, step=1)
    sover_med = st.number_input("Sover med", min_value=0, step=1)
    nils_sex = st.number_input("Nils sex", min_value=0, step=1)
    prenumeranter = st.number_input("Prenumeranter", min_value=0, step=1)

    kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=1.0)
    mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=1.0)
    kompisars_lön = st.number_input("Kompisars lön ($)", min_value=0.0, step=1.0)

    # Enkel beräkning av total tid
    tot_tid_sek = (
        (enkel_vaginal + enkel_anal) * (tid_enkel + vila) +
        (dp + dpp + dap) * (tid_dubbel + vila) +
        (tpp + tpa + tap) * (tid_trippel + vila)
    )

    tot_tid_h = round(tot_tid_sek / 3600, 2)
    minuter_per_kille = round(tot_tid_sek / (nya_män + 1), 2) if nya_män + 1 > 0 else 0

    st.markdown(f"**Total tid:** `{tot_tid_h}` timmar")

    # Varning om > 18 timmar
    if tot_tid_h > 18:
        st.warning("⚠️ Tiden överstiger 18 timmar! Justera tider.")
        tid_enkel = st.number_input("Justera tid enkel", value=tid_enkel, key="just_enkel")
        tid_dubbel = st.number_input("Justera tid dubbel", value=tid_dubbel, key="just_dubbel")
        tid_trippel = st.number_input("Justera tid trippel", value=tid_trippel, key="just_trippel")

    bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
    submit = st.form_submit_button("Lägg till")

if submit and bekräfta:
    rad = [
        str(nästa_datum.date()), typ, antal_vilodagar, nya_män, enkel_vaginal, enkel_anal, dp, dpp, dap, tpp, tpa, tap,
        tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans_vänner, nils_vänner, nils_familj,
        dt_tid_per_man, antal_varv, älskar_med, sover_med, nils_sex, prenumeranter,
        0.0, kvinnans_lön, mäns_lön, kompisars_lön,
        dt_tid_per_man * (antal_varv or 0), tot_tid_sek, tot_tid_h, minuter_per_kille, vila
    ]
    try:
        data_sheet.append_row(rad)
        st.success("Rad tillagd!")
    except Exception as e:
        st.error(f"Fel vid sparning: {e}")

# Visa existerande data
st.markdown("## 📊 Nuvarande data i databasen")
try:
    df = pd.DataFrame(data_sheet.get_all_records())
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("Databasen är tom.")
except Exception as e:
    st.error(f"Fel vid hämtning av data: {e}")

# --- MAIN ---
def main():
    st.set_page_config(layout="wide", page_title="Malin-produktionsapp")
    st.title("🎬 Malin-produktionsapp")
    st.markdown("En app för att dokumentera och beräkna scenaktiviteter.")

if __name__ == "__main__":
    main()
