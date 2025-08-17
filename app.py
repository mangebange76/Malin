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
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        if title == SETTINGS_SHEET:
            ws = spreadsheet.add_worksheet(title=SETTINGS_SHEET, rows=200, cols=3)
            _retry_call(ws.update, "A1:C1", [["Key","Value","Label"]])
            # Seed defaults (only first time)
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
                # Bonus counters (persistent)
                ["BONUS_TOTAL", "0", "Bonus killar totalt"],
                ["BONUS_USED", "0", "Bonus killar deltagit"],
                ["BONUS_LEFT", "0", "Bonus killar kvar"],
                # Labels for data columns (optional overrides)
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
        else:
            ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=60)
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
    "Intäkt män","Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst",
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
        # Correct A1 range for updating header
        import gspread
        last = gspread.utils.rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{last}", [new_header])
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
KOLUMNER = st.session_state["COLUMNS"]

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    vals = _retry_call(settings_ws.get_all_records)  # columns Key, Value, Label
    d = {}
    labels = {}
    for r in vals:
        key = (r.get("Key") or "").strip()
        if not key:
            continue
        val = r.get("Value")
        lab = r.get("Label")
        d[key] = val
        if lab is not None and str(lab).strip():
            labels[key] = str(lab).strip()
        # Also collect LABEL_* entries as mapping to column names
        if key.startswith("LABEL_"):
            colname = key[len("LABEL_"):]
            if str(val or "").strip():
                labels[colname] = str(val).strip()
    return d, labels

def _save_setting(key: str, value: str, label: str|None=None):
    recs = _retry_call(settings_ws.get_all_records)
    keys = [ (r.get("Key") or "") for r in recs ]
    try:
        idx = keys.index(key)  # 0-based within data (A2..)
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
    # dates/times
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
    # integers/floats
    C["MAX_PAPPAN"] = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"] = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"] = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"] = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"] = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"] = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"] = int(float(_get("PROD_STAFF", 800)))
    # Bonus counters
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ===== Meny =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# ---- Cache-a läsning av alla rader för att minska lagg ----
@st.cache_data(ttl=30, show_spinner=False)
def _get_all_rows_cached():
    try:
        return _retry_call(sheet.get_all_records)
    except Exception:
        return []

