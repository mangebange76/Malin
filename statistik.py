# statistik.py
from __future__ import annotations
import re
import math
import pandas as pd

WS_STRIP_RE = re.compile(r"[\u00A0\u2007\u202F\u200B\u200C\u200D]")  # NBSP, figure, narrow, zero-widths
MULTI_SPACE_RE = re.compile(r"\s+")

def _clean_colname(s: str) -> str:
    s = str(s)
    s = WS_STRIP_RE.sub(" ", s)          # ersätt “special”-mellanrum med vanlig space
    s = MULTI_SPACE_RE.sub(" ", s).strip()
    return s

NUM_KEEP_RE = re.compile(r"[^0-9,.\-()]")  # behåll bara siffror, , . - ( )

def _parse_float(val) -> float:
    """
    Robust parsning av tal från strängar:
    - tar bort valutasymboler/bokstäver
    - hanterar tusentalsavgränsare och både punkt/komma som decimaltecken
    - stödjer parentes för negativa tal
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0.0
    if isinstance(val, (int, float)):
        try:
            return float(val)
        except Exception:
            return 0.0

    s = str(val).strip()
    if not s:
        return 0.0

    # Negativt med parentes
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]

    # Ta bort allt utom siffror och skiljetecken
    s = NUM_KEEP_RE.sub("", s)
    s = s.replace(" ", "").replace("\u00A0", "")  # säkra ännu en gång

    if not s:
        return 0.0

    # Om både komma och punkt finns: välj den SISTA som decimal, rensa andra
    if "," in s and "." in s:
        last_comma = s.rfind(",")
        last_dot   = s.rfind(".")
        if last_dot > last_comma:
            # punkt som decimal -> ta bort alla komman
            s = s.replace(",", "")
        else:
            # komma som decimal -> ta bort alla punkter
            s = s.replace(".", "")
            s = s.replace(",", ".")
    elif "," in s and "." not in s:
        # bara komma -> decimal
        s = s.replace(",", ".")
    # annars: bara punkt -> redan decimal

    try:
        out = float(s)
    except Exception:
        out = 0.0
    return -out if neg else out

def _to_float_series(s: pd.Series) -> pd.Series:
    return s.apply(_parse_float).astype("float64")

def _fmt2(x: float) -> str:
    try:
        return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"

def _fmt_pct(p: float) -> str:
    return f"{_fmt2(p)} %"

def compute_stats(df: pd.DataFrame, cfg: dict | None = None) -> dict:
    stats: dict[str,str] = {}
    if df is None or df.empty:
        return stats

    # ---------- 1) Städa kolumnnamn och duplicera inte ----------
    clean_map = {}
    used = set()
    for c in df.columns:
        cc = _clean_colname(c)
        if cc in used:
            # om renat namn skulle krocka, behåll originalnamn
            cc = str(c)
        used.add(cc)
        clean_map[c] = cc
    df = df.rename(columns=clean_map)
    cols = set(df.columns)

    # ---------- 2) Hämta labels & max från cfg ----------
    cfg = cfg or {}
    LBL_PAPPAN  = cfg.get("LBL_PAPPAN",  "Pappans vänner")
    LBL_GRANNAR = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV      = cfg.get("LBL_NILS_VANNER",  "Nils vänner")
    LBL_NF      = cfg.get("LBL_NILS_FAMILJ",  "Nils familj")
    LBL_BEK     = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK     = cfg.get("LBL_ESK",     "Eskilstuna killar")

    MAX_PAPPAN  = _parse_float(cfg.get("MAX_PAPPAN", 0))
    MAX_GRANNAR = _parse_float(cfg.get("MAX_GRANNAR", 0))
    MAX_NV      = _parse_float(cfg.get("MAX_NILS_VANNER", 0))
    MAX_NF      = _parse_float(cfg.get("MAX_NILS_FAMILJ", 0))
    MAX_BEK     = _parse_float(cfg.get("MAX_BEKANTA", 0))
    PROD_STAFF  = _parse_float(cfg.get("PROD_STAFF", 0))

    # ---------- 3) Hjälpare ----------
    def s_col(name: str) -> pd.Series:
        if name not in cols:
            return pd.Series([0.0]*len(df), dtype="float64")
        return _to_float_series(df[name])

    def sum_exact(name: str) -> float:
        return float(s_col(name).sum()) if name in cols else 0.0

    def exist(name: str) -> bool:
        return name in cols

    # Händer aktiv robust
    def hander_aktiv_series() -> pd.Series:
        nm = None
        for cand in ["Händer aktiv", "Hander aktiv"]:
            if cand in cols:
                nm = cand; break
        if nm is None:
            return pd.Series([0.0]*len(df), dtype="float64")

        raw = df[nm].fillna("")
        out = []
        for v in raw:
            if isinstance(v, (int, float)):
                out.append(1.0 if _parse_float(v) >= 1 else 0.0)
            else:
                vs = str(v).strip().lower()
                if vs in ("1","ja","true","t","y","yes"):
                    out.append(1.0)
                elif vs in ("0","nej","false","f","n","no",""):
                    out.append(0.0)
                else:
                    out.append(1.0 if _parse_float(v) >= 1 else 0.0)
        return pd.Series(out, dtype="float64")

    # mm:ss fallback
    MMSS_RE = re.compile(r"^\s*(\d+)\s*:\s*([0-5]?\d)\s*$")
    def mmss_to_sec_series(name: str) -> pd.Series:
        if name not in cols:
            return pd.Series([0.0]*len(df), dtype="float64")
        raw = df[name].fillna("")
        out = []
        for v in raw:
            if isinstance(v, (int, float)):
                out.append(float(v))
                continue
            m = MMSS_RE.match(str(v))
            if m:
                mm = int(m.group(1)); ss = int(m.group(2)); out.append(float(mm*60+ss))
            else:
                out.append(_parse_float(v))  # om någon redan skrivit sekunder
        return pd.Series(out, dtype="float64")

    # Totalt män per rad (egen beräkning – robust mot saknade kolumner)
    def totalt_man_per_rad() -> pd.Series:
        parts = [
            s_col("Män"), s_col("Svarta"), s_col(LBL_PAPPAN), s_col(LBL_GRANNAR),
            s_col(LBL_NV), s_col(LBL_NF), s_col(LBL_BEK), s_col(LBL_ESK),
            s_col("Bonus deltagit"), s_col("Personal deltagit")
        ]
        s = parts[0].copy()
        for p in parts[1:]:
            s = s.add(p, fill_value=0.0)
        return s

    # ---------- 4) GB/Privat GB (överst) ----------
    man = s_col("Män")
    antal_gb = int((man > 0).sum())

    privat_mask = (man == 0) & (
        (s_col(LBL_PAPPAN) > 0) |
        (s_col(LBL_GRANNAR) > 0) |
        (s_col(LBL_NV) > 0) |
        (s_col(LBL_NF) > 0)
    )
    antal_privat_gb = int(privat_mask.sum())

    stats["Antal GB"] = _fmt2(antal_gb)
    stats["Privat GB"] = _fmt2(antal_privat_gb)

    # ---------- 5) TOTALER ----------
    stats["— TOTALER —"] = ""

    total_man_stat = (
        sum_exact("Män")
        + sum_exact("Svarta")
        + sum_exact("Bonus deltagit")
        + sum_exact(LBL_ESK)
        + MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK + PROD_STAFF
    )
    stats["Totalt antal män (statistik)"] = _fmt2(total_man_stat)

    svarta = s_col("Svarta")
    svart_mask = (svarta > 0)
    andel_svarta_numer = float(
        svarta[svart_mask].sum()
        + s_col(LBL_ESK)[svart_mask].sum()
        + s_col("Bonus deltagit")[svart_mask].sum()
    )
    stats["Svarta (antal för andel)"] = _fmt2(andel_svarta_numer)
    stats["Andel svarta"] = _fmt_pct((andel_svarta_numer / total_man_stat * 100.0) if total_man_stat > 0 else 0.0)

    # DP/DPP/DAP/TAP (summa + snitt per scen där Totalt män > 0)
    tot_man_rad = totalt_man_per_rad()
    n_scen_totman = int((tot_man_rad > 0).sum())

    for etikett in ["DP", "DPP", "DAP", "TAP"]:
        s = sum_exact(etikett)
        stats[f"{etikett} (summa)"] = _fmt2(s)
        stats[f"{etikett} – snitt per scen"] = ""
        stats[f"{etikett} snitt per scen"] = _fmt2(s / (n_scen_totman if n_scen_totman > 0 else 1))

    # Älskar / Sover med (summa)
    stats["Älskar (summa)"]    = _fmt2(sum_exact("Älskar"))
    stats["Sover med (summa)"] = _fmt2(sum_exact("Sover med"))

    # Enskilda kolumner (summa + snitt per scen där kolumn > 0)
    def add_sum_and_avg(col_name: str):
        s = sum_exact(col_name)
        n_pos = int((s_col(col_name) > 0).sum()) if exist(col_name) else 0
        stats[f"{col_name} (summa)"] = _fmt2(s)
        stats[f"{col_name} – snitt per scen"] = ""
        stats[f"{col_name} snitt per scen"] = _fmt2(s / (n_pos if n_pos > 0 else 1))

    for nm in ["Bonus deltagit","Personal deltagit", LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        add_sum_and_avg(nm)

    # Summa maxvärden (Känner)
    stats["Summa maxvärden (Känner)"] = _fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ---------- 6) TID ----------
    stats["— TID —"] = ""

    def alias_sum_seconds(cands: list[str]) -> float:
        for nm in cands:
            if nm in cols:
                return float(s_col(nm).sum())
        return 0.0

    # Summa tid (sek) (alias) + presentation (h/d/veckor)
    AL_SUM_TID = ["Summa tid (sek)","Summa tid sek","Summa tid"]
    AL_SUM_D   = ["Summa D (sek)","Summa D sek","Summa D"]
    AL_SUM_TP  = ["Summa TP (sek)","Summa TP sek","Summa TP"]

    def time_block(prefix: str, seconds: float):
        hours = seconds / 3600.0
        days  = seconds / 86400.0
        weeks = seconds / (7*86400.0)
        stats[f"{prefix} – timmar"] = _fmt2(hours)
        stats[f"{prefix} – dagar"]  = _fmt2(days)
        stats[f"{prefix} – veckor"] = _fmt2(weeks)

    sum_tid_sec = alias_sum_seconds(AL_SUM_TID)
    time_block("Summa tid", sum_tid_sec)

    sum_d_sec  = alias_sum_seconds(AL_SUM_D)
    sum_tp_sec = alias_sum_seconds(AL_SUM_TP)
    time_block("Summa D",  sum_d_sec)
    time_block("Summa TP", sum_tp_sec)

    # ---------- 7) HÄNDER ----------
    stats["— HÄNDER —"] = ""
    total_rows = int(len(df))
    h_aktiv = hander_aktiv_series()
    aktiva = int((h_aktiv == 1).sum()) if len(h_aktiv) else 0
    inaktiva = max(0, total_rows - aktiva)
    p_aktiva = (aktiva / total_rows * 100.0) if total_rows > 0 else 0.0
    p_inaktiva = (inaktiva / total_rows * 100.0) if total_rows > 0 else 0.0
    stats["Händer aktiva (antal)"]   = _fmt2(aktiva)
    stats["Händer aktiva (%)"]       = _fmt_pct(p_aktiva)
    stats["Händer inaktiva (antal)"] = _fmt2(inaktiva)
    stats["Händer inaktiva (%)"]     = _fmt_pct(p_inaktiva)

    # ---------- 8) EKONOMI ----------
    stats["— EKONOMI —"] = ""
    # Summa
    stats["Prenumeranter (summa)"]   = _fmt2(sum_exact("Prenumeranter"))
    stats["Intäkter (summa)"]        = _fmt2(sum_exact("Intäkter"))
    stats["Kostnad män (summa)"]     = _fmt2(sum_exact("Kostnad män"))
    stats["Intäkt Känner (summa)"]   = _fmt2(sum_exact("Intäkt Känner"))
    stats["Intäkt företag (summa)"]  = _fmt2(sum_exact("Intäkt företag"))
    stats["Lön Malin (summa)"]       = _fmt2(sum_exact("Lön Malin"))
    stats["Vinst (summa)"]           = _fmt2(sum_exact("Vinst"))

    # Snitt Lön Malin per scen / per totalt män
    lon_tot = sum_exact("Lön Malin")
    stats["Lön Malin / Per scen"]   = _fmt2(lon_tot / (antal_gb if antal_gb > 0 else 1))
    stats["Lön Malin / Totalt män"] = _fmt2(lon_tot / (total_man_stat if total_man_stat > 0 else 1))

    # ---------- 9) SNITT ----------
    stats["— SNITT —"] = ""

    # Snitt GB / Snitt Privat GB (Totalt män / antal)
    totman_rad = totalt_man_per_rad()
    sum_totman_gb     = float(totman_rad[man > 0].sum()) if len(totman_rad) else 0.0
    sum_totman_privat = float(totman_rad[privat_mask].sum()) if len(totman_rad) else 0.0
    stats["Snitt GB (Totalt män / Antal GB)"]               = _fmt2(sum_totman_gb / (antal_gb if antal_gb > 0 else 1))
    stats["Snitt Privat GB (Totalt män / Antal Privat GB)"] = _fmt2(sum_totman_privat / (antal_privat_gb if antal_privat_gb > 0 else 1))

    # Snitt tid GB/Privat GB (h)
    sum_tid_series = None
    for nm in AL_SUM_TID:
        if exist(nm):
            sum_tid_series = s_col(nm); break
    if sum_tid_series is None:
        sum_tid_series = pd.Series([0.0]*len(df), dtype="float64")

    stats["Snitt tid GB (h)"]        = _fmt2((float(sum_tid_series[man > 0].sum())      / 3600.0) / (antal_gb if antal_gb > 0 else 1))
    stats["Snitt tid Privat GB (h)"] = _fmt2((float(sum_tid_series[privat_mask].sum()) / 3600.0) / (antal_privat_gb if antal_privat_gb > 0 else 1))

    # Tid/kille snitt inkl/ex händer (min)
    # a) tpk (sek)
    if "Tid per kille (sek)" in cols:
        tpk_sec = s_col("Tid per kille (sek)")
    elif "Tid/kille (sek)" in cols:
        tpk_sec = s_col("Tid/kille (sek)")
    elif "Tid per kille" in cols:
        tpk_sec = mmss_to_sec_series("Tid per kille")
    else:
        tpk_sec = pd.Series([0.0]*len(df), dtype="float64")

    # b) händer per kille (sek)
    if "Händer per kille (sek)" in cols:
        hpk_sec = s_col("Händer per kille (sek)")
    elif "Hander per kille (sek)" in cols:
        hpk_sec = s_col("Hander per kille (sek)")
    else:
        hpk_sec = pd.Series([0.0]*len(df), dtype="float64")

    h_act = hander_aktiv_series()
    extra = hpk_sec.where(h_act == 1, other=0.0)

    snitt_tid_ex = float(tpk_sec.mean()) / 60.0 if len(tpk_sec) else 0.0
    snitt_tid_in = float((tpk_sec + extra).mean()) / 60.0 if len(tpk_sec) else 0.0
    stats["Tid/kille snitt ex händer (min)"]   = _fmt2(snitt_tid_ex)
    stats["Tid/kille snitt inkl händer (min)"] = _fmt2(snitt_tid_in)

    # Hångel snitt (min)
    if "Hångel (sek/kille)" in cols:
        hangel_sec = s_col("Hångel (sek/kille)")
    else:
        hangel_sec = pd.Series([0.0]*len(df), dtype="float64")
    stats["Hångel snitt (min)"] = _fmt2(float(hangel_sec.mean() / 60.0) if len(hangel_sec) else 0.0)

    # Älskar snitt Känner
    kanner_max_sum = (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)
    stats["Älskar snitt Känner"] = _fmt2(sum_exact("Älskar") / (kanner_max_sum if kanner_max_sum > 0 else 1))

    # Sover med snitt Nils familj
    stats["Sover med snitt Nils familj"] = _fmt2(sum_exact("Sover med") / (MAX_NF if MAX_NF > 0 else 1))

    return stats
