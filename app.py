# ===================== app.py — DEL 1/4 =====================
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
    #    print("safe_int failed for", x)  # valfri debug
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
        # Skapa endast efterfrågad flik
        ws = spreadsheet.add_worksheet(title=title, rows=200 if title==SETTINGS_SHEET else 2000, cols=80)
        if title == SETTINGS_SHEET:
            _retry_call(ws.update, "A1:C1", [["Key","Value","Label"]])
            # Grundvärden + etiketter & bonusräknare (en gång)
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

                # Nya inställningar
                ["PERSONAL_PCT", "10", "Personal deltagit (%)"],
                ["ESK_MIN", "20", "Eskilstuna killar – min"],
                ["ESK_MAX", "40", "Eskilstuna killar – max"],

                # Bonusräknare (persistenta)
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
            ]
            _retry_call(ws.update, f"A2:C{len(defaults)+1}", defaults)
        return ws

# OBS: initiera flikar en gång vid appstart
sheet = _get_ws(WORKSHEET_TITLE)
settings_ws = _get_ws(SETTINGS_SHEET)

# =========================== Header-säkring / migration =========================
DEFAULT_COLUMNS = [
    "Datum","Typ","Veckodag","Scen",
    "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
    "Summa S","Summa D","Summa TP","Summa Vila",
    "Tid Älskar (sek)","Tid Älskar",
    "Tid Sover med (sek)","Tid Sover med",
    "Summa tid","Summa tid (sek)",
    "Tid per kille (sek)","Tid per kille",
    "Klockan","Älskar","Sover med","Känner",
    "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar",
    "Bonus killar","Bonus deltagit","Personal deltagit",
    "Totalt Män","Tid kille","Nils",
    "Hångel (sek/kille)","Hångel (m:s/kille)",
    "Suger","Suger per kille (sek)",
    "Hårdhet","Prenumeranter","Avgift","Intäkter",
    "Utgift män","Intäkt Känner","Lön Malin","Vinst",
    "Känner Sammanlagt"
]

def ensure_header_and_migrate_once():
    """Kör header-kontrollen max EN gång per session för att undvika onödiga sheets-anrop."""
    if st.session_state.get("_header_ok", False):
        return
    header = _retry_call(sheet.row_values, 1)
    if not header:
        _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
        st.session_state["COLUMNS"] = DEFAULT_COLUMNS
        st.session_state["_header_ok"] = True
        st.caption("🧱 Skapade kolumnrubriker.")
        return

    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        from gspread.utils import rowcol_to_a1
        new_header = header + missing
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        st.session_state["COLUMNS"] = new_header
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
    else:
        st.session_state["COLUMNS"] = header
    st.session_state["_header_ok"] = True

ensure_header_and_migrate_once()
KOLUMNER = st.session_state["COLUMNS"]

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    """Läs 'Inställningar' (Key/Value/Label) -> (CFG_RAW, LABELS)."""
    rows = _retry_call(settings_ws.get_all_records)  # [{'Key':..,'Value':..,'Label':..}, ...]
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
        idx = keys.index(key)  # 0-baserat (A2..)
        rowno = idx + 2
    except ValueError:
        rowno = len(recs) + 2
        _retry_call(settings_ws.update, f"A{rowno}:C{rowno}", [[key, value, label or ""]])
        return
    _retry_call(settings_ws.update, f"B{rowno}", [[value]])
    if label is not None:
        _retry_call(settings_ws.update, f"C{rowno}", [[label]])

