import streamlit as st
import pandas as pd
import gspread
import random
import datetime
from google.oauth2.service_account import Credentials

# Importera beräkningar och statistik
from berakningar import calc_row_values
from statistik import compute_stats

st.set_page_config(page_title="Malin-produktionsapp", layout="wide")

# Google Sheets setup
SHEET_URL = st.secrets["SHEET_URL"]

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)

def skapa_koppling(sheet_name: str):
    return client.open_by_url(SHEET_URL).worksheet(sheet_name)

def hamta_data(sheet_name: str) -> pd.DataFrame:
    try:
        sheet = skapa_koppling(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

def spara_data(df: pd.DataFrame, sheet_name: str):
    sheet = skapa_koppling(sheet_name)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

def säkerställ_kolumner(df: pd.DataFrame, kolumner: list) -> pd.DataFrame:
    for kol in kolumner:
        if kol not in df.columns:
            df[kol] = 0
    return df

# =========================
# Del 2 — Profiler, state och in-/utläsning
# =========================

# Keys i session_state
CFG_KEY        = "CFG"
PROFILE_KEY    = "PROFILE"
DATA_KEY       = "DATA"            # Dataframe med rader för aktiv profil
HIST_KEY       = "HIST_MINMAX"     # min/max-cache för slump
BONUS_LEFT_KEY = "BONUS_LEFT"      # kvarvarande bonuskillar enligt profil

# Standard-konfig (kan skrivas över av profilsheet)
DEFAULT_CFG = {
    "startdatum":   datetime.date(1990, 1, 1),
    "starttid":     datetime.time(7, 0),
    "fodelsedatum": datetime.date(1970, 1, 1),
    "avgift_usd":   30.0,
    "PROD_STAFF":   800,

    # Bonuskillar & procentsats
    "BONUS_AVAILABLE": 500,         # startvärde i profil
    "BONUS_RATE_PCT":  1.0,         # t.ex. 1.0 (%) – styr hur många nya bonuskillar som skapas

    # Eskilstuna-intervall
    "ESK_MIN": 20, "ESK_MAX": 40,

    # Max-värden (källor)
    "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
    "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
    "MAX_BEKANTA": 100,

    # Etiketter (går att döpa om)
    "LBL_PAPPAN": "Pappans vänner",
    "LBL_GRANNAR": "Grannar",
    "LBL_NILS_VANNER": "Nils vänner",
    "LBL_NILS_FAMILJ": "Nils familj",
    "LBL_BEKANTA": "Bekanta",
    "LBL_ESK": "Eskilstuna killar",

    # Profil-specifikt mått (t.ex. längd i meter för mål-vikt)
    "PROFILE_HEIGHT_M": 1.64,
}

def _ensure_ws(title: str):
    """Hämta/Skapa ett kalkylblad med given titel."""
    sh = client.open_by_url(SHEET_URL)
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=2000, cols=50)

def _read_key_value_sheet(ws) -> dict:
    """Läs in ett Key/Value-ark -> dict (för profiler/inställningar)."""
    rows = ws.get_all_values()
    out = {}
    # hoppa ev rubrik
    start_i = 1 if rows and rows[0] and rows[0][0].strip().lower() in ("key", "nyckel") else 0
    for r in rows[start_i:]:
        if not r: 
            continue
        key = (r[0] if len(r) > 0 else "").strip()
        val = (r[1] if len(r) > 1 else "").strip()
        if not key:
            continue
        out[key] = val
    return out

def _parse_cfg_from_sheet(d: dict) -> dict:
    """Konvertera strängvärden från profilblad till rätt typer och lägg ovanpå DEFAULT_CFG."""
    cfg = DEFAULT_CFG.copy()

    def _to_date(s):
        try:
            y, m, d = [int(x) for x in s.split("-")]
            return datetime.date(y, m, d)
        except Exception:
            return None

    def _to_int(s):
        try: return int(s)
        except: return None

    def _to_float(s):
        try: return float(s)
        except: return None

    # Tillåt alla nycklar; försök smart typparsning
    for k, v in d.items():
        if k in ("startdatum", "fodelsedatum"):
            dv = _to_date(v)
            if dv: cfg[k] = dv
        elif k in DEFAULT_CFG:
            # matcha default-typ
            t = type(DEFAULT_CFG[k])
            if t is int:
                iv = _to_int(v)
                if iv is not None: cfg[k] = iv
            elif t is float:
                fv = _to_float(v)
                if fv is not None: cfg[k] = fv
            elif t is datetime.date:
                dv = _to_date(v)
                if dv: cfg[k] = dv
            elif t is datetime.time:
                # acceptera HH:MM
                try:
                    hh, mm = [int(x) for x in v.split(":")[:2]]
                    cfg[k] = datetime.time(hh, mm)
                except:
                    pass
            else:
                # str/bool/övrigt
                cfg[k] = v
        else:
            # ny/okänd nyckel → spara som sträng
            cfg[k] = v

    # Sanera rimligheter
    if cfg["ESK_MAX"] < cfg["ESK_MIN"]:
        cfg["ESK_MAX"] = cfg["ESK_MIN"]

    return cfg

