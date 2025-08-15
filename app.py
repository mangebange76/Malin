import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random

try:
    from berakningar import beräkna_radvärden
except Exception:
    beräkna_radvärden = None

st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin-produktionsapp")

# ---------- Retry-hjälpare för 429 ----------
def _retry_call(fn, *args, **kwargs):
    """Kör fn med exponential backoff vid rate limit (429/RESOURCE_EXHAUSTED)."""
    delay = 0.5
    for _ in range(6):  # ~ max ~15s
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "RATE_LIMIT_EXCEEDED"]):
                _time.sleep(delay + random.uniform(0, 0.25))
                delay = min(delay * 2, 4)
                continue
            raise
    return fn(*args, **kwargs)

# ---------- Auth: ENDAST Sheets-scope (cacheas) ----------
@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

client = get_client()

# ---------- Öppna arket (cacheas) ----------
@st.cache_resource(show_spinner=False)
def resolve_sheet(gc):
    """
    Öppna arket EN gång per session. Preferera GOOGLE_SHEET_ID (mindre overhead) före URL.
    """
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        st.caption("🆔 Öppnar via GOOGLE_SHEET_ID…")
        return _retry_call(gc.open_by_key, sid).sheet1

    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        st.caption("🔗 Öppnar via SHEET_URL…")
        return _retry_call(gc.open_by_url, url).sheet1

    # Fallback via query param ?sheet=<id|url>
    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        st.caption("🔎 Öppnar via query-param 'sheet'…")
        if qp.startswith("http"):
            return _retry_call(gc.open_by_url, qp).sheet1
        else:
            return _retry_call(gc.open_by_key, qp).sheet1

    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

sheet = resolve_sheet(client)

# ---------- Kolumnsäkring (cacheas; körs en gång) ----------
KOLUMNER = [
    "Veckodag","Scen","Män","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","Summa S","Summa D","Summa TP","Summa Vila",
    "Summa tid","Summa tid (sek)",
    "Klockan","Älskar","Sover med","Känner","Pappans vänner","Grannar",
    "Nils vänner","Nils familj","Totalt Män","Tid kille","Nils",
    "Hångel","Suger","Prenumeranter","Avgift","Intäkter","Intäkt män",
    "Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst","Känner Sammanlagt","Hårdhet"
]

@st.cache_resource(show_spinner=False)
def ensure_header_once(_sheet):
    try:
        header = _retry_call(_sheet.row_values, 1)
        if header != KOLUMNER:
            _retry_call(_sheet.clear)
            _retry_call(_sheet.insert_row, KOLUMNER, 1)
            st.caption("🧱 Kolumnrubriker uppdaterade.")
    except Exception as e:
        st.warning(f"Kunde inte säkerställa kolumner (fortsätter ändå): {e}")

ensure_header_once(sheet)

# ---------- Sidopanel ----------
st.sidebar.header("Inställningar")
startdatum = st.sidebar.date_input("Historiskt startdatum", value=date.today())
starttid   = st.sidebar.time_input("Starttid", value=time(7, 0))
födelsedatum = st.sidebar.date_input("Malins födelsedatum", value=date(1999,1,1))

# Max-regler (Auto-Max) i session_state
def _init_max(key, default_val=10):
    if key not in st.session_state:
        st.session_state[key] = default_val
_init_max("MAX_PAPPAN", 10)
_init_max("MAX_GRANNAR", 10)
_init_max("MAX_NILS_VANNER", 10)
_init_max("MAX_NILS_FAMILJ", 10)

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
st.session_state.MAX_PAPPAN      = st.sidebar.number_input("Max Pappans vänner", min_value=0, step=1, value=st.session_state.MAX_PAPPAN)
st.session_state.MAX_GRANNAR     = st.sidebar.number_input("Max Grannar",        min_value=0, step=1, value=st.session_state.MAX_GRANNAR)
st.session_state.MAX_NILS_VANNER = st.sidebar.number_input("Max Nils vänner",    min_value=0, step=1, value=st.session_state.MAX_NILS_VANNER)
st.session_state.MAX_NILS_FAMILJ = st.sidebar.number_input("Max Nils familj",    min_value=0, step=1, value=st.session_state.MAX_NILS_FAMILJ)

def datum_och_veckodag_för_scen(scen_nummer: int):
    rad_datum = startdatum + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return rad_datum, veckodagar[rad_datum.weekday()]

