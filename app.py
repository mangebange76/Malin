# app.py
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
st.title("Malin-produktionsapp")

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

# =============================== Google Sheets =================================
@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

client = get_client()

@st.cache_resource(show_spinner=False)
def resolve_sheet():
    """Öppna arket via ID eller URL (ingen Drive-API krävs)."""
    sid = st.secrets.get("GOOGLE_SHEET_ID", "").strip() if "GOOGLE_SHEET_ID" in st.secrets else ""
    if sid:
        st.caption("🆔 Öppnar via GOOGLE_SHEET_ID…")
        return _retry_call(client.open_by_key, sid).sheet1

    url = st.secrets.get("SHEET_URL", "").strip() if "SHEET_URL" in st.secrets else ""
    if url:
        st.caption("🔗 Öppnar via SHEET_URL…")
        return _retry_call(client.open_by_url, url).sheet1

    qp = ""
    try:
        qp = st.experimental_get_query_params().get("sheet", [""])[0]
    except Exception:
        pass
    if qp:
        st.caption("🔎 Öppnar via query-param 'sheet'…")
        return (_retry_call(client.open_by_url, qp).sheet1
                if qp.startswith("http")
                else _retry_call(client.open_by_key, qp).sheet1)

    st.error("Lägg in GOOGLE_SHEET_ID eller SHEET_URL i Secrets (eller ?sheet=<url|id>).")
    st.stop()

sheet = resolve_sheet()

