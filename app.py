# ============================== app.py (DEL 1/6) ==============================
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random
import functools

# ---------- extern beräkning ----------
try:
    from berakningar import berakna_radvarden as calc_row_values
except Exception:
    calc_row_values = None

st.set_page_config(page_title="Malin – produktionsapp", layout="centered")
st.title("Malin – produktionsapp")

# =============================== Hjälpfunktioner ===============================
def _retry_call(fn, *args, **kwargs):
    """Exponential backoff för 429/RESOURCE_EXHAUSTED."""
    delay = 0.5
    for _ in range(6):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if any(x in msg for x in ("429", "RESOURCE_EXHAUSTED", "RATE_LIMIT_EXCEEDED")):
                _time.sleep(delay + random.uniform(0, 0.25))
                delay = min(delay * 2, 4)
                continue
            raise
    return fn(*args, **kwargs)

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

# =============================== Google Sheets (LAZY) ==========================
WORKSHEET_TITLE = "Data"
SETTINGS_SHEET  = "Inställningar"

@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def resolve_spreadsheet():
    client = get_client()
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        return _retry_call(client.open_by_key, sid)
    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        return _retry_call(client.open_by_url, url)
    # tillåt query-param ?sheet=
    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        return _retry_call(client.open_by_url, qp) if qp.startswith("http") else _retry_call(client.open_by_key, qp)
    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

@functools.lru_cache(maxsize=1)
def _lazy_sheet_and_settings():
    """Skapa/hämta blad bara när vi verkligen behöver dem."""
    ss = resolve_spreadsheet()
    try:
        sheet = ss.worksheet(WORKSHEET_TITLE)
    except gspread.WorksheetNotFound:
        sheet = ss.add_worksheet(title=WORKSHEET_TITLE, rows=2000, cols=80)
    try:
        settings = ss.worksheet(SETTINGS_SHEET)
    except gspread.WorksheetNotFound:
        settings = ss.add_worksheet(title=SETTINGS_SHEET, rows=200, cols=3)
        _retry_call(settings.update, "A1:C1", [["Key","Value","Label"]])
        defaults = [
            ["startdatum", date.today().isoformat(), ""],
            ["starttid", "07:00", ""],
            ["födelsedatum", date(1990,1,1).isoformat(), "Malins födelsedatum"],

            ["MAX_PAPPAN", "10", "Pappans vänner"],
            ["MAX_GRANNAR", "10", "Grannar"],
            ["MAX_NILS_VANNER", "10", "Nils vänner"],
            ["MAX_NILS_FAMILJ", "10", "Nils familj"],
            ["MAX_BEKANTA", "10", "Bekanta"],

            ["avgift_usd", "30.0", "Avgift (USD, per rad)"],

            # Produktionspersonal total + procentsats för deltagit
            ["PROD_STAFF", "800", "Produktionspersonal (fast)"],
            ["PROD_PCT", "10", "Andel personal som deltar (%)"],

            # Eskilstuna intervall (standard 20–40)
            ["ESK_MIN", "20", "Eskilstuna killar (min)"],
            ["ESK_MAX", "40", "Eskilstuna killar (max)"],

            # Bonusräknare (persistenta totals)
            ["BONUS_TOTAL", "0", "Bonus killar totalt"],
            ["BONUS_USED",  "0", "Bonus killar deltagit"],
            ["BONUS_LEFT",  "0", "Bonus killar kvar"],

            # Etiketter (visningsoverride)
            ["LABEL_Pappans vänner", "", ""],
            ["LABEL_Grannar", "", ""],
            ["LABEL_Nils vänner", "", ""],
            ["LABEL_Nils familj", "", ""],
            ["LABEL_Bekanta", "", ""],
            ["LABEL_Eskilstuna killar", "", ""],
            ["LABEL_Män", "", ""],
            ["LABEL_Svarta", "", ""],
            ["LABEL_Känner", "", ""],
            ["LABEL_Personal deltagit", "", ""],
            ["LABEL_Bonus killar", "", ""],
            ["LABEL_Bonus deltagit", "", ""],
            ["LABEL_Malins födelsedatum", "", ""],
        ]
        _retry_call(settings.update, f"A2:C{len(defaults)+1}", defaults)
    return sheet, settings

def get_sheet():
    sh, _ = _lazy_sheet_and_settings()
    return sh

def get_settings_ws():
    _, ws = _lazy_sheet_and_settings()
    return ws

# ============================== Inställningar (Key/Value/Label) ================
def _settings_as_dict():
    """Läs 'Inställningar' (Key/Value/Label) -> (CFG_RAW, LABELS). Körs lazily vid första behov."""
    recs = _retry_call(get_settings_ws().get_all_records)
    d, labels = {}, {}
    for r in recs:
        key = (r.get("Key") or "").strip()
        if not key:
            continue
        d[key] = r.get("Value")
        if r.get("Label") is not None:
            labels[key] = str(r.get("Label"))
        if key.startswith("LABEL_"):
            cname = key[len("LABEL_"):]
            if str(r.get("Value") or "").strip():
                labels[cname] = str(r.get("Value")).strip()
    return d, labels

def _save_setting(key: str, value: str, label: str|None=None):
    """Skriv/uppdatera en rad i 'Inställningar'."""
    ws = get_settings_ws()
    recs = _retry_call(ws.get_all_records)
    keys = [(r.get("Key") or "") for r in recs]
    try:
        idx = keys.index(key)
        rowno = idx + 2
    except ValueError:
        rowno = len(recs) + 2
        _retry_call(ws.update, f"A{rowno}:C{rowno}", [[key, value, label or ""]])
        return
    _retry_call(ws.update, f"B{rowno}", [[value]])
    if label is not None:
        _retry_call(ws.update, f"C{rowno}", [[label]])

def _init_cfg_defaults_from_settings():
    CFG_RAW, LABELS = _settings_as_dict()
    st.session_state.setdefault("CFG", {})
    C = st.session_state["CFG"]

    def _get(k, fb): return CFG_RAW.get(k, fb)

    # datum/tid
    try:
        C["startdatum"] = datetime.fromisoformat(_get("startdatum", date.today().isoformat())).date()
    except Exception:
        C["startdatum"] = date.today()
    try:
        hh, mm = str(_get("starttid", "07:00")).split(":")
        C["starttid"] = time(int(hh), int(mm))
    except Exception:
        C["starttid"] = time(7, 0)
    try:
        C["födelsedatum"] = datetime.fromisoformat(_get("födelsedatum", "1990-01-01")).date()
    except Exception:
        C["födelsedatum"] = date(1990,1,1)

    # max/avgifter
    C["MAX_PAPPAN"]      = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]     = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"] = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"] = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]     = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]      = float(_get("avgift_usd", 30.0))

    # personal
    C["PROD_STAFF"] = int(float(_get("PROD_STAFF", 800)))
    C["PROD_PCT"]   = float(_get("PROD_PCT", 10))  # procent för personal som deltar

    # eskilstuna intervall
    C["ESK_MIN"] = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"] = int(float(_get("ESK_MAX", 40)))

    # bonusräknare
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

    # etiketter
    st.session_state["LABELS"] = {}
    for k, v in _settings_as_dict()[1].items():
        st.session_state["LABELS"][k] = v