# ---------- Minimera reads: håll koll på antal datarader lokalt ----------
def _init_row_count():
    if "ROW_COUNT" not in st.session_state:
        try:
            # Läs bara kolumn A för att approximera antal rader (mindre read)
            vals = _retry_call(sheet.col_values, 1)  # kolumn A
            if vals and vals[0] == "Veckodag":
                datarader = max(0, len(vals) - 1)
            else:
                datarader = len(vals)
            st.session_state.ROW_COUNT = datarader
        except Exception:
            st.session_state.ROW_COUNT = 0

_init_row_count()

def next_scene_number():
    return st.session_state.ROW_COUNT + 1

# ---------- Formulär ----------
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

    # Max-etiketter + heads-up
    lbl_p  = f"Pappans vänner (max {st.session_state.MAX_PAPPAN})"
    lbl_g  = f"Grannar (max {st.session_state.MAX_GRANNAR})"
    lbl_nv = f"Nils vänner (max {st.session_state.MAX_NILS_VANNER})"
    lbl_nf = f"Nils familj (max {st.session_state.MAX_NILS_FAMILJ})"

    pappans_vänner = st.number_input(lbl_p, min_value=0, step=1, value=0, key="input_pappan")
    if pappans_vänner > st.session_state.MAX_PAPPAN:
        st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} överskrider max {st.session_state.MAX_PAPPAN}</span>", unsafe_allow_html=True)

    grannar = st.number_input(lbl_g, min_value=0, step=1, value=0, key="input_grannar")
    if grannar > st.session_state.MAX_GRANNAR:
        st.markdown(f"<span style='color:#d00'>⚠️ {grannar} överskrider max {st.session_state.MAX_GRANNAR}</span>", unsafe_allow_html=True)

    nils_vänner = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
    if nils_vänner > st.session_state.MAX_NILS_VANNER:
        st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} överskrider max {st.session_state.MAX_NILS_VANNER}</span>", unsafe_allow_html=True)

    nils_familj = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")
    if nils_familj > st.session_state.MAX_NILS_FAMILJ:
        st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} överskrider max {st.session_state.MAX_NILS_FAMILJ}</span>", unsafe_allow_html=True)

    nils = st.number_input("Nils", min_value=0, step=1, value=0)

    submit = st.form_submit_button("💾 Spara")

# ---------- Fallback-beräkning (om modulen saknas) ----------
def fallback_beräkning(rad_in, rad_datum, födelsedatum, starttid):
    c = rad_in["Män"]; d=rad_in["Fitta"]; e=rad_in["Rumpa"]
    f=rad_in["DP"]; g=rad_in["DPP"]; h=rad_in["DAP"]; i=rad_in["TAP"]
    j=rad_in["Tid S"]; k=rad_in["Tid D"]; l=rad_in["Vila"]

    m = (c+d+e)*j; n=(f+g+h)*k; o=i*k; p=(c+d+e+f+g+h+i)*l
    q_sec = m+n+o+p
    q_hours = q_sec/3600.0
    klockan_str = (datetime.combine(rad_datum, starttid)
                   + timedelta(hours=3) + timedelta(hours=q_hours) + timedelta(hours=1)
                   ).strftime("%H:%M")

    # 'xh yy min'
    h_t = int(q_sec//3600); m_t = int(round((q_sec%3600)/60.0))
    if m_t == 60: h_t += 1; m_t = 0
    summa_tid_str = f"{h_t}h {m_t} min"

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
        "Summa tid": summa_tid_str,"Summa tid (sek)": q_sec,
        "Klockan": klockan_str,"Känner": u,"Totalt Män": z,
        "Tid kille": ((m/z_safe)+(n/z_safe)+(o/z_safe)+ad)/60,
        "Hångel": ac,"Suger": ad,"Prenumeranter": ae,"Avgift": af,"Intäkter": ag,
        "Intäkt män": ah,"Intäkt Känner": ai,"Lön Malin": aj,"Intäkt Företaget": ak,
        "Vinst": al,"Känner Sammanlagt": u,"Hårdhet": hårdhet
    }

# ---------- Auto-Max: pending-save hantering ----------
def _store_pending(grund_dict, scen, rad_datum, veckodag, over_max_dict):
    st.session_state["PENDING_SAVE"] = {
        "grund": grund_dict,
        "scen": scen,
        "rad_datum": str(rad_datum),
        "veckodag": veckodag,
        "over_max": over_max_dict
    }

def _clear_pending():
    if "PENDING_SAVE" in st.session_state:
        del st.session_state["PENDING_SAVE"]

def _parse_date(d):
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()

