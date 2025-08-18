# app.py  —  Del 1/6
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random

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
SETTINGS_SHEET = "Inställningar"

@st.cache_resource(show_spinner=False)
def resolve_spreadsheet():
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        return _retry_call(client.open_by_key, sid)
    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
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

spreadsheet = resolve_spreadsheet()

def _get_ws(title: str):
    """Hämta ett blad; skapa endast om det inte finns. Inga extrablad skapas."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=200 if title==SETTINGS_SHEET else 2000, cols=80)
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
                ["avgift_usd", "30.0", "Avgift (USD, per rad)"],
                ["PROD_STAFF", "800", "Produktionspersonal (fast)"],
                # Bonus-räknare (persistenta)
                ["BONUS_TOTAL", "0", "Bonus killar totalt"],
                ["BONUS_USED",  "0", "Bonus killar deltagit"],
                ["BONUS_LEFT",  "0", "Bonus killar kvar"],
                # Etikett-override (visning)
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
                # Nya: styrning för personal-% och Eskilstuna-intervall
                ["PERSONAL_PCT_DEFAULT", "10.0", "Personal deltagit % (default)"],
                ["ESK_MIN_DEFAULT", "20", "Eskilstuna min (default)"],
                ["ESK_MAX_DEFAULT", "40", "Eskilstuna max (default)"],
            ]
            _retry_call(ws.update, f"A2:C{len(defaults)+1}", defaults)
        return ws

# OBS: Vi hämtar endast referenser till bladen här. INGA läs/skriv i loopar.
sheet = _get_ws(WORKSHEET_TITLE)
settings_ws = _get_ws(SETTINGS_SHEET)

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    """Läs 'Inställningar' (Key/Value/Label) -> (CFG_RAW, LABELS)."""
    rows = _retry_call(settings_ws.get_all_records)  # engångsläsning
    d = {}
    labels = {}
    for r in rows:
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
    """Uppdatera/skriv ett key-value (+label) i fliken Inställningar."""
    recs = _retry_call(settings_ws.get_all_records)
    keys = [ (r.get("Key") or "") for r in recs ]
    try:
        idx = keys.index(key)  # 0-baserat bland data (A2..)
        rowno = idx + 2
    except ValueError:
        rowno = len(recs) + 2
        _retry_call(settings_ws.update, f"A{rowno}:C{rowno}", [[key, value, label or ""]])
        return
    _retry_call(settings_ws.update, f"B{rowno}", [[value]])
    if label is not None:
        _retry_call(settings_ws.update, f"C{rowno}", [[label]])

def _get_label(labels_map: dict, default_text: str) -> str:
    """Returnera ev. etikett-override, annars default_text."""
    return labels_map.get(default_text, default_text)

CFG_RAW, LABELS = _settings_as_dict()

def _init_cfg_defaults_from_settings():
    st.session_state.setdefault("CFG", {})
    C = st.session_state["CFG"]

    def _get(k, fallback):
        return CFG_RAW.get(k, fallback)

    # Datum/tid
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

    # Hårda siffror
    C["MAX_PAPPAN"]       = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]      = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"]  = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"]  = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]      = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]       = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"]       = int(float(_get("PROD_STAFF", 800)))

    # Bonus-räknare (pool)
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

    # UI-defaults
    try:
        C["PERSONAL_PCT_DEFAULT"] = float(_get("PERSONAL_PCT_DEFAULT", 10.0))
    except Exception:
        C["PERSONAL_PCT_DEFAULT"] = 10.0
    C["ESK_MIN_DEFAULT"] = int(float(_get("ESK_MIN_DEFAULT", 20)))
    C["ESK_MAX_DEFAULT"] = int(float(_get("ESK_MAX_DEFAULT", 40)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# --------------------- Globala konstantnycklar (för state) ---------------------
ROW_COUNT_KEY = "ROW_COUNT"   # används vid sparning
PLAN_KEY = "HOME_PLAN"        # lista med 7 dagars "Vila i hemmet" (förhandsvisning)
PLAN_IDX_KEY = "HOME_PLAN_IDX"

# ================================ Meny & Sidopanel ================================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("Inställningar / Etiketter")

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input("Historiskt startdatum", value=CFG["startdatum"])
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    födelsedatum = st.date_input(_get_label(LABELS, "Malins födelsedatum"), value=CFG["födelsedatum"])

    max_p  = st.number_input(f"Max {_get_label(LABELS, 'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_get_label(LABELS, 'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_get_label(LABELS, 'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_get_label(LABELS, 'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_get_label(LABELS, 'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

    prod_staff = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))

    # Din önskade: ange % (inte slider) för "Personal deltagit"
    if "personal_pct" not in st.session_state:
        st.session_state.personal_pct = float(CFG.get("PERSONAL_PCT_DEFAULT", 10.0))
    st.session_state.personal_pct = st.number_input(
        "Personal deltagit % (används som standard)", min_value=0.0, max_value=100.0, step=0.5,
        value=float(st.session_state.personal_pct), key="personal_pct_input"
    )

    # Eskilstuna intervall (min–max) för slump
    if "eskilstuna_min" not in st.session_state:
        st.session_state.eskilstuna_min = int(CFG.get("ESK_MIN_DEFAULT", 20))
    if "eskilstuna_max" not in st.session_state:
        st.session_state.eskilstuna_max = int(CFG.get("ESK_MAX_DEFAULT", 40))

    st.session_state.eskilstuna_min = st.number_input(
        "Eskilstuna min (slump)", key="esk_min_input", value=int(st.session_state.eskilstuna_min), min_value=0, step=1
    )
    st.session_state.eskilstuna_max = st.number_input(
        "Eskilstuna max (slump)", key="esk_max_input",
        value=max(int(st.session_state.eskilstuna_min)+1, int(st.session_state.eskilstuna_max) or 40),
        min_value=int(st.session_state.eskilstuna_min)+1, step=1
    )

    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    st.markdown("**Etiketter (påverkar endast visning)**")
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
        # Skriv EN gång (ingen autouppdatering)
        _save_setting("startdatum", startdatum.isoformat())
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", födelsedatum.isoformat(), label=lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)
        _save_setting("PROD_STAFF", str(int(prod_staff)))
        _save_setting("avgift_usd", str(float(avgift_input)))

        # spara defaults för personal % + Eskilstuna-intervall
        _save_setting("PERSONAL_PCT_DEFAULT", str(float(st.session_state.personal_pct)))
        _save_setting("ESK_MIN_DEFAULT", str(int(st.session_state.eskilstuna_min)))
        _save_setting("ESK_MAX_DEFAULT", str(int(st.session_state.eskilstuna_max)))

        # label-only overrides
        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_person, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")

        st.success("Inställningar och etiketter sparade ✅")
        st.rerun()

# app.py — Del 2/6  (scen-väljare + Hämta värden + min/max-cache)

# -------------------------- State: init input-fält ---------------------------
INPUT_KEYS = [
    "in_man", "in_svarta", "in_fitta", "in_rumpa",
    "in_dp", "in_dpp", "in_dap", "in_tap",
    "in_pappan", "in_grannar", "in_nils_vanner", "in_nils_familj", "in_bekanta",
    "in_eskilstuna",
    "in_bonus_deltagit", "in_personal_deltagit",
    "in_alskar", "in_sover",
    "in_tid_s", "in_tid_d", "in_vila", "in_dt_tid", "in_dt_vila",
    "in_nils",
    "in_avgift"
]

def _ensure_input_defaults():
    ss = st.session_state
    defaults = {
        "in_man": 0, "in_svarta": 0, "in_fitta": 0, "in_rumpa": 0,
        "in_dp": 0, "in_dpp": 0, "in_dap": 0, "in_tap": 0,
        "in_pappan": 0, "in_grannar": 0, "in_nils_vanner": 0, "in_nils_familj": 0, "in_bekanta": 0,
        "in_eskilstuna": 0,
        "in_bonus_deltagit": 0, "in_personal_deltagit": 0,
        "in_alskar": 0, "in_sover": 0,
        "in_tid_s": 60, "in_tid_d": 60, "in_vila": 7, "in_dt_tid": 60, "in_dt_vila": 3,
        "in_nils": 0,
        "in_avgift": float(CFG["avgift_usd"]),
    }
    for k, v in defaults.items():
        if k not in ss:
            ss[k] = v

_ensure_input_defaults()

# -------------------------- Min/Max från Sheet (cache) -----------------------
@st.cache_data(show_spinner=False, ttl=60)
def _sheet_min_max_map():
    """Hämtar en gång (cache) min/max per kolumn från Data-bladet."""
    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception:
        rows = []
    cols = [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"
    ]
    mm = {}
    for c in cols:
        vals = []
        for r in rows:
            vals.append(_safe_int(r.get(c, 0), 0))
        if len(vals) == 0:
            mm[c] = (0, 0)
        else:
            mm[c] = (min(vals), max(vals))
    return mm

def _min_max(colname: str):
    mm = _sheet_min_max_map()
    return mm.get(colname, (0, 0))

def _rand_between_min_max(colname: str):
    lo, hi = _min_max(colname)
    if hi < lo:
        lo, hi = 0, 0
    return random.randint(lo, hi)

# -------------------------- Hjälpfunktioner scenario -------------------------
def _personal_from_pct():
    """Personal deltagit enligt sidopanel-procentsats (avrundat)."""
    pct = float(st.session_state.get("personal_pct", CFG.get("PERSONAL_PCT_DEFAULT", 10.0)))
    return int(round(int(CFG["PROD_STAFF"]) * pct / 100.0))

def _bonus_deltagit_proposal():
    """40% av bonus kvar – endast som förslag i input (ingen skrivning till settings)."""
    left = int(CFG.get("BONUS_LEFT", 0))
    return int(round(left * 0.40))

def _reset_all_inputs():
    """Nollställ allt till default innan vi fyller scenario."""
    for k in INPUT_KEYS:
        if k == "in_avgift":
            st.session_state[k] = float(CFG["avgift_usd"])
        elif k in ("in_tid_s","in_tid_d"):
            st.session_state[k] = 60
        elif k == "in_vila":
            st.session_state[k] = 7
        elif k == "in_dt_tid":
            st.session_state[k] = 60
        elif k == "in_dt_vila":
            st.session_state[k] = 3
        else:
            st.session_state[k] = 0

def _apply_scenario_fill(scenario: str):
    """Fyll endast st.session_state[...] för inputs. Inget spar, inga skrivningar till Sheet."""
    _reset_all_inputs()

    # Alltid sätt avgift från settings default
    st.session_state.in_avgift = float(CFG["avgift_usd"])

    if scenario == "Ny scen":
        # Endast personal & bonus enligt regler, resten 0.
        st.session_state.in_personal_deltagit = _personal_from_pct()
        st.session_state.in_bonus_deltagit = _bonus_deltagit_proposal()

    elif scenario == "Slumpa scen vit":
        # Slumpa inom historiska min–max
        st.session_state.in_man = _rand_between_min_max("Män")
        st.session_state.in_svarta = 0  # vit scen -> svarta 0
        st.session_state.in_fitta = _rand_between_min_max("Fitta")
        st.session_state.in_rumpa = _rand_between_min_max("Rumpa")
        st.session_state.in_dp = _rand_between_min_max("DP")
        st.session_state.in_dpp = _rand_between_min_max("DPP")
        st.session_state.in_dap = _rand_between_min_max("DAP")
        st.session_state.in_tap = _rand_between_min_max("TAP")

        st.session_state.in_pappan = _rand_between_min_max("Pappans vänner")
        st.session_state.in_grannar = _rand_between_min_max("Grannar")
        st.session_state.in_nils_vanner = _rand_between_min_max("Nils vänner")
        st.session_state.in_nils_familj = _rand_between_min_max("Nils familj")
        # Bekanta har eget max i sidopanelen men här använder vi histogram-min/max
        st.session_state.in_bekanta = _rand_between_min_max("Bekanta")
        # Eskilstuna enligt sidopanel-intervall
        emin = int(st.session_state.eskilstuna_min)
        emax = int(st.session_state.eskilstuna_max)
        if emax < emin: emax = emin
        st.session_state.in_eskilstuna = random.randint(emin, emax)

        st.session_state.in_alskar = 8
        st.session_state.in_sover = 1
        st.session_state.in_personal_deltagit = _personal_from_pct()
        st.session_state.in_bonus_deltagit = _bonus_deltagit_proposal()

    elif scenario == "Slumpa scen svart":
        # Slumpa svarta + akter; alla källor & Män = 0
        st.session_state.in_man = 0
        st.session_state.in_svarta = _rand_between_min_max("Svarta")
        st.session_state.in_fitta = _rand_between_min_max("Fitta")
        st.session_state.in_rumpa = _rand_between_min_max("Rumpa")
        st.session_state.in_dp = _rand_between_min_max("DP")
        st.session_state.in_dpp = _rand_between_min_max("DPP")
        st.session_state.in_dap = _rand_between_min_max("DAP")
        st.session_state.in_tap = _rand_between_min_max("TAP")

        st.session_state.in_pappan = 0
        st.session_state.in_grannar = 0
        st.session_state.in_nils_vanner = 0
        st.session_state.in_nils_familj = 0
        st.session_state.in_bekanta = 0
        st.session_state.in_eskilstuna = 0

        st.session_state.in_alskar = 8
        st.session_state.in_sover = 1
        # Du bad specifikt: personal deltagit = 0 för svart slump
        st.session_state.in_personal_deltagit = 0
        st.session_state.in_bonus_deltagit = _bonus_deltagit_proposal()  # de här räknas som svarta i statistik vid spar

    elif scenario == "Vila på jobbet":
        # Slumpa akter mellan historiska min–max (Män/Svarta = 0)
        st.session_state.in_man = 0
        st.session_state.in_svarta = 0
        st.session_state.in_fitta = _rand_between_min_max("Fitta")
        st.session_state.in_rumpa = _rand_between_min_max("Rumpa")
        st.session_state.in_dp = _rand_between_min_max("DP")
        st.session_state.in_dpp = _rand_between_min_max("DPP")
        st.session_state.in_dap = _rand_between_min_max("DAP")
        st.session_state.in_tap = _rand_between_min_max("TAP")

        # Källor approx 40–60% av max är tidigare logik, men du ville minska calls.
        # Vi använder historiska min–max även här för enkelhet vid "Hämta".
        st.session_state.in_pappan = _rand_between_min_max("Pappans vänner")
        st.session_state.in_grannar = _rand_between_min_max("Grannar")
        st.session_state.in_nils_vanner = _rand_between_min_max("Nils vänner")
        st.session_state.in_nils_familj = _rand_between_min_max("Nils familj")
        st.session_state.in_bekanta = _rand_between_min_max("Bekanta")
        # Eskilstuna enligt intervall
        emin = int(st.session_state.eskilstuna_min); emax = int(st.session_state.eskilstuna_max)
        if emax < emin: emax = emin
        st.session_state.in_eskilstuna = random.randint(emin, emax)

        st.session_state.in_alskar = 12
        st.session_state.in_sover = 1
        st.session_state.in_personal_deltagit = _personal_from_pct()
        st.session_state.in_bonus_deltagit = _bonus_deltagit_proposal()

    elif scenario == "Vila i hemmet":
        # Generera en 7-dagars plan i sessionen (förhands), fyll dag 1 i inputs nu.
        # Plan-logik (enkel här; detaljerad fördelning görs i Del 5/6):
        plan = []
        for day in range(7):
            entry = {
                "Män": 0, "Svarta": 0,
                "Fitta": _rand_between_min_max("Fitta") if day <= 4 else 0,
                "Rumpa": _rand_between_min_max("Rumpa") if day <= 4 else 0,
                "DP":    _rand_between_min_max("DP")    if day <= 4 else 0,
                "DPP":   _rand_between_min_max("DPP")   if day <= 4 else 0,
                "DAP":   _rand_between_min_max("DAP")   if day <= 4 else 0,
                "TAP":   _rand_between_min_max("TAP")   if day <= 4 else 0,
                "Pappans vänner": _rand_between_min_max("Pappans vänner") if day <= 4 else 0,
                "Grannar":         _rand_between_min_max("Grannar") if day <= 4 else 0,
                "Nils vänner":     _rand_between_min_max("Nils vänner") if day <= 4 else 0,
                "Nils familj":     _rand_between_min_max("Nils familj") if day <= 4 else 0,
                "Bekanta":         _rand_between_min_max("Bekanta") if day <= 4 else 0,
                "Eskilstuna killar": random.randint(int(st.session_state.eskilstuna_min), int(st.session_state.eskilstuna_max)),
                "Älskar": 6, "Sover med": 1 if day == 6 else 0,
                "Personal deltagit": _personal_from_pct() if day <= 4 else 0,
                "Bonus deltagit": _bonus_deltagit_proposal() if day <= 4 else 0,
            }
            plan.append(entry)
        st.session_state[PLAN_KEY] = plan
        st.session_state[PLAN_IDX_KEY] = 0

        # Fyll dag 1
        e = plan[0]
        st.session_state.in_man = 0
        st.session_state.in_svarta = 0
        st.session_state.in_fitta = e["Fitta"]; st.session_state.in_rumpa = e["Rumpa"]
        st.session_state.in_dp = e["DP"]; st.session_state.in_dpp = e["DPP"]; st.session_state.in_dap = e["DAP"]; st.session_state.in_tap = e["TAP"]
        st.session_state.in_pappan = e["Pappans vänner"]; st.session_state.in_grannar = e["Grannar"]
        st.session_state.in_nils_vanner = e["Nils vänner"]; st.session_state.in_nils_familj = e["Nils familj"]; st.session_state.in_bekanta = e["Bekanta"]
        st.session_state.in_eskilstuna = e["Eskilstuna killar"]
        st.session_state.in_alskar = e["Älskar"]; st.session_state.in_sover = e["Sover med"]
        st.session_state.in_personal_deltagit = e["Personal deltagit"]
        st.session_state.in_bonus_deltagit = e["Bonus deltagit"]

    # Efter if-scen: uppdatera UI
    st.rerun()

# ------------------------------ UI: scenväljare -------------------------------
st.subheader("🎬 Välj scenario")
scenario = st.selectbox(
    "Scenario",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet", "Vila på jobbet"],
    index=0,
    key="scenario_choice"
)

# “Hämta värden” – fyller enbart inputs (session_state), inga spar-anrop
if st.button("📥 Hämta värden för valt scenario"):
    _apply_scenario_fill(st.session_state.scenario_choice)

# app.py — Del 3/6  (input i rätt ordning + live-förhandsvisning)

# --------- Hjälp (etiketter + datum/veckodag för aktuell scen) ----------
def _L(txt: str) -> str:
    return LABELS.get(txt, txt)

def _current_scene_info():
    scen = st.session_state.get(ROW_COUNT_KEY, 0) + 1
    d, veckodag = datum_och_veckodag_för_scen(scen)
    return scen, d, veckodag

scen, rad_datum, veckodag = _current_scene_info()

st.subheader("✍️ Inmatning")

# --------- INPUT I DENNA EXAKTA ORDNING ---------
# 1 kolumn per rad för att hålla ordningen visuellt kompakt men tydlig
in_m1 = st.number_input(_L("Män"),    min_value=0, step=1, value=st.session_state.in_man, key="in_man")
in_m2 = st.number_input(_L("Svarta"), min_value=0, step=1, value=st.session_state.in_svarta, key="in_svarta")

in_fitta  = st.number_input("Fitta", min_value=0, step=1, value=st.session_state.in_fitta, key="in_fitta")
in_rumpa  = st.number_input("Rumpa", min_value=0, step=1, value=st.session_state.in_rumpa, key="in_rumpa")
in_dp     = st.number_input("DP",    min_value=0, step=1, value=st.session_state.in_dp, key="in_dp")
in_dpp    = st.number_input("DPP",   min_value=0, step=1, value=st.session_state.in_dpp, key="in_dpp")
in_dap    = st.number_input("DAP",   min_value=0, step=1, value=st.session_state.in_dap, key="in_dap")
in_tap    = st.number_input("TAP",   min_value=0, step=1, value=st.session_state.in_tap, key="in_tap")

in_pappan = st.number_input(_L("Pappans vänner"), min_value=0, step=1, value=st.session_state.in_pappan, key="in_pappan")
in_grann  = st.number_input(_L("Grannar"),        min_value=0, step=1, value=st.session_state.in_grannar, key="in_grannar")
in_nv     = st.number_input(_L("Nils vänner"),    min_value=0, step=1, value=st.session_state.in_nils_vanner, key="in_nils_vanner")
in_nf     = st.number_input(_L("Nils familj"),    min_value=0, step=1, value=st.session_state.in_nils_familj, key="in_nils_familj")
in_bek    = st.number_input(_L("Bekanta"),        min_value=0, step=1, value=st.session_state.in_bekanta, key="in_bekanta")
in_esk    = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, value=st.session_state.in_eskilstuna, key="in_eskilstuna")

in_bonus  = st.number_input(_L("Bonus deltagit"),     min_value=0, step=1, value=st.session_state.in_bonus_deltagit, key="in_bonus_deltagit")
in_pers   = st.number_input(_L("Personal deltagit"),  min_value=0, step=1, value=st.session_state.in_personal_deltagit, key="in_personal_deltagit")

in_alskar = st.number_input("Älskar",                    min_value=0, step=1, value=st.session_state.in_alskar, key="in_alskar")
in_sover  = st.number_input("Sover med (0 eller 1)",     min_value=0, max_value=1, step=1, value=st.session_state.in_sover, key="in_sover")

in_ts  = st.number_input("Tid S (sek)",        min_value=0, step=1, value=st.session_state.in_tid_s, key="in_tid_s")
in_td  = st.number_input("Tid D (sek)",        min_value=0, step=1, value=st.session_state.in_tid_d, key="in_tid_d")
in_v   = st.number_input("Vila (sek)",         min_value=0, step=1, value=st.session_state.in_vila, key="in_vila")
in_dtt = st.number_input("DT tid (sek/kille)", min_value=0, step=1, value=st.session_state.in_dt_tid, key="in_dt_tid")
in_dtv = st.number_input("DT vila (sek/kille)",min_value=0, step=1, value=st.session_state.in_dt_vila, key="in_dt_vila")

# (valfritt fält du använt tidigare)
in_nils  = st.number_input("Nils",  min_value=0, step=1, value=st.session_state.in_nils, key="in_nils")
in_avg   = st.number_input("Avgift (USD, per rad)", min_value=0.0, step=1.0, value=float(st.session_state.in_avgift), key="in_avgift")

# --------- Live-förhandsberäkning (endast i minnet) ----------
grund_preview = {
    "Typ": st.session_state.get("scenario_choice",""),
    "Veckodag": veckodag, "Scen": scen,
    "Män": in_m1, "Svarta": in_m2,
    "Fitta": in_fitta, "Rumpa": in_rumpa, "DP": in_dp, "DPP": in_dpp, "DAP": in_dap, "TAP": in_tap,
    "Tid S": in_ts, "Tid D": in_td, "Vila": in_v,
    "DT tid (sek/kille)": in_dtt, "DT vila (sek/kille)": in_dtv,
    "Älskar": in_alskar, "Sover med": in_sover,
    "Pappans vänner": in_pappan, "Grannar": in_grann,
    "Nils vänner": in_nv, "Nils familj": in_nf, "Bekanta": in_bek, "Eskilstuna killar": in_esk,
    "Bonus deltagit": in_bonus, "Personal deltagit": in_pers,
    "Nils": in_nils,
    "Avgift": float(in_avg),

    # Viktigt: Skicka in PROD_STAFF så att hela personalstyrkan alltid räknas i lönen.
    "PROD_STAFF": int(CFG["PROD_STAFF"]),
}

def _calc_preview(grund):
    try:
        if callable(calc_row_values):
            # Skicka rätt namn: fodelsedatum (ej foddatum), och starttid
            return calc_row_values(
                grund,
                rad_datum=rad_datum,
                fodelsedatum=CFG["födelsedatum"],
                starttid=CFG["starttid"],
                cfg=CFG
            )
        else:
            return {}
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview(grund_preview)

# --------- Malins ålder (live) ----------
def _age_on(d: date, born: date) -> int:
    return d.year - born.year - ((d.month, d.day) < (born.month, born.day))

malin_ald = _age_on(rad_datum, CFG["födelsedatum"])

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

c1, c2 = st.columns(2)
with c1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder Malin", f"{malin_ald} år")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with c2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"🕒 Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

st.markdown("#### 💵 Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", in_avg)))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# app.py — Del 4/6  (spara, auto-max-dialog, radera)

# --------- Hjälp: packa "över max"-info ----------
def _collect_over_max(grund_vals):
    over = {}
    def _chk(field, max_key):
        cur = int(CFG.get(max_key, 0))
        val = int(grund_vals.get(field, 0))
        if val > cur:
            over[field] = {"current_max": cur, "new_value": val, "max_key": max_key}
    _chk("Pappans vänner", "MAX_PAPPAN")
    _chk("Grannar",        "MAX_GRANNAR")
    _chk("Nils vänner",    "MAX_NILS_VANNER")
    _chk("Nils familj",    "MAX_NILS_FAMILJ")
    _chk("Bekanta",        "MAX_BEKANTA")
    return over

# --------- Spara (beräkna -> skriv 1 rad till Data) ----------
def _save_row(grund, rad_datum, veckodag):
    try:
        base = dict(grund)
        # säkerställ avgift och PROD_STAFF följer CFG
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        base["PROD_STAFF"] = int(CFG["PROD_STAFF"])

        ber = calc_row_values(
            base,
            rad_datum=rad_datum,
            fodelsedatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
            cfg=CFG
        )
        ber["Datum"] = rad_datum.isoformat()
        ber["Veckodag"] = veckodag
        ber["Typ"] = base.get("Typ", "")
        ber["Scen"] = st.session_state.get(ROW_COUNT_KEY, 0) + 1
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    # Ordna utdata efter aktuell header
    row = [ber.get(col, "") for col in KOLUMNER]

    # Skriv ENDAST här
    _retry_call(sheet.append_row, row)

    # Uppdatera lokal rad-räknare
    st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1
    st.session_state[SCEN_START_TS_KEY] = None  # nollställ ev. scenstart-klocka

    ålder = rad_datum.year - CFG["födelsedatum"].year - (
        (rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day)
    )
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")
    st.rerun()

# --------- Auto-Max: spara pending + uppdatera Inställningar om bekräftat ----------
def _store_pending_save(grund, scen, rad_datum, veckodag, over_max_dict):
    st.session_state["PENDING_SAVE"] = {
        "grund": grund,
        "scen": int(scen),
        "rad_datum": str(rad_datum),
        "veckodag": veckodag,
        "over_max": over_max_dict
    }

def _apply_auto_max_and_save():
    pending = st.session_state.get("PENDING_SAVE")
    if not pending:
        return
    # Uppdatera maxvärden i Inställningar
    for _, info in pending["over_max"].items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))
        CFG[key] = new_val  # reflektera direkt i minnet

    # Kör sparning
    grund = pending["grund"]
    rd = datetime.fromisoformat(pending["rad_datum"]).date()
    _save_row(grund, rd, pending["veckodag"])

# --------- Spara-knapp ----------
save_clicked = st.button("💾 Spara raden", key="btn_save_row")
if save_clicked:
    # Använd de *aktuella* inmatade värdena (grund_preview)
    over_max = _collect_over_max(grund_preview)
    if over_max:
        _store_pending_save(grund_preview, scen, rad_datum, veckodag, over_max)
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# --------- Auto-Max-dialog ----------
if "PENDING_SAVE" in st.session_state:
    p = st.session_state["PENDING_SAVE"]
    st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden i Inställningar och spara raden?")
    for f, info in p["over_max"].items():
        st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")
    cA, cB = st.columns(2)
    with cA:
        if st.button("✅ Ja, uppdatera max och spara", key="btn_apply_max_and_save"):
            _apply_auto_max_and_save()
            st.session_state.pop("PENDING_SAVE", None)
            st.rerun()
    with cB:
        if st.button("✋ Nej, avbryt", key="btn_cancel_pending"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

# --------- Radera rad ----------
st.markdown("---")
st.subheader("🗑 Ta bort rad")
try:
    total_rows = st.session_state.get(ROW_COUNT_KEY, 0)
    if total_rows > 0:
        idx = st.number_input(
            "Radnummer att ta bort (1 = första dataraden)",
            min_value=1, max_value=total_rows, step=1, value=total_rows,
            key="delete_row_idx"
        )
        if st.button("Ta bort vald rad", key="btn_delete_row"):
            _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 för header
            st.session_state[ROW_COUNT_KEY] = max(0, total_rows - 1)
            st.success(f"Rad {idx} borttagen.")
            st.rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")

# app.py — Del 5/6  (Scenario-väljare + Hämta värden)
# ---------------------------------------------------

# ---- Hjälp: personal %-sats -> antal ----
def _personal_from_percent():
    pct = float(st.session_state.get("staff_pct", 10.0))  # sätts i sidopanelen
    return max(0, int(round(int(CFG["PROD_STAFF"]) * pct / 100.0)))

# ---- Hjälp: Eskilstuna-intervall (från sidopanelen) ----
def _esk_range():
    lo = int(st.session_state.get("eskilstuna_min", 20))
    hi = int(st.session_state.get("eskilstuna_max", 40))
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi

# ---- Hjälp: hämta min/max från databasen (kallas endast vid knapptryck) ----
def _get_min_max(colname: str):
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

# ---- Hjälp: bonus-beräkning baserad på live-prenumeranter ----
def _calc_bonus_for_current_inputs(grund_dict) -> dict:
    """
    Anropa beräkningen för att få 'Prenumeranter' (live), simulera 5%-chans/individ,
    och räkna fram 'bonus_killar_pending' samt 'bonus_deltagit_suggestion' (= 40% av (left+pending))
    utan att skriva något till Inställningar.
    """
    try:
        base = dict(grund_dict)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        base["PROD_STAFF"] = int(CFG["PROD_STAFF"])  # hela personalstyrkan räknas i lönen
        live = calc_row_values(
            base,
            rad_datum=rad_datum,
            fodelsedatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
            cfg=CFG
        )
        pren = int(_safe_int(live.get("Prenumeranter", 0), 0))
    except Exception:
        pren = 0

    # simulera Binomial(pren, 0.05) – enkel simulering utan numpy
    new_bonus = 0
    if pren > 0:
        # säkra mot väldigt stora slumpar: använd approx om pren är väldigt stort
        if pren > 5000:
            new_bonus = int(round(pren * 0.05))  # approx
        else:
            import random as _r
            new_bonus = sum(1 for _ in range(pren) if _r.random() < 0.05)

    # pool: nuvarande kvar + nya (ännu ej sparade)
    pool_left_now = int(CFG.get("BONUS_LEFT", 0))
    pool_with_pending = pool_left_now + new_bonus
    # 40% deltar på den här raden
    deltagit = int(pool_with_pending * 0.40)

    return {
        "pren": pren,
        "bonus_killar_pending": new_bonus,
        "bonus_deltagit_suggestion": deltagit,
        "pool_left_if_saved": max(0, pool_with_pending - deltagit)  # endast info
    }

# ---- Hjälp: fyll inputfält på ett säkert sätt (undviker dubblett-key-felet) ----
def _set_input_values(**kwargs):
    """
    Ange fält via session_state för alla in_* värden vi använder.
    Använd *exakt samma keys* som dina st.number_input i Del 3.
    """
    for k, v in kwargs.items():
        st.session_state[k] = v

# ---- Scenario-väljare + Hämta värden ----
scenario = st.selectbox(
    "Välj scenario",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet"],
    index=0,
    key="scenario_select"
)

if st.button("📥 Hämta värden", key="btn_fetch_values"):
    # Läs nuvarande inputs som bas
    current = {
        "Typ": "",
        "Veckodag": veckodag, "Scen": scen,
        "Män": st.session_state.get("in_man", 0),
        "Svarta": st.session_state.get("in_svarta", 0),
        "Fitta": st.session_state.get("in_fitta", 0),
        "Rumpa": st.session_state.get("in_rumpa", 0),
        "DP": st.session_state.get("in_dp", 0),
        "DPP": st.session_state.get("in_dpp", 0),
        "DAP": st.session_state.get("in_dap", 0),
        "TAP": st.session_state.get("in_tap", 0),
        "Tid S": st.session_state.get("in_tid_s", 60),
        "Tid D": st.session_state.get("in_tid_d", 60),
        "Vila":  st.session_state.get("in_vila", 7),
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 60),
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 3),
        "Älskar": st.session_state.get("in_alskar", 0),
        "Sover med": st.session_state.get("in_sover", 0),

        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar":        st.session_state.get("in_grannar", 0),
        "Nils vänner":    st.session_state.get("in_nils_vanner", 0),
        "Nils familj":    st.session_state.get("in_nils_familj", 0),
        "Bekanta":        st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        "Bonus killar":   st.session_state.get("in_bonus_killar", 0),
        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
        "Personal deltagit": st.session_state.get("in_personal_deltagit", _personal_from_percent()),
        "Nils": st.session_state.get("in_nils", 0),
        "Avgift": float(st.session_state.get("in_avgift", float(CFG["avgift_usd"]))),
        "PROD_STAFF": int(CFG["PROD_STAFF"])
    }

    # Gemensamma helpers för slumpning
    def rnd_col(col): 
        a, b = _get_min_max(col)
        if b < a: a, b = b, a
        return random.randint(a, b) if b >= a else 0

    esk_lo, esk_hi = _esk_range()
    esk_rand = lambda : random.randint(esk_lo, esk_hi)

    pers = _personal_from_percent()

    if scenario == "Ny scen":
        # Sätt bara "Typ" + personal och räkna bonus från prenumeranter (live)
        current["Typ"] = "Ny scen"
        current["Personal deltagit"] = pers

        # Bonus (via prenumeranter)
        b = _calc_bonus_for_current_inputs(current)
        current["Bonus killar"] = b["bonus_killar_pending"]
        current["Bonus deltagit"] = b["bonus_deltagit_suggestion"]

        _set_input_values(
            in_personal_deltagit=current["Personal deltagit"],
            in_bonus_killar=current["Bonus killar"],
            in_bonus_deltagit=current["Bonus deltagit"]
        )

    elif scenario == "Slumpa scen vit":
        current["Typ"] = "Ny scen (vit)"
        # Slumpa från min/max i databasen
        current["Män"]   = rnd_col("Män")
        current["Fitta"] = rnd_col("Fitta")
        current["Rumpa"] = rnd_col("Rumpa")
        current["DP"]    = rnd_col("DP")
        current["DPP"]   = rnd_col("DPP")
        current["DAP"]   = rnd_col("DAP")
        current["TAP"]   = rnd_col("TAP")

        current["Pappans vänner"] = rnd_col("Pappans vänner")
        current["Grannar"]        = rnd_col("Grannar")
        current["Nils vänner"]    = rnd_col("Nils vänner")
        current["Nils familj"]    = rnd_col("Nils familj")
        current["Bekanta"]        = rnd_col("Bekanta")
        current["Eskilstuna killar"] = rnd_col("Eskilstuna killar")

        current["Älskar"] = 8
        current["Sover med"] = 1
        current["Personal deltagit"] = pers

        # Bonus (via pren)
        b = _calc_bonus_for_current_inputs(current)
        current["Bonus killar"] = b["bonus_killar_pending"]
        current["Bonus deltagit"] = b["bonus_deltagit_suggestion"]

        _set_input_values(
            in_man=current["Män"],
            in_fitta=current["Fitta"],
            in_rumpa=current["Rumpa"],
            in_dp=current["DP"],
            in_dpp=current["DPP"],
            in_dap=current["DAP"],
            in_tap=current["TAP"],
            in_pappan=current["Pappans vänner"],
            in_grannar=current["Grannar"],
            in_nils_vanner=current["Nils vänner"],
            in_nils_familj=current["Nils familj"],
            in_bekanta=current["Bekanta"],
            in_eskilstuna=current["Eskilstuna killar"],
            in_alskar=current["Älskar"],
            in_sover=current["Sover med"],
            in_personal_deltagit=current["Personal deltagit"],
            in_bonus_killar=current["Bonus killar"],
            in_bonus_deltagit=current["Bonus deltagit"]
        )

    elif scenario == "Slumpa scen svart":
        current["Typ"] = "Ny scen (svart)"
        # Slumpa akter + Svarta från historik, nollställ källor och Män
        current["Fitta"] = rnd_col("Fitta")
        current["Rumpa"] = rnd_col("Rumpa")
        current["DP"]    = rnd_col("DP")
        current["DPP"]   = rnd_col("DPP")
        current["DAP"]   = rnd_col("DAP")
        current["TAP"]   = rnd_col("TAP")
        current["Svarta"] = rnd_col("Svarta")

        current["Män"] = 0
        current["Pappans vänner"] = 0
        current["Grannar"]        = 0
        current["Nils vänner"]    = 0
        current["Nils familj"]    = 0
        current["Bekanta"]        = 0
        current["Eskilstuna killar"] = 0

        current["Älskar"] = 8
        current["Sover med"] = 1
        # >>> per din senaste instruktion: personal deltagit = 0 i svart
        current["Personal deltagit"] = 0

        # Bonus (via pren)
        b = _calc_bonus_for_current_inputs(current)
        current["Bonus killar"] = b["bonus_killar_pending"]
        # Dessa bonusdeltagare ska räknas som "svarta" i statistiken senare,
        # men här fyller vi inputfältet:
        current["Bonus deltagit"] = b["bonus_deltagit_suggestion"]

        _set_input_values(
            in_man=0,
            in_svarta=current["Svarta"],
            in_fitta=current["Fitta"],
            in_rumpa=current["Rumpa"],
            in_dp=current["DP"],
            in_dpp=current["DPP"],
            in_dap=current["DAP"],
            in_tap=current["TAP"],
            in_pappan=0,
            in_grannar=0,
            in_nils_vanner=0,
            in_nils_familj=0,
            in_bekanta=0,
            in_eskilstuna=0,
            in_alskar=current["Älskar"],
            in_sover=current["Sover med"],
            in_personal_deltagit=0,
            in_bonus_killar=current["Bonus killar"],
            in_bonus_deltagit=current["Bonus deltagit"]
        )

    elif scenario == "Vila på jobbet":
        current["Typ"] = "Vila på jobbet"
        # Slumpa akter från historikens min/max
        current["Fitta"] = rnd_col("Fitta")
        current["Rumpa"] = rnd_col("Rumpa")
        current["DP"]    = rnd_col("DP")
        current["DPP"]   = rnd_col("DPP")
        current["DAP"]   = rnd_col("DAP")
        current["TAP"]   = rnd_col("TAP")

        # Källor enligt tidigare spec (40–60% av max) + Eskilstuna i valt intervall
        def _rand_40_60(mx): 
            lo = int(round(mx * 0.40)); hi = int(round(mx * 0.60))
            if hi < lo: lo, hi = hi, lo
            return random.randint(lo, hi) if hi >= lo and hi > 0 else 0

        current["Pappans vänner"] = _rand_40_60(CFG["MAX_PAPPAN"])
        current["Grannar"]        = _rand_40_60(CFG["MAX_GRANNAR"])
        current["Nils vänner"]    = _rand_40_60(CFG["MAX_NILS_VANNER"])
        current["Nils familj"]    = _rand_40_60(CFG["MAX_NILS_FAMILJ"])
        current["Bekanta"]        = _rand_40_60(CFG["MAX_BEKANTA"])
        current["Eskilstuna killar"] = esk_rand()

        # övrigt
        current["Män"] = 0
        current["Svarta"] = 0
        current["Älskar"] = 12
        current["Sover med"] = 1
        current["Personal deltagit"] = pers  # följer %-satsen

        # Bonus (via pren)
        b = _calc_bonus_for_current_inputs(current)
        current["Bonus killar"] = b["bonus_killar_pending"]
        current["Bonus deltagit"] = b["bonus_deltagit_suggestion"]

        _set_input_values(
            in_fitta=current["Fitta"], in_rumpa=current["Rumpa"],
            in_dp=current["DP"], in_dpp=current["DPP"],
            in_dap=current["DAP"], in_tap=current["TAP"],
            in_pappan=current["Pappans vänner"], in_grannar=current["Grannar"],
            in_nils_vanner=current["Nils vänner"], in_nils_familj=current["Nils familj"],
            in_bekanta=current["Bekanta"], in_eskilstuna=current["Eskilstuna killar"],
            in_man=0, in_svarta=0, in_alskar=current["Älskar"], in_sover=current["Sover med"],
            in_personal_deltagit=current["Personal deltagit"],
            in_bonus_killar=current["Bonus killar"],
            in_bonus_deltagit=current["Bonus deltagit"]
        )

    elif scenario == "Vila i hemmet":
        current["Typ"] = "Vila i hemmet"
        # Dag 1: 40–60% för källor, Eskilstuna i intervall
        current["Pappans vänner"] = rnd_col("Pappans vänner") or 0  # alt: 40–60% av max om du vill
        current["Grannar"]        = rnd_col("Grannar") or 0
        current["Nils vänner"]    = rnd_col("Nils vänner") or 0
        current["Nils familj"]    = rnd_col("Nils familj") or 0
        current["Bekanta"]        = rnd_col("Bekanta") or 0
        current["Eskilstuna killar"] = esk_rand()

        # Dag 1 övrigt:
        current["Män"] = 0
        current["Svarta"] = 0
        current["Fitta"] = 0
        current["Rumpa"] = 0
        current["DP"] = 0
        current["DPP"] = 0
        current["DAP"] = 0
        current["TAP"] = 0
        current["Älskar"] = 6
        current["Sover med"] = 0   # sv = 1 brukar vi lägga dag 6
        current["Personal deltagit"] = pers  # dag 1–5: pers, dag 6–7: 0 (hanteras när du sparar varje dag)

        # Bonus (via pren) – fördelas normalt dag 1–5; här visar vi dag 1:s “andel”
        b = _calc_bonus_for_current_inputs(current)
        # Om vi tänker oss att total kvar + pending fördelas dag 1–5:
        per_day = int((CFG.get("BONUS_LEFT", 0) + b["bonus_killar_pending"]) // 5) if (CFG.get("BONUS_LEFT", 0) + b["bonus_killar_pending"]) > 0 else 0
        current["Bonus killar"] = b["bonus_killar_pending"]
        current["Bonus deltagit"] = per_day

        _set_input_values(
            in_pappan=current["Pappans vänner"], in_grannar=current["Grannar"],
            in_nils_vanner=current["Nils vänner"], in_nils_familj=current["Nils familj"],
            in_bekanta=current["Bekanta"], in_eskilstuna=current["Eskilstuna killar"],
            in_man=0, in_svarta=0, in_fitta=0, in_rumpa=0, in_dp=0, in_dpp=0, in_dap=0, in_tap=0,
            in_alskar=current["Älskar"], in_sover=current["Sover med"],
            in_personal_deltagit=current["Personal deltagit"],
            in_bonus_killar=current["Bonus killar"],
            in_bonus_deltagit=current["Bonus deltagit"]
        )

    # Efter att vi fyllt input: trigga uppdatering av liven
    st.rerun()

# app.py — Del 6/6  (Spara + Bonus-pool + stabilitet)
# ----------------------------------------------------

def _normalize_typ_from_scenario(sel: str) -> str:
    # Mappa selectbox-värdet till "Typ" på raden
    if sel == "Ny scen": return "Ny scen"
    if sel == "Slumpa scen vit": return "Ny scen (vit)"
    if sel == "Slumpa scen svart": return "Ny scen (svart)"
    if sel == "Vila på jobbet": return "Vila på jobbet"
    if sel == "Vila i hemmet": return "Vila i hemmet"
    return "Händelse"

def _compose_current_input_dict():
    # Läs alla inputfält från sessionen (identiska keys som i Del 3)
    d = {
        "Typ": _normalize_typ_from_scenario(st.session_state.get("scenario_select","Ny scen")),
        "Veckodag": veckodag, "Scen": scen,

        "Män": st.session_state.get("in_man", 0),
        "Svarta": st.session_state.get("in_svarta", 0),
        "Fitta": st.session_state.get("in_fitta", 0),
        "Rumpa": st.session_state.get("in_rumpa", 0),
        "DP": st.session_state.get("in_dp", 0),
        "DPP": st.session_state.get("in_dpp", 0),
        "DAP": st.session_state.get("in_dap", 0),
        "TAP": st.session_state.get("in_tap", 0),

        "Tid S": st.session_state.get("in_tid_s", 60),
        "Tid D": st.session_state.get("in_tid_d", 60),
        "Vila":  st.session_state.get("in_vila", 7),
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 60),
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 3),

        "Älskar": st.session_state.get("in_alskar", 0),
        "Sover med": st.session_state.get("in_sover", 0),

        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar":        st.session_state.get("in_grannar", 0),
        "Nils vänner":    st.session_state.get("in_nils_vanner", 0),
        "Nils familj":    st.session_state.get("in_nils_familj", 0),
        "Bekanta":        st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        "Bonus killar":   st.session_state.get("in_bonus_killar", 0),
        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),

        # OBS: detta är bara “med i scenen”; lönen räknas alltid på PROD_STAFF nedan
        "Personal deltagit": st.session_state.get("in_personal_deltagit", _personal_from_percent()),

        "Nils": st.session_state.get("in_nils", 0),
        "Avgift": float(st.session_state.get("in_avgift", float(CFG["avgift_usd"]))),

        # Lönebas: alltid hela personalstyrkan
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
    }
    return d

def _recalc_bonus_pending(grund: dict):
    """
    Räkna fram aktuella prenumeranter -> bonus_killar_pending
    (5% chans per prenumerant), samt föreslaget 'Bonus deltagit' (40% av kvar+pending).
    Används vid spar för robusthet (om användaren inte tryckt Hämta värden igen).
    """
    try:
        base = dict(grund)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        base["PROD_STAFF"] = int(CFG["PROD_STAFF"])
        live = calc_row_values(
            base,
            rad_datum=rad_datum,
            fodelsedatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
            cfg=CFG
        )
        pren = int(_safe_int(live.get("Prenumeranter", 0), 0))
    except Exception:
        pren = 0

    pending = 0
    if pren > 0:
        if pren > 5000:
            pending = int(round(pren * 0.05))
        else:
            import random as _r
            pending = sum(1 for _ in range(pren) if _r.random() < 0.05)

    pool_left_now = int(CFG.get("BONUS_LEFT", 0))
    deltag_suggestion = int((pool_left_now + pending) * 0.40)
    return pending, deltag_suggestion

def _update_bonus_counters_on_save(row_bonus_killar_pending: int, row_bonus_deltagit: int):
    """
    Uppdatera bonusräknare i Inställningar när RADEN sparas.
    - BONUS_TOTAL ökar med 'row_bonus_killar_pending'
    - BONUS_USED  ökar med 'row_bonus_deltagit'
    - BONUS_LEFT  ökar med 'row_bonus_killar_pending' och minskas sedan med 'row_bonus_deltagit' (golv: 0)
    """
    total = int(CFG.get("BONUS_TOTAL", 0))
    used  = int(CFG.get("BONUS_USED", 0))
    left  = int(CFG.get("BONUS_LEFT", 0))

    total_new = max(0, total + int(row_bonus_killar_pending))
    used_new  = max(0, used  + int(row_bonus_deltagit))
    left_new  = max(0, left  + int(row_bonus_killar_pending) - int(row_bonus_deltagit))

    _save_setting("BONUS_TOTAL", str(total_new))
    _save_setting("BONUS_USED",  str(used_new))
    _save_setting("BONUS_LEFT",  str(left_new))

    CFG["BONUS_TOTAL"] = total_new
    CFG["BONUS_USED"]  = used_new
    CFG["BONUS_LEFT"]  = left_new

    return total, used, left, total_new, used_new, left_new

def _save_row_to_sheet(ber: dict):
    # Skriv enligt KOLUMNERs ordning
    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    # bump radräknare
    st.session_state["ROW_COUNT"] = st.session_state.get("ROW_COUNT", 0) + 1

def _save_row_action():
    """Körs när du trycker på 💾 Spara raden."""
    # 1) Läs nuvarande inputs
    grund = _compose_current_input_dict()

    # 2) Robusthet: om Bonus killar/deltagit saknas/0, räkna pending snabbt igen
    pending_bonus, deltag_suggest = _recalc_bonus_pending(grund)
    row_bonus_killar_pending = int(grund.get("Bonus killar", 0))
    row_bonus_deltagit       = int(grund.get("Bonus deltagit", 0))

    if row_bonus_killar_pending <= 0:
        row_bonus_killar_pending = pending_bonus
    if row_bonus_deltagit <= 0:
        # Låt användarens input vinna om den inte är 0; annars föreslagen
        row_bonus_deltagit = deltag_suggest

    # 3) Kör beräkningar för raden (inkl. att använda PROD_STAFF för löner)
    try:
        base = dict(grund)
        base["Bonus killar"]   = row_bonus_killar_pending
        base["Bonus deltagit"] = row_bonus_deltagit
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        ber = calc_row_values(
            base,
            rad_datum=rad_datum,
            fodelsedatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
            cfg=CFG
        )
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    # 4) Spara raden
    try:
        _save_row_to_sheet(ber)
    except Exception as e:
        st.error(f"Kunde inte spara till Google Sheets: {e}")
        return

    # 5) Uppdatera bonuspoolens räknare
    oldT, oldU, oldL, newT, newU, newL = _update_bonus_counters_on_save(
        row_bonus_killar_pending, row_bonus_deltagit
    )

    # 6) Bekräftelse
    ålder = (
        rad_datum.year - CFG["födelsedatum"].year
        - ((rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day))
    )
    st.success(
        f"✅ Rad sparad ({ber.get('Typ','Händelse')}). Datum {rad_datum} ({veckodag}), "
        f"Ålder {ålder} år, Klockan {ber.get('Klockan','-')}."
    )
    st.info(
        f"Bonus: TOTAL {oldT}→{newT}, USED {oldU}→{newU}, LEFT {oldL}→{newL} "
        f"(denna rad: +{row_bonus_killar_pending} till total, −{row_bonus_deltagit} från left)."
    )

# ---- Spara-knappen (koppla till nya logiken) ----
if st.button("💾 Spara raden", key="btn_save_row"):
    _save_row_action()
