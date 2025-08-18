# app.py — Del 1/5
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random

# ===== extern beräkning =====
try:
    from berakningar import berakna_radvarden as calc_row_values
except Exception:
    calc_row_values = None

# ===== app-setup =====
st.set_page_config(page_title="Malin – produktionsapp", layout="centered")
st.title("Malin – produktionsapp")

# ===== konstanter =====
WORKSHEET_TITLE = "Data"
SETTINGS_SHEET = "Inställningar"
DEFAULT_FEE_USD = 30.0

# ===== hjälpfunktioner =====
def _retry_call(fn, *args, **kwargs):
    """Exponential backoff för 429/RESOURCE_EXHAUSTED osv."""
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

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return float(x)
    except Exception:
        return default

def _clamp_date(d: date, lo: date, hi: date):
    if d < lo: return lo
    if d > hi: return hi
    return d

def _ms_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _hm_from_seconds(sec: int) -> str:
    h = sec // 3600
    m = round((sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _get_age_on(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))

# ===== Google Sheets-klient (init – men vi läser/sparar först när vi verkligen behöver) =====
@st.cache_resource(show_spinner=False)
def _get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def _get_spreadsheet():
    client = _get_client()
    sid = (st.secrets.get("GOOGLE_SHEET_ID","") or "").strip()
    url = (st.secrets.get("SHEET_URL","") or "").strip()
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
    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

def _get_worksheet(title: str):
    """Hämtar exakt det blad vi ber om; skapar om saknas. (Anropas sparsamt.)"""
    ss = _get_spreadsheet()
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=2000 if title==WORKSHEET_TITLE else 200, cols=80)
        if title == SETTINGS_SHEET:
            _retry_call(ws.update, "A1:C1", [["Key","Value","Label"]])
            defaults = [
                ["startdatum", date.today().isoformat(), ""],
                ["starttid", "07:00", ""],
                ["födelsedatum", date(1990,1,1).isoformat(), "Malins födelsedatum"],
                ["MAX_PAPPAN", "10", "Pappans vänner"],
                ["MAX_GRANNAR", "10", "Grannar"],
                ["MAX_NILS_VANNER", "10", "Nils vänner"],
                ["MAX_NILS_FAMILJ", "10", "Nils familj"],
                ["MAX_BEKANTA", "10", "Bekanta"],
                ["avgift_usd", str(DEFAULT_FEE_USD), "Avgift (USD, per rad)"],
                ["PROD_STAFF", "800", "Produktionspersonal (fast)"],

                # etiketter
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
            _retry_call(ws.update, f"A2:C{len(defaults)+1}", defaults)
        return ws

# ===== Läs/skriv Inställningar (anropas on-demand, inte vid varje widgetändring) =====
def _read_settings() -> tuple[dict, dict]:
    ws = _get_worksheet(SETTINGS_SHEET)
    rows = _retry_call(ws.get_all_records)  # [{Key,Value,Label}, ...]
    raw = {}
    labels = {}
    for r in rows:
        k = (r.get("Key") or "").strip()
        if not k:
            continue
        raw[k] = r.get("Value")
        lab = r.get("Label")
        if lab is not None:
            labels[k] = str(lab)
        if k.startswith("LABEL_"):
            cname = k[len("LABEL_"):]
            if str(r.get("Value") or "").strip():
                labels[cname] = str(r.get("Value")).strip()
    return raw, labels

def _save_setting(key: str, value: str, label: str|None=None):
    ws = _get_worksheet(SETTINGS_SHEET)
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

def _label(labels_map: dict, default_text: str) -> str:
    return labels_map.get(default_text, default_text)

# ===== Global konfig i sessionen (hämtas EN gång nu, sen sparas på ”Spara inställningar”) =====
if "CFG" not in st.session_state:
    CFG_RAW, LABELS = _read_settings()
    C = {}

    def _get(k, fallback): return CFG_RAW.get(k, fallback)

    # datum/tid
    try:
        C["startdatum"] = datetime.fromisoformat(_get("startdatum", date.today().isoformat())).date()
    except Exception:
        C["startdatum"] = date.today()
    try:
        hh, mm = str(_get("starttid", "07:00")).split(":")
        C["starttid"] = time(int(hh), int(mm))
    except Exception:
        C["starttid"] = time(7,0)
    try:
        C["födelsedatum"] = datetime.fromisoformat(_get("födelsedatum", "1990-01-01")).date()
    except Exception:
        C["födelsedatum"] = date(1990,1,1)

    # hårda värden
    C["MAX_PAPPAN"]      = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]     = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"] = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"] = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]     = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]      = float(_get("avgift_usd", DEFAULT_FEE_USD))
    C["PROD_STAFF"]      = int(float(_get("PROD_STAFF", 800)))

    # etiketter
    C["LABELS"] = LABELS

    # app-övergripande UI-inställningar (lagras bara i sessionen):
    # 1) procent personal som deltar (default 10%)
    st.session_state.setdefault("personal_percent", 10.0)
    # 2) intervall för Eskilstuna-killar (default 20–40)
    st.session_state.setdefault("eskilstuna_min", 20)
    st.session_state.setdefault("eskilstuna_max", 40)

    # placeholder för sheets header (hämtas/sätts först när vi sparar)
    st.session_state["COLUMNS"] = None

    st.session_state["CFG"] = C

CFG = st.session_state["CFG"]
LABELS = CFG["LABELS"]

# ===== Meny (Produktion/Statistik) + val av scenario utan att skriva till sheets =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

