# app.py
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

def _age_on(dob: date, on_date: date) -> int:
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))

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
        ws = spreadsheet.add_worksheet(title=title, rows=200 if title==SETTINGS_SHEET else 2000, cols=120)
        if title == SETTINGS_SHEET:
            _retry_call(ws.update, "A1:D1", [["Key","Value","Label","Help"]])
            # Grundvärden + etiketter & bonusräknare (en gång)
            defaults = [
                ["startdatum", date.today().isoformat(), "", ""],
                ["starttid", "07:00", "", ""],
                ["födelsedatum", date(1990,1,1).isoformat(), "Malins födelsedatum", ""],

                ["MAX_PAPPAN", "10", "Pappans vänner", ""],
                ["MAX_GRANNAR", "10", "Grannar", ""],
                ["MAX_NILS_VANNER", "10", "Nils vänner", ""],
                ["MAX_NILS_FAMILJ", "10", "Nils familj", ""],
                ["MAX_BEKANTA", "10", "Bekanta", ""],

                ["avgift_usd", "30.0", "Avgift (USD/rad)", ""],
                ["PROD_STAFF", "800", "Produktionspersonal (fast)", ""],
                ["PERSONAL_PCT", "10", "Personal deltagit %", "Standard 10% av PROD_STAFF"],

                ["ESK_MIN", "20", "Esk-min", "Eskilstuna killar min vid slump"],
                ["ESK_MAX", "40", "Esk-max", "Eskilstuna killar max vid slump"],

                # Bonusräknare (persistenta totals)
                ["BONUS_TOTAL", "0", "Bonus killar totalt", ""],
                ["BONUS_USED",  "0", "Bonus killar deltagit", ""],
                ["BONUS_LEFT",  "0", "Bonus killar kvar", ""],

                # Etikett-override (visning)
                ["LABEL_Pappans vänner", "", "", ""],
                ["LABEL_Grannar", "", "", ""],
                ["LABEL_Nils vänner", "", "", ""],
                ["LABEL_Nils familj", "", "", ""],
                ["LABEL_Bekanta", "", "", ""],
                ["LABEL_Eskilstuna killar", "", "", ""],
                ["LABEL_Män", "", "", ""],
                ["LABEL_Svarta", "", "", ""],
                ["LABEL_Känner", "", "", ""],
                ["LABEL_Personal deltagit", "", "", ""],
                ["LABEL_Bonus killar", "", "", ""],
                ["LABEL_Bonus deltagit", "", "", ""],
                ["LABEL_Malins födelsedatum", "", "", ""],
            ]
            _retry_call(ws.update, f"A2:D{len(defaults)+1}", defaults)
        return ws

