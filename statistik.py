# statistik.py
# Basversion 250823 (uppdaterad): korrekt ordning + "antal tillfällen" (summa/max)
from typing import Dict, Any, Optional
import pandas as pd

def _fmt2(x: float) -> str:
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "0.00"

def _safe_sum(df: pd.DataFrame, col: str) -> float:
    if col in df.columns:
        return float(pd.to_numeric(df[col].fillna(0), errors="coerce").sum())
    return 0.0

def _safe_mean(series) -> float:
    try:
        s = pd.to_numeric(series, errors="coerce").dropna()
        return float(s.mean()) if len(s) else 0.0
    except Exception:
        return 0.0

def _secs_to_hm(secs: float) -> str:
    secs = max(0, int(round(secs)))
    h = secs // 3600
    m = (secs % 3600) // 60
    return f"{h}:{m:02d}"

def _secs_to_dh(secs: float) -> str:
    secs = max(0, int(round(secs)))
    d = secs // 86400
    h = (secs % 86400) // 3600
    return f"{d}d {h}h"

def _secs_to_wd(secs: float) -> str:
    secs = max(0, int(round(secs)))
    days = secs // 86400
    w = days // 7
    d = days % 7
    return f"{w}v {d}d"

def compute_stats(rows: pd.DataFrame, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    if rows is None or rows.empty:
        return {"Info": "Inga rader i databasen ännu."}

    cfg = cfg or {}

    # Dynamiska etiketter/inställningar
    LBL_PAPPAN  = cfg.get("LBL_PAPPAN", "Pappans vänner")
    LBL_GRANNAR = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV      = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    LBL_NF      = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    LBL_BEK     = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK     = cfg.get("LBL_ESK", "Eskilstuna killar")

    MAX_PAPPAN  = float(cfg.get("MAX_PAPPAN", 0))
    MAX_GRANNAR = float(cfg.get("MAX_GRANNAR", 0))
    MAX_NV      = float(cfg.get("MAX_NILS_VANNER", 0))
    MAX_NF      = float(cfg.get("MAX_NILS_FAMILJ", 0))
    MAX_BEK     = float(cfg.get("MAX_BEKANTA", 0))
    PROD_STAFF  = float(cfg.get("PROD_STAFF", 0))

    # Kolumner
    col_man       = "Män"
    col_svarta    = "Svarta"
    col_bonus     = "Bonus deltagit"
    col_personal  = "Personal deltagit"
    col_tot_men   = "Totalt Män"
    col_hand_aktiv= "Händer aktiv"

    col_tid_sum   = "Summa tid (sek)"
    col_tidD_sum  = "Summa D (sek)"
    col_tidTP_sum = "Summa TP (sek)"

    col_tid_kille = "Tid per kille (sek)"
    col_hand_kille= "Händer per kille (sek)"
    col_hangel    = "Hångel (sek/kille)"
    col_alskar_s  = "Tid Älskar (sek)"

    # === Topp: GB / Privat GB ===
    gb_mask = pd.to_numeric(rows.get(col_man, 0), errors="coerce").fillna(0) > 0
    antal_gb = int(gb_mask.sum())

    kallsum = (
        pd.to_numeric(rows.get(LBL_PAPPAN, 0), errors="coerce").fillna(0)
      + pd.to_numeric(rows.get(LBL_GRANNAR, 0), errors="coerce").fillna(0)
      + pd.to_numeric(rows.get(LBL_NV, 0), errors="coerce").fillna(0)
      + pd.to_numeric(rows.get(LBL_NF, 0), errors="coerce").fillna(0)
    )
    privat_gb_mask = (pd.to_numeric(rows.get(col_man, 0), errors="coerce").fillna(0) == 0) & (kallsum > 0)
    antal_privat_gb = int(privat_gb_mask.sum())

    stats["Antal GB"] = antal_gb
    stats["Privat GB"] = antal_privat_gb

    # Snitt GB & Privat GB
    tot_men_series = pd.to_numeric(rows.get(col_tot_men, rows.get(col_man, 0)), errors="coerce").fillna(0)
    snitt_gb = float(tot_men_series[gb_mask].sum()) / antal_gb if antal_gb > 0 else 0.0
    snitt_priv_gb = float(tot_men_series[privat_gb_mask].sum()) / antal_privat_gb if antal_privat_gb > 0 else 0.0

    stats["— Snitt —"] = ""
    stats["Snitt GB (Totalt män / GB)"] = _fmt2(snitt_gb)
    stats["Snitt Privat GB (Totalt män / Privat GB)"] = _fmt2(snitt_priv_gb)

    # === Totalt antal män (def) ===
    total_man = (
        _safe_sum(rows, col_man)
      + _safe_sum(rows, col_svarta)
      + _safe_sum(rows, col_bonus)
      + _safe_sum(rows, LBL_ESK)
      + float(PROD_STAFF)
      + _safe_sum(rows, LBL_PAPPAN)
      + _safe_sum(rows, LBL_GRANNAR)
      + _safe_sum(rows, LBL_NV)
      + _safe_sum(rows, LBL_NF)
      + _safe_sum(rows, LBL_BEK)
    )
    stats["Totalt antal män (def)"] = _fmt2(total_man)

    # === Andel svarta (%) + antal ===
    sv_series  = pd.to_numeric(rows.get(col_svarta, 0), errors="coerce").fillna(0)
    esk_series = pd.to_numeric(rows.get(LBL_ESK, 0), errors="coerce").fillna(0)
    bon_series = pd.to_numeric(rows.get(col_bonus, 0), errors="coerce").fillna(0)
    mask_svarta = sv_series > 0
    total_svarta_count = float(sv_series.sum() + esk_series[mask_svarta].sum() + bon_series[mask_svarta].sum())
    stats["Svarta – antal"] = _fmt2(total_svarta_count)
    andel_svarta_pct = (total_svarta_count / total_man * 100.0) if total_man > 0 else 0.0
    stats["Andel svarta (%)"] = _fmt2(andel_svarta_pct)

    # === DP/DPP/DAP/TAP: summor + snitt per scen (Totalt män > 0) ===
    for col in ["DP", "DPP", "DAP", "TAP"]:
        summan = _safe_sum(rows, col)
        stats[f"{col} – summa"] = _fmt2(summan)
        mask = pd.to_numeric(rows.get(col_tot_men, rows.get(col_man, 0)), errors="coerce").fillna(0) > 0
        denom = int(mask.sum())
        snitt = float(pd.to_numeric(rows.get(col, 0), errors="coerce").fillna(0)[mask].sum()) / denom if denom > 0 else 0.0
        stats[f"{col} – snitt per scen"] = _fmt2(snitt)

    # === Älskar / Sover med – summor (enskilt) ===
    stats["Älskar – summa"] = _fmt2(_safe_sum(rows, "Älskar"))
    stats["Sover med – summa"] = _fmt2(_safe_sum(rows, "Sover med"))

    # === Enskilda fält: SUMMA -> SNITT PER SCEN -> ANTAL TILLFÄLLEN (summa/max) ===
    def _snitt_per_scen(colname: str) -> float:
        series = pd.to_numeric(rows.get(colname, 0), errors="coerce").fillna(0)
        mask = series > 0
        denom = int(mask.sum())
        return float(series[mask].sum()) / denom if denom > 0 else 0.0

    def _block_sum_snitt_tillfallen(field_label: str, colname: str, maxval: float):
        s = _safe_sum(rows, colname)
        stats[f"{field_label} – summa"] = _fmt2(s)
        stats[f"{field_label} – snitt per scen"] = _fmt2(_snitt_per_scen(colname))
        # "antal tillfällen" = summa / max
        antal = s / maxval if maxval > 0 else 0.0
        stats[f"{field_label} – antal tillfällen"] = _fmt2(antal)

    _block_sum_snitt_tillfallen("Personal deltagit", col_personal, PROD_STAFF)
    _block_sum_snitt_tillfallen(LBL_PAPPAN, LBL_PAPPAN, MAX_PAPPAN)
    _block_sum_snitt_tillfallen(LBL_GRANNAR, LBL_GRANNAR, MAX_GRANNAR)
    _block_sum_snitt_tillfallen(LBL_NV, LBL_NV, MAX_NV)
    _block_sum_snitt_tillfallen(LBL_NF, LBL_NF, MAX_NF)
    _block_sum_snitt_tillfallen(LBL_BEK, LBL_BEK, MAX_BEK)

    # Summa av MAX-värden (källor)
    stats["Summa MAX (källor)"] = _fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # === Tidsstatistik: Summa tid/D/TP sek -> HM / D:H / V:D ===
    def _time_block(title: str, secs: float):
        stats[f"{title} – timmar:minuter"] = _secs_to_hm(secs)
        stats[f"{title} – dagar:timmar"]   = _secs_to_dh(secs)
        stats[f"{title} – veckor:dagar"]   = _secs_to_wd(secs)

    tot_secs  = _safe_sum(rows, col_tid_sum)
    _time_block("Summa tid (sek)", tot_secs)
    if col_tidD_sum in rows.columns:
        _time_block("Summa D (sek)", _safe_sum(rows, col_tidD_sum))
    if col_tidTP_sum in rows.columns:
        _time_block("Summa TP (sek)", _safe_sum(rows, col_tidTP_sum))

    # === Händer aktiv/inaktiv antal + % ===
    if col_hand_aktiv in rows.columns:
        hand = pd.to_numeric(rows[col_hand_aktiv].fillna(0), errors="coerce")
        n_rows = len(rows)
        aktiva = int((hand == 1).sum())
        inakt  = int((hand == 0).sum())
        stats["Händer aktiva – antal"]   = aktiva
        stats["Händer aktiva – %"]       = _fmt2(aktiva / n_rows * 100.0 if n_rows else 0.0)
        stats["Händer inaktiva – antal"] = inakt
        stats["Händer inaktiva – %"]     = _fmt2(inakt / n_rows * 100.0 if n_rows else 0.0)

    # === Tid per kille snitt – med & utan händer ===
    tid_kille = pd.to_numeric(rows.get(col_tid_kille, 0), errors="coerce").fillna(0)
    hand_kille= pd.to_numeric(rows.get(col_hand_kille, 0), errors="coerce").fillna(0)
    stats["Tid/kille snitt (ex händer)"] = _fmt2(float(tid_kille.mean()) if len(rows) else 0.0)
    stats["Tid/kille snitt (inkl händer)"] = _fmt2(float((tid_kille + hand_kille).mean()) if len(rows) else 0.0)

    # === Genomsnitt hångel tid ===
    if col_hangel in rows.columns:
        stats["Hångel – snitt (sek/kille)"] = _fmt2(_safe_mean(rows[col_hangel]))

    # === Tid älskar: summa + snitt KÄNNER ===
    alskar_sum = _safe_sum(rows, "Älskar")
    stats["Älskar – summa"] = _fmt2(alskar_sum)
    denom_kanner = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    stats["Älskar snitt känner"] = _fmt2(alskar_sum / denom_kanner if denom_kanner > 0 else 0.0)

    # Sover med: summa / MAX_NF
    sover_sum = _safe_sum(rows, "Sover med")
    stats["Sover med – summa / MAX Nils familj"] = _fmt2(sover_sum / MAX_NF if MAX_NF > 0 else 0.0)

    # === Ekonomi (summor) ===
    for col, label in [
        ("Prenumeranter", "Prenumeranter – summa"),
        ("Intäkter", "Intäkter – summa"),
        ("Kostnad män", "Kostnad män – summa"),
        ("Intäkt Känner", "Intäkt Känner – summa"),
        ("Intäkt företag", "Intäkt företag – summa"),
        ("Lön Malin", "Lön Malin – summa"),
        ("Vinst", "Vinst – summa"),
    ]:
        stats[label] = _fmt2(_safe_sum(rows, col))

    # === Snitt på Lön Malin ===
    lon_sum = _safe_sum(rows, "Lön Malin")
    total_men_all = float(tot_men_series.sum())
    stats["Lön Malin / Per scen"] = _fmt2(lon_sum / antal_gb if antal_gb > 0 else 0.0)
    stats["Lön Malin / Totalt män"] = _fmt2(lon_sum / total_men_all if total_men_all > 0 else 0.0)

    return stats