_init_cfg_defaults_from_settings()
CFG     = st.session_state["CFG"]
LABELS  = st.session_state["LABELS"]

def _L(txt: str) -> str:
    return LABELS.get(txt, txt)

# =============================== Sidopanel (etiketter & parametrar) ============
st.sidebar.header("Inställningar & etiketter")

# Personalkonfig
prod_total = st.sidebar.number_input("Produktionspersonal (totalt)", min_value=0, step=1,
                                     value=int(CFG["PROD_STAFF"]), key="sb_prod_total")
prod_pct   = st.sidebar.number_input("Andel personal som deltar (%)", min_value=0.0, step=0.5,
                                     value=float(CFG["PROD_PCT"]), key="sb_prod_pct")

# Eskilstuna intervall
esk_min = st.sidebar.number_input("Eskilstuna killar – min", min_value=0, step=1,
                                  value=int(CFG["ESK_MIN"]), key="sb_esk_min")
esk_max = st.sidebar.number_input("Eskilstuna killar – max", min_value=0, step=1,
                                  value=int(CFG["ESK_MAX"]), key="sb_esk_max")

st.sidebar.markdown("**Max per källa (påverkar varningar & slump):**")
max_p  = st.sidebar.number_input(_L("Pappans vänner"), min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]), key="sb_max_pappan")
max_g  = st.sidebar.number_input(_L("Grannar"),        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]), key="sb_max_grannar")
max_nv = st.sidebar.number_input(_L("Nils vänner"),    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]), key="sb_max_nv")
max_nf = st.sidebar.number_input(_L("Nils familj"),    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]), key="sb_max_nf")
max_bk = st.sidebar.number_input(_L("Bekanta"),        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]), key="sb_max_bk")

avgift_val = st.sidebar.number_input("Avgift (USD, per rad)", min_value=0.0, step=1.0,
                                     value=float(CFG["avgift_usd"]), key="sb_fee")

st.sidebar.markdown("---")
st.sidebar.markdown("**Etiketter (visning):**")
lab_map = {
    "LABEL_Män": "Män",
    "LABEL_Svarta": "Svarta",
    "LABEL_Pappans vänner": "Pappans vänner",
    "LABEL_Grannar": "Grannar",
    "LABEL_Nils vänner": "Nils vänner",
    "LABEL_Nils familj": "Nils familj",
    "LABEL_Bekanta": "Bekanta",
    "LABEL_Eskilstuna killar": "Eskilstuna killar",
    "LABEL_Personal deltagit": "Personal deltagit",
    "LABEL_Bonus killar": "Bonus killar",
    "LABEL_Bonus deltagit": "Bonus deltagit",
    "LABEL_Känner": "Känner",
    "LABEL_Malins födelsedatum": "Malins födelsedatum",
}
lab_inputs = {}
for k, deflabel in lab_map.items():
    lab_inputs[k] = st.sidebar.text_input(deflabel, value=LABELS.get(deflabel, deflabel), key=f"lab_{k}")

if st.sidebar.button("💾 Spara inställningar & etiketter"):
    # spara siffror
    _save_setting("PROD_STAFF", str(int(prod_total)))
    _save_setting("PROD_PCT",   str(float(prod_pct)))
    _save_setting("ESK_MIN",    str(int(esk_min)))
    _save_setting("ESK_MAX",    str(int(esk_max)))

    _save_setting("MAX_PAPPAN", str(int(max_p)))
    _save_setting("MAX_GRANNAR", str(int(max_g)))
    _save_setting("MAX_NILS_VANNER", str(int(max_nv)))
    _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)))
    _save_setting("MAX_BEKANTA", str(int(max_bk)))
    _save_setting("avgift_usd",  str(float(avgift_val)))

    # etiketter
    for k, _ in lab_map.items():
        shown = lab_inputs[k]
        _save_setting(k, shown, label="")

    st.success("Inställningar sparade.")
    # uppdatera lokalt CFG/LABELS
    _init_cfg_defaults_from_settings()
    st.rerun()

# Meny: Produktion / Statistik
st.sidebar.markdown("---")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)
# ============================= SLUT DEL 1/6 ==============================

# ============================== app.py (DEL 2/6) ==============================
# --- Scenario-väljare ---
SCENARIO_KEY = "scenario_choice"
scenario = st.selectbox(
    "Välj scenario",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet", "Vila på jobbet"],
    key=SCENARIO_KEY
)

# --- Hjälpare för min/max från databasen (hämtas bara on-demand) ---
def _get_min_max(colname: str):
    """Hämta min/max från Data-bladet för angiven kolumn. Returnerar (min,max) eller (0,0)."""
    try:
        sheet = get_sheet()
        rows = _retry_call(sheet.get_all_records)
        vals = [_safe_int(r.get(colname, 0), 0) for r in rows if str(r.get(colname, "")).strip() != ""]
        if not vals:
            return 0, 0
        return min(vals), max(vals)
    except Exception:
        return 0, 0

def _rand_hist(col):
    mn, mx = _get_min_max(col)
    if mx < mn: return 0
    return random.randint(mn, mx)

def _personal_from_pct():
    return max(0, int(round(st.session_state["CFG"]["PROD_STAFF"] * (st.session_state["CFG"]["PROD_PCT"] / 100.0))))

def _bonus_use_now():
    # 40% av kvarvarande bonus-killar — visas bara i input (ingen persistering ännu)
    left = int(st.session_state["CFG"].get("BONUS_LEFT", 0))
    return int(left * 0.40)

def _rand_40_60_of(v):
    lo = int(round(v * 0.40))
    hi = int(round(v * 0.60))
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > 0 else 0

# ---- Init av inputs i exakt önskad ordning (en kolumn, inga duplicerade keys) ----
def _ensure_input_defaults():
    ss = st.session_state
    defaults = {
        "in_man": 0,
        "in_svarta": 0,
        "in_fitta": 0,
        "in_rumpa": 0,
        "in_dp": 0,
        "in_dpp": 0,
        "in_dap": 0,
        "in_tap": 0,

        "in_pappan": 0,
        "in_grannar": 0,
        "in_nils_v": 0,
        "in_nils_f": 0,
        "in_bekanta": 0,
        "in_esk": 0,

        "in_bonus_deltagit": 0,
        "in_personal_deltagit": _personal_from_pct(),

        "in_alskar": 0,
        "in_sover": 0,

        "in_tid_s": 60,
        "in_tid_d": 60,
        "in_vila": 7,
        "in_dt_tid": 60,
        "in_dt_vila": 3,
    }
    for k, v in defaults.items():
        ss.setdefault(k, v)

_ensure_input_defaults()

# ---- Rita input-fälten i EXAKT ordning ----
st.markdown("### Inmatning")
# (vi använder key= som ovan, så Hämta värden kan sätta via session_state)

in_man    = st.number_input(_L("Män"),    min_value=0, step=1, key="in_man")
in_svarta = st.number_input(_L("Svarta"), min_value=0, step=1, key="in_svarta")

