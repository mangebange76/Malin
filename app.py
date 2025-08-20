import streamlit as st
import pandas as pd
import random
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime, timedelta

# Importera statistik
from statistik import compute_stats

st.set_page_config(page_title="Malin-produktionsapp", layout="wide")

# -------------------------
# Globala nycklar för session_state
# -------------------------
ROWS_KEY          = "ROWS"
PROFILE_KEY       = "PROFILE"
PROFILE_LOADED    = "PROFILE_LOADED"
SCENEINFO_KEY     = "SCENEINFO"
HIST_MM_KEY       = "HIST_MINMAX"
BONUS_LEFT_KEY    = "BONUS_LEFT"

# -------------------------
# Default CFG (kan skrivas över från Inställningar i Google Sheets)
# -------------------------
CFG = {
    "startdatum":   date(1990, 1, 1),
    "fodelsedatum": date(1990, 1, 1),
    "BONUS_RATE": 0.01,
    "BONUS_AVAILABLE": 10000,
    "LBL_PAPPAN": "Pappan",
    "LBL_GRANNAR": "Grannar",
    "LBL_NILS_VANNER": "NilsV",
    "LBL_NILS_FAMILJ": "NilsF",
    "LBL_BEKANTA": "Bekanta",
    "LBL_ESK": "Eskorter",
}

# -------------------------
# Google Sheets koppling
# -------------------------
def _get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    return gspread.authorize(creds).open_by_url(st.secrets["SHEET_URL"])

def _ensure_ws(ss, title: str):
    """Returnera worksheet, skapa om saknas."""
    try:
        return ss.worksheet(title)
    except Exception:
        return ss.add_worksheet(title=title, rows="100", cols="20")

def _get_profiles(ss):
    """Hämta listan med profiler från bladet 'Profil'."""
    try:
        ws = _ensure_ws(ss, "Profil")
        vals = ws.col_values(1)
        return [v for v in vals if v.strip()]
    except Exception:
        return []

# -------------------------
# Hjälpfunktioner för statistik/slump
# -------------------------
def _add_hist_value(col, val):
    if not isinstance(val, (int, float)):
        try:
            val = int(val)
        except:
            return
    hist = st.session_state.get(HIST_MM_KEY, {})
    if col not in hist:
        hist[col] = {"min": val, "max": val}
    else:
        hist[col]["min"] = min(hist[col]["min"], val)
        hist[col]["max"] = max(hist[col]["max"], val)
    st.session_state[HIST_MM_KEY] = hist

def _rand_val(col):
    """Returnera slumpat heltal mellan min och max för en kolumn, eller 0."""
    hist = st.session_state.get(HIST_MM_KEY, {})
    if col not in hist:
        return 0
    lo, hi = hist[col]["min"], hist[col]["max"]
    if lo > hi:
        lo, hi = hi, lo
    return random.randint(int(lo), int(hi))

# -------------------------
# Ladda profil och data
# -------------------------
def _load_profile_and_data(profile_name: str):
    """Läs in både inställningar och scen-data för en vald profil."""
    ss = _get_gspread_client()

    # 1. Hämta inställningar från profil-bladet
    ws_prof = _ensure_ws(ss, "Profil")
    prof_data = ws_prof.get_all_records()

    cfg = CFG.copy()
    for row in prof_data:
        if row.get("Profil") == profile_name:
            if "Startdatum" in row and row["Startdatum"]:
                try:
                    cfg["startdatum"] = datetime.strptime(row["Startdatum"], "%Y-%m-%d").date()
                except:
                    pass
            if "Fodelsedatum" in row and row["Fodelsedatum"]:
                try:
                    cfg["fodelsedatum"] = datetime.strptime(row["Fodelsedatum"], "%Y-%m-%d").date()
                except:
                    pass
            if "BONUS_RATE" in row and row["BONUS_RATE"]:
                cfg["BONUS_RATE"] = float(row["BONUS_RATE"])
            if "BONUS_AVAILABLE" in row and row["BONUS_AVAILABLE"]:
                cfg["BONUS_AVAILABLE"] = int(row["BONUS_AVAILABLE"])

    # 2. Hämta scener från Data-bladet
    ws_data = _ensure_ws(ss, f"Data_{profile_name}")
    rows = pd.DataFrame(ws_data.get_all_records())

    # Sätt start i session_state
    st.session_state[PROFILE_KEY] = profile_name
    st.session_state[PROFILE_LOADED] = True
    st.session_state[ROWS_KEY] = rows
    st.session_state[SCENEINFO_KEY] = rows.to_dict("records")
    st.session_state[BONUS_LEFT_KEY] = cfg["BONUS_AVAILABLE"]

    return cfg, rows