def _apply_auto_max_and_save(pending):
    # Höj max för alla övertramp
    for key, info in pending["over_max"].items():
        st.session_state[info["max_key"]] = info["new_value"]

    grund = pending["grund"]
    scen = pending["scen"]
    rad_datum = _parse_date(pending["rad_datum"])
    veckodag = pending["veckodag"]

    try:
        if callable(beräkna_radvärden):
            ber = beräkna_radvärden(grund, rad_datum, födelsedatum, starttid)
        else:
            ber = fallback_beräkning(grund, rad_datum, födelsedatum, starttid)
    except Exception as e:
        st.warning(f"Beräkning fel: {e}. Använder fallback.")
        ber = fallback_beräkning(grund, rad_datum, födelsedatum, starttid)

    rad = [ber.get(k, "") for k in KOLUMNER]
    _retry_call(sheet.append_row, rad)
    st.session_state.ROW_COUNT += 1  # lokalt antal ökas

    ålder = rad_datum.year - födelsedatum.year - ((rad_datum.month,rad_datum.day)<(födelsedatum.month,födelsedatum.day))
    st.success(f"✅ Max uppdaterades och rad sparades. Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")

# ---------- Spara (med Auto-Max) ----------
if submit:
    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    grund = {
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Nils": nils
    }

    # Kolla övertramp mot max
    over_max = {}
    if pappans_vänner > st.session_state.MAX_PAPPAN:
        over_max["Pappans vänner"] = {"current_max": st.session_state.MAX_PAPPAN, "new_value": pappans_vänner, "max_key": "MAX_PAPPAN"}
    if grannar > st.session_state.MAX_GRANNAR:
        over_max["Grannar"] = {"current_max": st.session_state.MAX_GRANNAR, "new_value": grannar, "max_key": "MAX_GRANNAR"}
    if nils_vänner > st.session_state.MAX_NILS_VANNER:
        over_max["Nils vänner"] = {"current_max": st.session_state.MAX_NILS_VANNER, "new_value": nils_vänner, "max_key": "MAX_NILS_VANNER"}
    if nils_familj > st.session_state.MAX_NILS_FAMILJ:
        over_max["Nils familj"] = {"current_max": st.session_state.MAX_NILS_FAMILJ, "new_value": nils_familj, "max_key": "MAX_NILS_FAMILJ"}

    if over_max:
        # Kräver bekräftelse (visas nedan)
        _store_pending(grund, scen, rad_datum, veckodag, over_max)
    else:
        # Spara direkt
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
            _retry_call(sheet.append_row, rad)
            st.session_state.ROW_COUNT += 1  # lokalt antal ökas
            ålder = rad_datum.year - födelsedatum.year - ((rad_datum.month,rad_datum.day)<(födelsedatum.month,födelsedatum.day))
            st.success(f"✅ Rad sparad. Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")
        except Exception as e:
            st.error(f"Kunde inte spara raden: {e}")

# ---------- Visa ev. Auto-Max-varning ----------
if "PENDING_SAVE" in st.session_state:
    pending = st.session_state["PENDING_SAVE"]
    lst = []
    for f, info in pending["over_max"].items():
        lst.append(f"- **{f}**: nuvarande max {info['current_max']}, nytt värde {info['new_value']}")
    st.warning(
        "Du har angivit värden som överstiger nuvarande max.\n\n"
        + "\n".join(lst) +
        "\n\nVill du uppdatera maxvärdena till dessa nya värden och spara raden?"
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Ja, uppdatera och spara"):
            try:
                _apply_auto_max_and_save(pending)
            except Exception as e:
                st.error(f"Kunde inte spara: {e}")
            finally:
                _clear_pending()
                st.experimental_rerun()
    with c2:
        if st.button("✋ Nej, avbryt"):
            _clear_pending()
            st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

# ---------- Visa & radera ----------
st.subheader("📊 Aktuella data")
try:
    rows = _retry_call(sheet.get_all_records)
    if rows:
        show_secs = st.checkbox("Visa även 'Summa tid (sek)'", value=False)
        if not show_secs:
            rows = [{k: v for k, v in r.items() if k != "Summa tid (sek)"} for r in rows]
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Inga datarader ännu.")
except Exception as e:
    st.warning(f"Kunde inte läsa data: {e}")

st.subheader("🗑 Ta bort rad")
try:
    total_rows = st.session_state.ROW_COUNT  # lokalt räknat
    if total_rows > 0:
        idx = st.number_input("Radnummer att ta bort (1 = första dataraden)", min_value=1, max_value=total_rows, step=1, value=1)
        if st.button("Ta bort vald rad"):
            _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 för header
            st.session_state.ROW_COUNT -= 1
            st.success(f"Rad {idx} borttagen.")
            st.experimental_rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")