sheet = _get_ws(WORKSHEET_TITLE)
settings_ws = _get_ws(SETTINGS_SHEET)

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
        new_header = header + missing
        from gspread.utils import rowcol_to_a1
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
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
    C["PERSONAL_PCT"]     = float(_get("PERSONAL_PCT", 10))  # %

    # Eskilstuna-intervall
    C["ESK_MIN"]          = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]          = int(float(_get("ESK_MAX", 40)))

    # Bonus-räknare (persistenta totals – används i statistik/översikt, ej för live)
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ===== Meny (vyval) =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# ===== Sidopanel: etiketter + personal% + Eskiltuna-intervall (utan skrivning förrän klick) =====
with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], date(1990,1,1), date(2100,1,1)))
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    fod = st.date_input(_get_label(LABELS,"Malins födelsedatum"), value=_clamp(CFG["födelsedatum"], date(1970,1,1), date.today()))

    max_p  = st.number_input(f"Max {_get_label(LABELS,'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_get_label(LABELS,'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_get_label(LABELS,'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_get_label(LABELS,'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_get_label(LABELS,'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

    prod_staff = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    personal_pct = st.number_input("Personal deltagit (%)", min_value=0.0, max_value=100.0, step=0.5, value=float(CFG["PERSONAL_PCT"]))
    esk_min = st.number_input("Eskilstuna-killar: min", min_value=0, step=1, value=int(CFG["ESK_MIN"]))
    esk_max = st.number_input("Eskilstuna-killar: max", min_value=0, step=1, value=int(CFG["ESK_MAX"]))
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
        _save_setting("startdatum", startdatum.isoformat())
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", fod.isoformat(), label=lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)

        _save_setting("PROD_STAFF", str(int(prod_staff)))
        _save_setting("PERSONAL_PCT", str(float(personal_pct)))
        _save_setting("ESK_MIN", str(int(esk_min)))
        _save_setting("ESK_MAX", str(int(esk_max)))
        _save_setting("avgift_usd", str(float(avgift_input)))

        # Etikett-override som label-only
        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_person, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")

        st.success("Inställningar och etiketter sparade ✅")
        st.rerun()

# ================================ PRODUKTION – SCENARIO & INPUTS ================================
ROW_COUNT_KEY = "ROW_COUNT_CACHE"

def _init_row_counter_no_sheet():
    # Ingen läsning från Sheets: håll bara en cache i sessionen.
    if ROW_COUNT_KEY not in st.session_state:
        st.session_state[ROW_COUNT_KEY] = 0
_init_row_counter_no_sheet()

def next_scene_number():
    return st.session_state.get(ROW_COUNT_KEY, 0) + 1

def datum_och_veckodag_för_scen(scen_nummer: int):
    d = CFG["startdatum"] + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# ===== Scenario-väljare (påverkar endast inputfält – inga Sheets-anrop) =====
scenario = st.selectbox(
    "Välj scenario för att fylla in indata (sparar inte):",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet (7 dagar, förhandsgranskning)", "Vila på jobbet"],
    index=0,
)

def _suggest_personal_deltagit_for_inputs(force_zero=False):
    if force_zero:
        return 0
    return int(round(CFG["PROD_STAFF"] * (CFG["PERSONAL_PCT"] / 100.0)))

def _bonus_40pct_of_left():
    try:
        return int(round(CFG.get("BONUS_LEFT", 0) * 0.40))
    except Exception:
        return 0

def _rand_small():
    # liten neutral range för akter när vi inte läser historik (inga Sheets-anrop)
    return random.randint(0, 5)

def _rand_eskilstuna_from_settings():
    lo = int(CFG.get("ESK_MIN", 20))
    hi = int(CFG.get("ESK_MAX", 40))
    if hi < lo:
        lo, hi = hi, lo
    return random.randint(lo, hi)

def apply_scenario_fill(scn: str):
    # Sätter endast session_state för inputs. INTE spara.
    bonus_delt = _bonus_40pct_of_left()

    if scn == "Ny scen":
        # Nollställ / standard
        st.session_state.in_man = 0
        st.session_state.in_svarta = 0
        st.session_state.in_fitta = 0
        st.session_state.in_rumpa = 0
        st.session_state.in_dp = 0
        st.session_state.in_dpp = 0
        st.session_state.in_dap = 0
        st.session_state.in_tap = 0

        st.session_state.input_pappan = 0
        st.session_state.input_grannar = 0
        st.session_state.input_nils_vanner = 0
        st.session_state.input_nils_familj = 0
        st.session_state.input_bekanta = 0
        st.session_state.input_eskilstuna = 0

        st.session_state.input_bonus_deltagit = bonus_delt
        st.session_state.input_personal_deltagit = _suggest_personal_deltagit_for_inputs()

        st.session_state.in_alskar = 0
        st.session_state.in_sover = 0

        st.session_state.in_tid_s = 60
        st.session_state.in_tid_d = 60
        st.session_state.in_vila  = 7
        st.session_state.in_dt_tid  = 60
        st.session_state.in_dt_vila = 3

    elif scn == "Slumpa scen vit":
        # Slumpa sexakter lite lätt, källor från max i settings, eskilstuna från intervall
        st.session_state.in_man   = random.randint(0, 100)     # fritt då vi inte läser historik
        st.session_state.in_svarta= 0                          # vit scen → svarta 0
        st.session_state.in_fitta = _rand_small()
        st.session_state.in_rumpa = _rand_small()
        st.session_state.in_dp    = _rand_small()
        st.session_state.in_dpp   = _rand_small()
        st.session_state.in_dap   = _rand_small()
        st.session_state.in_tap   = _rand_small()

        st.session_state.input_pappan      = random.randint(0, int(CFG["MAX_PAPPAN"]))
        st.session_state.input_grannar     = random.randint(0, int(CFG["MAX_GRANNAR"]))
        st.session_state.input_nils_vanner = random.randint(0, int(CFG["MAX_NILS_VANNER"]))
        st.session_state.input_nils_familj = random.randint(0, int(CFG["MAX_NILS_FAMILJ"]))
        st.session_state.input_bekanta     = random.randint(0, int(CFG["MAX_BEKANTA"]))
        st.session_state.input_eskilstuna  = _rand_eskilstuna_from_settings()

        st.session_state.input_bonus_deltagit = bonus_delt
        st.session_state.input_personal_deltagit = _suggest_personal_deltagit_for_inputs()

        st.session_state.in_alskar = 8
        st.session_state.in_sover = 1

        # tider lämnas på standard / befintliga, rör inte om användaren ändrat

    elif scn == "Slumpa scen svart":
        # Svart scen: alla “känner”-källor 0, personal 0 (din spec), svarta slumpas >0
        st.session_state.in_man   = 0
        st.session_state.in_svarta= random.randint(1, 100)
        st.session_state.in_fitta = _rand_small()
        st.session_state.in_rumpa = _rand_small()
        st.session_state.in_dp    = _rand_small()
        st.session_state.in_dpp   = _rand_small()
        st.session_state.in_dap   = _rand_small()
        st.session_state.in_tap   = _rand_small()

        st.session_state.input_pappan      = 0
        st.session_state.input_grannar     = 0
        st.session_state.input_nils_vanner = 0
        st.session_state.input_nils_familj = 0
        st.session_state.input_bekanta     = 0
        st.session_state.input_eskilstuna  = 0

        st.session_state.input_bonus_deltagit = bonus_delt
        st.session_state.input_personal_deltagit = _suggest_personal_deltagit_for_inputs(force_zero=True)

        st.session_state.in_alskar = 8
        st.session_state.in_sover = 1

    elif scn == "Vila på jobbet":
        # Källor slumpas (40–60% av max skulle innebära settings+random men utan sheets – här tar vi 40–60% approx)
        def _rand_40_60(mx): 
            lo = int(round(mx * 0.40)); hi = int(round(mx * 0.60))
            if hi < lo: hi = lo
            return random.randint(lo, hi) if mx > 0 else 0

        st.session_state.in_man    = 0
        st.session_state.in_svarta = 0

        # Sexakter ska slumpas enligt din begäran
        st.session_state.in_fitta  = _rand_small()
        st.session_state.in_dp     = _rand_small()
        st.session_state.in_dap    = _rand_small()
        st.session_state.in_rumpa  = _rand_small()
        st.session_state.in_dpp    = _rand_small()
        st.session_state.in_tap    = _rand_small()

        st.session_state.input_pappan      = _rand_40_60(int(CFG["MAX_PAPPAN"]))
        st.session_state.input_grannar     = _rand_40_60(int(CFG["MAX_GRANNAR"]))
        st.session_state.input_nils_vanner = _rand_40_60(int(CFG["MAX_NILS_VANNER"]))
        st.session_state.input_nils_familj = _rand_40_60(int(CFG["MAX_NILS_FAMILJ"]))
        st.session_state.input_bekanta     = _rand_40_60(int(CFG["MAX_BEKANTA"]))
        st.session_state.input_eskilstuna  = _rand_eskilstuna_from_settings()

        st.session_state.input_bonus_deltagit = bonus_delt
        st.session_state.input_personal_deltagit = _suggest_personal_deltagit_for_inputs()  # alltid 80/10% osv

        # Älskar/sover som tidigare definierat för vila på jobbet
        st.session_state.in_alskar = 12
        st.session_state.in_sover  = 1

        # Tider för vila-scen kan lämnas till användaren att justera; standardvärden kvar

    elif scn == "Vila i hemmet (7 dagar, förhandsgranskning)":
        # Denna fyller inte in 7 rader här (vi spar inte). Här lägger vi ett “dag 1”-förslag i inputs
        # och visar info i förhandsvisningen i senare del.
        def _rand_40_60(mx): 
            lo = int(round(mx * 0.40)); hi = int(round(mx * 0.60))
            if hi < lo: hi = lo
            return random.randint(lo, hi) if mx > 0 else 0

        # Dag 1-5 har källor, 6-7 noll (men här lägger vi dag 1 i inputs)
        st.session_state.in_man    = 0
        st.session_state.in_svarta = 0
        st.session_state.in_fitta  = 0
        st.session_state.in_rumpa  = 0
        st.session_state.in_dp     = 0
        st.session_state.in_dpp    = 0
        st.session_state.in_dap    = 0
        st.session_state.in_tap    = 0

        st.session_state.input_pappan      = _rand_40_60(int(CFG["MAX_PAPPAN"]))
        st.session_state.input_grannar     = _rand_40_60(int(CFG["MAX_GRANNAR"]))
        st.session_state.input_nils_vanner = _rand_40_60(int(CFG["MAX_NILS_VANNER"]))
        st.session_state.input_nils_familj = _rand_40_60(int(CFG["MAX_NILS_FAMILJ"]))
        st.session_state.input_bekanta     = _rand_40_60(int(CFG["MAX_BEKANTA"]))
        st.session_state.input_eskilstuna  = _rand_eskilstuna_from_settings()

        # Bonus kvar fördelas dag 1–5 vid riktig skap – här lägger vi “per dag”-förslag i input
        bonus_left = int(CFG.get("BONUS_LEFT", 0))
        per_day = (bonus_left // 5) if bonus_left > 0 else 0
        st.session_state.input_bonus_deltagit = per_day

        # Personal 80%-regeln: för hemmet – dag1–5 = procenten, dag6–7 = 0 (här dag1)
        st.session_state.input_personal_deltagit = _suggest_personal_deltagit_for_inputs()

        st.session_state.in_alskar = 6
        st.session_state.in_sover  = 0  # i hemmet är sover=1 först på dag 6 (vi sätter 0 för dag1)

    else:
        pass

# Applicera scenario på knapp (ingen rerun krävs – värden landar i session_state)
if st.button("⚙️ Applicera scenario på indata (sparar inte)"):
    apply_scenario_fill(scenario)

# ===== Sceninfo (datum/veckodag/ålder) =====
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)
st.caption(f"Scen #{scen} — {rad_datum} ({veckodag}) — Malins ålder: {_age_on(CFG['födelsedatum'], rad_datum)} år")

# ===== Inmatning i EXAKT önskad ordning =====
# För att undvika dubblett-ID problem: skicka uttryckliga keys.
män             = st.number_input(_get_label(LABELS,"Män"),                min_value=0, step=1, value=st.session_state.get("in_man", 0), key="in_man")
svarta          = st.number_input(_get_label(LABELS,"Svarta"),             min_value=0, step=1, value=st.session_state.get("in_svarta", 0), key="in_svarta")
fitta           = st.number_input("Fitta",                                 min_value=0, step=1, value=st.session_state.get("in_fitta", 0), key="in_fitta")
rumpa           = st.number_input("Rumpa",                                 min_value=0, step=1, value=st.session_state.get("in_rumpa", 0), key="in_rumpa")
dp              = st.number_input("DP",                                    min_value=0, step=1, value=st.session_state.get("in_dp", 0), key="in_dp")
dpp             = st.number_input("DPP",                                   min_value=0, step=1, value=st.session_state.get("in_dpp", 0), key="in_dpp")
dap             = st.number_input("DAP",                                   min_value=0, step=1, value=st.session_state.get("in_dap", 0), key="in_dap")
tap             = st.number_input("TAP",                                   min_value=0, step=1, value=st.session_state.get("in_tap", 0), key="in_tap")

pappans_vänner  = st.number_input(_get_label(LABELS,"Pappans vänner"),     min_value=0, step=1, value=st.session_state.get("input_pappan", 0), key="input_pappan")
grannar         = st.number_input(_get_label(LABELS,"Grannar"),            min_value=0, step=1, value=st.session_state.get("input_grannar", 0), key="input_grannar")
nils_vänner     = st.number_input(_get_label(LABELS,"Nils vänner"),        min_value=0, step=1, value=st.session_state.get("input_nils_vanner", 0), key="input_nils_vanner")
nils_familj     = st.number_input(_get_label(LABELS,"Nils familj"),        min_value=0, step=1, value=st.session_state.get("input_nils_familj", 0), key="input_nils_familj")
bekanta         = st.number_input(_get_label(LABELS,"Bekanta"),            min_value=0, step=1, value=st.session_state.get("input_bekanta", 0), key="input_bekanta")
eskilstuna      = st.number_input(_get_label(LABELS,"Eskilstuna killar"),  min_value=0, step=1, value=st.session_state.get("input_eskilstuna", 0), key="input_eskilstuna")

bonus_deltagit  = st.number_input(_get_label(LABELS,"Bonus deltagit"),     min_value=0, step=1, value=st.session_state.get("input_bonus_deltagit", 0), key="input_bonus_deltagit")
personal_delt   = st.number_input(_get_label(LABELS,"Personal deltagit"),  min_value=0, step=1, value=st.session_state.get("input_personal_deltagit", _suggest_personal_deltagit_for_inputs()), key="input_personal_deltagit")

alskar          = st.number_input("Älskar",                                 min_value=0, step=1, value=st.session_state.get("in_alskar", 0), key="in_alskar")
sover_med       = st.number_input("Sover med (0 eller 1)",                  min_value=0, max_value=1, step=1, value=st.session_state.get("in_sover", 0), key="in_sover")

tid_s           = st.number_input("Tid S (sek)",                            min_value=0, step=1, value=st.session_state.get("in_tid_s", 60), key="in_tid_s")
tid_d           = st.number_input("Tid D (sek)",                            min_value=0, step=1, value=st.session_state.get("in_tid_d", 60), key="in_tid_d")
vila            = st.number_input("Vila (sek)",                             min_value=0, step=1, value=st.session_state.get("in_vila", 7), key="in_vila")
dt_tid          = st.number_input("DT tid (sek/kille)",                     min_value=0, step=1, value=st.session_state.get("in_dt_tid", 60), key="in_dt_tid")
dt_vila         = st.number_input("DT vila (sek/kille)",                    min_value=0, step=1, value=st.session_state.get("in_dt_vila", 3), key="in_dt_vila")

# Max-varningar (visuella, ingen skrivning)
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

# ============================ LIVE-FÖRHANDSVISNING (ingen Sheets-skrivning) ============================

# Bygg “grund”-dict från aktuella inputfält (detta sparas inte ännu)
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

grund_preview = {
    "Typ": scenario if scenario in ["Vila på jobbet", "Vila i hemmet (7 dagar, förhandsgranskning)"] else "",
    "Veckodag": veckodag,
    "Scen": scen,

    # Bas
    "Män": män,
    "Svarta": svarta,
    "Fitta": fitta,
    "Rumpa": rumpa,
    "DP": dp,
    "DPP": dpp,
    "DAP": dap,
    "TAP": tap,

    # Tider
    "Tid S": tid_s,
    "Tid D": tid_d,
    "Vila": vila,
    "DT tid (sek/kille)": dt_tid,
    "DT vila (sek/kille)": dt_vila,

    # Extra
    "Älskar": alskar,
    "Sover med": sover_med,

    # Känner-källor
    "Pappans vänner": pappans_vänner,
    "Grannar": grannar,
    "Nils vänner": nils_vänner,
    "Nils familj": nils_familj,
    "Bekanta": bekanta,
    "Eskilstuna killar": eskilstuna,

    # Bonus/Personal
    "Bonus killar": int(CFG.get("BONUS_TOTAL", 0)),
    "Bonus deltagit": bonus_deltagit,  # visas i input och ingår i beräkning
    "Personal deltagit": personal_delt,

    # Övrigt
    "Nils": 0,  # lämnas 0 om du inte använder just nu
    "Avgift": float(CFG.get("avgift_usd", 30.0)),
}

# Kör din externa beräkning (ingen läs/skriv till Sheets)
def _calc_preview_row(grund: dict):
    if not callable(calc_row_values):
        return {}
    try:
        return calc_row_values(
            grund=grund,
            rad_datum=rad_datum,
            foddatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
            prod_staff_total=int(CFG.get("PROD_STAFF", 800)),
            personal_pct=float(CFG.get("PERSONAL_PCT", 10.0)),
            esk_min=int(CFG.get("ESK_MIN", 20)),
            esk_max=int(CFG.get("ESK_MAX", 40)),
        )
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview_row(grund_preview)

# ============================ VISNING: FÖRHANDSMETRIK ============================
st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
c1, c2 = st.columns(2)
with c1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Malins ålder", f"{_age_on(CFG['födelsedatum'], rad_datum)} år")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
with c2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

# Hångel i liven (ingår ej i Summa tid enligt din spec)
st.markdown("#### 💋 Hångel (live)")
st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))

