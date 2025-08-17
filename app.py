import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random
import math

# ===================== Import av extern beräkning =====================
try:
    from berakningar import berakna_radvarden as calc_row_values
except Exception:
    calc_row_values = None

# ============================== App-inställningar ===============================
st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin – produktionsapp")

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

def _parse_iso_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _usd(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "-"

# =============================== Google Sheets =================================
@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

client = get_client()
WORKSHEET_TITLE = "Data"
CONFIG_SHEET = "Config"

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket via ID eller URL och hämta bladet 'Data'."""
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        st.caption("🔗 Öppnar via GOOGLE_SHEET_ID…")
        sh = _retry_call(client.open_by_key, sid)
        return sh.worksheet(WORKSHEET_TITLE)

    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        st.caption("🔗 Öppnar via SHEET_URL…")
        sh = _retry_call(client.open_by_url, url)
        return sh.worksheet(WORKSHEET_TITLE)

    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        st.caption("🔎 Öppnar via query-param 'sheet'…")
        sh = _retry_call(client.open_by_url, qp) if qp.startswith("http") else _retry_call(client.open_by_key, qp)
        return sh.worksheet(WORKSHEET_TITLE)

    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

def _open_spreadsheet():
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if sid:
        return _retry_call(client.open_by_key, sid)
    if url:
        return _retry_call(client.open_by_url, url)
    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        return _retry_call(client.open_by_url, qp) if qp.startswith("http") else _retry_call(client.open_by_key, qp)
    st.error("Kunde inte öppna Spreadsheet – saknar ID/URL.")
    st.stop()

sheet = resolve_sheet()

# =========================== Config-flik =======================================
def _ensure_config_sheet():
    ss = _open_spreadsheet()
    try:
        ws = ss.worksheet(CONFIG_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=CONFIG_SHEET, rows=200, cols=3)
        ws.update("A1:C1", [["Key", "Value", "Label"]])
    return ws

def _config_as_dict():
    ws = _ensure_config_sheet()
    rows = ws.get_all_records()
    d = {}
    for r in rows:
        key = (r.get("Key") or "").strip()
        val = (r.get("Value") or "").strip()
        lbl = (r.get("Label") or "").strip()
        if key:
            d[key] = {"value": val, "label": lbl}
    return d

def _save_config_value(key: str, value, label: str = ""):
    ws = _ensure_config_sheet()
    rows = ws.get_all_records()
    found_row = None
    for idx, r in enumerate(rows, start=2):
        if (r.get("Key") or "").strip() == key:
            found_row = idx
            break
    if found_row:
        ws.update(f"A{found_row}:C{found_row}", [[key, str(value), label]])
    else:
        ws.append_row([key, str(value), label])

def _inc_config_value(key: str, delta: int):
    cur = int(_config_as_dict().get(key,{}).get("value") or 0)
    _save_config_value(key, cur + int(delta))

def _load_cfg():
    defaults = {
        "startdatum": date.today().isoformat(),
        "starttid": "07:00:00",
        "födelsedatum": date(1990,1,1).isoformat(),
        "MAX_PAPPAN": "10",
        "MAX_GRANNAR": "10",
        "MAX_NILS_VANNER": "10",
        "MAX_NILS_FAMILJ": "10",
        "MAX_BEKANTA": "10",
        "avgift_usd": "30.0",
        # Bonus-pool
        "BONUS_TOTAL": "0",
        "BONUS_USED": "0",
        "BONUS_JOB_USED": "0",
        # Etiketter
        "LBL_PAPPAN": "Pappans vänner",
        "LBL_GRANNAR": "Grannar",
        "LBL_NILS_VANNER": "Nils vänner",
        "LBL_NILS_FAMILJ": "Nils familj",
        "LBL_BEKANTA": "Bekanta",
        "LBL_ESK": "Eskilstuna killar",
        "LBL_FOD": "Malins födelsedatum",
    }
    existing = _config_as_dict()
    for k, v in defaults.items():
        if k not in existing or (existing[k].get("value") or "") == "":
            _save_config_value(k, v, existing.get(k,{}).get("label",""))

    existing = _config_as_dict()
    merged = {k: existing[k]["value"] for k in defaults.keys()}

    labels = {
        "PAPPAN": (existing.get("LBL_PAPPAN",{}).get("label") or "Pappans vänner"),
        "GRANNAR": (existing.get("LBL_GRANNAR",{}).get("label") or "Grannar"),
        "NILS_VANNER": (existing.get("LBL_NILS_VANNER",{}).get("label") or "Nils vänner"),
        "NILS_FAMILJ": (existing.get("LBL_NILS_FAMILJ",{}).get("label") or "Nils familj"),
        "BEKANTA": (existing.get("LBL_BEKANTA",{}).get("label") or "Bekanta"),
        "ESK": (existing.get("LBL_ESK",{}).get("label") or "Eskilstuna killar"),
        "FOD": (existing.get("LBL_FOD",{}).get("label") or "Malins födelsedatum"),
    }
    return merged, labels

CFG_STR, LABELS = _load_cfg()

# typed versions
CFG = {
    "startdatum": _parse_iso_date(CFG_STR["startdatum"]) or date.today(),
    "starttid": datetime.strptime(CFG_STR["starttid"], "%H:%M:%S").time(),
    "födelsedatum": _parse_iso_date(CFG_STR["födelsedatum"]) or date(1990,1,1),
    "MAX_PAPPAN": int(CFG_STR["MAX_PAPPAN"]),
    "MAX_GRANNAR": int(CFG_STR["MAX_GRANNAR"]),
    "MAX_NILS_VANNER": int(CFG_STR["MAX_NILS_VANNER"]),
    "MAX_NILS_FAMILJ": int(CFG_STR["MAX_NILS_FAMILJ"]),
    "MAX_BEKANTA": int(CFG_STR["MAX_BEKANTA"]),
    "avgift_usd": float(CFG_STR["avgift_usd"]),
    "BONUS_TOTAL": int(CFG_STR["BONUS_TOTAL"]),
    "BONUS_USED": int(CFG_STR["BONUS_USED"]),
    "BONUS_JOB_USED": int(CFG_STR["BONUS_JOB_USED"]),
}

# =========================== Header-säkring / migration =========================
DEFAULT_COLUMNS = [
    "Datum",
    "Typ",
    "Veckodag","Scen",
    "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
    "Summa S","Summa D","Summa TP","Summa Vila",
    "Tid Älskar (sek)","Tid Älskar",
    "Tid Sover med (sek)","Tid Sover med",
    "Summa tid","Summa tid (sek)",
    "Tid per kille (sek)","Tid per kille",
    "Klockan","Älskar","Sover med","Känner",
    "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar",
    "Bonus tilldelade",
    "Totalt Män","Tid kille","Nils",
    "Hångel (sek/kille)","Hångel (m:s/kille)",
    "Suger","Suger per kille (sek)",
    "Hårdhet","Prenumeranter","Avgift","Intäkter",
    "Intäkt män","Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst",
    "Känner Sammanlagt"
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
        end_col_letter = "ZZ" if len(new_header) > 26 else chr(64 + len(new_header))
        _retry_call(sheet.update, f"A1:{end_col_letter}1", [new_header])
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
KOLUMNER = st.session_state["COLUMNS"]

# ===== Meny =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# =============================== STATISTIKVY ================================
if view == "Statistik":
    st.header("📊 Statistik")
    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # Antal scener definieras som rader där (män + esk + bonus + bekanta + källor) > 0
    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man = 0
    summa_for_snitt_scener = 0
    summa_privat_gb_kanner = 0
    total_svarta_sum = 0
    total_men_like_sum = 0

    for r in rows:
        man = _safe_int(r.get("Män", 0), 0)
        esk = _safe_int(r.get("Eskilstuna killar", 0), 0)
        bonus_row = _safe_int(r.get("Bonus tilldelade", 0), 0)
        bekanta = _safe_int(r.get("Bekanta", 0), 0)
        p = _safe_int(r.get("Pappans vänner", 0), 0)
        g = _safe_int(r.get("Grannar", 0), 0)
        nv = _safe_int(r.get("Nils vänner", 0), 0)
        nf = _safe_int(r.get("Nils familj", 0), 0)
        kanner = _safe_int(r.get("Känner", 0), 0)
        svarta = _safe_int(r.get("Svarta", 0), 0)

        men_like = man + esk + bonus_row + bekanta + p + g + nv + nf  # allt räknas som "män" i totals
        men_like_plus_black = men_like + svarta

        if men_like > 0:
            antal_scener += 1
            totalt_man += men_like
            summa_for_snitt_scener += (men_like + kanner)
        if men_like == 0 and kanner > 0:
            privat_gb_cnt += 1
            summa_privat_gb_kanner += kanner

        total_svarta_sum += svarta
        total_men_like_sum += men_like_plus_black

    snitt_scener = round(summa_for_snitt_scener / antal_scener, 2) if antal_scener > 0 else 0.0
    snitt_privat_gb = round(summa_privat_gb_kanner / privat_gb_cnt, 2) if privat_gb_cnt > 0 else 0.0
    andel_svarta_pct = round((total_svarta_sum / total_men_like_sum) * 100, 2) if total_men_like_sum > 0 else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Antal scener", antal_scener)
    with c2: st.metric("Privat GB", privat_gb_cnt)
    with c3: st.metric("Totalt antal män", totalt_man)
    with c4: st.metric("Snitt scener", snitt_scener)
    with c5: st.metric("Snitt Privat GB", snitt_privat_gb)
    st.metric("Andel svarta av män (%)", andel_svarta_pct)

    # Visa bonus-status (totalt, deltagit, kvar)
    cfg_now = _config_as_dict()
    bonus_total = int(cfg_now.get("BONUS_TOTAL",{}).get("value") or 0)
    bonus_used  = int(cfg_now.get("BONUS_USED",{}).get("value") or 0)
    bonus_left  = max(0, bonus_total - bonus_used)
    b1, b2, b3 = st.columns(3)
    with b1: st.metric("Bonus killar – totalt", bonus_total)
    with b2: st.metric("Bonus killar – deltagit", bonus_used)
    with b3: st.metric("Bonus killar – kvar", bonus_left)

    st.stop()

# ================================ Sidopanel (Produktion) ====================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

def _init_cfg_defaults():
    st.session_state.setdefault("CFG", {})
    st.session_state["CFG"]["startdatum"]    = _parse_iso_date(_config_as_dict().get("startdatum",{}).get("value") or date.today().isoformat())
    st.session_state["CFG"]["starttid"]      = datetime.strptime((_config_as_dict().get("starttid",{}).get("value") or "07:00:00"), "%H:%M:%S").time()
    st.session_state["CFG"]["födelsedatum"]  = _parse_iso_date(_config_as_dict().get("födelsedatum",{}).get("value") or date(1990,1,1).isoformat())
    st.session_state["CFG"]["MAX_PAPPAN"]    = int(_config_as_dict().get("MAX_PAPPAN",{}).get("value") or 10)
    st.session_state["CFG"]["MAX_GRANNAR"]   = int(_config_as_dict().get("MAX_GRANNAR",{}).get("value") or 10)
    st.session_state["CFG"]["MAX_NILS_VANNER"]=int(_config_as_dict().get("MAX_NILS_VANNER",{}).get("value") or 10)
    st.session_state["CFG"]["MAX_NILS_FAMILJ"]=int(_config_as_dict().get("MAX_NILS_FAMILJ",{}).get("value") or 10)
    st.session_state["CFG"]["MAX_BEKANTA"]   = int(_config_as_dict().get("MAX_BEKANTA",{}).get("value") or 10)
    st.session_state["CFG"]["avgift_usd"]    = float(_config_as_dict().get("avgift_usd",{}).get("value") or 30.0)

_init_cfg_defaults()
CFG = st.session_state["CFG"]

# Etiketter
st.sidebar.subheader("Etiketter (visar överallt)")
lbl_pappan = st.sidebar.text_input("Etikett – Pappans vänner", value=LABELS["PAPPAN"])
lbl_grann  = st.sidebar.text_input("Etikett – Grannar", value=LABELS["GRANNAR"])
lbl_nv     = st.sidebar.text_input("Etikett – Nils vänner", value=LABELS["NILS_VANNER"])
lbl_nf     = st.sidebar.text_input("Etikett – Nils familj", value=LABELS["NILS_FAMILJ"])
lbl_bk     = st.sidebar.text_input("Etikett – Bekanta", value=LABELS["BEKANTA"])
lbl_esk    = st.sidebar.text_input("Etikett – Eskilstuna killar", value=LABELS["ESK"])
lbl_fod    = st.sidebar.text_input("Etikett – Malins födelsedatum", value=LABELS["FOD"])

startdatum = st.sidebar.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
starttid   = st.sidebar.time_input("Starttid", value=CFG["starttid"])
födelsedatum = st.sidebar.date_input(lbl_fod, value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
                                     min_value=MIN_FOD, max_value=date.today())

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
max_p  = st.sidebar.number_input(f"Max {lbl_pappan}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
max_g  = st.sidebar.number_input(f"Max {lbl_grann}",  min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
max_nv = st.sidebar.number_input(f"Max {lbl_nv}",     min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
max_nf = st.sidebar.number_input(f"Max {lbl_nf}",     min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
max_bk = st.sidebar.number_input(f"Max {lbl_bk}",     min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

st.sidebar.subheader("Pris per prenumerant (gäller NÄSTA rad)")
avgift_input = st.sidebar.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

if st.sidebar.button("💾 Spara inställningar & etiketter"):
    _save_config_value("startdatum", startdatum.isoformat())
    _save_config_value("starttid", datetime.combine(date.today(), starttid).strftime("%H:%M:%S"))
    _save_config_value("födelsedatum", födelsedatum.isoformat())
    _save_config_value("MAX_PAPPAN", int(max_p), label=lbl_pappan)
    _save_config_value("MAX_GRANNAR", int(max_g), label=lbl_grann)
    _save_config_value("MAX_NILS_VANNER", int(max_nv), label=lbl_nv)
    _save_config_value("MAX_NILS_FAMILJ", int(max_nf), label=lbl_nf)
    _save_config_value("MAX_BEKANTA", int(max_bk), label=lbl_bk)
    _save_config_value("avgift_usd", float(avgift_input))
    _save_config_value("LBL_PAPPAN", "", label=lbl_pappan)
    _save_config_value("LBL_GRANNAR", "", label=lbl_grann)
    _save_config_value("LBL_NILS_VANNER", "", label=lbl_nv)
    _save_config_value("LBL_NILS_FAMILJ", "", label=lbl_nf)
    _save_config_value("LBL_BEKANTA", "", label=lbl_bk)
    _save_config_value("LBL_ESK", "", label=lbl_esk)
    _save_config_value("LBL_FOD", "", label=lbl_fod)
    st.success("Inställningar & etiketter sparade ✅")
    st.rerun()

# Se till att max finns i session (för etiketter)
st.session_state.setdefault("MAX_PAPPAN",      int(max_p))
st.session_state.setdefault("MAX_GRANNAR",     int(max_g))
st.session_state.setdefault("MAX_NILS_VANNER", int(max_nv))
st.session_state.setdefault("MAX_NILS_FAMILJ", int(max_nf))
st.session_state.setdefault("MAX_BEKANTA",     int(max_bk))

# ===== 30 dagar (rullande) i sidopanelen =====
st.sidebar.subheader("📆 30 dagar (rullande)")
try:
    all_rows = _retry_call(sheet.get_all_records)
    cutoff = date.today() - timedelta(days=30)
    active_subs = 0.0
    active_rev = 0.0
    for r in all_rows:
        typ = (r.get("Typ") or "").strip()
        if typ in ("Vila på jobbet", "Vila i hemmet"):
            continue  # exkludera helt
        d = _parse_iso_date(r.get("Datum", ""))
        if not d or d < cutoff:
            continue
        subs = float(r.get("Prenumeranter", 0) or 0)
        fee  = float(r.get("Avgift", CFG["avgift_usd"]) or 0)
        active_subs += subs
        active_rev  += subs * fee
    st.sidebar.metric("Aktiva prenumeranter", int(active_subs))
    st.sidebar.metric("Intäkter (30 dagar)", f"${active_rev:,.2f}")
except Exception as e:
    st.sidebar.warning(f"Kunde inte räkna 30-dagars: {e}")

# ============================== Radräkning / Scen ==============================
def _init_row_count():
    if "ROW_COUNT" not in st.session_state:
        try:
            vals = _retry_call(sheet.col_values, 1)  # kolumn A = Datum
            st.session_state.ROW_COUNT = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
        except Exception:
            st.session_state.ROW_COUNT = 0
_init_row_count()

def next_scene_number():
    return st.session_state.ROW_COUNT + 1

def datum_och_veckodag_för_scen(scen_nummer: int):
    d = CFG["startdatum"] + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# ============================ Inmatning (live-fält) ============================
st.subheader("➕ Lägg till ny händelse")

män    = st.number_input("Män",    min_value=0, step=1, value=0)
svarta = st.number_input("Svarta", min_value=0, step=1, value=0)
fitta  = st.number_input("Fitta",  min_value=0, step=1, value=0)
rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=0)
dp     = st.number_input("DP",     min_value=0, step=1, value=0)
dpp    = st.number_input("DPP",    min_value=0, step=1, value=0)
dap    = st.number_input("DAP",    min_value=0, step=1, value=0)
tap    = st.number_input("TAP",    min_value=0, step=1, value=0)

tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=60)
tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=60)
vila   = st.number_input("Vila (sek)",  min_value=0, step=1, value=7)

dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=60)
dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=3)

älskar    = st.number_input("Älskar",                min_value=0, step=1, value=0)
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0)

lbl_p  = f"{lbl_pappan} (max {st.session_state.MAX_PAPPAN})"
lbl_g  = f"{lbl_grann} (max {st.session_state.MAX_GRANNAR})"
lbl_nv2 = f"{lbl_nv} (max {st.session_state.MAX_NILS_VANNER})"
lbl_nf2 = f"{lbl_nf} (max {st.session_state.MAX_NILS_FAMILJ})"
lbl_bk2 = f"{lbl_bk} (max {st.session_state.MAX_BEKANTA})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
nils_vänner    = st.number_input(lbl_nv2, min_value=0, step=1, value=0, key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf2, min_value=0, step=1, value=0, key="input_nils_familj")
bekanta        = st.number_input(lbl_bk2, min_value=0, step=1, value=0, key="input_bekanta")

eskilstuna_killar = st.number_input(lbl_esk, min_value=0, step=1, value=0, key="input_eskilstuna")

nils = st.number_input("Nils", min_value=0, step=1, value=0)

# Varningsflaggor vid överskridna max (gäller inte Eskilstuna killar)
if pappans_vänner > st.session_state.MAX_PAPPAN:
    st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {st.session_state.MAX_PAPPAN}</span>", unsafe_allow_html=True)
if grannar > st.session_state.MAX_GRANNAR:
    st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {st.session_state.MAX_GRANNAR}</span>", unsafe_allow_html=True)
if nils_vänner > st.session_state.MAX_NILS_VANNER:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {st.session_state.MAX_NILS_VANNER}</span>", unsafe_allow_html=True)
if nils_familj > st.session_state.MAX_NILS_FAMILJ:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {st.session_state.MAX_NILS_FAMILJ}</span>", unsafe_allow_html=True)
if bekanta > st.session_state.MAX_BEKANTA:
    st.markdown(f"<span style='color:#d00'>⚠️ {bekanta} > max {st.session_state.MAX_BEKANTA}</span>", unsafe_allow_html=True)

# ============================ Live-förhandsberäkning ===========================
def next_scene_dict():
    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)
    return scen, rad_datum, veckodag

scen, rad_datum, veckodag = next_scene_dict()

grund_preview = {
    "Typ": "",
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
    "Älskar": älskar, "Sover med": sover_med,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
    "Bonus tilldelade": 0,
    "Nils": nils,
    "Avgift": float(CFG["avgift_usd"]),
}

def _calc_preview(grund):
    try:
        if callable(calc_row_values):
            return calc_row_values(grund, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        else:
            st.error("Hittar inte berakningar.py eller berakna_radvarden().")
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
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with col2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

# ===== Prenumeranter & Ekonomi (live) =====
st.markdown("#### 📈 Prenumeranter & Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Kostnad män", _usd(preview.get("Intäkt män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Intäkt Företaget", _usd(preview.get("Intäkt Företaget", 0)))
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ============================== Spara / Auto-Max ================================
def _store_pending(grund, scen, rad_datum, veckodag, over_max):
    st.session_state["PENDING_SAVE"] = {
        "grund": grund,
        "scen": scen,
        "rad_datum": str(rad_datum),
        "veckodag": veckodag,
        "over_max": over_max
    }

def _parse_date_for_save(d):
    return d if isinstance(d, date) else datetime.strptime(d, "%Y-%m-%d").date()

def _add_bonus_to_pool_from_row(ber: dict):
    # 5% chans per prenumerant att bli bonus
    subs = int(float(ber.get("Prenumeranter", 0) or 0))
    bonus_new = 0
    for _ in range(subs):
        if random.random() < 0.05:
            bonus_new += 1
    if bonus_new > 0:
        _inc_config_value("BONUS_TOTAL", bonus_new)
    ber["Bonus killar"] = bonus_new  # ej i header, men lagras ej; poolen uppdateras separat

def _save_row(grund, rad_datum, veckodag):
    try:
        base = dict(grund)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    # Uppdatera bonus-pool baserat på prenumeranter på denna rad
    _add_bonus_to_pool_from_row(ber)

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state.ROW_COUNT += 1

    ålder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month,rad_datum.day)<(CFG["födelsedatum"].month,CFG["födelsedatum"].day))
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")

def _apply_auto_max_and_save(pending):
    # uppdatera max i Config om över
    for _, info in pending["over_max"].items():
        new_val = int(info["new_value"])
        _save_config_value(info["max_key"], new_val)
        st.session_state[info["max_key"]] = new_val

    grund = pending["grund"]
    rad_datum = _parse_date_for_save(pending["rad_datum"])
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
    if bekanta > st.session_state.MAX_BEKANTA:
        over_max["Bekanta"] = {"current_max": st.session_state.MAX_BEKANTA, "new_value": bekanta, "max_key": "MAX_BEKANTA"}

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

# ============================== Snabbåtgärder ===============================
st.markdown("---")
st.subheader("🛠️ Snabbåtgärder")

def _rand_40_60_of_max(mx: int) -> int:
    try:
        mx = int(mx)
    except Exception:
        mx = 0
    if mx <= 0:
        return 0
    lo = max(0, int(round(mx * 0.40)))
    hi = max(lo, int(round(mx * 0.60)))
    import random as _r
    return _r.randint(lo, hi)

def _rand_eskilstuna_20_40() -> int:
    r = random.random()
    if r < 0.30:
        return random.randint(20, 30)
    else:
        return random.randint(31, 40)

def _bonus_left_cfg():
    cfg = _config_as_dict()
    total = int(cfg.get("BONUS_TOTAL",{}).get("value") or 0)
    used  = int(cfg.get("BONUS_USED",{}).get("value") or 0)
    return max(0, total - used), total, used, int(cfg.get("BONUS_JOB_USED",{}).get("value") or 0)

# --- Vila på jobbet ---
if st.button("➕ Skapa 'Vila på jobbet'-rad"):
    try:
        scen_num = next_scene_number()
        rad_datum2, veckodag2 = datum_och_veckodag_för_scen(scen_num)

        pv = _rand_40_60_of_max(st.session_state.get("MAX_PAPPAN", 0))
        gr = _rand_40_60_of_max(st.session_state.get("MAX_GRANNAR", 0))
        nv = _rand_40_60_of_max(st.session_state.get("MAX_NILS_VANNER", 0))
        nf = _rand_40_60_of_max(st.session_state.get("MAX_NILS_FAMILJ", 0))
        bk = _rand_40_60_of_max(st.session_state.get("MAX_BEKANTA", 0))
        esk = _rand_eskilstuna_20_40()

        # BONUS: använd upp till 40% av total i "jobbet"
        left, total, used, job_used = _bonus_left_cfg()
        target_job_total = int(math.floor(total * 0.40))
        remaining_for_job = max(0, target_job_total - job_used)
        bonus_allocate = min(left, remaining_for_job)

        grund_vila = {
            "Typ": "Vila på jobbet",
            "Veckodag": veckodag2, "Scen": scen_num,
            "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
            "Tid S": 0, "Tid D": 0, "Vila": 0,
            "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
            "Älskar": 12, "Sover med": 1,
            "Pappans vänner": pv, "Grannar": gr,
            "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
            "Bonus tilldelade": bonus_allocate,
            "Nils": 0,
            "Avgift": float(CFG.get("avgift_usd", 30.0)),
        }

        # spara rad
        def _save_and_update_bonus_job():
            _save_row(grund_vila, rad_datum2, veckodag2)
            if bonus_allocate > 0:
                _inc_config_value("BONUS_USED", bonus_allocate)
                _inc_config_value("BONUS_JOB_USED", bonus_allocate)
        _save_and_update_bonus_job()

    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

# --- Vila i hemmet (7 rader) ---
if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
    try:
        start_scene = next_scene_number()

        # Bestäm Nils (dag 1–6: 0/1; dag 7=0) – behåll tidigare logik 50/45/5
        r = random.random()
        if r < 0.50:
            ones_count = 0
        elif r < 0.95:
            ones_count = 1
        else:
            ones_count = 2
        nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

        # BONUS: allt kvar fördelas dag 1–5
        left, total, used, job_used = _bonus_left_cfg()
        # allt kvar (oavsett om 40% redan nyttjats) fördelas jämnt över dag 1–5
        per_day_bonus = left // 5
        remainder = left % 5

        for offset in range(7):
            scen_num = start_scene + offset
            rad_d, veckod = datum_och_veckodag_för_scen(scen_num)

            if offset <= 4:
                pv = _rand_40_60_of_max(st.session_state.get("MAX_PAPPAN", 0))
                gr = _rand_40_60_of_max(st.session_state.get("MAX_GRANNAR", 0))
                nv = _rand_40_60_of_max(st.session_state.get("MAX_NILS_VANNER", 0))
                nf = _rand_40_60_of_max(st.session_state.get("MAX_NILS_FAMILJ", 0))
                bk = _rand_40_60_of_max(st.session_state.get("MAX_BEKANTA", 0))
                esk = _rand_eskilstuna_20_40()
                # bonus denna dag
                bonus_today = per_day_bonus + (1 if offset < remainder else 0)
            else:
                pv = gr = nv = nf = bk = 0
                esk = _rand_eskilstuna_20_40()
                bonus_today = 0

            sv = 1 if offset == 6 else 0

            if offset == 6:
                nils_val = 0
            else:
                nils_val = 1 if offset in nils_one_offsets else 0

            grund_home = {
                "Typ": "Vila i hemmet",
                "Veckodag": veckod, "Scen": scen_num,
                "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
                "Tid S": 0, "Tid D": 0, "Vila": 0,
                "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
                "Älskar": 6, "Sover med": sv,
                "Pappans vänner": pv, "Grannar": gr,
                "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
                "Bonus tilldelade": bonus_today,
                "Nils": nils_val,
                "Avgift": float(CFG.get("avgift_usd", 30.0)),
            }
            _save_row(grund_home, rad_d, veckod)

        # Efter 7 dagar: all bonus som just delats ut räknas som använd
        if left > 0:
            _inc_config_value("BONUS_USED", left)

        st.success("✅ Skapade 7 'Vila i hemmet'-rader och fördelade bonus-killar på dag 1–5.")
    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila i hemmet': {e}")

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