# =============================== STATISTIKVY ================================
if view == "Statistik":
    st.header("📊 Statistik")

    try:
        rows = _get_all_rows_cached()
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # Basmetrik
    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man = 0  # inkluderar Män + Eskilstuna killar
    summa_for_snitt_scener = 0
    summa_privat_gb_kanner = 0

    total_svarta_sum = 0
    total_men_like_sum = 0  # män + eskilstuna + svarta (för andel svarta)
    bonus_deltagit_sum = 0
    personal_deltagit_sum = 0

    for r in rows:
        man = _safe_int(r.get("Män", 0), 0)
        esk = _safe_int(r.get("Eskilstuna killar", 0), 0)
        kanner = _safe_int(r.get("Känner", 0), 0)
        svarta = _safe_int(r.get("Svarta", 0), 0)
        bd = _safe_int(r.get("Bonus deltagit", 0), 0)
        pd = _safe_int(r.get("Personal deltagit", 0), 0)

        if (man + esk) > 0:
            antal_scener += 1
            totalt_man += (man + esk)
            summa_for_snitt_scener += (man + esk + kanner)

        if (man + esk) == 0 and kanner > 0:
            privat_gb_cnt += 1
            summa_privat_gb_kanner += kanner

        total_svarta_sum += svarta
        total_men_like_sum += (man + esk + svarta)
        bonus_deltagit_sum += bd
        personal_deltagit_sum += pd

    snitt_scener = round(summa_for_snitt_scener / antal_scener, 2) if antal_scener > 0 else 0.0
    snitt_privat_gb = round(summa_privat_gb_kanner / privat_gb_cnt, 2) if privat_gb_cnt > 0 else 0.0
    andel_svarta_pct = round((total_svarta_sum / total_men_like_sum) * 100, 2) if total_men_like_sum > 0 else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Antal scener", antal_scener)
    with c2: st.metric("Privat GB", privat_gb_cnt)
    with c3: st.metric("Totalt antal män", totalt_man)  # män + eskilstuna
    with c4: st.metric("Snitt scener", snitt_scener)
    with c5: st.metric("Snitt Privat GB", snitt_privat_gb)
    st.metric("Andel svarta av män (%)", andel_svarta_pct)
    st.metric("Bonus killar (deltagit)", bonus_deltagit_sum)
    st.metric("Personal (deltagit)", personal_deltagit_sum)

    # Snitt relativt max per källa + Totalt antal tillfällen
    max_p  = int(CFG["MAX_PAPPAN"])
    max_g  = int(CFG["MAX_GRANNAR"])
    max_nv = int(CFG["MAX_NILS_VANNER"])
    max_nf = int(CFG["MAX_NILS_FAMILJ"])

    pv_sum = sum(_safe_int(r.get("Pappans vänner", 0), 0) for r in rows)
    gr_sum = sum(_safe_int(r.get("Grannar", 0), 0) for r in rows)
    nv_sum = sum(_safe_int(r.get("Nils vänner", 0), 0) for r in rows)
    nf_sum = sum(_safe_int(r.get("Nils familj", 0), 0) for r in rows)

    pv_avg_rel = round(pv_sum / max_p, 2) if max_p > 0 else 0.0
    gr_avg_rel = round(gr_sum / max_g, 2) if max_g > 0 else 0.0
    nv_avg_rel = round(nv_sum / max_nv, 2) if max_nv > 0 else 0.0
    nf_avg_rel = round(nf_sum / max_nf, 2) if max_nf > 0 else 0.0

    alskar_sum_stat = sum(_safe_int(r.get("Älskar", 0), 0) for r in rows)
    sover_sum_stat  = sum(_safe_int(r.get("Sover med", 0), 0) for r in rows)

    denom_alskar = max_p + max_g + max_nv + max_nf
    snitt_alskar = round(alskar_sum_stat / denom_alskar, 2) if denom_alskar > 0 else 0.0
    snitt_sover  = round(sover_sum_stat / max_nf, 2) if max_nf > 0 else 0.0

    pv_tot_tillf = round(pv_avg_rel + snitt_alskar, 2)
    gr_tot_tillf = round(gr_avg_rel + snitt_alskar, 2)
    nv_tot_tillf = round(nv_avg_rel + snitt_alskar, 2)
    nf_tot_tillf = round(nf_avg_rel + snitt_alskar + snitt_sover, 2)

    st.markdown("---")
    st.subheader("📐 Snitt (rel. max) + Totalt antal tillfällen")
    cA, cB = st.columns(2)
    with cA:
        st.markdown(f"**{_get_label(LABELS, 'Pappans vänner')}**")
        st.metric("Snitt (rel. max)", pv_avg_rel)
        st.metric("Totalt antal tillfällen", pv_tot_tillf)

        st.markdown(f"**{_get_label(LABELS, 'Grannar')}**")
        st.metric("Snitt (rel. max)", gr_avg_rel)
        st.metric("Totalt antal tillfällen", gr_tot_tillf)
    with cB:
        st.markdown(f"**{_get_label(LABELS, 'Nils vänner')}**")
        st.metric("Snitt (rel. max)", nv_avg_rel)
        st.metric("Totalt antal tillfällen", nv_tot_tillf)

        st.markdown(f"**{_get_label(LABELS, 'Nils familj')}**")
        st.metric("Snitt (rel. max)", nf_avg_rel)
        st.metric("Totalt antal tillfällen", nf_tot_tillf)

    # Prenumeranter
    from datetime import timedelta as _td
    total_pren = 0
    for r in rows:
        typ = (r.get("Typ") or "").strip()
        if typ in ("Vila på jobbet", "Vila i hemmet"):
            continue
        total_pren += _safe_int(r.get("Prenumeranter", 0), 0)

    cutoff = date.today() - _td(days=30)
    aktiva_pren = 0
    for r in rows:
        typ = (r.get("Typ") or "").strip()
        if typ in ("Vila på jobbet", "Vila i hemmet"):
            continue
        d = _parse_iso_date(r.get("Datum", ""))
        if not d or d < cutoff:
            continue
        aktiva_pren += _safe_int(r.get("Prenumeranter", 0), 0)

    st.markdown("---")
    st.subheader("👥 Prenumeranter")
    pc1, pc2 = st.columns(2)
    with pc1: st.metric("Prenumeranter (totalt)", int(total_pren))
    with pc2: st.metric("Aktiva prenumeranter (30 dagar)", int(aktiva_pren))

    # Ekonomi (oförändrad tills vidare)
    total_intakt_kanner = sum(_safe_int(r.get("Intäkt Känner", 0), 0) for r in rows)
    total_intakt_foretag = sum(_safe_int(r.get("Intäkt Företaget", 0), 0) for r in rows)
    total_vinst = sum(_safe_int(r.get("Vinst", 0), 0) for r in rows)
    total_lon_malin = sum(_safe_int(r.get("Lön Malin", 0), 0) for r in rows)

    st.markdown("---")
    st.subheader("💰 Ekonomi (totalt)")
    ec1, ec2 = st.columns(2)
    with ec1: st.metric("Intäkt känner (totalt)", f"{round(total_intakt_kanner, 2)} USD")
    with ec2: st.metric("Intäkt företag (totalt)", f"{round(total_intakt_foretag, 2)} USD")
    ec3, ec4 = st.columns(2)
    with ec3: st.metric("Vinst (totalt)", f"{round(total_vinst, 2)} USD")
    with ec4: st.metric("Lön Malin (totalt)", f"{round(total_lon_malin, 2)} USD")

    sum_max = int(CFG["MAX_PAPPAN"]) + int(CFG["MAX_GRANNAR"]) + int(CFG["MAX_NILS_VANNER"]) + int(CFG["MAX_NILS_FAMILJ"])
    snitt_intakt_kanner = (total_intakt_kanner + total_intakt_foretag + total_vinst) / sum_max if sum_max > 0 else 0.0
    st.metric("Snitt intäkt känner", f"{snitt_intakt_kanner:.2f} USD")

    alskar_sum_all = sum(_safe_int(r.get("Älskar", 0), 0) for r in rows)
    sover_sum_all  = sum(_safe_int(r.get("Sover med", 0), 0) for r in rows)
    divisor_snitt_lon = (totalt_man + alskar_sum_all + sover_sum_all)
    snitt_lon = (total_intakt_kanner + total_intakt_foretag + total_vinst) / divisor_snitt_lon if divisor_snitt_lon > 0 else 0.0
    st.metric("Snitt lön", f"{snitt_lon:.2f} USD")

    # DP/DPP/DAP/TAP
    st.markdown("---")
    st.subheader("🔩 DP / DPP / DAP / TAP — summa & snitt")
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

    # Älskar / Sover med + Nils-summa + per dag
    st.markdown("---")
    st.subheader("💗 Älskar / 😴 Sover med — summa & snitt (plus Nils-summa)")
    alskar_sum = alskar_sum_all
    sover_sum  = sover_sum_all
    nils_sum   = sum(_safe_int(r.get("Nils", 0)) for r in rows)

    denom_alskar2 = (int(CFG["MAX_PAPPAN"]) + int(CFG["MAX_GRANNAR"]) + int(CFG["MAX_NILS_VANNER"]) + int(CFG["MAX_NILS_FAMILJ"]))
    snitt_alskar2 = round(alskar_sum / denom_alskar2, 2) if denom_alskar2 > 0 else 0.0
    snitt_sover2  = round(sover_sum / int(CFG["MAX_NILS_FAMILJ"]), 2) if int(CFG["MAX_NILS_FAMILJ"]) > 0 else 0.0

    c_als1, c_als2, c_sov1, c_sov2 = st.columns(4)
    with c_als1: st.metric("Summa Älskar", alskar_sum)
    with c_als2: st.metric("Snitt Älskar", snitt_alskar2)
    with c_sov1: st.metric("Summa Sover med", sover_sum)
    with c_sov2: st.metric("Snitt Sover med", snitt_sover2)
    st.metric("Nils (summa)", nils_sum)

    # Per dag
    total_rows = len(rows)
    alskar_per_dag = (alskar_sum / total_rows) if total_rows > 0 else 0.0
    sover_per_dag  = (sover_sum / total_rows) if total_rows > 0 else 0.0
    d1, d2 = st.columns(2)
    with d1: st.metric("Älskar / dag", f"{alskar_per_dag:.2f}")
    with d2: st.metric("Sover med / dag", f"{sover_per_dag:.2f}")

    # Snitt tid kille / scen
    st.markdown("---")
    st.subheader("⏱️ Tid per kille / scen")
    tpk_total_sec = sum(_safe_int(r.get("Tid per kille (sek)", 0)) for r in rows if (_safe_int(r.get("Män", 0)) + _safe_int(r.get("Eskilstuna killar", 0))) > 0)
    tpk_avg_sec = int(round(tpk_total_sec / denom_scen)) if antal_scener > 0 else 0
    tpk_avg_label = _ms_str_from_seconds(tpk_avg_sec)
    st.metric("Snitt tid kille / scen", tpk_avg_label)

    # Snitt tid (h) per scen exkl. älskar & sover med
    total_sec_scen = sum(
        _safe_int(r.get("Summa tid (sek)", 0), 0)
        for r in rows if (_safe_int(r.get("Män", 0)) + _safe_int(r.get("Eskilstuna killar", 0))) > 0
    )
    alskar_sec_scen = sum(
        _safe_int(r.get("Tid Älskar (sek)", 0), 0)
        for r in rows if (_safe_int(r.get("Män", 0)) + _safe_int(r.get("Eskilstuna killar", 0))) > 0
    )
    sover_sec_scen = sum(
        _safe_int(r.get("Tid Sover med (sek)", 0), 0)
        for r in rows if (_safe_int(r.get("Män", 0)) + _safe_int(r.get("Eskilstuna killar", 0))) > 0
    )
    justerad_sec = max(0, total_sec_scen - alskar_sec_scen - sover_sec_scen)
    snitt_tid_h_utan_extra = (justerad_sec / 3600.0 / antal_scener) if antal_scener > 0 else 0.0
    st.session_state["SNITT_TID_H_UTAN_ALSKAR_SOVER"] = snitt_tid_h_utan_extra
    st.metric("Snitt tid (h) per scen – exkl. älskar & sover med", f"{snitt_tid_h_utan_extra:.2f} h")

    st.stop()