# -------------------------
# Spara scen-rader
# -------------------------
def _save_rows(profile_name: str, rows: pd.DataFrame):
    ss = _get_gspread_client()
    ws_data = _ensure_ws(ss, f"Data_{profile_name}")
    if rows.empty:
        ws_data.clear()
    else:
        ws_data.clear()
        ws_data.update([rows.columns.values.tolist()] + rows.astype(str).values.tolist())


# -------------------------
# Sidopanel för profilval
# -------------------------
def sidebar():
    st.sidebar.header("Profil")
    ss = _get_gspread_client()
    profiles = _get_profiles(ss)

    if not profiles:
        st.sidebar.warning("Inga profiler hittades. Skapa en i bladet 'Profil'.")
        return None, None

    selected_profile = st.sidebar.selectbox("Välj profil", profiles)

    if st.sidebar.button("Ladda profil"):
        cfg, rows = _load_profile_and_data(selected_profile)
        st.success(f"Profil '{selected_profile}' laddad.")
        return cfg, rows

    if PROFILE_KEY in st.session_state and st.session_state[PROFILE_LOADED]:
        return CFG, st.session_state[ROWS_KEY]

    return None, None

# -------------------------
# Hjälpare: min/max från Data + slump
# -------------------------
def _minmax_from_df(df: pd.DataFrame, col: str):
    if df is None or df.empty or col not in df.columns:
        return (0, 0)
    try:
        s = pd.to_numeric(df[col], errors="coerce").dropna().astype(int)
        if s.empty:
            return (0, 0)
        return (int(s.min()), int(s.max()))
    except Exception:
        return (0, 0)

def _rand_from_df(df: pd.DataFrame, col: str):
    lo, hi = _minmax_from_df(df, col)
    if hi < lo:
        hi = lo
    return random.randint(lo, hi) if hi > lo else lo


# -------------------------
# Input-ordning (EXAKT) och labels
# -------------------------
INPUT_KEYS = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover",
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_nils"
]

def _ensure_input_defaults():
    defaults = {
        "in_tid_s": 60, "in_tid_d": 60, "in_vila": 7,
        "in_dt_tid": 60, "in_dt_vila": 3,
        "in_alskar": 0, "in_sover": 0, "in_nils": 0
    }
    for k in INPUT_KEYS:
        st.session_state.setdefault(k, defaults.get(k, 0))


