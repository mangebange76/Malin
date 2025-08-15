import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

try:
    from berakningar import beräkna_radvärden
except Exception:
    beräkna_radvärden = None  # appen startar även om filen saknas

st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin-produktionsapp")

# ---------- 1) Auth: ENBART Sheets-scope (ingen Drive) ----------
def get_client():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=SCOPES
    )
    return gspread.authorize(creds)

client = get_client()

# ---------- 2) Öppna arket UTAN Drive API ----------
def resolve_sheet(gc):
    sheet = None
    err = None

    # 1) Via full URL (rekommenderas)
    url = st.secrets.get("SHEET_URL", "").strip()
    if url:
        try:
            sheet = gc.open_by_url(url).sheet1
            st.caption("🔗 Öppnade Google Sheet via SHEET_URL (open_by_url).")
            return sheet
        except Exception as e:
            err = e
            st.warning(f"Kunde inte öppna via SHEET_URL: {e}")

    # 2) Via ID (om du vill undvika att lagra full URL)
    sheet_id = st.secrets.get("GOOGLE_SHEET_ID", "").strip()
    if sheet_id:
        try:
            sheet = gc.open_by_key(sheet_id).sheet1
            st.caption("🆔 Öppnade Google Sheet via GOOGLE_SHEET_ID (open_by_key).")
            return sheet
        except Exception as e:
            err = e
            st.warning(f"Kunde inte öppna via GOOGLE_SHEET_ID: {e}")

    st.error(
        "Hittade inget sätt att öppna Google Sheet utan Drive API.\n"
        "Lägg in antingen SHEET_URL eller GOOGLE_SHEET_ID i Secrets."
        f"\nSenaste fel: {err}"
    )
    st.stop()

sheet = resolve_sheet(client)

# ---------- 3) Säkerställ kolumner ----------
KOLUMNER = [
    "Veckodag","Scen","Män","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","Summa S","Summa D","Summa TP","Summa Vila","Summa tid",
    "Klockan","Älskar","Sover med","Känner","Pappans vänner","Grannar",
    "Nils vänner","Nils familj","Totalt Män","Tid kille","Nils",
    "Hångel","Suger","Prenumeranter","Avgift","Intäkter","Intäkt män",
    "Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst","Känner Sammanlagt","Hårdhet"
]
try:
    header = sheet.row_values(1)
    if header != KOLUMNER:
        sheet.clear()
        sheet.insert_row(KOLUMNER, 1)
        st.caption("🧱 Kolumnrubriker uppdaterade.")
except Exception as e:
    st.warning(f"Kunde inte säkerställa kolumner (fortsätter ändå): {e}")

# ---------- 4) Formulär ----------
with st.form("ny_rad"):
    st.subheader("Lägg till ny händelse")

    män = st.number_input("Män", min_value=0, step=1, value=0)
    fitta = st.number_input("Fitta", min_value=0, step=1, value=0)
    rumpa = st.number_input("Rumpa", min_value=0, step=1, value=0)
    dp = st.number_input("DP", min_value=0, step=1, value=0)
    dpp = st.number_input("DPP", min_value=0, step=1, value=0)
    dap = st.number_input("DAP", min_value=0, step=1, value=0)
    tap = st.number_input("TAP", min_value=0, step=1, value=0)
    tid_s = st.number_input("Tid S (sek)", min_value=0, step=1, value=60)
    tid_d = st.number_input("Tid D (sek)", min_value=0, step=1, value=60)
    vila = st.number_input("Vila (sek)", min_value=0, step=1, value=7)
    älskar = st.number_input("Älskar", min_value=0, step=1, value=0)
    sover_med = st.number_input("Sover med", min_value=0, step=1, value=0)
    pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1, value=0)
    grannar = st.number_input("Grannar", min_value=0, step=1, value=0)
    nils_vänner = st.number_input("Nils vänner", min_value=0, step=1, value=0)
    nils_familj = st.number_input("Nils familj", min_value=0, step=1, value=0)
    nils = st.number_input("Nils", min_value=0, step=1, value=0)

    submit = st.form_submit_button("Spara")

# ---------- 5) Beräkna + spara ----------
def fallback_beräkning(rad_in):
    # Minimal backup om berakningar.py saknas – så appen ALLTID kan spara
    c = rad_in["Män"]; d=rad_in["Fitta"]; e=rad_in["Rumpa"]
    f=rad_in["DP"]; g=rad_in["DPP"]; h=rad_in["DAP"]; i=rad_in["TAP"]
    j=rad_in["Tid S"]; k=rad_in["Tid D"]; l=rad_in["Vila"]
    m = (c+d+e)*j ; n = (f+g+h)*k ; o = i*k
    p = (c+d+e+f+g+h+i)*l
    q = (m+n+o+p)/3600.0
    r = 7+3+q+1
    u = rad_in["Pappans vänner"]+rad_in["Grannar"]+rad_in["Nils vänner"]+rad_in["Nils familj"]
    z = u + c if (u+c)>0 else 1
    ac = 10800/max(c,1)
    ad = (n*0.65)/z
    ae = (c+d+e+f+g+h+i)
    af = 15
    ag = ae*af
    ah = c*120
    aj = max(150, min(800, ae*0.10))
    ai = (aj+120)*u
    ak = ag*0.20
    al = ag - ah - ai - aj - ak
    hårdhet = (2 if f>0 else 0)+(3 if g>0 else 0)+(5 if h>0 else 0)+(7 if i>0 else 0)
    return {
        **rad_in,
        "Summa S": m, "Summa D": n, "Summa TP": o, "Summa Vila": p, "Summa tid": q, "Klockan": r,
        "Känner": u, "Totalt Män": u+c, "Tid kille": ((m/z)+(n/z)+(o/z)+ad)/60,
        "Hångel": ac, "Suger": ad, "Prenumeranter": ae, "Avgift": af, "Intäkter": ag,
        "Intäkt män": ah, "Intäkt Känner": ai, "Lön Malin": aj, "Intäkt Företaget": ak,
        "Vinst": al, "Känner Sammanlagt": u, "Hårdhet": hårdhet
    }

if submit:
    # Nästa veckodag + scen
    try:
        all_vals = sheet.get_all_values()
        scen = max(1, len(all_vals))  # nästa radnummer
        veckodagar = ["Lördag","Söndag","Måndag","Tisdag","Onsdag","Torsdag","Fredag"]
        veckodag = veckodagar[(scen-1) % 7]
    except Exception:
        scen, veckodag = 1, "Lördag"

    grund = {
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Nils": nils
    }

    # Försök med din modul; annars fallback
    if beräkna_radvärden:
        try:
            ber = beräkna_radvärden(grund)
        except Exception as e:
            st.warning(f"berakningar.py kastade fel ({e}). Använder fallback-beräkning.")
            ber = fallback_beräkning(grund)
    else:
        ber = fallback_beräkning(grund)

    # Lägg i rätt kolumnordning
    rad = [ber.get(k, "") for k in KOLUMNER]

    try:
        sheet.append_row(rad)
        st.success("✅ Rad sparad.")
    except Exception as e:
        st.error(f"Kunde inte spara raden: {e}")
