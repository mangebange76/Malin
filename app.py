import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
import time as _time
import random

# ====== extern beräkning ======
try:
    from berakningar import berakna_radvarden as calc_row_values
except Exception:
    calc_row_values = None

st.set_page_config(page_title="Malin", layout="centered")
st.title("Malin – produktionsapp")

# ---------------- Hjälpfunktioner ----------------
def _retry_call(fn, *args, **kwargs):
    delay = 0.5
    for _ in range(6):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if any(x in msg for x in ("429", "RESOURCE_EXHAUSTED", "RATE_LIMIT_EXCEEDED")):
                _time.sleep(delay + random.uniform(0, 0.25))
                delay = min(delay * 2, 4)
                continue
            raise
    return fn(*args, **kwargs)

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "": return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "": return default
        return float(x)
    except Exception:
        return default

def _hm_str_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60: h += 1; m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _parse_iso_date(s: str):
    s = (s or "").strip()
    if not s: return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None

def _usd(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "-"

# ---------------- Google Sheets (lazy) ----------------
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

SPREADSHEET = resolve_spreadsheet()
WORKSHEET_TITLE = "Data"
SETTINGS_SHEET = "Inställningar"

def _get_ws(title: str):
    # hämtas bara när vi verkligen behöver bladet
    try:
        return SPREADSHEET.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = SPREADSHEET.add_worksheet(title=title, rows=200 if title==SETTINGS_SHEET else 2000, cols=120)
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

                # bonus-räknare (kan användas i statistikflöde, inte i live)
                ["BONUS_TOTAL", "0", "Bonus killar totalt"],
                ["BONUS_USED",  "0", "Bonus killar deltagit"],
                ["BONUS_LEFT",  "0", "Bonus killar kvar"],

                # visnings-etiketter
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

def _settings_as_dict():
    ws = _get_ws(SETTINGS_SHEET)
    rows = _retry_call(ws.get_all_records)
    d, labels = {}, {}
    for r in rows:
        key = (r.get("Key") or "").strip()
        if not key: continue
        d[key] = r.get("Value")
        if r.get("Label") is not None:
            labels[key] = str(r.get("Label"))
        if key.startswith("LABEL_"):
            cname = key[len("LABEL_"):]
            val = str(r.get("Value") or "").strip()
            if val:
                labels[cname] = val
    return d, labels

CFG_RAW, LABELS = _settings_as_dict()

def _L(txt: str) -> str:
    return LABELS.get(txt, txt)

def _init_cfg_defaults_from_settings():
    st.session_state.setdefault("CFG", {})
    C = st.session_state["CFG"]

    def _get(k, fallback):
        return CFG_RAW.get(k, fallback)

    # datum/tid
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

    # tal
    C["MAX_PAPPAN"]       = int(float(_get("MAX_PAPPAN", 10)))
    C["MAX_GRANNAR"]      = int(float(_get("MAX_GRANNAR", 10)))
    C["MAX_NILS_VANNER"]  = int(float(_get("MAX_NILS_VANNER", 10)))
    C["MAX_NILS_FAMILJ"]  = int(float(_get("MAX_NILS_FAMILJ", 10)))
    C["MAX_BEKANTA"]      = int(float(_get("MAX_BEKANTA", 10)))
    C["avgift_usd"]       = float(_get("avgift_usd", 30.0))
    C["PROD_STAFF"]       = int(float(_get("PROD_STAFF", 800)))

_init_cfg_defaults_from_settings()
CFG = st.session_state["CFG"]

# ---------------- Sidopanel: inställningar & etiketter ----------------
st.sidebar.header("Inställningar")

with st.sidebar.expander("⚙️ Konfiguration (persistent)", expanded=False):
    # OBS: Dessa spar-funktioner lägger vi i DEL 4 (för att hålla delarna korta)
    st.caption("Start/grund:")
    st.write(f"Historiskt startdatum: **{CFG['startdatum']}**")
    st.write(f"Starttid: **{CFG['starttid'].strftime('%H:%M')}**")
    st.write(f"{_L('Malins födelsedatum')}: **{CFG['födelsedatum']}**")

    st.markdown("---")
    st.caption("Maxvärden (visning/varning):")
    st.write(f"{_L('Pappans vänner')}: **{CFG['MAX_PAPPAN']}**")
    st.write(f"{_L('Grannar')}: **{CFG['MAX_GRANNAR']}**")
    st.write(f"{_L('Nils vänner')}: **{CFG['MAX_NILS_VANNER']}**")
    st.write(f"{_L('Nils familj')}: **{CFG['MAX_NILS_FAMILJ']}**")
    st.write(f"{_L('Bekanta')}: **{CFG['MAX_BEKANTA']}**")

    st.markdown("---")
    st.caption("Personal & Eskilstuna-intervall")
    # procentsats personal deltagit (0-100, ej slider)
    st.session_state.setdefault("staff_percent", 10.0)
    st.session_state.staff_percent = st.number_input(
        "Personal deltagit (%)", min_value=0.0, max_value=100.0, step=0.5, value=st.session_state.staff_percent, key="staff_percent_in"
    )
    # intervall för Eskilstuna killar
    st.session_state.setdefault("esk_min", 20)
    st.session_state.setdefault("esk_max", 40)
    colA, colB = st.columns(2)
    with colA:
        st.session_state.esk_min = st.number_input("Eskilstuna min", min_value=0, step=1, value=st.session_state.esk_min, key="esk_min_in")
    with colB:
        st.session_state.esk_max = st.number_input("Eskilstuna max", min_value=0, step=1, value=st.session_state.esk_max, key="esk_max_in")
    if st.session_state.esk_max < st.session_state.esk_min:
        st.warning("Eskilstuna max måste vara ≥ min. Justera värdena.")

    st.markdown("---")
    st.caption("Etiketter (visning, påverkar ej beräkningar)")
    for base in ["Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar","Män","Svarta","Känner","Personal deltagit","Bonus killar","Bonus deltagit","Malins födelsedatum"]:
        st.session_state.setdefault(f"lab_{base}", _L(base))
        st.session_state[f"lab_{base}"] = st.text_input(f"Etikett: {base}", value=st.session_state[f"lab_{base}"], key=f"lab_in_{base}")

    # (Sparknapp + persist sparning kommer i DEL 4)

# ---------- Scenario-väljare ----------
SCENARIOS = ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet (7 dagar)"]
st.session_state.setdefault("scenario", SCENARIOS[0])
scenario = st.selectbox("🧪 Välj scenario", SCENARIOS, index=SCENARIOS.index(st.session_state["scenario"]), key="scenario_select")
st.session_state["scenario"] = scenario

# ---------- Safe defaults i session_state för alla inputfält ----------
def _init_defaults():
    ss = st.session_state
    # ordningen enligt din specifikation
    ss.setdefault("in_man", 0)
    ss.setdefault("in_svarta", 0)
    ss.setdefault("in_fitta", 0)
    ss.setdefault("in_rumpa", 0)
    ss.setdefault("in_dp", 0)
    ss.setdefault("in_dpp", 0)
    ss.setdefault("in_dap", 0)
    ss.setdefault("in_tap", 0)

    ss.setdefault("in_pappan", 0)
    ss.setdefault("in_grannar", 0)
    ss.setdefault("in_nils_vanner", 0)
    ss.setdefault("in_nils_familj", 0)
    ss.setdefault("in_bekanta", 0)
    ss.setdefault("in_eskilstuna", 0)

    ss.setdefault("in_bonus_deltagit", 0)
    # bonus_killar behövs internt för att visa beräkningen – vi håller ett in-”spöke” också:
    ss.setdefault("in_bonus_killar", 0)

    # personal följer procent – init med procent på hel styrka
    default_staff = int(round(CFG["PROD_STAFF"] * (st.session_state.get("staff_percent", 10.0) / 100.0)))
    ss.setdefault("in_personal_deltagit", default_staff)

    ss.setdefault("in_alskar", 0)
    ss.setdefault("in_sover", 0)

    ss.setdefault("in_tid_s", 60)
    ss.setdefault("in_tid_d", 60)
    ss.setdefault("in_vila", 7)
    ss.setdefault("in_dt_tid", 60)
    ss.setdefault("in_dt_vila", 3)

    # övrigt
    ss.setdefault("ROW_COUNT", 0)
    ss.setdefault("SCENARIO_SEED", random.randint(1, 10**9))  # stabil slump per scenario
    ss.setdefault("BATCH", None)  # används för "Vila i hemmet (7 dagar)"
    ss.setdefault("BATCH_INDEX", 0)

_init_defaults()

# ---------- Radräkning / Datum / Veckodag ----------
def _row_count_lazy():
    # Hämtas bara när vi faktiskt ska spara eller visa tabell – i live jobbar vi lokalt.
    return st.session_state.get("ROW_COUNT", 0)

def _next_scene_number():
    return _row_count_lazy() + 1

def _datum_och_veckodag_for_scen(scen_nr: int):
    d = CFG["startdatum"] + timedelta(days=scen_nr - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

scen = _next_scene_number()
rad_datum, veckodag = _datum_och_veckodag_for_scen(scen)

st.subheader("➕ Lägg till / simulera rad (input)")

# ---------- Input (exakt ordning du ville) ----------
# OBS: vi använder value=st.session_state[...] + key, men vi sätter ALDRIG samma nyckel efter widgeten.
colA, colB, colC = st.columns(3)

with colA:
    in_man = st.number_input(_L("Män"), min_value=0, step=1,
                             value=st.session_state["in_man"], key="in_man")
    in_svarta = st.number_input(_L("Svarta"), min_value=0, step=1,
                                value=st.session_state["in_svarta"], key="in_svarta")
    in_fitta = st.number_input("Fitta", min_value=0, step=1,
                               value=st.session_state["in_fitta"], key="in_fitta")
    in_rumpa = st.number_input("Rumpa", min_value=0, step=1,
                               value=st.session_state["in_rumpa"], key="in_rumpa")
    in_dp = st.number_input("DP", min_value=0, step=1,
                            value=st.session_state["in_dp"], key="in_dp")
    in_dpp = st.number_input("DPP", min_value=0, step=1,
                             value=st.session_state["in_dpp"], key="in_dpp")

with colB:
    in_dap = st.number_input("DAP", min_value=0, step=1,
                             value=st.session_state["in_dap"], key="in_dap")
    in_tap = st.number_input("TAP", min_value=0, step=1,
                             value=st.session_state["in_tap"], key="in_tap")

    lbl_p = f"{_L('Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
    lbl_g = f"{_L('Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
    lbl_nv = f"{_L('Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
    lbl_nf = f"{_L('Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
    lbl_bk = f"{_L('Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

    in_pappan = st.number_input(lbl_p, min_value=0, step=1,
                                value=st.session_state["in_pappan"], key="in_pappan")
    in_grannar = st.number_input(lbl_g, min_value=0, step=1,
                                 value=st.session_state["in_grannar"], key="in_grannar")
    in_nils_vanner = st.number_input(lbl_nv, min_value=0, step=1,
                                     value=st.session_state["in_nils_vanner"], key="in_nils_vanner")
    in_nils_familj = st.number_input(lbl_nf, min_value=0, step=1,
                                     value=st.session_state["in_nils_familj"], key="in_nils_familj")
    in_bekanta = st.number_input(_L("Bekanta"), min_value=0, step=1,
                                 value=st.session_state["in_bekanta"], key="in_bekanta")
    in_esk = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1,
                             value=st.session_state["in_eskilstuna"], key="in_eskilstuna")

with colC:
    # Bonus killar finns inte som eget input (enligt dina senaste flöden),
    # men Bonus deltagit SKA synas i inputfältet. Vi autoifyller nedan.
    in_bonus_deltagit = st.number_input(_L("Bonus deltagit"), min_value=0, step=1,
                                        value=st.session_state["in_bonus_deltagit"], key="in_bonus_deltagit")

    # Personal följer sidopanelens procent; men låt användaren justera om de vill.
    # Vi räknar initialt default i DEL 1, och uppdaterar här om procenten ändrats.
    suggested_staff = int(round(CFG["PROD_STAFF"] * (st.session_state.get("staff_percent", 10.0) / 100.0)))
    if st.session_state["in_personal_deltagit"] != suggested_staff:
        # bara justera automatiskt när den skiljer sig och användaren inte redan ändrat i rutan
        st.session_state["in_personal_deltagit"] = suggested_staff
    in_personal = st.number_input(_L("Personal deltagit"), min_value=0, step=1,
                                  value=st.session_state["in_personal_deltagit"], key="in_personal_deltagit")

    in_alskar = st.number_input("Älskar", min_value=0, step=1,
                                value=st.session_state["in_alskar"], key="in_alskar")
    in_sover = st.number_input("Sover med", min_value=0, max_value=1, step=1,
                               value=st.session_state["in_sover"], key="in_sover")

    in_tid_s = st.number_input("Tid S (sek)", min_value=0, step=1,
                               value=st.session_state["in_tid_s"], key="in_tid_s")
    in_tid_d = st.number_input("Tid D (sek)", min_value=0, step=1,
                               value=st.session_state["in_tid_d"], key="in_tid_d")
    in_vila = st.number_input("Vila (sek)", min_value=0, step=1,
                              value=st.session_state["in_vila"], key="in_vila")
    in_dt_tid = st.number_input("DT tid (sek/kille)", min_value=0, step=1,
                                value=st.session_state["in_dt_tid"], key="in_dt_tid")
    in_dt_vila = st.number_input("DT vila (sek/kille)", min_value=0, step=1,
                                 value=st.session_state["in_dt_vila"], key="in_dt_vila")

# ----------- Max-varningar (endast visning, inga skrivningar sker) -----------
if in_pappan > int(CFG["MAX_PAPPAN"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_pappan} > max {int(CFG['MAX_PAPPAN'])}</span>", unsafe_allow_html=True)
if in_grannar > int(CFG["MAX_GRANNAR"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_grannar} > max {int(CFG['MAX_GRANNAR'])}</span>", unsafe_allow_html=True)
if in_nils_vanner > int(CFG["MAX_NILS_VANNER"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_nils_vanner} > max {int(CFG['MAX_NILS_VANNER'])}</span>", unsafe_allow_html=True)
if in_nils_familj > int(CFG["MAX_NILS_FAMILJ"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_nils_familj} > max {int(CFG['MAX_NILS_FAMILJ'])}</span>", unsafe_allow_html=True)
if in_bekanta > int(CFG["MAX_BEKANTA"]):
    st.markdown(f"<span style='color:#d00'>⚠️ {in_bekanta} > max {int(CFG['MAX_BEKANTA'])}</span>", unsafe_allow_html=True)

# ----------- Autoifyll Bonus deltagit (40% av Bonus killar om känt) -----------
# Vi håller ett internt "in_bonus_killar" i session_state; scenariofyllningar sätter det.
bk_local = st.session_state.get("in_bonus_killar", 0)
if bk_local and st.session_state.get("in_bonus_deltagit", 0) == 0:
    # lägg 40% i inputfältet om användaren inte redan fyllt något
    st.session_state["in_bonus_deltagit"] = int(round(bk_local * 0.40))
    # OBS: vi skriver inte direkt till widgeten här (det skapar varningar), utan använder session_state-värdet nästa render.

# ----------- Grund-dict för beräkning (enbart live) -----------
grund_preview = {
    "Typ": st.session_state.get("scenario", "Ny scen"),
    "Veckodag": veckodag,
    "Scen": scen,

    "Män": in_man,
    "Svarta": in_svarta,
    "Fitta": in_fitta,
    "Rumpa": in_rumpa,
    "DP": in_dp,
    "DPP": in_dpp,
    "DAP": in_dap,
    "TAP": in_tap,

    "Pappans vänner": in_pappan,
    "Grannar": in_grannar,
    "Nils vänner": in_nils_vanner,
    "Nils familj": in_nils_familj,
    "Bekanta": in_bekanta,
    "Eskilstuna killar": in_esk,

    "Bonus killar": bk_local,                         # används av beräkningar vid behov
    "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
    "Personal deltagit": in_personal,

    "Älskar": in_alskar,
    "Sover med": in_sover,

    "Tid S": in_tid_s,
    "Tid D": in_tid_d,
    "Vila": in_vila,
    "DT tid (sek/kille)": in_dt_tid,
    "DT vila (sek/kille)": in_dt_vila,

    # Ekonomi – avgift (~rad)
    "Avgift": float(CFG["avgift_usd"]),
}

# ----------- Live-beräkning (positionella argument! INTE foddatum) -----------
def _calc_preview(grund):
    try:
        if callable(calc_row_values):
            return calc_row_values(grund, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        return {}
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview(grund_preview)

# ----------- Ålder (live) -----------
def _age_at(d: date, born: date) -> int:
    return d.year - born.year - ((d.month, d.day) < (born.month, born.day))

alder_malin = _age_at(rad_datum, CFG["födelsedatum"])

# ----------- Live-visning -----------
st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

c1, c2 = st.columns(2)
with c1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin)", f"{alder_malin} år")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with c2:
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

# ===================== SCENARIO: välj & fyll inputs (lägg detta FÖRE input-blocket) =====================

SCENARIO_OPTIONS = [
    "Ny scen",
    "Slumpa scen vit",
    "Slumpa scen svart",
    "Vila på jobbet",
    "Vila i hemmet (7 dagar)"
]

# visa minsta/lägsta för Eskilstuna-intervall i sidopanel (unikt key-prefix så vi ej dubblar)
with st.sidebar.expander("⚙️ Scenario-inställningar", expanded=False):
    st.session_state.eskilstuna_min = st.number_input(
        "Eskilstuna – min", min_value=0, step=1,
        value=st.session_state.get("eskilstuna_min", 20), key="eskilstuna_min"
    )
    st.session_state.eskilstuna_max = st.number_input(
        "Eskilstuna – max", min_value=st.session_state.eskilstuna_min, step=1,
        value=st.session_state.get("eskilstuna_max", 40), key="eskilstuna_max"
    )

scenario = st.selectbox("Välj scenario", SCENARIO_OPTIONS, index=SCENARIO_OPTIONS.index(st.session_state.get("scenario", "Ny scen")), key="scenario")

# --- Hjälpare: historikens min/max per kolumn (cache i sessionen, 1 läsning per session) ---
def _ensure_hist_cache():
    if "HIST_CACHE" in st.session_state:
        return
    try:
        recs = _retry_call(sheet.get_all_records)  # EN läsning, cache: inga fler calls vid input-ändringar
    except Exception:
        recs = []
    cache = {}
    if recs:
        cols = recs[0].keys()
        for c in cols:
            vals = []
            for r in recs:
                try:
                    v = r.get(c, "")
                    if v == "" or v is None:
                        continue
                    vals.append(int(float(v)))
                except Exception:
                    continue
            if vals:
                cache[c] = (min(vals), max(vals))
    st.session_state["HIST_CACHE"] = cache

def _get_hist_min_max(col: str):
    _ensure_hist_cache()
    return st.session_state["HIST_CACHE"].get(col, (0, 0))

def _rand_hist(col: str):
    lo, hi = _get_hist_min_max(col)
    if hi < lo:
        lo, hi = 0, 0
    return random.randint(lo, hi) if hi >= lo else 0

# personal-deltagit = procent av PROD_STAFF (följer alltid procenten)
def _suggest_personal():
    return int(round(CFG["PROD_STAFF"] * (st.session_state.get("staff_percent", 10.0) / 100.0)))

# --- Bonus: räkna fram Bonus killar (binomial på prenumeranter), lägg 40% i Bonus deltagit ---
def _apply_bonus_from_inputs_and_preview(tmp_inputs: dict, rad_d: date):
    """Kör en snabb lokal förhandsberäkning för att extrahera Prenumeranter -> Bonus killar -> Bonus deltagit."""
    if not callable(calc_row_values):
        return
    try:
        preview_tmp = calc_row_values(tmp_inputs, rad_d, CFG["födelsedatum"], CFG["starttid"])
        pren = int(max(0, int(preview_tmp.get("Prenumeranter", 0))))
        # 5% chans per pren – simulera binomial utan numpy
        bonus_k = sum(1 for _ in range(pren) if random.random() < 0.05)
        st.session_state["in_bonus_killar"] = int(bonus_k)
        st.session_state["in_bonus_deltagit"] = int(round(bonus_k * 0.40))
    except Exception:
        # Lämna orört om något fallerar
        pass

# --- Nollställ inputs (för "Ny scen") ---
def _reset_all_inputs_for_new_scene():
    st.session_state["in_man"] = 0
    st.session_state["in_svarta"] = 0
    st.session_state["in_fitta"] = 0
    st.session_state["in_rumpa"] = 0
    st.session_state["in_dp"] = 0
    st.session_state["in_dpp"] = 0
    st.session_state["in_dap"] = 0
    st.session_state["in_tap"] = 0

    st.session_state["in_pappan"] = 0
    st.session_state["in_grannar"] = 0
    st.session_state["in_nils_vanner"] = 0
    st.session_state["in_nils_familj"] = 0
    st.session_state["in_bekanta"] = 0
    st.session_state["in_eskilstuna"] = 0

    st.session_state["in_bonus_killar"] = 0
    st.session_state["in_bonus_deltagit"] = 0

    st.session_state["in_personal_deltagit"] = _suggest_personal()

    st.session_state["in_alskar"] = 0
    st.session_state["in_sover"]  = 0

    # tider
    st.session_state["in_tid_s"] = 60
    st.session_state["in_tid_d"] = 60
    st.session_state["in_vila"]  = 7
    st.session_state["in_dt_tid"]  = 60
    st.session_state["in_dt_vila"] = 3

# --- Applicera valt scenario och fyll inputs ---
def apply_scenario_fill(selected: str):
    scen_nr = _next_scene_number()
    d, vdag = _datum_och_veckodag_for_scen(scen_nr)

    if selected == "Ny scen":
        _reset_all_inputs_for_new_scene()
        st.rerun()

    elif selected == "Slumpa scen vit":
        # Slumpa mot historikens min/max
        st.session_state["in_man"]   = _rand_hist("Män")
        st.session_state["in_svarta"] = 0  # vit scen: svarta=0
        st.session_state["in_fitta"] = _rand_hist("Fitta")
        st.session_state["in_rumpa"] = _rand_hist("Rumpa")
        st.session_state["in_dp"]    = _rand_hist("DP")
        st.session_state["in_dpp"]   = _rand_hist("DPP")
        st.session_state["in_dap"]   = _rand_hist("DAP")
        st.session_state["in_tap"]   = _rand_hist("TAP")

        st.session_state["in_pappan"] = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"] = _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"] = _rand_hist("Bekanta")
        # Eskilstuna via sidopanelens intervall
        emin = int(st.session_state.get("eskilstuna_min", 20))
        emax = int(st.session_state.get("eskilstuna_max", 40))
        if emax < emin: emax = emin
        st.session_state["in_eskilstuna"] = random.randint(emin, emax)

        st.session_state["in_personal_deltagit"] = _suggest_personal()

        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

        # Bonus – räkna från inputs+preview → lägg 40% i inputfältet
        tmp = {
            "Typ": "Slumpa scen vit", "Veckodag": vdag, "Scen": scen_nr,
            "Män": st.session_state["in_man"],
            "Svarta": st.session_state["in_svarta"],
            "Fitta": st.session_state["in_fitta"],
            "Rumpa": st.session_state["in_rumpa"],
            "DP": st.session_state["in_dp"],
            "DPP": st.session_state["in_dpp"],
            "DAP": st.session_state["in_dap"],
            "TAP": st.session_state["in_tap"],

            "Pappans vänner": st.session_state["in_pappan"],
            "Grannar": st.session_state["in_grannar"],
            "Nils vänner": st.session_state["in_nils_vanner"],
            "Nils familj": st.session_state["in_nils_familj"],
            "Bekanta": st.session_state["in_bekanta"],
            "Eskilstuna killar": st.session_state["in_eskilstuna"],

            "Bonus killar": 0,
            "Bonus deltagit": 0,
            "Personal deltagit": st.session_state["in_personal_deltagit"],

            "Älskar": st.session_state["in_alskar"],
            "Sover med": st.session_state["in_sover"],

            "Tid S": st.session_state["in_tid_s"],
            "Tid D": st.session_state["in_tid_d"],
            "Vila":  st.session_state["in_vila"],
            "DT tid (sek/kille)":  st.session_state["in_dt_tid"],
            "DT vila (sek/kille)": st.session_state["in_dt_vila"],

            "Avgift": float(CFG["avgift_usd"]),
        }
        _apply_bonus_from_inputs_and_preview(tmp, d)
        st.rerun()

    elif selected == "Slumpa scen svart":
        # Svart scen: alla källor 0, personal = 0, svarta slumpas; övriga sex acts slumpas
        st.session_state["in_man"]   = 0
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        st.session_state["in_fitta"] = _rand_hist("Fitta")
        st.session_state["in_rumpa"] = _rand_hist("Rumpa")
        st.session_state["in_dp"]    = _rand_hist("DP")
        st.session_state["in_dpp"]   = _rand_hist("DPP")
        st.session_state["in_dap"]   = _rand_hist("DAP")
        st.session_state["in_tap"]   = _rand_hist("TAP")

        st.session_state["in_pappan"] = 0
        st.session_state["in_grannar"] = 0
        st.session_state["in_nils_vanner"] = 0
        st.session_state["in_nils_familj"] = 0
        st.session_state["in_bekanta"] = 0
        st.session_state["in_eskilstuna"] = 0

        st.session_state["in_personal_deltagit"] = 0  # enligt senaste kravet
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

        # Bonus från inputs (binomial 5%) → 40% in i inputfältet
        tmp = {
            "Typ": "Slumpa scen svart", "Veckodag": vdag, "Scen": scen_nr,
            "Män": 0,
            "Svarta": st.session_state["in_svarta"],
            "Fitta": st.session_state["in_fitta"],
            "Rumpa": st.session_state["in_rumpa"],
            "DP": st.session_state["in_dp"],
            "DPP": st.session_state["in_dpp"],
            "DAP": st.session_state["in_dap"],
            "TAP": st.session_state["in_tap"],

            "Pappans vänner": 0,
            "Grannar": 0,
            "Nils vänner": 0,
            "Nils familj": 0,
            "Bekanta": 0,
            "Eskilstuna killar": 0,

            "Bonus killar": 0,
            "Bonus deltagit": 0,
            "Personal deltagit": 0,

            "Älskar": st.session_state["in_alskar"],
            "Sover med": st.session_state["in_sover"],

            "Tid S": st.session_state["in_tid_s"],
            "Tid D": st.session_state["in_tid_d"],
            "Vila":  st.session_state["in_vila"],
            "DT tid (sek/kille)":  st.session_state["in_dt_tid"],
            "DT vila (sek/kille)": st.session_state["in_dt_vila"],

            "Avgift": float(CFG["avgift_usd"]),
        }
        _apply_bonus_from_inputs_and_preview(tmp, d)
        st.rerun()

    elif selected == "Vila på jobbet":
        # Enligt dina krav: slumpa fitta, rumpa, DP, DPP, DAP, TAP från historikens min–max
        st.session_state["in_man"] = 0
        st.session_state["in_svarta"] = 0

        st.session_state["in_fitta"] = _rand_hist("Fitta")
        st.session_state["in_rumpa"] = _rand_hist("Rumpa")
        st.session_state["in_dp"]    = _rand_hist("DP")
        st.session_state["in_dpp"]   = _rand_hist("DPP")
        st.session_state["in_dap"]   = _rand_hist("DAP")
        st.session_state["in_tap"]   = _rand_hist("TAP")

        # Källor (känner m.fl.) kan vara 40–60% av max om du vill; du bad nu främst om acts.
        # Vi sätter dem till 0 här för att hålla “vila”-scen ren, men ändra gärna om du vill.
        st.session_state["in_pappan"] = 0
        st.session_state["in_grannar"] = 0
        st.session_state["in_nils_vanner"] = 0
        st.session_state["in_nils_familj"] = 0
        st.session_state["in_bekanta"] = 0
        # Eskilstuna enligt intervall
        emin = int(st.session_state.get("eskilstuna_min", 20))
        emax = int(st.session_state.get("eskilstuna_max", 40))
        if emax < emin: emax = emin
        st.session_state["in_eskilstuna"] = random.randint(emin, emax)

        st.session_state["in_personal_deltagit"] = _suggest_personal()
        st.session_state["in_alskar"] = 12  # enligt tidigare spec “vila på jobbet”
        st.session_state["in_sover"]  = 1

        tmp = {
            "Typ": "Vila på jobbet", "Veckodag": vdag, "Scen": scen_nr,
            "Män": 0,
            "Svarta": 0,
            "Fitta": st.session_state["in_fitta"],
            "Rumpa": st.session_state["in_rumpa"],
            "DP": st.session_state["in_dp"],
            "DPP": st.session_state["in_dpp"],
            "DAP": st.session_state["in_dap"],
            "TAP": st.session_state["in_tap"],

            "Pappans vänner": 0, "Grannar": 0, "Nils vänner": 0, "Nils familj": 0, "Bekanta": 0,
            "Eskilstuna killar": st.session_state["in_eskilstuna"],

            "Bonus killar": 0, "Bonus deltagit": 0,
            "Personal deltagit": st.session_state["in_personal_deltagit"],

            "Älskar": st.session_state["in_alskar"],
            "Sover med": st.session_state["in_sover"],

            "Tid S": st.session_state["in_tid_s"],
            "Tid D": st.session_state["in_tid_d"],
            "Vila":  st.session_state["in_vila"],
            "DT tid (sek/kille)":  st.session_state["in_dt_tid"],
            "DT vila (sek/kille)": st.session_state["in_dt_vila"],

            "Avgift": float(CFG["avgift_usd"]),
        }
        _apply_bonus_from_inputs_and_preview(tmp, d)
        st.rerun()

    elif selected == "Vila i hemmet (7 dagar)":
        # Skapa en 7-dagars kö i session_state, fyll dag 1 direkt till inputs; dag 2–7 sparas i HOME_QUEUE
        queue = []
        # Nils 50/45/5 för dag 1–6
        r = random.random()
        if r < 0.50: ones_count = 0
        elif r < 0.95: ones_count = 1
        else: ones_count = 2
        one_days = set(random.sample(range(6), ones_count)) if ones_count > 0 else set()

        emin = int(st.session_state.get("eskilstuna_min", 20))
        emax = int(st.session_state.get("eskilstuna_max", 40))
        if emax < emin: emax = emin

        for offset in range(7):
            scen_i = scen_nr + offset
            di, vi = _datum_och_veckodag_for_scen(scen_i)

            if offset <= 4:
                # dag 1–5: acts 0 i originaldefinitionen, men du bad att “samma slump-tal ska genereras”
                # för enkelhet: slumpa mot historik även här
                f = _rand_hist("Fitta")
                rmp = _rand_hist("Rumpa")
                dpv = _rand_hist("DP")
                dppv= _rand_hist("DPP")
                dapv= _rand_hist("DAP")
                tapv= _rand_hist("TAP")
                eskv= random.randint(emin, emax)
                pers = _suggest_personal()  # följer procenten
            else:
                f = rmp = dpv = dppv = dapv = tapv = 0
                eskv = random.randint(emin, emax)
                pers = 0  # dag 6–7 = 0

            sv = 1 if offset == 6 else 0
            nils_val = 0 if offset == 6 else (1 if offset in one_days else 0)

            base = {
                "Typ": "Vila i hemmet",
                "Veckodag": vi, "Scen": scen_i,
                "Män": 0, "Svarta": 0,
                "Fitta": f, "Rumpa": rmp, "DP": dpv, "DPP": dppv, "DAP": dapv, "TAP": tapv,

                "Pappans vänner": 0, "Grannar": 0, "Nils vänner": 0, "Nils familj": 0, "Bekanta": 0,
                "Eskilstuna killar": eskv,

                "Bonus killar": 0, "Bonus deltagit": 0,   # fylls via preview när vi tar ut från kön
                "Personal deltagit": pers,

                "Älskar": 6, "Sover med": sv,

                "Tid S": 0, "Tid D": 0, "Vila": 0,
                "DT tid (sek/kille)": 60, "DT vila (sek/kille)": 3,

                "Avgift": float(CFG["avgift_usd"]),
                "Nils": nils_val,
            }
            queue.append(base)

        st.session_state["HOME_QUEUE"] = queue

        # Fyll dag 1 in i inputs + räkna bonus på dag 1
        first = queue[0]
        for k_src, k_dest in [
            ("Män", "in_man"), ("Svarta", "in_svarta"), ("Fitta", "in_fitta"), ("Rumpa", "in_rumpa"),
            ("DP","in_dp"), ("DPP","in_dpp"), ("DAP","in_dap"), ("TAP","in_tap"),
            ("Pappans vänner","in_pappan"), ("Grannar","in_grannar"), ("Nils vänner","in_nils_vanner"),
            ("Nils familj","in_nils_familj"), ("Bekanta","in_bekanta"), ("Eskilstuna killar","in_eskilstuna"),
        ]:
            st.session_state[k_dest] = int(first.get(k_src, 0))

        st.session_state["in_personal_deltagit"] = int(first["Personal deltagit"])
        st.session_state["in_alskar"] = int(first["Älskar"])
        st.session_state["in_sover"]  = int(first["Sover med"])

        # räkna bonus för dag 1 och lägg i inputs
        _apply_bonus_from_inputs_and_preview(first, d)

        st.info("Skapade 7-dagars kö för 'Vila i hemmet'. Dag 1 är nu ifylld i inputs. Använd knappen '➡️ Nästa vilodag' (kommer i DEL 4) för att fylla dag 2–7.")
        st.rerun()

# En tydlig knapp för att applicera vald scenariofyllning
if st.button("⚡ Fyll inputs enligt valt scenario"):
    apply_scenario_fill(scenario)

# ===================== VILA I HEMMET: Nästa vilodag (fyll inputs från kön) =====================

def _fill_inputs_from_dict(d: dict):
    """Säker fyllning av alla input-keys från en dict."""
    mapping = [
        ("Män","in_man"), ("Svarta","in_svarta"), ("Fitta","in_fitta"), ("Rumpa","in_rumpa"),
        ("DP","in_dp"), ("DPP","in_dpp"), ("DAP","in_dap"), ("TAP","in_tap"),
        ("Pappans vänner","in_pappan"), ("Grannar","in_grannar"),
        ("Nils vänner","in_nils_vanner"), ("Nils familj","in_nils_familj"),
        ("Bekanta","in_bekanta"), ("Eskilstuna killar","in_eskilstuna"),
    ]
    for src, dest in mapping:
        st.session_state[dest] = int(d.get(src, 0))

    st.session_state["in_personal_deltagit"] = int(d.get("Personal deltagit", 0))
    st.session_state["in_alskar"] = int(d.get("Älskar", 0))
    st.session_state["in_sover"]  = int(d.get("Sover med", 0))

    # tider
    st.session_state["in_tid_s"] = int(d.get("Tid S", 0))
    st.session_state["in_tid_d"] = int(d.get("Tid D", 0))
    st.session_state["in_vila"]  = int(d.get("Vila", 0))
    st.session_state["in_dt_tid"]  = int(d.get("DT tid (sek/kille)", 60))
    st.session_state["in_dt_vila"] = int(d.get("DT vila (sek/kille)", 3))

def _compute_and_place_bonus_from_current_inputs():
    """Räkna Prenumeranter → Bonus killar → 40% delt. och lägg i inputfältet."""
    if not callable(calc_row_values):
        return
    scen_nr = _next_scene_number()
    d, vdag = _datum_och_veckodag_for_scen(scen_nr)
    tmp = {
        "Typ": st.session_state.get("scenario", "Ny scen"),
        "Veckodag": vdag, "Scen": scen_nr,

        "Män": st.session_state.get("in_man", 0),
        "Svarta": st.session_state.get("in_svarta", 0),
        "Fitta": st.session_state.get("in_fitta", 0),
        "Rumpa": st.session_state.get("in_rumpa", 0),
        "DP": st.session_state.get("in_dp", 0),
        "DPP": st.session_state.get("in_dpp", 0),
        "DAP": st.session_state.get("in_dap", 0),
        "TAP": st.session_state.get("in_tap", 0),

        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar": st.session_state.get("in_grannar", 0),
        "Nils vänner": st.session_state.get("in_nils_vanner", 0),
        "Nils familj": st.session_state.get("in_nils_familj", 0),
        "Bekanta": st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        "Bonus killar": st.session_state.get("in_bonus_killar", 0),
        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
        "Personal deltagit": st.session_state.get("in_personal_deltagit", 0),

        "Älskar": st.session_state.get("in_alskar", 0),
        "Sover med": st.session_state.get("in_sover", 0),

        "Tid S": st.session_state.get("in_tid_s", 0),
        "Tid D": st.session_state.get("in_tid_d", 0),
        "Vila":  st.session_state.get("in_vila", 0),
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 60),
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 3),

        "Avgift": float(CFG.get("avgift_usd", 30.0)),
    }
    try:
        prev = calc_row_values(tmp, d, CFG["födelsedatum"], CFG["starttid"])
        pren = int(prev.get("Prenumeranter", 0) or 0)
        bonus_k = sum(1 for _ in range(pren) if random.random() < 0.05)
        st.session_state["in_bonus_killar"] = int(bonus_k)
        st.session_state["in_bonus_deltagit"] = int(round(bonus_k * 0.40))
    except Exception:
        pass

# Visar knappen endast när det finns en väntande kö
if st.session_state.get("HOME_QUEUE"):
    st.info("Det finns en aktiv 7-dagars kö för **Vila i hemmet**.")
    if st.button("➡️ Nästa vilodag"):
        q = st.session_state.get("HOME_QUEUE", [])
        if len(q) > 1:
            # Poppa första som redan visats, ta nästa för inputs
            q.pop(0)
            st.session_state["HOME_QUEUE"] = q
            # Fyll inputs från nästa dag och räkna bonus → lägg in i inputfältet
            next_day = q[0]
            _fill_inputs_from_dict(next_day)

            # Uppdatera Bonus killar/deltagit i input efter förhandsberäkning
            _compute_and_place_bonus_from_current_inputs()
            st.rerun()
        else:
            st.session_state.pop("HOME_QUEUE", None)
            st.success("Kön för 'Vila i hemmet' är slut. Alla 7 dagar visade.")
            st.rerun()

# ===================== SPARA / AUTO-MAX (endast vid knapptryck) =====================

def _collect_current_inputs_dict(typ_text: str) -> dict:
    return {
        "Typ": typ_text,
        "Veckodag": _datum_och_veckodag_for_scen(_next_scene_number())[1],
        "Scen": _next_scene_number(),

        "Män": st.session_state.get("in_man", 0),
        "Svarta": st.session_state.get("in_svarta", 0),
        "Fitta": st.session_state.get("in_fitta", 0),
        "Rumpa": st.session_state.get("in_rumpa", 0),
        "DP": st.session_state.get("in_dp", 0),
        "DPP": st.session_state.get("in_dpp", 0),
        "DAP": st.session_state.get("in_dap", 0),
        "TAP": st.session_state.get("in_tap", 0),

        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar": st.session_state.get("in_grannar", 0),
        "Nils vänner": st.session_state.get("in_nils_vanner", 0),
        "Nils familj": st.session_state.get("in_nils_familj", 0),
        "Bekanta": st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        "Bonus killar": st.session_state.get("in_bonus_killar", 0),
        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
        "Personal deltagit": st.session_state.get("in_personal_deltagit", 0),

        "Älskar": st.session_state.get("in_alskar", 0),
        "Sover med": st.session_state.get("in_sover", 0),

        "Tid S": st.session_state.get("in_tid_s", 0),
        "Tid D": st.session_state.get("in_tid_d", 0),
        "Vila":  st.session_state.get("in_vila", 0),
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 60),
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 3),

        "Avgift": float(st.session_state.get("in_avgift", CFG.get("avgift_usd", 30.0))),
        "Nils": st.session_state.get("in_nils", 0),
    }

