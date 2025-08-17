# ============================== app.py — DEL 1/4 ===============================
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

sheet = _get_ws(WORKSHEET_TITLE)
settings_ws = _get_ws(SETTINGS_SHEET)

# =========================== Header-säkring / migration =========================
# OBS: Vi tar bort "Intäkt Företaget" och "Kostnad män" ur vår schema, ersätter med "Utgift män".
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

    # Lägg till saknade kolumner men rör inte ev. extra gamla kolumner
    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        new_header = header + missing
        # Skriv endast första raden med nya rubriker
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

    # Bonus-räknare
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]
# ============================== SLUT PÅ DEL 1/4 ================================

# =============================== STATISTIKVY ================================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

if view == "Statistik":
    st.header("📊 Statistik")

    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # ----- Bas-summeringar -----
    antal_scener = 0
    privat_gb_cnt = 0

    # Vi använder kolumnen "Totalt Män" om den finns på raderna,
    # annars räknar vi on-the-fly (Män + Känner + Svarta + Bekanta + Eskilstuna + Bonus deltagit + Personal deltagit)
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

    # Andel svarta: Svarta + Bonus deltagit räknas som "svarta" (enligt senaste spec)
    svarta_like_sum = 0
    tot_for_andel_svarta = 0

    # Prenumeranter (total + 30-dagar)
    from datetime import timedelta as _td
    total_pren = 0
    cutoff = date.today() - _td(days=30)
    aktiva_pren = 0

    for r in rows:
        typ = (r.get("Typ") or "").strip()
        tot_men_row = _row_tot_men(r)

        # Antal scener / privat GB (scen = Totalt Män > 0)
        if tot_men_row > 0:
            antal_scener += 1
        elif _safe_int(r.get("Känner", 0), 0) > 0:
            privat_gb_cnt += 1

        totalt_man_sum += tot_men_row

        # Svarta + Bonus deltagit räknas i "svarta"
        svarta_like_sum += _safe_int(r.get("Svarta", 0), 0) + _safe_int(r.get("Bonus deltagit", 0), 0)
        tot_for_andel_svarta += max(0, tot_men_row)  # hela totalen

        bonus_deltagit_sum += _safe_int(r.get("Bonus deltagit", 0), 0)
        personal_deltagit_sum += _safe_int(r.get("Personal deltagit", 0), 0)

        # Prenumeranter (exkludera vila-typer)
        if typ not in ("Vila på jobbet", "Vila i hemmet"):
            total_pren += _safe_int(r.get("Prenumeranter", 0), 0)
            d = _parse_iso_date(r.get("Datum", ""))
            if d and d >= cutoff:
                aktiva_pren += _safe_int(r.get("Prenumeranter", 0), 0)

    andel_svarta_pct = round((svarta_like_sum / tot_for_andel_svarta) * 100, 2) if tot_for_andel_svarta > 0 else 0.0

    # ----- Visning basmetrik -----
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Antal scener", antal_scener)
    with c2: st.metric("Privat GB", privat_gb_cnt)
    with c3: st.metric("Totalt män (summa)", totalt_man_sum)
    with c4: st.metric("Andel svarta (%)", andel_svarta_pct)

    c5, c6 = st.columns(2)
    with c5: st.metric("Bonus killar (deltagit, sum)", bonus_deltagit_sum)
    with c6: st.metric("Personal (deltagit, sum)", personal_deltagit_sum)

    # ----- Prenumeranter -----
    st.markdown("---")
    st.subheader("👥 Prenumeranter")
    pc1, pc2 = st.columns(2)
    with pc1: st.metric("Prenumeranter (totalt)", int(total_pren))
    with pc2: st.metric("Aktiva prenumeranter (30 dagar)", int(aktiva_pren))

    # ----- DP/DPP/DAP/TAP summering & snitt per scen -----
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

