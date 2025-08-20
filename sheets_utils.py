# sheets_utils.py
import json
from typing import List, Tuple, Dict, Any

import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread


# -------------------------------
# Låg nivå: koppling & worksheets
# -------------------------------
def get_client():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS och/eller SHEET_URL).")
    raw = st.secrets["GOOGLE_CREDENTIALS"]
    creds_info = json.loads(raw) if isinstance(raw, str) else json.loads(json.dumps(dict(raw)))
    creds = Credentials.from_service_account_info(creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return ss

def ensure_ws(ss, title: str, rows: int = 4000, cols: int = 80):
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)


# -------------------------------
# Hjälpare
# -------------------------------
_NUM_COLS = {
    "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
    "Älskar","Sover med","Bonus deltagit","Personal deltagit",
    "Prenumeranter","Hårdhet","Intäkter","Intäkt Känner","Kostnad män",
    "Lön Malin","Intäkt företag","Vinst","Suger","Suger per kille (sek)",
    "Händer per kille (sek)","Händer aktiv","Totalt Män","Känner","Känner sammanlagt"
}

def _to_num(x):
    try:
        if x is None or x == "":
            return 0
        # vissa kommer in som "12.0" / "12,0"
        xs = str(x).replace(",", ".")
        if xs.strip().isdigit():
            return int(xs)
        return float(xs)
    except Exception:
        return 0

def _normalize_labels(rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Säkerställ att både ”kanoniska” och etikettnamn finns.
    Ex: om raden har ”Eskilstuna killar” men cfg säger LBL_ESK="Kalles gäng",
    kopiera värdet så att båda nycklarna finns (samma siffra).
    """
    canon_to_lbl = {
        "Pappans vänner": cfg.get("LBL_PAPPAN", "Pappans vänner"),
        "Grannar":        cfg.get("LBL_GRANNAR","Grannar"),
        "Nils vänner":    cfg.get("LBL_NILS_VANNER","Nils vänner"),
        "Nils familj":    cfg.get("LBL_NILS_FAMILJ","Nils familj"),
        "Bekanta":        cfg.get("LBL_BEKANTA","Bekanta"),
        "Eskilstuna killar": cfg.get("LBL_ESK","Eskilstuna killar"),
    }
    out = []
    for r in rows:
        r2 = dict(r)
        # spegla båda nycklarna
        for canon, lbl in canon_to_lbl.items():
            if canon in r2 and lbl not in r2:
                r2[lbl] = r2[canon]
            if lbl in r2 and canon not in r2:
                r2[canon] = r2[lbl]
        # numeriska fält -> tal
        for k, v in list(r2.items()):
            if k in _NUM_COLS:
                r2[k] = _to_num(v)
        # default för "Händer aktiv" om saknas
        if "Händer aktiv" not in r2 and "Hander aktiv" in r2:
            r2["Händer aktiv"] = _to_num(r2["Hander aktiv"])
        if "Händer aktiv" not in r2:
            r2["Händer aktiv"] = 1
        out.append(r2)
    return out


# -------------------------------
# Läsa profiler & innehåll
# -------------------------------
def list_profiles() -> List[str]:
    ss = get_client()
    ws = ensure_ws(ss, "Profil")
    names = [x.strip() for x in ws.col_values(1) if x and x.strip()]
    # ta bort rubrikrad om du har ”Namn” överst
    if names and names[0].lower() in ("namn","name"):
        names = names[1:]
    return names

def read_profile_settings(profile_name: str) -> Dict[str, Any]:
    """
    Läser bladet som heter exakt som profilen. Förväntar två kolumner Key/Value
    (med eller utan rubrikrad). Returnerar en dict.
    """
    ss = get_client()
    ws = ensure_ws(ss, profile_name)
    vals = ws.get_all_values()
    out = {}
    if not vals:
        return out
    # hoppa rubrikrad om första raden ser ut som headers
    start = 1 if len(vals[0]) >= 2 and vals[0][0].strip().lower() in ("key","nyckel") else 0
    for row in vals[start:]:
        if not row or len(row) < 2:
            continue
        k = str(row[0]).strip()
        v = str(row[1]).strip()
        if not k:
            continue
        # typning
        if k in ("startdatum","fodelsedatum"):
            try:
                y, m, d = [int(x) for x in v.split("-")]
                out[k] = pd.Timestamp(y, m, d).date()
                continue
            except Exception:
                pass
        try:
            out[k] = int(v) if v.isdigit() else float(v.replace(",", "."))
        except Exception:
            out[k] = v
    return out

def read_profile_rows(profile_name: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Läser alla rader från fliken 'Data' och filtrerar på kolumn 'Profil' == profile_name,
    om kolumnen finns. Normaliserar sedan mot etiketter + numerik.
    """
    ss = get_client()
    ws = ensure_ws(ss, "Data")
    records = ws.get_all_records()  # list[dict]
    if not records:
        return []
    if "Profil" in records[0]:
        filtered = [r for r in records if str(r.get("Profil","")).strip() == str(profile_name)]
    else:
        filtered = records
    return _normalize_labels(filtered, cfg)


# -------------------------------
# High-level: ladda hela profilen
# -------------------------------
def load_profile(profile_name: str, current_cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Hämtar (inställningar, rader) för vald profil.
    - settings: key/value från profilbladet
    - rows: normaliserade Data-rader för profilen
    """
    cfg_upd = read_profile_settings(profile_name)
    # slå ihop med befintlig cfg (behåll dina defaults om något saknas)
    tmp_cfg = dict(current_cfg)
    tmp_cfg.update(cfg_upd)
    rows = read_profile_rows(profile_name, tmp_cfg)
    return cfg_upd, rows
