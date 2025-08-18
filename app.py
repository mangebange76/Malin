# app.py — DEL 1/6
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
                ["PERSONAL_PCT", "10", "Personal deltagit (% av PROD_STAFF)"],
                ["ESK_MIN", "20", "Eskilstuna min (slump)"],
                ["ESK_MAX", "40", "Eskilstuna max (slump)"],
                # Bonusräknare (persistenta – uppdateras bara vid Spara)
                ["BONUS_TOTAL", "0", "Bonus killar totalt"],
                ["BONUS_USED",  "0", "Bonus killar deltagit"],
                ["BONUS_LEFT",  "0", "Bonus killar kvar"],
                # Etiketter (visning)
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

# =========================== Header-säkring / schema ===========================
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

    # Tal
    C["MAX_PAPPAN"]       = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]      = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"]  = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"]  = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]      = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]       = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"]       = int(float(_get("PROD_STAFF", 800)))
    C["PERSONAL_PCT"]     = int(float(_get("PERSONAL_PCT", 10)))
    C["ESK_MIN"]          = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]          = int(float(_get("ESK_MAX", 40)))

    # Bonus-räknare (läses, men uppdateras först vid Spara)
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ==== Scen- och datumhjälpare (robust, inga onödiga Sheets-anrop) ====
ROW_COUNT_KEY = "ROW_COUNT"

def _init_row_count_once():
    if ROW_COUNT_KEY in st.session_state:
        return
    try:
        vals = _retry_call(sheet.col_values, 1)  # EN gång
        st.session_state[ROW_COUNT_KEY] = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
    except Exception:
        st.session_state[ROW_COUNT_KEY] = 0

_init_row_count_once()

def next_scene_number() -> int:
    return int(st.session_state.get(ROW_COUNT_KEY, 0)) + 1

def datum_och_veckodag_för_scen(scen_nummer: int):
    start = CFG.get("startdatum") or date.today()
    d = start + timedelta(days=int(scen_nummer) - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

def _current_scene_info():
    scen = next_scene_number()
    d, veckodag = datum_och_veckodag_för_scen(scen)
    return scen, d, veckodag

# ============================== MENY (vyval) ===============================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# ============================== Sidopanel – inställningar ==============================
with st.sidebar.expander("⚙️ Konfiguration & etiketter", expanded=False):
    # datum/tid
    startdatum = st.date_input("Historiskt startdatum", value=CFG["startdatum"], key="sb_startdatum")
    starttid   = st.time_input("Starttid", value=CFG["starttid"], key="sb_starttid")
    fod        = st.date_input(_get_label(LABELS,"Malins födelsedatum"),
                               value=_clamp(CFG["födelsedatum"], date(1970,1,1), date.today()),
                               key="sb_fod")

    # max-värden
    max_p  = st.number_input(_get_label(LABELS,"Pappans vänner")+" (max)", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]), key="sb_max_p")
    max_g  = st.number_input(_get_label(LABELS,"Grannar")+" (max)",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]), key="sb_max_g")
    max_nv = st.number_input(_get_label(LABELS,"Nils vänner")+" (max)",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]), key="sb_max_nv")
    max_nf = st.number_input(_get_label(LABELS,"Nils familj")+" (max)",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]), key="sb_max_nf")
    max_bk = st.number_input(_get_label(LABELS,"Bekanta")+" (max)",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]), key="sb_max_bk")

    # personal totalt + procent som deltar (ALLTID följer procenten)
    prod_staff = st.number_input("Produktionspersonal (fast)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]), key="sb_prod")
    personal_pct = st.number_input("Personal deltagit (%)", min_value=0, max_value=100, step=1, value=int(CFG["PERSONAL_PCT"]), key="sb_pct")

    # Eskilstuna intervall
    esk_min = st.number_input("Eskilstuna min (slump)", min_value=0, step=1, value=int(CFG["ESK_MIN"]), key="sb_esk_min")
    esk_max = st.number_input("Eskilstuna max (slump)", min_value=0, step=1, value=int(CFG["ESK_MAX"]), key="sb_esk_max")

    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="sb_fee")

    st.markdown("**Etiketter (påverkar endast visning)**")
    lab_p  = st.text_input("Etikett: Pappans vänner", value=_get_label(LABELS, "Pappans vänner"), key="sb_lab_p")
    lab_g  = st.text_input("Etikett: Grannar", value=_get_label(LABELS, "Grannar"), key="sb_lab_g")
    lab_nv = st.text_input("Etikett: Nils vänner", value=_get_label(LABELS, "Nils vänner"), key="sb_lab_nv")
    lab_nf = st.text_input("Etikett: Nils familj", value=_get_label(LABELS, "Nils familj"), key="sb_lab_nf")
    lab_bk = st.text_input("Etikett: Bekanta", value=_get_label(LABELS, "Bekanta"), key="sb_lab_bk")
    lab_esk= st.text_input("Etikett: Eskilstuna killar", value=_get_label(LABELS, "Eskilstuna killar"), key="sb_lab_esk")
    lab_man= st.text_input("Etikett: Män", value=_get_label(LABELS, "Män"), key="sb_lab_man")
    lab_sva= st.text_input("Etikett: Svarta", value=_get_label(LABELS, "Svarta"), key="sb_lab_sva")
    lab_kann=st.text_input("Etikett: Känner", value=_get_label(LABELS, "Känner"), key="sb_lab_kann")
    lab_person=st.text_input("Etikett: Personal deltagit", value=_get_label(LABELS, "Personal deltagit"), key="sb_lab_person")
    lab_bonus =st.text_input("Etikett: Bonus killar", value=_get_label(LABELS, "Bonus killar"), key="sb_lab_bonus")
    lab_bonusd=st.text_input("Etikett: Bonus deltagit", value=_get_label(LABELS, "Bonus deltagit"), key="sb_lab_bonusd")
    lab_mfd   = st.text_input("Etikett: Malins födelsedatum", value=_get_label(LABELS, "Malins födelsedatum"), key="sb_lab_mfd")

    if st.button("💾 Spara inställningar", key="sb_save_cfg"):
        # Skriv endast vid klick
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