def _save_row(grund: dict, rad_datum: date, veckodag: str):
    """Beräkna + spara en (1) rad till Google Sheet. Inga andra anrop här."""
    try:
        base = dict(grund)
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    # Skriv enligt aktuell header-ordning
    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    # bumpa lokal räknare (utan kryptisk key)
    st.session_state["ROW_COUNT"] = int(st.session_state.get("ROW_COUNT", 0)) + 1

    # Info
    ålder = rad_datum.year - CFG["födelsedatum"].year - (
        (rad_datum.month,rad_datum.day) < (CFG["födelsedatum"].month,CFG["födelsedatum"].day)
    )
    typ_label = ber.get("Typ") or "Händelse"
    st.success(f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), Ålder {ålder} år, Klockan {ber.get('Klockan','-')}")

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

def _apply_auto_max_and_save(pending):
    for _, info in pending["over_max"].items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))
        CFG[key] = new_val
    grund = pending["grund"]
    _save_row(grund, _parse_date_for_save(pending["rad_datum"]), pending["veckodag"])

# ——— Spara-knapp ———
st.markdown("---")
col_save1, col_save2 = st.columns([1,3])
with col_save1:
    save_clicked = st.button("💾 Spara raden", type="primary")
with col_save2:
    st.caption("Inget sparas till databasen förrän du trycker här.")

