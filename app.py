import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

try:
    from berakningar import berakna_radvärden
except Exception:
    berakna_radvärden = None  # Appen startar även om filen saknas

# ---- Sidinställning ----
st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin-produktionsapp")

# ---- Google Sheets Auth ----
def get_client():
    """Skapar gspread-klient med breda scopes (Sheets + Drive)."""
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=SCOPES
    )
    return gspread.authorize(creds)

client = get_client()

# ---- Öppna arket ----
def resolve_sheet(gc):
    """
    Försöker öppna arket i prioriterad ordning:
    SHEET_URL → GOOGLE_SHEET_ID → SHEET_NAME → fallback-namn 'MalinData2'
    """
    # 1) Via full URL
    if "SHEET_URL" in st.secrets:
        try:
            sh = gc.open_by_url(st.secrets["SHEET_URL"])
            st.caption("🔗 Öppnade Google Sheet via SHEET_URL.")
            return sh.sheet1
        except Exception as e:
            st.warning(f"Kunde inte öppna via SHEET_URL: {e}")

    # 2) Via ID
    if "GOOGLE_SHEET_ID" in st.secrets:
        try:
            sh = gc.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
            st.caption("🆔 Öppnade Google Sheet via GOOGLE_SHEET_ID.")
            return sh.sheet1
        except Exception as e:
            st.warning(f"Kunde inte öppna via GOOGLE_SHEET_ID: {e}")

    # 3) Via namn
    if "SHEET_NAME" in st.secrets:
        try:
            sh = gc.open(st.secrets["SHEET_NAME"])
            st.caption("📄 Öppnade Google Sheet via SHEET_NAME.")
            return sh.sheet1
        except Exception as e:
            st.warning(f"Kunde inte öppna via SHEET_NAME: {e}")

    # 4) Fallback
    try:
        sh = gc.open("MalinData2")
        st.caption("🪪 Öppnade Google Sheet via fallback-namnet 'MalinData2'.")
        return sh.sheet1
    except Exception as e:
        st.error(
            "Kunde inte öppna något Google Sheet.\n\n"
            "Testade i ordning: SHEET_URL → GOOGLE_SHEET_ID → SHEET_NAME → 'MalinData2'.\n"
            f"Fel från Google: {e}"
        )
        raise

sheet = resolve_sheet(client)

import pandas as pd

# ---- Säkerställ att alla kolumner finns ----
def säkerställ_kolumner(df):
    """Ser till att alla nödvändiga kolumner finns i rätt ordning."""
    kolumner = [
        "Datum", "Veckodag", "Typ", "Antal män", "Minuter per kille",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya män",
        "Summa tid (h)", "Tid kille (min)", "Kvinnans lön (USD)",
        "Malins lön (USD)", "Totalt män", "Kommentar"
    ]
    for kol in kolumner:
        if kol not in df.columns:
            df[kol] = ""
    return df[kolumner]

# ---- Läs in data från Google Sheets ----
def hamta_data():
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    df = säkerställ_kolumner(df)
    return df

# ---- Spara data till Google Sheets ----
def spara_data(df):
    df = säkerställ_kolumner(df)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

# ---- Datum & veckodagslogik ----
def bestäm_datum(df):
    """Returnerar nästa datum och veckodag baserat på senaste raden i df."""
    if df.empty or not df["Datum"].iloc[-1]:
        startdatum = st.secrets.get("STARTDATUM", datetime.today().strftime("%Y-%m-%d"))
        dt = datetime.strptime(startdatum, "%Y-%m-%d")
    else:
        senaste = datetime.strptime(df["Datum"].iloc[-1], "%Y-%m-%d")
        dt = senaste + pd.Timedelta(days=1)
    veckodag = dt.strftime("%A")
    return dt.strftime("%Y-%m-%d"), veckodag

# ---- Formulär för att lägga till rad ----
def scenformulär(df):
    st.subheader("➕ Lägg till ny rad")
    datum, veckodag = bestäm_datum(df)
    st.info(f"📅 Datum sätts automatiskt: {datum} ({veckodag})")

    with st.form("lägg_till_rad", clear_on_submit=True):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_män = st.number_input("Antal män", min_value=0, step=1)
        minuter_per_kille = st.number_input("Minuter per kille", min_value=0, step=1)
        jobb = st.number_input("Jobb", min_value=0, step=1)
        grannar = st.number_input("Grannar", min_value=0, step=1)
        tjej_pojkv = st.number_input("Tjej PojkV", min_value=0, step=1)
        nils_fam = st.number_input("Nils fam", min_value=0, step=1)
        nya_män = st.number_input("Nya män", min_value=0, step=1)
        kommentar = st.text_input("Kommentar")

        sparaknapp = st.form_submit_button("💾 Spara rad")

    if sparaknapp:
        ny_rad = {
            "Datum": datum,
            "Veckodag": veckodag,
            "Typ": typ,
            "Antal män": antal_män,
            "Minuter per kille": minuter_per_kille,
            "Jobb": jobb,
            "Grannar": grannar,
            "Tjej PojkV": tjej_pojkv,
            "Nils fam": nils_fam,
            "Nya män": nya_män,
            "Kommentar": kommentar
        }
        if berakna_radvärden:
            ny_rad = berakna_radvärden(ny_rad)
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(df)
        st.success("✅ Raden sparades!")
    return df

def main():
    st.title("🎬 Malin Produktionsapp")

    # Hämta befintliga data
    df = hamta_data()

    # Formulär för ny rad
    df = scenformulär(df)

    st.subheader("📊 Aktuell data")
    st.dataframe(df, use_container_width=True)

    # Radera rad
    st.subheader("🗑 Ta bort rad")
    if not df.empty:
        rad_index = st.number_input("Ange radnummer att ta bort", min_value=0, max_value=len(df)-1, step=1)
        if st.button("Ta bort vald rad"):
            df = df.drop(index=rad_index).reset_index(drop=True)
            spara_data(df)
            st.success(f"✅ Rad {rad_index} togs bort.")
            st.experimental_rerun()
    else:
        st.info("Ingen data att visa eller ta bort.")

if __name__ == "__main__":
    main()