def _load_profile_names() -> list:
    """Hämta profilnamn från bladet 'Profil' (kolumn A)."""
    ws = _ensure_ws("Profil")
    rows = ws.get_all_values()
    names = []
    for r in rows[1:] if rows else []:   # hoppa ev rubrik
        if r and r[0].strip():
            names.append(r[0].strip())
    return names

def _load_profile(profile_name: str):
    """
    Läs in inställningar från blad med samma namn som profilen,
    samt data från blad 'Data_<profil>'.
    """
    # Inställningar
    ws_cfg = _ensure_ws(profile_name)
    kv = _read_key_value_sheet(ws_cfg)
    cfg = _parse_cfg_from_sheet(kv)

    # Kvarvarande bonuskillar separat nyckel i state (så vi kan uppdatera live)
    st.session_state[BONUS_LEFT_KEY] = int(cfg.get("BONUS_AVAILABLE", DEFAULT_CFG["BONUS_AVAILABLE"]))

    # Data
    ws_data_name = f"Data_{profile_name}"
    ws_data = _ensure_ws(ws_data_name)
    records = ws_data.get_all_records()  # lista av dictar
    df = pd.DataFrame(records) if records else pd.DataFrame()

    # Säkerställ att DF åtminstone har kolumnen Datum (för ordning)
    if "Datum" not in df.columns:
        df["Datum"] = []

    # Lägg in i session_state
    st.session_state[CFG_KEY] = cfg
    st.session_state[DATA_KEY] = df
    st.session_state[HIST_KEY] = {}  # min/max byggs löpande

def _save_profile_settings(profile_name: str):
    """Spara nuvarande CFG till blad med profilens namn (Key/Value)."""
    ws = _ensure_ws(profile_name)
    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    rows = []
    for k, v in st.session_state[CFG_KEY].items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            v = v.strftime("%Y-%m-%d")
        elif isinstance(v, datetime.time):
            v = v.strftime("%H:%M")
        rows.append([k, str(v)])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def _save_profile_data(profile_name: str):
    """Spara DATA (DF) till blad 'Data_<profil>'."""
    ws = _ensure_ws(f"Data_{profile_name}")
    df = st.session_state.get(DATA_KEY, pd.DataFrame())
    ws.clear()
    if df.empty:
        ws.update("A1", [["Datum"]])
    else:
        ws.update("A1", [df.columns.tolist()])
        ws.update(f"A2", df.astype(str).values.tolist())

# ============ Profilväljare i sidopanel ============
with st.sidebar:
    st.subheader("Profil")
    profiles = _load_profile_names()
    if not profiles:
        st.info("Lägg till namn i bladet **Profil** (kolumn A).")
    # Standardprofil i state
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = profiles[0] if profiles else "Standard"

    sel = st.selectbox("Välj profil", options=profiles if profiles else [st.session_state[PROFILE_KEY]],
                       index=0 if profiles else 0, key="__profile_select__")

    # Ladda vald profil (vid första render eller byte)
    if sel != st.session_state[PROFILE_KEY] or CFG_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = sel
        _load_profile(sel)
        st.success(f"Profil '{sel}' inläst.")

    # Knappar för att spara
    cA, cB = st.columns(2)
    with cA:
        if st.button("💾 Spara inställningar", use_container_width=True):
            _save_profile_settings(st.session_state[PROFILE_KEY])
            st.success("Inställningar sparade till profilbladet.")
    with cB:
        if st.button("📤 Spara DATA", use_container_width=True):
            _save_profile_data(st.session_state[PROFILE_KEY])
            st.success("Data sparad till Data_-bladet för profilen.")

# =========================
# Del 3 — Scenario, inmatning, live, spara
# =========================

# ---- Små hjälpare för min/max & slump ----
def _minmax(col: str):
    mm = st.session_state[HIST_KEY].get(col)
    if mm:
        return mm
    # bygg från redan inläst DATA
    df = st.session_state.get(DATA_KEY, pd.DataFrame())
    if col in df.columns and not df.empty:
        try:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals):
                mm = (int(vals.min()), int(vals.max()))
            else:
                mm = (0, 0)
        except Exception:
            mm = (0, 0)
    else:
        mm = (0, 0)
    st.session_state[HIST_KEY][col] = mm
    return mm