if save_clicked:
    scen = _next_scene_number()
    rad_datum, veckodag = _datum_och_veckodag_for_scen(scen)

    grund_preview = _collect_current_inputs_dict(st.session_state.get("scenario", "Ny scen"))

    # Auto-max-koll (källor)
    over_max = {}
    if grund_preview["Pappans vänner"] > int(CFG["MAX_PAPPAN"]):
        over_max["Pappans vänner"] = {"current_max": int(CFG["MAX_PAPPAN"]), "new_value": grund_preview["Pappans vänner"], "max_key": "MAX_PAPPAN"}
    if grund_preview["Grannar"] > int(CFG["MAX_GRANNAR"]):
        over_max["Grannar"] = {"current_max": int(CFG["MAX_GRANNAR"]), "new_value": grund_preview["Grannar"], "max_key": "MAX_GRANNAR"}
    if grund_preview["Nils vänner"] > int(CFG["MAX_NILS_VANNER"]):
        over_max["Nils vänner"] = {"current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": grund_preview["Nils vänner"], "max_key": "MAX_NILS_VANNER"}
    if grund_preview["Nils familj"] > int(CFG["MAX_NILS_FAMILJ"]):
        over_max["Nils familj"] = {"current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": grund_preview["Nils familj"], "max_key": "MAX_NILS_FAMILJ"}
    if grund_preview["Bekanta"] > int(CFG["MAX_BEKANTA"]):
        over_max["Bekanta"] = {"current_max": int(CFG["MAX_BEKANTA"]), "new_value": grund_preview["Bekanta"], "max_key": "MAX_BEKANTA"}

    if over_max:
        _store_pending(grund_preview, scen, rad_datum, veckodag, over_max)
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# ——— Auto-max dialog ———
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