st.sidebar.header("⚙️ Inställningar (persistenta)")
with st.sidebar.expander("Grund & etiketter", expanded=False):
    startdatum_ui = st.date_input("Historiskt startdatum", value=_clamp_date(CFG["startdatum"], date(1990,1,1), date(2100,1,1)))
    starttid_ui   = st.time_input("Starttid", value=CFG["starttid"])
    fodd_ui       = st.date_input(_label(LABELS, "Malins födelsedatum"), value=_clamp_date(CFG["födelsedatum"], date(1970,1,1), date.today()))

    max_p  = st.number_input(f"Max {_label(LABELS,'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_label(LABELS,'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_label(LABELS,'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_label(LABELS,'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_label(LABELS,'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))
    prod_staff_ui = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    fee_ui = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    st.markdown("**Etiketter (visning – påverkar inte beräkningar)**")
    lab_p  = st.text_input("Etikett: Pappans vänner", value=LABELS.get("Pappans vänner","Pappans vänner"))
    lab_g  = st.text_input("Etikett: Grannar", value=LABELS.get("Grannar","Grannar"))
    lab_nv = st.text_input("Etikett: Nils vänner", value=LABELS.get("Nils vänner","Nils vänner"))
    lab_nf = st.text_input("Etikett: Nils familj", value=LABELS.get("Nils familj","Nils familj"))
    lab_bk = st.text_input("Etikett: Bekanta", value=LABELS.get("Bekanta","Bekanta"))
    lab_esk= st.text_input("Etikett: Eskilstuna killar", value=LABELS.get("Eskilstuna killar","Eskilstuna killar"))
    lab_man= st.text_input("Etikett: Män", value=LABELS.get("Män","Män"))
    lab_sva= st.text_input("Etikett: Svarta", value=LABELS.get("Svarta","Svarta"))
    lab_kann=st.text_input("Etikett: Känner", value=LABELS.get("Känner","Känner"))
    lab_person=st.text_input("Etikett: Personal deltagit", value=LABELS.get("Personal deltagit","Personal deltagit"))
    lab_bonus =st.text_input("Etikett: Bonus killar", value=LABELS.get("Bonus killar","Bonus killar"))
    lab_bonusd=st.text_input("Etikett: Bonus deltagit", value=LABELS.get("Bonus deltagit","Bonus deltagit"))
    lab_mfd   = st.text_input("Etikett: Malins födelsedatum", value=LABELS.get("Malins födelsedatum","Malins födelsedatum"))

    if st.button("💾 Spara inställningar"):
        # skriv först när man klickar
        _save_setting("startdatum", startdatum_ui.isoformat(), lab_mfd)
        _save_setting("starttid", starttid_ui.strftime("%H:%M"))
        _save_setting("födelsedatum", fodd_ui.isoformat(), lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), lab_bk)
        _save_setting("PROD_STAFF", str(int(prod_staff_ui)))
        _save_setting("avgift_usd", str(float(fee_ui)))

        _save_setting("LABEL_Eskilstuna killar", lab_esk, "")
        _save_setting("LABEL_Män", lab_man, "")
        _save_setting("LABEL_Svarta", lab_sva, "")
        _save_setting("LABEL_Känner", lab_kann, "")
        _save_setting("LABEL_Personal deltagit", lab_person, "")
        _save_setting("LABEL_Bonus killar", lab_bonus, "")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, "")

        # uppdatera sessionens CFG direkt
        CFG.update({
            "startdatum": startdatum_ui,
            "starttid": starttid_ui,
            "födelsedatum": fodd_ui,
            "MAX_PAPPAN": int(max_p),
            "MAX_GRANNAR": int(max_g),
            "MAX_NILS_VANNER": int(max_nv),
            "MAX_NILS_FAMILJ": int(max_nf),
            "MAX_BEKANTA": int(max_bk),
            "PROD_STAFF": int(prod_staff_ui),
            "avgift_usd": float(fee_ui),
        })
        CFG["LABELS"].update({
            "Pappans vänner": lab_p, "Grannar": lab_g, "Nils vänner": lab_nv, "Nils familj": lab_nf,
            "Bekanta": lab_bk, "Eskilstuna killar": lab_esk, "Män": lab_man, "Svarta": lab_sva,
            "Känner": lab_kann, "Personal deltagit": lab_person, "Bonus killar": lab_bonus,
            "Bonus deltagit": lab_bonusd, "Malins födelsedatum": lab_mfd
        })
        st.success("Inställningar sparade ✅")
        st.rerun()

st.sidebar.header("🎛️ Live-parametrar (session)")
# exaktför inmatning (ingen dubblett av element-id)
pp = st.sidebar.number_input("Personal som deltar (%)", min_value=0.0, max_value=100.0, step=0.1,
                             value=float(st.session_state.personal_percent), key="personal_percent")
em = st.sidebar.number_input("Eskilstuna killar – min", min_value=0, step=1,
                             value=int(st.session_state.eskilstuna_min), key="eskilstuna_min")
ex = st.sidebar.number_input("Eskilstuna killar – max", min_value=0, step=1,
                             value=int(st.session_state.eskilstuna_max), key="eskilstuna_max")

# ===== scenario-väljare (inget sheets-anrop här) =====
SCENARIO_OPTIONS = ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet", "Vila på jobbet"]
scenario = st.selectbox("Välj scenario", SCENARIO_OPTIONS, index=0, key="scenario_select")

# app.py — Del 2/5
# ======= Input-fält (i rätt ordning) + "Hämta värden" för scenario =======

# --- stable widget keys (så vi inte råkar ändra ordning/namn) ---
IN_KEYS = {
    "man": "in_man",
    "svarta": "in_svarta",
    "fitta": "in_fitta",
    "rumpa": "in_rumpa",
    "dp": "in_dp",
    "dpp": "in_dpp",
    "dap": "in_dap",
    "tap": "in_tap",
    "pappan": "in_pappan",
    "grannar": "in_grannar",
    "nils_v": "in_nils_vanner",
    "nils_f": "in_nils_familj",
    "bekanta": "in_bekanta",
    "eskilstuna": "in_eskilstuna",
    "bonus_deltagit": "in_bonus_deltagit",
    "personal": "in_personal",
    "alskar": "in_alskar",
    "sover": "in_sover",
    "tid_s": "in_tid_s",
    "tid_d": "in_tid_d",
    "vila": "in_vila",
    "dt_tid": "in_dt_tid",
    "dt_vila": "in_dt_vila",
    "avgift": "in_avgift",
    "nils": "in_nils",
}

