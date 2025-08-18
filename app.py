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
        h += 1; m = 0
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
WORKSHEET_TITLE = "Data"
SETTINGS_SHEET  = "Inställningar"

@st.cache_resource(show_spinner=False)
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def resolve_spreadsheet():
    client = get_client()
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

@st.cache_resource(show_spinner=False)
def _get_ws_cached(title: str):
    """Cache:ad worksheet-hämtning. Körs endast vid first load / cache-invalid."""
    ss = resolve_spreadsheet()
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=200 if title==SETTINGS_SHEET else 3000, cols=100)
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
                ["PERSONAL_PROCENT", "10.0", "Personal deltagit (% av total)"],
                ["ESK_MIN", "20", "Eskilstuna min"],
                ["ESK_MAX", "40", "Eskilstuna max"],
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

# Hämta cache:ade referenser EN gång
sheet       = _get_ws_cached(WORKSHEET_TITLE)
settings_ws = _get_ws_cached(SETTINGS_SHEET)

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
    # Körs vid first load (cache:ad sheet). Inga fler anrop efteråt.
    header = _retry_call(sheet.row_values, 1)
    if not header:
        _retry_call(sheet.insert_row, DEFAULT_COLUMNS, 1)
        st.session_state["COLUMNS"] = DEFAULT_COLUMNS
        return
    missing = [c for c in DEFAULT_COLUMNS if c not in header]
    if missing:
        from gspread.utils import rowcol_to_a1
        new_header = header + missing
        end_cell = rowcol_to_a1(1, len(new_header))
        _retry_call(sheet.update, f"A1:{end_cell}", [new_header])
        st.session_state["COLUMNS"] = new_header
    else:
        st.session_state["COLUMNS"] = header

ensure_header_and_migrate()
KOLUMNER = st.session_state["COLUMNS"]

# ============================== Inställningar (persistent) ==============================
def _settings_as_dict():
    rows = _retry_call(settings_ws.get_all_records)  # Körs vid sidstart/rerun, men cache:ad ws → snabb
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
    # Skrivs ENDAST när du trycker på "Spara inställningar".
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

def _Lmap(labels_map: dict, default_text: str) -> str:
    return labels_map.get(default_text, default_text)

CFG_RAW, LABELS = _settings_as_dict()

