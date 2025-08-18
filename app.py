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

# Rerun: stabil variant med fallback
try:
    RERUN = st.rerun
except AttributeError:
    RERUN = st.experimental_rerun  # äldre Streamlit

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
    """Hämta ett blad; skapa endast om det inte finns."""
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
                # Nya UI-önskemål
                ["PROD_PARTICIPATION_PCT", "10", "Personal deltagit (% av PROD_STAFF)"],
                ["ESK_MIN", "20", "Eskilstuna killar – minintervall"],
                ["ESK_MAX", "40", "Eskilstuna killar – maxintervall"],

                # Bonusräknare
                ["BONUS_TOTAL", "0", "Bonus killar totalt"],
                ["BONUS_USED",  "0", "Bonus killar deltagit"],
                ["BONUS_LEFT",  "0", "Bonus killar kvar"],

                # Etikett-override
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

# OBS: Vi hämtar INTE header vid import/render längre!
sheet = _get_ws(WORKSHEET_TITLE)
settings_ws = _get_ws(SETTINGS_SHEET)

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

@st.cache_resource(show_spinner=False)
def get_or_create_header():
    """Hämtar/skapar header EN gång när vi verkligen behöver den (Spara/Statistik)."""
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
    rows = _retry_call(settings_ws.get_all_records)
    d, labels = {}, {}
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

    def _get(k, fallback): return CFG_RAW.get(k, fallback)

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
    C["MAX_PAPPAN"]      = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]     = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"] = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"] = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]     = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]      = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"]      = int(float(_get("PROD_STAFF", 800)))
    C["PROD_PARTICIPATION_PCT"] = float(_get("PROD_PARTICIPATION_PCT", 10))
    C["ESK_MIN"]         = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]         = int(float(_get("ESK_MAX", 40)))

    # Bonus
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# =============================== SIDOPANEL ===============================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    MIN_FOD   = date(1970, 1, 1)
    MIN_START = date(1990, 1, 1)
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
    prod_pct   = st.number_input("Personal deltagit – % av PROD_STAFF", min_value=0.0, max_value=100.0, step=0.5, value=float(CFG["PROD_PARTICIPATION_PCT"]))
    esk_min    = st.number_input("Eskilstuna killar – min", min_value=0, step=1, value=int(CFG["ESK_MIN"]))
    esk_max    = st.number_input("Eskilstuna killar – max", min_value=0, step=1, value=int(CFG["ESK_MAX"]))

    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    st.markdown("**Etiketter (påverkar endast visning)**")
    lab_fields = {
        "Pappans vänner":"Pappans vänner","Grannar":"Grannar",
        "Nils vänner":"Nils vänner","Nils familj":"Nils familj","Bekanta":"Bekanta",
        "Eskilstuna killar":"Eskilstuna killar","Män":"Män","Svarta":"Svarta","Känner":"Känner",
        "Personal deltagit":"Personal deltagit","Bonus killar":"Bonus killar","Bonus deltagit":"Bonus deltagit",
        "Malins födelsedatum":"Malins födelsedatum",
    }
    label_inputs = {}
    for k, default in lab_fields.items():
        label_inputs[k] = st.text_input(f"Etikett: {default}", value=_get_label(LABELS, default))

    if st.button("💾 Spara inställningar"):
        _save_setting("startdatum", startdatum.isoformat(), label=label_inputs["Malins födelsedatum"])
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", födelsedatum.isoformat())

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=label_inputs["Pappans vänner"])
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=label_inputs["Grannar"])
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=label_inputs["Nils vänner"])
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=label_inputs["Nils familj"])
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=label_inputs["Bekanta"])

        _save_setting("PROD_STAFF", str(int(prod_staff)))
        _save_setting("PROD_PARTICIPATION_PCT", str(float(prod_pct)))
        _save_setting("ESK_MIN", str(int(esk_min)))
        _save_setting("ESK_MAX", str(int(esk_max)))

        _save_setting("avgift_usd", str(float(avgift_input)))

        # label-only overrides
        _save_setting("LABEL_Eskilstuna killar", label_inputs["Eskilstuna killar"], label="")
        _save_setting("LABEL_Män", label_inputs["Män"], label="")
        _save_setting("LABEL_Svarta", label_inputs["Svarta"], label="")
        _save_setting("LABEL_Känner", label_inputs["Känner"], label="")
        _save_setting("LABEL_Personal deltagit", label_inputs["Personal deltagit"], label="")
        _save_setting("LABEL_Bonus killar", label_inputs["Bonus killar"], label="")
        _save_setting("LABEL_Bonus deltagit", label_inputs["Bonus deltagit"], label="")

        st.success("Inställningar & etiketter sparade ✅")
        RERUN()