# --- init av sessionens inputstandard (görs en gång) ---
def _init_inputs_once():
    ss = st.session_state
    def setdef(k, v):
        if k not in ss: ss[k] = v

    setdef(IN_KEYS["man"], 0)
    setdef(IN_KEYS["svarta"], 0)
    setdef(IN_KEYS["fitta"], 0)
    setdef(IN_KEYS["rumpa"], 0)
    setdef(IN_KEYS["dp"], 0)
    setdef(IN_KEYS["dpp"], 0)
    setdef(IN_KEYS["dap"], 0)
    setdef(IN_KEYS["tap"], 0)
    setdef(IN_KEYS["pappan"], 0)
    setdef(IN_KEYS["grannar"], 0)
    setdef(IN_KEYS["nils_v"], 0)
    setdef(IN_KEYS["nils_f"], 0)
    setdef(IN_KEYS["bekanta"], 0)
    setdef(IN_KEYS["eskilstuna"], 0)
    setdef(IN_KEYS["bonus_deltagit"], 0)

    # personal följer procent av PROD_STAFF (avrundat)
    setdef(IN_KEYS["personal"], int(round(CFG["PROD_STAFF"] * (st.session_state.personal_percent/100.0))))

    setdef(IN_KEYS["alskar"], 0)
    setdef(IN_KEYS["sover"], 0)
    setdef(IN_KEYS["tid_s"], 60)
    setdef(IN_KEYS["tid_d"], 60)
    setdef(IN_KEYS["vila"], 7)
    setdef(IN_KEYS["dt_tid"], 60)
    setdef(IN_KEYS["dt_vila"], 3)
    setdef(IN_KEYS["avgift"], float(CFG["avgift_usd"]))
    setdef(IN_KEYS["nils"], 0)

    # container för ”Vila i hemmet”-veckan (lista av 7 rader)
    setdef("home_week_rows", None)
    setdef("home_week_index", 0)   # aktiv dag i förhandsvisning

_init_inputs_once()

# --- min/max-hämtning per kolumn (läser sheets ENDAST när knappen trycks) ---
def _get_min_max(colname: str) -> tuple[int,int]:
    try:
        ws = _get_worksheet(WORKSHEET_TITLE)
        rows = _retry_call(ws.get_all_records)
    except Exception:
        return (0, 0)
    vals = []
    for r in rows:
        vals.append(_safe_int(r.get(colname, 0), 0))
    if not vals:
        return (0, 0)
    return (min(vals), max(vals))

def _rand_between_col(colname: str) -> int:
    lo, hi = _get_min_max(colname)
    if hi < lo: return 0
    return random.randint(lo, hi)

def _rand_eskilstuna_from_sidebar_rng() -> int:
    lo = int(st.session_state.eskilstuna_min)
    hi = int(st.session_state.eskilstuna_max)
    if hi < lo: hi = lo
    return random.randint(lo, hi)

def _set_inputs_from_dict(d: dict):
    """Sätter sessionens inputfält från en dict med nycklar i IN_KEYS-värden."""
    for key, value in d.items():
        st.session_state[key] = value

