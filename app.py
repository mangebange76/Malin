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
SETTINGS_SHEET  = "Inställningar"

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket via ID eller URL och hämta bladet 'Data'."""
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        sh = _retry_call(client.open_by_key, sid)
    else:
        url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
        if not url:
            st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets.")
            st.stop()
        sh = _retry_call(client.open_by_url, url)

    # Säkerställ att Inställningar-bladet finns (INTE skapa något annat blad)
    try:
        _ = sh.worksheet(SETTINGS_SHEET)
    except gspread.WorksheetNotFound:
        _retry_call(sh.add_worksheet, title=SETTINGS_SHEET, rows=200, cols=3)
        ws = sh.worksheet(SETTINGS_SHEET)
        _retry_call(ws.update, "A1:C1", [["Key", "Value", "Label"]])

    return sh

spreadsheet = resolve_sheet()

def _get_settings_ws():
    # Robust: undvik APIError genom att slå upp via metadata och fallback till listning
    try:
        return spreadsheet.worksheet(SETTINGS_SHEET)
    except Exception:
        # Hitta via lista
        for ws in spreadsheet.worksheets():
            if ws.title == SETTINGS_SHEET:
                return ws
        # Om saknas helt: skapa (enda plats vi skapar)
        ws = _retry_call(spreadsheet.add_worksheet, title=SETTINGS_SHEET, rows=200, cols=3)
        _retry_call(ws.update, "A1:C1", [["Key", "Value", "Label"]])
        return ws

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
    "Bonus killar","Bonus deltagit",
    "Totalt Män","Tid kille","Nils",
    "Hångel (sek/kille)","Hångel (m:s/kille)",
    "Suger","Suger per kille (sek)",
    "Hårdhet","Prenumeranter","Avgift","Intäkter",
    "Intäkt män","Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst",
    "Känner Sammanlagt"
]

def _ensure_data_ws_and_header():
    # Öppna/Skapa bara DATA-bladet och säkerställ headers
    try:
        data_ws = spreadsheet.worksheet(WORKSHEET_TITLE)
    except gspread.WorksheetNotFound:
        data_ws = _retry_call(spreadsheet.add_worksheet, title=WORKSHEET_TITLE, rows=1000, cols=len(DEFAULT_COLUMNS)+5)
        _retry_call(data_ws.update, "A1:ZZ1", [DEFAULT_COLUMNS])
        return data_ws

    header = _retry_call(data_ws.row_values, 1)
    if not header:
        _retry_call(data_ws.update, "A1:ZZ1", [DEFAULT_COLUMNS])
    else:
        missing = [c for c in DEFAULT_COLUMNS if c not in header]
        if missing:
            new_header = header + missing
            _retry_call(data_ws.update, "A1:ZZ1", [new_header])
    return data_ws

sheet = _ensure_data_ws_and_header()
KOLUMNER = _retry_call(sheet.row_values, 1)

# ====================== Ladda / Spara Inställningar (Key/Value/Label) ======================
DEFAULT_CFG = {
    "STARTDATE": date.today().isoformat(),
    "STARTTIME": "07:00:00",
    "BIRTHDATE": "1990-01-01",
    "MAX_PAPPAN": "10",
    "MAX_GRANNAR": "10",
    "MAX_NILS_VANNER": "10",
    "MAX_NILS_FAMILJ": "10",
    "MAX_BEKANTA": "10",
    "FEE_USD": "30",
    # Bonus-pool
    "BONUS_POOL_TOTAL": "0",
    "BONUS_PARTICIPATED": "0",
    # Etiketter
    "LABEL_PAPPAN": "Pappans vänner",
    "LABEL_GRANNAR": "Grannar",
    "LABEL_NILS_VANNER": "Nils vänner",
    "LABEL_NILS_FAMILJ": "Nils familj",
    "LABEL_BEKANTA": "Bekanta",
    "LABEL_ESKILSTUNA": "Eskilstuna killar",
    "LABEL_MEN": "Män",
    "LABEL_BLACK": "Svarta",
    "LABEL_BIRTHDATE": "Malins födelsedatum",
}

def _settings_as_dict():
    ws = _get_settings_ws()
    rows = _retry_call(ws.get_all_records)
    data = {}
    for r in rows:
        key = (r.get("Key") or "").strip()
        if not key:
            continue
        val = (str(r.get("Value")) if r.get("Value") is not None else "").strip()
        label = (r.get("Label") or "").strip()
        data[key] = {"Value": val, "Label": label}
    # Fyll på saknade nycklar med default
    changed = False
    for k, v in DEFAULT_CFG.items():
        if k not in data:
            data[k] = {"Value": str(v), "Label": ""}
            changed = True
    if changed:
        _write_settings_dict(data)
    return data

def _write_settings_dict(dct):
    ws = _get_settings_ws()
    # skriv rubriker varje gång för säkerhets skull
    values = [["Key", "Value", "Label"]]
    for k, trip in dct.items():
        values.append([k, trip.get("Value", ""), trip.get("Label", "")])
    _retry_call(ws.clear)
    _retry_call(ws.update, f"A1:C{len(values)}", values)

def _load_cfg():
    d = _settings_as_dict()
    # Gör ett string->value map + labels
    CFG_STR = {k: v["Value"] for k, v in d.items()}
    LABELS = {
        "PAPPAN": d.get("LABEL_PAPPAN", {}).get("Label") or "Pappans vänner",
        "GRANNAR": d.get("LABEL_GRANNAR", {}).get("Label") or "Grannar",
        "NILS_VANNER": d.get("LABEL_NILS_VANNER", {}).get("Label") or "Nils vänner",
        "NILS_FAMILJ": d.get("LABEL_NILS_FAMILJ", {}).get("Label") or "Nils familj",
        "BEKANTA": d.get("LABEL_BEKANTA", {}).get("Label") or "Bekanta",
        "ESKILSTUNA": d.get("LABEL_ESKILSTUNA", {}).get("Label") or "Eskilstuna killar",
        "MEN": d.get("LABEL_MEN", {}).get("Label") or "Män",
        "BLACK": d.get("LABEL_BLACK", {}).get("Label") or "Svarta",
        "BIRTHDATE": d.get("LABEL_BIRTHDATE", {}).get("Label") or "Malins födelsedatum",
    }
    return CFG_STR, LABELS

CFG_STR, LABELS = _load_cfg()

# Helper getters
def _cfg_int(k, default=0):
    try:
        return int(float(CFG_STR.get(k, default)))
    except Exception:
        return int(default)

def _cfg_float(k, default=0.0):
    try:
        return float(CFG_STR.get(k, default))
    except Exception:
        return float(default)

def _cfg_date(k, default_iso):
    s = CFG_STR.get(k, default_iso)
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return _parse_iso_date(s) or date.today()

def _cfg_time(k, default="07:00:00"):
    s = CFG_STR.get(k, default)
    try:
        return datetime.fromisoformat(s).time()
    except Exception:
        try:
            return datetime.strptime(s, "%H:%M").time()
        except Exception:
            try:
                return datetime.strptime(s, "%H:%M:%S").time()
            except Exception:
                return time(7,0)

# ===== Meny =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik", "Inställningar"], index=0)

# =============================== STATISTIKVY (oförändrad logik) ================================
if view == "Statistik":
    st.header("📊 Statistik")
    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # --- Basmetrik ---
    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man = 0  # män + eskilstuna
    summa_for_snitt_scener = 0
    summa_privat_gb_kanner = 0

    total_svarta_sum = 0
    total_men_like_sum = 0  # män + eskilstuna + svarta

    for r in rows:
        man = _safe_int(r.get("Män", 0), 0) + _safe_int(r.get("Eskilstuna killar", 0), 0)
        esk = 0
        kanner = _safe_int(r.get("Känner", 0), 0)
        svarta = _safe_int(r.get("Svarta", 0), 0)

        men_like = man
        men_like_plus_black = man + svarta

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

    st.stop()

# ================================ Inställningar ===============================
if view == "Inställningar":
    st.header("⚙️ Inställningar (permanenta via fliken 'Inställningar')")

    startdatum = st.date_input("Historiskt startdatum", value=_cfg_date("STARTDATE", date.today().isoformat()))
    starttid   = st.time_input("Starttid", value=_cfg_time("STARTTIME"))
    födelsedatum = st.date_input(LABELS["BIRTHDATE"], value=_cfg_date("BIRTHDATE", "1990-01-01"))

    st.subheader("Maxvärden (Auto-Max med varning)")
    max_p  = st.number_input(f'{LABELS["PAPPAN"]} (max)', min_value=0, step=1, value=_cfg_int("MAX_PAPPAN", 10))
    max_g  = st.number_input(f'{LABELS["GRANNAR"]} (max)', min_value=0, step=1, value=_cfg_int("MAX_GRANNAR", 10))
    max_nv = st.number_input(f'{LABELS["NILS_VANNER"]} (max)', min_value=0, step=1, value=_cfg_int("MAX_NILS_VANNER", 10))
    max_nf = st.number_input(f'{LABELS["NILS_FAMILJ"]} (max)', min_value=0, step=1, value=_cfg_int("MAX_NILS_FAMILJ", 10))
    max_bk = st.number_input(f'{LABELS["BEKANTA"]} (max)', min_value=0, step=1, value=_cfg_int("MAX_BEKANTA", 10))

    st.subheader("Pris per prenumerant (gäller NÄSTA rad)")
    fee = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=_cfg_float("FEE_USD", 30.0))

    st.subheader("Etiketter")
    lbl_p  = st.text_input("Etikett – Pappans vänner", value=LABELS["PAPPAN"])
    lbl_g  = st.text_input("Etikett – Grannar", value=LABELS["GRANNAR"])
    lbl_nv = st.text_input("Etikett – Nils vänner", value=LABELS["NILS_VANNER"])
    lbl_nf = st.text_input("Etikett – Nils familj", value=LABELS["NILS_FAMILJ"])
    lbl_bk = st.text_input("Etikett – Bekanta", value=LABELS["BEKANTA"])
    lbl_es = st.text_input("Etikett – Eskilstuna killar", value=LABELS["ESKILSTUNA"])
    lbl_m  = st.text_input("Etikett – Män", value=LABELS["MEN"])
    lbl_bl = st.text_input("Etikett – Svarta", value=LABELS["BLACK"])
    lbl_bd = st.text_input("Etikett – Malins födelsedatum", value=LABELS["BIRTHDATE"])

    if st.button("💾 Spara inställningar"):
        d = _settings_as_dict()  # hämtar befintliga (inkl defaults)

        # Uppdatera values
        d["STARTDATE"]["Value"] = startdatum.isoformat()
        d["STARTTIME"]["Value"] = starttid.strftime("%H:%M:%S")
        d["BIRTHDATE"]["Value"] = födelsedatum.isoformat()
        d["FEE_USD"]["Value"]   = str(float(fee))

        d["MAX_PAPPAN"]["Value"] = str(int(max_p))
        d["MAX_GRANNAR"]["Value"] = str(int(max_g))
        d["MAX_NILS_VANNER"]["Value"] = str(int(max_nv))
        d["MAX_NILS_FAMILJ"]["Value"] = str(int(max_nf))
        d["MAX_BEKANTA"]["Value"] = str(int(max_bk))

        # Etiketter
        d["LABEL_PAPPAN"]["Label"] = lbl_p
        d["LABEL_GRANNAR"]["Label"] = lbl_g
        d["LABEL_NILS_VANNER"]["Label"] = lbl_nv
        d["LABEL_NILS_FAMILJ"]["Label"] = lbl_nf
        d["LABEL_BEKANTA"]["Label"] = lbl_bk
        d["LABEL_ESKILSTUNA"]["Label"] = lbl_es
        d["LABEL_MEN"]["Label"] = lbl_m
        d["LABEL_BLACK"]["Label"] = lbl_bl
        d["LABEL_BIRTHDATE"]["Label"] = lbl_bd

        _write_settings_dict(d)
        st.success("Inställningar sparade. Ladda om vyn Produktion/Statistik för att se etiketter.")
        st.stop()

# ================================ Produktion (visar inputs) ===============================
if view == "Produktion":
    # Läser in igen för att få senaste etiketter/values
    CFG_STR, LABELS = _load_cfg()

    # Initiera session max (för varningar/etiketter)
    st.session_state.setdefault("MAX_PAPPAN", _cfg_int("MAX_PAPPAN", 10))
    st.session_state.setdefault("MAX_GRANNAR", _cfg_int("MAX_GRANNAR", 10))
    st.session_state.setdefault("MAX_NILS_VANNER", _cfg_int("MAX_NILS_VANNER", 10))
    st.session_state.setdefault("MAX_NILS_FAMILJ", _cfg_int("MAX_NILS_FAMILJ", 10))
    st.session_state.setdefault("MAX_BEKANTA", _cfg_int("MAX_BEKANTA", 10))
    st.session_state.setdefault("FEE_USD", _cfg_float("FEE_USD", 30.0))

    def next_scene_number():
        try:
            vals = _retry_call(sheet.col_values, 1)  # Datum
            row_count = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
        except Exception:
            row_count = 0
        return row_count + 1

    def datum_och_veckodag_för_scen(nr: int):
        startdatum = _cfg_date("STARTDATE", date.today().isoformat())
        veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
        d = startdatum + timedelta(days=nr - 1)
        return d, veckodagar[d.weekday()]

    st.subheader("➕ Lägg till ny händelse")

    män_label = LABELS["MEN"]
    svarta_label = LABELS["BLACK"]
    män    = st.number_input(män_label,    min_value=0, step=1, value=0)
    svarta = st.number_input(svarta_label, min_value=0, step=1, value=0)
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

    lbl_p  = f'{LABELS["PAPPAN"]} (max {st.session_state.MAX_PAPPAN})'
    lbl_g  = f'{LABELS["GRANNAR"]} (max {st.session_state.MAX_GRANNAR})'
    lbl_nv = f'{LABELS["NILS_VANNER"]} (max {st.session_state.MAX_NILS_VANNER})'
    lbl_nf = f'{LABELS["NILS_FAMILJ"]} (max {st.session_state.MAX_NILS_FAMILJ})'
    lbl_bk = f'{LABELS["BEKANTA"]} (max {st.session_state.MAX_BEKANTA})'

    pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
    grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
    nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
    nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")
    bekanta        = st.number_input(lbl_bk, min_value=0, step=1, value=0, key="input_bekanta")

    eskilstuna_killar = st.number_input(LABELS["ESKILSTUNA"], min_value=0, step=1, value=0, key="input_eskilstuna")

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

    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    grund_preview = {
        "Typ": "",
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
        "Nils": nils,
        "Avgift": float(st.session_state["FEE_USD"]),
    }

    def _calc_preview(grund):
        try:
            if callable(calc_row_values):
                bd = _cfg_date("BIRTHDATE", "1990-01-01")
                stime = _cfg_time("STARTTIME", "07:00:00")
                return calc_row_values(grund, rad_datum, bd, stime)
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

    st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {_cfg_time('STARTTIME').strftime('%H:%M')})")

    # ===== Prenumeranter & Ekonomi (live) =====
    st.markdown("#### 📈 Prenumeranter & Ekonomi (live)")
    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
        st.metric("Avgift (rad)", _usd(preview.get("Avgift", _cfg_float("FEE_USD",30.0))))
    with ec2:
        st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
        st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
    with ec3:
        st.metric("Kostnad män", _usd(preview.get("Intäkt män", 0)))
        st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
    with ec4:
        st.metric("Intäkt Företaget", _usd(preview.get("Intäkt Företaget", 0)))
        st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

    # ============================== Spara ================================
    def _save_row(grund, rad_datum, veckodag):
        try:
            base = dict(grund)
            base.setdefault("Avgift", float(st.session_state["FEE_USD"]))
            bd = _cfg_date("BIRTHDATE", "1990-01-01")
            stime = _cfg_time("STARTTIME", "07:00:00")
            ber = calc_row_values(base, rad_datum, bd, stime)
            ber["Datum"] = rad_datum.isoformat()
        except Exception as e:
            st.error(f"Beräkningen misslyckades vid sparning: {e}")
            return

        row = [ber.get(col, "") for col in _retry_call(sheet.row_values,1)]
        _retry_call(sheet.append_row, row)
        st.success(f"✅ Rad sparad ({ber.get('Typ') or 'Händelse'}). Datum {rad_datum} ({veckodag}), Klockan {ber.get('Klockan','-')}")

    if st.button("💾 Spara raden"):
        _save_row(grund_preview, rad_datum, veckodag)

    # ============================== Snabbåtgärder (exempel: vila) ===============================
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

    if st.button("➕ Skapa 'Vila på jobbet'-rad"):
        try:
            scen_num = next_scene_number()
            rad_datum2, veckodag2 = datum_och_veckodag_för_scen(scen_num)

            pv = _rand_40_60_of_max(_cfg_int("MAX_PAPPAN", 0))
            gr = _rand_40_60_of_max(_cfg_int("MAX_GRANNAR", 0))
            nv = _rand_40_60_of_max(_cfg_int("MAX_NILS_VANNER", 0))
            nf = _rand_40_60_of_max(_cfg_int("MAX_NILS_FAMILJ", 0))
            bk = _rand_40_60_of_max(_cfg_int("MAX_BEKANTA", 0))
            esk = _rand_eskilstuna_20_40()

            grund_vila = {
                "Typ": "Vila på jobbet",
                "Veckodag": veckodag2, "Scen": scen_num,
                "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
                "Tid S": 0, "Tid D": 0, "Vila": 0,
                "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
                "Älskar": 12, "Sover med": 1,
                "Pappans vänner": pv, "Grannar": gr,
                "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
                "Nils": 0,
                "Avgift": float(st.session_state["FEE_USD"]),
            }
            _save_row(grund_vila, rad_datum2, veckodag2)
        except Exception as e:
            st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

    if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
        try:
            start_scene = next_scene_number()
            r = random.random()
            if r < 0.50:
                ones_count = 0
            elif r < 0.95:
                ones_count = 1
            else:
                ones_count = 2
            nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

            for offset in range(7):
                scen_num = start_scene + offset
                rad_d, veckod = datum_och_veckodag_för_scen(scen_num)

                if offset <= 4:
                    pv = _rand_40_60_of_max(_cfg_int("MAX_PAPPAN", 0))
                    gr = _rand_40_60_of_max(_cfg_int("MAX_GRANNAR", 0))
                    nv = _rand_40_60_of_max(_cfg_int("MAX_NILS_VANNER", 0))
                    nf = _rand_40_60_of_max(_cfg_int("MAX_NILS_FAMILJ", 0))
                    bk = _rand_40_60_of_max(_cfg_int("MAX_BEKANTA", 0))
                    esk = _rand_eskilstuna_20_40()
                else:
                    pv = gr = nv = nf = bk = 0
                    esk = _rand_eskilstuna_20_40()

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
                    "Nils": nils_val,
                    "Avgift": float(st.session_state["FEE_USD"]),
                }
                _save_row(grund_home, rad_d, veckod)

            st.success("✅ Skapade 7 'Vila i hemmet'-rader.")
        except Exception as e:
            st.error(f"Misslyckades att skapa 'Vila i hemmet': {e}")

    # ================================ Visa ================================
    st.subheader("📊 Aktuella data")
    try:
        rows = _retry_call(sheet.get_all_records)
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("Inga datarader ännu.")
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
