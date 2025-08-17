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
CONFIG_SHEET = "Config"   # Nytt: konfiguration (värden & etiketter)

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket via ID eller URL och hämta bladet 'Data'."""
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        st.caption("🔗 Öppnar via GOOGLE_SHEET_ID…")
        sh = _retry_call(client.open_by_key, sid)
        return sh

    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        st.caption("🔗 Öppnar via SHEET_URL…")
        sh = _retry_call(client.open_by_url, url)
        return sh

    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        st.caption("🔎 Öppnar via query-param 'sheet'…")
        sh = _retry_call(client.open_by_url, qp) if qp.startswith("http") else _retry_call(client.open_by_key, qp)
        return sh

    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

spreadsheet = resolve_sheet()
sheet = spreadsheet.worksheet(WORKSHEET_TITLE)

# =========================== Config/Etiketter ===========================
DEFAULT_CONFIG_ROWS = [
    # Key, Value, Label
    ["MAX_PAPPAN", "10", "Pappans vänner"],
    ["MAX_GRANNAR", "10", "Grannar"],
    ["MAX_NILS_VANNER", "10", "Nils vänner"],
    ["MAX_NILS_FAMILJ", "10", "Nils familj"],
    ["MAX_BEKANTA", "10", "Bekanta"],
    ["AVGIFT_USD", "30", "Avgift (USD, per ny rad)"],
    ["STARTDATUM", "", "Historiskt startdatum"],
    ["STARTTID", "", "Starttid"],
    ["MALIN_FODELSEDATUM", "", "Malins födelsedatum"],  # + Etikett stöds nu
    ["LABEL_PAPPANS_VANNER", "", "Pappans vänner"],
    ["LABEL_GRANNAR", "", "Grannar"],
    ["LABEL_NILS_VANNER", "", "Nils vänner"],
    ["LABEL_NILS_FAMILJ", "", "Nils familj"],
    ["LABEL_BEKANTA", "", "Bekanta"],
    ["LABEL_MALIN_FODELSEDATUM", "", "Malins födelsedatum"],  # <- Nyckeln för etikett till datumfältet
]

def _ensure_config_sheet():
    try:
        cfg_ws = spreadsheet.worksheet(CONFIG_SHEET)
    except gspread.WorksheetNotFound:
        cfg_ws = spreadsheet.add_worksheet(title=CONFIG_SHEET, rows=100, cols=3)
        cfg_ws.update("A1:C1", [["Key", "Value", "Label"]])
        cfg_ws.update(f"A2:C{2+len(DEFAULT_CONFIG_ROWS)-1}", DEFAULT_CONFIG_ROWS)
    return cfg_ws

def _config_as_dict():
    ws = _ensure_config_sheet()
    rows = ws.get_all_records()
    d = {}
    for r in rows:
        key = (r.get("Key") or "").strip()
        val = (r.get("Value") or "").strip()
        lab = (r.get("Label") or "").strip()
        if key:
            d[key] = {"value": val, "label": lab}
    return d

def _save_config_value(key, value=None, label=None):
    ws = _ensure_config_sheet()
    # Hämta hela arket för positioner
    rows = ws.get_all_values()
    header = rows[0] if rows else []
    # Förväntad header: ["Key","Value","Label"]
    key_col = 1
    val_col = 2
    lab_col = 3
    # Sök efter key
    row_idx = None
    for i in range(1, len(rows)):
        if rows[i][0] == key:
            row_idx = i + 1  # 1-indexerat
            break
    if row_idx is None:
        row_idx = len(rows) + 1
        ws.update(f"A{row_idx}:C{row_idx}", [[key, value or "", label or ""]])
        return
    # Uppdatera befintlig
    row_vals = rows[row_idx-1] + ["", "", ""]
    new_val = value if value is not None else row_vals[val_col-1]
    new_lab = label if label is not None else row_vals[lab_col-1]
    ws.update(f"A{row_idx}:C{row_idx}", [[key, new_val, new_lab]])

def _label_for(default_text, label_key):
    cfg = st.session_state.get("_CFG_RAW", {})
    lab = (cfg.get(label_key, {}) or {}).get("label", "").strip()
    return lab if lab else default_text

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
    "Totalt Män","Tid kille","Nils",
    "Hångel (sek/kille)","Hångel (m:s/kille)",
    "Suger","Suger per kille (sek)",
    "Hårdhet","Prenumeranter","Bonus killar","Avgift","Intäkter",
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
        end_col_letter = "ZZ" if len(new_header) > 26 else chr(64 + len(new_header))
        _retry_call(sheet.update, f"A1:{end_col_letter}1", [new_header])
        st.caption(f"🔧 Migrerade header, lade till: {', '.join(missing)}")
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
KOLUMNER = st.session_state["COLUMNS"]

# ================================ Ladda konfig/etiketter ================================
def _load_cfg():
    raw = _config_as_dict()
    st.session_state["_CFG_RAW"] = raw

    def _int_val(k, default):
        try:
            return int(raw.get(k, {}).get("value") or default)
        except Exception:
            return default

    def _float_val(k, default):
        try:
            return float(raw.get(k, {}).get("value") or default)
        except Exception:
            return default

    def _date_val(k, default):
        v = (raw.get(k, {}).get("value") or "").strip()
        if not v:
            return default
        try:
            return datetime.fromisoformat(v).date()
        except Exception:
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except Exception:
                return default

    def _time_val(k, default):
        v = (raw.get(k, {}).get("value") or "").strip()
        if not v:
            return default
        try:
            return datetime.strptime(v, "%H:%M:%S").time()
        except Exception:
            try:
                return datetime.strptime(v, "%H:%M").time()
            except Exception:
                return default

    CFG = {
        "MAX_PAPPAN": _int_val("MAX_PAPPAN", 10),
        "MAX_GRANNAR": _int_val("MAX_GRANNAR", 10),
        "MAX_NILS_VANNER": _int_val("MAX_NILS_VANNER", 10),
        "MAX_NILS_FAMILJ": _int_val("MAX_NILS_FAMILJ", 10),
        "MAX_BEKANTA": _int_val("MAX_BEKANTA", 10),
        "avgift_usd": _float_val("AVGIFT_USD", 30.0),
        "startdatum": _date_val("STARTDATUM", date.today()),
        "starttid": _time_val("STARTTID", time(7, 0)),
        "födelsedatum": _date_val("MALIN_FODELSEDATUM", date(1990,1,1)),
    }

    LABELS = {
        "PAPPANS_VANNER": _label_for("Pappans vänner", "LABEL_PAPPANS_VANNER"),
        "GRANNAR": _label_for("Grannar", "LABEL_GRANNAR"),
        "NILS_VANNER": _label_for("Nils vänner", "LABEL_NILS_VANNER"),
        "NILS_FAMILJ": _label_for("Nils familj", "LABEL_NILS_FAMILJ"),
        "BEKANTA": _label_for("Bekanta", "LABEL_BEKANTA"),
        "MALIN_FODELSEDATUM": _label_for("Malins födelsedatum", "LABEL_MALIN_FODELSEDATUM"),
    }
    return CFG, LABELS

CFG, LABELS = _load_cfg()

# ===== Meny =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik", "Inställningar"], index=0)

# =============================== INSTÄLLNINGAR ================================
if view == "Inställningar":
    st.header("⚙️ Inställningar & Etiketter (sparas i fliken 'Config')")

    # Värden
    c1, c2 = st.columns(2)
    with c1:
        new_startdatum = st.date_input(_label_for("Historiskt startdatum", "STARTDATUM"), value=CFG["startdatum"])
        new_starttid = st.time_input(_label_for("Starttid", "STARTTID"), value=CFG["starttid"])
        new_fodelse = st.date_input(LABELS["MALIN_FODELSEDATUM"], value=CFG["födelsedatum"])
        new_avgift = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))
    with c2:
        new_max_p = st.number_input(LABELS["PAPPANS_VANNER"] + " (max)", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
        new_max_g = st.number_input(LABELS["GRANNAR"] + " (max)", min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
        new_max_nv = st.number_input(LABELS["NILS_VANNER"] + " (max)", min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
        new_max_nf = st.number_input(LABELS["NILS_FAMILJ"] + " (max)", min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
        new_max_bk = st.number_input(LABELS["BEKANTA"] + " (max)", min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

    st.markdown("### Etiketter")
    e1, e2 = st.columns(2)
    with e1:
        lab_p = st.text_input("Etikett för Pappans vänner", value=LABELS["PAPPANS_VANNER"])
        lab_g = st.text_input("Etikett för Grannar", value=LABELS["GRANNAR"])
        lab_nv = st.text_input("Etikett för Nils vänner", value=LABELS["NILS_VANNER"])
    with e2:
        lab_nf = st.text_input("Etikett för Nils familj", value=LABELS["NILS_FAMILJ"])
        lab_bk = st.text_input("Etikett för Bekanta", value=LABELS["BEKANTA"])
        lab_fod = st.text_input("Etikett för Malins födelsedatum", value=LABELS["MALIN_FODELSEDATUM"])

    if st.button("💾 Spara inställningar & etiketter"):
        _save_config_value("STARTDATUM", new_startdatum.isoformat())
        _save_config_value("STARTTID", new_starttid.strftime("%H:%M:%S"))
        _save_config_value("MALIN_FODELSEDATUM", new_fodelse.isoformat())
        _save_config_value("AVGIFT_USD", str(new_avgift))

        _save_config_value("MAX_PAPPAN", str(int(new_max_p)))
        _save_config_value("MAX_GRANNAR", str(int(new_max_g)))
        _save_config_value("MAX_NILS_VANNER", str(int(new_max_nv)))
        _save_config_value("MAX_NILS_FAMILJ", str(int(new_max_nf)))
        _save_config_value("MAX_BEKANTA", str(int(new_max_bk)))

        _save_config_value("LABEL_PAPPANS_VANNER", label=lab_p)
        _save_config_value("LABEL_GRANNAR", label=lab_g)
        _save_config_value("LABEL_NILS_VANNER", label=lab_nv)
        _save_config_value("LABEL_NILS_FAMILJ", label=lab_nf)
        _save_config_value("LABEL_BEKANTA", label=lab_bk)
        _save_config_value("LABEL_MALIN_FODELSEDATUM", label=lab_fod)

        st.success("Sparat! Laddar om…")
        st.rerun()

    st.stop()

# =============================== STATISTIKVY ================================
if view == "Statistik":
    st.header("📊 Statistik")

    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

    # --- Basmetrik: scener, privat GB, totalt män (män+eskilstuna), snitt scener, snitt privat GB ---
    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man = 0  # summerar Män + Eskilstuna killar
    summa_for_snitt_scener = 0
    summa_privat_gb_kanner = 0

    total_svarta_sum = 0
    total_men_like_sum = 0  # män + eskilstuna + svarta (för andel svarta)

    for r in rows:
        man = _safe_int(r.get("Män", 0), 0)
        esk = _safe_int(r.get("Eskilstuna killar", 0), 0)
        kanner = _safe_int(r.get("Känner", 0), 0)
        svarta = _safe_int(r.get("Svarta", 0), 0)

        men_like = man + esk  # för scener och totals
        men_like_plus_black = man + esk + svarta

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
    with c3: st.metric("Totalt antal män", totalt_man)  # män + eskilstuna
    with c4: st.metric("Snitt scener", snitt_scener)
    with c5: st.metric("Snitt Privat GB", snitt_privat_gb)
    st.metric("Andel svarta av män (%)", andel_svarta_pct)

    # --- Snitt relativt max per källa + Totalt antal tillfällen (rel. snitt + älskar [+ sover]) ---
    max_p  = int(st.session_state.get("MAX_PAPPAN", CFG["MAX_PAPPAN"]))
    max_g  = int(st.session_state.get("MAX_GRANNAR", CFG["MAX_GRANNAR"]))
    max_nv = int(st.session_state.get("MAX_NILS_VANNER", CFG["MAX_NILS_VANNER"]))
    max_nf = int(st.session_state.get("MAX_NILS_FAMILJ", CFG["MAX_NILS_FAMILJ"]))

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
        st.markdown(f"**{LABELS['PAPPANS_VANNER']}**")
        st.metric("Snitt (rel. max)", pv_avg_rel)
        st.metric("Totalt antal tillfällen", pv_tot_tillf)

        st.markdown(f"**{LABELS['GRANNAR']}**")
        st.metric("Snitt (rel. max)", gr_avg_rel)
        st.metric("Totalt antal tillfällen", gr_tot_tillf)
    with cB:
        st.markdown(f"**{LABELS['NILS_VANNER']}**")
        st.metric("Snitt (rel. max)", nv_avg_rel)
        st.metric("Totalt antal tillfällen", nv_tot_tillf)

        st.markdown(f"**{LABELS['NILS_FAMILJ']}**")
        st.metric("Snitt (rel. max)", nf_avg_rel)
        st.metric("Totalt antal tillfällen", nf_tot_tillf)

    # --- Prenumeranter: total + aktiva 30 dagar ---
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

    # --- Ekonomi (totalsummor i USD) ---
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

    # Snitt intäkt känner (enligt tidigare överenskommelse)
    sum_max = max_p + max_g + max_nv + max_nf
    snitt_intakt_kanner = (total_intakt_kanner + total_intakt_foretag + total_vinst) / sum_max if sum_max > 0 else 0.0
    st.metric("Snitt intäkt känner", f"{snitt_intakt_kanner:.2f} USD")

    # Snitt lön = (intäkt_känner + intäkt_företag + vinst) / (totalt_män (män+esk) + älskar + sover med)
    alskar_sum_all = sum(_safe_int(r.get("Älskar", 0), 0) for r in rows)
    sover_sum_all  = sum(_safe_int(r.get("Sover med", 0), 0) for r in rows)
    divisor_snitt_lon = (totalt_man + alskar_sum_all + sover_sum_all)
    snitt_lon = (total_intakt_kanner + total_intakt_foretag + total_vinst) / divisor_snitt_lon if divisor_snitt_lon > 0 else 0.0
    st.metric("Snitt lön", f"{snitt_lon:.2f} USD")

    # --- DP/DPP/DAP/TAP ---
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

    # --- Älskar / Sover med + Nils-summa + per dag ---
    st.markdown("---")
    st.subheader("💗 Älskar / 😴 Sover med — summa & snitt (plus Nils-summa)")
    alskar_sum = alskar_sum_all
    sover_sum  = sover_sum_all
    nils_sum   = sum(_safe_int(r.get("Nils", 0)) for r in rows)

    denom_alskar2 = (max_p + max_g + max_nv + max_nf)
    snitt_alskar2 = round(alskar_sum / denom_alskar2, 2) if denom_alskar2 > 0 else 0.0
    snitt_sover2  = round(sover_sum / max_nf, 2) if max_nf > 0 else 0.0

    c_als1, c_als2, c_sov1, c_sov2 = st.columns(4)
    with c_als1: st.metric("Summa Älskar", alskar_sum)
    with c_als2: st.metric("Snitt Älskar", snitt_alskar2)
    with c_sov1: st.metric("Summa Sover med", sover_sum)
    with c_sov2: st.metric("Snitt Sover med", snitt_sover2)
    st.metric("Nils (summa)", nils_sum)

    # ---- Älskar/Sover per dag ----
    total_rows = len(rows)
    alskar_per_dag = (alskar_sum / total_rows) if total_rows > 0 else 0.0
    sover_per_dag  = (sover_sum / total_rows) if total_rows > 0 else 0.0
    d1, d2 = st.columns(2)
    with d1: st.metric("Älskar / dag", f"{alskar_per_dag:.2f}")
    with d2: st.metric("Sover med / dag", f"{sover_per_dag:.2f}")

    # --- Snitt tid kille / scen ---
    st.markdown("---")
    st.subheader("⏱️ Tid per kille / scen")
    tpk_total_sec = sum(_safe_int(r.get("Tid per kille (sek)", 0)) for r in rows if (_safe_int(r.get("Män", 0)) + _safe_int(r.get("Eskilstuna killar", 0))) > 0)
    tpk_avg_sec = int(round(tpk_total_sec / denom_scen)) if antal_scener > 0 else 0
    tpk_avg_label = _ms_str_from_seconds(tpk_avg_sec)
    st.metric("Snitt tid kille / scen", tpk_avg_label)

    # --- Snitt tid (h) per scen exkl. älskar & sover med ---
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

# init defaults from CONFIG
st.session_state.setdefault("CFG", {})
for k in ["startdatum","starttid","födelsedatum","MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA","avgift_usd"]:
    st.session_state["CFG"].setdefault(k, CFG[k])

startdatum = st.sidebar.date_input(_label_for("Historiskt startdatum", "STARTDATUM"), value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
starttid   = st.sidebar.time_input(_label_for("Starttid", "STARTTID"), value=CFG["starttid"])
födelsedatum = st.sidebar.date_input(
    _label_for("Malins födelsedatum", "LABEL_MALIN_FODELSEDATUM"),
    value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
    min_value=MIN_FOD, max_value=date.today()
)

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
max_p  = st.sidebar.number_input(f"{LABELS['PAPPANS_VANNER']} (max)", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
max_g  = st.sidebar.number_input(f"{LABELS['GRANNAR']} (max)",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
max_nv = st.sidebar.number_input(f"{LABELS['NILS_VANNER']} (max)",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
max_nf = st.sidebar.number_input(f"{LABELS['NILS_FAMILJ']} (max)",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
max_bk = st.sidebar.number_input(f"{LABELS['BEKANTA']} (max)",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

st.sidebar.subheader("Pris per prenumerant (gäller NÄSTA rad)")
avgift_input = st.sidebar.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

if st.sidebar.button("💾 Spara inställningar"):
    # Spara i config-sheet
    _save_config_value("STARTDATUM", startdatum.isoformat())
    _save_config_value("STARTTID", starttid.strftime("%H:%M:%S"))
    _save_config_value("MALIN_FODELSEDATUM", födelsedatum.isoformat())
    _save_config_value("AVGIFT_USD", str(float(avgift_input)))
    _save_config_value("MAX_PAPPAN", str(int(max_p)))
    _save_config_value("MAX_GRANNAR", str(int(max_g)))
    _save_config_value("MAX_NILS_VANNER", str(int(max_nv)))
    _save_config_value("MAX_NILS_FAMILJ", str(int(max_nf)))
    _save_config_value("MAX_BEKANTA", str(int(max_bk)))

    # Uppdatera session
    CFG.update({
        "startdatum": startdatum,
        "starttid": starttid,
        "födelsedatum": födelsedatum,
        "MAX_PAPPAN": int(max_p),
        "MAX_GRANNAR": int(max_g),
        "MAX_NILS_VANNER": int(max_nv),
        "MAX_NILS_FAMILJ": int(max_nf),
        "MAX_BEKANTA": int(max_bk),
        "avgift_usd": float(avgift_input),
    })
    st.session_state.update(
        MAX_PAPPAN=int(max_p),
        MAX_GRANNAR=int(max_g),
        MAX_NILS_VANNER=int(max_nv),
        MAX_NILS_FAMILJ=int(max_nf),
        MAX_BEKANTA=int(max_bk),
    )
    st.success("Inställningar sparade ✅")

# Se till att max finns i session (för etiketter)
st.session_state.setdefault("MAX_PAPPAN",      int(CFG["MAX_PAPPAN"]))
st.session_state.setdefault("MAX_GRANNAR",     int(CFG["MAX_GRANNAR"]))
st.session_state.setdefault("MAX_NILS_VANNER", int(CFG["MAX_NILS_VANNER"]))
st.session_state.setdefault("MAX_NILS_FAMILJ", int(CFG["MAX_NILS_FAMILJ"]))
st.session_state.setdefault("MAX_BEKANTA",     int(CFG["MAX_BEKANTA"]))

# ===== 30 dagar (rullande) i sidopanelen =====
st.sidebar.subheader("📆 30 dagar (rullande)")
try:
    all_rows = _retry_call(sheet.get_all_records)
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

män    = st.number_input("Män",    min_value=0, step=1, value=0)
svarta = st.number_input("Svarta", min_value=0, step=1, value=0)
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

lbl_p  = f"{LABELS['PAPPANS_VANNER']} (max {st.session_state.MAX_PAPPAN})"
lbl_g  = f"{LABELS['GRANNAR']} (max {st.session_state.MAX_GRANNAR})"
lbl_nv = f"{LABELS['NILS_VANNER']} (max {st.session_state.MAX_NILS_VANNER})"
lbl_nf = f"{LABELS['NILS_FAMILJ']} (max {st.session_state.MAX_NILS_FAMILJ})"
lbl_bk = f"{LABELS['BEKANTA']} (max {st.session_state.MAX_BEKANTA})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")
bekanta        = st.number_input(lbl_bk, min_value=0, step=1, value=0, key="input_bekanta")

eskilstuna_killar = st.number_input("Eskilstuna killar", min_value=0, step=1, value=0, key="input_eskilstuna")

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

# ============================ Live-förhandsberäkning ===========================
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

# ---- Bonus-system (5% chans per prenumerant) i PREVIEW ----
def _binomial_draw(n, p=0.05):
    k = 0
    for _ in range(int(max(0, n))):
        if random.random() < p:
            k += 1
    return k

bonus_preview = _binomial_draw(int(preview.get("Prenumeranter", 0)), 0.05)

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
with col2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
with col3:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Bonus killar (preview)", int(bonus_preview))

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

        # Bonus killar på spar-ögonblicket (bind raddata)
        bonus = _binomial_draw(int(ber.get("Prenumeranter", 0)), 0.05)
        ber["Bonus killar"] = int(bonus)
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state.ROW_COUNT += 1

    ålder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month,rad_datum.day)<(CFG["födelsedatum"].month,CFG["födelsedatum"].day))
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")

def _apply_auto_max_and_save(pending):
    # Uppdatera config-sheet också
    for _, info in pending["over_max"].items():
        new_val = int(info["new_value"])
        st.session_state[info["max_key"]] = new_val
        _save_config_value(info["max_key"], str(new_val))

    grund = pending["grund"]
    rad_datum = _parse_date_for_save(pending["rad_datum"])
    veckodag = pending["veckodag"]
    _save_row(grund, rad_datum, veckodag)

save_clicked = st.button("💾 Spara raden")
if save_clicked:
    over_max = {}
    if pappans_vänner > st.session_state.MAX_PAPPAN:
        over_max["Pappans vänner"] = {"current_max": st.session_state.MAX_PAPPAN, "new_value": pappans_vänner, "max_key": "MAX_PAPPAN"}
    if grannar > st.session_state.MAX_GRANNAR:
        over_max["Grannar"] = {"current_max": st.session_state.MAX_GRANNAR, "new_value": grannar, "max_key": "MAX_GRANNAR"}
    if nils_vänner > st.session_state.MAX_NILS_VANNER:
        over_max["Nils vänner"] = {"current_max": st.session_state.MAX_NILS_VANNER, "new_value": nils_vänner, "max_key": "MAX_NILS_VANNER"}
    if nils_familj > st.session_state.MAX_NILS_FAMILJ:
        over_max["Nils familj"] = {"current_max": st.session_state.MAX_NILS_FAMILJ, "new_value": nils_familj, "max_key": "MAX_NILS_FAMILJ"}
    if bekanta > st.session_state.MAX_BEKANTA:
        over_max["Bekanta"] = {"current_max": st.session_state.MAX_BEKANTA, "new_value": bekanta, "max_key": "MAX_BEKANTA"}

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
                st.error(f"Kunde inte spara: {e}")
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
    """Ny range: 40–60% av max (används i vila-knapparna)."""
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
    """20–40; 70% chans >30, 30% chans ≤30."""
    r = random.random()
    if r < 0.30:
        # 30% chans: 20–30
        return random.randint(20, 30)
    else:
        # 70% chans: 31–40
        return random.randint(31, 40)

# --- Vila på jobbet ---
if st.button("➕ Skapa 'Vila på jobbet'-rad"):
    try:
        scen_num = next_scene_number()
        rad_datum2, veckodag2 = datum_och_veckodag_för_scen(scen_num)

        pv = _rand_40_60_of_max(st.session_state.get("MAX_PAPPAN", CFG["MAX_PAPPAN"]))
        gr = _rand_40_60_of_max(st.session_state.get("MAX_GRANNAR", CFG["MAX_GRANNAR"]))
        nv = _rand_40_60_of_max(st.session_state.get("MAX_NILS_VANNER", CFG["MAX_NILS_VANNER"]))
        nf = _rand_40_60_of_max(st.session_state.get("MAX_NILS_FAMILJ", CFG["MAX_NILS_FAMILJ"]))
        bk = _rand_40_60_of_max(st.session_state.get("MAX_BEKANTA", CFG["MAX_BEKANTA"]))
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
            "Avgift": float(CFG.get("avgift_usd", 30.0)),
        }
        _save_row(grund_vila, rad_datum2, veckodag2)
    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

# --- Vila i hemmet (7 rader) — med Nils-fördelning 50/45/5 ---
if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
    try:
        start_scene = next_scene_number()

        # Bestäm antal ettor för dag 1–6 (50%:0, 45%:1, 5%:2)
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

            # Dag 1–5 slump, dag 6–7 noll
            if offset <= 4:
                pv = _rand_40_60_of_max(st.session_state.get("MAX_PAPPAN", CFG["MAX_PAPPAN"]))
                gr = _rand_40_60_of_max(st.session_state.get("MAX_GRANNAR", CFG["MAX_GRANNAR"]))
                nv = _rand_40_60_of_max(st.session_state.get("MAX_NILS_VANNER", CFG["MAX_NILS_VANNER"]))
                nf = _rand_40_60_of_max(st.session_state.get("MAX_NILS_FAMILJ", CFG["MAX_NILS_FAMILJ"]))
                bk = _rand_40_60_of_max(st.session_state.get("MAX_BEKANTA", CFG["MAX_BEKANTA"]))
                esk = _rand_eskilstuna_20_40()
            else:
                pv = gr = nv = nf = bk = 0
                esk = _rand_eskilstuna_20_40()  # även dag6–7 får ett antal enligt regeln

            sv = 1 if offset == 6 else 0  # dag7 sover med

            # Nils: dag7 = 0, dag1–6: enligt fördelning
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
                "Avgift": float(CFG.get("avgift_usd", 30.0)),
            }
            _save_row(grund_home, rad_d, veckod)

        st.success("✅ Skapade 7 'Vila i hemmet'-rader (Nils 50/45/5).")
    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila i hemmet': {e}")

# ================================ Visa & radera ================================
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