# --- Hämta värden enligt scenario (fyller inputs, ingen sparning) ---
def apply_scenario_fill():
    scen = st.session_state.get("scenario_select", "Ny scen")
    # default-personal enligt procent – gäller alla scenarier,
    # förutom "Slumpa scen svart" där personal=0 enligt senaste krav.
    personal_auto = int(round(CFG["PROD_STAFF"] * (st.session_state.personal_percent/100.0)))

    # gemensam grund
    base = {
        IN_KEYS["man"]: 0,
        IN_KEYS["svarta"]: 0,
        IN_KEYS["fitta"]: 0,
        IN_KEYS["rumpa"]: 0,
        IN_KEYS["dp"]: 0,
        IN_KEYS["dpp"]: 0,
        IN_KEYS["dap"]: 0,
        IN_KEYS["tap"]: 0,
        IN_KEYS["pappan"]: 0,
        IN_KEYS["grannar"]: 0,
        IN_KEYS["nils_v"]: 0,
        IN_KEYS["nils_f"]: 0,
        IN_KEYS["bekanta"]: 0,
        IN_KEYS["eskilstuna"]: 0,
        IN_KEYS["bonus_deltagit"]: 0,   # sätts nedan
        IN_KEYS["personal"]: personal_auto,
        IN_KEYS["alskar"]: 0,
        IN_KEYS["sover"]: 0,
        IN_KEYS["tid_s"]: st.session_state[IN_KEYS["tid_s"]],
        IN_KEYS["tid_d"]: st.session_state[IN_KEYS["tid_d"]],
        IN_KEYS["vila"]: st.session_state[IN_KEYS["vila"]],
        IN_KEYS["dt_tid"]: st.session_state[IN_KEYS["dt_tid"]],
        IN_KEYS["dt_vila"]: st.session_state[IN_KEYS["dt_vila"]],
        IN_KEYS["avgift"]: st.session_state[IN_KEYS["avgift"]],
        IN_KEYS["nils"]: st.session_state[IN_KEYS["nils"]],
    }

    # BONUS_DELTAGIT – 40% av ”bonus killar” (vi utgår från BONUS_LEFT i Settings om den finns),
    # men eftersom vi inte läser den vid varje render, räknar vi här konservativt
    # genom att försöka hitta en historisk kolumn ”Bonus killar” och göra 40% av dess max (fallback 0).
    def _estimate_bonus_deltagit_40pct() -> int:
        try:
            lo, hi = _get_min_max("Bonus killar")
            if hi <= 0:
                return 0
            return max(0, int(round(hi * 0.40)))
        except Exception:
            return 0

    if scen == "Ny scen":
        # bara fyll i standardvärden + personal-procent
        # Bonus deltagit ska visas som eget fält -> sätt 40% uppskattning
        base[IN_KEYS["bonus_deltagit"]] = _estimate_bonus_deltagit_40pct()

    elif scen == "Slumpa scen vit":
        # slumpa mellan min/max från historik
        base.update({
            IN_KEYS["man"]: _rand_between_col("Män"),
            IN_KEYS["svarta"]: 0,
            IN_KEYS["fitta"]: _rand_between_col("Fitta"),
            IN_KEYS["rumpa"]: _rand_between_col("Rumpa"),
            IN_KEYS["dp"]: _rand_between_col("DP"),
            IN_KEYS["dpp"]: _rand_between_col("DPP"),
            IN_KEYS["dap"]: _rand_between_col("DAP"),
            IN_KEYS["tap"]: _rand_between_col("TAP"),
            IN_KEYS["pappan"]: _rand_between_col("Pappans vänner"),
            IN_KEYS["grannar"]: _rand_between_col("Grannar"),
            IN_KEYS["nils_v"]: _rand_between_col("Nils vänner"),
            IN_KEYS["nils_f"]: _rand_between_col("Nils familj"),
            IN_KEYS["bekanta"]: _rand_between_col("Bekanta"),
            IN_KEYS["eskilstuna"]: _rand_between_col("Eskilstuna killar"),
            IN_KEYS["alskar"]: 8,
            IN_KEYS["sover"]: 1,
        })
        base[IN_KEYS["bonus_deltagit"]] = _estimate_bonus_deltagit_40pct()
        # personal följer procentsatsen
        base[IN_KEYS["personal"]] = personal_auto

    elif scen == "Slumpa scen svart":
        # alla källor 0 utom Svarta + sex/akt-fält slumpas, personal=0 (spec)
        base.update({
            IN_KEYS["man"]: 0,
            IN_KEYS["svarta"]: _rand_between_col("Svarta"),
            IN_KEYS["fitta"]: _rand_between_col("Fitta"),
            IN_KEYS["rumpa"]: _rand_between_col("Rumpa"),
            IN_KEYS["dp"]: _rand_between_col("DP"),
            IN_KEYS["dpp"]: _rand_between_col("DPP"),
            IN_KEYS["dap"]: _rand_between_col("DAP"),
            IN_KEYS["tap"]: _rand_between_col("TAP"),
            IN_KEYS["pappan"]: 0,
            IN_KEYS["grannar"]: 0,
            IN_KEYS["nils_v"]: 0,
            IN_KEYS["nils_f"]: 0,
            IN_KEYS["bekanta"]: 0,
            IN_KEYS["eskilstuna"]: 0,
            IN_KEYS["alskar"]: 8,
            IN_KEYS["sover"]: 1,
            IN_KEYS["personal"]: 0,  # viktig ändring
        })
        base[IN_KEYS["bonus_deltagit"]] = _estimate_bonus_deltagit_40pct()

    elif scen == "Vila på jobbet":
        # slumpa sex/akt-kolumner inom historiskt min/max
        base.update({
            IN_KEYS["fitta"]: _rand_between_col("Fitta"),
            IN_KEYS["rumpa"]: _rand_between_col("Rumpa"),
            IN_KEYS["dp"]: _rand_between_col("DP"),
            IN_KEYS["dpp"]: _rand_between_col("DPP"),
            IN_KEYS["dap"]: _rand_between_col("DAP"),
            IN_KEYS["tap"]: _rand_between_col("TAP"),
            IN_KEYS["alskar"]: 12,
            IN_KEYS["sover"]: 1,
        })
        # källor (män/känner/svarta etc) kan vara 0 här
        base[IN_KEYS["bonus_deltagit"]] = _estimate_bonus_deltagit_40pct()
        base[IN_KEYS["personal"]] = personal_auto

    elif scen == "Vila i hemmet":
        # Genererar 7 dagar till sessionen (home_week_rows); här fyller vi inputs med dag 1
        week = []
        # För slump – använd samma slumpade tal för Fitta/Rumpa/DP/DPP/DAP/TAP över alla dagar
        f_val  = _rand_between_col("Fitta")
        r_val  = _rand_between_col("Rumpa")
        dp_val = _rand_between_col("DP")
        dpp_v  = _rand_between_col("DPP")
        dap_v  = _rand_between_col("DAP")
        tap_v  = _rand_between_col("TAP")
        bonus40 = _estimate_bonus_deltagit_40pct()

        for i in range(7):
            # Dag 1–5: personal enligt procent, Dag 6–7: 0 (spec)
            pers = personal_auto if i <= 4 else 0
            rowi = {
                IN_KEYS["man"]: 0,
                IN_KEYS["svarta"]: 0,
                IN_KEYS["fitta"]: f_val,
                IN_KEYS["rumpa"]: r_val,
                IN_KEYS["dp"]: dp_val,
                IN_KEYS["dpp"]: dpp_v,
                IN_KEYS["dap"]: dap_v,
                IN_KEYS["tap"]: tap_v,
                IN_KEYS["pappan"]: 0,
                IN_KEYS["grannar"]: 0,
                IN_KEYS["nils_v"]: 0,
                IN_KEYS["nils_f"]: 0,
                IN_KEYS["bekanta"]: 0,
                IN_KEYS["eskilstuna"]: _rand_eskilstuna_from_sidebar_rng(),
                IN_KEYS["bonus_deltagit"]: bonus40,
                IN_KEYS["personal"]: pers,
                IN_KEYS["alskar"]: 6,
                IN_KEYS["sover"]: 1 if i == 6 else 0,
                IN_KEYS["tid_s"]: st.session_state[IN_KEYS["tid_s"]],
                IN_KEYS["tid_d"]: st.session_state[IN_KEYS["tid_d"]],
                IN_KEYS["vila"]: st.session_state[IN_KEYS["vila"]],
                IN_KEYS["dt_tid"]: st.session_state[IN_KEYS["dt_tid"]],
                IN_KEYS["dt_vila"]: st.session_state[IN_KEYS["dt_vila"]],
                IN_KEYS["avgift"]: st.session_state[IN_KEYS["avgift"]],
                IN_KEYS["nils"]: 0 if i == 6 else (1 if random.random() < 0.2 else 0),
            }
            week.append(rowi)

        st.session_state.home_week_rows = week
        st.session_state.home_week_index = 0
        # lägg in dag 1 i input-fälten
        base.update(week[0])

    # applicera valda värden i sessionens inputs
    _set_inputs_from_dict(base)
    st.success("Värden hämtade ✔️ (ingen sparning gjord).")

# --------- UI: Själva input-fälten i den ordning du önskar ---------
st.subheader("➕ Lägg till / justera scen (inputs)")

# Kolumnlayout som bara grupperar visuellt – ordningen nedan är exakt den du bad om.
c1, c2, c3, c4 = st.columns(4)