def _init_cfg_defaults_from_settings():
    st.session_state.setdefault("CFG", {})
    C = st.session_state["CFG"]

    def _get(k, fallback): return CFG_RAW.get(k, fallback)

    # Datum/tid
    try:    C["startdatum"] = datetime.fromisoformat(_get("startdatum", date.today().isoformat())).date()
    except: C["startdatum"] = date.today()
    try:
        hh, mm = str(_get("starttid", "07:00")).split(":")
        C["starttid"] = time(int(hh), int(mm))
    except Exception:
        C["starttid"] = time(7,0)
    try:    C["födelsedatum"] = datetime.fromisoformat(_get("födelsedatum", "1990-01-01")).date()
    except: C["födelsedatum"] = date(1990,1,1)

    # Hårda siffror
    C["MAX_PAPPAN"]       = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]      = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"]  = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"]  = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]      = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]       = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"]       = int(float(_get("PROD_STAFF", 800)))
    C["PERSONAL_PROCENT"] = float(_get("PERSONAL_PROCENT", 10.0))
    C["ESK_MIN"]          = int(float(_get("ESK_MIN", 20)))
    C["ESK_MAX"]          = int(float(_get("ESK_MAX", 40)))

    # Bonus-räknare
    C["BONUS_TOTAL"] = int(float(_get("BONUS_TOTAL", 0)))
    C["BONUS_USED"]  = int(float(_get("BONUS_USED", 0)))
    C["BONUS_LEFT"]  = int(float(_get("BONUS_LEFT", 0)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ================================ SIDOPANEL ====================================
st.sidebar.header("Inställningar")

MIN_FOD   = date(1970, 1, 1)
MIN_START = date(1990, 1, 1)

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    startdatum = st.date_input("Historiskt startdatum", value=_clamp(CFG["startdatum"], MIN_START, date(2100,1,1)))
    starttid   = st.time_input("Starttid", value=CFG["starttid"])
    födelsedatum = st.date_input(
        _Lmap(LABELS, "Malins födelsedatum"),
        value=_clamp(CFG["födelsedatum"], MIN_FOD, date.today()),
        min_value=MIN_FOD, max_value=date.today()
    )

    # Maxvärden
    max_p  = st.number_input(f"Max {_Lmap(LABELS, 'Pappans vänner')}", min_value=0, step=1, value=int(CFG["MAX_PAPPAN"]))
    max_g  = st.number_input(f"Max {_Lmap(LABELS, 'Grannar')}",        min_value=0, step=1, value=int(CFG["MAX_GRANNAR"]))
    max_nv = st.number_input(f"Max {_Lmap(LABELS, 'Nils vänner')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_VANNER"]))
    max_nf = st.number_input(f"Max {_Lmap(LABELS, 'Nils familj')}",    min_value=0, step=1, value=int(CFG["MAX_NILS_FAMILJ"]))
    max_bk = st.number_input(f"Max {_Lmap(LABELS, 'Bekanta')}",        min_value=0, step=1, value=int(CFG["MAX_BEKANTA"]))

    # Produktionspersonal: total + procent (utan slider)
    prod_staff_total = st.number_input("Produktionspersonal (fast antal)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    personal_proc    = st.number_input("Personal deltagit (% av total personal)", min_value=0.0, max_value=100.0, step=0.1, value=float(CFG["PERSONAL_PROCENT"]))
    st.caption(f"→ Standardvärde i 'Personal deltagit' blir {int(round(prod_staff_total * (personal_proc/100.0)))}")

    # Eskilstuna intervall
    esk_min = st.number_input("Eskilstuna min", min_value=0, step=1, value=int(CFG["ESK_MIN"]))
    esk_max = st.number_input("Eskilstuna max", min_value=0, step=1, value=int(CFG["ESK_MAX"]))
    if esk_max < esk_min:
        st.warning("Eskilstuna max kan inte vara mindre än min.")

    avgift_input = st.number_input("Avgift (USD, per ny rad)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))

    st.markdown("**Etiketter (påverkar endast visning)**")
    lab_p   = st.text_input("Etikett: Pappans vänner", value=_Lmap(LABELS, "Pappans vänner"))
    lab_g   = st.text_input("Etikett: Grannar", value=_Lmap(LABELS, "Grannar"))
    lab_nv  = st.text_input("Etikett: Nils vänner", value=_Lmap(LABELS, "Nils vänner"))
    lab_nf  = st.text_input("Etikett: Nils familj", value=_Lmap(LABELS, "Nils familj"))
    lab_bk  = st.text_input("Etikett: Bekanta", value=_Lmap(LABELS, "Bekanta"))
    lab_esk = st.text_input("Etikett: Eskilstuna killar", value=_Lmap(LABELS, "Eskilstuna killar"))
    lab_man = st.text_input("Etikett: Män", value=_Lmap(LABELS, "Män"))
    lab_sva = st.text_input("Etikett: Svarta", value=_Lmap(LABELS, "Svarta"))
    lab_kann= st.text_input("Etikett: Känner", value=_Lmap(LABELS, "Känner"))
    lab_person = st.text_input("Etikett: Personal deltagit", value=_Lmap(LABELS, "Personal deltagit"))
    lab_bonus  = st.text_input("Etikett: Bonus killar", value=_Lmap(LABELS, "Bonus killar"))
    lab_bonusd = st.text_input("Etikett: Bonus deltagit", value=_Lmap(LABELS, "Bonus deltagit"))
    lab_mfd    = st.text_input("Etikett: Malins födelsedatum", value=_Lmap(LABELS, "Malins födelsedatum"))

    if st.button("💾 Spara inställningar"):
        _save_setting("startdatum", startdatum.isoformat())
        _save_setting("starttid", starttid.strftime("%H:%M"))
        _save_setting("födelsedatum", födelsedatum.isoformat(), label=lab_mfd)

        _save_setting("MAX_PAPPAN", str(int(max_p)), label=lab_p)
        _save_setting("MAX_GRANNAR", str(int(max_g)), label=lab_g)
        _save_setting("MAX_NILS_VANNER", str(int(max_nv)), label=lab_nv)
        _save_setting("MAX_NILS_FAMILJ", str(int(max_nf)), label=lab_nf)
        _save_setting("MAX_BEKANTA", str(int(max_bk)), label=lab_bk)

        _save_setting("PROD_STAFF", str(int(prod_staff_total)))
        _save_setting("PERSONAL_PROCENT", str(float(personal_proc)))
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

        st.success("Inställningar sparade ✅")
        st.experimental_rerun()

# =============================== MENY & VY ===============================
st.sidebar.title("Meny")
view = st.sidebar.radio("Välj vy", ["Produktion", "Statistik"], index=0)

# =============================== STATISTIK ===============================
if view == "Statistik":
    st.header("📊 Statistik")
    try:
        rows = _retry_call(sheet.get_all_records)
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")
        st.stop()

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

    antal_scener = 0
    privat_gb_cnt = 0
    totalt_man_sum = 0
    bonus_deltagit_sum = 0
    personal_deltagit_sum = 0
    svarta_like_sum = 0
    tot_for_andel_svarta = 0

    from datetime import timedelta as _td
    total_pren = 0
    cutoff = date.today() - _td(days=30)
    aktiva_pren = 0

    for r in rows:
        typ = (r.get("Typ") or "").strip()
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

        if typ not in ("Vila på jobbet", "Vila i hemmet"):
            total_pren += _safe_int(r.get("Prenumeranter", 0), 0)
            d = _parse_iso_date(r.get("Datum", ""))
            if d and d >= cutoff:
                aktiva_pren += _safe_int(r.get("Prenumeranter", 0), 0)

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
    st.subheader("👥 Prenumeranter")
    pc1, pc2 = st.columns(2)
    with pc1: st.metric("Prenumeranter (totalt)", int(total_pren))
    with pc2: st.metric("Aktiva prenumeranter (30 dagar)", int(aktiva_pren))

    st.stop()

# =============================== PRODUKTION ===============================
st.header("🧪 Produktion – ny rad")

# ----- Scenhelpers -----
def _init_row_count():
    if "ROW_COUNT" not in st.session_state:
        try:
            vals = _retry_call(sheet.col_values, 1)  # kol A = Datum
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

# ----- Scen-väljare (inget spar – bara fyll inputs) -----
scenario = st.selectbox(
    "Välj scenario att fylla inmatning med (inget spar förrän du trycker Spara):",
    ["Ny scen", "Vila på jobbet", "Vila i hemmet (7 dagar)", "Slumpa scen vit", "Slumpa scen svart"],
    index=0
)

# ----- Input i ÖNSKAD ORDNING -----
scen = next_scene_number()
rad_datum, veckodag = datum_och_veckodag_för_scen(scen)

colA, colB, colC, colD = st.columns(4)

with colA:
    män    = st.number_input(_Lmap(LABELS,"Män"),    min_value=0, step=1, value=0, key="in_man")
    fitta  = st.number_input("Fitta",  min_value=0, step=1, value=0, key="in_fitta")
    dp     = st.number_input("DP",     min_value=0, step=1, value=0, key="in_dp")
    dap    = st.number_input("DAP",    min_value=0, step=1, value=0, key="in_dap")
with colB:
    svarta = st.number_input(_Lmap(LABELS,"Svarta"), min_value=0, step=1, value=0, key="in_svarta")
    rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=0, key="in_rumpa")
    dpp    = st.number_input("DPP",    min_value=0, step=1, value=0, key="in_dpp")
    tap    = st.number_input("TAP",    min_value=0, step=1, value=0, key="in_tap")
with colC:
    pappans_vänner = st.number_input(f"{_Lmap(LABELS,'Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})", min_value=0, step=1, value=0, key="in_pappan")
    grannar        = st.number_input(f"{_Lmap(LABELS,'Grannar')} (max {int(CFG['MAX_GRANNAR'])})", min_value=0, step=1, value=0, key="in_grannar")
    nils_vänner    = st.number_input(f"{_Lmap(LABELS,'Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})", min_value=0, step=1, value=0, key="in_nils_vanner")
    nils_familj    = st.number_input(f"{_Lmap(LABELS,'Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})", min_value=0, step=1, value=0, key="in_nils_familj")
with colD:
    bekanta            = st.number_input(_Lmap(LABELS,"Bekanta"), min_value=0, step=1, value=0, key="in_bekanta")
    eskilstuna_killar  = st.number_input(_Lmap(LABELS,"Eskilstuna killar"), min_value=0, step=1, value=0, key="in_esk")
    bonus_deltagit     = st.number_input(_Lmap(LABELS,"Bonus deltagit"), min_value=0, step=1, value=0, key="in_bonus_deltagit")
    personal_deltagit  = st.number_input(_Lmap(LABELS,"Personal deltagit"),
                                         min_value=0, step=1,
                                         value=int(round(int(CFG["PROD_STAFF"])*float(CFG["PERSONAL_PROCENT"])/100.0)),
                                         key="in_personal")

colE, colF, colG = st.columns(3)
with colE:
    älskar    = st.number_input("Älskar", min_value=0, step=1, value=0, key="in_alskar")
    sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=0, key="in_sover")
