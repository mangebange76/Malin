# app.py (Del 1/5)

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
                # Persistens för sidopanelens parametrar
                ["ESK_MIN", "20", ""],
                ["ESK_MAX", "40", ""],
                ["STAFF_PCT", "10.0", ""],
            ]
            _retry_call(ws.update, f"A2:C{len(defaults)+1}", defaults)
        return ws

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

def ensure_header_and_migrate():
    header = _retry_call(sheet.row_values, 1)
    if not header:
        _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
        st.session_state["COLUMNS"] = DEFAULT_COLUMNS
        st.caption("🧱 Skapade kolumnrubriker.")
        return
    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        from gspread.utils import rowcol_to_a1
        new_header = header + missing
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

# Kör header/migration max en gång per session (undvik onödiga API-anrop)
if "HEADER_OK" not in st.session_state:
    ensure_header_and_migrate()
    st.session_state["HEADER_OK"] = True

KOLUMNER = st.session_state["COLUMNS"]

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    rows = _retry_call(settings_ws.get_all_records)
    d = {}; labels = {}
    for r in rows:
        key = (r.get("Key") or "").strip()
        if not key: continue
        d[key] = r.get("Value")
        if r.get("Label") is not None:
            labels[key] = str(r.get("Label"))
        if key.startswith("LABEL_"):
            cname = key[len("LABEL_"):]
            if str(r.get("Value") or "").strip():
                labels[cname] = str(r.get("Value")).strip()
    return d, labels

def _save_setting(key: str, value: str, label: str|None=None):
    recs = _retry_call(settings_ws.get_all_records)
    keys = [ (r.get("Key") or "") for r in recs ]
    try:
        idx = keys.index(key)
        rowno = idx + 2
    except ValueError:
        rowno = len(recs) + 2
        _retry_call(settings_ws.update, f"A{rowno}:C{rowno}", [[key, value, label or ""]])
        return
    _retry_call(settings_ws.update, f"B{rowno}", [[value]])
    if label is not None:
        _retry_call(settings_ws.update, f"C{rowno}", [[label]])

def _get_label(labels_map: dict, default_text: str) -> str:
    return labels_map.get(default_text, default_text)

CFG_RAW, LABELS = _settings_as_dict()

def _init_cfg_defaults_from_settings():
    st.session_state.setdefault("CFG", {})
    C = st.session_state["CFG"]
    def _get(k, fb): return CFG_RAW.get(k, fb)

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

    # Bonus-räknare
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

    # Sidopanelens persistenta parametrar
    try:
        C["ESK_MIN"] = int(float(_get("ESK_MIN", 20)))
    except Exception:
        C["ESK_MIN"] = 20
    try:
        C["ESK_MAX"] = int(float(_get("ESK_MAX", 40)))
    except Exception:
        C["ESK_MAX"] = 40
    try:
        C["STAFF_PCT"] = float(_get("STAFF_PCT", 10.0))
    except Exception:
        C["STAFF_PCT"] = 10.0

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ======== Hjälpfunktioner som använder sidopanelens parametrar =========
def _personal_deltagit_suggest() -> int:
    pct = float(st.session_state.get("cfg_staff_pct", CFG.get("STAFF_PCT", 10.0)))
    total = int(CFG.get("PROD_STAFF", 800))
    return max(0, int(round(total * (pct / 100.0))))

def _rand_eskilstuna_custom() -> int:
    lo = int(st.session_state.get("cfg_esk_min", CFG.get("ESK_MIN", 20)))
    hi = int(st.session_state.get("cfg_esk_max", CFG.get("ESK_MAX", 40)))
    if hi < lo:
        lo, hi = hi, lo
    return random.randint(lo, hi) if hi >= lo else 0