def _L_map(labels_map: dict, default_text: str) -> str:
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

    # Nya: personal-procent + Eskilstuna-intervall
    C["PERSONAL_PCT"]     = int(float(_get("PERSONAL_PCT", 10)))   # procent
    C["ESK_MIN"]          = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]          = int(float(_get("ESK_MAX", 40)))

    # Bonus-räknare
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ================================ Sidopanel ====================================
st.sidebar.header("Inställningar")
MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    fod = st.date_input(
        _L_map(LABELS, "Malins födelsedatum"),
        value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
        min_value=MIN_FOD, max_value=date.today()
    )
    max_p  = st.number_input(f"Max {_L_map(LABELS, 'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_L_map(LABELS, 'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_L_map(LABELS, 'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_L_map(LABELS, 'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_L_map(LABELS, 'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))
    prod_staff   = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    personal_pct = st.number_input("Personal deltagit (%)", min_value=0, max_value=100, step=1, value=int(CFG["PERSONAL_PCT"]))
    esk_min = st.number_input("Eskilstuna killar – min", min_value=0, step=1, value=int(CFG["ESK_MIN"]))
    esk_max = st.number_input("Eskilstuna killar – max", min_value=0, step=1, value=int(CFG["ESK_MAX"]))
    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    st.markdown("**Etiketter (visning)**")
    lab_p   = st.text_input("Etikett: Pappans vänner", value=_L_map(LABELS, "Pappans vänner"))
    lab_g   = st.text_input("Etikett: Grannar", value=_L_map(LABELS, "Grannar"))
    lab_nv  = st.text_input("Etikett: Nils vänner", value=_L_map(LABELS, "Nils vänner"))
    lab_nf  = st.text_input("Etikett: Nils familj", value=_L_map(LABELS, "Nils familj"))
    lab_bk  = st.text_input("Etikett: Bekanta", value=_L_map(LABELS, "Bekanta"))
    lab_esk = st.text_input("Etikett: Eskilstuna killar", value=_L_map(LABELS, "Eskilstuna killar"))
    lab_man = st.text_input("Etikett: Män", value=_L_map(LABELS, "Män"))
    lab_sva = st.text_input("Etikett: Svarta", value=_L_map(LABELS, "Svarta"))
    lab_kann= st.text_input("Etikett: Känner", value=_L_map(LABELS, "Känner"))
    lab_person = st.text_input("Etikett: Personal deltagit", value=_L_map(LABELS, "Personal deltagit"))
    lab_bonus  = st.text_input("Etikett: Bonus killar", value=_L_map(LABELS, "Bonus killar"))
    lab_bonusd = st.text_input("Etikett: Bonus deltagit", value=_L_map(LABELS, "Bonus deltagit"))
    lab_mfd    = st.text_input("Etikett: Malins födelsedatum", value=_L_map(LABELS, "Malins födelsedatum"))

    if st.button("💾 Spara inställningar"):
        # värden
        _save_setting("startdatum", startdatum.isoformat())
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", fod.isoformat(), label=lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)

        _save_setting("PROD_STAFF", str(int(prod_staff)))
        _save_setting("PERSONAL_PCT", str(int(personal_pct)))
        _save_setting("ESK_MIN", str(int(esk_min)))
        _save_setting("ESK_MAX", str(int(esk_max)))
        _save_setting("avgift_usd", str(float(avgift_input)))

        # Etiketter (label-only overrides på nyckeln LABEL_*)
        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_person, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")

        st.success("Inställningar & etiketter sparade ✅")
        st.rerun()
# ===================== SLUT DEL 1/4 =====================

# ===================== app.py — DEL 2/4 (Scenario + Inputs) =====================

st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# ---------- Hjälpare som bara läser från Sheets vid behov ----------
def _get_all_rows_once():
    # Ladda och cacha bara när vi behöver slump-intervall från historik
    if "ALL_ROWS_CACHE" not in st.session_state:
        try:
            st.session_state["ALL_ROWS_CACHE"] = _retry_call(sheet.get_all_records)
        except Exception:
            st.session_state["ALL_ROWS_CACHE"] = []
    return st.session_state["ALL_ROWS_CACHE"]

def _get_min_max_from_history(colname: str):
    rows = _get_all_rows_once()
    vals = []
    for r in rows:
        try:
            v = r.get(colname, 0)
            if v is None or str(v).strip() == "":
                continue
            vals.append(int(float(v)))
        except Exception:
            continue
    if not vals:
        return 0, 0
    return min(vals), max(vals)

# ---------- Radräkning / datum ----------
def _init_row_count():
    # Räknas enbart vid appstart (cachas) – används för scennummer i liven/spara.
    if "ROW_COUNT" not in st.session_state:
        try:
            vals = _retry_call(sheet.col_values, 1)  # kolumn A = Datum
            st.session_state.ROW_COUNT = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
        except Exception:
            st.session_state.ROW_COUNT = 0
_init_row_count()

def next_scene_number():
    return int(st.session_state.ROW_COUNT) + 1

def datum_och_veckodag_för_scen(scen_nummer: int):
    d = CFG["startdatum"] + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# ---------- Standardvärden (beräknade från sidopanelens inställningar) ----------
def _personal_default():
    return max(0, int(round(int(CFG["PROD_STAFF"]) * int(CFG["PERSONAL_PCT"]) / 100.0)))

def _esk_rand():
    lo, hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
    if hi < lo: lo, hi = hi, lo
    return random.randint(lo, hi) if hi >= lo else 0

def _forty_percent_bonus_left():
    try:
        return int(round(int(CFG.get("BONUS_LEFT", 0)) * 0.40))
    except Exception:
        return 0

# ---------- Scenario-väljare ----------
if view == "Produktion":
    st.header("🧪 Produktion – ny rad")

    scenario = st.selectbox(
        "Vad vill du skapa?",
        ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet", "Vila på jobbet"],
        index=0,
        key="scenario_select"
    )

    # Initiera input-keys om de saknas (ASCII-nycklar)
    for k, v in {
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
        "in_nils_vanner": 0,
        "in_nils_familj": 0,
        "in_bekanta": 0,
        "in_eskilstuna": 0,

        "in_bonus_deltagit": 0,
        "in_personal_deltagit": _personal_default(),

        "in_alskar": 0,
        "in_sover": 0,

        "in_tid_s": 60,
        "in_tid_d": 60,
        "in_vila": 7,
        "in_dt_tid": 60,
        "in_dt_vila": 3,

        "in_nils": 0,
        "in_avgift": float(CFG["avgift_usd"]),
    }.items():
        st.session_state.setdefault(k, v)

    # ---------- Applicera scenariofyllning (endast minne, ingen skrivning) ----------
    def apply_scenario_fill(name: str):
        # Nollställ ev. 7-dagarskö när vi byter scenario
        st.session_state.pop("preview_queue", None)
        st.session_state.pop("preview_queue_idx", None)

        if name == "Ny scen":
            # Lämna fält som de är, men säkerställ personal följer procenten
            st.session_state["in_personal_deltagit"] = _personal_default()

        elif name == "Slumpa scen vit":
            # Slumpa utifrån historikens min/max för dessa fält
            def rcol(c): 
                mn, mx = _get_min_max_from_history(c)
                return random.randint(mn, mx) if mx >= mn else 0

            st.session_state["in_man"] = rcol("Män")
            st.session_state["in_svarta"] = rcol("Svarta")
            st.session_state["in_fitta"] = rcol("Fitta")
            st.session_state["in_rumpa"] = rcol("Rumpa")
            st.session_state["in_dp"] = rcol("DP")
            st.session_state["in_dpp"] = rcol("DPP")
            st.session_state["in_dap"] = rcol("DAP")
            st.session_state["in_tap"] = rcol("TAP")

            st.session_state["in_pappan"] = rcol("Pappans vänner")
            st.session_state["in_grannar"] = rcol("Grannar")
            st.session_state["in_nils_vanner"] = rcol("Nils vänner")
            st.session_state["in_nils_familj"] = rcol("Nils familj")
            st.session_state["in_bekanta"] = rcol("Bekanta")
            st.session_state["in_eskilstuna"] = rcol("Eskilstuna killar")

            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"] = 1
            st.session_state["in_personal_deltagit"] = _personal_default()

            # 40% av kvarvarande bonus som deltar på denna rad (visas i input)
            st.session_state["in_bonus_deltagit"] = _forty_percent_bonus_left()

        elif name == "Slumpa scen svart":
            def rcol(c): 
                mn, mx = _get_min_max_from_history(c)
                return random.randint(mn, mx) if mx >= mn else 0

            # Svart scen: endast sex-akter + Svarta slumpas; övriga källor 0
            st.session_state["in_fitta"] = rcol("Fitta")
            st.session_state["in_rumpa"] = rcol("Rumpa")
            st.session_state["in_dp"] = rcol("DP")
            st.session_state["in_dpp"] = rcol("DPP")
            st.session_state["in_dap"] = rcol("DAP")
            st.session_state["in_tap"] = rcol("TAP")
            st.session_state["in_svarta"] = rcol("Svarta")

            # Nollställ övriga deltagar-kolumner
            st.session_state["in_man"] = 0
            st.session_state["in_pappan"] = 0
            st.session_state["in_grannar"] = 0
            st.session_state["in_nils_vanner"] = 0
            st.session_state["in_nils_familj"] = 0
            st.session_state["in_bekanta"] = 0
            st.session_state["in_eskilstuna"] = 0

            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"] = 1
            st.session_state["in_personal_deltagit"] = _personal_default()
            st.session_state["in_bonus_deltagit"] = _forty_percent_bonus_left()

        elif name == "Vila på jobbet":
            # 40–60% av respektive max, Eskilstuna enligt intervall, personal = procent
            def r4060(mx): 
                try: mx = int(mx)
                except: mx = 0
                if mx <= 0: return 0
                lo = max(0, int(round(mx * 0.40)))
                hi = max(lo, int(round(mx * 0.60)))
                return random.randint(lo, hi)

            st.session_state["in_man"] = 0
            st.session_state["in_svarta"] = 0
            st.session_state["in_fitta"] = 0
            st.session_state["in_rumpa"] = 0
            st.session_state["in_dp"] = 0
            st.session_state["in_dpp"] = 0
            st.session_state["in_dap"] = 0
            st.session_state["in_tap"] = 0

            st.session_state["in_pappan"] = r4060(CFG["MAX_PAPPAN"])
            st.session_state["in_grannar"] = r4060(CFG["MAX_GRANNAR"])
            st.session_state["in_nils_vanner"] = r4060(CFG["MAX_NILS_VANNER"])
            st.session_state["in_nils_familj"] = r4060(CFG["MAX_NILS_FAMILJ"])
            st.session_state["in_bekanta"] = r4060(CFG["MAX_BEKANTA"])
            st.session_state["in_eskilstuna"] = _esk_rand()

            st.session_state["in_alskar"] = 12
            st.session_state["in_sover"] = 1
            st.session_state["in_personal_deltagit"] = _personal_default()
            st.session_state["in_bonus_deltagit"] = _forty_percent_bonus_left()

        elif name == "Vila i hemmet":
            # Skapa 7-dagars kö (dag 1–5: källor 40–60%+Eskilstuna; dag 6–7: noll källor; pers=0 dag 6–7)
            def r4060(mx): 
                try: mx = int(mx)
                except: mx = 0
                if mx <= 0: return 0
                lo = max(0, int(round(mx * 0.40)))
                hi = max(lo, int(round(mx * 0.60)))
                return random.randint(lo, hi)

            start_scen = next_scene_number()
            queue = []
            # Fördela kvarvarande bonus lika över dag 1–5
            bonus_left = int(CFG.get("BONUS_LEFT", 0))
            per_day_bonus = bonus_left // 5 if bonus_left > 0 else 0

            # Nils 50/45/5 modell för dag 1–6 (antal ettor)
            r = random.random()
            if r < 0.50:
                ones_count = 0
            elif r < 0.95:
                ones_count = 1
            else:
                ones_count = 2
            nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

            for offset in range(7):
                scen_num = start_scen + offset
                # Basobjekt per dag
                item = {
                    "Typ": "Vila i hemmet",
                    "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
                    "Tid S": 0, "Tid D": 0, "Vila": 0,
                    "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
                    "Älskar": 6, "Sover med": 0,
                    "Pappans vänner": 0, "Grannar": 0, "Nils vänner": 0, "Nils familj": 0, "Bekanta": 0,
                    "Eskilstuna killar": 0,
                    "Bonus deltagit": 0,
                    "Personal deltagit": 0,
                    "Nils": 0,
                    "Avgift": float(CFG["avgift_usd"]),
                }

                if offset <= 4:
                    # dag 1-5
                    item.update({
                        "Pappans vänner": r4060(CFG["MAX_PAPPAN"]),
                        "Grannar": r4060(CFG["MAX_GRANNAR"]),
                        "Nils vänner": r4060(CFG["MAX_NILS_VANNER"]),
                        "Nils familj": r4060(CFG["MAX_NILS_FAMILJ"]),
                        "Bekanta": r4060(CFG["MAX_BEKANTA"]),
                        "Eskilstuna killar": _esk_rand(),
                        "Bonus deltagit": per_day_bonus,
                        "Personal deltagit": _personal_default(),
                        "Sover med": 0,
                        "Nils": 1 if offset in nils_one_offsets else 0,
                    })
                elif offset == 5:
                    # dag 6
                    item.update({
                        "Sover med": 1,
                        "Personal deltagit": 0
                    })
                else:
                    # dag 7
                    item.update({
                        "Sover med": 0,
                        "Personal deltagit": 0
                    })

                queue.append(item)

            st.session_state["preview_queue"] = queue
            st.session_state["preview_queue_idx"] = 0

            # Fyll även current inputs med dag 1 för att visa i formuläret direkt
            first = queue[0]
            st.session_state["in_man"] = first["Män"]
            st.session_state["in_svarta"] = first["Svarta"]
            st.session_state["in_fitta"] = first["Fitta"]
            st.session_state["in_rumpa"] = first["Rumpa"]
            st.session_state["in_dp"] = first["DP"]
            st.session_state["in_dpp"] = first["DPP"]
            st.session_state["in_dap"] = first["DAP"]
            st.session_state["in_tap"] = first["TAP"]

            st.session_state["in_pappan"] = first["Pappans vänner"]
            st.session_state["in_grannar"] = first["Grannar"]
            st.session_state["in_nils_vanner"] = first["Nils vänner"]
            st.session_state["in_nils_familj"] = first["Nils familj"]
            st.session_state["in_bekanta"] = first["Bekanta"]
            st.session_state["in_eskilstuna"] = first["Eskilstuna killar"]

            st.session_state["in_bonus_deltagit"] = first["Bonus deltagit"]
            st.session_state["in_personal_deltagit"] = first["Personal deltagit"]
            st.session_state["in_alskar"] = first["Älskar"]
            st.session_state["in_sover"] = first["Sover med"]

            st.session_state["in_tid_s"] = first["Tid S"]
            st.session_state["in_tid_d"] = first["Tid D"]
            st.session_state["in_vila"] = first["Vila"]
            st.session_state["in_dt_tid"] = first["DT tid (sek/kille)"]
            st.session_state["in_dt_vila"] = first["DT vila (sek/kille)"]

        # Trigger ommålning
        st.rerun()

    # Fyll enligt valt scenario
    if st.button("⚡ Fyll enligt val"):
        apply_scenario_fill(st.session_state["scenario_select"])

    # ---------- INPUTFÄLT (exakt ordning du önskade) ----------
    # Radens datum/veckodag för visning och live-beräkning
    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    st.caption(f"Scen #{scen} — {rad_datum} ({veckodag})")

    # Ordning:
    # Män, Svarta, Fitta, Rumpa, DP, DPP, DAP, TAP,
    # Pappans vänner, Grannar, Nils vänner, Nils familj, Bekanta, Eskilstuna killar,
    # Bonus deltagit, Personal deltagit,
    # Älskar, Sover med,
    # Tid S, Tid D, Vila, DT tid, DT vila

    cA, cB, cC = st.columns(3)

    with cA:
        män    = st.number_input(_L_map(LABELS, "Män"),    min_value=0, step=1, key="in_man")
        svarta = st.number_input(_L_map(LABELS, "Svarta"), min_value=0, step=1, key="in_svarta")
        fitta  = st.number_input("Fitta",  min_value=0, step=1, key="in_fitta")
        rumpa  = st.number_input("Rumpa",  min_value=0, step=1, key="in_rumpa")
        dp     = st.number_input("DP",     min_value=0, step=1, key="in_dp")
        dpp    = st.number_input("DPP",    min_value=0, step=1, key="in_dpp")
        dap    = st.number_input("DAP",    min_value=0, step=1, key="in_dap")
        tap    = st.number_input("TAP",    min_value=0, step=1, key="in_tap")

    with cB:
        lbl_p  = f"{_L_map(LABELS, 'Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
        lbl_g  = f"{_L_map(LABELS, 'Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
        lbl_nv = f"{_L_map(LABELS, 'Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
        lbl_nf = f"{_L_map(LABELS, 'Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
        lbl_bk = f"{_L_map(LABELS, 'Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

        pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, key="in_pappan")
        grannar        = st.number_input(lbl_g,  min_value=0, step=1, key="in_grannar")
        nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, key="in_nils_vanner")
        nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, key="in_nils_familj")
        bekanta        = st.number_input(_L_map(LABELS, "Bekanta"), min_value=0, step=1, key="in_bekanta")
        eskilstuna_killar = st.number_input(_L_map(LABELS, "Eskilstuna killar"), min_value=0, step=1, key="in_eskilstuna")

        bonus_deltagit    = st.number_input(_L_map(LABELS, "Bonus deltagit"), min_value=0, step=1, key="in_bonus_deltagit")
        personal_deltagit = st.number_input(_L_map(LABELS, "Personal deltagit"), min_value=0, step=1, key="in_personal_deltagit")

    with cC:
        älskar    = st.number_input("Älskar",                min_value=0, step=1, key="in_alskar")
        sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, key="in_sover")

        tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, key="in_tid_s")
        tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, key="in_tid_d")
        vila   = st.number_input("Vila (sek)",  min_value=0, step=1, key="in_vila")
        dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, key="in_dt_tid")
        dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, key="in_dt_vila")

    # Snabb info om max-överskridanden (endast visning)
    if pappans_vänner > int(CFG["MAX_PAPPAN"]):
        st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {int(CFG['MAX_PAPPAN'])}</span>", unsafe_allow_html=True)
    if grannar > int(CFG["MAX_GRANNAR"]):
        st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {int(CFG['MAX_GRANNAR'])}</span>", unsafe_allow_html=True)
    if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
        st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {int(CFG['MAX_NILS_VANNER'])}</span>", unsafe_allow_html=True)
    if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
        st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {int(CFG['MAX_NILS_FAMILJ'])}</span>", unsafe_allow_html=True)
    if bekanta > int(CFG["MAX_BEKANTA"]):
        st.markdown(f"<span style='color:#d00'>⚠️ {bekanta} > max {int(CFG['MAX_BEKANTA'])}</span>", unsafe_allow_html=True)