in_fitta  = st.number_input("Fitta", min_value=0, step=1, key="in_fitta")
in_rumpa  = st.number_input("Rumpa", min_value=0, step=1, key="in_rumpa")
in_dp     = st.number_input("DP",    min_value=0, step=1, key="in_dp")
in_dpp    = st.number_input("DPP",   min_value=0, step=1, key="in_dpp")
in_dap    = st.number_input("DAP",   min_value=0, step=1, key="in_dap")
in_tap    = st.number_input("TAP",   min_value=0, step=1, key="in_tap")

in_pappan  = st.number_input(_L("Pappans vänner"), min_value=0, step=1, key="in_pappan")
in_grannar = st.number_input(_L("Grannar"),        min_value=0, step=1, key="in_grannar")
in_nils_v  = st.number_input(_L("Nils vänner"),    min_value=0, step=1, key="in_nils_v")
in_nils_f  = st.number_input(_L("Nils familj"),    min_value=0, step=1, key="in_nils_f")
in_bekanta = st.number_input(_L("Bekanta"),        min_value=0, step=1, key="in_bekanta")
in_esk     = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, key="in_esk")

in_bonus_deltagit    = st.number_input(_L("Bonus deltagit"),    min_value=0, step=1, key="in_bonus_deltagit")
in_personal_deltagit = st.number_input(_L("Personal deltagit"), min_value=0, step=1, key="in_personal_deltagit")

in_alskar = st.number_input("Älskar",    min_value=0, step=1, key="in_alskar")
in_sover  = st.number_input("Sover med", min_value=0, max_value=1, step=1, key="in_sover")

in_tid_s   = st.number_input("Tid S (sek)",           min_value=0, step=1, key="in_tid_s")
in_tid_d   = st.number_input("Tid D (sek)",           min_value=0, step=1, key="in_tid_d")
in_vila    = st.number_input("Vila (sek)",            min_value=0, step=1, key="in_vila")
in_dt_tid  = st.number_input("DT tid (sek/kille)",    min_value=0, step=1, key="in_dt_tid")
in_dt_vila = st.number_input("DT vila (sek/kille)",   min_value=0, step=1, key="in_dt_vila")

# ---- Hämta värden (fyll inputs beroende på scenario) ----
def apply_scenario_fill():
    CFG = st.session_state["CFG"]

    # reset endast de fält scenariot uttryckligen styr; lämna övriga oförändrade
    # bonus deltagit alltid 40% av BONUS_LEFT vid fyllning:
    bd_use = _bonus_use_now()

    if scenario == "Ny scen":
        # Endast bas: bonus deltagit + personal via procent
        st.session_state.in_bonus_deltagit    = bd_use
        st.session_state.in_personal_deltagit = _personal_from_pct()
        # Älskar/sover rör vi inte (användaren kan ställa själv)
        # Eskilstuna låter vi vara (manuell), Män/Svarta manuellt
        return

    if scenario == "Slumpa scen vit":
        # Män & acts från historiska min/max, Svarta=0, källor från historik, Eskilstuna enligt sidopanelens intervall
        st.session_state.in_man   = _rand_hist("Män")
        st.session_state.in_svarta= 0
        st.session_state.in_fitta = _rand_hist("Fitta")
        st.session_state.in_rumpa = _rand_hist("Rumpa")
        st.session_state.in_dp    = _rand_hist("DP")
        st.session_state.in_dpp   = _rand_hist("DPP")
        st.session_state.in_dap   = _rand_hist("DAP")
        st.session_state.in_tap   = _rand_hist("TAP")

        st.session_state.in_pappan  = _rand_hist("Pappans vänner")
        st.session_state.in_grannar = _rand_hist("Grannar")
        st.session_state.in_nils_v  = _rand_hist("Nils vänner")
        st.session_state.in_nils_f  = _rand_hist("Nils familj")
        st.session_state.in_bekanta = _rand_hist("Bekanta")

        # Eskilstuna enligt sidopanelens intervall:
        e_min = int(CFG["ESK_MIN"]); e_max = int(CFG["ESK_MAX"])
        if e_max < e_min: e_max = e_min
        st.session_state.in_esk = random.randint(e_min, e_max)

        st.session_state.in_alskar = 8
        st.session_state.in_sover  = 1
        st.session_state.in_personal_deltagit = _personal_from_pct()
        st.session_state.in_bonus_deltagit    = bd_use
        return

    if scenario == "Slumpa scen svart":
        # Acts + Svarta från historik. Alla källor = 0. Eskilstuna = 0. Personal deltagit = 0 (enligt senaste önskemål)
        st.session_state.in_fitta = _rand_hist("Fitta")
        st.session_state.in_rumpa = _rand_hist("Rumpa")
        st.session_state.in_dp    = _rand_hist("DP")
        st.session_state.in_dpp   = _rand_hist("DPP")
        st.session_state.in_dap   = _rand_hist("DAP")
        st.session_state.in_tap   = _rand_hist("TAP")
        st.session_state.in_svarta= _rand_hist("Svarta")

        st.session_state.in_man   = 0
        st.session_state.in_pappan= 0
        st.session_state.in_grannar=0
        st.session_state.in_nils_v= 0
        st.session_state.in_nils_f= 0
        st.session_state.in_bekanta=0
        st.session_state.in_esk   = 0

        st.session_state.in_alskar = 8
        st.session_state.in_sover  = 1
        st.session_state.in_personal_deltagit = 0  # viktigt enligt din instruktion
        st.session_state.in_bonus_deltagit    = bd_use
        return

    if scenario == "Vila på jobbet":
        # Män/Svarta = 0. Acts från historiska min/max.
        st.session_state.in_man    = 0
        st.session_state.in_svarta = 0
        st.session_state.in_fitta  = _rand_hist("Fitta")
        st.session_state.in_rumpa  = _rand_hist("Rumpa")
        st.session_state.in_dp     = _rand_hist("DP")
        st.session_state.in_dpp    = _rand_hist("DPP")
        st.session_state.in_dap    =

# ============================== app.py (DEL 3/6) ==============================
# --- Scen/datum-hjälpare (utan Sheets-anrop) ---
SCENE_BASE_KEY = "SCEN_BASINDEX"
if SCENE_BASE_KEY not in st.session_state:
    # Basindex för "nästa scen" i denna session (ökar vid spar – i del 5)
    st.session_state[SCENE_BASE_KEY] = 1

def _scene_number() -> int:
    # "Aktuell" scen i denna session (utan koppling till Sheets förrän spar)
    return int(st.session_state.get(SCENE_BASE_KEY, 1))

