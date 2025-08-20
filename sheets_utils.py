# sheets_utils.py
import json
import pandas as pd
import streamlit as st

def get_client():
    """Skapa gspread-klient från st.secrets (tål str/dict/AttrDict)."""
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar GOOGLE_CREDENTIALS eller SHEET_URL i secrets.")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))

    from google.oauth2.service_account import Credentials
    import gspread
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return ss

def ensure_ws(ss, title, rows=4000, cols=80):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

# ---------- Profilhantering ----------

def list_profiles():
    try:
        ss = get_client()
        ws = ensure_ws(ss, "Profil")
        vals = ws.col_values(1)
        names = [v.strip() for v in vals if v and v.strip()]
        if names and names[0].lower() in ("namn","name","profil","profiles"):
            names = names[1:]
        return names
    except Exception as e:
        st.error(f"Kunde inte läsa profil-lista: {e}")
        return []

def load_profile_cfg(profile_name: str) -> dict:
    """Läs in key/value från blad med samma namn som profilen."""
    out = {}
    if not profile_name:
        return out
    try:
        ss = get_client()
        ws = ensure_ws(ss, profile_name)
        rows = ws.get_all_values()
        for row in rows:
            if len(row) < 2 or not row[0]:
                continue
            key = row[0].strip()
            val = row[1]
            # datum
            if key in ("startdatum","fodelsedatum"):
                out[key] = val
                continue
            # försök typa
            try:
                out[key] = float(val) if "." in val else int(val)
            except:
                out[key] = val
    except Exception as e:
        st.error(f"Kunde inte läsa profil-inställningar ({profile_name}): {e}")
    return out

def load_profile_rows(profile_name: str, cfg_labels: dict) -> pd.DataFrame:
    """
    Läs rader för profilen från:
    - fliken 'Data' filtrerat på kolumn 'Profil'
    - annars dedikerade blad: 'Data_<profil>' / '<profil>_Data' / '<profil> Data'
    Försöker typa numeriska kolumner.
    """
    try:
        ss = get_client()
        # Försök gemensam Data
        try:
            recs = ensure_ws(ss, "Data").get_all_records()
            df = pd.DataFrame(recs)
            if not df.empty and "Profil" in df.columns:
                df = df[df["Profil"] == profile_name].copy()
        except Exception:
            df = pd.DataFrame()

        # Fallbacks
        if df.empty:
            for cand in (f"Data_{profile_name}", f"{profile_name}_Data", f"{profile_name} Data"):
                try:
                    recs = ensure_ws(ss, cand).get_all_records()
                    tmp = pd.DataFrame(recs)
                    if not tmp.empty:
                        df = tmp
                        break
                except Exception:
                    continue

        if df.empty:
            return df  # tomt

        # typa numeriskt där det går
        numeric_cols = [
            "Scen","Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
            cfg_labels.get("LBL_PAPPAN","Pappans vänner"),
            cfg_labels.get("LBL_GRANNAR","Grannar"),
            cfg_labels.get("LBL_NILS_VANNER","Nils vänner"),
            cfg_labels.get("LBL_NILS_FAMILJ","Nils familj"),
            cfg_labels.get("LBL_BEKANTA","Bekanta"),
            cfg_labels.get("LBL_ESK","Eskilstuna killar"),
            "Bonus deltagit","Personal deltagit",
            "Känner","Känner sammanlagt","Totalt Män",
            "Prenumeranter","Hårdhet",
            "Suger","Suger per kille (sek)","Händer per kille (sek)","Tid/kille inkl händer (sek)",
            "Summa S (sek)","Summa D (sek)","Summa TP (sek)","Summa tid (sek)",
            "Intäkter","Intäkt Känner","Intäkt företag","Kostnad män","Lön Malin","Vinst",
            "Händer aktiv"
        ]
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        return df
    except Exception as e:
        st.error(f"Kunde inte läsa profilens data ({profile_name}): {e}")
        return pd.DataFrame()

# ---------- Spara ----------

def save_settings(cfg: dict):
    """Skriv hela CFG till fliken 'Inställningar' (Key/Value)."""
    ss = get_client()
    ws = ensure_ws(ss, "Inställningar")
    rows = []
    for k, v in cfg.items():
        if hasattr(v, "isoformat"):
            rows.append([k, v.isoformat()])
        else:
            rows.append([k, str(v)])
    ws.clear()
    ws.update("A1", [["Key","Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def append_row_to_data(row: dict):
    """Append en rad till fliken 'Data'. Skapar header om saknas."""
    ss = get_client()
    ws = ensure_ws(ss, "Data")
    header = ws.row_values(1)
    if not header:
        header = list(row.keys())
        ws.update("A1", [header])
    values = [row.get(col, "") for col in header]
    ws.append_row(values)