# app.py — DEL 2/6  (Scenarioväljare + Hämta värden + Input i rätt ordning)

# ====== Små hjälp-funktioner för scenarion ======
def _personal_from_pct() -> int:
    try:
        return int(round((CFG["PROD_STAFF"] * CFG["PERSONAL_PCT"]) / 100))
    except Exception:
        return 0

def _eskilstuna_random():
    lo = min(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
    hi = max(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
    return random.randint(lo, hi) if hi >= lo else 0

def _get_min_max_from_sheet(colname: str):
    """Hämtar min/max från Google Sheet endast vid behov (när du klickar 'Hämta värden')."""
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = []
    for r in all_rows:
        v = _safe_int(r.get(colname, 0), 0)
        vals.append(v)
    if not vals:
        return 0, 0
    return min(vals), max(vals)

# ====== Scenarioväljare ======
st.markdown("---")
st.subheader("🎬 Välj scenario")
scenario = st.selectbox(
    "Scenario",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet (7 dagar)", "Vila på jobbet"],
    index=0,
    key="scenario_select"
)

# ====== Knappar för flöde ======
c_btn1, c_btn2 = st.columns([1,2])
with c_btn1:
    fetch_clicked = st.button("📥 Hämta/slumpa värden", key="btn_fetch_values")
with c_btn2:
    st.caption("Klick fyller enbart **input** enligt valt scenario. Inget sparas förrän du klickar **Spara raden**.")

# ====== Sätt input via scenario när man klickar 'Hämta värden' ======
if fetch_clicked:
    # Nollställ inte explicit — vi sätter alla fält nedan.
    # Grund: standardvärden för vissa fält
    alskar_val = 8
    sover_val  = 1
    personal_val = _personal_from_pct()

    if scenario == "Ny scen":
        # Här sätter vi endast 'Personal deltagit' enligt %; övriga lämnas som de är (0).
        st.session_state["in_personal_deltagit"] = personal_val

    elif scenario == "Slumpa scen vit":
        # Slumpa utifrån min/max historik (alla relevanta kolumner)
        for col, key in [
            ("Män", "in_men"),
            ("Svarta", "in_svarta"),
            ("Fitta", "in_fitta"),
            ("Rumpa", "in_rumpa"),
            ("DP", "in_dp"),
            ("DPP", "in_dpp"),
            ("DAP", "in_dap"),
            ("TAP", "in_tap"),
            ("Pappans vänner", "in_pappan"),
            ("Grannar", "in_grannar"),
            ("Nils vänner", "in_nils_vanner"),
            ("Nils familj", "in_nils_familj"),
            ("Bekanta", "in_bekanta"),
            ("Eskilstuna killar", "in_eskilstuna"),
        ]:
            mn, mx = _get_min_max_from_sheet(col)
            st.session_state[key] = random.randint(mn, mx) if mx >= mn else 0
        # Älskar / Sover med enligt specifikationen
        st.session_state["in_alskar"] = alskar_val
        st.session_state["in_sover"]  = sover_val
        # Personal enligt % (vit-scen)
        st.session_state["in_personal_deltagit"] = personal_val
        # Bonus deltagit kommer från beräkningar/baserat på bonus-killar — förifyll 0 här; beräkning visar i live
        st.session_state["in_bonus_deltagit"] = 0

    elif scenario == "Slumpa scen svart":
        # Svart: endast sex-aktiviteter + Svarta; övriga källor 0
        for col, key in [
            ("Fitta", "in_fitta"),
            ("Rumpa", "in_rumpa"),
            ("DP", "in_dp"),
            ("DPP", "in_dpp"),
            ("DAP", "in_dap"),
            ("TAP", "in_tap"),
        ]:
            mn, mx = _get_min_max_from_sheet(col)
            st.session_state[key] = random.randint(mn, mx) if mx >= mn else 0
        mn_b, mx_b = _get_min_max_from_sheet("Svarta")
        st.session_state["in_svarta"] = random.randint(mn_b, mx_b) if mx_b >= mn_b else 0

        # Nollställ män-relaterade källor och män
        for k in ["in_men","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
            st.session_state[k] = 0

        st.session_state["in_alskar"] = alskar_val
        st.session_state["in_sover"]  = sover_val
        # Svart-scen: personal deltagit ska vara 0 enligt senaste kravet
        st.session_state["in_personal_deltagit"] = 0
        # Bonus deltagit – sätt 0 här; live-beräkning kommer visa enligt bonus-reglerna
        st.session_state["in_bonus_deltagit"] = 0

    elif scenario == "Vila på jobbet":
        # Slumpa fitta, rumpa, DP, DPP, DAP, TAP mellan MIN/MAX i historiken
        for col, key in [
            ("Fitta", "in_fitta"),
            ("Rumpa", "in_rumpa"),
            ("DP", "in_dp"),
            ("DPP", "in_dpp"),
            ("DAP", "in_dap"),
            ("TAP", "in_tap"),
        ]:
            mn, mx = _get_min_max_from_sheet(col)
            st.session_state[key] = random.randint(mn, mx) if mx >= mn else 0

        # Övriga källor (män etc.) = 0 enligt tidigare logik
        for k in ["in_men","in_svarta","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"]:
            st.session_state[k] = 0
        # Eskilstuna: enligt intervall i sidopanelen
        st.session_state["in_eskilstuna"] = _eskilstuna_random()

        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        st.session_state["in_personal_deltagit"] = personal_val
        st.session_state["in_bonus_deltagit"] = 0  # live-beräkning hanterar bonuslogik

    elif scenario == "Vila i hemmet (7 dagar)":
        # Förhandsifyll för dag 1 i input (alla 7 skapas inte här — du får en separat knapp “Generera 7 rader” senare)
        # Slumpa samma set (fitta,rumpa,dp,dpp,dap,tap) som för “Vila på jobbet”
        for col, key in [
            ("Fitta", "in_fitta"),
            ("Rumpa", "in_rumpa"),
            ("DP", "in_dp"),
            ("DPP", "in_dpp"),
            ("DAP", "in_dap"),
            ("TAP", "in_tap"),
        ]:
            mn, mx = _get_min_max_from_sheet(col)
            st.session_state[key] = random.randint(mn, mx) if mx >= mn else 0

        # Dag 1: män-relaterade = 0, Eskilstuna enligt intervall
        for k in ["in_men","in_svarta","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"]:
            st.session_state[k] = 0
        st.session_state["in_eskilstuna"] = _eskilstuna_random()

        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0  # dag 1 brukar vara 0; (senare dag 6 blir 1 i genereringen)
        st.session_state["in_personal_deltagit"] = personal_val
        st.session_state["in_bonus_deltagit"] = 0

    st.rerun()

# ====== Datum/veckodag för aktuell scen (ej sheets-anrop) ======
scen, rad_datum, veckodag = _current_scene_info()

# ====== INPUT – Exakt ordning ======
st.markdown("---")
st.subheader("➕ Input (i rätt ordning)")

cA, cB, cC, cD = st.columns(4)
with cA:
    in_men     = st.number_input(_get_label(LABELS,"Män"),    min_value=0, step=1, value=st.session_state.get("in_men", 0), key="in_men")
    in_fitta   = st.number_input("Fitta",  min_value=0, step=1, value=st.session_state.get("in_fitta", 0), key="in_fitta")
    in_dp      = st.number_input("DP",     min_value=0, step=1, value=st.session_state.get("in_dp", 0), key="in_dp")
    in_dap     = st.number_input("DAP",    min_value=0, step=1, value=st.session_state.get("in_dap", 0), key="in_dap")
    in_pappan  = st.number_input(_get_label(LABELS,"Pappans vänner"), min_value=0, step=1, value=st.session_state.get("in_pappan", 0), key="in_pappan")
    in_nils_v  = st.number_input(_get_label(LABELS,"Nils vänner"),    min_value=0, step=1, value=st.session_state.get("in_nils_vanner", 0), key="in_nils_vanner")
    in_bekanta = st.number_input(_get_label(LABELS,"Bekanta"),        min_value=0, step=1, value=st.session_state.get("in_bekanta", 0), key="in_bekanta")
    in_bonus_d = st.number_input(_get_label(LABELS,"Bonus deltagit"), min_value=0, step=1, value=st.session_state.get("in_bonus_deltagit", 0), key="in_bonus_deltagit")
    in_alskar  = st.number_input("Älskar", min_value=0, step=1, value=st.session_state.get("in_alskar", 0), key="in_alskar")
    in_tid_s   = st.number_input("Tid S (sek)", min_value=0, step=1, value=st.session_state.get("in_tid_s", 60), key="in_tid_s")
    in_dt_tid  = st.number_input("DT tid (sek/kille)", min_value=0, step=1, value=st.session_state.get("in_dt_tid", 60), key="in_dt_tid")

with cB:
    in_svarta  = st.number_input(_get_label(LABELS,"Svarta"), min_value=0, step=1, value=st.session_state.get("in_svarta", 0), key="in_svarta")
    in_rumpa   = st.number_input("Rumpa",  min_value=0, step=1, value=st.session_state.get("in_rumpa", 0), key="in_rumpa")
    in_dpp     = st.number_input("DPP",    min_value=0, step=1, value=st.session_state.get("in_dpp", 0), key="in_dpp")
    in_tap     = st.number_input("TAP",    min_value=0, step=1, value=st.session_state.get("in_tap", 0), key="in_tap")
    in_grannar = st.number_input(_get_label(LABELS,"Grannar"),        min_value=0, step=1, value=st.session_state.get("in_grannar", 0), key="in_grannar")
    in_nils_f  = st.number_input(_get_label(LABELS,"Nils familj"),    min_value=0, step=1, value=st.session_state.get("in_nils_familj", 0), key="in_nils_familj")
    in_esk     = st.number_input(_get_label(LABELS,"Eskilstuna killar"), min_value=0, step=1, value=st.session_state.get("in_eskilstuna", 0), key="in_eskilstuna")
    in_person  = st.number_input(_get_label(LABELS,"Personal deltagit"), min_value=0, step=1, value=st.session_state.get("in_personal_deltagit", _personal_from_pct()), key="in_personal_deltagit")
    in_sover   = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=st.session_state.get("in_sover", 0), key="in_sover")
    in_tid_d   = st.number_input("Tid D (sek)", min_value=0, step=1, value=st.session_state.get("in_tid_d", 60), key="in_tid_d")
    in_dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=st.session_state.get("in_dt_vila", 3), key="in_dt_vila")

with cC:
    # Tom kolumn för luft / framtida fält
    pass

with cD:
    in_vila    = st.number_input("Vila (sek)",  min_value=0, step=1, value=st.session_state.get("in_vila", 7), key="in_vila")
    # Här kan vi lägga ev. extra fält senare
    avgift_val = st.number_input("Avgift (USD, per rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="in_avgift")

# ====== Varningsflaggor (max) – endast visning ======
if in_pappan > int(CFG["MAX_PAPPAN"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_pappan} > max {int(CFG['MAX_PAPPAN'])}</span>", unsafe_allow_html=True)
if in_grannar > int(CFG["MAX_GRANNAR"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_grannar} > max {int(CFG['MAX_GRANNAR'])}</span>", unsafe_allow_html=True)
if in_nils_v > int(CFG["MAX_NILS_VANNER"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_nils_v} > max {int(CFG['MAX_NILS_VANNER'])}</span>", unsafe_allow_html=True)
if in_nils_f > int(CFG["MAX_NILS_FAMILJ"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_nils_f} > max {int(CFG['MAX_NILS_FAMILJ'])}</span>", unsafe_allow_html=True)
if in_bekanta > int(CFG["MAX_BEKANTA"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_bekanta} > max {int(CFG['MAX_BEKANTA'])}</span>", unsafe_allow_html=True)

# app.py — DEL 3/6  (Live-förhandsberäkning + Ekonomi + Ålder)

# ====== Hjälp: räkna ålder vid datum ======
def _age_on(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))

# ====== Bygg grund_preview från inputs (utan att skriva till Sheets) ======
grund_preview = {
    "Typ": scenario if scenario != "Ny scen" else "",
    "Veckodag": veckodag,
    "Scen": scen,

    # Inputfält (i rätt ordning)
    "Män": in_men,
    "Svarta": in_svarta,
    "Fitta": in_fitta,
    "Rumpa": in_rumpa,
    "DP": in_dp,
    "DPP": in_dpp,
    "DAP": in_dap,
    "TAP": in_tap,

    "Pappans vänner": in_pappan,
    "Grannar": in_grannar,
    "Nils vänner": in_nils_v,
    "Nils familj": in_nils_f,
    "Bekanta": in_bekanta,
    "Eskilstuna killar": in_esk,

    "Bonus killar": 0,  # (räknas i beräkningar utifrån prenumeranter/logik)
    "Bonus deltagit": in_bonus_d,  # visas live enligt input (beräkningar får också sätta värde i resultatet)
    "Personal deltagit": in_person,

    "Älskar": in_alskar,
    "Sover med": in_sover,

    "Tid S": in_tid_s,
    "Tid D": in_tid_d,
    "Vila": in_vila,
    "DT tid (sek/kille)": in_dt_tid,
    "DT vila (sek/kille)": in_dt_vila,

    "Nils": 0,  # separat fält vid behov
    "Avgift": float(avgift_val),

    # Viktigt: total personal (alla ska få lön oavsett deltagit)
    "PROD_STAFF": int(CFG.get("PROD_STAFF", 800)),
}

# ====== Live-beräkning (ingen skrivning) ======
preview = {}
try:
    if callable(calc_row_values):
        # Anropa POSITIONELLT: (grund_dict, rad_datum, födelsedatum, starttid)
        preview = calc_row_values(grund_preview, rad_datum, CFG["födelsedatum"], CFG["starttid"])
    else:
        preview = {}
except Exception as e:
    st.warning(f"Förhandsberäkning misslyckades: {e}")
    preview = {}

# ====== Ålder live ======
alder_live = _age_on(rad_datum, CFG["födelsedatum"])

# ====== Live-visning ======
st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin)", f"{alder_live} år")
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
with col2:
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
with col3:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Klockan", preview.get("Klockan", "-"))

# Visa även Bonus deltagit som faktisk siffra som används i beräkning
st.caption(f"Bonus deltagit (input): {in_bonus_d}  •  Beräknad (preview): {preview.get('Bonus deltagit','-')}")

# ====== Ekonomi (live) ======
st.markdown("#### 💵 Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", avgift_val)))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ====== Info om vilka värden som INTE räknas in i scenernas körtid ======
with st.expander("ℹ️ Tidslogik (live)", expanded=False):
    st.write(
        "- **Summa tid** innehåller: Summa S (inkl. DT tid), Summa D, Summa TP, Summa Vila (inkl. DT vila).\n"
        "- **Älskar/Sover med** adderas till **Klockan** men **ingår inte** i scenernas körtid.\n"
        "- **Hångel** och **Suger** visas endast i live för uppföljning.\n"
        "- **Lön/Utgift män** räknar med hela personalstyrkan (`PROD_STAFF`), oberoende av 'Personal deltagit'."
    )

# app.py — DEL 4/6  (Spara-flöde, Auto-max, batch-sparning för 7-dagars)

ROW_COUNT_KEY = "ROW_COUNT"

# ---- Hjälp: bygg en "grund"-rad från nuvarande inputs (för enkelrads-scenario) ----
def _build_base_from_inputs(scen_label: str) -> dict:
    return {
        "Typ": scen_label if scen_label != "Ny scen" else "",
        "Veckodag": veckodag,
        "Scen": scen,
        "Män": in_men,
        "Svarta": in_svarta,
        "Fitta": in_fitta,
        "Rumpa": in_rumpa,
        "DP": in_dp,
        "DPP": in_dpp,
        "DAP": in_dap,
        "TAP": in_tap,
        "Pappans vänner": in_pappan,
        "Grannar": in_grannar,
        "Nils vänner": in_nils_v,
        "Nils familj": in_nils_f,
        "Bekanta": in_bekanta,
        "Eskilstuna killar": in_esk,
        "Bonus killar": 0,                 # räknas i beräkningar
        "Bonus deltagit": in_bonus_d,      # enligt input/buffert
        "Personal deltagit": in_person,
        "Älskar": in_alskar,
        "Sover med": in_sover,
        "Tid S": in_tid_s,
        "Tid D": in_tid_d,
        "Vila": in_vila,
        "DT tid (sek/kille)": in_dt_tid,
        "DT vila (sek/kille)": in_dt_vila,
        "Nils": 0,
        "Avgift": float(avgift_val),
        "PROD_STAFF": int(CFG.get("PROD_STAFF", 800)),  # hela personalstyrkan ska få lön
    }

# ---- Hjälp: se till att header finns (kallas vid spar) ----
def _ensure_header_on_save():
    header = _retry_call(sheet.row_values, 1)
    if not header:
        _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
        st.session_state[ROW_COUNT_KEY] = 0
        return DEFAULT_COLUMNS
    # migrera ev. saknade
    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        from gspread.utils import rowcol_to_a1
        new_header = header + missing
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        return new_header
    return header

# ---- Auto-max kontroll för källor (görs vid spar) ----
def _compute_over_max_for(base: dict) -> dict:
    over = {}
    if base.get("Pappans vänner", 0) > int(CFG["MAX_PAPPAN"]):
        over["Pappans vänner"] = {"current_max": int(CFG["MAX_PAPPAN"]), "new_value": int(base["Pappans vänner"]), "max_key": "MAX_PAPPAN"}
    if base.get("Grannar", 0) > int(CFG["MAX_GRANNAR"]):
        over["Grannar"] = {"current_max": int(CFG["MAX_GRANNAR"]), "new_value": int(base["Grannar"]), "max_key": "MAX_GRANNAR"}
    if base.get("Nils vänner", 0) > int(CFG["MAX_NILS_VANNER"]):
        over["Nils vänner"] = {"current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": int(base["Nils vänner"]), "max_key": "MAX_NILS_VANNER"}
    if base.get("Nils familj", 0) > int(CFG["MAX_NILS_FAMILJ"]):
        over["Nils familj"] = {"current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": int(base["Nils familj"]), "max_key": "MAX_NILS_FAMILJ"}
    if base.get("Bekanta", 0) > int(CFG["MAX_BEKANTA"]):
        over["Bekanta"] = {"current_max": int(CFG["MAX_BEKANTA"]), "new_value": int(base["Bekanta"]), "max_key": "MAX_BEKANTA"}
    return over

def _apply_over_max_updates(over: dict):
    # uppdatera Inställningar (max) när användaren bekräftar
    for _, info in over.items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))
        CFG[key] = new_val

# ---- Spara EN rad till Sheets ----
def _save_one_row(base: dict, row_date: date, veckodag_str: str):
    _ensure_header_on_save()
    # kör den riktiga rad-beräkningen
    ber = calc_row_values(base, row_date, CFG["födelsedatum"], CFG["starttid"])
    ber["Datum"] = row_date.isoformat()
    # skriv i kolumnordning
    header = _retry_call(sheet.row_values, 1)
    cols = header if header else DEFAULT_COLUMNS
    out = [ber.get(c, "") for c in cols]
    _retry_call(sheet.append_row, out)
    # bumpa räknare
    st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1

# ---- Spara antingen EN rad, eller en lista av rader (t.ex. 7 för "Vila i hemmet") ----
def _save_rows(rows_to_save: list):
    # rows_to_save: lista av tuples (base_dict, datum, veckodag_str)
    for base, dt, vd in rows_to_save:
        _save_one_row(base, dt, vd)

# ========= UI: Spara-knapp (hanterar Auto-max & batch) =========
st.markdown("---")
st.subheader("💾 Spara")

# Buffert: om scenario "Vila i hemmet" genererade 7 dagar ligger de här (från Del 2)
multi = st.session_state.get("MULTI_PREVIEW_ROWS", None)

def _make_rows_payload():
    if multi:
        # spara alla 7
        return [(row["base"], row["date"], row["veckodag"]) for row in multi]
    # annars spara den aktuella
    single_base = _build_base_from_inputs(scenario)
    return [(single_base, rad_datum, veckodag)]

# Förhandsvisa vilka rader som kommer sparas
with st.expander("Visa rader som kommer att sparas", expanded=False):
    payload = _make_rows_payload()
    st.write(f"Antal rader: {len(payload)}")
    for i, (b, dt, vd) in enumerate(payload, start=1):
        st.write(f"**{i}.** {dt} ({vd}) — Typ: {b.get('Typ','') or 'Ny scen'} — Män: {b.get('Män',0)}, Svarta: {b.get('Svarta',0)}, Bonus deltagit: {b.get('Bonus deltagit',0)}, Personal deltagit: {b.get('Personal deltagit',0)}")

# Klick = gör över-max-kontroll; om något över -> fråga; annars skriv direkt
if st.button("💾 Spara nu"):
    payload = _make_rows_payload()
    # samla alla over_max över samtliga rader
    over_all = {}
    for (b, _dt, _vd) in payload:
        over = _compute_over_max_for(b)
        if over:
            over_all.update(over)

    if over_all:
        # visa bekräftelse
        st.session_state["PENDING_SAVE_ROWS"] = payload
        st.session_state["PENDING_OVERMAX"] = over_all
        st.warning("Vissa värden överstiger nuvarande max. Vill du uppdatera max och fortsätta spara?")
    else:
        try:
            _save_rows(payload)
            st.success(f"Sparade {len(payload)} rad(er) ✅")
            # töm buffert för 7-dagars om den fanns
            st.session_state.pop("MULTI_PREVIEW_ROWS", None)
            st.rerun()
        except Exception as e:
            st.error(f"Kunde inte spara: {e}")

# Bekräftelsedialog för Auto-max
if "PENDING_SAVE_ROWS" in st.session_state:
    over_all = st.session_state.get("PENDING_OVERMAX", {})
    if over_all:
        with st.expander("Detaljer om max-uppdateringar", expanded=True):
            for f, info in over_all.items():
                st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Uppdatera max och spara"):
                try:
                    _apply_over_max_updates(over_all)
                    _save_rows(st.session_state["PENDING_SAVE_ROWS"])
                    st.success(f"Sparade {len(st.session_state['PENDING_SAVE_ROWS'])} rad(er) ✅")
                    st.session_state.pop("PENDING_SAVE_ROWS", None)
                    st.session_state.pop("PENDING_OVERMAX", None)
                    st.session_state.pop("MULTI_PREVIEW_ROWS", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Kunde inte spara: {e}")
        with c2:
            if st.button("✋ Avbryt"):
                st.session_state.pop("PENDING_SAVE_ROWS", None)
                st.session_state.pop("PENDING_OVERMAX", None)
                st.info("Sparning avbruten.")

# app.py — DEL 5/6  (Sidopanel + Statistik)

# ---------------------- SIDOPANEL: inställningar & etiketter ----------------------
st.sidebar.header("Inställningar")

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    # --- Basvärden (läser från CFG en gång; skriver först på klick) ---
    startdatum_inp = st.date_input("Historiskt startdatum",
                                   value=CFG["startdatum"],
                                   key="sb_startdatum")
    starttid_inp   = st.time_input("Starttid",
                                   value=CFG["starttid"],
                                   key="sb_starttid")
    fod_inp        = st.date_input("Malins födelsedatum",
                                   value=CFG["födelsedatum"],
                                   key="sb_fodelsedatum")

    # Maxkällor
    max_p  = st.number_input("Max Pappans vänner", min_value=0, step=1,
                             value=int(CFG["MAX_PAPPAN"]), key="sb_max_p")
    max_g  = st.number_input("Max Grannar",        min_value=0, step=1,
                             value=int(CFG["MAX_GRANNAR"]), key="sb_max_g")
    max_nv = st.number_input("Max Nils vänner",    min_value=0, step=1,
                             value=int(CFG["MAX_NILS_VANNER"]), key="sb_max_nv")
    max_nf = st.number_input("Max Nils familj",    min_value=0, step=1,
                             value=int(CFG["MAX_NILS_FAMILJ"]), key="sb_max_nf")
    max_bk = st.number_input("Max Bekanta",        min_value=0, step=1,
                             value=int(CFG["MAX_BEKANTA"]), key="sb_max_bk")

    # Produktionspersonal totalt + procent som deltar (standard 10%)
    prod_staff_inp = st.number_input("Produktionspersonal totalt",
                                     min_value=0, step=1,
                                     value=int(CFG.get("PROD_STAFF", 800)),
                                     key="sb_prod_staff")
    personal_pct_inp = st.number_input(
        "Andel personal som deltar (%)",
        min_value=0.0, max_value=100.0, step=0.1,
        value=float(st.session_state.get("personal_pct", 10.0)),
        key="sb_personal_pct"
    )

    # Eskilstuna-intervall för slump
    st.markdown("**Intervall för Eskilstuna killar (slump)**")
    esk_min_inp = st.number_input("Min", min_value=0, step=1,
                                  value=int(st.session_state.get("eskilstuna_min", 20)),
                                  key="sb_esk_min")
    esk_max_inp = st.number_input("Max", min_value=0, step=1,
                                  value=int(st.session_state.get("eskilstuna_max", 40)),
                                  key="sb_esk_max")

    # Avgift per rad
    avgift_inp = st.number_input("Avgift (USD, per ny rad)",
                                 min_value=0.0, step=1.0,
                                 value=float(CFG["avgift_usd"]),
                                 key="sb_avgift")

    st.markdown("---")
    st.markdown("**Etiketter (påverkar endast visning)**")
    lab_p   = st.text_input("Etikett: Pappans vänner",   value=LABELS.get("Pappans vänner",""), key="sb_lab_p")
    lab_g   = st.text_input("Etikett: Grannar",          value=LABELS.get("Grannar",""), key="sb_lab_g")
    lab_nv  = st.text_input("Etikett: Nils vänner",      value=LABELS.get("Nils vänner",""), key="sb_lab_nv")
    lab_nf  = st.text_input("Etikett: Nils familj",      value=LABELS.get("Nils familj",""), key="sb_lab_nf")
    lab_bk  = st.text_input("Etikett: Bekanta",          value=LABELS.get("Bekanta",""), key="sb_lab_bk")
    lab_esk = st.text_input("Etikett: Eskilstuna killar",value=LABELS.get("Eskilstuna killar",""), key="sb_lab_esk")
    lab_man = st.text_input("Etikett: Män",              value=LABELS.get("Män",""), key="sb_lab_man")
    lab_sva = st.text_input("Etikett: Svarta",           value=LABELS.get("Svarta",""), key="sb_lab_sva")
    lab_kann= st.text_input("Etikett: Känner",           value=LABELS.get("Känner",""), key="sb_lab_kann")
    lab_per = st.text_input("Etikett: Personal deltagit",value=LABELS.get("Personal deltagit",""), key="sb_lab_per")
    lab_bon = st.text_input("Etikett: Bonus killar",     value=LABELS.get("Bonus killar",""), key="sb_lab_bon")
    lab_bod = st.text_input("Etikett: Bonus deltagit",   value=LABELS.get("Bonus deltagit",""), key="sb_lab_bod")

    # Spara inställningar
    if st.button("💾 Spara inställningar", key="sb_save"):
        try:
            # Persist
            _save_setting("startdatum", startdatum_inp.isoformat())
            _save_setting("starttid", starttid_inp.strftime("%H:%M"))
            _save_setting("födelsedatum", fod_inp.isoformat())

            _save_setting("MAX_PAPPAN", str(int(max_p)))
            _save_setting("MAX_GRANNAR", str(int(max_g)))
            _save_setting("MAX_NILS_VANNER", str(int(max_nv)))
            _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)))
            _save_setting("MAX_BEKANTA", str(int(max_bk)))

            _save_setting("PROD_STAFF", str(int(prod_staff_inp)))
            _save_setting("avgift_usd", str(float(avgift_inp)))

            # Etikett-override
            _save_setting("LABEL_Pappans vänner", lab_p or "", "")
            _save_setting("LABEL_Grannar",        lab_g or "", "")
            _save_setting("LABEL_Nils vänner",    lab_nv or "", "")
            _save_setting("LABEL_Nils familj",    lab_nf or "", "")
            _save_setting("LABEL_Bekanta",        lab_bk or "", "")
            _save_setting("LABEL_Eskilstuna killar", lab_esk or "", "")
            _save_setting("LABEL_Män", lab_man or "", "")
            _save_setting("LABEL_Svarta", lab_sva or "", "")
            _save_setting("LABEL_Känner", lab_kann or "", "")
            _save_setting("LABEL_Personal deltagit", lab_per or "", "")
            _save_setting("LABEL_Bonus killar", lab_bon or "", "")
            _save_setting("LABEL_Bonus deltagit", lab_bod or "", "")

            # Uppdatera runtime-CFG / session_state (utan fler Sheets-anrop)
            CFG["startdatum"]       = startdatum_inp
            CFG["starttid"]         = starttid_inp
            CFG["födelsedatum"]     = fod_inp
            CFG["MAX_PAPPAN"]       = int(max_p)
            CFG["MAX_GRANNAR"]      = int(max_g)
            CFG["MAX_NILS_VANNER"]  = int(max_nv)
            CFG["MAX_NILS_FAMILJ"]  = int(max_nf)
            CFG["MAX_BEKANTA"]      = int(max_bk)
            CFG["PROD_STAFF"]       = int(prod_staff_inp)
            CFG["avgift_usd"]       = float(avgift_inp)

            st.session_state.personal_pct  = float(personal_pct_inp)
            st.session_state.eskilstuna_min = int(min(esk_min_inp, esk_max_inp))
            st.session_state.eskilstuna_max = int(max(esk_min_inp, esk_max_inp))

            # Uppdatera LABELS i minnet
            for k, v in [
                ("Pappans vänner", lab_p), ("Grannar", lab_g), ("Nils vänner", lab_nv),
                ("Nils familj", lab_nf), ("Bekanta", lab_bk), ("Eskilstuna killar", lab_esk),
                ("Män", lab_man), ("Svarta", lab_sva), ("Känner", lab_kann),
                ("Personal deltagit", lab_per), ("Bonus killar", lab_bon), ("Bonus deltagit", lab_bod)
            ]:
                if v is not None and v.strip() != "":
                    LABELS[k] = v.strip()

            st.success("Inställningar & etiketter sparade ✅")
            st.rerun()
        except Exception as e:
            st.error(f"Kunde inte spara inställningarna: {e}")

