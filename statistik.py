# statistik.py
import math
import pandas as pd

def compute_stats(df: pd.DataFrame, cfg: dict | None = None) -> dict:
    """
    Returnerar en ordnad dict med alla statistikrader.
    Allt formateras med två decimaler och svensk decimal-komma.
    Säker mot saknade kolumner.
    """

    stats: dict[str, str] = {}

    # ===== Hjälpare =====
    cfg = cfg or {}
    LBL_PAPPAN  = cfg.get("LBL_PAPPAN",  "Pappans vänner")
    LBL_GRANNAR = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV      = cfg.get("LBL_NILS_VANNER",  "Nils vänner")
    LBL_NF      = cfg.get("LBL_NILS_FAMILJ",  "Nils familj")
    LBL_BEK     = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK     = cfg.get("LBL_ESK",     "Eskilstuna killar")

    MAX_PAPPAN  = float(cfg.get("MAX_PAPPAN", 0))
    MAX_GRANNAR = float(cfg.get("MAX_GRANNAR", 0))
    MAX_NV      = float(cfg.get("MAX_NILS_VANNER", 0))
    MAX_NF      = float(cfg.get("MAX_NILS_FAMILJ", 0))
    MAX_BEK     = float(cfg.get("MAX_BEKANTA", 0))
    PROD_STAFF  = float(cfg.get("PROD_STAFF", 0))

    def num(col: str) -> pd.Series:
        if df is None or df.empty or col not in df.columns:
            return pd.Series([], dtype="float64")
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    def fmt2(x: float) -> str:
        # två decimaler med svensk decimal-komma
        try:
            return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00"

    def fmt_pct(p: float) -> str:
        return f"{fmt2(p)} %"

    def safe_sum(col: str) -> float:
        return float(num(col).sum())

    # Per-rad “Totalt män” (radnivå = Män+Svarta+källor+Bekanta+Esk+Bonus+Personal)
    def totalt_man_per_rad_series() -> pd.Series:
        cols = [
            "Män", "Svarta", LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK,
            LBL_ESK, "Bonus deltagit", "Personal deltagit"
        ]
        parts = [num(c) for c in cols]
        if not parts:
            return pd.Series([], dtype="float64")
        s = parts[0]
        for p in parts[1:]:
            s = s.add(p, fill_value=0.0)
        return s

    # Global “Totalt antal män (statistik)” enligt din definition
    def totalt_man_stat() -> float:
        return (
            safe_sum("Män") + safe_sum("Svarta") + safe_sum("Bonus deltagit") + safe_sum(LBL_ESK)
            + MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK + PROD_STAFF
        )

    # ===== Högst upp: GB =====
    man_col = num("Män")
    antal_gb = int((man_col > 0).sum())

    # Privat GB: Män == 0 och minst en av Pappan/Grannar/Nils vänner/Nils familj >0
    privat_mask = (
        (man_col == 0) &
        (
            (num(LBL_PAPPAN) > 0) |
            (num(LBL_GRANNAR) > 0) |
            (num(LBL_NV) > 0) |
            (num(LBL_NF) > 0)
        )
    )
    antal_privat_gb = int(privat_mask.sum())

    stats["Antal GB"] = fmt2(antal_gb)
    stats["Privat GB"] = fmt2(antal_privat_gb)

    # ===== — TOTALER — =====
    stats["— TOTALER —"] = ""

    # Totalt antal män (statistik)
    total_man_stat = totalt_man_stat()
    stats["Totalt antal män (statistik)"] = fmt2(total_man_stat)

    # Andel svarta %
    # numerator: sum över rader med Svarta>0 av (Svarta + Eskilstuna + Bonus deltagit)
    svarta = num("Svarta")
    svart_mask = (svarta > 0)
    andel_svarta_numerator = float(
        (svarta[svart_mask]).sum()
        + (num(LBL_ESK)[svart_mask]).sum()
        + (num("Bonus deltagit")[svart_mask]).sum()
    )
    andel_svarta = (andel_svarta_numerator / total_man_stat * 100.0) if total_man_stat > 0 else 0.0
    stats["Andel svarta"] = fmt_pct(andel_svarta)

    # DP/DPP/DAP/TAP (summa kolumn)
    stats["DP (summa)"]  = fmt2(safe_sum("DP"))
    stats["DPP (summa)"] = fmt2(safe_sum("DPP"))
    stats["DAP (summa)"] = fmt2(safe_sum("DAP"))
    stats["TAP (summa)"] = fmt2(safe_sum("TAP"))

    # Älskar / Sover med (summa)
    stats["Älskar (summa)"]    = fmt2(safe_sum("Älskar"))
    stats["Sover med (summa)"] = fmt2(safe_sum("Sover med"))

    # Enskilda kolumner (summa)
    stats["Bonus deltagit (summa)"]    = fmt2(safe_sum("Bonus deltagit"))
    stats["Personal deltagit (summa)"] = fmt2(safe_sum("Personal deltagit"))
    stats[f"{LBL_PAPPAN} (summa)"]     = fmt2(safe_sum(LBL_PAPPAN))
    stats[f"{LBL_GRANNAR} (summa)"]    = fmt2(safe_sum(LBL_GRANNAR))
    stats[f"{LBL_NV} (summa)"]         = fmt2(safe_sum(LBL_NV))
    stats[f"{LBL_NF} (summa)"]         = fmt2(safe_sum(LBL_NF))
    stats[f"{LBL_BEK} (summa)"]        = fmt2(safe_sum(LBL_BEK))
    stats[f"{LBL_ESK} (summa)"]        = fmt2(safe_sum(LBL_ESK))

    # Summa maxvärden (Känner)
    summa_max_kanner = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    stats["Summa maxvärden (Känner)"] = fmt2(summa_max_kanner)

    # ===== — TID — =====
    stats["— TID —"] = ""

    def time_block(prefix: str, sec_total: float):
        # presenterar som timmar, dagar, veckor (alla med två decimaler)
        hours = sec_total / 3600.0
        days  = sec_total / 86400.0
        weeks = sec_total / (7 * 86400.0)
        stats[f"{prefix} – timmar"] = fmt2(hours)
        stats[f"{prefix} – dagar"]  = fmt2(days)
        stats[f"{prefix} – veckor"] = fmt2(weeks)

    sum_tid_sec = float(num("Summa tid (sek)").sum())
    time_block("Summa tid", sum_tid_sec)

    # Summa D (sek) & Summa TP (sek) – tål att saknas
    sum_d_sec  = float(num("Summa D (sek)").sum() if "Summa D (sek)" in df.columns else num("Summa D").sum())
    sum_tp_sec = float(num("Summa TP (sek)").sum() if "Summa TP (sek)" in df.columns else num("Summa TP").sum())
    time_block("Summa D",  sum_d_sec)
    time_block("Summa TP", sum_tp_sec)

    # ===== — HÄNDER — =====
    stats["— HÄNDER —"] = ""
    total_rows = int(len(df)) if df is not None else 0
    hander = num("Händer aktiv")
    aktiva = int((hander == 1).sum())
    inaktiva = int((hander != 1).sum()) if total_rows > 0 else 0
    p_aktiva = (aktiva / total_rows * 100.0) if total_rows > 0 else 0.0
    p_inaktiva = (inaktiva / total_rows * 100.0) if total_rows > 0 else 0.0
    stats["Händer aktiva (antal)"]   = fmt2(aktiva)
    stats["Händer aktiva (%)"]       = fmt_pct(p_aktiva)
    stats["Händer inaktiva (antal)"] = fmt2(inaktiva)
    stats["Händer inaktiva (%)"]     = fmt_pct(p_inaktiva)

    # ===== — EKONOMI — =====
    stats["— EKONOMI —"] = ""
    stats["Prenumeranter (summa)"]   = fmt2(safe_sum("Prenumeranter"))
    stats["Intäkter (summa)"]        = fmt2(safe_sum("Intäkter"))
    stats["Kostnad män (summa)"]     = fmt2(safe_sum("Kostnad män"))
    stats["Intäkt Känner (summa)"]   = fmt2(safe_sum("Intäkt Känner"))
    stats["Intäkt företag (summa)"]  = fmt2(safe_sum("Intäkt företag"))
    stats["Lön Malin (summa)"]       = fmt2(safe_sum("Lön Malin"))
    stats["Vinst (summa)"]           = fmt2(safe_sum("Vinst"))

    # ===== SNITT: Lön Malin — direkt under EKONOMI =====
    lon_tot = safe_sum("Lön Malin")
    # Totalt män (stat) redan beräknad som total_man_stat
    # Totalt antal tillfällen (enligt din formel)
    totalt_tillfallen = (
        safe_sum("Män") + safe_sum("Svarta") + safe_sum("Älskar") + safe_sum("Sover med")
        + safe_sum("Bonus deltagit") + safe_sum("Personal deltagit")
        + safe_sum(LBL_PAPPAN) + safe_sum(LBL_GRANNAR) + safe_sum(LBL_NV) + safe_sum(LBL_NF)
        + safe_sum(LBL_BEK) + safe_sum(LBL_ESK)
    )
    stats["Lön Malin / Antal GB"]                = fmt2(lon_tot / (antal_gb if antal_gb > 0 else 1))
    stats["Lön Malin / Totalt män"]              = fmt2(lon_tot / (total_man_stat if total_man_stat > 0 else 1))
    stats["Lön Malin / Totalt antal tillfällen"] = fmt2(lon_tot / (totalt_tillfallen if totalt_tillfallen > 0 else 1))

    # ===== — SNITT — (alla övriga snitt) =====
    stats["— SNITT —"] = ""

    # Snitt GB = (sum Totalt män på rader med Män>0) / Antal GB
    total_man_per_row = totalt_man_per_rad_series()
    sum_gb_totman = float(total_man_per_row[man_col > 0].sum()) if not total_man_per_row.empty else 0.0
    stats["Snitt GB (Totalt män / Antal GB)"] = fmt2(sum_gb_totman / (antal_gb if antal_gb > 0 else 1))

    # Snitt Privat GB = (sum Totalt män på rader med privat_mask) / Antal Privat GB
    sum_privat_totman = float(total_man_per_row[privat_mask].sum()) if not total_man_per_row.empty else 0.0
    stats["Snitt Privat GB (Totalt män / Antal Privat GB)"] = fmt2(sum_privat_totman / (antal_privat_gb if antal_privat_gb > 0 else 1))

    # Snitt tid GB / Privat GB (timmar)
    sum_tid_gb_sec = float(num("Summa tid (sek)")[man_col > 0].sum())
    sum_tid_privat_sec = float(num("Summa tid (sek)")[privat_mask].sum())
    stats["Snitt tid GB (h)"]     = fmt2((sum_tid_gb_sec / 3600.0) / (antal_gb if antal_gb > 0 else 1))
    stats["Snitt tid Privat GB (h)"] = fmt2((sum_tid_privat_sec / 3600.0) / (antal_privat_gb if antal_privat_gb > 0 else 1))

    # Tid/kille snitt – exkl/inkl händer (minuter)
    tid_per_kille_sec = num("Tid per kille (sek)")
    hander_per_kille_sec = num("Händer per kille (sek)")
    hander_aktiv = num("Händer aktiv")

    # exkl händer
    if len(tid_per_kille_sec) > 0:
        snitt_tid_ex = float(tid_per_kille_sec.mean()) / 60.0
    else:
        snitt_tid_ex = 0.0
    # inkl händer (räkna bara händer när Händer aktiv == 1)
    if len(tid_per_kille_sec) > 0:
        extra = (hander_per_kille_sec.where(hander_aktiv == 1, other=0.0)).fillna(0.0)
        snitt_tid_in = float((tid_per_kille_sec + extra).mean()) / 60.0
    else:
        snitt_tid_in = 0.0

    stats["Tid/kille snitt ex händer (min)"]  = fmt2(snitt_tid_ex)
    stats["Tid/kille snitt inkl händer (min)"] = fmt2(snitt_tid_in)

    # Hångel snitt (min) – använder "Hångel (sek/kille)"
    hangel_sec = num("Hångel (sek/kille)")
    snitt_hangel_min = float(hangel_sec.mean() / 60.0) if len(hangel_sec) > 0 else 0.0
    stats["Hångel snitt (min)"] = fmt2(snitt_hangel_min)

    # Älskar snitt Känner = sum(Älskar) / (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)
    kanner_max_sum = (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)
    stats["Älskar snitt Känner"] = fmt2(safe_sum("Älskar") / (kanner_max_sum if kanner_max_sum > 0 else 1))

    # Sover med snitt Nils familj = sum(Sover med) / MAX_NF
    stats["Sover med snitt Nils familj"] = fmt2(safe_sum("Sover med") / (MAX_NF if MAX_NF > 0 else 1))

    return stats