# ================================ Sidopanel (Produktion) ====================================
st.sidebar.header("Inställningar")

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
    lab_p  = st.text_input("Etikett: Pappans vänner", value=_get_label(LABELS, "Pappans vänner"))
    lab_g  = st.text_input("Etikett: Grannar", value=_get_label(LABELS, "Grannar"))
    lab_nv = st.text_input("Etikett: Nils vänner", value=_get_label(LABELS, "Nils vänner"))
    lab_nf = st.text_input("Etikett: Nils familj", value=_get_label(LABELS, "Nils familj"))
    lab_bk = st.text_input("Etikett: Bekanta", value=_get_label(LABELS, "Bekanta"))
    lab_esk= st.text_input("Etikett: Eskilstuna killar", value=_get_label(LABELS, "Eskilstuna killar"))
    lab_man= st.text_input("Etikett: Män", value=_get_label(LABELS, "Män"))
    lab_sva= st.text_input("Etikett: Svarta", value=_get_label(LABELS, "Svarta"))
    lab_kann=st.text_input("Etikett: Känner", value=_get_label(LABELS, "Känner"))
    lab_person=st.text_input("Etikett: Personal deltagit", value=_get_label(LABELS, "Personal deltagit"))
    lab_bonus =st.text_input("Etikett: Bonus killar", value=_get_label(LABELS, "Bonus killar"))
    lab_bonusd=st.text_input("Etikett: Bonus deltagit", value=_get_label(LABELS, "Bonus deltagit"))
    lab_mfd   = st.text_input("Etikett: Malins födelsedatum", value=_get_label(LABELS, "Malins födelsedatum"))

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

        # label-only overrides
        _save_setting("LABEL_Eskilstuna killar", lab_esk, label="")
        _save_setting("LABEL_Män", lab_man, label="")
        _save_setting("LABEL_Svarta", lab_sva, label="")
        _save_setting("LABEL_Känner", lab_kann, label="")
        _save_setting("LABEL_Personal deltagit", lab_person, label="")
        _save_setting("LABEL_Bonus killar", lab_bonus, label="")
        _save_setting("LABEL_Bonus deltagit", lab_bonusd, label="")
        _save_setting("LABEL_Malins födelsedatum", lab_mfd, label="")

        st.success("Inställningar och etiketter sparade ✅")
        st.rerun()