# =============================== STATISTIKVY ===============================
if view == "Statistik":
    st.header("📊 Statistik")

    # Hämta/skapa header NU (inte vid varje render i Produktion)
    header = get_or_create_header()

    # Läs all data (OK i Statistik-vyn)
    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # ----- Bas-summeringar -----
    antal_scener = 0
    privat_gb_cnt = 0

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

    totalt_man_sum = 0
    bonus_deltagit_sum = 0
    personal_deltagit_sum = 0
    svarta_like_sum = 0
    tot_for_andel_svarta = 0

    for r in rows:
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

# ================================ PRODUKTION ================================
if view == "Produktion":
    st.header("🧪 Produktion – ny rad")

    # Hjälp: etiketter
    def _L(txt: str) -> str:
        return LABELS.get(txt, txt)

    # Radräkning: läs EN gång per session (inte varje render)
    if "ROW_COUNT" not in st.session_state:
        try:
            vals = _retry_call(sheet.col_values, 1)  # A-kolumn
            st.session_state.ROW_COUNT = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
        except Exception:
            st.session_state.ROW_COUNT = 0

    def next_scene_number():
        return st.session_state.ROW_COUNT + 1

    def datum_och_veckodag_för_scen(scen_nummer: int):
        d = CFG["startdatum"] + timedelta(days=scen_nummer - 1)
        veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
        return d, veckodagar[d.weekday()]

    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    # ===== EXACT ORDNING PÅ INPUT =====
    män    = st.number_input(_L("Män"),    min_value=0, step=1, value=0, key="in_män")
    svarta = st.number_input(_L("Svarta"), min_value=0, step=1, value=0, key="in_svarta")
    fitta  = st.number_input("Fitta",      min_value=0, step=1, value=0, key="in_fitta")
    rumpa  = st.number_input("Rumpa",      min_value=0, step=1, value=0, key="in_rumpa")
    dp     = st.number_input("DP",         min_value=0, step=1, value=0, key="in_dp")
    dpp    = st.number_input("DPP",        min_value=0, step=1, value=0, key="in_dpp")
    dap    = st.number_input("DAP",        min_value=0, step=1, value=0, key="in_dap")
    tap    = st.number_input("TAP",        min_value=0, step=1, value=0, key="in_tap")

    pappans_vänner = st.number_input(f"{_L('Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})",  min_value=0, step=1, value=0, key="in_pappan")
    grannar        = st.number_input(f"{_L('Grannar')} (max {int(CFG['MAX_GRANNAR'])})",        min_value=0, step=1, value=0, key="in_grannar")
    nils_vänner    = st.number_input(f"{_L('Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})",min_value=0, step=1, value=0, key="in_nils_vanner")
    nils_familj    = st.number_input(f"{_L('Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})",min_value=0, step=1, value=0, key="in_nils_familj")
    bekanta        = st.number_input(_L("Bekanta"), min_value=0, step=1, value=0, key="in_bekanta")
    eskilstuna_killar = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, value=0, key="in_esk")
    bonus_deltagit = st.number_input(_L("Bonus deltagit"), min_value=0, step=1, value=0, key="in_bonus_deltagit")
    personal_deltagit = st.number_input(_L("Personal deltagit"), min_value=0, step=1,
                                        value=int(round(CFG["PROD_STAFF"]*CFG["PROD_PARTICIPATION_PCT"]/100.0)),
                                        key="in_personal")

    älskar    = st.number_input("Älskar",                min_value=0, step=1, value=0, key="in_alskar")
    sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0, key="in_sover")

    tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=60, key="in_tid_s")
    tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=60, key="in_tid_d")
    vila   = st.number_input("Vila (sek)",  min_value=0, step=1, value=7,  key="in_vila")
    dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=60, key="in_dt_tid")
    dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=3,  key="in_dt_vila")

    avgift_val = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="in_avgift")

    # Max-varningar — endast visning (ingen skrivning)
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

    # Live-förhandsberäkning (enbart i minnet)
    grund_preview = {
        "Typ": "",
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
        "Bonus killar": 0, "Bonus deltagit": bonus_deltagit, "Personal deltagit": personal_deltagit,
        "Nils": 0,
        "Avgift": float(avgift_val),
    }

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

    # Ålder i live
    alder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month,rad_datum.day) < (CFG["födelsedatum"].month,CFG["födelsedatum"].day))
    st.markdown("---")
    st.subheader("🔎 Förhandsvisning (innan spar)")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
        st.metric("Ålder (Malin)", f"{alder} år")
        st.metric("Summa tid", preview.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
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
        st.metric("Avgift (rad)", _usd(preview.get("Avgift", avgift_val)))
    with ec2:
        st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
        st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
    with ec3:
        st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
        st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
    with ec4:
        st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

    # ======================= SPARA =======================
    def _save_row(grund, rad_datum, veckodag):
        # Hämta/skapa header först NU
        columns = get_or_create_header()
        try:
            base = dict(grund)
            base.setdefault("Avgift", float(CFG["avgift_usd"]))
            ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
            ber["Datum"] = rad_datum.isoformat()
        except Exception as e:
            st.error(f"Beräkningen misslyckades vid sparning: {e}")
            return

        row = [ber.get(col, "") for col in columns]
        _retry_call(sheet.append_row, row)
        st.session_state.ROW_COUNT += 1
        st.success(f"✅ Rad sparad ({ber.get('Typ','Händelse')}). Datum {rad_datum} ({veckodag}), Ålder {alder} år, Klockan {ber.get('Klockan','-')}")

    if st.button("💾 Spara raden"):
        _save_row(grund_preview, rad_datum, veckodag)

    # ======================= SCENARION (utan spar, endast fylla inputs) =======================
    st.markdown("---")
    st.subheader("🛠️ Snabbåtgärder (fyll inputs, ingen sparning)")

    def _esk_rand():
        lo, hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
        if lo > hi: lo, hi = hi, lo
        return random.randint(lo, hi) if hi >= lo else 0

    # För "Slumpa" behöver vi historikens min/max => hämta rader ENDAST vid knapptryck
    def _get_min_max(colname: str):
        try:
            rows = _retry_call(sheet.get_all_records)
        except Exception:
            return 0, 0
        vals = [_safe_int(r.get(colname, 0), 0) for r in rows]
        return (min(vals), max(vals)) if vals else (0, 0)

    cA, cB, cC = st.columns(3)
    with cA:
        if st.button("🎲 Slumpa scen vit"):
            st.session_state["in_män"] = random.randint(*_get_min_max("Män"))
            st.session_state["in_svarta"] = 0
            st.session_state["in_fitta"] = random.randint(*_get_min_max("Fitta"))
            st.session_state["in_rumpa"] = random.randint(*_get_min_max("Rumpa"))
            st.session_state["in_dp"] = random.randint(*_get_min_max("DP"))
            st.session_state["in_dpp"] = random.randint(*_get_min_max("DPP"))
            st.session_state["in_dap"] = random.randint(*_get_min_max("DAP"))
            st.session_state["in_tap"] = random.randint(*_get_min_max("TAP"))
            st.session_state["in_pappan"] = random.randint(*_get_min_max("Pappans vänner"))
            st.session_state["in_grannar"] = random.randint(*_get_min_max("Grannar"))
            st.session_state["in_nils_vanner"] = random.randint(*_get_min_max("Nils vänner"))
            st.session_state["in_nils_familj"] = random.randint(*_get_min_max("Nils familj"))
            st.session_state["in_bekanta"] = random.randint(*_get_min_max("Bekanta"))
            st.session_state["in_esk"] = _esk_rand()
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"] = 1
            st.session_state["in_personal"] = int(round(CFG["PROD_STAFF"]*CFG["PROD_PARTICIPATION_PCT"]/100.0))
            RERUN()
    with cB:
        if st.button("🎲 Slumpa scen svart"):
            # de andra källorna = 0
            st.session_state["in_män"] = 0
            st.session_state["in_pappan"] = 0
            st.session_state["in_grannar"] = 0
            st.session_state["in_nils_vanner"] = 0
            st.session_state["in_nils_familj"] = 0
            st.session_state["in_bekanta"] = 0
            st.session_state["in_esk"] = 0

            st.session_state["in_svarta"] = random.randint(*_get_min_max("Svarta"))
            st.session_state["in_fitta"]  = random.randint(*_get_min_max("Fitta"))
            st.session_state["in_rumpa"]  = random.randint(*_get_min_max("Rumpa"))
            st.session_state["in_dp"]     = random.randint(*_get_min_max("DP"))
            st.session_state["in_dpp"]    = random.randint(*_get_min_max("DPP"))
            st.session_state["in_dap"]    = random.randint(*_get_min_max("DAP"))
            st.session_state["in_tap"]    = random.randint(*_get_min_max("TAP"))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1
            st.session_state["in_personal"] = int(round(CFG["PROD_STAFF"]*CFG["PROD_PARTICIPATION_PCT"]/100.0))
            RERUN()
    with cC:
        if st.button("➕ Fyll 'Vila på jobbet' (utan spar)"):
            # 40–60% av max för källorna
            def _rand_40_60(mx): 
                mx = int(mx)
                lo, hi = int(round(mx*0.4)), int(round(mx*0.6))
                return random.randint(lo, max(lo, hi)) if mx>0 else 0

            st.session_state["in_män"] = 0
            st.session_state["in_svarta"] = 0
            st.session_state["in_fitta"] = 0
            st.session_state["in_rumpa"] = 0
            st.session_state["in_dp"] = 0
            st.session_state["in_dpp"] = 0
            st.session_state["in_dap"] = 0
            st.session_state["in_tap"] = 0

            st.session_state["in_pappan"] = _rand_40_60(CFG["MAX_PAPPAN"])
            st.session_state["in_grannar"] = _rand_40_60(CFG["MAX_GRANNAR"])
            st.session_state["in_nils_vanner"] = _rand_40_60(CFG["MAX_NILS_VANNER"])
            st.session_state["in_nils_familj"] = _rand_40_60(CFG["MAX_NILS_FAMILJ"])
            st.session_state["in_bekanta"] = _rand_40_60(CFG["MAX_BEKANTA"])
            st.session_state["in_esk"] = _esk_rand()

            st.session_state["in_alskar"] = 12
            st.session_state["in_sover"]  = 1
            st.session_state["in_personal"] = int(round(CFG["PROD_STAFF"]*CFG["PROD_PARTICIPATION_PCT"]/100.0))
            RERUN()

    # (Vila i hemmet genererar 7 dgr – vi kan fylla “dag 1” i inputs här om du vill, annars hoppar vi.)
