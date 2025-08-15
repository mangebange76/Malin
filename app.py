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

# ---------- 2A) Säkerställ kolumner (exakt enligt din struktur) ----------
KOLUMNER = [
    "Veckodag","Scen","Män","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","Summa S","Summa D","Summa TP","Summa Vila","Summa tid",
    "Klockan","Älskar","Sover med","Känner","Pappans vänner","Grannar",
    "Nils vänner","Nils familj","Totalt Män","Tid kille","Nils",
    "Hångel","Suger","Prenumeranter","Avgift","Intäkter","Intäkt män",
    "Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst","Känner Sammanlagt","Hårdhet"
]

def säkerställ_kolumnrubriker():
    try:
        header = sheet.row_values(1)
        if header != KOLUMNER:
            sheet.clear()
            sheet.insert_row(KOLUMNER, 1)
            st.caption("🧱 Kolumnrubriker uppdaterade.")
    except Exception as e:
        st.warning(f"Kunde inte säkerställa kolumner (fortsätter ändå): {e}")

säkerställ_kolumnrubriker()

# ---------- 2B) Hjälpare: nästa veckodag + scennummer ----------
def nästa_veckodag_och_scen():
    try:
        all_vals = sheet.get_all_values()
        # rad 1 = header → antal datarader = len(all_vals) - 1
        datarader = max(0, len(all_vals) - 1)
        scen = datarader + 1  # nästa scen är antal datarader + 1
        veckodagar = ["Lördag","Söndag","Måndag","Tisdag","Onsdag","Torsdag","Fredag"]
        veckodag = veckodagar[(scen - 1) % 7]  # första raden Lördag
        return veckodag, scen
    except Exception:
        return "Lördag", 1

# ---------- 2C) Formulär (exakt dina fält) ----------
with st.form("ny_rad"):
    st.subheader("➕ Lägg till ny händelse")

    män = st.number_input("Män", min_value=0, step=1, value=0)
    fitta = st.number_input("Fitta", min_value=0, step=1, value=0)
    rumpa = st.number_input("Rumpa", min_value=0, step=1, value=0)
    dp = st.number_input("DP", min_value=0, step=1, value=0)
    dpp = st.number_input("DPP", min_value=0, step=1, value=0)
    dap = st.number_input("DAP", min_value=0, step=1, value=0)
    tap = st.number_input("TAP", min_value=0, step=1, value=0)

    tid_s = st.number_input("Tid S (sek)", min_value=0, step=1, value=60)
    tid_d = st.number_input("Tid D (sek)", min_value=0, step=1, value=60)
    vila  = st.number_input("Vila (sek)",  min_value=0, step=1, value=7)

    älskar    = st.number_input("Älskar", min_value=0, step=1, value=0)
    sover_med = st.number_input("Sover med", min_value=0, step=1, value=0)

    pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1, value=0)
    grannar        = st.number_input("Grannar", min_value=0, step=1, value=0)
    nils_vänner    = st.number_input("Nils vänner", min_value=0, step=1, value=0)
    nils_familj    = st.number_input("Nils familj", min_value=0, step=1, value=0)

    nils = st.number_input("Nils", min_value=0, step=1, value=0)

    submit = st.form_submit_button("💾 Spara")

# ---------- 3A) Fallback-beräkning (om berakningar.py saknas) ----------
def fallback_beräkning(rad_in):
    c = rad_in["Män"]; d=rad_in["Fitta"]; e=rad_in["Rumpa"]
    f=rad_in["DP"]; g=rad_in["DPP"]; h=rad_in["DAP"]; i=rad_in["TAP"]
    j=rad_in["Tid S"]; k=rad_in["Tid D"]; l=rad_in["Vila"]
    m = (c+d+e)*j
    n = (f+g+h)*k
    o = i*k
    p = (c+d+e+f+g+h+i)*l
    q = (m+n+o+p)/3600.0
    r = 7+3+q+1
    u = rad_in["Pappans vänner"] + rad_in["Grannar"] + rad_in["Nils vänner"] + rad_in["Nils familj"]
    z = u + c
    z_safe = z if z > 0 else 1
    ac = 10800/max(c,1)
    ad = (n*0.65)/z_safe
    ae = (c+d+e+f+g+h+i)
    af = 15
    ag = ae*af
    ah = c*120
    aj = max(150, min(800, ae*0.10))
    ai = (aj+120)*u
    ak = ag*0.20
    al = ag - ah - ai - aj - ak
    hårdhet = (2 if f>0 else 0) + (3 if g>0 else 0) + (5 if h>0 else 0) + (7 if i>0 else 0)

    return {
        **rad_in,
        "Summa S": m, "Summa D": n, "Summa TP": o, "Summa Vila": p, "Summa tid": q, "Klockan": r,
        "Känner": u, "Totalt Män": z, "Tid kille": ((m/z_safe)+(n/z_safe)+(o/z_safe)+ad)/60,
        "Hångel": ac, "Suger": ad, "Prenumeranter": ae, "Avgift": af, "Intäkter": ag,
        "Intäkt män": ah, "Intäkt Känner": ai, "Lön Malin": aj, "Intäkt Företaget": ak,
        "Vinst": al, "Känner Sammanlagt": u, "Hårdhet": hårdhet
    }

# ---------- 3B) Spara rad vid submit ----------
if submit:
    veckodag, scen = nästa_veckodag_och_scen()

    grund = {
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj,
        "Nils": nils
    }

    # Använd din beräkningsmodul om den finns, annars fallback
    if callable(berakna_radvärden):
        try:
            ber = berakna_radvärden(grund)
        except Exception as e:
            st.warning(f"berakningar.py kastade fel ({e}). Använder fallback-beräkning.")
            ber = fallback_beräkning(grund)
    else:
        ber = fallback_beräkning(grund)

    # Lägg i exakt kolumnordning
    rad_lista = [ber.get(k, "") for k in KOLUMNER]

    try:
        sheet.append_row(rad_lista)
        st.success("✅ Rad sparad.")
    except Exception as e:
        st.error(f"Kunde inte spara raden: {e}")

# ---------- 3C) Visa data + ta bort rader ----------
st.subheader("📊 Aktuella data")
try:
    records = sheet.get_all_records()
    if records:
        st.dataframe(records, use_container_width=True)
    else:
        st.info("Inga datarader ännu.")
except Exception as e:
    st.warning(f"Kunde inte läsa data: {e}")

st.subheader("🗑 Ta bort rad")
try:
    total_rows = len(sheet.get_all_values()) - 1  # antal datarader (exkl. header)
    if total_rows > 0:
        idx = st.number_input(
            "Radnummer att ta bort (1 = första dataraden under rubriken)",
            min_value=1, max_value=total_rows, step=1, value=1
        )
        if st.button("Ta bort vald rad"):
            # Header = rad 1 → datarad N = rad_index = N+1
            sheet.delete_rows(int(idx) + 1)
            st.success(f"Rad {idx} borttagen.")
            st.experimental_rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")