# 1–8
with c1:
    st.number_input(LABELS.get("Män","Män"), min_value=0, step=1, key=IN_KEYS["man"])
    st.number_input("Fitta", min_value=0, step=1, key=IN_KEYS["fitta"])
    st.number_input("DP", min_value=0, step=1, key=IN_KEYS["dp"])
    st.number_input("DAP", min_value=0, step=1, key=IN_KEYS["dap"])
with c2:
    st.number_input(LABELS.get("Svarta","Svarta"), min_value=0, step=1, key=IN_KEYS["svarta"])
    st.number_input("Rumpa", min_value=0, step=1, key=IN_KEYS["rumpa"])
    st.number_input("DPP", min_value=0, step=1, key=IN_KEYS["dpp"])
    st.number_input("TAP", min_value=0, step=1, key=IN_KEYS["tap"])

# 9–13
with c3:
    st.number_input(LABELS.get("Pappans vänner","Pappans vänner"), min_value=0, step=1, key=IN_KEYS["pappan"])
    st.number_input(LABELS.get("Nils vänner","Nils vänner"), min_value=0, step=1, key=IN_KEYS["nils_v"])
    st.number_input(LABELS.get("Bekanta","Bekanta"), min_value=0, step=1, key=IN_KEYS["bekanta"])
with c4:
    st.number_input(LABELS.get("Grannar","Grannar"), min_value=0, step=1, key=IN_KEYS["grannar"])
    st.number_input(LABELS.get("Nils familj","Nils familj"), min_value=0, step=1, key=IN_KEYS["nils_f"])
    st.number_input(LABELS.get("Eskilstuna killar","Eskilstuna killar"), min_value=0, step=1, key=IN_KEYS["eskilstuna"])

# 14–16
d1, d2, d3 = st.columns(3)
with d1:
    st.number_input(LABELS.get("Bonus deltagit","Bonus deltagit"), min_value=0, step=1, key=IN_KEYS["bonus_deltagit"])
with d2:
    st.number_input(LABELS.get("Personal deltagit","Personal deltagit"), min_value=0, step=1, key=IN_KEYS["personal"])
with d3:
    st.number_input("Älskar", min_value=0, step=1, key=IN_KEYS["alskar"])

# 17–23
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.number_input("Sover med (0/1)", min_value=0, max_value=1, step=1, key=IN_KEYS["sover"])
with e2:
    st.number_input("Tid S (sek)", min_value=0, step=1, key=IN_KEYS["tid_s"])
with e3:
    st.number_input("Tid D (sek)", min_value=0, step=1, key=IN_KEYS["tid_d"])
with e4:
    st.number_input("Vila (sek)", min_value=0, step=1, key=IN_KEYS["vila"])

f1, f2 = st.columns(2)
with f1:
    st.number_input("DT tid (sek/kille)", min_value=0, step=1, key=IN_KEYS["dt_tid"])
with f2:
    st.number_input("DT vila (sek/kille)", min_value=0, step=1, key=IN_KEYS["dt_vila"])

# Övrigt som fanns (avgift & nils)
g1, g2 = st.columns(2)
with g1:
    st.number_input("Avgift (USD, per rad)", min_value=0.0, step=1.0, key=IN_KEYS["avgift"])
with g2:
    st.number_input("Nils", min_value=0, step=1, key=IN_KEYS["nils"])

# Knapp för att fylla fälten utifrån vald scenario
if st.button("🔄 Hämta värden enligt val"):
    apply_scenario_fill()

# app.py — Del 3/5
# ======= Live-beräkningar / Preview (utan sparning) =======

# Hjälp: hämta sceninfo (Del 1 definierade datum_och_veckodag_för_scen + ROW_COUNT)
def _current_scene_info():
    scen = st.session_state.get(ROW_COUNT_KEY, 0) + 1
    d, veckodag = datum_och_veckodag_för_scen(scen)
    return scen, d, veckodag

scen, rad_datum, veckodag = _current_scene_info()

# Om vi är i "Vila i hemmet": visa navigator (dag 1–7) + fyll inputs automatiskt
if st.session_state.get("scenario_select") == "Vila i hemmet" and st.session_state.get("home_week_rows"):
    cols_nav = st.columns([1,3,1,1,1])
    with cols_nav[1]:
        st.caption("Förhandsvisning: dag i veckan (Vila i hemmet)")
    with cols_nav[2]:
        if st.button("◀️ Föregående dag", key="home_prev"):
            st.session_state.home_week_index = max(0, st.session_state.home_week_index - 1)
    with cols_nav[3]:
        st.write(f"Dag {st.session_state.home_week_index+1}/7")
    with cols_nav[4]:
        if st.button("Nästa dag ▶️", key="home_next"):
            st.session_state.home_week_index = min(6, st.session_state.home_week_index + 1)

    # lägg vald dags värden i inputs (utan att spara)
    _set_inputs_from_dict(st.session_state.home_week_rows[st.session_state.home_week_index])

# Bygg grunddict till beräkning från inputs
grund_preview = {
    "Typ": st.session_state.get("scenario_select", "Ny scen"),
    "Veckodag": veckodag,
    "Scen": scen,

    # Inputfält (Del 2)
    "Män": st.session_state[IN_KEYS["man"]],
    "Svarta": st.session_state[IN_KEYS["svarta"]],
    "Fitta": st.session_state[IN_KEYS["fitta"]],
    "Rumpa": st.session_state[IN_KEYS["rumpa"]],
    "DP": st.session_state[IN_KEYS["dp"]],
    "DPP": st.session_state[IN_KEYS["dpp"]],
    "DAP": st.session_state[IN_KEYS["dap"]],
    "TAP": st.session_state[IN_KEYS["tap"]],
    "Pappans vänner": st.session_state[IN_KEYS["pappan"]],
    "Grannar": st.session_state[IN_KEYS["grannar"]],
    "Nils vänner": st.session_state[IN_KEYS["nils_v"]],
    "Nils familj": st.session_state[IN_KEYS["nils_f"]],
    "Bekanta": st.session_state[IN_KEYS["bekanta"]],
    "Eskilstuna killar": st.session_state[IN_KEYS["eskilstuna"]],
    "Bonus deltagit": st.session_state[IN_KEYS["bonus_deltagit"]],
    "Personal deltagit": st.session_state[IN_KEYS["personal"]],
    "Älskar": st.session_state[IN_KEYS["alskar"]],
    "Sover med": st.session_state[IN_KEYS["sover"]],
    "Tid S": st.session_state[IN_KEYS["tid_s"]],
    "Tid D": st.session_state[IN_KEYS["tid_d"]],
    "Vila": st.session_state[IN_KEYS["vila"]],
    "DT tid (sek/kille)": st.session_state[IN_KEYS["dt_tid"]],
    "DT vila (sek/kille)": st.session_state[IN_KEYS["dt_vila"]],
    "Avgift": float(st.session_state[IN_KEYS["avgift"]]),
    "Nils": st.session_state[IN_KEYS["nils"]],

    # Viktigt: hel personalstyrka för lönebasen
    "PROD_STAFF": int(CFG["PROD_STAFF"]),
}

