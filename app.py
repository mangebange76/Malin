import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random
import pandas as pd

# Försök använda din beräkningsmodul; fallback om den saknas
try:
    from berakningar import beräkna_radvärden
except Exception:
    berakna_radvärden = None

# ===================================================================
#                      Grundinställning för appen
# ===================================================================
st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin-produktionsapp")

# ===================================================================
#                           Hjälpfunktioner
# ===================================================================
def _retry_call(fn, *args, **kwargs):
    """Kör fn med exponential backoff vid rate limit (429/RESOURCE_EXHAUSTED)."""
    delay = 0.5
    for _ in range(6):  # upp till ~15s
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

def _clamp(d: date, lo: date, hi: date):
    if d < lo: return lo
    if d > hi: return hi
    return d

def _hm_str_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

# ===================================================================
#                         Google Sheets-klient
# ===================================================================
@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

client = get_client()

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket EN gång per session utan Drive-API (ingen open(name))."""
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        st.caption("🆔 Öppnar via GOOGLE_SHEET_ID…")
        return _retry_call(client.open_by_key, sid).sheet1

    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        st.caption("🔗 Öppnar via SHEET_URL…")
        return _retry_call(client.open_by_url, url).sheet1

    # Fallback via query param ?sheet=<id|url>
    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        st.caption("🔎 Öppnar via query-param 'sheet'…")
        return (_retry_call(client.open_by_url, qp).sheet1
                if qp.startswith("http")
                else _retry_call(client.open_by_key, qp).sheet1)

    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

sheet = resolve_sheet()

# ===================================================================
#                   Kolumnsäkring (icke-destruktiv migration)
# ===================================================================
DEFAULT_COLUMNS = [
    "Veckodag","Scen","Män","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","Summa S","Summa D","Summa TP","Summa Vila",
    "Tid Älskar (sek)","Tid Älskar",
    "Tid Sover med (sek)","Tid Sover med",
    "Summa tid","Summa tid (sek)",
    "Tid per kille (sek)","Tid per kille",
    "Klockan","Älskar","Sover med","Känner","Pappans vänner","Grannar",
    "Nils vänner","Nils familj","Totalt Män","Tid kille","Nils",
    "Hångel","Suger","Prenumeranter","Avgift","Intäkter","Intäkt män",
    "Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst","Känner Sammanlagt","Hårdhet"
]

def ensure_header_and_migrate():
    header = _retry_call(sheet.row_values, 1)
    if not header:
        _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
        st.session_state["COLUMNS"] = DEFAULT_COLUMNS
        st.caption("🧱 Skapade kolumnrubriker.")
        return

    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        new_header = header + missing
        end_col_letter = chr(64 + min(len(new_header), 26)) if len(new_header) <= 26 else "ZZ"
        _retry_call(sheet.update, f"A1:{end_col_letter}1", [new_header])
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
KOLUMNER = st.session_state["COLUMNS"]

# ===================================================================
#                      Sidopanel: Inställningar
# ===================================================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

CFG = st.session_state.get("CFG", {})

default_startdatum = _clamp(
    st.session_state.get("CFG", {}).get("startdatum", CFG.get("startdatum", date.today())),
    MIN_START, date(2100,1,1)
)
default_starttid   = st.session_state.get("CFG", {}).get("starttid",   CFG.get("starttid",   time(7, 0)))
default_fod        = _clamp(
    st.session_state.get("CFG", {}).get("födelsedatum", CFG.get("födelsedatum", date(1990,1,1))),
    MIN_FOD, date.today()
)

# Maxvärden (sparas i session + CFG)
def _init_cfg_defaults():
    st.session_state.setdefault("CFG", {})
    st.session_state["CFG"].setdefault("MAX_PAPPAN", 10)
    st.session_state["CFG"].setdefault("MAX_GRANNAR", 10)
    st.session_state["CFG"].setdefault("MAX_NILS_VANNER", 10)
    st.session_state["CFG"].setdefault("MAX_NILS_FAMILJ", 10)

_init_cfg_defaults()
CFG = st.session_state["CFG"]

default_max_p  = int(st.session_state.get("MAX_PAPPAN",      CFG.get("MAX_PAPPAN", 10)))
default_max_g  = int(st.session_state.get("MAX_GRANNAR",     CFG.get("MAX_GRANNAR", 10)))
default_max_nv = int(st.session_state.get("MAX_NILS_VANNER", CFG.get("MAX_NILS_VANNER", 10)))
default_max_nf = int(st.session_state.get("MAX_NILS_FAMILJ", CFG.get("MAX_NILS_FAMILJ", 10)))

startdatum = st.sidebar.date_input("Historiskt startdatum", value=default_startdatum, min_value=MIN_START, key="ui_startdatum")
starttid   = st.sidebar.time_input("Starttid", value=default_starttid, key="ui_starttid")
födelsedatum = st.sidebar.date_input("Malins födelsedatum", value=default_fod, min_value=MIN_FOD, max_value=date.today(), key="ui_födelsedatum")

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
max_p  = st.sidebar.number_input("Max Pappans vänner", min_value=0, step=1, value=default_max_p,  key="ui_MAX_PAPPAN")
max_g  = st.sidebar.number_input("Max Grannar",        min_value=0, step=1, value=default_max_g,  key="ui_MAX_GRANNAR")
max_nv = st.sidebar.number_input("Max Nils vänner",    min_value=0, step=1, value=default_max_nv, key="ui_MAX_NILS_VANNER")
max_nf = st.sidebar.number_input("Max Nils familj",    min_value=0, step=1, value=default_max_nf, key="ui_MAX_NILS_FAMILJ")

if st.sidebar.button("💾 Spara inställningar"):
    st.session_state["CFG"].update({
        "startdatum": startdatum,
        "starttid": starttid,
        "födelsedatum": födelsedatum,
        "MAX_PAPPAN": int(max_p),
        "MAX_GRANNAR": int(max_g),
        "MAX_NILS_VANNER": int(max_nv),
        "MAX_NILS_FAMILJ": int(max_nf),
    })
    st.session_state.MAX_PAPPAN      = int(max_p)
    st.session_state.MAX_GRANNAR     = int(max_g)
    st.session_state.MAX_NILS_VANNER = int(max_nv)
    st.session_state.MAX_NILS_FAMILJ = int(max_nf)
    st.success("Inställningar sparade ✅")

cfg = st.session_state.get("CFG", {})
startdatum   = cfg.get("startdatum", startdatum)
starttid     = cfg.get("starttid", starttid)
födelsedatum = cfg.get("födelsedatum", födelsedatum)

def _init_max(key, default_val):
    if key not in st.session_state:
        st.session_state[key] = int(cfg.get(key, default_val))

_init_max("MAX_PAPPAN",      int(max_p))
_init_max("MAX_GRANNAR",     int(max_g))
_init_max("MAX_NILS_VANNER", int(max_nv))
_init_max("MAX_NILS_FAMILJ", int(max_nf))

# ===================================================================
#                        Radräkning (minimerar reads)
# ===================================================================
def _init_row_count():
    if "ROW_COUNT" not in st.session_state:
        try:
            vals = _retry_call(sheet.col_values, 1)  # kolumn A
            st.session_state.ROW_COUNT = max(0, len(vals) - 1) if (vals and vals[0] == "Veckodag") else len(vals)
        except Exception:
            st.session_state.ROW_COUNT = 0

_init_row_count()

def next_scene_number():
    return st.session_state.ROW_COUNT + 1

def datum_och_veckodag_för_scen(scen_nummer: int):
    d = startdatum + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# ===================================================================
#                          INMATNING (live)
# ===================================================================
st.subheader("➕ Lägg till ny händelse")

män   = st.number_input("Män",   min_value=0, step=1, value=0)
fitta = st.number_input("Fitta", min_value=0, step=1, value=0)
rumpa = st.number_input("Rumpa", min_value=0, step=1, value=0)
dp    = st.number_input("DP",    min_value=0, step=1, value=0)
dpp   = st.number_input("DPP",   min_value=0, step=1, value=0)
dap   = st.number_input("DAP",   min_value=0, step=1, value=0)
tap   = st.number_input("TAP",   min_value=0, step=1, value=0)

tid_s = st.number_input("Tid S (sek)", min_value=0, step=1, value=60)
tid_d = st.number_input("Tid D (sek)", min_value=0, step=1, value=60)
vila  = st.number_input("Vila (sek)",  min_value=0, step=1, value=7)

älskar    = st.number_input("Älskar",                min_value=0, step=1, value=0)
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0)

lbl_p  = f"Pappans vänner (max {st.session_state.MAX_PAPPAN})"
lbl_g  = f"Grannar (max {st.session_state.MAX_GRANNAR})"
lbl_nv = f"Nils vänner (max {st.session_state.MAX_NILS_VANNER})"
lbl_nf = f"Nils familj (max {st.session_state.MAX_NILS_FAMILJ})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")

nils = st.number_input("Nils", min_value=0, step=1, value=0)

# Varningar om > max
if pappans_vänner > st.session_state.MAX_PAPPAN:
    st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {st.session_state.MAX_PAPPAN}</span>", unsafe_allow_html=True)
if grannar > st.session_state.MAX_GRANNAR:
    st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {st.session_state.MAX_GRANNAR}</span>", unsafe_allow_html=True)
if nils_vänner > st.session_state.MAX_NILS_VANNER:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {st.session_state.MAX_NILS_VANNER}</span>", unsafe_allow_html=True)
if nils_familj > st.session_state.MAX_NILS_FAMILJ:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {st.session_state.MAX_NILS_FAMILJ}</span>", unsafe_allow_html=True)

# ===================================================================
#                        LIVE-FÖRHANDSVISNING
# ===================================================================
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

grund_preview = {
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "Älskar": älskar, "Sover med": sover_med,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Nils": nils
}

def _calc_preview(grund):
    try:
        if callable(berakna_radvärden):
            return berakna_radvärden(grund, rad_datum, födelsedatum, starttid)
        else:
            return {}
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview(grund_preview)

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
col1, col2 = st.columns(2)
with col1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
with col2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))  # min:sek
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {starttid})")

# Bonus-info i sidopanelen
try:
    bonus_sec = int(älskar) * 1800 + int(sover_med) * 3600
    st.sidebar.info(f"Tidsbonus (Älskar + Sover med): {_hm_str_from_seconds(bonus_sec)}")
except Exception:
    pass

# ===================================================================
#                   Pending-save & Auto-Max-hantering
# ===================================================================
def _store_pending(grund, scen, rad_datum, veckodag, over_max):
    st.session_state["PENDING_SAVE"] = {
        "grund": grund,
        "scen": scen,
        "rad_datum": str(rad_datum),
        "veckodag": veckodag,
        "over_max": over_max
    }

def _parse_date(d):
    return d if isinstance(d, date) else datetime.strptime(d, "%Y-%m-%d").date()

def _save_row(grund, rad_datum, veckodag):
    # Beräkna igen på serversidan
    try:
        if callable(berakna_radvärden):
            ber = berakna_radvärden(grund, rad_datum, födelsedatum, starttid)
        else:
            st.error("berakningar.py saknas – kan inte spara korrekt.")
            return
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state.ROW_COUNT += 1

    ålder = rad_datum.year - födelsedatum.year - ((rad_datum.month,rad_datum.day)<(födelsedatum.month,födelsedatum.day))
    st.success(f"✅ Rad sparad. Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")

def _apply_auto_max_and_save(pending):
    cfg = st.session_state.get("CFG", {})
    for _, info in pending["over_max"].items():
        new_val = int(info["new_value"])
        st.session_state[info["max_key"]] = new_val
        cfg[info["max_key"]] = new_val
    st.session_state["CFG"] = cfg

    grund = pending["grund"]
    rad_datum = _parse_date(pending["rad_datum"])
    veckodag = pending["veckodag"]
    _save_row(grund, rad_datum, veckodag)

# ===================================================================
#                         Spara (med Auto-Max)
# ===================================================================
save_clicked = st.button("💾 Spara raden")
if save_clicked:
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
        _store_pending(grund_preview, scen, rad_datum, veckodag, over_max)
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# Auto-Max dialog
if "PENDING_SAVE" in st.session_state:
    pending = st.session_state["PENDING_SAVE"]
    st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara raden?")
    for f, info in pending["over_max"].items():
        st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Ja, uppdatera max och spara"):
            try:
                _apply_auto_max_and_save(pending)
            except Exception as e:
                st.error(f"Kunde inte spara: {e}")
            finally:
                st.session_state.pop("PENDING_SAVE", None)
                st.rerun()
    with c2:
        if st.button("✋ Nej, avbryt"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

# ===================================================================
#                         Visa & radera
# ===================================================================
st.subheader("📊 Aktuella data")
try:
    rows = _retry_call(sheet.get_all_records)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Inga datarader ännu.")
except Exception as e:
    st.warning(f"Kunde inte läsa data: {e}")

st.subheader("🗑 Ta bort rad")
try:
    total_rows = st.session_state.ROW_COUNT
    if total_rows > 0:
        idx = st.number_input("Radnummer att ta bort (1 = första dataraden)", min_value=1, max_value=total_rows, step=1, value=1)
        if st.button("Ta bort vald rad"):
            _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 för header
            st.session_state.ROW_COUNT -= 1
            st.success(f"Rad {idx} borttagen.")
            st.rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")