# ===================== SLUT DEL 2/4 =====================

# -------------------------
# SIDOPANEL – INSTÄLLNINGAR
# -------------------------
st.sidebar.header("Inställningar")

# Total personalstyrka
if "personal_total" not in st.session_state:
    st.session_state.personal_total = 800
st.session_state.personal_total = st.sidebar.number_input(
    "Total personalstyrka",
    min_value=1,
    value=st.session_state.personal_total,
    step=1
)

# Procent personal deltagit
if "personal_procent" not in st.session_state:
    st.session_state.personal_procent = 10
st.session_state.personal_procent = st.sidebar.number_input(
    "Personal deltagit (%)",
    min_value=1,
    max_value=100,
    value=st.session_state.personal_procent,
    step=1
)

# Eskilstuna killar – intervall
if "eskilstuna_min" not in st.session_state:
    st.session_state.eskilstuna_min = 20
if "eskilstuna_max" not in st.session_state:
    st.session_state.eskilstuna_max = 40

st.session_state.eskilstuna_min = st.sidebar.number_input(
    "Eskilstuna killar – min",
    min_value=0,
    value=st.session_state.eskilstuna_min,
    step=1
)
st.session_state.eskilstuna_max = st.sidebar.number_input(
    "Eskilstuna killar – max",
    min_value=st.session_state.eskilstuna_min + 1,
    value=st.session_state.eskilstuna_max,
    step=1
)