# Anropa beräkning (extern modul)
preview = {}
try:
    if callable(calc_row_values):
        # OBS: funktionen tar parameternamnet 'foddatum' (ej fodelsedatum) och 'starttid'
        preview = calc_row_values(
            grund_preview,
            rad_datum=rad_datum,
            foddatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
        ) or {}
    else:
        st.warning("Hittar inte berakningar.py / berakna_radvarden().")
except TypeError as e:
    st.error(f"Förhandsberäkning misslyckades: {e}")
except Exception as e:
    st.error(f"Förhandsberäkning misslyckades: {e}")

# Visning: rubrik
st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

# Ålder
try:
    age = rad_datum.year - CFG["födelsedatum"].year - (
        (rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day)
    )
except Exception:
    age = "-"

# Toppmetrik
c_top = st.columns(3)
with c_top[0]:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
with c_top[1]:
    st.metric("Ålder (år)", age)
with c_top[2]:
    st.metric("Klockan (slut)", preview.get("Klockan", "-"))

# Tider
c_time = st.columns(4)
with c_time[0]:
    st.metric("Summa tid", preview.get("Summa tid", "-"))
with c_time[1]:
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
with c_time[2]:
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
with c_time[3]:
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))

# Hångel & Suger
c_hs = st.columns(3)
with c_hs[0]:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with c_hs[1]:
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c_hs[2]:
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

# Totalt män + Känner (radnivå)
c_men = st.columns(2)
with c_men[0]:
    st.metric("Totalt Män (raden)", int(preview.get("Totalt Män", 0)))
with c_men[1]:
    st.metric("Känner (rad)", int(preview.get("Känner", 0)))

# Ekonomi live
st.markdown("#### 💵 Ekonomi (live)")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", grund_preview["Avgift"])))
with e2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with e3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with e4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet", 0)))

# Extra debug/info (kan döljas vid behov)
with st.expander("Beräkningsdetaljer (debug)", expanded=False):
    st.json({
        "Input (kort)": {
            "Män": grund_preview["Män"], "Svarta": grund_preview["Svarta"],
            "Bekanta": grund_preview["Bekanta"], "Eskilstuna": grund_preview["Eskilstuna killar"],
            "Bonus deltagit": grund_preview["Bonus deltagit"], "Personal deltagit": grund_preview["Personal deltagit"],
            "Älskar": grund_preview["Älskar"], "Sover med": grund_preview["Sover med"],
            "Tid S": grund_preview["Tid S"], "Tid D": grund_preview["Tid D"], "Vila": grund_preview["Vila"],
            "DT tid": grund_preview["DT tid (sek/kille)"], "DT vila": grund_preview["DT vila (sek/kille)"],
            "Avgift": grund_preview["Avgift"], "PROD_STAFF": grund_preview["PROD_STAFF"],
        },
        "Preview (kort)": {
            "Summa tid (sek)": preview.get("Summa tid (sek)", 0),
            "Tid Älskar (sek)": preview.get("Tid Älskar (sek)", 0),
            "Tid Sover med (sek)": preview.get("Tid Sover med (sek)", 0),
            "Totalt Män": preview.get("Totalt Män", 0),
            "Prenumeranter": preview.get("Prenumeranter", 0),
            "Hårdhet": preview.get("Hårdhet", 0),
        }
    })

# app.py — Del 4/5
# ======= Spara / Auto-max / Batch-spara (Vila i hemmet) =======

# Hjälp: bygg en "grund"-rad (rådata) från aktuella inputfält
def _row_from_inputs(typ_label: str, scen_num: int, veckodag: str):
    return {
        "Typ": typ_label,
        "Veckodag": veckodag,
        "Scen": scen_num,

        "Män": st.session_state[IN_KEYS["man"]],
        "Svarta": st.session_state[IN_KEYS["svarta"]],
        "Fitta": st.session_state[IN_KEYS["fitta"]],
        "Rumpa": st.session_state[IN_KEYS["rumpa"]],
        "DP": st.session_state[IN_KEYS["dp"]],
        "DPP": st.session_state[IN_KEYS["dpp"]],
        "DAP": st.session_state[IN_KEYS["dap"]],
        "TAP": st.session_state[IN_KEYS["tap"]],

        "Pappans vänner": st.session_state[IN_KEYS["pappan"]],
        "Grannar": st.session_state[IN_KEYS["grannar"]],
        "Nils vänner": st.session_state[IN_KEYS["nils_v"]],
        "Nils familj": st.session_state[IN_KEYS["nils_f"]],
        "Bekanta": st.session_state[IN_KEYS["bekanta"]],
        "Eskilstuna killar": st.session_state[IN_KEYS["eskilstuna"]],

        "Bonus deltagit": st.session_state[IN_KEYS["bonus_deltagit"]],
        "Personal deltagit": st.session_state[IN_KEYS["personal"]],

        "Älskar": st.session_state[IN_KEYS["alskar"]],
        "Sover med": st.session_state[IN_KEYS["sover"]],

        "Tid S": st.session_state[IN_KEYS["tid_s"]],
        "Tid D": st.session_state[IN_KEYS["tid_d"]],
        "Vila": st.session_state[IN_KEYS["vila"]],
        "DT tid (sek/kille)": st.session_state[IN_KEYS["dt_tid"]],
        "DT vila (sek/kille)": st.session_state[IN_KEYS["dt_vila"]],

        "Avgift": float(st.session_state[IN_KEYS["avgift"]]),
        "Nils": st.session_state[IN_KEYS["nils"]],
        # Lönekalkyl ska alltid baseras på hela personalstyrkan:
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
    }

