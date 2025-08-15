import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta

try:
    from berakningar import beräkna_radvärden
except Exception:
    beräkna_radvärden = None

st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin-produktionsapp")

# ---------- 1) Auth: ENDAST Sheets-scope (ingen Drive) ----------
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

client = get_client()

# ---------- 2) Öppna arket via URL/ID (ingen Drive-listning) ----------
def _get_query_param(name, default=""):
    if hasattr(st, "query_params"):
        return st.query_params.get(name, [""])[0] if st.query_params.get(name) else default
    try:
        return st.experimental_get_query_params().get(name, [""])[0]
    except Exception:
        return default

def resolve_sheet(gc):
    last_err = None
    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        try:
            st.caption("🔗 Öppnar via SHEET_URL…")
            return gc.open_by_url(url).sheet1
        except Exception as e:
            last_err = e
            st.warning(f"SHEET_URL misslyckades: {e}")
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        try:
            st.caption("🆔 Öppnar via GOOGLE_SHEET_ID…")
            return gc.open_by_key(sid).sheet1
        except Exception as e:
            last_err = e
            st.warning(f"GOOGLE_SHEET_ID misslyckades: {e}")
    qp = _get_query_param("sheet", "")
    if qp:
        try:
            st.caption("🔎 Öppnar via query-param 'sheet'…")
            return gc.open_by_url(qp).sheet1 if qp.startswith("http") else gc.open_by_key(qp).sheet1
        except Exception as e:
            last_err = e
            st.warning(f"Query 'sheet' misslyckades: {e}")

    st.error("Hittade inget sätt att öppna arket. Lägg in SHEET_URL eller GOOGLE_SHEET_ID i Secrets, "
             "eller skicka ?sheet=<url|id> i adressen."
             f"\nSenaste fel: {last_err}")
    st.stop()

sheet = resolve_sheet(client)

# ---------- 3) Kolumnsäkring ----------
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

# ---------- 4) Sidopanelinställningar ----------
st.sidebar.header("Inställningar")
startdatum = st.sidebar.date_input("Historiskt startdatum", value=date.today())
starttid   = st.sidebar.time_input("Starttid", value=time(7, 0))
födelsedatum = st.sidebar.date_input("Malins födelsedatum", value=date(1999,1,1))

def datum_och_veckodag_för_scen(scen_nummer: int):
    rad_datum = startdatum + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return rad_datum, veckodagar[rad_datum.weekday()]

# ---------- 5) Formulär ----------
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

# ---------- 6) Fallback-beräkning (om modulen saknas) ----------
def fallback_beräkning(rad_in, rad_datum, födelsedatum, starttid):
    c = rad_in["Män"]; d=rad_in["Fitta"]; e=rad_in["Rumpa"]
    f=rad_in["DP"]; g=rad_in["DPP"]; h=rad_in["DAP"]; i=rad_in["TAP"]
    j=rad_in["Tid S"]; k=rad_in["Tid D"]; l=rad_in["Vila"]

    m = (c+d+e)*j; n=(f+g+h)*k; o=i*k; p=(c+d+e+f+g+h+i)*l
    q_hours = round((m+n+o+p)/3600.0, 1)
    start_dt = datetime.combine(rad_datum, starttid)
    klockan_str = (start_dt + timedelta(hours=3+q_hours+1)).strftime("%H:%M")

    u = rad_in["Pappans vänner"]+rad_in["Grannar"]+rad_in["Nils vänner"]+rad_in["Nils familj"]
    z = u + c; z_safe = z if z>0 else 1
    ac = 10800/max(c,1); ad=(n*0.65)/z_safe
    ae=(c+d+e+f+g+h+i); af=15; ag=ae*af; ah=c*120

    ålder = rad_datum.year - födelsedatum.year - ((rad_datum.month,rad_datum.day)<(födelsedatum.month,födelsedatum.day))
    if ålder < 18: raise ValueError("Ålder < 18 — spärrad rad.")
    faktor = 1.20 if 18<=ålder<=25 else 1.10 if 26<=ålder<=30 else 1.00 if 31<=ålder<=40 else 0.90
    aj = max(150, min(800, max(150, min(800, ae*0.10))*faktor))

    ai=(aj+120)*u; ak=ag*0.20; al=ag-ah-ai-aj-ak
    hårdhet=(2 if f>0 else 0)+(3 if g>0 else 0)+(5 if h>0 else 0)+(7 if i>0 else 0)

    return {
        **rad_in,
        "Summa S": m,"Summa D": n,"Summa TP": o,"Summa Vila": p,
        "Summa tid": q_hours,"Klockan": klockan_str,"Känner": u,"Totalt Män": z,
        "Tid kille": ((m/z_safe)+(n/z_safe)+(o/z_safe)+ad)/60,
        "Hångel": ac,"Suger": ad,"Prenumeranter": ae,"Avgift": af,"Intäkter": ag,
        "Intäkt män": ah,"Intäkt Känner": ai,"Lön Malin": aj,"Intäkt Företaget": ak,
        "Vinst": al,"Känner Sammanlagt": u,"Hårdhet": hårdhet
    }

# ---------- 7) Spara ----------
if submit:
    try:
        all_vals = sheet.get_all_values()
        scen = max(1, len(all_vals))  # nästa datarad
    except Exception:
        scen = 1

    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    grund = {
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Nils": nils
    }

    try:
        if callable(beräkna_radvärden):
            ber = beräkna_radvärden(grund, rad_datum, födelsedatum, starttid)
        else:
            ber = fallback_beräkning(grund, rad_datum, födelsedatum, starttid)
    except Exception as e:
        st.warning(f"Beräkning fel: {e}. Använder fallback.")
        ber = fallback_beräkning(grund, rad_datum, födelsedatum, starttid)

    rad = [ber.get(k, "") for k in KOLUMNER]
    try:
        sheet.append_row(rad)
        ålder = rad_datum.year - födelsedatum.year - ((rad_datum.month,rad_datum.day)<(födelsedatum.month,födelsedatum.day))
        st.success(f"✅ Rad sparad. Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")
    except Exception as e:
        st.error(f"Kunde inte spara raden: {e}")

# ---------- 8) Visa & radera ----------
st.subheader("📊 Aktuella data")
try:
    rows = sheet.get_all_records()
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Inga datarader ännu.")
except Exception as e:
    st.warning(f"Kunde inte läsa data: {e}")

st.subheader("🗑 Ta bort rad")
try:
    total_rows = len(sheet.get_all_values()) - 1
    if total_rows > 0:
        idx = st.number_input("Radnummer att ta bort (1 = första dataraden)", min_value=1, max_value=total_rows, step=1, value=1)
        if st.button("Ta bort vald rad"):
            sheet.delete_rows(int(idx) + 1)  # +1 för header
            st.success(f"Rad {idx} borttagen.")
            st.experimental_rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")