# -------------------------
# Scenario-fill (skriver endast till session_state inputs)
# -------------------------
def apply_scenario_fill(cfg: dict, rows_df: pd.DataFrame, scenario: str):
    _ensure_input_defaults()

    # Nollställ (behåll standarder för tidsfält)
    keep = {"in_tid_s","in_tid_d","in_vila","in_dt_tid","in_dt_vila"}
    for k in INPUT_KEYS:
        if k not in keep:
            st.session_state[k] = 0

    # Alias för etiketter (kan vara omdöpta i sidopanel)
    lbl_p = cfg["LBL_PAPPAN"]
    lbl_g = cfg["LBL_GRANNAR"]
    lbl_nv = cfg["LBL_NILS_VANNER"]
    lbl_nf = cfg["LBL_NILS_FAMILJ"]
    lbl_bk = cfg["LBL_BEKANTA"]
    lbl_esk = cfg["LBL_ESK"]

    def rand_hist(col):
        # stöd både Data_<profil> och lokala st.state[ROWS_KEY]
        return _rand_from_df(rows_df, col)

    if scenario == "Ny scen" or scenario is None:
        return

    elif scenario == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = rand_hist("Män")
        for src, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                         ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = rand_hist(src)
        for src, key in [(lbl_p,"in_pappan"),(lbl_g,"in_grannar"),
                         (lbl_nv,"in_nils_vanner"),(lbl_nf,"in_nils_familj"),
                         (lbl_bk,"in_bekanta")]:
            st.session_state[key] = rand_hist(src)
        st.session_state["in_eskilstuna"] = random.randint(int(cfg["ESK_MIN"]), int(cfg["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif scenario == "Slumpa scen svart":
        st.session_state["in_svarta"] = rand_hist("Svarta")
        for src, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                         ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = rand_hist(src)
        # övriga källor/personaldeltagit = 0 (redan nollade)

    elif scenario == "Vila på jobbet":
        # Sexuella + källor slumpas
        for src, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                         ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = rand_hist(src)
        for src, key in [(lbl_p,"in_pappan"),(lbl_bk,"in_bekanta"),
                         (lbl_g,"in_grannar"),(lbl_nv,"in_nils_vanner"),(lbl_nf,"in_nils_familj")]:
            st.session_state[key] = rand_hist(src)
        st.session_state["in_eskilstuna"] = random.randint(int(cfg["ESK_MIN"]), int(cfg["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif scenario == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dags slump (enligt din senaste spec)
        for src, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                         ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = rand_hist(src)
        for src, key in [(lbl_p,"in_pappan"),(lbl_g,"in_grannar"),
                         (lbl_nv,"in_nils_vanner"),(lbl_nf,"in_nils_familj"),
                         (lbl_bk,"in_bekanta")]:
            st.session_state[key] = rand_hist(src)
        st.session_state["in_eskilstuna"] = random.randint(int(cfg["ESK_MIN"]), int(cfg["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    # uppdatera “current scene” (nr, datum, veckodag) baserat på aktuella rader
    scen_nr = (0 if st.session_state.get(ROWS_KEY) is None else len(st.session_state[ROWS_KEY])) + 1
    d = cfg["startdatum"] + datetime.timedelta(days=scen_nr - 1)
    veckonamn = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]
    st.session_state[SCENEINFO_KEY] = (scen_nr, d, veckonamn)


# -------------------------
# Input-formulär (exakt ordning)
# -------------------------
def render_input_form(cfg: dict):
    _ensure_input_defaults()

    lbl_p = cfg["LBL_PAPPAN"]
    lbl_g = cfg["LBL_GRANNAR"]
    lbl_nv = cfg["LBL_NILS_VANNER"]
    lbl_nf = cfg["LBL_NILS_FAMILJ"]
    lbl_bk = cfg["LBL_BEKANTA"]
    lbl_esk = cfg["LBL_ESK"]

    labels = {
        "in_man": "Män",
        "in_svarta": "Svarta",
        "in_fitta": "Fitta",
        "in_rumpa": "Rumpa",
        "in_dp": "DP",
        "in_dpp":"DPP",
        "in_dap":"DAP",
        "in_tap":"TAP",
        "in_tid_s":"Tid S (sek)",
        "in_tid_d":"Tid D (sek)",
        "in_vila":"Vila (sek)",
        "in_dt_tid":"DT tid (sek/kille)",
        "in_dt_vila":"DT vila (sek/kille)",
        "in_alskar":"Älskar",
        "in_sover":"Sover med (0/1)",
        "in_pappan": f"{lbl_p} (MAX {int(cfg['MAX_PAPPAN'])})",
        "in_grannar": f"{lbl_g} (MAX {int(cfg['MAX_GRANNAR'])})",
        "in_nils_vanner": f"{lbl_nv} (MAX {int(cfg['MAX_NILS_VANNER'])})",
        "in_nils_familj": f"{lbl_nf} (MAX {int(cfg['MAX_NILS_FAMILJ'])})",
        "in_bekanta": f"{lbl_bk} (MAX {int(cfg['MAX_BEKANTA'])})",
        "in_eskilstuna": f"{lbl_esk} ({int(cfg['ESK_MIN'])}–{int(cfg['ESK_MAX'])})",
        "in_bonus_deltagit": f"Bonus deltagit (kvar {int(st.session_state.get(BONUS_LEFT_KEY, cfg['BONUS_AVAILABLE']))})",
        "in_personal_deltagit": f"Personal deltagit (av {int(cfg['PROD_STAFF'])})",
        "in_nils":"Nils (0/1/2)",
    }

    st.subheader("Input (exakt ordning)")
    c1, c2 = st.columns(2)

    with c1:
        for key in [
            "in_man","in_svarta",
            "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
            "in_tid_s","in_tid_d","in_vila"
        ]:
            st.number_input(labels[key], min_value=0, step=1, key=key)

    with c2:
        for key in ["in_dt_tid","in_dt_vila","in_alskar"]:
            st.number_input(labels[key], min_value=0, step=1, key=key)
        st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
        for key in [
            "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
            "in_bekanta","in_eskilstuna",
            "in_bonus_deltagit","in_personal_deltagit",
            "in_nils"
        ]:
            st.number_input(labels[key], min_value=0, step=1, key=key)

# -------------------------
# Bygg basrad från inputs (använder dynamiska etiketter)
# -------------------------
def _build_base(cfg: dict):
    # Sceninfo
    if SCENEINFO_KEY in st.session_state:
        scen_nr, d, veckodag = st.session_state[SCENEINFO_KEY]
    else:
        # fallback om något saknas
        scen_nr = len(st.session_state.get(ROWS_KEY, [])) + 1
        d = cfg["startdatum"] + datetime.timedelta(days=scen_nr - 1)
        veckodag = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]
        st.session_state[SCENEINFO_KEY] = (scen_nr, d, veckodag)

    # Etiketter (namn som kan ändras i sidopanel)
    lbl_p  = cfg["LBL_PAPPAN"]
    lbl_g  = cfg["LBL_GRANNAR"]
    lbl_nv = cfg["LBL_NILS_VANNER"]
    lbl_nf = cfg["LBL_NILS_FAMILJ"]
    lbl_bk = cfg["LBL_BEKANTA"]
    lbl_esk= cfg["LBL_ESK"]

    base = {
        "Datum": d.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen_nr,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        # Inmatning (kärnordning)
        "Män":   int(st.session_state.get("in_man", 0)),
        "Svarta":int(st.session_state.get("in_svarta", 0)),
        "Fitta": int(st.session_state.get("in_fitta", 0)),
        "Rumpa": int(st.session_state.get("in_rumpa", 0)),
        "DP":    int(st.session_state.get("in_dp", 0)),
        "DPP":   int(st.session_state.get("in_dpp", 0)),
        "DAP":   int(st.session_state.get("in_dap", 0)),
        "TAP":   int(st.session_state.get("in_tap", 0)),

        "Tid S": int(st.session_state.get("in_tid_s", 60)),
        "Tid D": int(st.session_state.get("in_tid_d", 60)),
        "Vila":  int(st.session_state.get("in_vila", 7)),
        "DT tid (sek/kille)":  int(st.session_state.get("in_dt_tid", 60)),
        "DT vila (sek/kille)": int(st.session_state.get("in_dt_vila", 3)),

        "Älskar":    int(st.session_state.get("in_alskar", 0)),
        "Sover med": int(st.session_state.get("in_sover", 0)),

        # Källor med dynamiska labels
        lbl_p:   int(st.session_state.get("in_pappan", 0)),
        lbl_g:   int(st.session_state.get("in_grannar", 0)),
        lbl_nv:  int(st.session_state.get("in_nils_vanner", 0)),
        lbl_nf:  int(st.session_state.get("in_nils_familj", 0)),
        lbl_bk:  int(st.session_state.get("in_bekanta", 0)),
        lbl_esk: int(st.session_state.get("in_eskilstuna", 0)),

        "Bonus deltagit":    int(st.session_state.get("in_bonus_deltagit", 0)),
        "Personal deltagit": int(st.session_state.get("in_personal_deltagit", 0)),

        "Nils": int(st.session_state.get("in_nils", 0)),

        # Metadata/konfig
        "Avgift":     float(cfg.get("avgift_usd", 30.0)),
        "PROD_STAFF": int(cfg.get("PROD_STAFF", 800)),

        # Max för statistik (skickas till beräkningsmodul om den använder dem)
        "MAX_PAPPAN":      int(cfg.get("MAX_PAPPAN", 0)),
        "MAX_GRANNAR":     int(cfg.get("MAX_GRANNAR", 0)),
        "MAX_NILS_VANNER": int(cfg.get("MAX_NILS_VANNER", 0)),
        "MAX_NILS_FAMILJ": int(cfg.get("MAX_NILS_FAMILJ", 0)),
        "MAX_BEKANTA":     int(cfg.get("MAX_BEKANTA", 0)),
    }

    # Känner (rad) som ren summa av fyra källor
    base["Känner"] = (base[lbl_p] + base[lbl_g] + base[lbl_nv] + base[lbl_nf])

    # meta till beräkning
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = cfg["fodelsedatum"]
    base["_starttid"]     = cfg["starttid"]

    return base


# -------------------------
# Live-panel (kallar beräkning)
# -------------------------
def render_live_and_preview(cfg: dict, rows_df: pd.DataFrame):
    base = _build_base(cfg)
    try:
        preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
    except TypeError:
        # fallback till äldre signatur (om din beräkningsmodul råkar vara så)
        preview = calc_row_values(base, base["_rad_datum"], cfg["fodelsedatum"], cfg["starttid"])

    # Visa datum/ålder
    try:
        rad_datum = preview.get("Datum", base["Datum"])
        if isinstance(rad_datum, str):
            _d = datetime.date.fromisoformat(rad_datum)
        elif isinstance(rad_datum, datetime.date):
            _d = rad_datum
        else:
            _d = datetime.date.today()
    except Exception:
        _d = datetime.date.today()

    fd = cfg["fodelsedatum"]
    alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))

    st.markdown("---")
    st.subheader("🔎 Live")
    st.markdown(f"**Datum/Veckodag:** {preview.get('Datum', base['Datum'])} / {preview.get('Veckodag','-')} &nbsp;•&nbsp; **Ålder:** {alder} år")

    # Tid/Klocka/Män
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", preview.get("Summa tid","-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
    with c2:
        st.metric("Tid/kille", preview.get("Tid per kille","-"))
        st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)",0)))
    with c3:
        st.metric("Klockan", preview.get("Klockan","-"))
        st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))

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
        st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))
        st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
    with e2:
        st.metric("Intäkter", f"${float(preview.get('Intäkter',0)):,.2f}")
        st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner',0)):,.2f}")
    with e3:
        st.metric("Utgift män", f"${float(preview.get('Utgift män',0)):,.2f}")
        st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
    with e4:
        st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
        st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

    # Källor (med dynamiska etiketter)
    lbl_p  = cfg["LBL_PAPPAN"]
    lbl_g  = cfg["LBL_GRANNAR"]
    lbl_nv = cfg["LBL_NILS_VANNER"]
    lbl_nf = cfg["LBL_NILS_FAMILJ"]
    lbl_bk = cfg["LBL_BEKANTA"]
    lbl_esk= cfg["LBL_ESK"]

    st.markdown("**👥 Källor (live)**")
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: st.metric(lbl_p,   int(base.get(lbl_p,0)))
    with k2: st.metric(lbl_g,   int(base.get(lbl_g,0)))
    with k3: st.metric(lbl_nv,  int(base.get(lbl_nv,0)))
    with k4: st.metric(lbl_nf,  int(base.get(lbl_nf,0)))
    with k5: st.metric(lbl_bk,  int(base.get(lbl_bk,0)))
    with k6: st.metric(lbl_esk, int(base.get(lbl_esk,0)))

    # Visa “bonus killar kvar” live (från state-key om vi för ledger)
    bleft = int(st.session_state.get(BONUS_LEFT_KEY, cfg.get("BONUS_AVAILABLE", 0)))
    st.caption(f"Bonus killar kvar (live): **{bleft}**")

    return base, preview