# ===== 30 dagar (rullande) i sidopanelen =====
st.sidebar.subheader("📆 30 dagar (rullande)")
try:
    all_rows = _get_all_rows_cached()
    cutoff = date.today() - timedelta(days=30)
    active_subs = 0.0
    active_rev = 0.0
    for r in all_rows:
        typ = (r.get("Typ") or "").strip()
        if typ in ("Vila på jobbet", "Vila i hemmet"):
            continue  # exkludera helt
        d = _parse_iso_date(r.get("Datum", ""))
        if not d or d < cutoff:
            continue
        subs = float(r.get("Prenumeranter", 0) or 0)
        fee  = float(r.get("Avgift", CFG["avgift_usd"]) or 0)
        active_subs += subs
        active_rev  += subs * fee
    st.sidebar.metric("Aktiva prenumeranter", int(active_subs))
    st.sidebar.metric("Intäkter (30 dagar)", f"${active_rev:,.2f}")
except Exception as e:
    st.sidebar.warning(f"Kunde inte räkna 30-dagars: {e}")

# ============================== Radräkning / Scen ==============================
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

# ============================ Inmatning (live-fält) ============================
st.subheader("➕ Lägg till ny händelse")

# förifyll 10% personal
def _suggest_personal_deltagit():
    return max(0, int(round(int(CFG.get("PROD_STAFF", 0)) * 0.10)))