# ===================== TABELL & RADERA (hämtas bara vid knapptryck) =====================

st.markdown("---")
st.subheader("📊 Aktuella data")

if st.button("🔄 Uppdatera tabell"):
    try:
        st.session_state["LATEST_ROWS"] = _retry_call(sheet.get_all_records)
        st.success("Tabell uppdaterad.")
    except Exception as e:
        st.warning(f"Kunde inte läsa data: {e}")

rows = st.session_state.get("LATEST_ROWS", [])
if rows:
    st.dataframe(rows, use_container_width=True)
else:
    st.caption("Klicka på **Uppdatera tabell** för att läsa in data.")

st.subheader("🗑 Ta bort rad")
if rows:
    total_rows = len(rows)
else:
    # fallback mot ROW_COUNT om tabellen ej laddats
    total_rows = int(st.session_state.get("ROW_COUNT", 0))

if total_rows > 0:
    idx = st.number_input(
        "Radnummer att ta bort (1 = första dataraden)",
        min_value=1, max_value=total_rows, step=1, value=1, key="delete_idx"
    )
    if st.button("Ta bort vald rad"):
        try:
            _retry_call(sheet.delete_rows, int(idx) + 1)  # +1 för header
            st.session_state["ROW_COUNT"] = max(0, int(st.session_state.get("ROW_COUNT", 0)) - 1)
            # uppdatera ev. cache
            if "LATEST_ROWS" in st.session_state and st.session_state["LATEST_ROWS"]:
                try:
                    st.session_state["LATEST_ROWS"].pop(int(idx) - 1)
                except Exception:
                    st.session_state["LATEST_ROWS"] = []
            st.success(f"Rad {idx} borttagen.")
            st.rerun()
        except Exception as e:
            st.warning(f"Kunde inte ta bort rad: {e}")