# ------------------------------ STATISTIK-VY -----------------------------------
if view == "Statistik":
    st.header("📊 Statistik")

    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # Hjälpare
    def _safe_i(x): return _safe_int(x, 0)

    def _row_tot_men(r):
        # Om "Totalt Män" finns, använd den. Annars räkna ihop komponenterna.
        if "Totalt Män" in r and str(r.get("Totalt Män","")).strip() != "":
            return _safe_i(r.get("Totalt Män", 0))
        return (
            _safe_i(r.get("Män", 0)) + _safe_i(r.get("Känner", 0)) + _safe_i(r.get("Svarta", 0)) +
            _safe_i(r.get("Bekanta", 0)) + _safe_i(r.get("Eskilstuna killar", 0)) +
            _safe_i(r.get("Bonus deltagit", 0)) + _safe_i(r.get("Personal deltagit", 0))
        )

    # Bas
    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man_sum = 0
    bonus_deltagit_sum = 0
    personal_deltagit_sum = 0

    svarta_like_sum = 0  # Svarta + Bonus deltagit räknas som svarta i andel
    tot_for_andel_svarta = 0

    # Prenumeranter
    from datetime import timedelta as _td
    cutoff = date.today() - _td(days=30)
    total_pren = 0
    aktiva_pren = 0

    for r in rows:
        typ = (r.get("Typ") or "").strip()
        tot_m = _row_tot_men(r)

        if tot_m > 0:
            antal_scener += 1
        elif _safe_i(r.get("Känner", 0)) > 0:
            privat_gb_cnt += 1

        totalt_man_sum += tot_m

        svarta_like_sum += _safe_i(r.get("Svarta", 0)) + _safe_i(r.get("Bonus deltagit", 0))
        tot_for_andel_svarta += max(0, tot_m)

        bonus_deltagit_sum   += _safe_i(r.get("Bonus deltagit", 0))
        personal_deltagit_sum+= _safe_i(r.get("Personal deltagit", 0))

        if typ not in ("Vila på jobbet", "Vila i hemmet"):
            total_pren += _safe_i(r.get("Prenumeranter", 0))
            d = _parse_iso_date(r.get("Datum", ""))
            if d and d >= cutoff:
                aktiva_pren += _safe_i(r.get("Prenumeranter", 0))

    andel_svarta_pct = round((svarta_like_sum / tot_for_andel_svarta) * 100, 2) if tot_for_andel_svarta > 0 else 0.0

    # Metrik
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

    st.markdown("---")
    st.subheader("🔩 DP/DPP/DAP/TAP — Summa och snitt per scen")
    dp_sum  = sum(_safe_i(r.get("DP", 0))  for r in rows if _safe_i(r.get("DP", 0))  > 0)
    dpp_sum = sum(_safe_i(r.get("DPP", 0)) for r in rows if _safe_i(r.get("DPP", 0)) > 0)
    dap_sum = sum(_safe_i(r.get("DAP", 0)) for r in rows if _safe_i(r.get("DAP", 0)) > 0)
    tap_sum = sum(_safe_i(r.get("TAP", 0)) for r in rows if _safe_i(r.get("TAP", 0)) > 0)

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