# Inputs med stabila keys så vi kan sätta via session_state (slumpknappar)
män    = st.number_input(_get_label(LABELS, "Män"),    min_value=0, step=1, value=0, key="in_man")
svarta = st.number_input(_get_label(LABELS, "Svarta"), min_value=0, step=1, value=0, key="in_svarta")
fitta  = st.number_input("Fitta",  min_value=0, step=1, value=0, key="in_fitta")
rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=0, key="in_rumpa")
dp     = st.number_input("DP",     min_value=0, step=1, value=0, key="in_dp")
dpp    = st.number_input("DPP",    min_value=0, step=1, value=0, key="in_dpp")
dap    = st.number_input("DAP",    min_value=0, step=1, value=0, key="in_dap")
tap    = st.number_input("TAP",    min_value=0, step=1, value=0, key="in_tap")

tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=60, key="in_tid_s")
tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=60, key="in_tid_d")
vila   = st.number_input("Vila (sek)",  min_value=0, step=1, value=7, key="in_vila")

dt_tid  = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=60, key="in_dt_tid")
dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=3, key="in_dt_vila")

älskar    = st.number_input("Älskar",                min_value=0, step=1, value=0, key="in_alskar")
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0, key="in_sover")

lbl_p  = f"{_get_label(LABELS, 'Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
lbl_g  = f"{_get_label(LABELS, 'Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
lbl_nv = f"{_get_label(LABELS, 'Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
lbl_nf = f"{_get_label(LABELS, 'Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
lbl_bk = f"{_get_label(LABELS, 'Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")
bekanta        = st.number_input(lbl_bk, min_value=0, step=1, value=0, key="input_bekanta")