# Kör beräkningen inför sparning (samma som preview men with typ/rad_datum)
def _calc_for_save(grund: dict, d: date):
    if not callable(calc_row_values):
        st.error("Hittar inte berakningar.py / berakna_radvarden().")
        return None
    try:
        return calc_row_values(
            grund,
            rad_datum=d,
            foddatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
        )
    except Exception as e:
        st.error(f"Beräkning vid sparning misslyckades: {e}")
        return None

# Faktisk skrivning av en rad till Data
def _append_computed_row_to_sheet(ber: dict):
    # Se till att alla kolumner finns och lägg i rätt ordning
    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)

# Auto-max hjälp
def _collect_over_max(grund: dict):
    over = {}
    def _chk(field, max_key):
        val = int(grund.get(field, 0) or 0)
        mx = int(CFG[max_key])
        if val > mx:
            over[field] = {"current_max": mx, "new_value": val, "max_key": max_key}
    _chk("Pappans vänner", "MAX_PAPPAN")
    _chk("Grannar", "MAX_GRANNAR")
    _chk("Nils vänner", "MAX_NILS_VANNER")
    _chk("Nils familj", "MAX_NILS_FAMILJ")
    _chk("Bekanta", "MAX_BEKANTA")
    return over

def _apply_auto_max(over: dict):
    # Uppdaterar fliken Inställningar och lokal CFG
    for _, info in over.items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))
        CFG[key] = new_val

# Spara EN rad (”Ny scen”, ”Slumpa…”, ”Vila på jobbet”, eller en vald dag från ”Vila i hemmet”)
def _save_single_row(typ_label: str):
    scen_num, d, veckodag = _current_scene_info()
    grund = _row_from_inputs(typ_label, scen_num, veckodag)

    # Auto-max-koll
    over_max = _collect_over_max(grund)
    if over_max:
        st.session_state["PENDING_SAVE"] = {
            "mode": "single",
            "grund": grund,
            "date": d.isoformat(),
            "over_max": over_max,
        }
        return  # visa dialogen nedanför

    ber = _calc_for_save(grund, d)
    if not ber:
        return
    ber["Datum"] = d.isoformat()

    # Skriv
    _append_computed_row_to_sheet(ber)

    # Uppdatera row counter
    st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1

    # Klarsignal
    st.success(f"✅ Rad sparad ({typ_label}) – {d} ({ber.get('Klockan','-')}).")
    st.rerun()

# Batch-spara 7 dagar ”Vila i hemmet” (från st.session_state.home_week_rows)
def _save_home_week():
    if not st.session_state.get("home_week_rows"):
        st.warning("Inga 7-dagarsvärden laddade.")
        return

    # Bygg 7 beräknade rader i ordning
    scen_start = st.session_state.get(ROW_COUNT_KEY, 0) + 1
    to_write = []
    for i, base in enumerate(st.session_state.home_week_rows):
        scen_num = scen_start + i
        d, veckodag = datum_och_veckodag_för_scen(scen_num)
        # se till att PROD_STAFF följer nuvarande CFG
        base = dict(base)
        base["PROD_STAFF"] = int(CFG["PROD_STAFF"])
        base["Veckodag"] = veckodag
        base["Scen"] = scen_num

        # Auto-max per rad? Vi samlar alla överskridanden först
        over = _collect_over_max(base)
        if over:
            st.session_state["PENDING_SAVE"] = {
                "mode": "batch",
                "rows": st.session_state.home_week_rows,
                "date_start": d.isoformat(),
                "over_max": over,  # OBS: visar endast första överskridandet här (enklare UI)
            }
            return

        ber = _calc_for_save(base, d)
        if not ber:
            return
        ber["Datum"] = d.isoformat()
        to_write.append(ber)

    # Skriv alla
    for ber in to_write:
        _append_computed_row_to_sheet(ber)

    # bump counter med 7
    st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + len(to_write)

    st.success("✅ Sparade alla 7 dagar för 'Vila i hemmet'.")
    # Nollställ veckodata efter sparning
    st.session_state.home_week_rows = None
    st.session_state.home_week_index = 0
    st.rerun()

# ========== SPAR-KNAPPAR ==========
st.markdown("---")
st.subheader("💾 Spara")

left, mid, right = st.columns([1,1,2])

with left:
    if st.button("💾 Spara raden", key="save_one"):
        # Typ hämtas från scenario-select (”Ny scen”, ”Slumpa scen vit/svart”, ”Vila på jobbet”, eller ”Vila i hemmet (en vald dag)”)
        typ_label = st.session_state.get("scenario_select") or "Ny scen"
        # Om vi befinner oss i ”Vila i hemmet” men bara vill spara enstaka dag (den som visas)
        if typ_label == "Vila i hemmet" and st.session_state.get("home_week_rows"):
            typ_label = "Vila i hemmet (dag)"
        _save_single_row(typ_label)

with mid:
    # Batch-spara endast synligt i ”Vila i hemmet”-läge
    if st.session_state.get("home_week_rows"):
        if st.button("💾 Spara alla 7 dagar", key="save_week"):
            _save_home_week()

with right:
    st.caption("Ingenting sparas förrän du aktivt trycker på en av sparknapparna.")

