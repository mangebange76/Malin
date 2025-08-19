import streamlit as st
from datetime import date, time, datetime, timedelta
import random
import json
import pandas as pd

# ========================= App & Title =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp")

# ========================= State keys =========================
CFG_KEY       = "CFG"
ROWS_KEY      = "ROWS"           # sparade rader i minnet (för min/max)
HIST_MM_KEY   = "HIST_MINMAX"    # min/max per fält (bygger vi när du sparar)
SCENEINFO_KEY = "CURRENT_SCENE"  # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY  = "SCENARIO"       # rullist-valet

# ====== Inputfält – EXAKT ordning du begärt (och visning i en kolumn) ======
ORDERED_INPUT_KEYS = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover",
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_nils"
]

LABELS = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":"Pappans vänner","in_grannar":"Grannar",
    "in_nils_vanner":"Nils vänner","in_nils_familj":"Nils familj",
    "in_bekanta":"Bekanta","in_eskilstuna":"Eskilstuna killar",
    "in_bonus_deltagit":"Bonus deltagit","in_personal_deltagit":"Personal deltagit",
    "in_nils":"Nils"
}

# ========================= Init state =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7,0),
            "fodelsedatum": date(1995,1,1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,         # hela personalstyrkan som ska få lön
            "BONUS_AVAILABLE": 500,    # tillgängliga bonuskillar (endast info)
            "ESK_MIN": 20, "ESK_MAX": 40,
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []  # lista av dictar
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {} # t.ex. {"Fitta": (min,max), ...}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
    # säkra alla inputs med default = 0
    for k in ORDERED_INPUT_KEYS:
        st.session_state.setdefault(k, 0)
    # dagväljare för vila i hemmet
    st.session_state.setdefault("VIH_DAY", 1)

init_state()

# ========================= Import av beräkning =========================
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# ========================= Hjälpare (min/max) =========================
def _minmax_from_hist(colname: str):
    """Hämtar (min,max) från lokal historik; bygger från sparade rader om saknas."""
    if colname in st.session_state[HIST_MM_KEY]:
        return st.session_state[HIST_MM_KEY][colname]
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try:
            vals.append(int(r.get(colname, 0)))
        except:
            pass
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0, 0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# ========================= Scenariofyllning =========================
def apply_scenario_fill():
    """Fyller endast input-fälten i session_state – inga externa anrop."""
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla alla inputs först
    for k in ORDERED_INPUT_KEYS:
        st.session_state[k] = 0

    if s == "Ny scen":
        # allt 0 – du matar in själv
        pass

    elif s == "Slumpa scen vit":
        # Svarta = 0 (alltid)
        st.session_state["in_svarta"] = 0
        # Slumpa övriga via historik
        st.session_state["in_man"]    = _rand_hist("Män")
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_pappan"]      = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"]     = _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"]     = _rand_hist("Bekanta")
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        # bonus/personaldeltagit anger du manuellt

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        # andra källor = 0, personal deltagit = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_personal_deltagit"] = 0

    elif s == "Vila på jobbet":
        # Slumpa källor + sexuella fält
        for f, key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                       ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                       ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        # bonus/personaldeltagit anger du själv

    elif s == "Vila i hemmet (dag 1–7)":
        # dag 1–7 väljs i UI nedan (vi uppdaterar bara state här om behövs)
        day = st.session_state.get("VIH_DAY", 1)
        day = max(1, min(7, int(day)))
        st.session_state["VIH_DAY"] = day
        if day <= 5:
            # Slumpa ALLA fält du listade (utom bonus/personaldeltagit som du matar själv)
            st.session_state["in_fitta"]  = _rand_hist("Fitta")
            st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
            st.session_state["in_dp"]     = _rand_hist("DP")
            st.session_state["in_dpp"]    = _rand_hist("DPP")
            st.session_state["in_dap"]    = _rand_hist("DAP")
            st.session_state["in_tap"]    = _rand_hist("TAP")
            for f, key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                           ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                           ("Nils familj","in_nils_familj")]:
                st.session_state[key] = _rand_hist(f)
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 0
            # enkel Nils-slump för dagen (0/1/2)
            r = random.random()
            st.session_state["in_nils"] = 0 if r < 0.50 else (1 if r < 0.95 else 2)
        else:
            # Dag 6–7: allt 0 utom älskar=6 (sista dagen sover=1)
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 1 if day == 7 else 0
            # övriga fält förblir 0

    # uppdatera scen-info
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ========================= Sidopanel =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    st.caption(f"Bonus killar tillgängliga (info): {int(CFG['BONUS_AVAILABLE'])}")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1)

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.session_state[SCENARIO_KEY] == "Vila i hemmet (dag 1–7)":
        st.session_state["VIH_DAY"] = st.number_input("Dag (1–7)", min_value=1, max_value=7, value=st.session_state["VIH_DAY"], step=1)
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

# ========================= UI – Inputs (EN kolumn, exakt ordning) =========================
st.subheader("Input (exakt ordning) — en kolumn")
for key in ORDERED_INPUT_KEYS:
    if key == "in_sover":
        st.number_input(LABELS[key], min_value=0, max_value=1, step=1, key=key)
    else:
        st.number_input(LABELS[key], min_value=0, step=1, key=key)