eskilstuna_killar = st.number_input(_get_label(LABELS, "Eskilstuna killar"), min_value=0, step=1, value=0, key="input_eskilstuna")
bonus_killar      = st.number_input(_get_label(LABELS, "Bonus killar"), min_value=0, step=1, value=0, key="input_bonus_killar")
bonus_deltagit    = st.number_input(_get_label(LABELS, "Bonus deltagit"), min_value=0, step=1, value=0, key="input_bonus_deltagit")
# förifyll 10% personal här
_default_personal = _suggest_personal_deltagit()
if st.session_state.get("input_personal_deltagit", None) is None:
    st.session_state["input_personal_deltagit"] = _default_personal
personal_deltagit = st.number_input(_get_label(LABELS, "Personal deltagit"), min_value=0, step=1, value=st.session_state["input_personal_deltagit"], key="input_personal_deltagit")

nils = st.number_input("Nils", min_value=0, step=1, value=0, key="in_nils")

# Varningsflaggor (gäller max för källorna)
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

# ============================ Live-förhandsberäkning ===========================
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

grund_preview = {
    "Typ": "",
    "Veckodag": veckodag, "Scen": scen,
    "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"], "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"], "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"], "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],
    "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
    "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
    "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],
    "Pappans vänner": st.session_state["input_pappan"], "Grannar": st.session_state["input_grannar"],
    "Nils vänner": st.session_state["input_nils_vanner"], "Nils familj": st.session_state["input_nils_familj"], "Bekanta": st.session_state["input_bekanta"], "Eskilstuna killar": st.session_state["input_eskilstuna"],
    "Bonus killar": st.session_state["input_bonus_killar"], "Bonus deltagit": st.session_state["input_bonus_deltagit"], "Personal deltagit": st.session_state["input_personal_deltagit"],
    "Nils": st.session_state["in_nils"],
    "Avgift": float(CFG["avgift_usd"]),
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

# ===== Prenumeranter & Ekonomi (live) =====
st.markdown("#### 📈 Prenumeranter & Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Kostnad män", _usd(preview.get("Intäkt män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Intäkt Företaget", _usd(preview.get("Intäkt Företaget", 0)))
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ============================== Spara / Auto-Max ================================
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

    ålder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month,rad_datum.day)<(CFG["födelsedatum"].month,CFG["födelsedatum"].day))
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")

def _apply_auto_max_and_save(pending):
    # Uppdatera endast max-värden i Inställningar när användaren accepterar
    for field, info in pending["over_max"].items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))
        CFG[key] = new_val
    # Spara raden
    grund = pending["grund"]
    rad_datum = _parse_date_for_save(pending["rad_datum"])
    veckodag = pending["veckodag"]
    _save_row(grund, rad_datum, veckodag)

