# profiler.py
import datetime
from typing import Dict, Any, List
import pandas as pd

import sheets_utils as SU  # använder ensure_ws/get_client

# --- Publika API:t som app.py anropar ---

def get_profiles(ss) -> List[str]:
    """
    Läser fliken 'Profil' och returnerar listan med profilnamn (kolumn A).
    Första raden får gärna vara 'Profil' (hoppar vi över).
    """
    ws = SU.ensure_ws(ss, "Profil", rows=100, cols=2)
    names = [n.strip() for n in ws.col_values(1) if n and n.strip()]
    if names and names[0].lower() in ("profil", "namn", "name"):
        names = names[1:]
    return names or ["Malin"]

def load_profile_cfg(ss, profile_name: str) -> Dict[str, Any]:
    """
    Läser nyckel/värde från bladet med samma namn som profilen.
    Första raden kan vara header 'Key' / 'Value' (hoppar vi över).
    Försöker typa värden (int/float/datum). BONUS_RATE kan anges som 0.01 eller 1–100 (%).
    """
    ws = SU.ensure_ws(ss, profile_name, rows=200, cols=2)
    rows = ws.get_all_values()
    cfg: Dict[str, Any] = {}
    if not rows:
        return cfg

    start_idx = 1 if (rows and rows[0] and rows[0][0].strip().lower() in ("key","nyckel")) else 0
    for r in rows[start_idx:]:
        if len(r) < 2:
            continue
        key = str(r[0]).strip()
        val = str(r[1]).strip()
        if not key:
            continue
        cfg[key] = _parse_value(key, val)
    return cfg

def save_profile_cfg(ss, profile_name: str, cfg: Dict[str, Any]) -> None:
    """
    Skriver hela CFG som Key/Value till profilens blad (rensar först).
    Datum serialiseras som YYYY-MM-DD.
    """
    ws = SU.ensure_ws(ss, profile_name, rows=400, cols=2)
    data = [["Key","Value"]]
    for k, v in cfg.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            v_out = v.strftime("%Y-%m-%d")
        else:
            v_out = str(v)
        data.append([k, v_out])
    ws.clear()
    ws.update("A1", data)

def load_profile_rows(ss, profile_name: str) -> pd.DataFrame:
    """
    Läser fliken 'Data' och filtrerar på kolumnen 'Profil' == profile_name om den finns.
    Returnerar en DataFrame (kan vara tom).
    """
    ws = SU.ensure_ws(ss, "Data")
    try:
        records = ws.get_all_records()
    except Exception:
        records = []
    df = pd.DataFrame(records)
    if "Profil" in df.columns:
        df = df[df["Profil"] == profile_name].copy()
    return df

# --- Hjälpare ---

def _parse_value(key: str, raw: str):
    """Försiktig typning: datum/int/float; BONUS_RATE till fraction (0–1) om nödvändigt."""
    s = raw.strip()

    # Datum
    if key in ("startdatum","fodelsedatum"):
        try:
            y, m, d = (int(x) for x in s.split("-"))
            return datetime.date(y, m, d)
        except Exception:
            return s  # lämna som str om den inte gick att parsa

    # Int
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass

    # Float
    try:
        # tillåt komma
        sval = s.replace(",", ".") if ("," in s and "." not in s) else s
        f = float(sval)
        if key == "BONUS_RATE":
            # tillåt att lagra som procent (1–100) eller fraction (0–1)
            if f > 1.0:
                f = f / 100.0
        return f
    except Exception:
        return s