# ========== AUTO-MAX DIALOG ==========
if "PENDING_SAVE" in st.session_state:
    pending = st.session_state["PENDING_SAVE"]
    st.warning("Värden överstiger nuvarande max. Vill du uppdatera maxvärden (Inställningar) och fortsätta spara?")
    for f, info in pending["over_max"].items():
        st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")

    cA, cB = st.columns(2)
    with cA:
        if st.button("✅ Uppdatera max & spara", key="apply_max_and_save"):
            try:
                _apply_auto_max(pending["over_max"])
                mode = pending.get("mode")
                if mode == "single":
                    d = datetime.fromisoformat(pending["date"]).date()
                    ber = _calc_for_save(pending["grund"], d)
                    if ber:
                        ber["Datum"] = d.isoformat()
                        _append_computed_row_to_sheet(ber)
                        st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1
                        st.success("✅ Rad sparad efter max-uppdatering.")
                elif mode == "batch":
                    # Kör full batch igen nu när max är uppdaterat
                    _save_home_week()
            except Exception as e:
                st.error(f"Kunde inte spara: {e}")
            finally:
                st.session_state.pop("PENDING_SAVE", None)
                st.rerun()
    with cB:
        if st.button("✋ Avbryt", key="cancel_pending_save"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbruten. Justera värden eller max i sidopanelen.")

# app.py — Del 5/5
# ======= Visa data / Radera / Diagnostik =======

st.markdown("---")
st.subheader("📄 Data – visa och uppdatera manuellt")

with st.expander("Visa/uppdatera aktuell data (hämtar från Google Sheets på begäran)", expanded=False):
    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("🔄 Hämta data nu", key="btn_fetch_data"):
            try:
                rows = _retry_call(sheet.get_all_records)
                st.session_state["LAST_DATA"] = rows
                st.session_state["LAST_FETCH_TS"] = datetime.now().isoformat(timespec="seconds")
                st.success(f"Hämtade {len(rows)} rader.")
            except Exception as e:
                st.error(f"Kunde inte läsa data: {e}")

    with col_b:
        if st.button("🧹 Töm visad cache", key="btn_clear_cache"):
            st.session_state.pop("LAST_DATA", None)
            st.session_state.pop("LAST_FETCH_TS", None)
            st.info("Cache för visad data tömd.")

    rows = st.session_state.get("LAST_DATA", [])
    ts   = st.session_state.get("LAST_FETCH_TS", "–")
    st.caption(f"Senast hämtad: {ts}")
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Ingen data i visnings-cachen. Klicka ”Hämta data nu” för att ladda från Google Sheets.")

# ======= Radera en rad (1 = första dataraden, under headern) =======
st.markdown("---")
st.subheader("🗑 Radera rad")

current_rows = st.session_state.get(ROW_COUNT_KEY, 0)
if current_rows <= 0:
    st.caption("Det finns inga datarader registrerade ännu.")
else:
    del_idx = st.number_input(
        "Radnummer att ta bort (1 = första dataraden)",
        min_value=1, max_value=current_rows, value=1, step=1, key="del_row_idx")
    if st.button("Ta bort vald rad", key="btn_delete_row"):
        try:
            # +1 för att hoppa över header-raden
            _retry_call(sheet.delete_rows, int(del_idx) + 1)
            # Uppdatera vår lokala räknare
            st.session_state[ROW_COUNT_KEY] = max(0, st.session_state.get(ROW_COUNT_KEY, 0) - 1)
            # Städa bort cachead data så den inte är inkonsistent
            st.session_state.pop("LAST_DATA", None)
            st.session_state.pop("LAST_FETCH_TS", None)
            st.success(f"Rad {int(del_idx)} borttagen.")
            st.rerun()
        except Exception as e:
            st.error(f"Kunde inte ta bort rad: {e}")

# ======= Diagnostik (frivilligt) =======
st.markdown("---")
with st.expander("🧪 Diagnostik (valfritt)", expanded=False):
    scen_num, diag_date, diag_vd = _current_scene_info()
    st.write("**Nuvarande sceninfo**")
    st.json({
        "Scen": scen_num,
        "Datum": diag_date.isoformat(),
        "Veckodag": diag_vd,
        "ROW_COUNT (lokal)": st.session_state.get(ROW_COUNT_KEY, 0),
        "Scenario-val": st.session_state.get("scenario_select", "(ej satt)"),
    })

    st.write("**Konfig/Inställningar (utdrag)**")
    st.json({
        "PROD_STAFF": CFG.get("PROD_STAFF"),
        "Eskilstuna intervall": [st.session_state.get("eskilstuna_min", 20),
                                 st.session_state.get("eskilstuna_max", 40)],
        "Bonus 30d %": st.session_state.get("bonus_percent_pren", 5.0),
        "Personal %": st.session_state.get("personal_pct", 10.0),
        "Avgift USD": CFG.get("avgift_usd"),
    })

    st.write("**Aktuella inputvärden (kort)**")
    st.json({
        "Män": st.session_state.get(IN_KEYS["man"], 0),
        "Svarta": st.session_state.get(IN_KEYS["svarta"], 0),
        "Fitta": st.session_state.get(IN_KEYS["fitta"], 0),
        "Rumpa": st.session_state.get(IN_KEYS["rumpa"], 0),
        "DP/DPP/DAP/TAP": [
            st.session_state.get(IN_KEYS["dp"], 0),
            st.session_state.get(IN_KEYS["dpp"], 0),
            st.session_state.get(IN_KEYS["dap"], 0),
            st.session_state.get(IN_KEYS["tap"], 0),
        ],
        "Känner-källor": [
            st.session_state.get(IN_KEYS["pappan"], 0),
            st.session_state.get(IN_KEYS["grannar"], 0),
            st.session_state.get(IN_KEYS["nils_v"], 0),
            st.session_state.get(IN_KEYS["nils_f"], 0),
        ],
        "Bekanta": st.session_state.get(IN_KEYS["bekanta"], 0),
        "Eskilstuna killar": st.session_state.get(IN_KEYS["eskilstuna"], 0),
        "Bonus deltagit": st.session_state.get(IN_KEYS["bonus_deltagit"], 0),
        "Personal deltagit": st.session_state.get(IN_KEYS["personal"], 0),
        "Älskar / Sover": [
            st.session_state.get(IN_KEYS["alskar"], 0),
            st.session_state.get(IN_KEYS["sover"], 0),
        ],
        "Tider (S/D/Vila/DT)": [
            st.session_state.get(IN_KEYS["tid_s"], 0),
            st.session_state.get(IN_KEYS["tid_d"], 0),
            st.session_state.get(IN_KEYS["vila"], 0),
            st.session_state.get(IN_KEYS["dt_tid"], 0),
            st.session_state.get(IN_KEYS["dt_vila"], 0),
        ],
    })

# ======= Slut =======
# Inga fler Sheets-anrop görs här. All skrivning sker enbart via save-knapparna ovan.