# Funktion för att beräkna personal deltagit baserat på % av total
def calc_personal_deltagit():
    return int(round(st.session_state.personal_total * st.session_state.personal_procent / 100))

# -------------------------
# SCENARIOVÄLJARE + INPUTS
# -------------------------

# Hjälp: etikett-funktion för visning
def _L(txt: str) -> str:
    return LABELS.get(txt, txt)

# Init standardvärden i sessionen (så widgets får stabila keys)
def _ensure_input_defaults():
    ss = st.session_state
    ss.setdefault("in_man", 0)
    ss.setdefault("in_svarta", 0)
    ss.setdefault("in_fitta", 0)
    ss.setdefault("in_rumpa", 0)
    ss.setdefault("in_dp", 0)
    ss.setdefault("in_dpp", 0)
    ss.setdefault("in_dap", 0)
    ss.setdefault("in_tap", 0)

    ss.setdefault("in_pappan", 0)
    ss.setdefault("in_grannar", 0)
    ss.setdefault("in_nils_vanner", 0)
    ss.setdefault("in_nils_familj", 0)
    ss.setdefault("in_bekanta", 0)
    ss.setdefault("in_eskilstuna", 0)

    # Bonus och personal
    ss.setdefault("in_bonus_killar", 0)
    ss.setdefault("in_bonus_deltagit", 0)
    # Personal deltagit följer alltid % av total
    ss["in_personal_deltagit"] = calc_personal_deltagit()

    # Extra
    ss.setdefault("in_alskar", 0)
    ss.setdefault("in_sover", 0)
    ss.setdefault("in_tid_s", 60)
    ss.setdefault("in_tid_d", 60)
    ss.setdefault("in_vila", 7)
    ss.setdefault("in_dt_tid", 60)
    ss.setdefault("in_dt_vila", 3)
    ss.setdefault("in_nils", 0)