def _datum_och_veckodag_for_scene(scene_num: int):
    d = st.session_state["CFG"]["startdatum"] + timedelta(days=scene_num - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

scen = _scene_number()
rad_datum, veckodag = _datum_och_veckodag_for_scene(scen)

# --- Bygg grund-preview från inputs (ingen skrivning till Sheets!) ---
def _build_grund_from_inputs():
    C = st.session_state["CFG"]
    grund = {
        "Typ": (st.session_state.get(SCENARIO_KEY) or "Ny scen"),
        "Veckodag": veckodag,
        "Scen": scen,

        "Män":                 st.session_state.in_man,
        "Svarta":              st.session_state.in_svarta,
        "Fitta":               st.session_state.in_fitta,
        "Rumpa":               st.session_state.in_rumpa,
        "DP":                  st.session_state.in_dp,
        "DPP":                 st.session_state.in_dpp,
        "DAP":                 st.session_state.in_dap,
        "TAP":                 st.session_state.in_tap,

        "Tid S":               st.session_state.in_tid_s,
        "Tid D":               st.session_state.in_tid_d,
        "Vila":                st.session_state.in_vila,
        "DT tid (sek/kille)":  st.session_state.in_dt_tid,
        "DT vila (sek/kille)": st.session_state.in_dt_vila,

        "Älskar":              st.session_state.in_alskar,
        "Sover med":           st.session_state.in_sover,

        "Pappans vänner":      st.session_state.in_pappan,
        "Grannar":             st.session_state.in_grannar,
        "Nils vänner":         st.session_state.in_nils_v,
        "Nils familj":         st.session_state.in_nils_f,
        "Bekanta":             st.session_state.in_bekanta,
        "Eskilstuna killar":   st.session_state.in_esk,

        # Bonus/Personal enligt inputs
        "Bonus killar":        int(C.get("BONUS_TOTAL", 0)),   # total finns i settings
        "Bonus deltagit":      st.session_state.in_bonus_deltagit,
        "Personal deltagit":   st.session_state.in_personal_deltagit,

        "Nils":                st.session_state.get("in_nils", 0),

        # Ekonomi
        "Avgift":              float(C.get("avgift_usd", 30.0)),

        # Viktigt: hela personalstyrkan för lönebasen (ignorerar "Personal deltagit" i lönebas)
        "PROD_STAFF":          int(C.get("PROD_STAFF", 800)),
    }
    return grund

grund_preview = _build_grund_from_inputs()

# --- Trygg anropare till beräkningar (positional args så vi undviker namnmismatch) ---
def _calc_preview(grund, rad_datum, foddat, starttid):
    # 1) Försök extern beräkningsmodul
    if callable(calc_row_values):
        try:
            return calc_row_values(grund, rad_datum, foddat, starttid)
        except TypeError:
            # Fallback: om extern modul har annan signatur – prova bara (grund, rad_datum)
            try:
                return calc_row_values(grund, rad_datum)  # äldre variant
            except Exception:
                pass
        except Exception:
            pass
    # 2) Minimal intern fallback (om berakningar.py saknas/krånglar)
    try:
        # Totalt män (för förhandsvisning)
        tot_man = (
            grund.get("Män", 0)
            + grund.get("Svarta", 0)
            + grund.get("Bekanta", 0)
            + grund.get("Eskilstuna killar", 0)
            + grund.get("Bonus deltagit", 0)
            + grund.get("Pappans vänner", 0)
            + grund.get("Grannar", 0)
            + grund.get("Nils vänner", 0)
            + grund.get("Nils familj", 0)
            + grund.get("Personal deltagit", 0)  # räknas till total män, även om lönebas = PROD_STAFF
        )
        fitta = grund.get("Fitta",0); rumpa=grund.get("Rumpa",0)
        dp=grund.get("DP",0); dpp=grund.get("DPP",0); dap=grund.get("DAP",0); tap=grund.get("TAP",0)

        tid_s = int(grund.get("Tid S",0)); tid_d = int(grund.get("Tid D",0)); vila=int(grund.get("Vila",0))
        dt_tid=int(grund.get("DT tid (sek/kille)",0)); dt_vila=int(grund.get("DT vila (sek/kille)",0))

        # Summa S/D/TP/Vila enligt din spec
        summa_s   = tid_s * (fitta + rumpa) + dt_tid * max(tot_man, 0)
        summa_d   = tid_d * (dp + dpp + dap)
        summa_tp  = 3 * tap
        summa_vila= vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * max(tot_man, 0)

        tid_alskar_sek = int(grund.get("Älskar",0)) * 20 * 60
        tid_sover_sek  = int(grund.get("Sover med",0)) * 20 * 60

        summa_tid_sek  = int(summa_s + summa_d + summa_tp + summa_vila)
        # Klockan = summa tid + 3 + 1 + älskar + sover (minuter)
        klocka_sek = summa_tid_sek + (3*60) + (1*60) + tid_alskar_sek + tid_sover_sek

        # Tid per kille
        men_base = max(tot_man, 1)
        tpk_s   = (summa_s / men_base) if men_base>0 else 0
        tpk_d   = ((summa_d / men_base) * 2) if men_base>0 else 0
        tpk_tp  = ((summa_tp / men_base) * 3) if men_base>0 else 0
        suger_total = 0.6 * summa_tid_sek
        tpk_suger = (suger_total / men_base) if men_base>0 else 0
        tpk_dt   = dt_tid  # per kille

        tid_per_kille_sek = int(round(tpk_s + tpk_d + tpk_tp + tpk_suger + tpk_dt))

        # Hångel (sek/kille)
        hangel_per_kille = int(round((3*3600) / men_base)) if men_base>0 else 0
        m = hangel_per_kille // 60; s = hangel_per_kille % 60
        hangel_ms = f"{m}m {s}s/kille"

        # Hårdhet
        hard = 0
        if dp>0: hard += 3
        if dpp>0: hard += 5
        if dap>0: hard += 7
        if tap>0: hard += 9
        if tot_man>100: hard += 1
        if tot_man>200: hard += 3
        if tot_man>=300: hard += 5
        if tot_man>=500: hard += 6
        if tot_man>=1000: hard += 10
        if int(grund.get("Svarta",0))>0: hard += 3

        # Prenumeranter & Intäkter (rad)
        pren = int( (fitta + rumpa + dp + dpp + dap + tap + tot_man) * hard )
        avgift = float(grund.get("Avgift", 30.0))
        intakter = pren * avgift

        # Utgift män (hela personalstyrkan räknas i lönebasen)
        prod_staff = int(grund.get("PROD_STAFF", 800))
        lon_base_cnt = (
            int(grund.get("Män",0)) + int(grund.get("Svarta",0)) + int(grund.get("Bekanta",0))
            + int(grund.get("Eskilstuna killar",0)) + int(grund.get("Bonus deltagit",0))
            + prod_staff
        )
        utgift_man = lon_base_cnt * (summa_tid_sek/3600.0) * 15.0

        # Intäkt Känner
        känner = int(grund.get("Pappans vänner",0)) + int(grund.get("Grannar",0)) + int(grund.get("Nils vänner",0)) + int(grund.get("Nils familj",0))
        intakt_kanner = (summa_tid_sek/3600.0) * 35.0 * känner

        # Lön Malin: 8% av (intäkter - utgift män), min 150, max 800 (lägst 0 om negativt underlag)
        underlag = max(0.0, (intakter - utgift_man))
        lon_malin = min(800.0, max(150.0, underlag * 0.08))

        # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
        vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

        return {
            "Totalt Män": tot_man,
            "Summa S": int(summa_s),
            "Summa D": int(summa_d),
            "Summa TP": int(summa_tp),
            "Summa Vila": int(summa_vila),
            "Summa tid (sek)": int(summa_tid_sek),
            "Summa tid": _hm_str_from_seconds(int(summa_tid_sek)),

            "Tid Älskar (sek)": int(tid_alskar_sek),
            "Tid Älskar": _hm_str_from_seconds(int(tid_alskar_sek)),
            "Tid Sover med (sek)": int(tid_sover_sek),
            "Tid Sover med": _hm_str_from_seconds(int(tid_sover_sek)),

            "Klockan": _hm_str_from_seconds(int(klocka_sek)),

            "Tid per kille (sek)": int(tid_per_kille_sek),
            "Tid per kille": _ms_str_from_seconds(int(tid_per_kille_sek)),

            "Hångel (sek/kille)": int(hangel_per_kille),
            "Hångel (m:s/kille)": hangel_ms,

            "Suger": int(suger_total),
            "Suger per kille (sek)": int(tpk_suger),

            "Hårdhet": int(hard),
            "Prenumeranter": int(pren),
            "Avgift": float(avgift),
            "Intäkter": float(intakter),

            "Utgift män": float(utgift_man),
            "Intäkt Känner": float(intakt_kanner),
            "Lön Malin": float(lon_malin),
            "Vinst": float(vinst),

            "Känner": int(känner),
        }
    except Exception:
        return {}

preview = _calc_preview(
    grund_preview,
    rad_datum,
    st.session_state["CFG"]["födelsedatum"],
    st.session_state["CFG"]["starttid"],
)

# --- Ålder i liven ---
def _alder_at(d: date, fodelsedatum: date) -> int:
    return d.year - fodelsedatum.year - ((d.month, d.day) < (fodelsedatum.month, fodelsedatum.day))

alder = _alder_at(rad_datum, st.session_state["CFG"]["födelsedatum"])

# --- Live-visning ---
st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
c1, c2 = st.columns(2)
with c1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin)", f"{alder} år")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with c2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {st.session_state['CFG']['starttid']})")