# ============================ VISNING: EKONOMI (live) ============================
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

# ============================ SPARRUTINER & AUTO-MAX ============================

ROW_COUNT_KEY = "ROW_COUNT"  # för att undvika NameError

def _store_pending(grund: dict, scen_nr: int, rad_d: date, veckodag_txt: str, over_max: dict):
    """Spara beslutet i sessionen tills användaren bekräftar."""
    st.session_state["PENDING_SAVE"] = {
        "grund": grund,
        "scen": scen_nr,
        "rad_datum": rad_d.isoformat(),
        "veckodag": veckodag_txt,
        "over_max": over_max,
    }

def _parse_date_for_save(d_any):
    if isinstance(d_any, date):
        return d_any
    return datetime.fromisoformat(str(d_any)).date()

def _append_row_to_sheet(ber: dict):
    """Append en färdigberäknad rad till Sheets (kallas bara när du explicit sparar)."""
    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    # Håll intern radräknare i synk
    st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1

def _save_row(grund: dict, rad_datum: date, veckodag_txt: str):
    """Beräkna + spara EN rad (ny scen / vila på jobbet / slumpa vit/svart)."""
    if not callable(calc_row_values):
        st.error("Beräkningsmodulen saknas (berakningar.py).")
        return

    base = dict(grund)
    base.setdefault("Avgift", float(CFG.get("avgift_usd", 30.0)))

    ber = calc_row_values(
        grund=base,
        rad_datum=rad_datum,
        foddatum=CFG["födelsedatum"],
        starttid=CFG["starttid"],
        prod_staff_total=int(CFG.get("PROD_STAFF", 800)),
        personal_pct=float(CFG.get("PERSONAL_PCT", 10.0)),
        esk_min=int(CFG.get("ESK_MIN", 20)),
        esk_max=int(CFG.get("ESK_MAX", 40)),
    )
    ber["Datum"] = rad_datum.isoformat()

    # OBS: alla uppdateringar mot "Inställningar" (t.ex. BONUS-räknare) görs INNE i calc_row_values
    # när en rad faktiskt sparas – inte under live.

    _append_row_to_sheet(ber)

    # Feedback
    ålder = _age_on(CFG["födelsedatum"], rad_datum)
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag_txt}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")