_ensure_input_defaults()

# Läs historik (endast när vi behöver min/max för slump)
def _get_min_max(colname: str):
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

def _rand_40_60_of_max(mx: int) -> int:
    try:
        mx = int(mx)
    except Exception:
        mx = 0
    if mx <= 0:
        return 0
    lo = max(0, int(round(mx * 0.40)))
    hi = max(lo, int(round(mx * 0.60)))
    return random.randint(lo, hi)

def _rand_eskilstuna_in_range() -> int:
    a = int(st.session_state.eskilstuna_min)
    b = int(st.session_state.eskilstuna_max)
    if b < a:
        a, b = b, a
    return random.randint(a, b)

# Fyller inputs enligt valt scenario (INTE sparning)
def apply_scenario_fill(scen_choice: str):
    ss = st.session_state

    if scen_choice == "Ny scen":
        # Nollställ allt utom personal (som följer %)
        for k in [
            "in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
            "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna",
            "in_bonus_killar","in_bonus_deltagit","in_nils"
        ]:
            ss[k] = 0
        ss["in_alskar"] = 0
        ss["in_sover"] = 0
        # Tider lämnas med defaults
        ss["in_personal_deltagit"] = calc_personal_deltagit()

    elif scen_choice == "Slumpa scen vit":
        # Slumpa från historiska min/max
        mn, mx = _get_min_max("Män");                 ss["in_man"]   = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Fitta");               ss["in_fitta"] = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Rumpa");               ss["in_rumpa"] = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("DP");                  ss["in_dp"]    = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("DPP");                 ss["in_dpp"]   = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("DAP");                 ss["in_dap"]   = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("TAP");                 ss["in_tap"]   = random.randint(mn, mx) if mx >= mn else 0

        mn, mx = _get_min_max("Pappans vänner");      ss["in_pappan"]       = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Grannar");             ss["in_grannar"]      = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Nils vänner");         ss["in_nils_vanner"]  = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Nils familj");         ss["in_nils_familj"]  = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Bekanta");             ss["in_bekanta"]      = random.randint(mn, mx) if mx >= mn else 0
        # Eskilstuna ur valbart intervall i sidopanelen
        ss["in_eskilstuna"] = _rand_eskilstuna_in_range()

        ss["in_svarta"] = 0           # vit scen
        ss["in_alskar"] = 8
        ss["in_sover"]  = 1
        ss["in_nils"]   = 0
        ss["in_bonus_deltagit"] = 0   # beräknas i preview om så krävs
        ss["in_personal_deltagit"] = calc_personal_deltagit()

    elif scen_choice == "Slumpa scen svart":
        # Svart scen: slumpa sex-akter + svarta, sätt övriga källor = 0
        for col in ["Fitta","Rumpa","DP","DPP","DAP","TAP","Svarta"]:
            mn, mx = _get_min_max(col)
            val = random.randint(mn, mx) if mx >= mn else 0
            if col == "Fitta": ss["in_fitta"] = val
            elif col == "Rumpa": ss["in_rumpa"] = val
            elif col == "DP": ss["in_dp"] = val
            elif col == "DPP": ss["in_dpp"] = val
            elif col == "DAP": ss["in_dap"] = val
            elif col == "TAP": ss["in_tap"] = val
            elif col == "Svarta": ss["in_svarta"] = val

        # Källor = 0
        for k in ["in_man","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
            ss[k] = 0

        ss["in_alskar"] = 8
        ss["in_sover"]  = 1
        ss["in_nils"]   = 0
        ss["in_bonus_deltagit"] = 0
        ss["in_personal_deltagit"] = calc_personal_deltagit()

    elif scen_choice == "Vila på jobbet":
        # 40–60% av max för källor, Eskilstuna enligt intervall, övriga aktiva noll
        ss["in_man"] = 0
        ss["in_svarta"] = 0
        for k in ["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"]:
            ss[k] = 0

        ss["in_pappan"]      = _rand_40_60_of_max(CFG.get("MAX_PAPPAN", 0))
        ss["in_grannar"]     = _rand_40_60_of_max(CFG.get("MAX_GRANNAR", 0))
        ss["in_nils_vanner"] = _rand_40_60_of_max(CFG.get("MAX_NILS_VANNER", 0))
        ss["in_nils_familj"] = _rand_40_60_of_max(CFG.get("MAX_NILS_FAMILJ", 0))
        ss["in_bekanta"]     = _rand_40_60_of_max(CFG.get("MAX_BEKANTA", 0))
        ss["in_eskilstuna"]  = _rand_eskilstuna_in_range()

        ss["in_alskar"] = 12
        ss["in_sover"]  = 1
        ss["in_nils"]   = 0
        ss["in_bonus_deltagit"] = 0
        ss["in_personal_deltagit"] = calc_personal_deltagit()

    elif scen_choice == "Vila i hemmet":
        # Denna knapp ska normalt generera 7-dagars paket i ett flöde.
        # Men här fyller vi bara första dagens standard i inputs (dag 1).
        ss["in_man"] = 0
        ss["in_svarta"] = 0
        for k in ["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"]:
            ss[k] = 0

        # Dag 1-liknande: 40–60% källor + eskilstuna i intervall
        ss["in_pappan"]      = _rand_40_60_of_max(CFG.get("MAX_PAPPAN", 0))
        ss["in_grannar"]     = _rand_40_60_of_max(CFG.get("MAX_GRANNAR", 0))
        ss["in_nils_vanner"] = _rand_40_60_of_max(CFG.get("MAX_NILS_VANNER", 0))
        ss["in_nils_familj"] = _rand_40_60_of_max(CFG.get("MAX_NILS_FAMILJ", 0))
        ss["in_bekanta"]     = _rand_40_60_of_max(CFG.get("MAX_BEKANTA", 0))
        ss["in_eskilstuna"]  = _rand_eskilstuna_in_range()

        ss["in_alskar"] = 6
        ss["in_sover"]  = 0
        ss["in_nils"]   = 0  # faktiska 7-dagarsfördelningen hanteras när vi bygger paketet vid "spara"
        ss["in_bonus_deltagit"] = 0
        # Dag1–5: personal  = %; dag6–7: 0. Här visar vi dag1-liknande:
        ss["in_personal_deltagit"] = calc_personal_deltagit()

# Rullista för val av scenario + "Fyll" knapp
col_sc_sel, col_sc_btn = st.columns([3,1])
scenario_choice = col_sc_sel.selectbox(
    "Välj scenario",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet", "Vila på jobbet"],
    index=0,
    key="scenario_choice"
)
if col_sc_btn.button("Fyll från val"):
    apply_scenario_fill(st.session_state.scenario_choice)
    st.rerun()

# -------------------------
# INPUTFÄLT I ÖNSKAD ORDNING
# -------------------------
# (Allt visas – och uppdateras endast i sessionen)

män    = st.number_input(_L("Män"),    min_value=0, step=1, value=st.session_state["in_man"],           key="in_man")
svarta = st.number_input(_L("Svarta"), min_value=0, step=1, value=st.session_state["in_svarta"],        key="in_svarta")
fitta  = st.number_input("Fitta",      min_value=0, step=1, value=st.session_state["in_fitta"],         key="in_fitta")
rumpa  = st.number_input("Rumpa",      min_value=0, step=1, value=st.session_state["in_rumpa"],         key="in_rumpa")
dp     = st.number_input("DP",         min_value=0, step=1, value=st.session_state["in_dp"],            key="in_dp")
dpp    = st.number_input("DPP",        min_value=0, step=1, value=st.session_state["in_dpp"],           key="in_dpp")
dap    = st.number_input("DAP",        min_value=0, step=1, value=st.session_state["in_dap"],           key="in_dap")
tap    = st.number_input("TAP",        min_value=0, step=1, value=st.session_state["in_tap"],           key="in_tap")

lbl_p  = f"{_L('Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
lbl_g  = f"{_L('Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
lbl_nv = f"{_L('Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
lbl_nf = f"{_L('Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
lbl_bk = f"{_L('Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

pappans_vänner   = st.number_input(lbl_p,  min_value=0, step=1, value=st.session_state["in_pappan"],        key="in_pappan")
grannar          = st.number_input(lbl_g,  min_value=0, step=1, value=st.session_state["in_grannar"],       key="in_grannar")
nils_vänner      = st.number_input(lbl_nv, min_value=0, step=1, value=st.session_state["in_nils_vanner"],   key="in_nils_vanner")
nils_familj      = st.number_input(lbl_nf, min_value=0, step=1, value=st.session_state["in_nils_familj"],   key="in_nils_familj")
bekanta          = st.number_input(_L("Bekanta"),        min_value=0, step=1, value=st.session_state["in_bekanta"],     key="in_bekanta")
eskilstuna_killar= st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, value=st.session_state["in_eskilstuna"], key="in_eskilstuna")