# app.py — DEL 6/6  (Data-tabell, radering & småhjälpare)

# ------------------------------ VISA DATA (frivillig läsning) ------------------------------
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

# -------------------------------- RADERA RAD (explicit åtgärd) -----------------------------
st.subheader("🗑 Ta bort rad")
try:
    # ROW_COUNT hålls uppdaterad endast när vi sparar/ta bort (inte vid varje keypress)
    total_rows = st.session_state.get(ROW_COUNT_KEY, 0)
    if total_rows <= 0:
        # Om vi inte har någon cache (t.ex. precis startat), försök läsa snabbt EN gång:
        try:
            vals = _retry_call(sheet.col_values, 1)  # kolumn A (Datum)
            total_rows = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
            st.session_state[ROW_COUNT_KEY] = total_rows
        except Exception:
            total_rows = 0

    if total_rows > 0:
        idx = st.number_input(
            "Radnummer att ta bort (1 = första dataraden)",
            min_value=1, max_value=total_rows, step=1, value=1, key="del_idx"
        )
        if st.button("Ta bort vald rad", key="btn_del_row"):
            try:
                _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 pga header
                st.session_state[ROW_COUNT_KEY] = max(0, st.session_state.get(ROW_COUNT_KEY, 0) - 1)
                st.success(f"Rad {idx} borttagen.")
                st.rerun()
            except Exception as e:
                st.error(f"Kunde inte ta bort rad: {e}")
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte initiera radering: {e}")

# ----------------------------------- SLUT PÅ APP -----------------------------------
