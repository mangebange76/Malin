# app.py — Del 1/6
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
    """Hämta ett blad; skapa endast om det inte finns. Inga extrablad skapas i onödan."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
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
                # Slumpintervall & personal%-inmatning
                ["ESK_MIN", "20", "Eskilstuna min"],
                ["ESK_MAX", "40", "Eskilstuna max"],
                ["PERSONAL_PCT", "10", "Personal deltagit (%)"],
            ]
            _retry_call(ws.update, f"A2:C{len(defaults)+1}", defaults)
        return ws

# OBS: Vi initierar bladobjekt, men anropar inte tunga läsningar kontinuerligt.
sheet = _get_ws(WORKSHEET_TITLE)
settings_ws = _get_ws(SETTINGS_SHEET)

# =========================== Header-schema (används först vid spar / data-visning) =========================
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

def ensure_header_once():
    """Körs vid behov (sparning / datatabell), inte vid varje input-förändring."""
    header = _retry_call(sheet.row_values, 1)
    if not header:
        _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
        return DEFAULT_COLUMNS
    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        from gspread.utils import rowcol_to_a1
        new_header = header + missing
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        return new_header
    return header

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    rows = _retry_call(settings_ws.get_all_records)  # [{'Key':..,'Value':..,'Label':..}, ...]
    d, labels = {}, {}
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

    # Bonus-räknare
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

    # Slumpintervall & personal-procent
    C["ESK_MIN"]      = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]      = int(float(_get("ESK_MAX", 40)))
    C["PERSONAL_PCT"] = float(_get("PERSONAL_PCT", 10.0))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# app.py — Del 2/6
# =============================== SIDOPANEL: Inställningar ===============================
st.sidebar.header("Inställningar")

def _L(txt: str) -> str:
    return LABELS.get(txt, txt)

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input(
        "Historiskt startdatum",
        value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)),
        key="cfg_startdatum",
    )
    starttid   = st.time_input("Starttid", value=CFG["starttid"], key="cfg_starttid")
    foddatum   = st.date_input(
        _L("Malins födelsedatum"),
        value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
        min_value=MIN_FOD, max_value=date.today(),
        key="cfg_foddatum",
    )

    # Max-värden för källor
    max_p  = st.number_input(f"Max {_L('Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]), key="cfg_max_pappan")
    max_g  = st.number_input(f"Max {_L('Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]), key="cfg_max_grannar")
    max_nv = st.number_input(f"Max {_L('Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]), key="cfg_max_nv")
    max_nf = st.number_input(f"Max {_L('Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]), key="cfg_max_nf")
    max_bk = st.number_input(f"Max {_L('Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]), key="cfg_max_bk")

    # Produktionspersonal (totalt) + procent för "Personal deltagit"
    prod_staff_total = st.number_input("Produktionspersonal (total)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]), key="cfg_prod_staff")
    personal_pct     = st.number_input("Personal deltagit (%)", min_value=0.0, step=0.5, value=float(CFG["PERSONAL_PCT"]), key="cfg_personal_pct")

    # Eskilstuna-intervall för slump
    esk_min = st.number_input("Eskilstuna min", min_value=0, step=1, value=int(CFG["ESK_MIN"]), key="cfg_esk_min")
    esk_max = st.number_input("Eskilstuna max", min_value=0, step=1, value=int(CFG["ESK_MAX"]), key="cfg_esk_max")

    # Avgift per prenumerant
    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="cfg_avgift")

    st.markdown("**Etiketter (påverkar endast visning)**")
    lab_p   = st.text_input("Etikett: Pappans vänner",      value=_L("Pappans vänner"), key="lab_p")
    lab_g   = st.text_input("Etikett: Grannar",             value=_L("Grannar"), key="lab_g")
    lab_nv  = st.text_input("Etikett: Nils vänner",         value=_L("Nils vänner"), key="lab_nv")
    lab_nf  = st.text_input("Etikett: Nils familj",         value=_L("Nils familj"), key="lab_nf")
    lab_bk  = st.text_input("Etikett: Bekanta",             value=_L("Bekanta"), key="lab_bk")
    lab_esk = st.text_input("Etikett: Eskilstuna killar",   value=_L("Eskilstuna killar"), key="lab_esk")
    lab_man = st.text_input("Etikett: Män",                 value=_L("Män"), key="lab_man")
    lab_sva = st.text_input("Etikett: Svarta",              value=_L("Svarta"), key="lab_sva")
    lab_kann= st.text_input("Etikett: Känner",              value=_L("Känner"), key="lab_kann")
    lab_pers= st.text_input("Etikett: Personal deltagit",   value=_L("Personal deltagit"), key="lab_pers")
    lab_bonus=st.text_input("Etikett: Bonus killar",        value=_L("Bonus killar"), key="lab_bonus")
    lab_bonusd=st.text_input("Etikett: Bonus deltagit",     value=_L("Bonus deltagit"), key="lab_bonusd")
    lab_mfd = st.text_input("Etikett: Malins födelsedatum", value=_L("Malins födelsedatum"), key="lab_mfd")

    if st.button("💾 Spara inställningar", key="btn_save_cfg"):
        # Spara värden
        _save_setting("startdatum", startdatum.isoformat())
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", foddatum.isoformat(), label=lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)

        _save_setting("PROD_STAFF", str(int(prod_staff_total)))
        _save_setting("PERSONAL_PCT", str(float(personal_pct)))

        _save_setting("ESK_MIN", str(int(esk_min)))
        _save_setting("ESK_MAX", str(int(esk_max)))

        _save_setting("avgift_usd", str(float(avgift_input)))

        # label-only overrides
        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_pers, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")

        st.success("Inställningar & etiketter sparade ✅")
        st.rerun()

# =============================== Meny & Scenväljare ===============================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0, key="main_view")

# Scenario-väljare + “Hämta värden”
SCENARIO_OPTIONS = ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet (7 dagar)", "Vila på jobbet"]
scenario = st.selectbox("Välj scenario", SCENARIO_OPTIONS, index=0, key="scenario_select")

# “Hämta värden” knappen triggar att vi fyller inputfält i session_state, men sparar inte.
if st.button("🔄 Hämta värden", key="btn_fetch_values"):
    st.session_state["PENDING_SCENARIO_FILL"] = scenario
    st.rerun()

# app.py — Del 3/6
# =============================== Formulär: Ny rad ===============================
st.header("➕ Lägg till rad")

with st.form("radformulär", clear_on_submit=False):
    # Grunddata
    veckodag = st.selectbox("Veckodag", ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"], key="in_veckodag")
    datum    = st.date_input("Datum", value=date.today(), key="in_datum")

    # Inputfält (alla källor + bonus + övrigt)
    in_pappan   = st.number_input(_L("Pappans vänner"), min_value=0, step=1, key="in_pappan")
    in_grannar  = st.number_input(_L("Grannar"),        min_value=0, step=1, key="in_grannar")
    in_nvanner  = st.number_input(_L("Nils vänner"),    min_value=0, step=1, key="in_nvanner")
    in_nfamilj  = st.number_input(_L("Nils familj"),    min_value=0, step=1, key="in_nfamilj")
    in_bekanta  = st.number_input(_L("Bekanta"),        min_value=0, step=1, key="in_bekanta")
    in_eskilst  = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, key="in_eskilstuna")

    in_man      = st.number_input(_L("Män"),     min_value=0, step=1, key="in_man")
    in_svart    = st.number_input(_L("Svarta"),  min_value=0, step=1, key="in_svart")
    in_kanner   = st.number_input(_L("Känner"),  min_value=0, step=1, key="in_kanner")

    in_pers     = st.number_input(_L("Personal deltagit"), min_value=0, step=1, key="in_pers")
    in_bonus_k  = st.number_input(_L("Bonus killar"),       min_value=0, step=1, key="in_bonus_k")
    in_bonus_d  = st.number_input(_L("Bonus deltagit"),     min_value=0, step=1, key="in_bonus_d")

    # Val för typ av rad
    typ = st.selectbox("Typ", ["Scen","Vila inspelningsplats","Vilovecka hemma"], key="in_typ")

    # Kvinnans lön (kan bli 0 vid vila)
    kvinnan_lon = st.number_input("Kvinnans lön (USD)", min_value=0.0, step=1.0, key="in_kvinnan_lon")

    submitted = st.form_submit_button("✅ Lägg till rad")

# =============================== Hantering av 'Hämta värden' ===============================
if "PENDING_SCENARIO_FILL" in st.session_state:
    scen = st.session_state.pop("PENDING_SCENARIO_FILL")

    # Slumpa och fyll fält beroende på scenario
    if scen == "Slumpa scen vit":
        st.session_state.in_pappan   = random.randint(0, CFG["MAX_PAPPAN"])
        st.session_state.in_grannar  = random.randint(0, CFG["MAX_GRANNAR"])
        st.session_state.in_nvanner  = random.randint(0, CFG["MAX_NILS_VANNER"])
        st.session_state.in_nfamilj  = random.randint(0, CFG["MAX_NILS_FAMILJ"])
        st.session_state.in_bekanta  = random.randint(0, CFG["MAX_BEKANTA"])
        st.session_state.in_eskilstuna = random.randint(CFG["ESK_MIN"], CFG["ESK_MAX"])
        st.session_state.in_svart    = 0  # vit = ingen svart
        st.session_state.in_pers     = int(round(CFG["PROD_STAFF"] * CFG["PERSONAL_PCT"] / 100.0))
        st.session_state.in_bonus_k  = random.randint(0, 3)
        st.session_state.in_bonus_d  = random.randint(0, 2)

    elif scen == "Slumpa scen svart":
        st.session_state.in_pappan   = random.randint(0, CFG["MAX_PAPPAN"])
        st.session_state.in_grannar  = random.randint(0, CFG["MAX_GRANNAR"])
        st.session_state.in_nvanner  = random.randint(0, CFG["MAX_NILS_VANNER"])
        st.session_state.in_nfamilj  = random.randint(0, CFG["MAX_NILS_FAMILJ"])
        st.session_state.in_bekanta  = random.randint(0, CFG["MAX_BEKANTA"])
        st.session_state.in_eskilstuna = random.randint(CFG["ESK_MIN"], CFG["ESK_MAX"])
        st.session_state.in_svart    = random.randint(1, 5)  # minst 1 svart
        st.session_state.in_pers     = 0  # svartscen = personal ej med
        st.session_state.in_bonus_k  = random.randint(0, 3)
        st.session_state.in_bonus_d  = random.randint(0, 2)

    elif scen == "Vila på jobbet":
        # slump mellan min och max i fitta, rumpa, DP, DPP, DAP, TAP
        min_val, max_val = 1, 5
        slump_val = random.randint(min_val, max_val)
        st.session_state.in_pappan   = slump_val
        st.session_state.in_grannar  = slump_val
        st.session_state.in_nvanner  = slump_val
        st.session_state.in_nfamilj  = slump_val
        st.session_state.in_bekanta  = slump_val
        st.session_state.in_eskilstuna = slump_val
        st.session_state.in_svart    = 0
        st.session_state.in_pers     = 0
        st.session_state.in_bonus_k  = slump_val
        st.session_state.in_bonus_d  = slump_val

    elif scen == "Vila i hemmet (7 dagar)":
        # samma slump som jobb
        min_val, max_val = 1, 5
        slump_val = random.randint(min_val, max_val)
        st.session_state.in_pappan   = slump_val
        st.session_state.in_grannar  = slump_val
        st.session_state.in_nvanner  = slump_val
        st.session_state.in_nfamilj  = slump_val
        st.session_state.in_bekanta  = slump_val
        st.session_state.in_eskilstuna = slump_val
        st.session_state.in_svart    = 0
        st.session_state.in_pers     = 0
        st.session_state.in_bonus_k  = slump_val
        st.session_state.in_bonus_d  = slump_val

    st.rerun()

# app.py — Del 4/6
# =============================== Live-beräkning ===============================
ROW_COUNT_KEY = "ROW_COUNT"

def _build_row_from_form():
    # Hämta allt från session_state (formuläret i Del 3/6)
    g = {
        "Typ": st.session_state.get("in_typ", "Scen"),
        "Veckodag": st.session_state.get("in_veckodag", ""),
        "Scen": st.session_state.get(ROW_COUNT_KEY, 0) + 1,  # endast visning
        "Datum": st.session_state.get("in_datum", date.today()).isoformat(),

        # Källor / antal
        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar":        st.session_state.get("in_grannar", 0),
        "Nils vänner":    st.session_state.get("in_nvanner", 0),
        "Nils familj":    st.session_state.get("in_nfamilj", 0),
        "Bekanta":        st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        # Män/Svarta/Känner
        "Män":     st.session_state.get("in_man", 0),
        "Svarta":  st.session_state.get("in_svart", 0),
        "Känner":  st.session_state.get("in_kanner", 0),

        # Bonus / Personal
        "Bonus killar":    st.session_state.get("in_bonus_k", 0),
        "Bonus deltagit":  st.session_state.get("in_bonus_d", 0),
        "Personal deltagit": st.session_state.get("in_pers", 0),

        # Övrigt
        "Älskar":      st.session_state.get("in_alskar", 0) if "in_alskar" in st.session_state else 0,
        "Sover med":   st.session_state.get("in_sover", 0) if "in_sover" in st.session_state else 0,

        # Tider (sek)
        "Tid S": st.session_state.get("in_tid_s", 0) if "in_tid_s" in st.session_state else 0,
        "Tid D": st.session_state.get("in_tid_d", 0) if "in_tid_d" in st.session_state else 0,
        "Vila":  st.session_state.get("in_vila", 0)  if "in_vila"  in st.session_state else 0,

        # DT (sek/kille)
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 0) if "in_dt_tid" in st.session_state else 0,
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 0) if "in_dt_vila" in st.session_state else 0,

        # Ekonomi
        "Avgift": float(CFG.get("avgift_usd", 30.0)),
    }
    return g

def _calc_preview_from_form():
    g = _build_row_from_form()
    datum_val = _parse_iso_date(g["Datum"]) or date.today()
    if not callable(calc_row_values):
        return {}, g, datum_val
    try:
        # OBS! Korrekt parameterordning/namn (tidigare fel: 'foddatum')
        out = calc_row_values(
            grund=g,
            rad_datum=datum_val,
            fodelsedatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
        )
        return out, g, datum_val
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}, g, datum_val

preview, grund_preview, rad_datum = _calc_preview_from_form()

# =============================== Livevisning ===============================
st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

# Ålder i live
alder = rad_datum.year - CFG["födelsedatum"].year - (
    (rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day)
)
st.caption(f"Ålder Malin denna dag: **{alder} år**")

cA, cB = st.columns(2)
with cA:
    st.metric("Datum / veckodag", f"{rad_datum} / {grund_preview.get('Veckodag','-')}")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with cB:
    st.metric("Totalt Män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

st.markdown("#### 💵 Ekonomi (live)")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with e2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with e3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with e4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# =============================== Spara-rad ===============================
def _save_row_to_sheet(ber, rad_datum_iso):
    # Ordna rätt kolumnordning
    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1

def _save_clicked():
    if not callable(calc_row_values):
        st.error("Hittar inte berakningar.py / berakna_radvarden().")
        return
    try:
        base = dict(grund_preview)
        # beräkna på nytt vid spar
        ber = calc_row_values(
            grund=base,
            rad_datum=rad_datum,
            fodelsedatum=CFG["födelsedatum"],
            starttid=CFG["starttid"],
        )
        ber["Datum"] = rad_datum.isoformat()
        _save_row_to_sheet(ber, ber["Datum"])

        typ_label = ber.get("Typ") or "Händelse"
        st.success(f"✅ Rad sparad ({typ_label}). Datum {ber['Datum']} / {grund_preview.get('Veckodag','-')}.")
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")

# Spara-knapp
col_save, _ = st.columns([1,3])
with col_save:
    if st.button("💾 Spara raden"):
        _save_clicked()

# app.py — Del 5/6
# =============================== Sidopanel =====================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

def _L(txt: str) -> str:
    return LABELS.get(txt, txt)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    # Basdatum/tid
    startdatum = st.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    fodate     = st.date_input(_L("Malins födelsedatum"),
                               value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
                               min_value=MIN_FOD, max_value=date.today())

    # Maxvärden för källor
    c1, c2 = st.columns(2)
    with c1:
        max_p  = st.number_input(f"Max {_L('Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
        max_nv = st.number_input(f"Max {_L('Nils vänner')}",   min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
        max_bk = st.number_input(f"Max {_L('Bekanta')}",       min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))
    with c2:
        max_g  = st.number_input(f"Max {_L('Grannar')}",       min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
        max_nf = st.number_input(f"Max {_L('Nils familj')}",   min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
        avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    # Produktionspersonal & andel som deltar
    st.markdown("### 👷 Produktionspersonal")
    c3, c4 = st.columns(2)
    with c3:
        prod_staff = st.number_input("Total personalstyrka", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    with c4:
        personal_pct = st.number_input("Andel som deltar (%)", min_value=0.0, max_value=100.0, step=0.1,
                                       value=float(CFG.get("PERSONAL_PCT", 10.0)))
    st.caption("Denna procentsats används för att beräkna **Personal deltagit** i alla scen-typer/snabblägen.")

    # Eskilstuna killar – intervall för slump
    st.markdown("### 🧮 Eskilstuna-intervall (slump)")
    esk_min = st.number_input("Min", min_value=0, step=1, value=int(CFG.get("ESK_MIN", 20)))
    esk_max = st.number_input("Max", min_value=0, step=1, value=int(CFG.get("ESK_MAX", 40)))
    if esk_max < esk_min:
        st.warning("Eskilstuna max är lägre än min – rätta innan du sparar.")

    # Etiketter (visning, påverkar inga beräkningar)
    st.markdown("### 🏷️ Etiketter")
    lab_p   = st.text_input("Etikett: Pappans vänner", value=_L("Pappans vänner"))
    lab_g   = st.text_input("Etikett: Grannar", value=_L("Grannar"))
    lab_nv  = st.text_input("Etikett: Nils vänner", value=_L("Nils vänner"))
    lab_nf  = st.text_input("Etikett: Nils familj", value=_L("Nils familj"))
    lab_bk  = st.text_input("Etikett: Bekanta", value=_L("Bekanta"))
    lab_esk = st.text_input("Etikett: Eskilstuna killar", value=_L("Eskilstuna killar"))
    lab_man = st.text_input("Etikett: Män", value=_L("Män"))
    lab_sva = st.text_input("Etikett: Svarta", value=_L("Svarta"))
    lab_kann= st.text_input("Etikett: Känner", value=_L("Känner"))
    lab_bonus = st.text_input("Etikett: Bonus killar", value=_L("Bonus killar"))
    lab_bonusd = st.text_input("Etikett: Bonus deltagit", value=_L("Bonus deltagit"))
    lab_pers = st.text_input("Etikett: Personal deltagit", value=_L("Personal deltagit"))
    lab_mfd  = st.text_input("Etikett: Malins födelsedatum", value=_L("Malins födelsedatum"))

    # Spara
    if st.button("💾 Spara inställningar"):
        try:
            _save_setting("startdatum", startdatum.isoformat(), None)
            _save_setting("starttid", starttid.strftime("%H:%M"), None)
            _save_setting("födelsedatum", fodate.isoformat(), lab_mfd)

            _save_setting("MAX_PAPPAN", str(int(max_p)), lab_p)
            _save_setting("MAX_GRANNAR", str(int(max_g)), lab_g)
            _save_setting("MAX_NILS_VANNER", str(int(max_nv)), lab_nv)
            _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), lab_nf)
            _save_setting("MAX_BEKANTA", str(int(max_bk)), lab_bk)

            _save_setting("avgift_usd", str(float(avgift_input)))
            _save_setting("PROD_STAFF", str(int(prod_staff)))
            _save_setting("PERSONAL_PCT", str(float(personal_pct)))

            _save_setting("ESK_MIN", str(int(esk_min)))
            _save_setting("ESK_MAX", str(int(esk_max)))

            # Label-only overrides
            _save_setting("LABEL_Eskilstuna killar", lab_esk, "")
            _save_setting("LABEL_Män", lab_man, "")
            _save_setting("LABEL_Svarta", lab_sva, "")
            _save_setting("LABEL_Känner", lab_kann, "")
            _save_setting("LABEL_Personal deltagit", lab_pers, "")
            _save_setting("LABEL_Bonus killar", lab_bonus, "")
            _save_setting("LABEL_Bonus deltagit", lab_bonusd, "")

            st.success("Inställningar och etiketter sparade ✅")
            st.rerun()
        except Exception as e:
            st.error(f"Kunde inte spara inställningar: {e}")

# app.py — Del 6/6
# ============================ Scenval + "Hämta värden" =========================
SCENARIO_OPTIONS = ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet"]
scenario = st.selectbox("Välj scenario", SCENARIO_OPTIONS, index=0, key="scenario_sel")

def _personal_suggestion():
    pct = float(CFG.get("PERSONAL_PCT", 10.0))
    total = int(CFG.get("PROD_STAFF", 800))
    return max(0, int(round(total * pct / 100.0)))

def _esk_rand():
    lo = int(CFG.get("ESK_MIN", 20))
    hi = int(CFG.get("ESK_MAX", 40))
    if hi < lo:
        lo, hi = hi, lo
    return random.randint(lo, hi)

def _get_min_max(colname: str):
    # Hämtas endast när vi klickar "Hämta värden"
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

def _rand_between_minmax(col):
    mn, mx = _get_min_max(col)
    if mx < mn:
        mn, mx = mx, mn
    return random.randint(mn, mx) if mx >= mn else 0

def _rand_40_60_of_max(mx: int) -> int:
    try: mx = int(mx)
    except Exception: mx = 0
    if mx <= 0: return 0
    lo = max(0, int(round(mx * 0.40)))
    hi = max(lo, int(round(mx * 0.60)))
    return random.randint(lo, hi)

def _bonus_deltagit_proposal():
    # 40% av kvarvarande bonus (utan att dra av något här)
    left = int(CFG.get("BONUS_LEFT", 0))
    return max(0, int(round(left * 0.40)))

def _set_ss(key, val):
    st.session_state[key] = val

def apply_scenario_fill():
    # Nollställ först allt till säkra standarder
    defaults = {
        "in_män": 0, "in_svarta": 0,
        "in_fitta": 0, "in_rumpa": 0, "in_dp": 0, "in_dpp": 0, "in_dap": 0, "in_tap": 0,
        "input_pappan": 0, "input_grannar": 0, "input_nils_vanner": 0, "input_nils_familj": 0,
        "input_bekanta": 0, "input_eskilstuna": 0, "input_bonus_deltagit": 0,
        "input_personal_deltagit": _personal_suggestion(),
        "in_alskar": 0, "in_sover": 0,
        "in_tid_s": 60, "in_tid_d": 60, "in_vila": 7, "in_dt_tid": 60, "in_dt_vila": 3,
    }
    for k, v in defaults.items():
        _set_ss(k, v)

    s = st.session_state.get("scenario_sel", "Ny scen")

    if s == "Ny scen":
        # Bara standarder + föreslagen personal + bonus deltagit
        _set_ss("input_personal_deltagit", _personal_suggestion())
        _set_ss("input_bonus_deltagit", _bonus_deltagit_proposal())

    elif s == "Slumpa scen vit":
        # Slumpa via min–max från befintliga rader
        _set_ss("in_män", _rand_between_minmax("Män"))
        _set_ss("in_fitta", _rand_between_minmax("Fitta"))
        _set_ss("in_rumpa", _rand_between_minmax("Rumpa"))
        _set_ss("in_dp", _rand_between_minmax("DP"))
        _set_ss("in_dpp", _rand_between_minmax("DPP"))
        _set_ss("in_dap", _rand_between_minmax("DAP"))
        _set_ss("in_tap", _rand_between_minmax("TAP"))

        _set_ss("input_pappan", _rand_between_minmax("Pappans vänner"))
        _set_ss("input_grannar", _rand_between_minmax("Grannar"))
        _set_ss("input_nils_vanner", _rand_between_minmax("Nils vänner"))
        _set_ss("input_nils_familj", _rand_between_minmax("Nils familj"))
        _set_ss("input_bekanta", _rand_between_minmax("Bekanta"))
        _set_ss("input_eskilstuna", _rand_between_minmax("Eskilstuna killar"))

        _set_ss("in_alskar", 8)
        _set_ss("in_sover", 1)
        _set_ss("input_personal_deltagit", _personal_suggestion())
        _set_ss("input_bonus_deltagit", _bonus_deltagit_proposal())

    elif s == "Slumpa scen svart":
        # Slumpa sex-delarna + Svarta via min–max. Övriga källor = 0. Personal = 0.
        _set_ss("in_fitta", _rand_between_minmax("Fitta"))
        _set_ss("in_rumpa", _rand_between_minmax("Rumpa"))
        _set_ss("in_dp", _rand_between_minmax("DP"))
        _set_ss("in_dpp", _rand_between_minmax("DPP"))
        _set_ss("in_dap", _rand_between_minmax("DAP"))
        _set_ss("in_tap", _rand_between_minmax("TAP"))
        _set_ss("in_svarta", _rand_between_minmax("Svarta"))

        _set_ss("in_män", 0)
        _set_ss("input_pappan", 0)
        _set_ss("input_grannar", 0)
        _set_ss("input_nils_vanner", 0)
        _set_ss("input_nils_familj", 0)
        _set_ss("input_bekanta", 0)
        _set_ss("input_eskilstuna", 0)

        _set_ss("in_alskar", 8)
        _set_ss("in_sover", 1)
        _set_ss("input_personal_deltagit", 0)  # enligt krav
        _set_ss("input_bonus_deltagit", _bonus_deltagit_proposal())

    elif s == "Vila på jobbet":
        # Källor ~40–60% av max; Eskilstuna från intervall; Personal från procentsats
        _set_ss("input_pappan", _rand_40_60_of_max(int(CFG["MAX_PAPPAN"])))
        _set_ss("input_grannar", _rand_40_60_of_max(int(CFG["MAX_GRANNAR"])))
        _set_ss("input_nils_vanner", _rand_40_60_of_max(int(CFG["MAX_NILS_VANNER"])))
        _set_ss("input_nils_familj", _rand_40_60_of_max(int(CFG["MAX_NILS_FAMILJ"])))
        _set_ss("input_bekanta", _rand_40_60_of_max(int(CFG["MAX_BEKANTA"])))
        _set_ss("input_eskilstuna", _esk_rand())

        # Sex-delar via min–max (enligt senaste önskemål)
        for col, key in [
            ("Fitta", "in_fitta"), ("Rumpa", "in_rumpa"),
            ("DP", "in_dp"), ("DPP", "in_dpp"),
            ("DAP", "in_dap"), ("TAP", "in_tap")
        ]:
            _set_ss(key, _rand_between_minmax(col))

        _set_ss("in_alskar", 12)
        _set_ss("in_sover", 1)
        _set_ss("input_personal_deltagit", _personal_suggestion())
        _set_ss("input_bonus_deltagit", _bonus_deltagit_proposal())

    elif s == "Vila i hemmet":
        # Vi fyller dag 1 som förhandsvisning (0 i sex-delar), källor 40–60% + Eskilstuna, personal = 80% första 5 dagar -> men här följer procent-inställningen:
        # På dag 6–7 ska personal = 0 (det sköts i multi-dag-wizard vid spar; här visar vi dag 1-inputen).
        _set_ss("input_pappan", _rand_40_60_of_max(int(CFG["MAX_PAPPAN"])))
        _set_ss("input_grannar", _rand_40_60_of_max(int(CFG["MAX_GRANNAR"])))
        _set_ss("input_nils_vanner", _rand_40_60_of_max(int(CFG["MAX_NILS_VANNER"])))
        _set_ss("input_nils_familj", _rand_40_60_of_max(int(CFG["MAX_NILS_FAMILJ"])))
        _set_ss("input_bekanta", _rand_40_60_of_max(int(CFG["MAX_BEKANTA"])))
        _set_ss("input_eskilstuna", _esk_rand())
        # sex-delar 0 enligt tidigare
        _set_ss("in_alskar", 6)
        _set_ss("in_sover", 0)
        _set_ss("input_personal_deltagit", _personal_suggestion())
        _set_ss("input_bonus_deltagit", _bonus_deltagit_proposal())

# Knapp som *endast* fyller inputfält (ingen skrivning)
if st.button("📥 Hämta värden"):
    apply_scenario_fill()
    st.rerun()

# ============================ Inmatning i rätt ordning =========================
# OBS: vi använder st.session_state.get(...) som value för att undvika "default+set" varning.
män    = st.number_input(_get_label(LABELS,"Män"),    min_value=0, step=1, value=st.session_state.get("in_män", 0), key="in_män")
svarta = st.number_input(_get_label(LABELS,"Svarta"), min_value=0, step=1, value=st.session_state.get("in_svarta", 0), key="in_svarta")
fitta  = st.number_input("Fitta",  min_value=0, step=1, value=st.session_state.get("in_fitta", 0), key="in_fitta")
rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=st.session_state.get("in_rumpa", 0), key="in_rumpa")
dp     = st.number_input("DP",     min_value=0, step=1, value=st.session_state.get("in_dp", 0), key="in_dp")
dpp    = st.number_input("DPP",    min_value=0, step=1, value=st.session_state.get("in_dpp", 0), key="in_dpp")
dap    = st.number_input("DAP",    min_value=0, step=1, value=st.session_state.get("in_dap", 0), key="in_dap")
tap    = st.number_input("TAP",    min_value=0, step=1, value=st.session_state.get("in_tap", 0), key="in_tap")

pappans_vänner = st.number_input(_get_label(LABELS,"Pappans vänner"), min_value=0, step=1, value=st.session_state.get("input_pappan", 0), key="input_pappan")
grannar        = st.number_input(_get_label(LABELS,"Grannar"),        min_value=0, step=1, value=st.session_state.get("input_grannar", 0), key="input_grannar")
nils_vänner    = st.number_input(_get_label(LABELS,"Nils vänner"),    min_value=0, step=1, value=st.session_state.get("input_nils_vanner", 0), key="input_nils_vanner")
nils_familj    = st.number_input(_get_label(LABELS,"Nils familj"),    min_value=0, step=1, value=st.session_state.get("input_nils_familj", 0), key="input_nils_familj")
bekanta        = st.number_input(_get_label(LABELS,"Bekanta"),        min_value=0, step=1, value=st.session_state.get("input_bekanta", 0), key="input_bekanta")
eskilstuna_killar = st.number_input(_get_label(LABELS,"Eskilstuna killar"), min_value=0, step=1, value=st.session_state.get("input_eskilstuna", 0), key="input_eskilstuna")
bonus_deltagit = st.number_input(_get_label(LABELS,"Bonus deltagit"), min_value=0, step=1, value=st.session_state.get("input_bonus_deltagit", 0), key="input_bonus_deltagit")
personal_deltagit = st.number_input(_get_label(LABELS,"Personal deltagit"), min_value=0, step=1, value=st.session_state.get("input_personal_deltagit", _personal_suggestion()), key="input_personal_deltagit")

alskar    = st.number_input("Älskar", min_value=0, step=1, value=st.session_state.get("in_alskar", 0), key="in_alskar")
sover_med = st.number_input("Sover med", min_value=0, max_value=1, step=1, value=st.session_state.get("in_sover", 0), key="in_sover")

tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=st.session_state.get("in_tid_s", 60), key="in_tid_s")
tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=st.session_state.get("in_tid_d", 60), key="in_tid_d")
vila   = st.number_input("Vila (sek)",  min_value=0, step=1, value=st.session_state.get("in_vila", 7), key="in_vila")
dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=st.session_state.get("in_dt_tid", 60), key="in_dt_tid")
dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=st.session_state.get("in_dt_vila", 3), key="in_dt_vila")

# ============================ Live-förhandsberäkning ===========================
scen = st.session_state.get("ROW_COUNT", 0) + 1
rad_datum = CFG["startdatum"] + timedelta(days=scen - 1)
veckodag = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][rad_datum.weekday()]

grund_preview = {
    "Typ": st.session_state.get("scenario_sel","Ny scen"),
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
    "Älskar": alskar, "Sover med": sover_med,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
    "Bonus killar": 0, "Bonus deltagit": bonus_deltagit, "Personal deltagit": personal_deltagit,
    "Nils": 0,
    "Avgift": float(CFG["avgift_usd"]),
}
preview = {}
if callable(calc_row_values):
    try:
        preview = calc_row_values(grund_preview, rad_datum, CFG["födelsedatum"], CFG["starttid"])
    except TypeError as te:
        # Fångar ev. fel med parameternamn; försök med namnet 'fodelsedatum' fallback
        try:
            preview = calc_row_values(grund_preview, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        except Exception as _:
            st.warning(f"Förhandsberäkning misslyckades: {te}")
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")

# Visa ålder live
alder = rad_datum.year - CFG["födelsedatum"].year - (
    (rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day)
)

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin)", f"{alder} år")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
with c2:
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
with c3:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

st.markdown("#### 💵 Ekonomi (live)")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with e2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with e3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with e4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ================================ Spara raden ==================================
def _save_row(grund, rad_datum, veckodag):
    try:
        base = dict(grund)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return
    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state["ROW_COUNT"] = st.session_state.get("ROW_COUNT", 0) + 1
    st.success("✅ Rad sparad.")
    st.rerun()

if st.button("💾 Spara raden"):
    _save_row(grund_preview, rad_datum, veckodag)