bonus_deltagit   = st.number_input(_L("Bonus deltagit"),    min_value=0, step=1, value=st.session_state["in_bonus_deltagit"], key="in_bonus_deltagit")
personal_deltagit= st.number_input(_L("Personal deltagit"), min_value=0, step=1, value=calc_personal_deltagit(), key="in_personal_deltagit")

älskar    = st.number_input("Älskar",                min_value=0, step=1, value=st.session_state["in_alskar"], key="in_alskar")
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=st.session_state["in_sover"], key="in_sover")

tid_s  = st.number_input("Tid S (sek)",           min_value=0, step=1, value=st.session_state["in_tid_s"],   key="in_tid_s")
tid_d  = st.number_input("Tid D (sek)",           min_value=0, step=1, value=st.session_state["in_tid_d"],   key="in_tid_d")
vila   = st.number_input("Vila (sek)",            min_value=0, step=1, value=st.session_state["in_vila"],    key="in_vila")
dt_tid = st.number_input("DT tid (sek/kille)",    min_value=0, step=1, value=st.session_state["in_dt_tid"],  key="in_dt_tid")
dt_vila= st.number_input("DT vila (sek/kille)",   min_value=0, step=1, value=st.session_state["in_dt_vila"], key="in_dt_vila")

# Varningar för max (visning)
if pappans_vänner > int(CFG["MAX_PAPPAN"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {int(CFG['MAX_PAPPAN'])}</span>", unsafe_allow_html=True)
if grannar > int(CFG["MAX_GRANNAR"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {int(CFG['MAX_GRANNAR'])}</span>", unsafe_allow_html=True)
if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {int(CFG['MAX_NILS_VANNER'])}</span>", unsafe_allow_html=True)
if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {int(CFG['MAX_NILS_FAMILJ'])}</span>", unsafe_allow_html=True)
if bekanta > int(CFG["MAX_BEKANTA"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {bekanta} > max {int(CFG['MAX_BEKANTA'])}</span>", unsafe_allow_html=True)

# -------------------------
# LIVE-FÖRHANDSVISNING + SPARA
# -------------------------

# Hjälp: scen-nummer utan nya Sheets-anrop (använd cachet värde)
def _tentative_scene_number():
    return int(st.session_state.get("ROW_COUNT", 0)) + 1

def _datum_och_veckodag_for_scen(scen_nummer: int):
    d = CFG["startdatum"] + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# Personaldeltagit ska alltid följa procent – skriv över ev. manuell justering före beräkning
st.session_state["in_personal_deltagit"] = calc_personal_deltagit()

# Bygg grundrad av input (endast i minnet)
scen_num = _tentative_scene_number()
rad_datum, veckodag = _datum_och_veckodag_for_scen(scen_num)

grund_preview = {
    "Typ": st.session_state.get("scenario_choice", "Ny scen"),
    "Veckodag": veckodag, "Scen": scen_num,

    "Män": st.session_state["in_man"],
    "Svarta": st.session_state["in_svarta"],
    "Fitta": st.session_state["in_fitta"],
    "Rumpa": st.session_state["in_rumpa"],
    "DP": st.session_state["in_dp"],
    "DPP": st.session_state["in_dpp"],
    "DAP": st.session_state["in_dap"],
    "TAP": st.session_state["in_tap"],

    "Tid S": st.session_state["in_tid_s"],
    "Tid D": st.session_state["in_tid_d"],
    "Vila":  st.session_state["in_vila"],

    "DT tid (sek/kille)":  st.session_state["in_dt_tid"],
    "DT vila (sek/kille)": st.session_state["in_dt_vila"],

    "Älskar":    st.session_state["in_alskar"],
    "Sover med": st.session_state["in_sover"],

    "Pappans vänner": st.session_state["in_pappan"],
    "Grannar":        st.session_state["in_grannar"],
    "Nils vänner":    st.session_state["in_nils_vanner"],
    "Nils familj":    st.session_state["in_nils_familj"],
    "Bekanta":        st.session_state["in_bekanta"],
    "Eskilstuna killar": st.session_state["in_eskilstuna"],

    "Bonus killar":   st.session_state.get("in_bonus_killar", 0),   # (ingår ej längre i logiken, behålls om du vill visa)
    "Bonus deltagit": st.session_state["in_bonus_deltagit"],
    "Personal deltagit": st.session_state["in_personal_deltagit"],

    "Nils": st.session_state["in_nils"],

    "Avgift": float(CFG.get("avgift_usd", 30.0)),
}

def _calc_preview(grund):
    if not callable(calc_row_values):
        return {}
    try:
        return calc_row_values(grund, rad_datum, CFG["födelsedatum"], CFG["starttid"])
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview(grund_preview)

# Ålder (live)
def _age_on(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))

alder_malin = _age_on(rad_datum, CFG["födelsedatum"])

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
cinfo, ctime = st.columns([1,1])
with cinfo:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin, live)", f"{alder_malin} år")
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with ctime:
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

st.markdown("#### 💵 Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG.get("avgift_usd", 30.0))))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))
    # plats över om du vill lägga något mer

# -------------------------
# SPARA (enda stället där vi skriver till Sheets)
# -------------------------

def _row_to_values_in_order(dikt, header):
    return [dikt.get(col, "") for col in header]

def _save_row(grund, rad_datum: date, veckodag: str):
    # Tvinga personal_deltagit följa procent vid sparning
    grund = dict(grund)
    grund["Personal deltagit"] = calc_personal_deltagit()

    # Kör beräkning och sätt datum
    ber = _calc_preview(grund)
    if not ber:
        st.error("Beräkning saknas – kunde inte spara.")
        return
    ber["Datum"] = rad_datum.isoformat()
    ber["Veckodag"] = veckodag
    ber["Scen"] = _tentative_scene_number()  # scennumret vid spar

    # Skriv raden
    row_values = _row_to_values_in_order(ber, KOLUMNER)
    _retry_call(sheet.append_row, row_values)
    # Uppdatera vår lokala radräknare
    st.session_state["ROW_COUNT"] = int(st.session_state.get("ROW_COUNT", 0)) + 1

    st.success(f"✅ Rad sparad ({ber.get('Typ','Händelse')}). Datum {rad_datum} ({veckodag}), Ålder {alder_malin} år, Klockan {ber.get('Klockan','-')}")
    st.balloons()

# Auto-max: visa dialog om något fält överskrider max. Max uppdateras endast om du bekräftar.
def _collect_over_max():
    over = {}
    if st.session_state["in_pappan"] > int(CFG["MAX_PAPPAN"]):
        over["Pappans vänner"] = ("MAX_PAPPAN", st.session_state["in_pappan"], int(CFG["MAX_PAPPAN"]))
    if st.session_state["in_grannar"] > int(CFG["MAX_GRANNAR"]):
        over["Grannar"] = ("MAX_GRANNAR", st.session_state["in_grannar"], int(CFG["MAX_GRANNAR"]))
    if st.session_state["in_nils_vanner"] > int(CFG["MAX_NILS_VANNER"]):
        over["Nils vänner"] = ("MAX_NILS_VANNER", st.session_state["in_nils_vanner"], int(CFG["MAX_NILS_VANNER"]))
    if st.session_state["in_nils_familj"] > int(CFG["MAX_NILS_FAMILJ"]):
        over["Nils familj"] = ("MAX_NILS_FAMILJ", st.session_state["in_nils_familj"], int(CFG["MAX_NILS_FAMILJ"]))
    if st.session_state["in_bekanta"] > int(CFG["MAX_BEKANTA"]):
        over["Bekanta"] = ("MAX_BEKANTA", st.session_state["in_bekanta"], int(CFG["MAX_BEKANTA"]))
    return over

col_save, col_cancel = st.columns([1,1])
if col_save.button("💾 Spara raden"):
    over = _collect_over_max()
    if over:
        st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara?")
        for namn, (key, new_val, cur_max) in over.items():
            st.write(f"- **{namn}**: max {cur_max} → **{new_val}**")

        cA, cB = st.columns(2)
        with cA:
            if st.button("✅ Uppdatera max och spara"):
                # Uppdatera max i "Inställningar"
                for _, (key, new_val, _) in over.items():
                    _save_setting(key, str(int(new_val)))
                    CFG[key] = int(new_val)
                _save_row(grund_preview, rad_datum, veckodag)
                st.rerun()
        with cB:
            if st.button("✋ Avbryt sparning"):
                st.info("Sparning avbröts.")
    else:
        _save_row(grund_preview, rad_datum, veckodag)

if col_cancel.button("♻️ Återställ fält (nollställ)"):
    apply_scenario_fill("Ny scen")
    st.rerun()

# -------------------------
# STATISTIKVY (read-only)
# -------------------------
if view == "Statistik":
    st.header("📊 Statistik")

    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # Hjälp: total män för en rad
    def _row_tot_men(r):
        # Om kolumnen finns och ej blank – använd den
        if "Totalt Män" in r and str(r.get("Totalt Män", "")).strip() != "":
            return _safe_int(r.get("Totalt Män", 0), 0)
        # Annars räkna on-the-fly enligt specifikationen
        return (
            _safe_int(r.get("Män", 0), 0)
            + _safe_int(r.get("Känner", 0), 0)
            + _safe_int(r.get("Svarta", 0), 0)
            + _safe_int(r.get("Bekanta", 0), 0)
            + _safe_int(r.get("Eskilstuna killar", 0), 0)
            + _safe_int(r.get("Bonus deltagit", 0), 0)
            + _safe_int(r.get("Personal deltagit", 0), 0)
        )

    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man_sum = 0

    # Andel svarta: (Svarta + Bonus deltagit) / Totalt Män
    svarta_like_sum = 0
    tot_for_andel_svarta = 0

    bonus_deltagit_sum = 0
    personal_deltagit_sum = 0

    # Prenumeranter totals + aktiva 30 dagar (exkludera vila-typer)
    total_pren = 0
    aktiva_pren = 0
    cutoff = date.today() - timedelta(days=30)

    for r in rows:
        typ = (r.get("Typ") or "").strip()
        tot_men_row = _row_tot_men(r)

        if tot_men_row > 0:
            antal_scener += 1
        elif _safe_int(r.get("Känner", 0), 0) > 0:
            privat_gb_cnt += 1

        totalt_man_sum += tot_men_row

        # Svarta + Bonus deltagit räknas som "svarta" i kvoten
        svarta_like_sum += _safe_int(r.get("Svarta", 0), 0) + _safe_int(r.get("Bonus deltagit", 0), 0)
        tot_for_andel_svarta += max(0, tot_men_row)

        bonus_deltagit_sum += _safe_int(r.get("Bonus deltagit", 0), 0)
        personal_deltagit_sum += _safe_int(r.get("Personal deltagit", 0), 0)

        if typ not in ("Vila på jobbet", "Vila i hemmet"):
            pren = _safe_int(r.get("Prenumeranter", 0), 0)
            total_pren += pren
            d = _parse_iso_date(r.get("Datum", ""))
            if d and d >= cutoff:
                aktiva_pren += pren

    andel_svarta_pct = round((svarta_like_sum / tot_for_andel_svarta) * 100, 2) if tot_for_andel_svarta > 0 else 0.0

    # ---- Översikt ----
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Antal scener", antal_scener)
    with c2: st.metric("Privat GB", privat_gb_cnt)
    with c3: st.metric("Totalt män (summa)", totalt_man_sum)
    with c4: st.metric("Andel svarta (%)", andel_svarta_pct)

    c5, c6 = st.columns(2)
    with c5: st.metric("Bonus killar (deltagit, sum)", bonus_deltagit_sum)
    with c6: st.metric("Personal (deltagit, sum)", personal_deltagit_sum)

    # ---- Prenumeranter ----
    st.markdown("---")
    st.subheader("👥 Prenumeranter")
    pc1, pc2 = st.columns(2)
    with pc1: st.metric("Prenumeranter (totalt)", int(total_pren))
    with pc2: st.metric("Aktiva prenumeranter (30 dagar)", int(aktiva_pren))

    # ---- DP/DPP/DAP/TAP: summa & snitt per scen ----
    st.markdown("---")
    st.subheader("🔩 DP / DPP / DAP / TAP — summa & snitt per scen")

    dp_sum  = sum(_safe_int(r.get("DP", 0))  for r in rows if _safe_int(r.get("DP", 0))  > 0)
    dpp_sum = sum(_safe_int(r.get("DPP", 0)) for r in rows if _safe_int(r.get("DPP", 0)) > 0)
    dap_sum = sum(_safe_int(r.get("DAP", 0)) for r in rows if _safe_int(r.get("DAP", 0)) > 0)
    tap_sum = sum(_safe_int(r.get("TAP", 0)) for r in rows if _safe_int(r.get("TAP", 0)) > 0)

    denom_scen = antal_scener if antal_scener > 0 else 1
    dp_avg  = round(dp_sum  / denom_scen, 2) if antal_scener > 0 else 0.0
    dpp_avg = round(dpp_sum / denom_scen, 2) if antal_scener > 0 else 0.0
    dap_avg = round(dap_sum / denom_scen, 2) if antal_scener > 0 else 0.0
    tap_avg = round(tap_sum / denom_scen, 2) if antal_scener > 0 else 0.0

    s1, s2, s3, s4 = st.columns(4)
    with s1: st.metric("Summa DP (>0)", dp_sum)
    with s2: st.metric("Summa DPP (>0)", dpp_sum)
    with s3: st.metric("Summa DAP (>0)", dap_sum)
    with s4: st.metric("Summa TAP (>0)", tap_sum)

    a1, a2, a3, a4 = st.columns(4)
    with a1: st.metric("Snitt DP / scen", dp_avg)
    with a2: st.metric("Snitt DPP / scen", dpp_avg)
    with a3: st.metric("Snitt DAP / scen", dap_avg)
    with a4: st.metric("Snitt TAP / scen", tap_avg)

    st.info("Statistiken uppdateras när du sparar nya rader. Inga beräkningar skriver till databasen i denna vy.")

# -------------------------
# TABELL + RADERA-RAD
# -------------------------
st.markdown("---")
st.subheader("📄 Data i databasen (read-only)")

try:
    all_rows = _retry_call(sheet.get_all_records)
    if all_rows:
        st.dataframe(all_rows, use_container_width=True)
    else:
        st.info("Inga datarader ännu.")
except Exception as e:
    st.warning(f"Kunde inte läsa data: {e}")

st.subheader("🗑 Ta bort rad")
try:
    # Antal datarader = antal rader i kolumn A minus headern (1)
    if "ROW_COUNT" not in st.session_state:
        try:
            a_vals = _retry_call(sheet.col_values, 1)
            st.session_state.ROW_COUNT = max(0, len(a_vals) - 1) if (a_vals and a_vals[0] == "Datum") else len(a_vals)
        except Exception:
            st.session_state.ROW_COUNT = 0

    total_rows = st.session_state.ROW_COUNT
    if total_rows > 0:
        idx = st.number_input(
            "Radnummer att ta bort (1 = första dataraden)",
            min_value=1, max_value=total_rows, step=1, value=1
        )
        if st.button("Ta bort vald rad"):
            # +1 för att hoppa över headern vid delete_rows
            _retry_call(sheet.delete_rows, int(idx) + 1)
            st.session_state.ROW_COUNT -= 1
            st.success(f"Rad {idx} borttagen.")
            st.rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")