# =========================== Header-säkring / migration =========================
DEFAULT_COLUMNS = [
    "Datum",               # används för 30-dagars
    "Typ",                 # "Vila på jobbet", "Vila i hemmet" eller tomt
    "Veckodag","Scen","Män","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","Summa S","Summa D","Summa TP","Summa Vila",
    "Tid Älskar (sek)","Tid Älskar",
    "Tid Sover med (sek)","Tid Sover med",
    "Summa tid","Summa tid (sek)",
    "Tid per kille (sek)","Tid per kille",
    "Klockan","Älskar","Sover med","Känner","Pappans vänner","Grannar",
    "Nils vänner","Nils familj","Totalt Män","Tid kille","Nils",
    "Hångel (sek/kille)","Hångel (m:s/kille)",
    "Suger","Suger per kille (sek)",
    "Hårdhet","Prenumeranter","Avgift","Intäkter",
    "Kostnad män","Intäkt Känner","Lön Malin","Intäkt Företaget","Vinst",
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

    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man = 0
    summa_for_snitt_scener = 0
    summa_privat_gb_kanner = 0

    for r in rows:
        man = _safe_int(r.get("Män", 0), 0)
        kanner = _safe_int(r.get("Känner", 0), 0)

        # Antal scener + summor för snitt (gäller bara rader där Män > 0)
        if man > 0:
            antal_scener += 1
            totalt_man += man
            summa_for_snitt_scener += (man + kanner)

        # Privat GB-rader (Män = 0 och Känner > 0)
        if man == 0 and kanner > 0:
            privat_gb_cnt += 1
            summa_privat_gb_kanner += kanner

    # Snitt scener
    snitt_scener = round(summa_for_snitt_scener / antal_scener, 2) if antal_scener > 0 else 0.0
    # Snitt Privat GB
    snitt_privat_gb = round(summa_privat_gb_kanner / privat_gb_cnt, 2) if privat_gb_cnt > 0 else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Antal scener", antal_scener)
    with c2:
        st.metric("Privat GB", privat_gb_cnt)
    with c3:
        st.metric("Totalt antal män", totalt_man)
    with c4:
        st.metric("Snitt scener", snitt_scener)
    with c5:
        st.metric("Snitt Privat GB", snitt_privat_gb)

    # Stoppa här så inte produktion-UI:t renderas
    st.stop()

# ================================ Sidopanel (Produktion) ====================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

def _init_cfg_defaults():
    st.session_state.setdefault("CFG", {})
    st.session_state["CFG"].setdefault("startdatum", date.today())
    st.session_state["CFG"].setdefault("starttid", time(7, 0))
    st.session_state["CFG"].setdefault("födelsedatum", date(1990,1,1))
    st.session_state["CFG"].setdefault("MAX_PAPPAN", 10)
    st.session_state["CFG"].setdefault("MAX_GRANNAR", 10)
    st.session_state["CFG"].setdefault("MAX_NILS_VANNER", 10)
    st.session_state["CFG"].setdefault("MAX_NILS_FAMILJ", 10)
    st.session_state["CFG"].setdefault("avgift_usd", 30.0)

_init_cfg_defaults()
CFG = st.session_state["CFG"]

startdatum = st.sidebar.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
starttid   = st.sidebar.time_input("Starttid", value=CFG["starttid"])
födelsedatum = st.sidebar.date_input(
    "Malins födelsedatum",
    value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
    min_value=MIN_FOD, max_value=date.today()
)

st.sidebar.subheader("Maxvärden (Auto-Max med varning)")
max_p  = st.sidebar.number_input("Max Pappans vänner", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
max_g  = st.sidebar.number_input("Max Grannar",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
max_nv = st.sidebar.number_input("Max Nils vänner",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
max_nf = st.sidebar.number_input("Max Nils familj",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))

st.sidebar.subheader("Pris per prenumerant (gäller NÄSTA rad)")
avgift_input = st.sidebar.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

if st.sidebar.button("💾 Spara inställningar"):
    CFG.update({
        "startdatum": startdatum,
        "starttid": starttid,
        "födelsedatum": födelsedatum,
        "MAX_PAPPAN": int(max_p),
        "MAX_GRANNAR": int(max_g),
        "MAX_NILS_VANNER": int(max_nv),
        "MAX_NILS_FAMILJ": int(max_nf),
        "avgift_usd": float(avgift_input),
    })
    st.session_state.update(
        MAX_PAPPAN=int(max_p),
        MAX_GRANNAR=int(max_g),
        MAX_NILS_VANNER=int(max_nv),
        MAX_NILS_FAMILJ=int(max_nf),
    )
    st.success("Inställningar sparade ✅")

# Se till att max finns i session (för etiketter)
st.session_state.setdefault("MAX_PAPPAN",      int(CFG["MAX_PAPPAN"]))
st.session_state.setdefault("MAX_GRANNAR",     int(CFG["MAX_GRANNAR"]))
st.session_state.setdefault("MAX_NILS_VANNER", int(CFG["MAX_NILS_VANNER"]))
st.session_state.setdefault("MAX_NILS_FAMILJ", int(CFG["MAX_NILS_FAMILJ"]))

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
        fee  = float(r.get("Avgift", 30) or 0)
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
    d = startdatum + timedelta(days=scen_nummer - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# ============================ Inmatning (live-fält) ============================
st.subheader("➕ Lägg till ny händelse")

män   = st.number_input("Män",   min_value=0, step=1, value=0)
fitta = st.number_input("Fitta", min_value=0, step=1, value=0)
rumpa = st.number_input("Rumpa", min_value=0, step=1, value=0)
dp    = st.number_input("DP",    min_value=0, step=1, value=0)
dpp   = st.number_input("DPP",   min_value=0, step=1, value=0)
dap   = st.number_input("DAP",   min_value=0, step=1, value=0)
tap   = st.number_input("TAP",   min_value=0, step=1, value=0)

tid_s = st.number_input("Tid S (sek)", min_value=0, step=1, value=60)
tid_d = st.number_input("Tid D (sek)", min_value=0, step=1, value=60)
vila  = st.number_input("Vila (sek)",  min_value=0, step=1, value=7)

älskar    = st.number_input("Älskar",                min_value=0, step=1, value=0)
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0)

lbl_p  = f"Pappans vänner (max {st.session_state.MAX_PAPPAN})"
lbl_g  = f"Grannar (max {st.session_state.MAX_GRANNAR})"
lbl_nv = f"Nils vänner (max {st.session_state.MAX_NILS_VANNER})"
lbl_nf = f"Nils familj (max {st.session_state.MAX_NILS_FAMILJ})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=0, key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=0, key="input_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=0, key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=0, key="input_nils_familj")

nils = st.number_input("Nils", min_value=0, step=1, value=0)

# Varningsflaggor vid överskridna max
if pappans_vänner > st.session_state.MAX_PAPPAN:
    st.markdown(f"<span style='color:#d00'>⚠️ {pappans_vänner} > max {st.session_state.MAX_PAPPAN}</span>", unsafe_allow_html=True)
if grannar > st.session_state.MAX_GRANNAR:
    st.markdown(f"<span style='color:#d00'>⚠️ {grannar} > max {st.session_state.MAX_GRANNAR}</span>", unsafe_allow_html=True)
if nils_vänner > st.session_state.MAX_NILS_VANNER:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_vänner} > max {st.session_state.MAX_NILS_VANNER}</span>", unsafe_allow_html=True)
if nils_familj > st.session_state.MAX_NILS_FAMILJ:
    st.markdown(f"<span style='color:#d00'>⚠️ {nils_familj} > max {st.session_state.MAX_NILS_FAMILJ}</span>", unsafe_allow_html=True)

# ============================ Live-förhandsberäkning ===========================
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

grund_preview = {
    "Typ": "",  # vanlig händelse
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "Älskar": älskar, "Sover med": sover_med,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Nils": nils,
    "Avgift": float(CFG["avgift_usd"]),
}

def _calc_preview(grund):
    try:
        if callable(calc_row_values):
            return calc_row_values(grund, rad_datum, födelsedatum, starttid)
        else:
            st.error("Hittar inte berakningar.py eller berakna_radvarden().")
            return {}
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview(grund_preview)

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

def _usd(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "-"

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

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {starttid})")

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
        ber = calc_row_values(base, rad_datum, födelsedatum, starttid)
        ber["Datum"] = rad_datum.isoformat()
        if "Intäkt män" in ber:
            ber["Kostnad män"] = ber["Intäkt män"]
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state.ROW_COUNT += 1

    ålder = rad_datum.year - födelsedatum.year - ((rad_datum.month,rad_datum.day)<(födelsedatum.month,födelsedatum.day))
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber['Klockan']}")