# ================================ PRODUKTIONSVY ================================
if view == "Produktion":
    st.header("🧪 Produktion – ny rad")

    # ---------- Hjälp: etikett-funktion ----------
    def _L(txt: str) -> str:
        return LABELS.get(txt, txt)

    # ---------- Radräkning / datum ----------
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

    scen = next_scene_number()
    rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

    # ---------- Inmatning ----------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        män    = st.number_input(_L("Män"),    min_value=0, step=1, value=0, key="in_man")
        fitta  = st.number_input("Fitta",  min_value=0, step=1, value=0, key="in_fitta")
        dp     = st.number_input("DP",     min_value=0, step=1, value=0, key="in_dp")
        dap    = st.number_input("DAP",    min_value=0, step=1, value=0, key="in_dap")
    with c2:
        svarta = st.number_input(_L("Svarta"), min_value=0, step=1, value=0, key="in_svarta")
        rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=0, key="in_rumpa")
        dpp    = st.number_input("DPP",    min_value=0, step=1, value=0, key="in_dpp")
        tap    = st.number_input("TAP",    min_value=0, step=1, value=0, key="in_tap")
    with c3:
        tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=60, key="in_tid_s")
        tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=60, key="in_tid_d")
        vila   = st.number_input("Vila (sek)",  min_value=0, step=1, value=7, key="in_vila")
        dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=60, key="in_dt_tid")
    with c4:
        dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=3, key="in_dt_vila")
        älskar    = st.number_input("Älskar",                min_value=0, step=1, value=0, key="in_alskar")
        sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0, key="in_sover")

    lbl_p  = f"{_L('Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
    lbl_g  = f"{_L('Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
    lbl_nv = f"{_L('Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
    lbl_nf = f"{_L('Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
    lbl_bk = f"{_L('Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

    c5, c6, c7 = st.columns(3)
    with c5:
        pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
        grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
        nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
        nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")
    with c6:
        bekanta        = st.number_input(_L("Bekanta"),        min_value=0, step=1, value=0, key="input_bekanta")
        eskilstuna_killar = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, value=0, key="input_eskilstuna")
        bonus_killar      = st.number_input(_L("Bonus killar"), min_value=0, step=1, value=0, key="input_bonus_killar")
        bonus_deltagit    = st.number_input(_L("Bonus deltagit"), min_value=0, step=1, value=0, key="input_bonus_deltagit")
    with c7:
        personal_deltagit = st.number_input(_L("Personal deltagit"), min_value=0, step=1, value=80, key="input_personal_deltagit")
        nils = st.number_input("Nils", min_value=0, step=1, value=0, key="in_nils")
        avgift_val = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="in_avgift")

    # ---------- Max-varningar (endast visning) ----------
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

    # ---------- Live-förhandsberäkning (enbart i minnet) ----------
    grund_preview = {
        "Typ": "",
        "Veckodag": veckodag, "Scen": scen,
        "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Pappans vänner": pappans_vänner, "Grannar": grannar,
        "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
        "Bonus killar": bonus_killar, "Bonus deltagit": bonus_deltagit, "Personal deltagit": personal_deltagit,
        "Nils": nils,
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
        st.metric("Avgift (rad)", _usd(preview.get("Avgift", avgift_val)))
    with ec2:
        st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
        st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
    with ec3:
        st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
        st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
    with ec4:
        st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

    # ---------- Spara / Auto-Max ----------
    def _store_pending(grund, scen, rad_datum, veckodag, over_max):
        st.session_state["PENDING_SAVE"] = {
            "grund": grund,
            "scen": scen,
            "rad_datum": str(rad_datum),
            "veckodag": veckodag,
            "over_max": over_max
        }

    def _parse_date_for_save(d):
        return d if isinstance(d, date) else datetime.strptime(d, "%Y-%m-%d").date()

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
        st.session_state.ROW_COUNT += 1

        ålder = rad_datum.year - CFG["födelsedatum"].year - (
            (rad_datum.month,rad_datum.day) < (CFG["födelsedatum"].month,CFG["födelsedatum"].day)
        )
        typ_label = ber.get("Typ") or "Händelse"
        st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")

    def _apply_auto_max_and_save(pending):
        for _, info in pending["over_max"].items():
            key = info["max_key"]
            new_val = int(info["new_value"])
            _save_setting(key, str(new_val))
            CFG[key] = new_val
        grund = pending["grund"]
        _save_row(grund, _parse_date_for_save(pending["rad_datum"]), pending["veckodag"])

    save_clicked = st.button("💾 Spara raden")
    if save_clicked:
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

    # Auto-Max dialog
    if "PENDING_SAVE" in st.session_state:
        pending = st.session_state["PENDING_SAVE"]
        st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara raden?")
        for f, info in pending["over_max"].items():
            st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")

        cA, cB = st.columns(2)
        with cA:
            if st.button("✅ Ja, uppdatera max och spara"):
                try:
                    _apply_auto_max_and_save(pending)
                except Exception as e:
                    st.error(f"Kun­de inte spara: {e}")
                finally:
                    st.session_state.pop("PENDING_SAVE", None)
                    st.rerun()
        with cB:
            if st.button("✋ Nej, avbryt"):
                st.session_state.pop("PENDING_SAVE", None)
                st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

    # ---------- Snabbåtgärder ----------
    st.markdown("---")
    st.subheader("🛠️ Snabbåtgärder")

    def _rand_40_60_of_max(mx: int) -> int:
        try: mx = int(mx)
        except Exception: mx = 0
        if mx <= 0: return 0
        lo = max(0, int(round(mx * 0.40)))
        hi = max(lo, int(round(mx * 0.60)))
        return random.randint(lo, hi)

    def _rand_eskilstuna_20_40() -> int:
        r = random.random()
        return random.randint(20, 30) if r < 0.30 else random.randint(31, 40)

    def _get_min_max(colname: str):
        try:
            all_rows = _retry_call(sheet.get_all_records)
        except Exception:
            return 0, 0
        vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
        if not vals:
            return 0, 0
        return min(vals), max(vals)

    # Slumpa scen vit
    if st.button("🎲 Slumpa scen vit"):
        st.session_state["in_man"] = random.randint(*_get_min_max("Män"))
        st.session_state["in_fitta"] = random.randint(*_get_min_max("Fitta"))
        st.session_state["in_rumpa"] = random.randint(*_get_min_max("Rumpa"))
        st.session_state["in_dp"] = random.randint(*_get_min_max("DP"))
        st.session_state["in_dpp"] = random.randint(*_get_min_max("DPP"))
        st.session_state["in_dap"] = random.randint(*_get_min_max("DAP"))
        st.session_state["in_tap"] = random.randint(*_get_min_max("TAP"))
        st.session_state["input_pappan"] = random.randint(*_get_min_max("Pappans vänner"))
        st.session_state["input_grannar"] = random.randint(*_get_min_max("Grannar"))
        st.session_state["input_nils_vanner"] = random.randint(*_get_min_max("Nils vänner"))
        st.session_state["input_nils_familj"] = random.randint(*_get_min_max("Nils familj"))
        st.session_state["input_bekanta"] = random.randint(*_get_min_max("Bekanta"))
        st.session_state["input_eskilstuna"] = random.randint(*_get_min_max("Eskilstuna killar"))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"] = 1
        st.session_state["input_personal_deltagit"] = 80
        st.experimental_rerun()

    # Slumpa scen svart (övriga källor 0, personal 80)
    if st.button("🎲 Slumpa scen svart"):
        st.session_state["in_fitta"] = random.randint(*_get_min_max("Fitta"))
        st.session_state["in_rumpa"] = random.randint(*_get_min_max("Rumpa"))
        st.session_state["in_dp"] = random.randint(*_get_min_max("DP"))
        st.session_state["in_dpp"] = random.randint(*_get_min_max("DPP"))
        st.session_state["in_dap"] = random.randint(*_get_min_max("DAP"))
        st.session_state["in_tap"] = random.randint(*_get_min_max("TAP"))
        st.session_state["in_svarta"] = random.randint(*_get_min_max("Svarta"))
        # Nollställ källor
        st.session_state["in_man"] = 0
        st.session_state["input_pappan"] = 0
        st.session_state["input_grannar"] = 0
        st.session_state["input_nils_vanner"] = 0
        st.session_state["input_nils_familj"] = 0
        st.session_state["input_bekanta"] = 0
        st.session_state["input_eskilstuna"] = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"] = 1
        st.session_state["input_personal_deltagit"] = 80
        # Bonus deltagit sätts separat i beräkningen men kan lämnas ifred här
        st.experimental_rerun()

    # Vila på jobbet (personal 80)
    if st.button("➕ Skapa 'Vila på jobbet'-rad"):
        try:
            scen_num = next_scene_number()
            rd2, vd2 = datum_och_veckodag_för_scen(scen_num)
            pv = _rand_40_60_of_max(int(CFG.get("MAX_PAPPAN", 0)))
            gr = _rand_40_60_of_max(int(CFG.get("MAX_GRANNAR", 0)))
            nv = _rand_40_60_of_max(int(CFG.get("MAX_NILS_VANNER", 0)))
            nf = _rand_40_60_of_max(int(CFG.get("MAX_NILS_FAMILJ", 0)))
            bk = _rand_40_60_of_max(int(CFG.get("MAX_BEKANTA", 0)))
            esk = _rand_eskilstuna_20_40()

            base = {
                "Typ": "Vila på jobbet",
                "Veckodag": vd2, "Scen": scen_num,
                "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
                "Tid S": 0, "Tid D": 0, "Vila": 0,
                "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
                "Älskar": 12, "Sover med": 1,
                "Pappans vänner": pv, "Grannar": gr,
                "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
                "Bonus killar": 0, "Bonus deltagit": 0,  # sätts av beräkningar vid behov
                "Personal deltagit": 80,
                "Nils": 0,
                "Avgift": float(CFG.get("avgift_usd", 30.0)),
            }
            _save_row(base, rd2, vd2)
        except Exception as e:
            st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

    # Vila i hemmet (7 dagar) – personal 80 på dag1–5, 0 på dag6–7
    if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
        try:
            start_scene = next_scene_number()

            # Nils 50/45/5 (antal ettor dag 1–6)
            r = random.random()
            if r < 0.50: ones_count = 0
            elif r < 0.95: ones_count = 1
            else: ones_count = 2
            nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

            for offset in range(7):
                scen_num = start_scene + offset
                rd, vd = datum_och_veckodag_för_scen(scen_num)

                if offset <= 4:
                    pv = _rand_40_60_of_max(int(CFG.get("MAX_PAPPAN", 0)))
                    gr = _rand_40_60_of_max(int(CFG.get("MAX_GRANNAR", 0)))
                    nv = _rand_40_60_of_max(int(CFG.get("MAX_NILS_VANNER", 0)))
                    nf = _rand_40_60_of_max(int(CFG.get("MAX_NILS_FAMILJ", 0)))
                    bk = _rand_40_60_of_max(int(CFG.get("MAX_BEKANTA", 0)))
                    esk = _rand_eskilstuna_20_40()
                    pers = 80
                else:
                    pv = gr = nv = nf = bk = 0
                    esk = _rand_eskilstuna_20_40()
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
                }
                _save_row(base, rd, vd)

            st.success("✅ Skapade 7 'Vila i hemmet'-rader.")
        except Exception as e:
            st.error(f"Misslyckades att skapa 'Vila i hemmet': {e}")

    # ---------- Visa & radera ----------
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
