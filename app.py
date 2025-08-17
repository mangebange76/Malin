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

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket via ID eller URL och hämta bladet 'Data'."""
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        st.caption("🔗 Öppnar via GOOGLE_SHEET_ID…")
        sh = _retry_call(client.open_by_key, sid)
        return sh.worksheet(WORKSHEET_TITLE)

    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        st.caption("🔗 Öppnar via SHEET_URL…")
        sh = _retry_call(client.open_by_url, url)
        return sh.worksheet(WORKSHEET_TITLE)

    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        st.caption("🔎 Öppnar via query-param 'sheet'…")
        sh = _retry_call(client.open_by_url, qp) if qp.startswith("http") else _retry_call(client.open_by_key, qp)
        return sh.worksheet(WORKSHEET_TITLE)

    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

sheet = resolve_sheet()

# =========================== Settings via fliken "Inställningar" =========================
SETTINGS_SHEET = "Inställningar"
SETTINGS_COLS = ["Key", "Value", "Label"]

def _get_settings_ws():
    ss = sheet.spreadsheet
    try:
        return ss.worksheet(SETTINGS_SHEET)
    except gspread.WorksheetNotFound:
        st.error("Fliken 'Inställningar' saknas. Skapa den med rubriker: Key | Value | Label.")
        st.stop()

def _config_as_dict():
    ws = _get_settings_ws()
    rows = ws.get_all_records()
    d = {}
    for r in rows:
        key   = str(r.get("Key", "")).strip()
        value = str(r.get("Value", "")).strip()
        label = str(r.get("Label", "")).strip()
        if key:
            d[key] = {"value": value, "label": label}
    return d

def _update_settings_row(key, *, value=None, label=None):
    ws = _get_settings_ws()
    data = ws.get_all_values()
    if not data:
        st.error("Fliken 'Inställningar' saknar data. Rubrikerna måste vara Key | Value | Label.")
        st.stop()
    header = data[0]
    try:
        key_col   = header.index("Key") + 1
        value_col = header.index("Value") + 1
        label_col = header.index("Label") + 1
    except ValueError:
        st.error("Rubrikerna i 'Inställningar' måste vara exakt: Key | Value | Label.")
        st.stop()

    target_row = None
    for i in range(1, len(data)):
        if (data[i][key_col-1] or "").strip() == key:
            target_row = i + 1
            break
    if target_row is None:
        st.error(f"Nyckeln '{key}' finns inte i 'Inställningar'.")
        st.stop()

    updates = []
    if value is not None:
        updates.append({"range": gspread.utils.rowcol_to_a1(target_row, value_col), "values": [[str(value)]]})
    if label is not None:
        updates.append({"range": gspread.utils.rowcol_to_a1(target_row, label_col), "values": [[str(label)]]})
    if updates:
        ws.batch_update([{"range": u["range"], "values": u["values"]} for u in updates])

def _load_cfg_and_labels():
    d = _config_as_dict()
    st.session_state.setdefault("CFG", {})
    st.session_state.setdefault("LABELS", {})
    for key, obj in d.items():
        st.session_state["CFG"][key]    = obj.get("value", "")
        st.session_state["LABELS"][key] = obj.get("label", "")
    return st.session_state["CFG"], st.session_state["LABELS"]

CFG_STR, LABELS = _load_cfg_and_labels()

def _lbl(key, fallback):
    s = (LABELS.get(key) or "").strip()
    return s if s else fallback

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

# ===== Meny =====
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# =============================== STATISTIKVY ================================
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
    total_men_like_sum = 0  # män + eskilstuna + svarta (för % svarta)

    bonus_deltagit_sum = sum(_safe_int(r.get("Bonus deltagit", 0), 0) for r in rows)

    for r in rows:
        man = _safe_int(r.get("Män", 0), 0)
        esk = _safe_int(r.get("Eskilstuna killar", 0), 0)
        kanner = _safe_int(r.get("Känner", 0), 0)
        svarta = _safe_int(r.get("Svarta", 0), 0)

        men_like = man + esk
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
    with c3: st.metric("Totalt antal män", totalt_man)
    with c4: st.metric("Snitt scener", snitt_scener)
    with c5: st.metric("Snitt Privat GB", snitt_privat_gb)
    st.metric("Andel svarta av män (%)", andel_svarta_pct)
    st.metric("Bonus killar som deltagit (summa)", int(bonus_deltagit_sum))

    # --- Snitt relativt max + Totalt antal tillfällen ---
    max_p  = int(st.session_state.get("CFG", {}).get("MAX_PAPPAN", 0) or 0)
    max_g  = int(st.session_state.get("CFG", {}).get("MAX_GRANNAR", 0) or 0)
    max_nv = int(st.session_state.get("CFG", {}).get("MAX_NILS_VANNER", 0) or 0)
    max_nf = int(st.session_state.get("CFG", {}).get("MAX_NILS_FAMILJ", 0) or 0)

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
        st.markdown(f"**{_lbl('MAX_PAPPAN','Pappans vänner')}**")
        st.metric("Snitt (rel. max)", pv_avg_rel)
        st.metric("Totalt antal tillfällen", pv_tot_tillf)

        st.markdown(f"**{_lbl('MAX_GRANNAR','Grannar')}**")
        st.metric("Snitt (rel. max)", gr_avg_rel)
        st.metric("Totalt antal tillfällen", gr_tot_tillf)
    with cB:
        st.markdown(f"**{_lbl('MAX_NILS_VANNER','Nils vänner')}**")
        st.metric("Snitt (rel. max)", nv_avg_rel)
        st.metric("Totalt antal tillfällen", nv_tot_tillf)

        st.markdown(f"**{_lbl('MAX_NILS_FAMILJ','Nils familj')}**")
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

    # --- Ekonomi (totalsummor i USD) --- (lämnas som tidigare – vi justerar senare)
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

    sum_max = max_p + max_g + max_nv + max_nf
    snitt_intakt_kanner = (total_intakt_kanner + total_intakt_foretag + total_vinst) / sum_max if sum_max > 0 else 0.0
    st.metric("Snitt intäkt känner", f"{snitt_intakt_kanner:.2f} USD")

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

def _init_cfg_defaults():
    # Om värden saknas i Inställningar-fliken kan vi initialisera default i sessionen,
    # men SKRIVER inte till bladet automatiskt.
    st.session_state.setdefault("CFG", {})
    ss_cfg = st.session_state["CFG"]
    ss_cfg.setdefault("startdatum", date.today().isoformat())
    ss_cfg.setdefault("starttid", time(7, 0).isoformat())
    ss_cfg.setdefault("födelsedatum", date(1990,1,1).isoformat())
    ss_cfg.setdefault("MAX_PAPPAN", "10")
    ss_cfg.setdefault("MAX_GRANNAR", "10")
    ss_cfg.setdefault("MAX_NILS_VANNER", "10")
    ss_cfg.setdefault("MAX_NILS_FAMILJ", "10")
    ss_cfg.setdefault("MAX_BEKANTA", "10")
    ss_cfg.setdefault("avgift_usd", "30.0")
    # Bonus-tracking
    ss_cfg.setdefault("BONUS_POOL_TOTAL", "0")
    ss_cfg.setdefault("BONUS_PARTICIPATED", "0")

_init_cfg_defaults()
CFG = st.session_state["CFG"]

# Läs labels
LABELS = st.session_state.get("LABELS", {})

# Helpers för att hämta typed values
def _get_cfg_date(key, default: date):
    s = CFG.get(key, "")
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return default

def _get_cfg_time(key, default: time):
    s = CFG.get(key, "")
    try:
        return datetime.fromisoformat(s).time()
    except Exception:
        return default

def _get_cfg_int(key, default: int):
    try:
        return int(float(CFG.get(key, default)))
    except Exception:
        return default

def _get_cfg_float(key, default: float):
    try:
        return float(CFG.get(key, default))
    except Exception:
        return default

startdatum = st.sidebar.date_input("Historiskt startdatum", value=_clamp(_get_cfg_date("startdatum", date.today()), MIN_START, date(2100,1,1)))
starttid   = st.sidebar.time_input("Starttid", value=_get_cfg_time("starttid", time(7,0)))
födelsedatum = st.sidebar.date_input(
    "Malins födelsedatum",
    value=_clamp(_get_cfg_date("födelsedatum", date(1990,1,1)), MIN_FOD, date.today()),
    min_value=MIN_FOD, max_value=date.today()
)

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
max_p  = st.sidebar.number_input(f"Max {_lbl('MAX_PAPPAN','Pappans vänner')}", min_value=0, step=1, value=_get_cfg_int("MAX_PAPPAN", 10))
max_g  = st.sidebar.number_input(f"Max {_lbl('MAX_GRANNAR','Grannar')}",        min_value=0, step=1, value=_get_cfg_int("MAX_GRANNAR", 10))
max_nv = st.sidebar.number_input(f"Max {_lbl('MAX_NILS_VANNER','Nils vänner')}",    min_value=0, step=1, value=_get_cfg_int("MAX_NILS_VANNER", 10))
max_nf = st.sidebar.number_input(f"Max {_lbl('MAX_NILS_FAMILJ','Nils familj')}",    min_value=0, step=1, value=_get_cfg_int("MAX_NILS_FAMILJ", 10))
max_bk = st.sidebar.number_input(f"Max {_lbl('MAX_BEKANTA','Bekanta')}",        min_value=0, step=1, value=_get_cfg_int("MAX_BEKANTA", 10))

st.sidebar.subheader("Pris per prenumerant (gäller NÄSTA rad)")
avgift_input = st.sidebar.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=_get_cfg_float("avgift_usd", 30.0))

# Visa/ändra etiketter
with st.sidebar.expander("Etiketter (ändrar bara UI-texter)"):
    lbl_p  = st.text_input("Etikett för Pappans vänner", value=_lbl("MAX_PAPPAN","Pappans vänner"))
    lbl_g  = st.text_input("Etikett för Grannar", value=_lbl("MAX_GRANNAR","Grannar"))
    lbl_nv = st.text_input("Etikett för Nils vänner", value=_lbl("MAX_NILS_VANNER","Nils vänner"))
    lbl_nf = st.text_input("Etikett för Nils familj", value=_lbl("MAX_NILS_FAMILJ","Nils familj"))
    lbl_bk = st.text_input("Etikett för Bekanta", value=_lbl("MAX_BEKANTA","Bekanta"))

if st.sidebar.button("💾 Spara inställningar"):
    # Spara Value
    _update_settings_row("startdatum", value=startdatum.isoformat())
    _update_settings_row("starttid", value=starttid.isoformat())
    _update_settings_row("födelsedatum", value=födelsedatum.isoformat())
    _update_settings_row("MAX_PAPPAN", value=int(max_p))
    _update_settings_row("MAX_GRANNAR", value=int(max_g))
    _update_settings_row("MAX_NILS_VANNER", value=int(max_nv))
    _update_settings_row("MAX_NILS_FAMILJ", value=int(max_nf))
    _update_settings_row("MAX_BEKANTA", value=int(max_bk))
    _update_settings_row("avgift_usd", value=float(avgift_input))
    # Spara Label
    _update_settings_row("MAX_PAPPAN", label=lbl_p)
    _update_settings_row("MAX_GRANNAR", label=lbl_g)
    _update_settings_row("MAX_NILS_VANNER", label=lbl_nv)
    _update_settings_row("MAX_NILS_FAMILJ", label=lbl_nf)
    _update_settings_row("MAX_BEKANTA", label=lbl_bk)
    # Ladda om till session
    _load_cfg_and_labels()
    st.success("Inställningar + etiketter sparade ✅")

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
        fee  = float(r.get("Avgift", _get_cfg_float("avgift_usd", 30.0)) or 0)
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
    startd = _get_cfg_date("startdatum", date.today())
    d = startd + timedelta(days=scen_nummer - 1)
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

lbl_p  = f"{_lbl('MAX_PAPPAN','Pappans vänner')} (max {_get_cfg_int('MAX_PAPPAN',10)})"
lbl_g  = f"{_lbl('MAX_GRANNAR','Grannar')} (max {_get_cfg_int('MAX_GRANNAR',10)})"
lbl_nv = f"{_lbl('MAX_NILS_VANNER','Nils vänner')} (max {_get_cfg_int('MAX_NILS_VANNER',10)})"
lbl_nf = f"{_lbl('MAX_NILS_FAMILJ','Nils familj')} (max {_get_cfg_int('MAX_NILS_FAMILJ',10)})"
lbl_bk = f"{_lbl('MAX_BEKANTA','Bekanta')} (max {_get_cfg_int('MAX_BEKANTA',10)})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")
bekanta        = st.number_input(lbl_bk, min_value=0, step=1, value=0, key="input_bekanta")

eskilstuna_killar = st.number_input("Eskilstuna killar", min_value=0, step=1, value=0, key="input_eskilstuna")

nils = st.number_input("Nils", min_value=0, step=1, value=0)

# Varningsflaggor vid överskridna max (gäller inte Eskilstuna killar)
if pappans_vänner > _get_cfg_int("MAX_PAPPAN",10):
    st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {_get_cfg_int('MAX_PAPPAN',10)}</span>", unsafe_allow_html=True)
if grannar > _get_cfg_int("MAX_GRANNAR",10):
    st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {_get_cfg_int('MAX_GRANNAR',10)}</span>", unsafe_allow_html=True)
if nils_vänner > _get_cfg_int("MAX_NILS_VANNER",10):
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {_get_cfg_int('MAX_NILS_VANNER',10)}</span>", unsafe_allow_html=True)
if nils_familj > _get_cfg_int("MAX_NILS_FAMILJ",10):
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {_get_cfg_int('MAX_NILS_FAMILJ',10)}</span>", unsafe_allow_html=True)
if bekanta > _get_cfg_int("MAX_BEKANTA",10):
    st.markdown(f"<span style='color:#d00'>⚠️ {bekanta} > max {_get_cfg_int('MAX_BEKANTA',10)}</span>", unsafe_allow_html=True)

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
    "Avgift": float(_get_cfg_float("avgift_usd", 30.0)),
}

def _calc_preview(grund):
    try:
        if callable(calc_row_values):
            return calc_row_values(grund, rad_datum, _get_cfg_date("födelsedatum", date(1990,1,1)), _get_cfg_time("starttid", time(7,0)))
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

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {_get_cfg_time('starttid', time(7,0))})")

# ===== Prenumeranter & Ekonomi (live) =====
st.markdown("#### 📈 Prenumeranter & Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", _get_cfg_float('avgift_usd',30.0))))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Kostnad män", _usd(preview.get("Intäkt män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Intäkt Företaget", _usd(preview.get("Intäkt Företaget", 0)))
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ============== Bonus: uppdatera pool vid SPARA (binomial 5% av Prenumeranter) ==============
def _inc_bonus_pool(n_add: int):
    # Öka BONUS_POOL_TOTAL och BONUS_REMAINING (impl via TOTAL - PARTICIPATED)
    total = _get_cfg_int("BONUS_POOL_TOTAL", 0) + int(n_add)
    _update_settings_row("BONUS_POOL_TOTAL", value=total)
    # ladda om
    _load_cfg_and_labels()

def _get_bonus_numbers():
    total = _get_cfg_int("BONUS_POOL_TOTAL", 0)
    used  = _get_cfg_int("BONUS_PARTICIPATED", 0)
    remaining = max(0, total - used)
    return total, used, remaining

def _use_bonus(n_use: int):
    used  = _get_cfg_int("BONUS_PARTICIPATED", 0) + int(n_use)
    _update_settings_row("BONUS_PARTICIPATED", value=used)
    _load_cfg_and_labels()

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
        base.setdefault("Avgift", float(_get_cfg_float("avgift_usd",30.0)))
        ber = calc_row_values(base, rad_datum, _get_cfg_date("födelsedatum", date(1990,1,1)), _get_cfg_time("starttid", time(7,0)))
        ber["Datum"] = rad_datum.isoformat()

        # Bonus killar (5% chans per prenumerant), sparas på raden + upp i poolen
        pren = int(ber.get("Prenumeranter", 0) or 0)
        bonus_killar = 0
        for _ in range(pren):
            if random.random() < 0.05:
                bonus_killar += 1
        ber["Bonus killar"] = bonus_killar
        ber.setdefault("Bonus deltagit", 0)
        if bonus_killar > 0:
            _inc_bonus_pool(bonus_killar)

    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state.ROW_COUNT += 1

    ålder = rad_datum.year - _get_cfg_date("födelsedatum", date(1990,1,1)).year - ((rad_datum.month,rad_datum.day)<(_get_cfg_date("födelsedatum", date(1990,1,1)).month,_get_cfg_date("födelsedatum", date(1990,1,1)).day))
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")

def _apply_auto_max_and_save(pending):
    # Uppdatera max i Inställningar
    for f, info in pending["over_max"].items():
        key = info["max_key"]
        _update_settings_row(key, value=int(info["new_value"]))
    # Ladda om till session
    _load_cfg_and_labels()

    grund = pending["grund"]
    rad_datum = _parse_date_for_save(pending["rad_datum"])
    veckodag = pending["veckodag"]
    _save_row(grund, rad_datum, veckodag)

save_clicked = st.button("💾 Spara raden")
if save_clicked:
    over_max = {}
    if pappans_vänner > _get_cfg_int("MAX_PAPPAN",10):
        over_max["Pappans vänner"] = {"current_max": _get_cfg_int("MAX_PAPPAN",10), "new_value": pappans_vänner, "max_key": "MAX_PAPPAN"}
    if grannar > _get_cfg_int("MAX_GRANNAR",10):
        over_max["Grannar"] = {"current_max": _get_cfg_int("MAX_GRANNAR",10), "new_value": grannar, "max_key": "MAX_GRANNAR"}
    if nils_vänner > _get_cfg_int("MAX_NILS_VANNER",10):
        over_max["Nils vänner"] = {"current_max": _get_cfg_int("MAX_NILS_VANNER",10), "new_value": nils_vänner, "max_key": "MAX_NILS_VANNER"}
    if nils_familj > _get_cfg_int("MAX_NILS_FAMILJ",10):
        over_max["Nils familj"] = {"current_max": _get_cfg_int("MAX_NILS_FAMILJ",10), "new_value": nils_familj, "max_key": "MAX_NILS_FAMILJ"}
    if bekanta > _get_cfg_int("MAX_BEKANTA",10):
        over_max["Bekanta"] = {"current_max": _get_cfg_int("MAX_BEKANTA",10), "new_value": bekanta, "max_key": "MAX_BEKANTA"}

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

# --- Visa bonusstatus ---
bt, bu, br = _get_bonus_numbers()
st.caption(f"🎁 Bonuspool – total: {bt}, deltagit: {bu}, kvar: {br}")

# --- Vila på jobbet ---
if st.button("➕ Skapa 'Vila på jobbet'-rad"):
    try:
        scen_num = next_scene_number()
        rad_datum2, veckodag2 = datum_och_veckodag_för_scen(scen_num)

        pv = _rand_40_60_of_max(_get_cfg_int("MAX_PAPPAN",0))
        gr = _rand_40_60_of_max(_get_cfg_int("MAX_GRANNAR",0))
        nv = _rand_40_60_of_max(_get_cfg_int("MAX_NILS_VANNER",0))
        nf = _rand_40_60_of_max(_get_cfg_int("MAX_NILS_FAMILJ",0))
        bk = _rand_40_60_of_max(_get_cfg_int("MAX_BEKANTA",0))
        esk = _rand_eskilstuna_20_40()

        # 40% av bonus kvar deltar här
        _, _, bonus_remaining = _get_bonus_numbers()
        bonus_use = int(math.floor(bonus_remaining * 0.40))
        if bonus_use < 0: bonus_use = 0

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
            "Bonus deltagit": bonus_use,
            "Avgift": float(_get_cfg_float("avgift_usd", 30.0)),
        }
        _save_row(grund_vila, rad_datum2, veckodag2)

        if bonus_use > 0:
            _use_bonus(bonus_use)

    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

# --- Vila i hemmet (7 rader) — fördela återstående bonus över dag 1–5 ---
if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
    try:
        start_scene = next_scene_number()

        # Nils 50/45/5 (ettor dag 1–6)
        r = random.random()
        if r < 0.50:
            ones_count = 0
        elif r < 0.95:
            ones_count = 1
        else:
            ones_count = 2
        nils_one_offsets = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

        # Bonus kvar att fördela över dag 1–5
        _, _, bonus_remaining = _get_bonus_numbers()
        per_day_bonus = [0]*7
        if bonus_remaining > 0:
            per = bonus_remaining // 5
            for i in range(5):
                per_day_bonus[i] = per

        total_bonus_used_this_block = 0

        for offset in range(7):
            scen_num = start_scene + offset
            rad_d, veckod = datum_och_veckodag_för_scen(scen_num)

            if offset <= 4:
                pv = _rand_40_60_of_max(_get_cfg_int("MAX_PAPPAN", 0))
                gr = _rand_40_60_of_max(_get_cfg_int("MAX_GRANNAR", 0))
                nv = _rand_40_60_of_max(_get_cfg_int("MAX_NILS_VANNER", 0))
                nf = _rand_40_60_of_max(_get_cfg_int("MAX_NILS_FAMILJ", 0))
                bk = _rand_40_60_of_max(_get_cfg_int("MAX_BEKANTA", 0))
                esk = _rand_eskilstuna_20_40()
            else:
                pv = gr = nv = nf = bk = 0
                esk = _rand_eskilstuna_20_40()

            sv = 1 if offset == 6 else 0

            if offset == 6:
                nils_val = 0
            else:
                nils_val = 1 if offset in nils_one_offsets else 0

            bonus_use = per_day_bonus[offset] if offset <= 4 else 0
            total_bonus_used_this_block += bonus_use

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
                "Bonus deltagit": bonus_use,
                "Avgift": float(_get_cfg_float("avgift_usd", 30.0)),
            }
            _save_row(grund_home, rad_d, veckod)

        if total_bonus_used_this_block > 0:
            _use_bonus(total_bonus_used_this_block)

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