def _rand_from_hist(col: str):
    lo, hi = _minmax(col)
    if hi < lo:
        hi = lo
    return random.randint(lo, hi) if hi > lo else lo

def _update_hist_from_row(row: dict):
    cols = ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
            "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]
    for c in cols:
        try:
            v = int(row.get(c, 0))
        except Exception:
            v = 0
        lo, hi = _minmax(c)
        st.session_state[HIST_KEY][c] = (min(lo, v), max(hi, v))

# ---- Scenario-fill (skriver BARA till input-state) ----
def apply_scenario_fill(scenario: str):
    CFG = st.session_state[CFG_KEY]

    # Nollställ alla in-fält först, men behåll dina tidsstandarder
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3}
    for key in [
        "in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
        "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
        "in_bekanta","in_eskilstuna","in_bonus_deltagit","in_personal_deltagit",
        "in_alskar","in_sover","in_tid_s","in_tid_d","in_vila","in_dt_tid","in_dt_vila","in_nils"
    ]:
        st.session_state[key] = keep_defaults.get(key, 0)

    if scenario == "Ny scen":
        return

    if scenario == "Slumpa scen vit":
        # Svarta = alltid 0
        st.session_state["in_svarta"] = 0
        # Slumpa övriga från historik
        st.session_state["in_man"]    = _rand_from_hist("Män")
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_from_hist(f)
        for f, key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                       ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                       ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_from_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif scenario == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_from_hist("Svarta")
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_from_hist(f)
        # övriga källor/personaldeltagit 0 enligt dina regler

    elif scenario == "Vila på jobbet":
        # Sexfält + källor slumpas
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_from_hist(f)
        for f, key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                       ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                       ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_from_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif scenario == "Vila i hemmet (dag 1–7)":
        # Förenklad: en dags slump enligt dina senaste regler
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_from_hist(f)
        for f, key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                       ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                       ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_from_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        # bonus/personaldeltagit anger du själv

# ---- Sidopanel: Scenario-knappar ----
with st.sidebar:
    st.subheader("Scenario")
    scen_val = st.selectbox("Välj scenario", ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
                            key="__scenario_sel__")
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill(scen_val)
        st.success("Värden hämtade till inmatningsfälten.")

# ---- Inmatningsfält (exakt ordning) ----
st.subheader("Input (exakt ordning)")

CFG = st.session_state[CFG_KEY]
c1, c2 = st.columns(2)

labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":f"{CFG['LBL_PAPPAN']} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{CFG['LBL_GRANNAR']} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{CFG['LBL_NILS_VANNER']} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{CFG['LBL_NILS_FAMILJ']} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{CFG['LBL_BEKANTA']} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{CFG['LBL_ESK']} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(st.session_state[BONUS_LEFT_KEY])})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_nils":"Nils (0/1/2)"
}