# ============================ Meny & Sidopanel-top =============================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    födelsedatum = st.date_input(
        _get_label(LABELS, "Malins födelsedatum"),
        value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
        min_value=MIN_FOD, max_value=date.today()
    )

    max_p  = st.number_input(f"Max {_get_label(LABELS, 'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_get_label(LABELS, 'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_get_label(LABELS, 'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_get_label(LABELS, 'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_get_label(LABELS, 'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))
    prod_staff = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    st.markdown("**Etiketter (påverkar endast visning)**")
    lab_p   = st.text_input("Etikett: Pappans vänner", value=_get_label(LABELS, "Pappans vänner"))
    lab_g   = st.text_input("Etikett: Grannar", value=_get_label(LABELS, "Grannar"))
    lab_nv  = st.text_input("Etikett: Nils vänner", value=_get_label(LABELS, "Nils vänner"))
    lab_nf  = st.text_input("Etikett: Nils familj", value=_get_label(LABELS, "Nils familj"))
    lab_bk  = st.text_input("Etikett: Bekanta", value=_get_label(LABELS, "Bekanta"))
    lab_esk = st.text_input("Etikett: Eskilstuna killar", value=_get_label(LABELS, "Eskilstuna killar"))
    lab_man = st.text_input("Etikett: Män", value=_get_label(LABELS, "Män"))
    lab_sva = st.text_input("Etikett: Svarta", value=_get_label(LABELS, "Svarta"))
    lab_kann= st.text_input("Etikett: Känner", value=_get_label(LABELS, "Känner"))
    lab_person = st.text_input("Etikett: Personal deltagit", value=_get_label(LABELS, "Personal deltagit"))
    lab_bonus  = st.text_input("Etikett: Bonus killar", value=_get_label(LABELS, "Bonus killar"))
    lab_bonusd = st.text_input("Etikett: Bonus deltagit", value=_get_label(LABELS, "Bonus deltagit"))
    lab_mfd    = st.text_input("Etikett: Malins födelsedatum", value=_get_label(LABELS, "Malins födelsedatum"))

    st.markdown("---")
    st.subheader("👥 Personal – deltagande")
    staff_pct = st.number_input(
        "Personal deltagit (%)",
        min_value=0.0, max_value=100.0, step=0.5,
        value=float(st.session_state.get("cfg_staff_pct", CFG.get("STAFF_PCT", 10.0))),
        key="cfg_staff_pct_input"
    )
    st.session_state["cfg_staff_pct"] = float(staff_pct)
    st.caption(f"Total personal: **{int(CFG.get('PROD_STAFF', 800))}**")

    st.markdown("---")
    st.subheader("🎲 Slumpintervall – Eskilstuna killar")
    esk_min = st.number_input(
        "Min (Eskilstuna-intervall)",
        min_value=0, step=1,
        value=int(st.session_state.get("cfg_esk_min", CFG.get("ESK_MIN", 20))),
        key="cfg_esk_min_input"
    )
    esk_max = st.number_input(
        "Max (Eskilstuna-intervall)",
        min_value=0, step=1,
        value=int(st.session_state.get("cfg_esk_max", CFG.get("ESK_MAX", 40))),
        key="cfg_esk_max_input"
    )
    st.session_state["cfg_esk_min"] = int(esk_min)
    st.session_state["cfg_esk_max"] = int(esk_max)

    if st.button("💾 Spara inställningar"):
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

        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_person, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")

        # Spara sidoparametrar persistent
        _save_setting("ESK_MIN", str(int(st.session_state["cfg_esk_min"])))
        _save_setting("ESK_MAX", str(int(st.session_state["cfg_esk_max"])))
        _save_setting("STAFF_PCT", str(float(st.session_state["cfg_staff_pct"])))

        st.success("Inställningar och etiketter sparade ✅")
        st.rerun()

# ================================ PRODUKTION – SCEN & INPUTS ================================
if view == "Produktion":
    st.header("🎬 Produktion – skapa rad i minnet")

    # ---------- Småhjälp ----------
    def _L(txt: str) -> str:
        return LABELS.get(txt, txt)

    # Radräkning / datum (endast läsning; sker en gång per session)
    def _init_row_count():
        if "ROW_COUNT" not in st.session_state:
            try:
                vals = _retry_call(sheet.col_values, 1)  # kolumn A = Datum
                st.session_state.ROW_COUNT = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
            except Exception:
                st.session_state.ROW_COUNT = 0
    if "ROW_COUNT" not in st.session_state:
        _init_row_count()

    def next_scene_number():
        return st.session_state.ROW_COUNT + 1

    def datum_och_veckodag_för_scen(scen_nummer: int):
        d = CFG["startdatum"] + timedelta(days=scen_nummer - 1)
        veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
        return d, veckodagar[d.weekday()]

    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    # ---------- Scenario-väljare ----------
    scenario = st.selectbox(
        "Välj scenario",
        [
            "Ny scen",
            "Slumpa scen vit",
            "Slumpa scen svart",
            "Vila i hemmet (7 dagar – i minnet)",
            "Vila på jobbet"
        ],
        index=0,
        key="scenario_select"
    )

    # ---------- Hjälpare för fyllning ----------
    def _get_min_max(colname: str):
        """Läser endast när du aktivt väljer/slumpar. Returnerar (min,max) eller (0,0)."""
        try:
            all_rows = _retry_call(sheet.get_all_records)
        except Exception:
            return (0, 0)
        vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
        if not vals:
            return (0, 0)
        return (min(vals), max(vals))

    def _safe_set(key: str, value):
        """Säker sättning i session_state (undviker StreamlitDuplicateElementId)."""
        st.session_state[key] = value

    def _fill_personal_by_pct():
        _safe_set("in_personal", _personal_deltagit_suggest())

    def _rand_between_minmax(col: str):
        lo, hi = _get_min_max(col)
        if hi < lo:
            lo, hi = hi, lo
        return random.randint(lo, hi) if hi >= lo else 0

    # ---------- Fyll scenario (endast i minnet) ----------
    def apply_scenario_fill():
        # Nollställ inte allt – vi fyller det som scenariot bestämmer.
        if scenario == "Ny scen":
            # Endast föreslå personal enligt procent
            _fill_personal_by_pct()
            return

        if scenario == "Slumpa scen vit":
            # Värden slumpas från historiska min/max i samma kolumner
            _safe_set("in_män",          _rand_between_minmax("Män"))
            _safe_set("in_svarta",       0)  # vit scen -> svarta 0 (om inte du manuellt sätter)
            _safe_set("in_fitta",        _rand_between_minmax("Fitta"))
            _safe_set("in_rumpa",        _rand_between_minmax("Rumpa"))
            _safe_set("in_dp",           _rand_between_minmax("DP"))
            _safe_set("in_dpp",          _rand_between_minmax("DPP"))
            _safe_set("in_dap",          _rand_between_minmax("DAP"))
            _safe_set("in_tap",          _rand_between_minmax("TAP"))

            _safe_set("in_pappan",       _rand_between_minmax("Pappans vänner"))
            _safe_set("in_grannar",      _rand_between_minmax("Grannar"))
            _safe_set("in_nils_vanner",  _rand_between_minmax("Nils vänner"))
            _safe_set("in_nils_familj",  _rand_between_minmax("Nils familj"))
            _safe_set("in_bekanta",      _rand_between_minmax("Bekanta"))
            # Eskilstuna via sidopanelens intervall
            _safe_set("in_eskilstuna",   _rand_eskilstuna_custom())

            # Bonus deltagit (sattes per rad i beräkningen, men om du vill se något direkt, lämna 0)
            # Personal följer procent
            _fill_personal_by_pct()

            # Standard: Älskar=8, Sover=1
            _safe_set("in_alskar", 8)
            _safe_set("in_sover", 1)
            return

        if scenario == "Slumpa scen svart":
            # Slumpa sex-aktiviteter + svarta; alla källfält = 0, män = 0
            _safe_set("in_män", 0)
            _safe_set("in_svarta",      _rand_between_minmax("Svarta"))
            _safe_set("in_fitta",       _rand_between_minmax("Fitta"))
            _safe_set("in_rumpa",       _rand_between_minmax("Rumpa"))
            _safe_set("in_dp",          _rand_between_minmax("DP"))
            _safe_set("in_dpp",         _rand_between_minmax("DPP"))
            _safe_set("in_dap",         _rand_between_minmax("DAP"))
            _safe_set("in_tap",         _rand_between_minmax("TAP"))

            _safe_set("in_pappan",      0)
            _safe_set("in_grannar",     0)
            _safe_set("in_nils_vanner", 0)
            _safe_set("in_nils_familj", 0)
            _safe_set("in_bekanta",     0)
            _safe_set("in_eskilstuna",  0)

            # Personal följer procent
            _fill_personal_by_pct()

            _safe_set("in_alskar", 8)
            _safe_set("in_sover", 1)
            return

        if scenario == "Vila på jobbet":
            # En enkel prefill för en "vila"-rad i minnet (sparas ej).
            _safe_set("in_män", 0)
            _safe_set("in_svarta", 0)
            _safe_set("in_fitta", 0)
            _safe_set("in_rumpa", 0)
            _safe_set("in_dp", 0)
            _safe_set("in_dpp", 0)
            _safe_set("in_dap", 0)
            _safe_set("in_tap", 0)

            # 40–60% av max för källor
            def _r46(mx): 
                try: mx=int(mx)
                except: mx=0
                if mx<=0: return 0
                lo=max(0,int(round(mx*0.40))); hi=max(lo,int(round(mx*0.60)))
                return random.randint(lo, hi)

            _safe_set("in_pappan",      _r46(CFG["MAX_PAPPAN"]))
            _safe_set("in_grannar",     _r46(CFG["MAX_GRANNAR"]))
            _safe_set("in_nils_vanner", _r46(CFG["MAX_NILS_VANNER"]))
            _safe_set("in_nils_familj", _r46(CFG["MAX_NILS_FAMILJ"]))
            _safe_set("in_bekanta",     _r46(CFG["MAX_BEKANTA"]))
            _safe_set("in_eskilstuna",  _rand_eskilstuna_custom())

            # Älskar/Sover standard för "vila på jobbet"
            _safe_set("in_alskar", 12)
            _safe_set("in_sover", 1)

            # Personal följer procent
            _fill_personal_by_pct()
            return

        if scenario == "Vila i hemmet (7 dagar – i minnet)":
            # Denna fyller en “batch” i session_state (INGEN sparning).
            # Vi renderar batchen senare i Del 3/5.
            # Sätt en flagga + skapa listan “HOME_BATCH” i sessionen.
            batch = []
            start_scene = scen

            # Nils 50/45/5 (antal ettor dag 1–6)
            r = random.random()
            if r < 0.50: ones_count = 0
            elif r < 0.95: ones_count = 1
            else: ones_count = 2
            nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

            def _r46(mx): 
                try: mx=int(mx)
                except: mx=0
                if mx<=0: return 0
                lo=max(0,int(round(mx*0.40))); hi=max(lo,int(round(mx*0.60)))
                return random.randint(lo, hi)

            for offset in range(7):
                scen_num = start_scene + offset
                rd, vd = datum_och_veckodag_för_scen(scen_num)

                if offset <= 4:
                    pv = _r46(CFG["MAX_PAPPAN"])
                    gr = _r46(CFG["MAX_GRANNAR"])
                    nv = _r46(CFG["MAX_NILS_VANNER"])
                    nf = _r46(CFG["MAX_NILS_FAMILJ"])
                    bk = _r46(CFG["MAX_BEKANTA"])
                    esk = _rand_eskilstuna_custom()
                    pers = _personal_deltagit_suggest()
                else:
                    pv = gr = nv = nf = bk = 0
                    esk = _rand_eskilstuna_custom()
                    pers = 0

                sv = 1 if offset == 6 else 0
                nils_val = 0 if offset == 6 else (1 if offset in nils_one_offsets else 0)

                base = {
                    "Typ": "Vila i hemmet",
                    "Veckodag": vd, "Scen": scen_num,
                    "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
                    "Tid S": 0, "Tid D": 0, "Vila": 0,
                    "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
                    "Älskar": 6, "Sover med": sv,
                    "Pappans vänner": pv, "Grannar": gr,
                    "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
                    "Bonus killar": 0, "Bonus deltagit": 0,
                    "Personal deltagit": pers,
                    "Nils": nils_val,
                    "Avgift": float(CFG.get("avgift_usd", 30.0)),
                    "Datum": rd.isoformat()
                }
                batch.append(base)

            st.session_state["HOME_BATCH"] = batch
            st.session_state["HOME_BATCH_IDX"] = 0
            st.session_state["HOME_BATCH_ACTIVE"] = True
            return

    # En knapp för att APPLY scenariot (så vi inte fyller på varje render)
    if st.button("⚙️ Fyll enligt valt scenario"):
        apply_scenario_fill()
        st.rerun()

    # ---------- Input-fält (DIN ÖNSKADE ORDNING) ----------
    # Säkerställ defaults
    st.session_state.setdefault("in_män", 0)
    st.session_state.setdefault("in_svarta", 0)
    st.session_state.setdefault("in_fitta", 0)
    st.session_state.setdefault("in_rumpa", 0)
    st.session_state.setdefault("in_dp", 0)
    st.session_state.setdefault("in_dpp", 0)
    st.session_state.setdefault("in_dap", 0)
    st.session_state.setdefault("in_tap", 0)
    st.session_state.setdefault("in_pappan", 0)
    st.session_state.setdefault("in_grannar", 0)
    st.session_state.setdefault("in_nils_vanner", 0)
    st.session_state.setdefault("in_nils_familj", 0)
    st.session_state.setdefault("in_bekanta", 0)
    st.session_state.setdefault("in_eskilstuna", 0)
    st.session_state.setdefault("in_bonus_deltagit", 0)
    st.session_state.setdefault("in_personal", _personal_deltagit_suggest())
    st.session_state.setdefault("in_alskar", 0)
    st.session_state.setdefault("in_sover", 0)
    st.session_state.setdefault("in_tid_s", 60)
    st.session_state.setdefault("in_tid_d", 60)
    st.session_state.setdefault("in_vila", 7)
    st.session_state.setdefault("in_dt_tid", 60)
    st.session_state.setdefault("in_dt_vila", 3)
    st.session_state.setdefault("in_nils", 0)
    st.session_state.setdefault("in_avgift", float(CFG["avgift_usd"]))

    # Rendera inputs i exakt ordning du angivit
    cols = st.columns(4)

    with cols[0]:
        män    = st.number_input(_L("Män"), min_value=0, step=1, value=st.session_state["in_män"], key="in_män")
        fitta  = st.number_input("Fitta", min_value=0, step=1, value=st.session_state["in_fitta"], key="in_fitta")
        dp     = st.number_input("DP", min_value=0, step=1, value=st.session_state["in_dp"], key="in_dp")
        dap    = st.number_input("DAP", min_value=0, step=1, value=st.session_state["in_dap"], key="in_dap")

    with cols[1]:
        svarta = st.number_input(_L("Svarta"), min_value=0, step=1, value=st.session_state["in_svarta"], key="in_svarta")
        rumpa  = st.number_input("Rumpa", min_value=0, step=1, value=st.session_state["in_rumpa"], key="in_rumpa")
        dpp    = st.number_input("DPP", min_value=0, step=1, value=st.session_state["in_dpp"], key="in_dpp")
        tap    = st.number_input("TAP", min_value=0, step=1, value=st.session_state["in_tap"], key="in_tap")

    with cols[2]:
        pappans_vänner = st.number_input(_L("Pappans vänner"), min_value=0, step=1, value=st.session_state["in_pappan"], key="in_pappan")
        grannar        = st.number_input(_L("Grannar"), min_value=0, step=1, value=st.session_state["in_grannar"], key="in_grannar")
        nils_vänner    = st.number_input(_L("Nils vänner"), min_value=0, step=1, value=st.session_state["in_nils_vanner"], key="in_nils_vanner")
        nils_familj    = st.number_input(_L("Nils familj"), min_value=0, step=1, value=st.session_state["in_nils_familj"], key="in_nils_familj")

    with cols[3]:
        bekanta        = st.number_input(_L("Bekanta"), min_value=0, step=1, value=st.session_state["in_bekanta"], key="in_bekanta")
        eskilstuna_killar = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, value=st.session_state["in_eskilstuna"], key="in_eskilstuna")
        bonus_deltagit    = st.number_input(_L("Bonus deltagit"), min_value=0, step=1, value=st.session_state["in_bonus_deltagit"], key="in_bonus_deltagit")
        personal_deltagit = st.number_input(_L("Personal deltagit"), min_value=0, step=1, value=_personal_deltagit_suggest(), key="in_personal")

    cols2 = st.columns(4)
    with cols2[0]:
        älskar    = st.number_input("Älskar", min_value=0, step=1, value=st.session_state["in_alskar"], key="in_alskar")
    with cols2[1]:
        sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=st.session_state["in_sover"], key="in_sover")
    with cols2[2]:
        tid_s     = st.number_input("Tid S (sek)", min_value=0, step=1, value=st.session_state["in_tid_s"], key="in_tid_s")
    with cols2[3]:
        tid_d     = st.number_input("Tid D (sek)", min_value=0, step=1, value=st.session_state["in_tid_d"], key="in_tid_d")

    cols3 = st.columns(4)
    with cols3[0]:
        vila      = st.number_input("Vila (sek)", min_value=0, step=1, value=st.session_state["in_vila"], key="in_vila")
    with cols3[1]:
        dt_tid    = st.number_input("DT tid (sek/kille)", min_value=0, step=1, value=st.session_state["in_dt_tid"], key="in_dt_tid")
    with cols3[2]:
        dt_vila   = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=st.session_state["in_dt_vila"], key="in_dt_vila")
    with cols3[3]:
        nils      = st.number_input("Nils", min_value=0, step=1, value=st.session_state["in_nils"], key="in_nils")

    avgift_val = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(st.session_state.get("in_avgift", CFG["avgift_usd"])), key="in_avgift")

    # Max-varningar (visning)
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

    # Grunddata till preview-beräkning (INGET sparas här)
    grund_preview = {
        "Typ": "" if scenario in ("Ny scen","Slumpa scen vit","Slumpa scen svart") else scenario.replace(" (7 dagar – i minnet)", ""),
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
        "Bonus killar": 0, "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": personal_deltagit,
        "Nils": nils,
        "Avgift": float(avgift_val),
    }

    # Denna “grund_preview” används av live-beräkningen i nästa del.

    # ============================ Live-beräkning / Preview ============================
    def _calc_preview(grund):
        try:
            if callable(calc_row_values):
                return calc_row_values(grund, rad_datum, CFG["födelsedatum"], CFG["starttid"])
            else:
                return {}
        except Exception as e:
            st.warning(f"Förhandsberäkning misslyckades: {e}")
            return {}

    preview = _calc_preview(grund_preview)

    # Ålder i live (vid rad_datum)
    try:
        fod = CFG["födelsedatum"]
        age_years = rad_datum.year - fod.year - ((rad_datum.month, rad_datum.day) < (fod.month, fod.day))
    except Exception:
        age_years = "-"

    st.markdown("---")
    st.subheader("🔎 Förhandsvisning (innan spar)")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
        st.metric("Malins ålder (live)", f"{age_years} år")
        st.metric("Summa tid", preview.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
        st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    with col2:
        st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
        st.metric("Tid per kille", preview.get("Tid per kille", "-"))
        st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
        st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

    st.markdown("#### 💵 Ekonomi (live)")
    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
        st.metric("Avgift (rad)", _usd(preview.get("Avgift", grund_preview.get("Avgift", CFG['avgift_usd']))))
    with ec2:
        st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
        st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
    with ec3:
        st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
        st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
    with ec4:
        st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

    # ====================== Batch: "Vila i hemmet (7 dagar – i minnet)" ======================
    st.markdown("---")
    if st.session_state.get("HOME_BATCH_ACTIVE", False):
        st.subheader("🏠 Förhandsgranska 'Vila i hemmet' (7 dagar) – i minnet")

        batch = st.session_state.get("HOME_BATCH", [])
        idx = int(st.session_state.get("HOME_BATCH_IDX", 0))
        total = len(batch)

        if total == 0:
            st.info("Ingen batch skapad ännu.")
        else:
            # Navigering
            nav1, nav2, nav3 = st.columns([1,1,2])
            with nav1:
                if st.button("⬅️ Föregående", disabled=(idx <= 0)):
                    st.session_state["HOME_BATCH_IDX"] = max(0, idx - 1)
                    st.rerun()
            with nav2:
                if st.button("Nästa ➡️", disabled=(idx >= total - 1)):
                    st.session_state["HOME_BATCH_IDX"] = min(total - 1, idx + 1)
                    st.rerun()
            with nav3:
                st.caption(f"Dag {idx+1} av {total}")

            current = batch[idx]
            # Visa en liten sammanfattning
            info_cols = st.columns(3)
            with info_cols[0]:
                st.metric("Datum", current.get("Datum", "-"))
                st.metric("Typ", current.get("Typ", "-"))
                st.metric("Veckodag", current.get("Veckodag", "-"))
            with info_cols[1]:
                st.metric("Känner (sum)", 
                    sum([
                        _safe_int(current.get("Pappans vänner", 0)),
                        _safe_int(current.get("Grannar", 0)),
                        _safe_int(current.get("Nils vänner", 0)),
                        _safe_int(current.get("Nils familj", 0)),
                    ])
                )
                st.metric("Eskilstuna killar", _safe_int(current.get("Eskilstuna killar", 0)))
                st.metric("Personal deltagit", _safe_int(current.get("Personal deltagit", 0)))
            with info_cols[2]:
                st.metric("Älskar", _safe_int(current.get("Älskar", 0)))
                st.metric("Sover med", _safe_int(current.get("Sover med", 0)))
                st.metric("Avgift", _usd(current.get("Avgift", CFG["avgift_usd"])))

            # Låt dig tillämpa denna dags värden på inputfälten (fortfarande i minnet)
            def _apply_home_day_to_inputs(day_obj: dict):
                # Sätt endast definierade fält
                mapping = {
                    "Män": "in_män",
                    "Svarta": "in_svarta",
                    "Fitta": "in_fitta",
                    "Rumpa": "in_rumpa",
                    "DP": "in_dp",
                    "DPP": "in_dpp",
                    "DAP": "in_dap",
                    "TAP": "in_tap",
                    "Pappans vänner": "in_pappan",
                    "Grannar": "in_grannar",
                    "Nils vänner": "in_nils_vanner",
                    "Nils familj": "in_nils_familj",
                    "Bekanta": "in_bekanta",
                    "Eskilstuna killar": "in_eskilstuna",
                    "Bonus deltagit": "in_bonus_deltagit",
                    "Personal deltagit": "in_personal",
                    "Älskar": "in_alskar",
                    "Sover med": "in_sover",
                    "Tid S": "in_tid_s",
                    "Tid D": "in_tid_d",
                    "Vila": "in_vila",
                    "DT tid (sek/kille)": "in_dt_tid",
                    "DT vila (sek/kille)": "in_dt_vila",
                    "Nils": "in_nils",
                    "Avgift": "in_avgift",
                }
                for k, target in mapping.items():
                    if k in day_obj:
                        st.session_state[target] = day_obj[k]

            if st.button("📥 Använd denna dag i inputs (redigera innan spar)"):
                _apply_home_day_to_inputs(current)
                # Uppdatera “scenario” text för tydlighet
                st.session_state["scenario_select"] = "Vila i hemmet (7 dagar – i minnet)"
                st.success("Dagens värden har lagts i inputfälten. Du kan redigera innan du sparar.")
                st.rerun()

            st.info("Inget sparas till databasen förrän du klickar på **Spara raden** (finns längre ner).")

    # ============================== Spara / Auto-Max ==============================
    def _ensure_header_once():
        """Skapa/migrera header ENDAST när vi ska spara första gången i sessionen."""
        if st.session_state.get("_HEADER_OK", False):
            return
        try:
            header = _retry_call(sheet.row_values, 1)
        except Exception as e:
            st.error(f"Kunde inte läsa header vid sparning: {e}")
            return
        if not header:
            _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
            st.session_state["_HEADER_OK"] = True
            st.session_state["COLUMNS"] = DEFAULT_COLUMNS
            return
        missing = [c for c in DEFAULT_COLUMNS if c not in header]
        if missing:
            from gspread.utils import rowcol_to_a1
            new_header = header + missing
            end_cell = rowcol_to_a1(1, len(new_header))
            _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
            st.session_state["COLUMNS"] = new_header
        else:
            st.session_state["COLUMNS"] = header
        st.session_state["_HEADER_OK"] = True

    def _parse_date_for_save(d):
        if isinstance(d, date):
            return d
        return datetime.strptime(str(d), "%Y-%m-%d").date()

    def _save_row(grund, rad_datum, veckodag):
        """Beräkna + spara EN rad till Sheets (kallas först när du klickar Spara)."""
        try:
            _ensure_header_once()
            base = dict(grund)
            base.setdefault("Avgift", float(CFG["avgift_usd"]))
            if not callable(calc_row_values):
                st.error("Beräkningsmodulen (berakningar.py) saknas eller saknar berakna_radvarden().")
                return
            ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
            ber["Datum"] = rad_datum.isoformat()
            ber["Veckodag"] = veckodag
        except Exception as e:
            st.error(f"Beräkningen misslyckades vid sparning: {e}")
            return

        cols = st.session_state.get("COLUMNS", DEFAULT_COLUMNS)
        row = [ber.get(col, "") for col in cols]
        try:
            _retry_call(sheet.append_row, row)
        except Exception as e:
            st.error(f"Kunde inte spara raden: {e}")
            return

        # Uppdatera lokal radräknare för framtida scen-nummer
        st.session_state.ROW_COUNT = st.session_state.get(ROW_COUNT_KEY, 0) + 1
        st.session_state[ROW_COUNT_KEY] = st.session_state.ROW_COUNT

        # Åldersfeedback
        fod = CFG["födelsedatum"]
        alder = rad_datum.year - fod.year - ((rad_datum.month, rad_datum.day) < (fod.month, fod.day))
        st.success(f"✅ Rad sparad. Datum {rad_datum} ({veckodag}), Malins ålder {alder} år, Klockan {ber.get('Klockan','-')}")

    # Samla Auto-Max varningar (endast visning — uppdatering sker först om du väljer det)
    over_max = {}
    if pappans_vänner > int(CFG["MAX_PAPPAN"]):
        over_max[_L('Pappans vänner')] = {"current_max": int(CFG["MAX_PAPPAN"]), "new_value": int(pappans_vänner), "max_key": "MAX_PAPPAN"}
    if grannar > int(CFG["MAX_GRANNAR"]):
        over_max[_L('Grannar')] = {"current_max": int(CFG["MAX_GRANNAR"]), "new_value": int(grannar), "max_key": "MAX_GRANNAR"}
    if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
        over_max[_L('Nils vänner')] = {"current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": int(nils_vänner), "max_key": "MAX_NILS_VANNER"}
    if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
        over_max[_L('Nils familj')] = {"current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": int(nils_familj), "max_key": "MAX_NILS_FAMILJ"}
    if bekanta > int(CFG["MAX_BEKANTA"]):
        over_max[_L('Bekanta')] = {"current_max": int(CFG["MAX_BEKANTA"]), "new_value": int(bekanta), "max_key": "MAX_BEKANTA"}

    # Primär spar-knapp (sparar EN aktuell rad — aldrig batch här)
    if st.button("💾 Spara raden till databasen"):
        if over_max:
            # Visa dialog i session_state (inga IO här)
            st.session_state["PENDING_SAVE"] = {
                "grund": grund_preview,
                "rad_datum": str(rad_datum),
                "veckodag": veckodag,
                "over_max": over_max,
            }
            st.rerun()
        else:
            _save_row(grund_preview, rad_datum, veckodag)

    # Auto-Max dialog (frivillig)
    if "PENDING_SAVE" in st.session_state:
        pending = st.session_state["PENDING_SAVE"]
        st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara raden?")
        for f, info in pending["over_max"].items():
            st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Uppdatera max och spara"):
                try:
                    # Uppdatera maxvärden i Inställningar (skrivning sker först nu)
                    for _, info in pending["over_max"].items():
                        _save_setting(info["max_key"], str(info["new_value"]))
                        CFG[info["max_key"]] = info["new_value"]
                    # Spara raden
                    _save_row(pending["grund"], _parse_date_for_save(pending["rad_datum"]), pending["veckodag"])
                except Exception as e:
                    st.error(f"Misslyckades: {e}")
                finally:
                    st.session_state.pop("PENDING_SAVE", None)
                    st.rerun()
        with c2:
            if st.button("✋ Spara utan att uppdatera max"):
                try:
                    _save_row(pending["grund"], _parse_date_for_save(pending["rad_datum"]), pending["veckodag"])
                except Exception as e:
                    st.error(f"Misslyckades: {e}")
                finally:
                    st.session_state.pop("PENDING_SAVE", None)
                    st.rerun()

    # ============================ Visa & radera (manuella IO) ============================
    st.markdown("---")
    st.subheader("📊 Visa data (explicit hämtning)")
    if st.button("🔄 Hämta data nu"):
        try:
            data_rows = _retry_call(sheet.get_all_records)
            st.session_state["_LAST_FETCH"] = data_rows
            st.success(f"Hämtade {len(data_rows)} rader.")
        except Exception as e:
            st.error(f"Kunde inte läsa data: {e}")

    # Visa senaste hämtade dataset (utan att fråga Sheets igen)
    last = st.session_state.get("_LAST_FETCH", None)
    if last is not None:
        st.dataframe(last, use_container_width=True)
    else:
        st.caption("Inget hämtat ännu. Klicka på **Hämta data nu** för att läsa från databasen.")

    st.subheader("🗑 Ta bort rad (explicit)")
    # Läs radantal endast när du klickar på knappen nedan
    if st.button("🔍 Hämta antal rader"):
        try:
            vals = _retry_call(sheet.col_values, 1)  # kolumn A = Datum
            rc = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
            st.session_state["_REMOTE_ROWS"] = rc
            st.success(f"Databasen har {rc} datarader (exkl. header).")
        except Exception as e:
            st.error(f"Kunde inte läsa antal rader: {e}")

    remote_rows = st.session_state.get("_REMOTE_ROWS", 0)
    if remote_rows > 0:
        idx = st.number_input(
            "Radnummer att ta bort (1 = första dataraden)",
            min_value=1,
            max_value=remote_rows,
            step=1,
            value=1,
            key="del_idx",
        )
        if st.button("🗑 Ta bort vald rad nu"):
            try:
                _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 för header
                st.success(f"Rad {idx} borttagen.")
                # Invalidera lokal cache så man kan hämta igen
                st.session_state.pop("_LAST_FETCH", None)
                st.session_state.pop("_REMOTE_ROWS", None)
            except Exception as e:
                st.error(f"Kunde inte ta bort rad: {e}")
    else:
        st.caption("Okänt antal rader. Klicka på **Hämta antal rader** först.")

    # ============================== Sidopanel (etiketter & params) ==============================
    st.sidebar.header("Inställningar")

    # Initiera UI-state en gång per session (påverkar bara live, inte Sheets)
    if "ui_personal_pct" not in st.session_state:
        st.session_state.ui_personal_pct = 10.0
    if "ui_esk_min" not in st.session_state:
        st.session_state.ui_esk_min = 20
    if "ui_esk_max" not in st.session_state:
        st.session_state.ui_esk_max = 40

    with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
        # Datum & tider (visas – sparas först vid klick)
        startdatum = st.date_input("Historiskt startdatum", value=CFG["startdatum"], key="cfg_startdatum")
        starttid   = st.time_input("Starttid", value=CFG["starttid"], key="cfg_starttid")
        foddag     = st.date_input(_get_label(LABELS, "Malins födelsedatum"), value=CFG["födelsedatum"],
                                   min_value=date(1970,1,1), max_value=date.today(), key="cfg_foddag")

        # Max för källor
        max_p  = st.number_input(f"Max {_get_label(LABELS, 'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]), key="cfg_max_p")
        max_g  = st.number_input(f"Max {_get_label(LABELS, 'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]), key="cfg_max_g")
        max_nv = st.number_input(f"Max {_get_label(LABELS, 'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]), key="cfg_max_nv")
        max_nf = st.number_input(f"Max {_get_label(LABELS, 'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]), key="cfg_max_nf")
        max_bk = st.number_input(f"Max {_get_label(LABELS, 'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]), key="cfg_max_bk")

        # Produktionspersonal (fast) och procent som deltar i live
        prod_staff = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]), key="cfg_prod_staff")
        st.session_state.ui_personal_pct = st.number_input(
            "Personal deltagit (% av total personal)", min_value=0.0, max_value=100.0, step=0.1,
            value=float(st.session_state.ui_personal_pct), key="ui_personal_pct_input"
        )

        # Eskilstuna slumpintervall för live
        st.session_state.ui_esk_min = st.number_input(
            "Eskilstuna killar – minimum (slumpintervall)", min_value=0, step=1,
            value=int(st.session_state.ui_esk_min), key="ui_esk_min_input"
        )
        st.session_state.ui_esk_max = st.number_input(
            "Eskilstuna killar – maximum (slumpintervall)", min_value=0, step=1,
            value=int(st.session_state.ui_esk_max), key="ui_esk_max_input"
        )
        if st.session_state.ui_esk_max < st.session_state.ui_esk_min:
            st.session_state.ui_esk_max = st.session_state.ui_esk_min

        avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0,
                                       value=float(CFG["avgift_usd"]), key="cfg_fee")

        st.markdown("**Etiketter (påverkar endast visning)**")
        lab_p   = st.text_input("Etikett: Pappans vänner", value=_get_label(LABELS, "Pappans vänner"), key="lab_p")
        lab_g   = st.text_input("Etikett: Grannar", value=_get_label(LABELS, "Grannar"), key="lab_g")
        lab_nv  = st.text_input("Etikett: Nils vänner", value=_get_label(LABELS, "Nils vänner"), key="lab_nv")
        lab_nf  = st.text_input("Etikett: Nils familj", value=_get_label(LABELS, "Nils familj"), key="lab_nf")
        lab_bk  = st.text_input("Etikett: Bekanta", value=_get_label(LABELS, "Bekanta"), key="lab_bk")
        lab_esk = st.text_input("Etikett: Eskilstuna killar", value=_get_label(LABELS, "Eskilstuna killar"), key="lab_esk")
        lab_man = st.text_input("Etikett: Män", value=_get_label(LABELS, "Män"), key="lab_man")
        lab_sv  = st.text_input("Etikett: Svarta", value=_get_label(LABELS, "Svarta"), key="lab_sv")
        lab_k   = st.text_input("Etikett: Känner", value=_get_label(LABELS, "Känner"), key="lab_k")
        lab_per = st.text_input("Etikett: Personal deltagit", value=_get_label(LABELS, "Personal deltagit"), key="lab_per")
        lab_bon = st.text_input("Etikett: Bonus killar", value=_get_label(LABELS, "Bonus killar"), key="lab_bon")
        lab_bod = st.text_input("Etikett: Bonus deltagit", value=_get_label(LABELS, "Bonus deltagit"), key="lab_bod")
        lab_mfd = st.text_input("Etikett: Malins födelsedatum", value=_get_label(LABELS, "Malins födelsedatum"), key="lab_mfd")

        if st.button("💾 Spara inställningar & etiketter"):
            _save_setting("startdatum", startdatum.isoformat())
            _save_setting("starttid", starttid.strftime("%H:%M"))
            _save_setting("födelsedatum", foddag.isoformat(), label=lab_mfd)

            _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
            _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
            _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
            _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
            _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)

            _save_setting("PROD_STAFF", str(int(prod_staff)))
            _save_setting("avgift_usd", str(float(avgift_input)))

            # UI-parametrar (sparas ej i Sheets – driver live)
            st.session_state.ui_personal_pct = float(st.session_state.ui_personal_pct)
            st.session_state.ui_esk_min = int(st.session_state.ui_esk_min)
            st.session_state.ui_esk_max = int(st.session_state.ui_esk_max)

            # Etikett-override (LABEL_*)
            _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
            _save_setting("LABEL_Män", lab_man, label="")
            _save_setting("LABEL_Svarta", lab_sv, label="")
            _save_setting("LABEL_Känner", lab_k, label="")
            _save_setting("LABEL_Personal deltagit", lab_per, label="")
            _save_setting("LABEL_Bonus killar", lab_bon, label="")
            _save_setting("LABEL_Bonus deltagit", lab_bod, label="")

            st.success("Inställningar & etiketter sparade. Ladda om för att se uppdaterade etiketter i alla vyer.")
            st.rerun()

    # Hjälptext i sidopanelen: visa aktiva live-parametrar (ingen Sheets-access)
    st.sidebar.caption(
        f"**Personal deltagit** = {st.session_state.ui_personal_pct:.1f}% av {CFG['PROD_STAFF']}  •  "
        f"**Eskilstuna slump** = {st.session_state.ui_esk_min}–{st.session_state.ui_esk_max}"
    )

    # =============================== Statistik – explicit ===============================
    if view == "Statistik":
        st.markdown("---")
        st.subheader("📥 Läs data (explicit)")
        if st.button("🔄 Hämta data för statistik"):
            try:
                rows = _retry_call(sheet.get_all_records)
                st.session_state["_STAT_RS"] = rows
                st.success(f"Hämtade {len(rows)} rader.")
            except Exception as e:
                st.error(f"Kunde inte läsa data: {e}")

        data = st.session_state.get("_STAT_RS")
        if not data:
            st.info("Ingen statistik hämtad. Klicka på **Hämta data för statistik** först.")
        else:
            # --- Bas-summeringar & KPI (samma logik som tidigare delar) ---
            rows = data
            def _row_tot_men(r):
                if "Totalt Män" in r and str(r.get("Totalt Män", "")).strip() != "":
                    return _safe_int(r.get("Totalt Män", 0), 0)
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
            bonus_deltagit_sum = 0
            personal_deltagit_sum = 0
            svarta_like_sum = 0
            tot_for_andel_svarta = 0

            # Prenumeranter 30 dagar
            total_pren = 0
            cutoff = date.today() - timedelta(days=30)
            aktiva_pren = 0

            for r in rows:
                typ = (r.get("Typ") or "").strip()
                tot_men_row = _row_tot_men(r)

                if tot_men_row > 0:
                    antal_scener += 1
                elif _safe_int(r.get("Känner", 0), 0) > 0:
                    privat_gb_cnt += 1

                totalt_man_sum += tot_men_row

                svarta_like_sum += _safe_int(r.get("Svarta", 0), 0) + _safe_int(r.get("Bonus deltagit", 0), 0)
                tot_for_andel_svarta += max(0, tot_men_row)

                bonus_deltagit_sum += _safe_int(r.get("Bonus deltagit", 0), 0)
                personal_deltagit_sum += _safe_int(r.get("Personal deltagit", 0), 0)

                if typ not in ("Vila på jobbet", "Vila i hemmet"):
                    total_pren += _safe_int(r.get("Prenumeranter", 0), 0)
                    d = _parse_iso_date(r.get("Datum", ""))
                    if d and d >= cutoff:
                        aktiva_pren += _safe_int(r.get("Prenumeranter", 0), 0)

            andel_svarta_pct = round((svarta_like_sum / tot_for_andel_svarta) * 100, 2) if tot_for_andel_svarta > 0 else 0.0

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Antal scener", antal_scener)
            with c2: st.metric("Privat GB", privat_gb_cnt)
            with c3: st.metric("Totalt män (summa)", totalt_man_sum)
            with c4: st.metric("Andel svarta (%)", andel_svarta_pct)

            c5, c6 = st.columns(2)
            with c5: st.metric("Bonus killar (deltagit, sum)", bonus_deltagit_sum)
            with c6: st.metric("Personal (deltagit, sum)", personal_deltagit_sum)

            st.markdown("---")
            st.subheader("👥 Prenumeranter")
            pc1, pc2 = st.columns(2)
            with pc1: st.metric("Prenumeranter (totalt)", int(total_pren))
            with pc2: st.metric("Aktiva prenumeranter (30 dagar)", int(aktiva_pren))

            # DP/DPP/DAP/TAP
            st.markdown("---")
            st.subheader("🔩 DP / DPP / DAP / TAP — summa & snitt per scen")
            dp_sum  = sum(_safe_int(r.get("DP", 0))  for r in rows if _safe_int(r.get("DP", 0))  > 0)
            dpp_sum = sum(_safe_int(r.get("DPP", 0)) for r in rows if _safe_int(r.get("DPP", 0)) > 0)
            dap_sum = sum(_safe_int(r.get("DAP", 0)) for r in rows if _safe_int(r.get("DAP", 0)) > 0)
            tap_sum = sum(_safe_int(r.get("TAP", 0)) for r in rows if _safe_int(r.get("TAP", 0)) > 0)
            denom_scen = antal_scener if antal_scener > 0 else 1
            st.metric("Summa DP (>0)", dp_sum)
            st.metric("Summa DPP (>0)", dpp_sum)
            st.metric("Summa DAP (>0)", dap_sum)
            st.metric("Summa TAP (>0)", tap_sum)
            st.caption(f"Snitt DP/DPP/DAP/TAP per scen: "
                       f"{round(dp_sum/denom_scen,2)}/{round(dpp_sum/denom_scen,2)}/"
                       f"{round(dap_sum/denom_scen,2)}/{round(tap_sum/denom_scen,2)}")