else:
    st.caption("Ingen datarad att ta bort – uppdatera tabellen först om du tror att det finns rader.")

# ===================== LIVE-FÖRHANDSVISNING (inkl. ålder) =====================

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")

def _current_inputs_for_preview_dict() -> dict:
    """Samla ihop nuvarande inputfält till ett dict för förhandsberäkningen."""
    return {
        "Typ": st.session_state.get("scenario", "Ny scen"),
        "Veckodag": _datum_och_veckodag_for_scen(_next_scene_number())[1],
        "Scen": _next_scene_number(),

        "Män": st.session_state.get("in_man", 0),
        "Svarta": st.session_state.get("in_svarta", 0),
        "Fitta": st.session_state.get("in_fitta", 0),
        "Rumpa": st.session_state.get("in_rumpa", 0),
        "DP": st.session_state.get("in_dp", 0),
        "DPP": st.session_state.get("in_dpp", 0),
        "DAP": st.session_state.get("in_dap", 0),
        "TAP": st.session_state.get("in_tap", 0),

        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar": st.session_state.get("in_grannar", 0),
        "Nils vänner": st.session_state.get("in_nils_vanner", 0),
        "Nils familj": st.session_state.get("in_nils_familj", 0),
        "Bekanta": st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        "Bonus killar": st.session_state.get("in_bonus_killar", 0),
        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
        "Personal deltagit": st.session_state.get("in_personal_deltagit", 0),

        "Älskar": st.session_state.get("in_alskar", 0),
        "Sover med": st.session_state.get("in_sover", 0),

        "Tid S": st.session_state.get("in_tid_s", 0),
        "Tid D": st.session_state.get("in_tid_d", 0),
        "Vila":  st.session_state.get("in_vila", 0),
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 60),
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 3),

        "Avgift": float(st.session_state.get("in_avgift", CFG.get("avgift_usd", 30.0))),
        "Nils": st.session_state.get("in_nils", 0),
    }

def _calc_preview_from_inputs() -> dict:
    if not callable(calc_row_values):
        return {}
    scen = _next_scene_number()
    rad_datum, veckodag = _datum_och_veckodag_for_scen(scen)
    base = _current_inputs_for_preview_dict()
    try:
        return calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview_from_inputs()
rad_datum, veckodag = _datum_och_veckodag_for_scen(_next_scene_number())

# Ålder i liven
ålder = rad_datum.year - CFG["födelsedatum"].year - (
    (rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day)
)

col_live1, col_live2 = st.columns(2)
with col_live1:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Ålder (Malin)", f"{ålder} år")
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with col_live2:
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

# ===================== EKONOMI (LIVE) =====================

st.markdown("#### 💵 Ekonomi (live)")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", st.session_state.get('in_avgift', CFG['avgift_usd']))))
with ec2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with ec3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with ec4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ===================== SLUT APP =====================