with c1:
    for key in ["in_man","in_svarta",
                "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
                "in_tid_s","in_tid_d","in_vila"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

with c2:
    for key in ["in_dt_tid","in_dt_vila","in_alskar"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
    for key in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
                "in_bekanta","in_eskilstuna",
                "in_bonus_deltagit","in_personal_deltagit",
                "in_nils"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

# ---- Bygg basrad (mappar alltid till KANONISKA namn för beräkningar) ----
def _build_base():
    # datum/veckodag
    df = st.session_state.get(DATA_KEY, pd.DataFrame())
    scen_nr = (len(df) + 1)
    d = CFG["startdatum"] + timedelta(days=scen_nr - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    veckodag = veckodagar[d.weekday()]

    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen_nr,
        "Typ": scen_val,

        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        "Pappans vänner": st.session_state["in_pappan"],
        "Grannar":        st.session_state["in_grannar"],
        "Nils vänner":    st.session_state["in_nils_vanner"],
        "Nils familj":    st.session_state["in_nils_familj"],
        "Bekanta":        st.session_state["in_bekanta"],
        "Eskilstuna killar": st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils": st.session_state["in_nils"],
        "Avgift": float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        # MAX för ”Känner sammanlagt” i beräkningar
        "MAX_PAPPAN":      int(CFG["MAX_PAPPAN"]),
        "MAX_GRANNAR":     int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
    }
    # meta för klocka
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

# ---- Live-förhandsvisning ----
st.markdown("---")
st.subheader("🔎 Live")

_base = _build_base()
try:
    preview = calc_row_values(_base, _base["_rad_datum"], _base["_fodelsedatum"], _base["_starttid"])
except TypeError:
    preview = calc_row_values(_base, _base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# Överkant: datum/ålder
rad_datum = preview.get("Datum", _base["Datum"])
veckodag  = preview.get("Veckodag", "-")
try:
    _dt = datetime.fromisoformat(rad_datum).date()
except Exception:
    _dt = datetime.today().date()
fd = CFG["fodelsedatum"]
alder = _dt.year - fd.year - ((_dt.month, _dt.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} • **Ålder:** {alder} år")

# Tid/Klocka/Män
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid", "-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
with c2:
    st.metric("Tid/kille", preview.get("Tid per kille", "-"))
    st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
with c3:
    st.metric("Klockan", preview.get("Klockan", "-"))
    st.metric("Totalt Män (rad)", int(preview.get("Totalt Män", 0)))

# Hångel/Sug
c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

# Ekonomi
st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter", int(preview.get("Prenumeranter", 0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet", 0)))
with e2:
    st.metric("Intäkter", f"${float(preview.get('Intäkter', 0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner', 0)):,.2f}")
with e3:
    st.metric("Utgift män", f"${float(preview.get('Utgift män', 0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin', 0)):,.2f}")
with e4:
    st.metric("Vinst", f"${float(preview.get('Vinst', 0)):,.2f}")
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

st.caption("Obs: Älskar/Sover-med ingår **inte** i scenens 'Summa tid', men läggs ovanpå klockan i separat vy.")

# ---- Spara lokalt / Sheets + bonuslogik ----
def _append_preview_to_df(preview_row: dict):
    df = st.session_state.get(DATA_KEY, pd.DataFrame())
    if df.empty:
        df = pd.DataFrame([preview_row])
    else:
        df = pd.concat([df, pd.DataFrame([preview_row])], ignore_index=True)
    st.session_state[DATA_KEY] = df

def _save_row_to_sheet(profile_name: str, preview_row: dict):
    ws = _ensure_ws(f"Data_{profile_name}")
    # säkerställ header
    header = ws.row_values(1)
    if not header:
        header = list(preview_row.keys())
        ws.update("A1", [header])
    values = [preview_row.get(col, "") for col in header]
    ws.append_row(values)

def _apply_bonus_bookkeeping(preview_row: dict):
    """Uppdatera BONUS_LEFT och även visa i etiketten/CFG."""
    # Nya bonus = Prenumeranter * BONUS_RATE_PCT/100
    pren = int(preview_row.get("Prenumeranter", 0))
    rate = float(CFG.get("BONUS_RATE_PCT", 1.0))
    bonus_new = int((pren * rate) // 100) if rate > 0 else 0
    used = int(_base.get("Bonus deltagit", 0))
    st.session_state[BONUS_LEFT_KEY] = max(0, st.session_state[BONUS_LEFT_KEY] + bonus_new - used)
    # spegla i CFG så etikett uppdateras
    CFG["BONUS_AVAILABLE"] = int(st.session_state[BONUS_LEFT_KEY])

# Knapp-rad
st.markdown("---")
cL, cR = st.columns(2)
with cL:
    if st.button("💾 Spara raden (lokalt)"):
        # Spara liven som den ser ut nu
        _append_preview_to_df(preview)
        _update_hist_from_row(preview)
        _apply_bonus_bookkeeping(preview)
        st.success("✅ Sparad lokalt.")
with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            _save_row_to_sheet(st.session_state[PROFILE_KEY], preview)
            _append_preview_to_df(preview)
            _update_hist_from_row(preview)
            _apply_bonus_bookkeeping(preview)
            st.success("✅ Sparad till Google Sheets (Data_…).")
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# ---- Visa lokala rader i denna session ----
st.markdown("---")
st.subheader("📋 Lokala rader (session)")
_df = st.session_state.get(DATA_KEY, pd.DataFrame())
if not _df.empty:
    st.dataframe(_df, use_container_width=True, height=320)
else:
    st.info("Inga rader ännu.")

# =========================
# Del 4 — Statistik (valfritt, om modul finns)
# =========================
try:
    from statistik import compute_stats
    st.markdown("---")
    st.subheader("📈 Statistik")

    if st.button("Beräkna statistik"):
        try:
            stats = compute_stats(st.session_state.get(DATA_KEY, pd.DataFrame()), st.session_state[CFG_KEY])
            if isinstance(stats, dict):
                for k, v in stats.items():
                    st.write(f"**{k}:** {v}")
            else:
                st.write(stats)
        except Exception as e:
            st.error(f"Kunde inte beräkna statistik: {e}")
except Exception as _e:
    # Statistikmodul saknas – inget att göra
    pass