# -------------------------
# Spara-rutiner (lokalt + Sheets) + bonus-uppdatering
# -------------------------
def _update_minmax_cache_from_row(row: dict, cfg: dict):
    # uppdatera min/max för kolumner som används i slump
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                cfg["LBL_PAPPAN"], cfg["LBL_GRANNAR"], cfg["LBL_NILS_VANNER"],
                cfg["LBL_NILS_FAMILJ"], cfg["LBL_BEKANTA"], cfg["LBL_ESK"]]:
        try:
            v = int(row.get(col, 0))
        except Exception:
            v = 0
        # bygg/uppdatera cache i st.session_state[HIST_MM_KEY] om du använder den i tidigare delar
        mm = st.session_state.get(HIST_MM_KEY, {})
        mn, mx = mm.get(col, (v, v))
        st.session_state.setdefault(HIST_MM_KEY, {})[col] = (min(mn, v), max(mx, v))

def _apply_bonus_ledger_on_save(preview: dict, cfg: dict):
    """
    Uppdaterar 'bonus killar kvar' (ledger i session) vid spar:
    - Lägg till nybonus = int(Prenumeranter * BONUS_RATE_PCT/100)
    - Dra av 'Bonus deltagit' från raden
    """
    rate_pct = float(cfg.get("BONUS_RATE_PCT", 1.0))
    new_bonus = int(round(int(preview.get("Prenumeranter", 0)) * (rate_pct / 100.0)))
    used_bonus = int(preview.get("Bonus deltagit", 0))

    current_left = int(st.session_state.get(BONUS_LEFT_KEY, cfg.get("BONUS_AVAILABLE", 0)))
    current_left = current_left + new_bonus - used_bonus
    if current_left < 0:
        current_left = 0
    st.session_state[BONUS_LEFT_KEY] = current_left
    # spegla till CFG (så etiketter i UI visar samma direkt)
    cfg["BONUS_AVAILABLE"] = current_left