def _apply_auto_max_and_save(pending):
    cfg = st.session_state.get("CFG", {})
    for _, info in pending["over_max"].items():
        new_val = int(info["new_value"])
        st.session_state[info["max_key"]] = new_val
        cfg[info["max_key"]] = new_val
    st.session_state["CFG"] = cfg

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

def _rand_30_50_of_max(mx: int) -> int:
    """Slumpa 30–50% av mx (heltal). Om mx <= 0 -> 0."""
    try:
        mx = int(mx)
    except Exception:
        mx = 0
    if mx <= 0:
        return 0
    lo = max(0, int(round(mx * 0.30)))
    hi = max(lo, int(round(mx * 0.50)))
    import random as _r
    return _r.randint(lo, hi)

# --- Vila på jobbet ---
if st.button("➕ Skapa 'Vila på jobbet'-rad"):
    try:
        scen_num = next_scene_number()
        rad_datum2, veckodag2 = datum_och_veckodag_för_scen(scen_num)

        pv = _rand_30_50_of_max(st.session_state.get("MAX_PAPPAN", 0))
        gr = _rand_30_50_of_max(st.session_state.get("MAX_GRANNAR", 0))
        nv = _rand_30_50_of_max(st.session_state.get("MAX_NILS_VANNER", 0))
        nf = _rand_30_50_of_max(st.session_state.get("MAX_NILS_FAMILJ", 0))

        grund_vila = {
            "Typ": "Vila på jobbet",
            "Veckodag": veckodag2, "Scen": scen_num,
            "Män": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
            "Tid S": 0, "Tid D": 0, "Vila": 0,
            "Älskar": 12, "Sover med": 1,
            "Pappans vänner": pv, "Grannar": gr,
            "Nils vänner": nv, "Nils familj": nf, "Nils": 0,
            "Avgift": float(CFG.get("avgift_usd", 30.0)),
        }
        _save_row(grund_vila, rad_datum2, veckodag2)
    except Exception as e:
        st.error(f"Misslyckades att skapa 'Vila på jobbet'-rad: {e}")

# --- Vila i hemmet (7 rader) ---
if st.button("🏠 Skapa 'Vila i hemmet' (7 dagar)"):
    try:
        start_scene = next_scene_number()
        for offset in range(7):
            scen_num = start_scene + offset
            rad_d, veckod = datum_och_veckodag_för_scen(scen_num)

            # Dag 1–5 slump, dag 6–7 ingen känner
            if offset <= 4:
                pv = _rand_30_50_of_max(st.session_state.get("MAX_PAPPAN", 0))
                gr = _rand_30_50_of_max(st.session_state.get("MAX_GRANNAR", 0))
                nv = _rand_30_50_of_max(st.session_state.get("MAX_NILS_VANNER", 0))
                nf = _rand_30_50_of_max(st.session_state.get("MAX_NILS_FAMILJ", 0))
            else:
                pv = gr = nv = nf = 0

            sv = 1 if offset == 6 else 0  # dag7 sover med

            grund_home = {
                "Typ": "Vila i hemmet",
                "Veckodag": veckod, "Scen": scen_num,
                "Män": 0, "Fitta": 0, "Rumpa": 0, "DP": 0, "DPP": 0, "DAP": 0, "TAP": 0,
                "Tid S": 0, "Tid D": 0, "Vila": 0,
                "Älskar": 6, "Sover med": sv,
                "Pappans vänner": pv, "Grannar": gr,
                "Nils vänner": nv, "Nils familj": nf, "Nils": 0,
                "Avgift": float(CFG.get("avgift_usd", 30.0)),
            }
            _save_row(grund_home, rad_d, veckod)

        st.success("✅ Skapade 7 'Vila i hemmet'-rader.")
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
