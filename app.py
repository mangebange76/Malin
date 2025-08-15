import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random
import pandas as pd

# ===================== Import av extern beräkning (om finns) =====================
try:
    # I din berakningar.py ska funktionen heta berakna_radvarden (utan prickar).
    from berakningar import berakna_radvarden as ext_calc_row
except Exception:
    ext_calc_row = None

# ============================== App-inställningar ===============================
st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin-produktionsapp")

# =============================== Hjälpfunktioner ================================
def _retry_call(fn, *args, **kwargs):
    """Exponential backoff för 429/RESOURCE_EXHAUSTED."""
    delay = 0.5
    for _ in range(6):
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

# =============================== Google Sheets =================================
@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

client = get_client()

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket via ID eller URL (ingen Drive-API krävs)."""
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

# =========================== Header-säkring / migration =========================
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

# ================================ Sidopanel ====================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

def _init_cfg_defaults():
    st.session_state.setdefault("CFG", {})
    st.session_state["CFG"].setdefault("startdatum", date.today())
    st.session_state["CFG"].setdefault("starttid", time(7, 0))
    st.session_state["CFG"].setdefault("födelsedatum", date(1990,1,1))
    st.session_state["CFG"].setdefault("MAX_PAPPAN", 10)
    st.session_state["CFG"].setdefault("MAX_GRANNAR", 10)
    st.session_state["CFG"].setdefault("MAX_NILS_VANNER", 10)
    st.session_state["CFG"].setdefault("MAX_NILS_FAMILJ", 10)

_init_cfg_defaults()
CFG = st.session_state["CFG"]

startdatum = st.sidebar.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
starttid   = st.sidebar.time_input("Starttid", value=CFG["starttid"])
födelsedatum = st.sidebar.date_input("Malins födelsedatum", value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
                                     min_value=MIN_FOD, max_value=date.today())

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
max_p  = st.sidebar.number_input("Max Pappans vänner", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
max_g  = st.sidebar.number_input("Max Grannar",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
max_nv = st.sidebar.number_input("Max Nils vänner",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
max_nf = st.sidebar.number_input("Max Nils familj",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))

if st.sidebar.button("💾 Spara inställningar"):
    CFG.update({
        "startdatum": startdatum,
        "starttid": starttid,
        "födelsedatum": födelsedatum,
        "MAX_PAPPAN": int(max_p),
        "MAX_GRANNAR": int(max_g),
        "MAX_NILS_VANNER": int(max_nv),
        "MAX_NILS_FAMILJ": int(max_nf),
    })
    st.session_state.update(
        MAX_PAPPAN=int(max_p),
        MAX_GRANNAR=int(max_g),
        MAX_NILS_VANNER=int(max_nv),
        MAX_NILS_FAMILJ=int(max_nf),
    )
    st.success("Inställningar sparade ✅")

# Se till att max finns i session (för etiketter)
st.session_state.setdefault("MAX_PAPPAN",      int(CFG["MAX_PAPPAN"]))
st.session_state.setdefault("MAX_GRANNAR",     int(CFG["MAX_GRANNAR"]))
st.session_state.setdefault("MAX_NILS_VANNER", int(CFG["MAX_NILS_VANNER"]))
st.session_state.setdefault("MAX_NILS_FAMILJ", int(CFG["MAX_NILS_FAMILJ"]))

# ============================== Radräkning / Scen ==============================
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

# ============================ Inmatning (live-fält) ============================
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

# Varningsflaggor vid överskridna max
if pappans_vänner > st.session_state.MAX_PAPPAN:
    st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {st.session_state.MAX_PAPPAN}</span>", unsafe_allow_html=True)
if grannar > st.session_state.MAX_GRANNAR:
    st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {st.session_state.MAX_GRANNAR}</span>", unsafe_allow_html=True)
if nils_vänner > st.session_state.MAX_NILS_VANNER:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {st.session_state.MAX_NILS_VANNER}</span>", unsafe_allow_html=True)
if nils_familj > st.session_state.MAX_NILS_FAMILJ:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {st.session_state.MAX_NILS_FAMILJ}</span>", unsafe_allow_html=True)

# =========================== Fallback-beräkning (lokal) =========================
def _fallback_calc(grund: dict, rad_datum: date, fod: date, starttid: time) -> dict:
    # Alias
    c = int(grund.get("Män", 0))
    d = int(grund.get("Fitta", 0))
    e = int(grund.get("Rumpa", 0))
    f = int(grund.get("DP", 0))
    g = int(grund.get("DPP", 0))
    h = int(grund.get("DAP", 0))
    i = int(grund.get("TAP", 0))
    j = int(grund.get("Tid S", 0))
    k = int(grund.get("Tid D", 0))
    l = int(grund.get("Vila", 0))
    alskar    = int(grund.get("Älskar", 0))
    sover_med = int(grund.get("Sover med", 0))
    if sover_med < 0: sover_med = 0
    if sover_med > 1: sover_med = 1

    # U = Känner
    u = int(grund.get("Pappans vänner",0)) + int(grund.get("Grannar",0)) + int(grund.get("Nils vänner",0)) + int(grund.get("Nils familj",0))

    # Summor inkl U
    m = (c + d + e + u) * j                 # Summa S (sek)
    n = (f + g + h + u) * k                 # Summa D (sek)
    o = (i + u) * k                         # Summa TP (sek)
    p = (c + d + e + f + g + h + i + u) * l # Summa Vila (sek)

    # Extra tid
    extra_alskar_sec    = alskar * 1800
    extra_sover_med_sec = sover_med * 3600

    # Total tid
    q_sec = m + n + o + p + extra_alskar_sec + extra_sover_med_sec
    q_hours = q_sec / 3600.0

    # Klockan (7 + 3 + q + 1) → HH:MM från starttid
    klockan_str = (
        datetime.combine(rad_datum, starttid)
        + timedelta(hours=3)
        + timedelta(hours=q_hours)
        + timedelta(hours=1)
    ).strftime("%H:%M")

    # Totalt män Z = Män + U (exkl. älskar / sover med)
    z = u + c
    z_safe = z if z > 0 else 1

    # Tid per kille (sek): M/Z + N/(Z*2) + O/(Z*3)
    if z > 0:
        tid_per_kille_sec = int(round(m / z + n / (z * 2) + o / (z * 3)))
    else:
        tid_per_kille_sec = 0

    # Övrig ekonomi (som tidigare)
    ac = 10800 / max(c, 1)   # Hångel
    ad = (n * 0.65) / z_safe # Suger
    ae = (c + d + e + f + g + h + i + u)  # Prenumeranter
    af = 15
    ag = ae * af
    ah = c * 120

    # Ålder + lön
    alder = rad_datum.year - fod.year - ((rad_datum.month,rad_datum.day) < (fod.month,fod.day))
    if alder < 18:
        raise ValueError("Ålder < 18 — spärrad rad.")
    if   18 <= alder <= 25: faktor = 1.20
    elif 26 <= alder <= 30: faktor = 1.10
    elif 31 <= alder <= 40: faktor = 1.00
    else:                    faktor = 0.90
    aj_base = max(150, min(800, ae * 0.10))
    aj = max(150, min(800, aj_base * faktor))

    ai = (aj + 120) * u
    ak = ag * 0.20
    al = ag - ah - ai - aj - ak
    hardhet = (2 if f > 0 else 0) + (3 if g > 0 else 0) + (5 if h > 0 else 0) + (7 if i > 0 else 0)

    return {
        **grund,
        "Känner": u,
        "Summa S": m, "Summa D": n, "Summa TP": o, "Summa Vila": p,
        "Tid Älskar (sek)": extra_alskar_sec, "Tid Älskar": _hm_str_from_seconds(extra_alskar_sec),
        "Tid Sover med (sek)": extra_sover_med_sec, "Tid Sover med": _hm_str_from_seconds(extra_sover_med_sec),
        "Summa tid (sek)": q_sec, "Summa tid": _hm_str_from_seconds(q_sec),
        "Klockan": klockan_str,
        "Totalt Män": z,
        "Tid per kille (sek)": tid_per_kille_sec, "Tid per kille": _ms_str_from_seconds(tid_per_kille_sec),
        "Tid kille": ((m / z_safe) + (n / z_safe) + (o / z_safe) + ad) / 60,
        "Hångel": ac, "Suger": ad, "Prenumeranter": ae, "Avgift": af, "Intäkter": ag, "Intäkt män": ah,
        "Intäkt Känner": ai, "Lön Malin": aj, "Intäkt Företaget": ak, "Vinst": al, "Känner Sammanlagt": u, "Hårdhet": hardhet
    }

def _calc_row(grund, rad_datum, fod, starttid):
    """Använd extern beräkning om den finns & returnerar nycklarna, annars fallback."""
    if callable(ext_calc_row):
        try:
            out = ext_calc_row(grund, rad_datum, fod, starttid)
            # Säkerställ kritiska nycklar – fyll i via fallback om något saknas
            must_keys = ["Summa tid (sek)","Summa tid","Tid per kille (sek)","Tid per kille","Totalt Män","Klockan",
                         "Summa S","Summa D","Summa TP","Summa Vila","Känner"]
            if any(k not in out for k in must_keys):
                fb = _fallback_calc(grund, rad_datum, fod, starttid)
                out = {**fb, **out}
            return out
        except Exception as e:
            st.warning(f"Extern beräkning kastade fel ({e}). Använder fallback.")
            return _fallback_calc(grund, rad_datum, fod, starttid)
    else:
        return _fallback_calc(grund, rad_datum, fod, starttid)

# ============================== Förhandsberäkning ===============================
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

try:
    preview = _calc_row(grund_preview, rad_datum, födelsedatum, starttid)
except Exception as e:
    st.warning(f"Förhandsberäkning misslyckades: {e}")
    preview = {}

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

# ============================== Spara / Auto-Max ================================
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
    try:
        ber = _calc_row(grund, rad_datum, födelsedatum, starttid)
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

# ================================ Visa & radera ================================
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