st.markdown("#### 💵 Ekonomi (live)")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", st.session_state['CFG'].get('avgift_usd', 30.0))))
with e2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with e3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with e4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))
# ============================= SLUT DEL 3/6 ==============================

# ============================== app.py (DEL 4/6) ==============================
# --- Spara / Auto-Max (inga skrivningar förrän du aktivt sparar) ---
ROW_COUNT_KEY = "ROW_COUNT"

def _collect_over_max(grund: dict) -> dict:
    C = st.session_state["CFG"]
    over = {}
    if grund.get("Pappans vänner", 0) > int(C["MAX_PAPPAN"]):
        over["Pappans vänner"] = {"current_max": int(C["MAX_PAPPAN"]), "new_value": int(grund["Pappans vänner"]), "max_key": "MAX_PAPPAN"}
    if grund.get("Grannar", 0) > int(C["MAX_GRANNAR"]):
        over["Grannar"] = {"current_max": int(C["MAX_GRANNAR"]), "new_value": int(grund["Grannar"]), "max_key": "MAX_GRANNAR"}
    if grund.get("Nils vänner", 0) > int(C["MAX_NILS_VANNER"]):
        over["Nils vänner"] = {"current_max": int(C["MAX_NILS_VANNER"]), "new_value": int(grund["Nils vänner"]), "max_key": "MAX_NILS_VANNER"}
    if grund.get("Nils familj", 0) > int(C["MAX_NILS_FAMILJ"]):
        over["Nils familj"] = {"current_max": int(C["MAX_NILS_FAMILJ"]), "new_value": int(grund["Nils familj"]), "max_key": "MAX_NILS_FAMILJ"}
    if grund.get("Bekanta", 0) > int(C["MAX_BEKANTA"]):
        over["Bekanta"] = {"current_max": int(C["MAX_BEKANTA"]), "new_value": int(grund["Bekanta"]), "max_key": "MAX_BEKANTA"}
    return over

def _store_pending_save(grund: dict, scen_num: int, d: date, veck: str, over_max: dict):
    st.session_state["PENDING_SAVE"] = {
        "grund": grund,
        "scen": scen_num,
        "rad_datum": d.isoformat(),
        "veckodag": veck,
        "over_max": over_max,
    }

def _apply_auto_max_and_save(pending: dict):
    # Uppdatera maxvärden i Inställningar (per din bekräftelse)
    for _, info in pending["over_max"].items():
        _save_setting(info["max_key"], str(int(info["new_value"])))
        st.session_state["CFG"][info["max_key"]] = int(info["new_value"])
    # Spara raden
    _save_row(pending["grund"],
              datetime.fromisoformat(pending["rad_datum"]).date(),
              pending["veckodag"])

def _save_row(grund: dict, d: date, veck: str):
    """Kör alla beräkningar, skriver EN rad till Data och ökar scenräknare i sessionen."""
    try:
        base = dict(grund)
        # säkerställ att Avgift/PROD_STAFF finns
        base.setdefault("Avgift", float(st.session_state["CFG"].get("avgift_usd", 30.0)))
        base.setdefault("PROD_STAFF", int(st.session_state["CFG"].get("PROD_STAFF", 800)))

        ber = _calc_preview(base, d, st.session_state["CFG"]["födelsedatum"], st.session_state["CFG"]["starttid"])
        if not ber:
            st.error("Beräkningen misslyckades – ingen rad sparad.")
            return
        ber["Datum"] = d.isoformat()
        ber["Typ"] = base.get("Typ") or "Ny scen"
        ber["Veckodag"] = veck
        ber["Scen"] = base.get("Scen", _scene_number())

        # Lägg även in alla inputfält (så vi sparar precis vad som matades)
        for k, v in base.items():
            if k not in ber:
                ber[k] = v

        # Skriv enligt KOLUMNER
        row = [ber.get(col, "") for col in KOLUMNER]
        _retry_call(sheet.append_row, row)

        # Öka lokal scenräknare/rowcount
        st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1
        st.session_state[SCENE_BASE_KEY] = st.session_state.get(SCENE_BASE_KEY, 1) + 1

        # Feedback
        age = _alder_at(d, st.session_state["CFG"]["födelsedatum"])
        st.success(f"✅ Rad sparad ({ber.get('Typ','Händelse')}). Datum {d} ({veck}), Ålder {age} år, Klockan {ber.get('Klockan','-')}")

    except Exception as e:
        st.error(f"Fel vid sparning: {e}")