save_clicked = st.button("💾 Spara raden")
if save_clicked:
    over_max = {}
    if pappans_vänner > int(CFG["MAX_PAPPAN"]):
        over_max[_get_label(LABELS,'Pappans vänner')] = {"current_max": int(CFG["MAX_PAPPAN"]), "new_value": pappans_vänner, "max_key": "MAX_PAPPAN"}
    if grannar > int(CFG["MAX_GRANNAR"]):
        over_max[_get_label(LABELS,'Grannar')] = {"current_max": int(CFG["MAX_GRANNAR"]), "new_value": grannar, "max_key": "MAX_GRANNAR"}
    if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
        over_max[_get_label(LABELS,'Nils vänner')] = {"current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": nils_vänner, "max_key": "MAX_NILS_VANNER"}
    if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
        over_max[_get_label(LABELS,'Nils familj')] = {"current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": nils_familj, "max_key": "MAX_NILS_FAMILJ"}
    if bekanta > int(CFG["MAX_BEKANTA"]):
        over_max[_get_label(LABELS,'Bekanta')] = {"current_max": int(CFG["MAX_BEKANTA"]), "new_value": bekanta, "max_key": "MAX_BEKANTA"}

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

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Ja, uppdatera max och spara"):
            try:
                _apply_auto_max_and_save(pending)
            except Exception as e:
                st.error(f"Kun­de inte spara: {e}")
            finally:
                st.session_state.pop("PENDING_SAVE", None)
                st.rerun()
    with c2:
        if st.button("✋ Nej, avbryt"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

# ============================== Snabbåtgärder ===============================
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

def _get_min_max(colname: str):
    try:
        all_rows = _get_all_rows_cached()
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

# --- Slumpa scen vit ---
if st.button("🎲 Slumpa scen vit"):
    # kolumnbaserat min/max
    st.session_state["in_man"]         = random.randint(*_get_min_max("Män"))
    st.session_state["in_fitta"]       = random.randint(*_get_min_max("Fitta"))
    st.session_state["in_rumpa"]       = random.randint(*_get_min_max("Rumpa"))
    st.session_state["in_dp"]          = random.randint(*_get_min_max("DP"))
    st.session_state["in_dpp"]         = random.randint(*_get_min_max("DPP"))
    st.session_state["in_dap"]         = random.randint(*_get_min_max("DAP"))
    st.session_state["in_tap"]         = random.randint(*_get_min_max("TAP"))
    st.session_state["input_pappan"]   = random.randint(*_get_min_max("Pappans vänner"))
    st.session_state["input_grannar"]  = random.randint(*_get_min_max("Grannar"))
    st.session_state["input_nils_vanner"] = random.randint(*_get_min_max("Nils vänner"))
    st.session_state["input_nils_familj"] = random.randint(*_get_min_max("Nils familj"))
    st.session_state["input_bekanta"]  = random.randint(*_get_min_max("Bekanta"))
    st.session_state["input_eskilstuna"] = random.randint(*_get_min_max("Eskilstuna killar"))
    # fasta
    st.session_state["in_alskar"] = 8
    st.session_state["in_sover"]  = 1
    # personal 10%
    st.session_state["input_personal_deltagit"] = _suggest_personal_deltagit()
    st.experimental_rerun()

# --- Slumpa scen svart ---
if st.button("🎲 Slumpa scen svart"):
    st.session_state["in_fitta"] = random.randint(*_get_min_max("Fitta"))
    st.session_state["in_rumpa"] = random.randint(*_get_min_max("Rumpa"))
    st.session_state["in_dp"]    = random.randint(*_get_min_max("DP"))
    st.session_state["in_dpp"]   = random.randint(*_get_min_max("DPP"))
    st.session_state["in_dap"]   = random.randint(*_get_min_max("DAP"))
    st.session_state["in_tap"]   = random.randint(*_get_min_max("TAP"))
    st.session_state["in_svarta"]= random.randint(*_get_min_max("Svarta"))
    st.session_state["in_alskar"]= 8
    st.session_state["in_sover"] = 1
    st.session_state["input_personal_deltagit"] = _suggest_personal_deltagit()
    st.experimental_rerun()

def _rand_40_60_source_values():
    return (
        _rand_40_60_of_max(int(CFG.get("MAX_PAPPAN", 0))),
        _rand_40_60_of_max(int(CFG.get("MAX_GRANNAR", 0))),
        _rand_40_60_of_max(int(CFG.get("MAX_NILS_VANNER", 0))),
        _rand_40_60_of_max(int(CFG.get("MAX_NILS_FAMILJ", 0))),
        _rand_40_60_of_max(int(CFG.get("MAX_BEKANTA", 0))),
    )

# --- Vila på jobbet ---
if st.button("➕ Skapa 'Vila på jobbet'-rad"):
    try:
        scen_num = next_scene_number()
        rad_datum2, veckodag2 = datum_och_veckodag_för_scen(scen_num)
        pv, gr, nv, nf, bk = _rand_40_60_source_values()
        esk = _rand_eskilstuna_20_40()

        # bonus: ta upp till 40% av BONUS_LEFT denna gång
        bonus_left = int(CFG.get("BONUS_LEFT", 0))
        use_now = int(round(bonus_left * 0.40))
        # uppdatera counters i settings (persistent)
        new_left = max(0, bonus_left - use_now)
        new_used = int(CFG.get("BONUS_USED", 0)) + use_now
        _save_setting("BONUS_LEFT", str(new_left))
        _save_setting("BONUS_USED", str(new_used))
        CFG["BONUS_LEFT"] = new_left
        CFG["BONUS_USED"] = new_used

        grund_vila = {
            "Typ": "Vila på jobbet",
            "Veckodag": veckodag2, "Scen": scen_num,
            "Män": 0, "Svarta": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
            "Tid S": 0, "Tid D": 0, "Vila": 0,
            "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,
            "Älskar": 12, "Sover med": 1,
            "Pappans vänner": pv, "Grannar": gr,
            "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
            "Bonus killar": int(CFG.get("BONUS_TOTAL",0)), "Bonus deltagit": use_now,
            "Personal deltagit": _suggest_personal_deltagit(),
            "Nils": 0,
            "Avgift": float(CFG.get("avgift_usd", 30.0)),
        }
        _save_row(grund_vila, rad_datum2, veckodag2)
    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

# --- Vila i hemmet (7 rader) – sprid återstående bonus på dag 1–5 ---
if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
    try:
        start_scene = next_scene_number()

        # Nils 50/45/5 (antal ettor dag 1–6)
        r = random.random()
        if r < 0.50:
            ones_count = 0
        elif r < 0.95:
            ones_count = 1
        else:
            ones_count = 2
        nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

        # bonus kvar att fördela dag 1–5
        bonus_left = int(CFG.get("BONUS_LEFT", 0))
        per_day = (bonus_left // 5) if bonus_left > 0 else 0

        for offset in range(7):
            scen_num = start_scene + offset
            rad_d, veckod = datum_och_veckodag_för_scen(scen_num)

            if offset <= 4:
                pv, gr, nv, nf, bk = _rand_40_60_source_values()
                esk = _rand_eskilstuna_20_40()
                bonus_use = per_day
            else:
                pv = gr = nv = nf = bk = 0
                esk = _rand_eskilstuna_20_40()
                bonus_use = 0

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
                "Bonus killar": int(CFG.get("BONUS_TOTAL",0)), "Bonus deltagit": bonus_use,
                "Personal deltagit": _suggest_personal_deltagit(),
                "Nils": nils_val,
                "Avgift": float(CFG.get("avgift_usd", 30.0)),
            }
            _save_row(grund_home, rad_d, veckod)

        # uppdatera counters efter användning dag1-5
        used_now = per_day * 5
        new_left = max(0, int(CFG.get("BONUS_LEFT", 0)) - used_now)
        new_used = int(CFG.get("BONUS_USED", 0)) + used_now
        _save_setting("BONUS_LEFT", str(new_left))
        _save_setting("BONUS_USED", str(new_used))
        CFG["BONUS_LEFT"] = new_left
        CFG["BONUS_USED"] = new_used

        st.success("✅ Skapade 7 'Vila i hemmet'-rader (med bonusfördelning).")
    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila i hemmet': {e}")

# ================================ Visa & radera ================================
st.subheader("📊 Aktuella data")
try:
    rows = _get_all_rows_cached()
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