# ========================= Live-förhandsvisning =========================
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],

        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        "Pappans vänner": st.session_state["in_pappan"], "Grannar": st.session_state["in_grannar"],
        "Nils vänner": st.session_state["in_nils_vanner"], "Nils familj": st.session_state["in_nils_familj"],
        "Bekanta": st.session_state["in_bekanta"], "Eskilstuna killar": st.session_state["in_eskilstuna"],

        "Bonus deltagit": st.session_state["in_bonus_deltagit"], "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils": st.session_state["in_nils"],
        "Avgift": float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"]),
    }
    base["Känner"] = int(base["Pappans vänner"]) + int(base["Grannar"]) + int(base["Nils vänner"]) + int(base["Nils familj"])
    # meta för beräkning
    base["_rad_datum"] = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
    return base

st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    # fallback om din beräkning har äldre signatur
    preview = calc_row_values(base, base["_rad_datum"], st.session_state[CFG_KEY]["fodelsedatum"], st.session_state[CFG_KEY]["starttid"])

# Överkant: datum/veckodag + ålder
rad_datum = preview.get("Datum", base["Datum"])
veckodag = preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try:
        _d = datetime.fromisoformat(rad_datum).date()
    except Exception:
        _d = datetime.today().date()
else:
    _d = datetime.today().date()
fd = st.session_state[CFG_KEY]["fodelsedatum"]
alder = _d.year - fd.year - (( _d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

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
    st.metric("Totalt män", int(preview.get("Totalt Män",0)))

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

st.caption("Obs: Älskar/Sover med ingår inte i scenens 'Summa tid', men läggs på klockan.")

# ========================= Google Sheets helpers =========================
def _get_gspread_client():
    # Kräver st.secrets["GOOGLE_CREDENTIALS"] och ["GOOGLE_SHEET_ID"]
    try:
        from google.oauth2.service_account import Credentials
        import gspread
    except Exception as e:
        st.error(f"Saknar gspread/google auth: {e}")
        return None, None

    if "GOOGLE_CREDENTIALS" not in st.secrets or "GOOGLE_SHEET_ID" not in st.secrets:
        st.error("Secrets för Google saknas (GOOGLE_CREDENTIALS och GOOGLE_SHEET_ID).")
        return None, None

    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        sa_info = json.loads(creds_raw)
    else:
        # AttrDict / Mapping → vanlig dict
        sa_info = json.loads(json.dumps(creds_raw))

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)
    sid = st.secrets["GOOGLE_SHEET_ID"]
    try:
        sh = gc.open_by_key(sid)
    except Exception as e:
        st.error(f"Kunde inte öppna Google Sheet: {e}")
        return None, None
    return gc, sh

def _get_or_create_worksheet(sh, title="Data"):
    import gspread
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=2000, cols=100)

def _ensure_header(ws, header_cols):
    # Läs första raden; om tom → skriv header
    try:
        header = ws.row_values(1)
    except Exception:
        header = []
    if not header:
        ws.update(f"A1:{chr(64+len(header_cols))}1", [header_cols])
        return header_cols
    return header

# ========================= Spara – Lokalt & Sheets =========================
st.markdown("---")
col_save1, col_save2 = st.columns([1,1])

with col_save1:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        # uppdatera min/max för slump framöver
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    "Pappans vänner","Grannar","Nils vänner","Nils familj",
                    "Bekanta","Eskilstuna killar"]:
            v = int(preview.get(col,0))
            mn,mx = st.session_state[HIST_MM_KEY].get(col,(v,v))
            st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
        # bonus-available: minska med inmatat bonus deltagit (du styr själv)
        st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = max(
            0,
            int(st.session_state[CFG_KEY]["BONUS_AVAILABLE"]) - int(preview.get("Bonus deltagit",0))
        )
        # nästa scen
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad i minnet.")

with col_save2:
    if st.button("🟢 Spara raden till Google Sheets"):
        gc, sh = _get_gspread_client()
        if gc and sh:
            try:
                ws = _get_or_create_worksheet(sh, title="Data")
                # Säkerställ header (första gången – ta nycklarna från preview i den ordning de kommer)
                header_cols = list(preview.keys())
                header = _ensure_header(ws, header_cols)
                # Bygg rad i samma kolumnordning som header
                row = [preview.get(col, "") for col in header]
                ws.append_row(row)
                # uppdatera lokal historik & scen
                st.session_state[ROWS_KEY].append(preview)
                for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                            "Pappans vänner","Grannar","Nils vänner","Nils familj",
                            "Bekanta","Eskilstuna killar"]:
                    v = int(preview.get(col,0))
                    mn,mx = st.session_state[HIST_MM_KEY].get(col,(v,v))
                    st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success("✅ Raden sparad till Google Sheets.")
            except Exception as e:
                st.error(f"Misslyckades att spara till Sheets: {e}")

# ========================= Visa lokala rader =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=300)
else:
    st.info("Inga lokala rader ännu.")