# --- Spara-knappen (sparar den aktuella input-raden) ---
save_clicked = st.button("💾 Spara raden")
if save_clicked:
    over = _collect_over_max(grund_preview)
    if over:
        _store_pending_save(grund_preview, scen, rad_datum, veckodag, over)
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# --- Auto-Max dialog ---
if "PENDING_SAVE" in st.session_state:
    pending = st.session_state["PENDING_SAVE"]
    st.warning("Du har angivit värden som överstiger max. Vill du uppdatera max och spara raden?")
    for f, info in pending["over_max"].items():
        st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Uppdatera max & spara"):
            try:
                _apply_auto_max_and_save(pending)
            finally:
                st.session_state.pop("PENDING_SAVE", None)
                st.rerun()
    with c2:
        if st.button("✋ Avbryt"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbruten – justera värden eller max i sidopanelen.")

# ==================== Buffert för 'Vila i hemmet' (7-dagars paket) ====================
HOME_BUF_KEY = "HOME_BUFFER"           # lista med 7 dictar (en per dag)
HOME_IDX_KEY = "HOME_BUFFER_INDEX"     # aktiv dag (0..6)

def _build_home_package(start_scene: int):
    """Skapar 7-dagarsstruktur UTAN att spara. Du kan bläddra + fylla inputs från bufferten."""
    C = st.session_state["CFG"]

    # bestäm Nils-dagar (0–6, men 6 = 'sover med'-dagen)
    r = random.random()
    if r < 0.50:
        ones_count = 0
    elif r < 0.95:
        ones_count = 1
    else:
        ones_count = 2
    nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

    # slumpa samma “core”-mönster för fitta/rumpa/dp/dpp/dap/tap för hela veckan
    # (som du önskade: samma slump för hela intervallet)
    all_rows = _retry_call(sheet.get_all_records)
    def _mm(name):
        vals = [_safe_int(r.get(name, 0), 0) for r in all_rows]
        return (min(vals), max(vals)) if vals else (0, 0)

    core = {
        "Fitta": random.randint(*_mm("Fitta")),
        "Rumpa": random.randint(*_mm("Rumpa")),
        "DP":    random.randint(*_mm("DP")),
        "DPP":   random.randint(*_mm("DPP")),
        "DAP":   random.randint(*_mm("DAP")),
        "TAP":   random.randint(*_mm("TAP")),
    }

    pkg = []
    for offset in range(7):
        scen_num = start_scene + offset
        d, vd = _datum_och_veckodag_for_scene(scen_num)

        if offset <= 4:
            # dag 1–5: källor fylls 40–60% av max och personal  = procenten från sidopanelen
            pv = int(round(random.uniform(0.40, 0.60) * int(C["MAX_PAPPAN"])))
            gr = int(round(random.uniform(0.40, 0.60) * int(C["MAX_GRANNAR"])))
            nv = int(round(random.uniform(0.40, 0.60) * int(C["MAX_NILS_VANNER"])))
            nf = int(round(random.uniform(0.40, 0.60) * int(C["MAX_NILS_FAMILJ"])))
            bk = int(round(random.uniform(0.40, 0.60) * int(C["MAX_BEKANTA"])))
            esk = random.randint(st.session_state.eskilstuna_min, st.session_state.eskilstuna_max)
            pers = int(round(int(C["PROD_STAFF"]) * (float(st.session_state.personal_pct)/100.0)))
        else:
            pv = gr = nv = nf = bk = 0
            esk = random.randint(st.session_state.eskilstuna_min, st.session_state.eskilstuna_max)
            pers = 0  # dag 6-7 = 0

        sover = 1 if offset == 6 else 0
        nils_val = 0 if offset == 6 else (1 if offset in nils_one_offsets else 0)

        # Bonus deltagit för varje dag hämtas från "Bonus killar" 40% – men här använder vi
        # totala BONUS_TOTAL från settings och tar 40% “denna dag” (utan att dra från lagret
        # eftersom inget sparas än). Det gör att du ser det i input.
        bonus_total = int(C.get("BONUS_TOTAL", 0))
        bonus_delt = int(round(bonus_total * 0.40)) if offset <= 4 else 0  # dag 1–5
        # räknas som svarta i statistik – det sker i beräkningar när vi räknar andel.

        base = {
            "Typ": "Vila i hemmet",
            "Veckodag": vd, "Scen": scen_num,
            "Män": 0, "Svarta": 0,
            "Fitta": core["Fitta"], "Rumpa": core["Rumpa"],
            "DP": core["DP"], "DPP": core["DPP"], "DAP": core["DAP"], "TAP": core["TAP"],
            "Tid S": 0, "Tid D": 0, "Vila": 0,
            "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
            "Älskar": 6, "Sover med": sover,

            "Pappans vänner": pv, "Grannar": gr,
            "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,

            "Bonus killar": bonus_total,
            "Bonus deltagit": bonus_delt,
            "Personal deltagit": pers,

            "Nils": nils_val,
            "Avgift": float(C.get("avgift_usd", 30.0)),
            "PROD_STAFF": int(C.get("PROD_STAFF", 800)),
        }
        pkg.append(base)
    return pkg

# UI för buffert (visas bara om buffert finns)
def _home_buffer_controls():
    if HOME_BUF_KEY not in st.session_state or not st.session_state[HOME_BUF_KEY]:
        return
    st.markdown("---")
    st.subheader("🏠 Förhandsbuffert: 'Vila i hemmet' (7 dagar)")
    idx = st.session_state.get(HOME_IDX_KEY, 0)
    left, mid, right = st.columns([1,2,1])
    with left:
        if st.button("⟵ Föregående dag", disabled=(idx<=0)):
            st.session_state[HOME_IDX_KEY] = max(0, idx-1)
            st.rerun()
    with mid:
        st.info(f"Dag {idx+1} / 7")
    with right:
        if st.button("Nästa dag ⟶", disabled=(idx>=6)):
            st.session_state[HOME_IDX_KEY] = min(6, idx+1)
            st.rerun()

    # Visa en snabb sammanfattning för vald dag
    item = st.session_state[HOME_BUF_KEY][idx]
    st.write({k: item[k] for k in [
        "Typ","Veckodag","Scen","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar",
        "Bonus deltagit","Personal deltagit","Sover med","Nils"
    ]})

    if st.button("⤴️ Fyll inputs med denna dag (utan att spara)"):
        # lägg in alla relevanta fält till inputs
        st.session_state.in_man    = 0
        st.session_state.in_svarta = 0
        st.session_state.in_fitta  = item["Fitta"]
        st.session_state.in_rumpa  = item["Rumpa"]
        st.session_state.in_dp     = item["DP"]
        st.session_state.in_dpp    = item["DPP"]
        st.session_state.in_dap    = item["DAP"]
        st.session_state.in_tap    = item["TAP"]

        st.session_state.in_pappan   = item["Pappans vänner"]
        st.session_state.in_grannar  = item["Grannar"]
        st.session_state.in_nils_v   = item["Nils vänner"]
        st.session_state.in_nils_f   = item["Nils familj"]
        st.session_state.in_bekanta  = item["Bekanta"]
        st.session_state.in_esk      = item["Eskilstuna killar"]

        st.session_state.in_bonus_deltagit    = item["Bonus deltagit"]
        st.session_state.in_personal_deltagit = item["Personal deltagit"]
        st.session_state.in_sover   = item["Sover med"]
        st.session_state.in_nils    = item["Nils"]

        # tider enligt spec för vila i hemmet
        st.session_state.in_tid_s   = 0
        st.session_state.in_tid_d   = 0
        st.session_state.in_vila    = 0
        st.session_state.in_dt_tid  = 60
        st.session_state.in_dt_vila = 3

        # sätt “Typ” i scenariofältet så liven visar korrekt text
        st.session_state[SCENARIO_KEY] = "Vila i hemmet"
        st.rerun()

# Anropa buffert-kontroller om det finns något i bufferten
_home_buffer_controls()
# ============================= SLUT DEL 4/6 ==============================

# ============================== app.py (DEL 5/6) ==============================
# -------- Snabbåtgärder / Hämta-värden (fyller bara inputs, SPARAR EJ) --------

# Hjälpare: min/max från historik
if "_get_min_max" not in globals():
    def _get_min_max(colname: str):
        try:
            all_rows = _retry_call(sheet.get_all_records)
        except Exception:
            return 0, 0
        vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
        if not vals:
            return 0, 0
        return min(vals), max(vals)

def _pct_of_staff() -> int:
    staff = int(st.session_state["CFG"].get("PROD_STAFF", 800))
    pct   = float(st.session_state.get("personal_pct", 10.0))
    return max(0, int(round(staff * (pct/100.0))))

def _bonus_40pct() -> int:
    return int(round(int(st.session_state["CFG"].get("BONUS_TOTAL", 0)) * 0.40))

def _fill_defaults_typ(typtext: str):
    st.session_state[SCENARIO_KEY] = typtext
    # Behåll redan inslagna tider etc – ändras per scenariofunktion nedan

# ---------- NY SCEN: fyll standardvärden ----------
if st.button("🎯 Hämta värden (Ny scen)"):
    _fill_defaults_typ("Ny scen")
    # Nollläge + standard på vissa
    st.session_state.in_man    = 0
    st.session_state.in_svarta = 0
    st.session_state.in_fitta  = 0
    st.session_state.in_rumpa  = 0
    st.session_state.in_dp     = 0
    st.session_state.in_dpp    = 0
    st.session_state.in_dap    = 0
    st.session_state.in_tap    = 0

    st.session_state.in_pappan  = 0
    st.session_state.in_grannar = 0
    st.session_state.in_nils_v  = 0
    st.session_state.in_nils_f  = 0
    st.session_state.in_bekanta = 0
    st.session_state.in_esk     = 0

    st.session_state.in_bonus_deltagit    = _bonus_40pct()
    st.session_state.in_personal_deltagit = _pct_of_staff()

    st.session_state.in_alskar = 0
    st.session_state.in_sover  = 0

    # standardtider (kan ändras manuellt)
    st.session_state.in_tid_s   = 60
    st.session_state.in_tid_d   = 60
    st.session_state.in_vila    = 7
    st.session_state.in_dt_tid  = 60
    st.session_state.in_dt_vila = 3

    st.rerun()

# ---------- SLUMPA SCEN VIT ----------
if st.button("🎲 Hämta värden (Slumpa scen vit)"):
    _fill_defaults_typ("Slumpa scen vit")
    # Slump mellan historikens min/max
    st.session_state.in_man    = random.randint(*_get_min_max("Män"))
    st.session_state.in_svarta = 0  # vit scen: svarta sätts ej här
    st.session_state.in_fitta  = random.randint(*_get_min_max("Fitta"))
    st.session_state.in_rumpa  = random.randint(*_get_min_max("Rumpa"))
    st.session_state.in_dp     = random.randint(*_get_min_max("DP"))
    st.session_state.in_dpp    = random.randint(*_get_min_max("DPP"))
    st.session_state.in_dap    = random.randint(*_get_min_max("DAP"))
    st.session_state.in_tap    = random.randint(*_get_min_max("TAP"))

    # Källor: slumpa via historikens min/max
    st.session_state.in_pappan  = random.randint(*_get_min_max("Pappans vänner"))
    st.session_state.in_grannar = random.randint(*_get_min_max("Grannar"))
    st.session_state.in_nils_v  = random.randint(*_get_min_max("Nils vänner"))
    st.session_state.in_nils_f  = random.randint(*_get_min_max("Nils familj"))
    st.session_state.in_bekanta = random.randint(*_get_min_max("Bekanta"))

    # Eskilstuna killar: från sidopanelens intervall
    st.session_state.in_esk = random.randint(
        int(st.session_state.eskilstuna_min),
        int(st.session_state.eskilstuna_max)
    )

    # Bonus & personal
    st.session_state.in_bonus_deltagit    = _bonus_40pct()
    st.session_state.in_personal_deltagit = _pct_of_staff()

    # Älskar/Sover enligt spec för slump vit
    st.session_state.in_alskar = 8
    st.session_state.in_sover  = 1

    # tider oförändrade (använd det du redan har i inputs)
    st.rerun()

# ---------- SLUMPA SCEN SVART ----------
if st.button("🖤 Hämta värden (Slumpa scen svart)"):
    _fill_defaults_typ("Slumpa scen svart")
    # Svarta + akter slumpas, övriga källor 0 (din spec)
    st.session_state.in_fitta  = random.randint(*_get_min_max("Fitta"))
    st.session_state.in_rumpa  = random.randint(*_get_min_max("Rumpa"))
    st.session_state.in_dp     = random.randint(*_get_min_max("DP"))
    st.session_state.in_dpp    = random.randint(*_get_min_max("DPP"))
    st.session_state.in_dap    = random.randint(*_get_min_max("DAP"))
    st.session_state.in_tap    = random.randint(*_get_min_max("TAP"))
    st.session_state.in_svarta = random.randint(*_get_min_max("Svarta"))

    # Nollställ män och alla källor (enligt din begäran)
    st.session_state.in_man    = 0
    st.session_state.in_pappan = 0
    st.session_state.in_grannar = 0
    st.session_state.in_nils_v  = 0
    st.session_state.in_nils_f  = 0
    st.session_state.in_bekanta = 0
    st.session_state.in_esk     = 0

    # Bonus & personal – svart: personal deltagit = 0 (din senaste regel)
    st.session_state.in_bonus_deltagit    = _bonus_40pct()
    st.session_state.in_personal_deltagit = 0

    st.session_state.in_alskar = 8
    st.session_state.in_sover  = 1

    st.rerun()

# ---------- VILA PÅ JOBBET ----------
if st.button("🏢 Hämta värden (Vila på jobbet)"):
    _fill_defaults_typ("Vila på jobbet")
    # Slumpa fitta/rumpa/dp/dpp/dap/tap från historikens min/max
    st.session_state.in_fitta  = random.randint(*_get_min_max("Fitta"))
    st.session_state.in_rumpa  = random.randint(*_get_min_max("Rumpa"))
    st.session_state.in_dp     = random.randint(*_get_min_max("DP"))
    st.session_state.in_dpp    = random.randint(*_get_min_max("DPP"))
    st.session_state.in_dap    = random.randint(*_get_min_max("DAP"))
    st.session_state.in_tap    = random.randint(*_get_min_max("TAP"))

    # Män/svarta = 0 (vila)
    st.session_state.in_man    = 0
    st.session_state.in_svarta = 0

    # Källor: 40–60% av max (enligt din tidigare spec)
    C = st.session_state["CFG"]
    def _r4060(mx): return int(round(random.uniform(0.40, 0.60) * int(mx)))
    st.session_state.in_pappan  = _r4060(C["MAX_PAPPAN"])
    st.session_state.in_grannar = _r4060(C["MAX_GRANNAR"])
    st.session_state.in_nils_v  = _r4060(C["MAX_NILS_VANNER"])
    st.session_state.in_nils_f  = _r4060(C["MAX_NILS_FAMILJ"])
    st.session_state.in_bekanta = _r4060(C["MAX_BEKANTA"])

    # Eskilstuna från intervall
    st.session_state.in_esk = random.randint(
        int(st.session_state.eskilstuna_min),
        int(st.session_state.eskilstuna_max)
    )

    # Bonus 40%, personal = procent av hela personalstyrkan (din senaste regel)
    st.session_state.in_bonus_deltagit    = _bonus_40pct()
    st.session_state.in_personal_deltagit = _pct_of_staff()

    # Vila på jobbet: älskar=12, sover=1
    st.session_state.in_alskar = 12
    st.session_state.in_sover  = 1

    # Tider för vila på jobbet – enligt din modell (kan ändras manuellt efter)
    st.session_state.in_tid_s   = 0
    st.session_state.in_tid_d   = 0
    st.session_state.in_vila    = 0
    st.session_state.in_dt_tid  = 60
    st.session_state.in_dt_vila = 3

    st.rerun()

# ---------- VILA I HEMMET (skapa buffert 7 dagar, SPARAR EJ) ----------
if st.button("📦 Skapa buffert (Vila i hemmet – 7 dagar)"):
    base_scene = _scene_number()
    st.session_state[HOME_BUF_KEY] = _build_home_package(base_scene)
    st.session_state[HOME_IDX_KEY] = 0
    st.success("Buffert skapad. Bläddra i sektionen nedan och 'Fyll inputs' för vald dag.")
    st.rerun()
# ============================= SLUT DEL 5/6 ==============================

# ============================== app.py (DEL 6/6) ==============================
# --------- "Vila i hemmet" – visa/beskriv buffert och fyll inputs från dag -----

st.markdown("---")
st.subheader("🏠 Vila i hemmet – buffert")

if HOME_BUF_KEY in st.session_state and st.session_state[HOME_BUF_KEY]:
    pkg = st.session_state[HOME_BUF_KEY]
    total_days = len(pkg)
    cur_idx = st.session_state.get(HOME_IDX_KEY, 0)

    # Välj dag i bufferten
    cX, cY = st.columns([3, 1])
    with cX:
        st.session_state[HOME_IDX_KEY] = st.number_input(
            "Visa dag (0–6)",
            min_value=0, max_value=max(0, total_days - 1), value=int(cur_idx), step=1
        )
    with cY:
        if st.button("⟲ Töm buffert"):
            st.session_state.pop(HOME_BUF_KEY, None)
            st.session_state.pop(HOME_IDX_KEY, None)
            st.info("Buffert rensad.")
            st.rerun()

    cur_idx = st.session_state[HOME_IDX_KEY]
    day_item = pkg[cur_idx]
    st.write(f"**Dag {cur_idx+1}** — Scen {day_item['Scen']}, {day_item['Veckodag']}")

    # Visa förhandsdata för vald buffertdag (en enkel tabell)
    show_map = {k: day_item.get(k, "") for k in [
        "Typ","Veckodag","Scen",
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar",
        "Bonus deltagit","Personal deltagit",
        "Älskar","Sover med","Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)"
    ]}
    st.table(show_map)

    # Fyll inputs med vald buffertdag (Sparar EJ till databasen)
    if st.button("🧪 Fyll inputs från vald buffertdag"):
        # Grundinputs
        st.session_state.in_man    = int(day_item.get("Män", 0))
        st.session_state.in_svarta = int(day_item.get("Svarta", 0))
        st.session_state.in_fitta  = int(day_item.get("Fitta", 0))
        st.session_state.in_rumpa  = int(day_item.get("Rumpa", 0))
        st.session_state.in_dp     = int(day_item.get("DP", 0))
        st.session_state.in_dpp    = int(day_item.get("DPP", 0))
        st.session_state.in_dap    = int(day_item.get("DAP", 0))
        st.session_state.in_tap    = int(day_item.get("TAP", 0))

        # Källor
        st.session_state.in_pappan  = int(day_item.get("Pappans vänner", 0))
        st.session_state.in_grannar = int(day_item.get("Grannar", 0))
        st.session_state.in_nils_v  = int(day_item.get("Nils vänner", 0))
        st.session_state.in_nils_f  = int(day_item.get("Nils familj", 0))
        st.session_state.in_bekanta = int(day_item.get("Bekanta", 0))
        st.session_state.in_esk     = int(day_item.get("Eskilstuna killar", 0))

        # Bonus & Personal
        st.session_state.in_bonus_deltagit    = int(day_item.get("Bonus deltagit", 0))
        st.session_state.in_personal_deltagit = int(day_item.get("Personal deltagit", 0))

        # Övrigt
        st.session_state.in_alskar   = int(day_item.get("Älskar", 0))
        st.session_state.in_sover    = int(day_item.get("Sover med", 0))
        st.session_state.in_tid_s    = int(day_item.get("Tid S", 0))
        st.session_state.in_tid_d    = int(day_item.get("Tid D", 0))
        st.session_state.in_vila     = int(day_item.get("Vila", 0))
        st.session_state.in_dt_tid   = int(day_item.get("DT tid (sek/kille)", 0))
        st.session_state.in_dt_vila  = int(day_item.get("DT vila (sek/kille)", 0))

        # metadata
        st.session_state[SCENARIO_KEY] = "Vila i hemmet"
        st.success("Inputs fyllda från buffertdag. Inget sparat till databasen.")
        st.rerun()
else:
    st.caption("Ingen buffert ännu. Skapa via knappen **📦 Skapa buffert (Vila i hemmet – 7 dagar)** ovan.")

# -------------------------- Visa data (läser från Sheet) -----------------------
st.markdown("---")
st.subheader("📊 Aktuella data i databasen (Google Sheets)")
try:
    rows = _retry_call(sheet.get_all_records)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Inga datarader ännu.")
except Exception as e:
    st.warning(f"Kunde inte läsa data: {e}")

# ------------------------------ Ta bort rad -----------------------------------
st.subheader("🗑 Ta bort rad")
try:
    # Hämta aktuell radcount (header exkl.)
    vals = _retry_call(sheet.col_values, 1)  # Kolumn A = Datum
    current_rows = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)

    if current_rows > 0:
        idx = st.number_input("Radnummer att ta bort (1 = första dataraden)", min_value=1, max_value=current_rows, step=1, value=1)
        if st.button("Ta bort vald rad"):
            _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 för header
            st.success(f"Rad {idx} borttagen.")
            st.rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")

# ================================== SLUT ======================================
