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
    """Hämta ett blad; skapa endast om det inte finns. Endast 'Data' & 'Inställningar' används."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=200 if title==SETTINGS_SHEET else 2000, cols=120)
        if title == SETTINGS_SHEET:
            _retry_call(ws.update, "A1:C1", [["Key","Value","Label"]])
            defaults = [
                ["startdatum", date.today().isoformat(), ""],
                ["starttid", "07:00", ""],
                ["födelsedatum", date(1990,1,1).isoformat(), "Malins födelsedatum"],

                # Max för källor
                ["MAX_PAPPAN", "10", "Pappans vänner"],
                ["MAX_GRANNAR", "10", "Grannar"],
                ["MAX_NILS_VANNER", "10", "Nils vänner"],
                ["MAX_NILS_FAMILJ", "10", "Nils familj"],
                ["MAX_BEKANTA", "10", "Bekanta"],

                # Ekonomi & personal
                ["avgift_usd", "30.0", "Avgift (USD, per rad)"],
                ["PROD_STAFF", "800", "Produktionspersonal (fast)"],
                ["PERSONAL_PCT", "10.0", "Personal deltagit % (av PROD_STAFF)"],

                # Eskilstuna slumpintervall
                ["ESK_MIN", "20", "Eskilstuna min"],
                ["ESK_MAX", "40", "Eskilstuna max"],

                # Bonus, enkel saldoräknare
                ["BONUS_AVAILABLE", "0", "Bonus killar - tillgängliga"],

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
        return
    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        new_header = header + missing
        from gspread.utils import rowcol_to_a1
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
KOLUMNER = st.session_state["COLUMNS"]

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    rows = _retry_call(settings_ws.get_all_records)
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

def _L(labels_map: dict, default_text: str) -> str:
    return labels_map.get(default_text, default_text)

CFG_RAW, LABELS = _settings_as_dict()

def _init_cfg_defaults_from_settings():
    st.session_state.setdefault("CFG", {})
    C = st.session_state["CFG"]
    def _get(k, fb): return CFG_RAW.get(k, fb)

    # Datum/tid
    try: C["startdatum"] = datetime.fromisoformat(_get("startdatum", date.today().isoformat())).date()
    except Exception: C["startdatum"] = date.today()
    try:
        hh, mm = str(_get("starttid", "07:00")).split(":")
        C["starttid"] = time(int(hh), int(mm))
    except Exception: C["starttid"] = time(7,0)
    try: C["födelsedatum"] = datetime.fromisoformat(_get("födelsedatum", "1990-01-01")).date()
    except Exception: C["födelsedatum"] = date(1990,1,1)

    # Max och ekonomi
    C["MAX_PAPPAN"]      = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]     = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"] = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"] = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]     = int(float(_get("MAX_BEKANTA", 10)))

    C["avgift_usd"]      = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"]      = int(float(_get("PROD_STAFF", 800)))
    C["PERSONAL_PCT"]    = float(_get("PERSONAL_PCT", 10.0))

    C["ESK_MIN"]         = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]         = int(float(_get("ESK_MAX", 40)))

    C["BONUS_AVAILABLE"] = int(float(_get("BONUS_AVAILABLE", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ============================== Sidopanel ======================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    fod = st.date_input(_L(LABELS,"Malins födelsedatum"), value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
                        min_value=MIN_FOD, max_value=date.today())

    max_p  = st.number_input(f"Max {_L(LABELS,'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_L(LABELS,'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_L(LABELS,'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_L(LABELS,'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_L(LABELS,'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

    avgift = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))
    prod_staff = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    personal_pct = st.number_input("Personal deltagit %", min_value=0.0, step=0.5, value=float(CFG["PERSONAL_PCT"]))

    st.markdown("**Eskilstuna-intervall (för slump)**")
    esk_min = st.number_input("Eskilstuna min", min_value=0, step=1, value=int(CFG["ESK_MIN"]), key="esk_min")
    esk_max = st.number_input("Eskilstuna max", min_value=0, step=1, value=int(CFG["ESK_MAX"]), key="esk_max")
    if esk_max < esk_min:
        st.warning("Eskilstuna max kan inte vara mindre än min.")

    st.markdown("**Bonus**")
    bonus_avail = st.number_input("Bonus tillgängliga (saldo)", min_value=0, step=1, value=int(CFG["BONUS_AVAILABLE"]))

    st.markdown("**Etiketter (visning, påverkar inte beräkningar)**")
    lab_p  = st.text_input("Etikett: Pappans vänner", value=_L(LABELS,"Pappans vänner"))
    lab_g  = st.text_input("Etikett: Grannar", value=_L(LABELS,"Grannar"))
    lab_nv = st.text_input("Etikett: Nils vänner", value=_L(LABELS,"Nils vänner"))
    lab_nf = st.text_input("Etikett: Nils familj", value=_L(LABELS,"Nils familj"))
    lab_bk = st.text_input("Etikett: Bekanta", value=_L(LABELS,"Bekanta"))
    lab_esk= st.text_input("Etikett: Eskilstuna killar", value=_L(LABELS,"Eskilstuna killar"))
    lab_man= st.text_input("Etikett: Män", value=_L(LABELS,"Män"))
    lab_sva= st.text_input("Etikett: Svarta", value=_L(LABELS,"Svarta"))
    lab_kann=st.text_input("Etikett: Känner", value=_L(LABELS,"Känner"))
    lab_person=st.text_input("Etikett: Personal deltagit", value=_L(LABELS,"Personal deltagit"))
    lab_bonus =st.text_input("Etikett: Bonus killar", value=_L(LABELS,"Bonus killar"))
    lab_bonusd=st.text_input("Etikett: Bonus deltagit", value=_L(LABELS,"Bonus deltagit"))
    lab_mfd   = st.text_input("Etikett: Malins födelsedatum", value=_L(LABELS,"Malins födelsedatum"))

    if st.button("💾 Spara inställningar"):
        _save_setting("startdatum", startdatum.isoformat())
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", fod.isoformat(), label=lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)

        _save_setting("avgift_usd", str(float(avgift)))
        _save_setting("PROD_STAFF", str(int(prod_staff)))
        _save_setting("PERSONAL_PCT", str(float(personal_pct)))

        _save_setting("ESK_MIN", str(int(esk_min)))
        _save_setting("ESK_MAX", str(int(esk_max)))

        _save_setting("BONUS_AVAILABLE", str(int(bonus_avail)))

        # label-only overrides
        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_person, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")

        st.success("Inställningar sparade ✅")
        st.rerun()

# ===== Radräkning (läsning, ej skrivning) =====
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

# =============================== PRODUKTION ===============================
st.header("🧪 Produktion – ny rad")

# Scenario-väljare + Hämta värden
scenario = st.selectbox(
    "Välj scenario",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet", "Vila på jobbet"],
    index=0,
    key="scenario_select"
)

def _esk_rand():
    mn, mx = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
    if mx < mn: mx = mn
    return random.randint(mn, mx) if mx >= mn else 0

def _get_min_max(colname: str):
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

def _fill_default_values_from_scenario():
    """Fyll endast session_state (inputs). Inget skrivs till Sheets."""
    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    # Förslag Bonus deltagit: 40% av tillgängliga (men du kan ändra)
    suggested_bonus = min(int(round(int(CFG["BONUS_AVAILABLE"]) * 0.40)), int(CFG["BONUS_AVAILABLE"]))

    # Personal deltagit följer procentsatsen
    suggested_personal = max(0, int(round(int(CFG["PROD_STAFF"]) * float(CFG["PERSONAL_PCT"]) / 100.0)))

    # Starta med nollor
    defaults = dict(
        man=0, svarta=0, fitta=0, rumpa=0, dp=0, dpp=0, dap=0, tap=0,
        pv=0, gr=0, nv=0, nf=0, bk=0, esk=0,
        bonus_d=0, personal_d=suggested_personal,
        alskar=0, sover=0,
        tid_s=60, tid_d=60, vila=7, dt_tid=60, dt_vila=3
    )

    if scenario == "Ny scen":
        defaults["esk"] = 0
        defaults["bonus_d"] = 0
        defaults["personal_d"] = suggested_personal
        # övrigt 0

    elif scenario == "Slumpa scen vit":
        # Slumpa inom historiska min/max för varje kolumn
        for key, col in [
            ("man","Män"),("fitta","Fitta"),("rumpa","Rumpa"),
            ("dp","DP"),("dpp","DPP"),("dap","DAP"),("tap","TAP"),
            ("pv","Pappans vänner"),("gr","Grannar"),
            ("nv","Nils vänner"),("nf","Nils familj"),
            ("bk","Bekanta"),("esk","Eskilstuna killar")
        ]:
            mn, mx = _get_min_max(col)
            defaults[key] = random.randint(mn, mx) if mx >= mn else 0
        defaults["alskar"] = 8
        defaults["sover"] = 1
        defaults["bonus_d"] = suggested_bonus
        defaults["personal_d"] = suggested_personal
        defaults["svarta"] = 0

    elif scenario == "Slumpa scen svart":
        # Slumpa svarta och sexmoment; övriga källor 0; personal deltagit = 0 enligt din senaste instruktion
        for key, col in [("fitta","Fitta"),("rumpa","Rumpa"),("dp","DP"),("dpp","DPP"),("dap","DAP"),("tap","TAP")]:
            mn, mx = _get_min_max(col)
            defaults[key] = random.randint(mn, mx) if mx >= mn else 0
        mn, mx = _get_min_max("Svarta")
        defaults["svarta"] = random.randint(mn, mx) if mx >= mn else 0
        defaults["alskar"] = 8
        defaults["sover"] = 1
        defaults["pv"]=defaults["gr"]=defaults["nv"]=defaults["nf"]=defaults["bk"]=defaults["man"]=defaults["esk"]=0
        defaults["personal_d"] = 0
        defaults["bonus_d"] = suggested_bonus

    elif scenario == "Vila i hemmet":
        # För enkelhet: fyll en "dag 1"-rad som förslag. (Vill du kan vi lägga batch-stege igen.)
        # Dag 1–5 får källor, dag 6–7 noll, men här visar vi dag 1 som default.
        # Samma slump-spann som 40-60% av max (enkel proxy). Eskilstuna enligt intervall.
        def r4060(mx): 
            try: mx=int(mx)
            except: mx=0
            if mx<=0: return 0
            lo=max(0,int(round(mx*0.40))); hi=max(lo,int(round(mx*0.60)))
            return random.randint(lo,hi)

        defaults["pv"] = r4060(CFG["MAX_PAPPAN"])
        defaults["gr"] = r4060(CFG["MAX_GRANNAR"])
        defaults["nv"] = r4060(CFG["MAX_NILS_VANNER"])
        defaults["nf"] = r4060(CFG["MAX_NILS_FAMILJ"])
        defaults["bk"] = r4060(CFG["MAX_BEKANTA"])
        defaults["esk"] = _esk_rand()
        defaults["alskar"] = 6
        defaults["sover"] = 0
        defaults["personal_d"] = suggested_personal
        defaults["bonus_d"] = suggested_bonus
        # Män/Svarta/sexmoment = 0 för vila

    elif scenario == "Vila på jobbet":
        # Slumpa sexmoment inom historiska min/max (enligt din begäran)
        for key, col in [("fitta","Fitta"),("rumpa","Rumpa"),("dp","DP"),("dpp","DPP"),("dap","DAP"),("tap","TAP")]:
            mn, mx = _get_min_max(col)
            defaults[key] = random.randint(mn, mx) if mx >= mn else 0
        # Källor 40–60% av max, Eskilstuna enligt intervall
        def r4060(mx): 
            try: mx=int(mx)
            except: mx=0
            if mx<=0: return 0
            lo=max(0,int(round(mx*0.40))); hi=max(lo,int(round(mx*0.60)))
            return random.randint(lo,hi)
        defaults["pv"] = r4060(CFG["MAX_PAPPAN"])
        defaults["gr"] = r4060(CFG["MAX_GRANNAR"])
        defaults["nv"] = r4060(CFG["MAX_NILS_VANNER"])
        defaults["nf"] = r4060(CFG["MAX_NILS_FAMILJ"])
        defaults["bk"] = r4060(CFG["MAX_BEKANTA"])
        defaults["esk"] = _esk_rand()
        defaults["alskar"] = 12
        defaults["sover"] = 1
        defaults["personal_d"] = suggested_personal
        defaults["bonus_d"] = suggested_bonus

    # Skriv in i session_state för input-fälten (unika nycklar)
    st.session_state.in_man   = defaults["man"]
    st.session_state.in_svarta= defaults["svarta"]
    st.session_state.in_fitta = defaults["fitta"]
    st.session_state.in_rumpa = defaults["rumpa"]
    st.session_state.in_dp    = defaults["dp"]
    st.session_state.in_dpp   = defaults["dpp"]
    st.session_state.in_dap   = defaults["dap"]
    st.session_state.in_tap   = defaults["tap"]

    st.session_state.in_pappan   = defaults["pv"]
    st.session_state.in_grannar  = defaults["gr"]
    st.session_state.in_nils_v   = defaults["nv"]
    st.session_state.in_nils_f   = defaults["nf"]
    st.session_state.in_bekanta  = defaults["bk"]
    st.session_state.in_esk      = defaults["esk"]

    st.session_state.in_bonus_d  = defaults["bonus_d"]
    st.session_state.in_personal = defaults["personal_d"]

    st.session_state.in_alskar   = defaults["alskar"]
    st.session_state.in_sover    = defaults["sover"]

    st.session_state.in_tid_s    = defaults["tid_s"]
    st.session_state.in_tid_d    = defaults["tid_d"]
    st.session_state.in_vila     = defaults["vila"]
    st.session_state.in_dt_tid   = defaults["dt_tid"]
    st.session_state.in_dt_vila  = defaults["dt_vila"]

st.button("🔄 Hämta värden", on_click=_fill_default_values_from_scenario)

# ==== Datum & ålder
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)
alder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month,rad_datum.day)<(CFG["födelsedatum"].month,CFG["födelsedatum"].day))
st.caption(f"Scen {scen} — {rad_datum} ({veckodag}) · Malins ålder: {alder} år")

# ============================ Inmatning (rätt ordning) ============================
# OBS: endast standardvärden från session_state om de finns; annars 0
def _sg(key, default):
    return st.session_state.get(key, default)

män    = st.number_input(_L(LABELS,"Män"),    min_value=0, step=1, value=_sg("in_man",0), key="in_man")
svarta = st.number_input(_L(LABELS,"Svarta"), min_value=0, step=1, value=_sg("in_svarta",0), key="in_svarta")
fitta  = st.number_input("Fitta",  min_value=0, step=1, value=_sg("in_fitta",0), key="in_fitta")
rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=_sg("in_rumpa",0), key="in_rumpa")
dp     = st.number_input("DP",     min_value=0, step=1, value=_sg("in_dp",0), key="in_dp")
dpp    = st.number_input("DPP",    min_value=0, step=1, value=_sg("in_dpp",0), key="in_dpp")
dap    = st.number_input("DAP",    min_value=0, step=1, value=_sg("in_dap",0), key="in_dap")
tap    = st.number_input("TAP",    min_value=0, step=1, value=_sg("in_tap",0), key="in_tap")

lbl_p  = f"{_L(LABELS,'Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
lbl_g  = f"{_L(LABELS,'Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
lbl_nv = f"{_L(LABELS,'Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
lbl_nf = f"{_L(LABELS,'Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
lbl_bk = f"{_L(LABELS,'Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=_sg("in_pappan",0), key="in_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=_sg("in_grannar",0), key="in_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=_sg("in_nils_v",0), key="in_nils_v")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=_sg("in_nils_f",0), key="in_nils_f")
bekanta        = st.number_input(_L(LABELS,"Bekanta"), min_value=0, step=1, value=_sg("in_bekanta",0), key="in_bekanta")
eskilstuna_killar = st.number_input(_L(LABELS,"Eskilstuna killar"), min_value=0, step=1, value=_sg("in_esk",0), key="in_esk")

bonus_deltagit    = st.number_input(_L(LABELS,"Bonus deltagit"), min_value=0, step=1, value=_sg("in_bonus_d",0), key="in_bonus_d")
personal_deltagit = st.number_input(_L(LABELS,"Personal deltagit"), min_value=0, step=1, value=_sg("in_personal",max(0,int(round(CFG['PROD_STAFF']*CFG['PERSONAL_PCT']/100)))), key="in_personal")

älskar    = st.number_input("Älskar",                min_value=0, step=1, value=_sg("in_alskar",0), key="in_alskar")
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=_sg("in_sover",0), key="in_sover")

tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=_sg("in_tid_s",60), key="in_tid_s")
tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=_sg("in_tid_d",60), key="in_tid_d")
vila   = st.number_input("Vila (sek)",  min_value=0, step=1, value=_sg("in_vila",7), key="in_vila")
dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=_sg("in_dt_tid",60), key="in_dt_tid")
dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=_sg("in_dt_vila",3), key="in_dt_vila")

# ===== Max-varningar (visuellt)
if pappans_vänner > int(CFG["MAX_PAPPAN"]):
    st.warning(f"{pappans_vänner} > max {int(CFG['MAX_PAPPAN'])} för Pappans vänner")
if grannar > int(CFG["MAX_GRANNAR"]):
    st.warning(f"{grannar} > max {int(CFG['MAX_GRANNAR'])} för Grannar")
if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
    st.warning(f"{nils_vänner} > max {int(CFG['MAX_NILS_VANNER'])} för Nils vänner")
if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
    st.warning(f"{nils_familj} > max {int(CFG['MAX_NILS_FAMILJ'])} för Nils familj")
if bekanta > int(CFG["MAX_BEKANTA"]):
    st.warning(f"{bekanta} > max {int(CFG['MAX_BEKANTA'])} för Bekanta")

# ===== Grunddict för beräkningen (OBS: PROD_STAFF skickas alltid för lönebas)
grund_preview = {
    "Typ": scenario,
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
    "Älskar": älskar, "Sover med": sover_med,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
    "Bonus killar": int(CFG["BONUS_AVAILABLE"]),  # totala tillg.
    "Bonus deltagit": bonus_deltagit,
    "Personal deltagit": personal_deltagit,
    "Nils": 0,
    "Avgift": float(CFG["avgift_usd"]),
    "PROD_STAFF": int(CFG["PROD_STAFF"])
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

# ===== Live
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

st.markdown("#### 💵 Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))
    st.metric("Bonus kvar (före spar)", int(CFG["BONUS_AVAILABLE"]))

# ===== Spara-rutin
def _save_row(grund, rad_datum, veckodag):
    try:
        base = dict(grund)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        base.setdefault("PROD_STAFF", int(CFG["PROD_STAFF"]))
        ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return False

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)

    # Uppdatera BONUS_AVAILABLE = max(0, old - Bonus deltagit)
    new_bonus_avail = max(0, int(CFG["BONUS_AVAILABLE"]) - int(grund.get("Bonus deltagit", 0)))
    _save_setting("BONUS_AVAILABLE", str(new_bonus_avail))
    CFG["BONUS_AVAILABLE"] = new_bonus_avail

    # bump row count
    st.session_state.ROW_COUNT = st.session_state.get("ROW_COUNT", 0) + 1

    ålder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month,rad_datum.day)<(CFG["födelsedatum"].month,CFG["födelsedatum"].day))
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")
    return True

# Auto-max (endast fråga – uppdaterar i Inställningar först vid bekräftelse)
def _collect_over_max():
    over_max = {}
    if pappans_vänner > int(CFG["MAX_PAPPAN"]):
        over_max[_L(LABELS,'Pappans vänner')] = {"max_key":"MAX_PAPPAN","new_value":pappans_vänner,"current":int(CFG["MAX_PAPPAN"])}
    if grannar > int(CFG["MAX_GRANNAR"]):
        over_max[_L(LABELS,'Grannar')] = {"max_key":"MAX_GRANNAR","new_value":grannar,"current":int(CFG["MAX_GRANNAR"])}
    if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
        over_max[_L(LABELS,'Nils vänner')] = {"max_key":"MAX_NILS_VANNER","new_value":nils_vänner,"current":int(CFG["MAX_NILS_VANNER"])}
    if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
        over_max[_L(LABELS,'Nils familj')] = {"max_key":"MAX_NILS_FAMILJ","new_value":nils_familj,"current":int(CFG["MAX_NILS_FAMILJ"])}
    if bekanta > int(CFG["MAX_BEKANTA"]):
        over_max[_L(LABELS,'Bekanta')] = {"max_key":"MAX_BEKANTA","new_value":bekanta,"current":int(CFG["MAX_BEKANTA"])}
    return over_max

if st.button("💾 Spara raden"):
    over_max = _collect_over_max()
    if over_max:
        st.warning("Värden överstiger max. Vill du uppdatera max i Inställningar först?")
        for f,info in over_max.items():
            st.write(f"- **{f}**: max {info['current']} → **{info['new_value']}**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Uppdatera max och spara"):
                for _,info in over_max.items():
                    _save_setting(info["max_key"], str(int(info["new_value"])))
                    CFG[info["max_key"]] = int(info["new_value"])
                _save_row(grund_preview, rad_datum, veckodag)
                st.rerun()
        with c2:
            if st.button("✋ Avbryt"):
                st.info("Sparning avbröts.")
    else:
        _save_row(grund_preview, rad_datum, veckodag)
        st.rerun()

# ================================ Visa & radera ================================
st.markdown("---")
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