with colF:
    tid_s  = st.number_input("Tid S (sek)", min_value=0, step=1, value=60, key="in_tid_s")
    tid_d  = st.number_input("Tid D (sek)", min_value=0, step=1, value=60, key="in_tid_d")
with colG:
    vila     = st.number_input("Vila (sek)",  min_value=0, step=1, value=7, key="in_vila")
    dt_tid   = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=60, key="in_dt_tid")
    dt_vila  = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=3,  key="in_dt_vila")

# ===== Max-varningar (endast UI) =====
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

# ===== Scenario-tillämpning (fyll bara inputs) =====
def _esk_rand():
    lo = int(CFG.get("ESK_MIN", 20))
    hi = int(CFG.get("ESK_MAX", 40))
    if hi < lo: hi = lo
    return random.randint(lo, hi)

def _get_min_max(colname: str):
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

def apply_scenario_fill(choice: str):
    # All fyllning görs i session_state → ingen skrivning till Sheets
    if choice == "Ny scen":
        pass  # lämna som är

    elif choice == "Vila på jobbet":
        st.session_state["in_man"] = 0
        st.session_state["in_svarta"] = 0
        st.session_state["in_fitta"] = 0
        st.session_state["in_rumpa"] = 0
        st.session_state["in_dp"] = 0
        st.session_state["in_dpp"] = 0
        st.session_state["in_dap"] = 0
        st.session_state["in_tap"] = 0
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"] = 1
        # 40–60% av max för källor
        def _rand_40_60(mx): 
            mx = int(mx); 
            lo = int(round(mx*0.40)); hi = int(round(mx*0.60))
            return random.randint(lo, hi) if hi>=lo else 0
        st.session_state["in_pappan"] = _rand_40_60(CFG["MAX_PAPPAN"])
        st.session_state["in_grannar"] = _rand_40_60(CFG["MAX_GRANNAR"])
        st.session_state["in_nils_vanner"] = _rand_40_60(CFG["MAX_NILS_VANNER"])
        st.session_state["in_nils_familj"] = _rand_40_60(CFG["MAX_NILS_FAMILJ"])
        st.session_state["in_bekanta"] = _rand_40_60(CFG["MAX_BEKANTA"])
        st.session_state["in_esk"] = _esk_rand()
        st.session_state["in_personal"] = int(round(int(CFG["PROD_STAFF"])*float(CFG["PERSONAL_PROCENT"])/100.0))

    elif choice == "Vila i hemmet (7 dagar)":
        st.info("Denna knapp skapar en 7-dagarsbundle när du sparar. Förhandsvisningen visar bara aktuell rad. (Vi bygger själva bundle-sparningen i Spara-rutinen nedan.)")

    elif choice == "Slumpa scen vit":
        # slumpa från historikens min..max per kolumn
        for key, col in [
            ("in_man","Män"),("in_fitta","Fitta"),("in_rumpa","Rumpa"),
            ("in_dp","DP"),("in_dpp","DPP"),("in_dap","DAP"),("in_tap","TAP")
        ]:
            mn,mx = _get_min_max(col); st.session_state[key] = random.randint(mn,mx) if mx>=mn else 0
        for key, col in [
            ("in_pappan","Pappans vänner"),("in_grannar","Grannar"),
            ("in_nils_vanner","Nils vänner"),("in_nils_familj","Nils familj"),("in_bekanta","Bekanta")
        ]:
            mn,mx = _get_min_max(col); st.session_state[key] = random.randint(mn,mx) if mx>=mn else 0
        st.session_state["in_esk"] = _esk_rand()
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"] = 1
        st.session_state["in_personal"] = int(round(int(CFG["PROD_STAFF"])*float(CFG["PERSONAL_PROCENT"])/100.0))

    elif choice == "Slumpa scen svart":
        for key, col in [
            ("in_fitta","Fitta"),("in_rumpa","Rumpa"),
            ("in_dp","DP"),("in_dpp","DPP"),("in_dap","DAP"),("in_tap","TAP")
        ]:
            mn,mx = _get_min_max(col); st.session_state[key] = random.randint(mn,mx) if mx>=mn else 0
        st.session_state["in_svarta"] = random.randint(*_get_min_max("Svarta"))
        # övriga källor 0
        st.session_state["in_man"] = 0
        st.session_state["in_pappan"] = 0
        st.session_state["in_grannar"] = 0
        st.session_state["in_nils_vanner"] = 0
        st.session_state["in_nils_familj"] = 0
        st.session_state["in_bekanta"] = 0
        st.session_state["in_esk"] = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"] = 1
        st.session_state["in_personal"] = int(round(int(CFG["PROD_STAFF"])*float(CFG["PERSONAL_PROCENT"])/100.0))