def _save_to_sheets(row_dict: dict):
    # kräver Del 1 hjälpare: _get_gspread_client, _ensure_ws
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, "Data")
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

# -------------------------
# Render: spara-knappar + statistik
# -------------------------
def render_save_and_stats(cfg: dict, rows_df: pd.DataFrame, base: dict, preview: dict):
    st.markdown("---")
    cL, cR = st.columns([1,1])

    with cL:
        if st.button("💾 Spara raden (lokalt)"):
            # lägg till raden i lokalt DataFrame → session
            new_row = preview.copy()
            # ledger bonus
            _apply_bonus_ledger_on_save(preview, cfg)
            # lägg in i sessionens rader-list (behåll som list[dict] för enkelhet)
            st.session_state.setdefault(ROWS_KEY, [])
            st.session_state[ROWS_KEY].append(new_row)
            # uppdatera min/max cache
            _update_minmax_cache_from_row(new_row, cfg)
            # bumpa sceninfo
            scen_nr = len(st.session_state[ROWS_KEY]) + 1
            d = cfg["startdatum"] + datetime.timedelta(days=scen_nr - 1)
            veckodag = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]
            st.session_state[SCENEINFO_KEY] = (scen_nr, d, veckodag)
            st.success("✅ Sparad i minnet.")

    with cR:
        if st.button("📤 Spara raden till Google Sheets"):
            try:
                _save_to_sheets(preview)
                # ledger bonus även vid Sheets-spar
                _apply_bonus_ledger_on_save(preview, cfg)
                # lägg i lokalt minne och bumpa scen för konsekvens
                st.session_state.setdefault(ROWS_KEY, [])
                st.session_state[ROWS_KEY].append(preview.copy())
                _update_minmax_cache_from_row(preview, cfg)
                scen_nr = len(st.session_state[ROWS_KEY]) + 1
                d = cfg["startdatum"] + datetime.timedelta(days=scen_nr - 1)
                veckodag = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]
                st.session_state[SCENEINFO_KEY] = (scen_nr, d, veckodag)
                st.success("✅ Sparad till Google Sheets (flik: Data).")
            except Exception as e:
                st.error(f"Misslyckades att spara till Sheets: {e}")

    # Visa lokala rader som tabell
    st.markdown("---")
    st.subheader("📋 Lokala rader (förhandslagrade)")
    rows = st.session_state.get(ROWS_KEY, [])
    if rows:
        df_show = pd.DataFrame(rows)
        st.dataframe(df_show, use_container_width=True, height=320)
    else:
        st.info("Inga lokala rader ännu.")

    # Statistik (om statistik-modul finns)
    st.markdown("---")
    st.subheader("📊 Statistik (profil)")
    try:
        # import redan gjord i Del 1; här bara användning
        # bygg en DataFrame “rows_df_current” från lokala rader (eller använd rows_df)
        rows_df_current = pd.DataFrame(st.session_state.get(ROWS_KEY, []))
        stats = compute_stats(rows_df_current, cfg)
        # visa nycklar/values
        if isinstance(stats, dict):
            for k, v in stats.items():
                st.write(f"**{k}:** {v}")
        else:
            st.write(stats)
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")


# -------------------------
# Kör Del 4 (render live + spara + statistik)
# -------------------------
# Viktigt: Del 2 bör ha satt rows_df (Data_<profil>) eller None
try:
    rows_df = st.session_state.get("PROFILE_ROWS_DF")  # Del 2 ska lägga denna
except Exception:
    rows_df = None

# Render live + preview
_base, _preview = render_live_and_preview(CFG, rows_df)

# Render save/statistik
render_save_and_stats(CFG, rows_df, _base, _preview)
