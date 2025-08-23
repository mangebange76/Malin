# statistik.py
# Basversion 250823 + "summa / maxvärde" under snitt per scen för Personal/Pappan/Grannar/Nils vänner/Nils familj/Bekanta

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
    """
    Returnerar en ordnad dict med statistik, färdig att visas.
    Alla presentationer har 2 decimaler där det är rimligt.
    """
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

    # Säkra kolumnnamn
    col_man       = "Män"
    col_svarta    = "Svarta"
    col_bonus     = "Bonus deltagit"
    col_personal  = "Personal deltagit"
    col_tot_men   = "Totalt Män"
    col_hand_aktiv= "Händer aktiv"

    col_tid_sum   = "Summa tid (sek)"
    col_tidD_sum  = "Summa D (sek)"      # om finns
    col_tidTP_sum = "Summa TP (sek)"     # om finns

    col_tid_kille = "Tid per kille (sek)"
    col_hand_kille= "Händer per kille (sek)"
    col_hangel    = "Hångel (sek/kille)"
    col_alskar_s  = "Tid Älskar (sek)"

    # === Topp: GB / Privat GB ===
    # Antal GB = rader där Män > 0
    gb_mask = pd.to_numeric(rows.get(col_man, 0), errors="coerce").fillna(0) > 0
    antal_gb = int(gb_mask.sum())

    # Privat GB = Män == 0 och minst en av källorna >0
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

    stats["— Snitt —"] = ""  # avdelare
    stats["Snitt GB (Totalt män / GB)"] = _fmt2(snitt_gb)
    stats["Snitt Privat GB (Totalt män / Privat GB)"] = _fmt2(snitt_priv_gb)

    # === Totalt antal män (enligt din definition) ===
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

    # === Andel svarta ===
    # Rader med svarta > 0: på dessa räknas även ESK + BONUS som svarta
    sv_series  = pd.to_numeric(rows.get(col_svarta, 0), errors="coerce").fillna(0)
    esk_series = pd.to_numeric(rows.get(LBL_ESK, 0), errors="coerce").fillna(0)
    bon_series = pd.to_numeric(rows.get(col_bonus, 0), errors="coerce").fillna(0)
    man_series = pd.to_numeric(rows.get(col_man, 0), errors="coerce").fillna(0)

    mask_svarta = sv_series > 0
    total_svarta_count = float(sv_series.sum() + esk_series[mask_svarta].sum() + bon_series[mask_svarta].sum())
    stats["Svarta – antal"] = _fmt2(total_svarta_count)
    andel_svarta_pct = (total_svarta_count / total_man * 100.0) if total_man > 0 else 0.0
    stats["Andel svarta (%)"] = _fmt2(andel_svarta_pct)

    # === DP/DPP/DAP/TAP: summor + snitt per scen (på rader med Totalt män > 0) ===
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

    # === Enskilda fält-summor ===
    stats["Bonus deltagit – summa"]   = _fmt2(_safe_sum(rows, col_bonus))
    stats["Personal deltagit – summa"] = _fmt2(_safe_sum(rows, col_personal))
    stats[f"{LBL_PAPPAN} – summa"]    = _fmt2(_safe_sum(rows, LBL_PAPPAN))
    stats[f"{LBL_GRANNAR} – summa"]   = _fmt2(_safe_sum(rows, LBL_GRANNAR))
    stats[f"{LBL_NV} – summa"]        = _fmt2(_safe_sum(rows, LBL_NV))
    stats[f"{LBL_NF} – summa"]        = _fmt2(_safe_sum(rows, LBL_NF))
    stats[f"{LBL_BEK} – summa"]       = _fmt2(_safe_sum(rows, LBL_BEK))
    stats[f"{LBL_ESK} – summa"]       = _fmt2(_safe_sum(rows, LBL_ESK))

    # === Snitt per scen för de enskilda fälten (summa / rader där fältet > 0) ===
    def _snitt_per_scen(colname: str) -> float:
        series = pd.to_numeric(rows.get(colname, 0), errors="coerce").fillna(0)
        mask = series > 0
        denom = int(mask.sum())
        return float(series[mask].sum()) / denom if denom > 0 else 0.0

    stats["Bonus deltagit – snitt per scen"]   = _fmt2(_snitt_per_scen(col_bonus))
    stats["Personal deltagit – snitt per scen"] = _fmt2(_snitt_per_scen(col_personal))
    stats[f"{LBL_PAPPAN} – snitt per scen"]    = _fmt2(_snitt_per_scen(LBL_PAPPAN))
    stats[f"{LBL_GRANNAR} – snitt per scen"]   = _fmt2(_snitt_per_scen(LBL_GRANNAR))
    stats[f"{LBL_NV} – snitt per scen"]        = _fmt2(_snitt_per_scen(LBL_NV))
    stats[f"{LBL_NF} – snitt per scen"]        = _fmt2(_snitt_per_scen(LBL_NF))
    stats[f"{LBL_BEK} – snitt per scen"]       = _fmt2(_snitt_per_scen(LBL_BEK))
    stats[f"{LBL_ESK} – snitt per scen"]       = _fmt2(_snitt_per_scen(LBL_ESK))

    # === NYTT: "summa / maxvärde från inställningar" direkt under snitt per scen ===
    def _sum_div_max(colname: str, maxval: float) -> str:
        s = _safe_sum(rows, colname)
        return _fmt2(s / maxval) if maxval > 0 else "0.00"

    # Personal deltagit / PROD_STAFF
    stats["Personal deltagit – summa / max (PROD_STAFF)"] = _sum_div_max(col_personal, PROD_STAFF)
    # Pappan/Grannar/Nils vänner/Nils familj/Bekanta mot respektive MAX_*
    stats[f"{LBL_PAPPAN} – summa / max"]  = _sum_div_max(LBL_PAPPAN, MAX_PAPPAN)
    stats[f"{LBL_GRANNAR} – summa / max"] = _sum_div_max(LBL_GRANNAR, MAX_GRANNAR)
    stats[f"{LBL_NV} – summa / max"]      = _sum_div_max(LBL_NV, MAX_NV)
    stats[f"{LBL_NF} – summa / max"]      = _sum_div_max(LBL_NF, MAX_NF)
    stats[f"{LBL_BEK} – summa / max"]     = _sum_div_max(LBL_BEK, MAX_BEK)

    # === Summa av MAX-värden (placeras under enskilda presentationer) ===
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

    # === Tid älskar: summa + snitt KÄNNER (sum Älskar / (MAX_PAPPAN+MAX_GRANNAR+MAX_NV+MAX_NF)) ===
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