def _apply_auto_max_and_save(pending: dict):
    """Om något input > max: uppdatera max i Inställningar och spara sedan raden."""
    for _, info in pending.get("over_max", {}).items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))  # skrivs ENDAST här, vid explicit spar
        CFG[key] = new_val  # uppdatera lokalt

    grund = pending["grund"]
    rad_d = _parse_date_for_save(pending["rad_datum"])
    veckodag_txt = pending["veckodag"]
    _save_row(grund, rad_d, veckodag_txt)

# --- Save-knapp för aktuell preview (alla scen-typer utom batch "Vila i hemmet") ---
save_clicked = st.button("💾 Spara den här raden")
if save_clicked and scenario != "Vila i hemmet":
    # Kontrollera över-max mot sidopanelens maxar (bara för källorna)
    over_max = {}
    if pappans_vänner > int(CFG["MAX_PAPPAN"]):
        over_max[_L('Pappans vänner')] = {"current_max": int(CFG["MAX_PAPPAN"]), "new_value": pappans_vänner, "max_key": "MAX_PAPPAN"}
    if grannar > int(CFG["MAX_GRANNAR"]):
        over_max[_L('Grannar')] = {"current_max": int(CFG["MAX_GRANNAR"]), "new_value": grannar, "max_key": "MAX_GRANNAR"}
    if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
        over_max[_L('Nils vänner')] = {"current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": nils_vänner, "max_key": "MAX_NILS_VANNER"}
    if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
        over_max[_L('Nils familj')] = {"current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": nils_familj, "max_key": "MAX_NILS_FAMILJ"}
    if bekanta > int(CFG["MAX_BEKANTA"]):
        over_max[_L('Bekanta')] = {"current_max": int(CFG["MAX_BEKANTA"]), "new_value": bekanta, "max_key": "MAX_BEKANTA"}

    if over_max:
        _store_pending(grund_preview, scen, rad_datum, veckodag, over_max)
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# --- Auto-Max bekräftelsedialog ---
if "PENDING_SAVE" in st.session_state:
    pending = st.session_state["PENDING_SAVE"]
    st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara raden?")
    for f, info in pending["over_max"].items():
        st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")

    cA, cB = st.columns(2)
    with cA:
        if st.button("✅ Ja, uppdatera max och spara nu"):
            try:
                _apply_auto_max_and_save(pending)
            except Exception as e:
                st.error(f"Kunde inte spara: {e}")
            finally:
                st.session_state.pop("PENDING_SAVE", None)
                st.rerun()
    with cB:
        if st.button("✋ Nej, avbryt"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

# ============================ "Vila i hemmet" – 7-dagars förhandslista ============================

# Del 2 sätter upp st.session_state["HOME_PREVIEW"] när du väljer scenariot.
home_preview = st.session_state.get("HOME_PREVIEW", [])

if scenario == "Vila i hemmet":
    st.markdown("---")
    st.subheader("🏠 Förhandslista: 'Vila i hemmet' (7 dagar) – inget sparas förrän du klickar spara")

    if not home_preview:
        st.info("Listan är tom. Välj 'Vila i hemmet' i rullistan igen för att generera 7 dagar.")
    else:
        # Visa en tabelliknande lista med centrala fält
        for i, item in enumerate(home_preview, start=1):
            pr = _calc_preview_row(item)  # beräkna i minnet för visning
            d = pr.get("Datum", item.get("Datum", ""))
            vd = item.get("Veckodag", "")
            st.markdown(
                f"**Dag {i}** — {d} ({vd}) • "
                f"Totalt Män: {pr.get('Totalt Män', 0)} • "
                f"Summa tid: {pr.get('Summa tid','-')} • "
                f"Klockan: {pr.get('Klockan','-')}"
            )

        # Spara alla 7 när du är nöjd
        if st.button("💾 Spara alla 7 dagar"):
            try:
                for item in home_preview:
                    # Skriv varje dag som separat rad
                    d = _parse_date_for_save(item.get("Datum"))
                    vd = item.get("Veckodag", "")
                    _save_row(item, d, vd)
                st.success("✅ Alla 7 'Vila i hemmet'-rader sparade.")
                # Töm förhandslistan efter spar
                st.session_state["HOME_PREVIEW"] = []
                st.rerun()
            except Exception as e:
                st.error(f"Kunde inte spara alla dagar: {e}")

# ================================ SIDOPANEL ====================================
st.sidebar.header("⚙️ Inställningar (sparas endast när du klickar Spara)")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

with st.sidebar.expander("Allmänt & gränser", expanded=True):
    # Datum/Tid
    sb_startdatum = st.date_input(
        "Historiskt startdatum",
        value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)),
        key="sb_startdatum",
    )
    sb_starttid = st.time_input(
        "Starttid",
        value=CFG["starttid"],
        step=60,
        key="sb_starttid",
    )
    sb_fod = st.date_input(
        _L("Malins födelsedatum"),
        value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
        min_value=MIN_FOD, max_value=date.today(),
        key="sb_fod",
    )

    # Maxvärden
    sb_max_p  = st.number_input(f"Max {_L('Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]), key="sb_max_p")
    sb_max_g  = st.number_input(f"Max {_L('Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]), key="sb_max_g")
    sb_max_nv = st.number_input(f"Max {_L('Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]), key="sb_max_nv")
    sb_max_nf = st.number_input(f"Max {_L('Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]), key="sb_max_nf")
    sb_max_bk = st.number_input(f"Max {_L('Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]), key="sb_max_bk")

    # Produktionspersonal total och %-andel som deltar
    sb_prod_staff = st.number_input("Produktionspersonal (fast totalt)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]), key="sb_prod_staff")
    # Procentinput (ej slider) – följer alltid denna i alla scenarier
    current_pct = float(CFG.get("PERSONAL_PCT", 10.0))
    sb_personal_pct = st.number_input("Personal deltagit (% av total)", min_value=0.0, max_value=100.0, step=0.1, value=current_pct, key="sb_personal_pct")

    # Eskilstuna-intervall
    esk_min_cur = int(CFG.get("ESK_MIN", 20))
    esk_max_cur = int(CFG.get("ESK_MAX", 40))
    sb_esk_min = st.number_input("Eskilstuna min", min_value=0, step=1, value=esk_min_cur, key="sb_esk_min")
    sb_esk_max = st.number_input("Eskilstuna max", min_value=0, step=1, value=max(esk_max_cur, sb_esk_min), key="sb_esk_max")

    # Avgift per prenumerant/rad
    sb_fee = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="sb_fee")

with st.sidebar.expander("Etiketter (visningsnamn)", expanded=False):
    sb_lab_p   = st.text_input("Etikett: Pappans vänner", value=_L("Pappans vänner"), key="sb_lab_p")
    sb_lab_g   = st.text_input("Etikett: Grannar", value=_L("Grannar"), key="sb_lab_g")
    sb_lab_nv  = st.text_input("Etikett: Nils vänner", value=_L("Nils vänner"), key="sb_lab_nv")
    sb_lab_nf  = st.text_input("Etikett: Nils familj", value=_L("Nils familj"), key="sb_lab_nf")
    sb_lab_bk  = st.text_input("Etikett: Bekanta", value=_L("Bekanta"), key="sb_lab_bk")
    sb_lab_esk = st.text_input("Etikett: Eskilstuna killar", value=_L("Eskilstuna killar"), key="sb_lab_esk")
    sb_lab_man = st.text_input("Etikett: Män", value=_L("Män"), key="sb_lab_man")
    sb_lab_sva = st.text_input("Etikett: Svarta", value=_L("Svarta"), key="sb_lab_sva")
    sb_lab_kan = st.text_input("Etikett: Känner", value=_L("Känner"), key="sb_lab_kan")
    sb_lab_per = st.text_input("Etikett: Personal deltagit", value=_L("Personal deltagit"), key="sb_lab_per")
    sb_lab_bok = st.text_input("Etikett: Bonus killar", value=_L("Bonus killar"), key="sb_lab_bok")
    sb_lab_bod = st.text_input("Etikett: Bonus deltagit", value=_L("Bonus deltagit"), key="sb_lab_bod")
    sb_lab_mfd = st.text_input("Etikett: Malins födelsedatum", value=_L("Malins födelsedatum"), key="sb_lab_mfd")

# --- SPARA INSTÄLLNINGAR ---
if st.sidebar.button("💾 Spara inställningar", key="sb_save_settings"):
    try:
        # Primära värden
        _save_setting("startdatum", sb_startdatum.isoformat())
        _save_setting("starttid", sb_starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", sb_fod.isoformat(), label=sb_lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(sb_max_p)), label=sb_lab_p)
        _save_setting("MAX_GRANNAR", str(int(sb_max_g)), label=sb_lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(sb_max_nv)), label=sb_lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(sb_max_nf)), label=sb_lab_nf)
        _save_setting("MAX_BEKANTA", str(int(sb_max_bk)), label=sb_lab_bk)

        _save_setting("PROD_STAFF", str(int(sb_prod_staff)))
        _save_setting("PERSONAL_PCT", f"{float(sb_personal_pct)}")

        _save_setting("ESK_MIN", str(int(sb_esk_min)))
        _save_setting("ESK_MAX", str(int(sb_esk_max)))

        _save_setting("avgift_usd", f"{float(sb_fee)}")

        # Etikett-overrides (LABEL_* nycklar påverkar endast visning)
        _save_setting("LABEL_Pappans vänner", sb_lab_p, label="")
        _save_setting("LABEL_Grannar", sb_lab_g, label="")
        _save_setting("LABEL_Nils vänner", sb_lab_nv, label="")
        _save_setting("LABEL_Nils familj", sb_lab_nf, label="")
        _save_setting("LABEL_Bekanta", sb_lab_bk, label="")
        _save_setting("LABEL_Eskilstuna killar", sb_lab_esk, label="")
        _save_setting("LABEL_Män", sb_lab_man, label="")
        _save_setting("LABEL_Svarta", sb_lab_sva, label="")
        _save_setting("LABEL_Känner", sb_lab_kan, label="")
        _save_setting("LABEL_Personal deltagit", sb_lab_per, label="")
        _save_setting("LABEL_Bonus killar", sb_lab_bok, label="")
        _save_setting("LABEL_Bonus deltagit", sb_lab_bod, label="")
        _save_setting("LABEL_Malins födelsedatum", sb_lab_mfd, label="")

        st.success("Inställningar & etiketter sparade ✅")
        st.rerun()
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")

# =============================== STATISTIKVY ===============================
if view == "Statistik":
    st.header("📊 Statistik")

    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # Totalt män på radnivå: kolumnen "Totalt Män" om den finns, annars beräkna on-the-fly
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

    # Andel svarta: "Svarta" + "Bonus deltagit" räknas som svarta
    svarta_like_sum = 0
    tot_for_andel_svarta = 0

    # Prenumeranter (totalt + aktiva 30 dagar, exkludera vila-typer)
    total_pren = 0
    cutoff = date.today() - timedelta(days=30)
    aktiva_pren = 0

    for r in rows:
        typ = (r.get("Typ") or "").strip()
        tot_men_row = _row_tot_men(r)

        # Scen definieras som en rad där Totalt Män > 0
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
            pren = _safe_int(r.get("Prenumeranter", 0), 0)
            total_pren += pren
            d = _parse_iso_date(r.get("Datum", ""))
            if d and d >= cutoff:
                aktiva_pren += pren

    andel_svarta_pct = round((svarta_like_sum / tot_for_andel_svarta) * 100, 2) if tot_for_andel_svarta > 0 else 0.0

    # Översikt
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Antal scener", antal_scener)
    with c2: st.metric("Privat GB", privat_gb_cnt)
    with c3: st.metric("Totalt män (summa)", totalt_man_sum)
    with c4: st.metric("Andel svarta (%)", andel_svarta_pct)

    c5, c6 = st.columns(2)
    with c5: st.metric("Bonus killar (deltagit, sum)", bonus_deltagit_sum)
    with c6: st.metric("Personal (deltagit, sum)", personal_deltagit_sum)

    # Prenumeranter
    st.markdown("---")
    st.subheader("👥 Prenumeranter")
    pc1, pc2 = st.columns(2)
    with pc1: st.metric("Prenumeranter (totalt)", int(total_pren))
    with pc2: st.metric("Aktiva prenumeranter (30 dagar)", int(aktiva_pren))

    # DP/DPP/DAP/TAP – sum & snitt / scen
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

    st.stop()