if st.button("⚡ Fyll enligt valt scenario"):
    apply_scenario_fill(scenario)
    st.experimental_rerun()

# ===== Live-förhandsberäkning (minne) =====
grund_preview = {
    "Typ": "" if scenario=="Ny scen" else scenario.replace(" (7 dagar)",""),
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
    "Älskar": älskar, "Sover med": sover_med,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
    "Bonus killar": 0,  # bonusantal beräknas i beräkningar från prenumeranter
    "Bonus deltagit": bonus_deltagit,
    "Personal deltagit": personal_deltagit,
    "Nils": 0,
    "Avgift": float(CFG["avgift_usd"]),
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

# Malins ålder (live)
try:
    alder = rad_datum.year - CFG["födelsedatum"].year - ((rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day))
except Exception:
    alder = "-"

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
col1, col2 = st.columns(2)
with col1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin)", str(alder))
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
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ===== Spara =====
def _save_row(grund, rad_datum, veckodag):
    try:
        base = dict(grund)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return False

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    st.session_state.ROW_COUNT += 1

    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {alder} år, Klockan {ber.get('Klockan','-')}")
    return True

def _auto_max_overages():
    over_max = {}
    if pappans_vänner > int(CFG["MAX_PAPPAN"]):
        over_max[_Lmap(LABELS,'Pappans vänner')] = {"current_max": int(CFG["MAX_PAPPAN"]), "new_value": pappans_vänner, "max_key": "MAX_PAPPAN"}
    if grannar > int(CFG["MAX_GRANNAR"]):
        over_max[_Lmap(LABELS,'Grannar')] = {"current_max": int(CFG["MAX_GRANNAR"]), "new_value": grannar, "max_key": "MAX_GRANNAR"}
    if nils_vänner > int(CFG["MAX_NILS_VANNER"]):
        over_max[_Lmap(LABELS,'Nils vänner')] = {"current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": nils_vänner, "max_key": "MAX_NILS_VANNER"}
    if nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
        over_max[_Lmap(LABELS,'Nils familj')] = {"current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": nils_familj, "max_key": "MAX_NILS_FAMILJ"}
    if bekanta > int(CFG["MAX_BEKANTA"]):
        over_max[_Lmap(LABELS,'Bekanta')] = {"current_max": int(CFG["MAX_BEKANTA"]), "new_value": bekanta, "max_key": "MAX_BEKANTA"}
    return over_max

def _apply_auto_max_and_save(grund, over_max):
    for _, info in over_max.items():
        key = info["max_key"]; new_val = int(info["new_value"])
        _save_setting(key, str(new_val)); CFG[key] = new_val
    d, v = datum_och_veckodag_för_scen(next_scene_number())
    _save_row(grund, d, v)

save_clicked = st.button("💾 Spara raden")
if save_clicked:
    over_max = _auto_max_overages()
    if over_max:
        st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara raden?")
        for f, info in over_max.items():
            st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Ja, uppdatera max och spara"):
                _apply_auto_max_and_save(grund_preview, over_max)
                st.experimental_rerun()
        with c2:
            if st.button("✋ Nej, avbryt"):
                st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# ===== Visa & radera =====
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
            st.experimental_rerun()
    else:
        st.caption("Ingen datarad att ta bort.")
except Exception as e:
    st.warning(f"Kunde inte ta bort rad: {e}")
