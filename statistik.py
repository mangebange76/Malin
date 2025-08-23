# statistik.py
# Bas 250823 – samlar all statistik enligt beställning
from __future__ import annotations
from typing import Dict, Any
import pandas as pd
import math

def compute_stats(rows: pd.DataFrame, cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = cfg or {}

    # ---- Hjälpare ----
    def get_col(name: str) -> pd.Series:
        if name in rows.columns:
            return pd.to_numeric(rows[name], errors="coerce").fillna(0)
        # saknas -> 0-serie
        return pd.Series([0] * len(rows), dtype=float)

    def f2(x: float) -> str:
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "0.00"

    def fmt_hm_from_seconds(total_sec: float) -> str:
        s = max(0, int(round(total_sec)))
        h, rem = divmod(s, 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def fmt_dh_from_seconds(total_sec: float) -> str:
        s = max(0, int(round(total_sec)))
        d, rem = divmod(s, 86400)
        h = rem // 3600
        return f"{d}d {h}h"

    def fmt_wd_from_seconds(total_sec: float) -> str:
        s = max(0, int(round(total_sec)))
        d = s // 86400
        w, d2 = divmod(d, 7)
        return f"{w}v {d2}d"

    def fmt_ms_from_seconds(total_sec: float) -> str:
        s = max(0, int(round(total_sec)))
        m, s2 = divmod(s, 60)
        return f"{m}:{s2:02d}"

    # ---- Etiketter från inställningar ----
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
    PROD_STAFF  = float(cfg.get("PROD_STAFF", 0))

    # ---- Kolumner (serier) ----
    M   = get_col("Män")
    S   = get_col("Svarta")
    DP  = get_col("DP")
    DPP = get_col("DPP")
    DAP = get_col("DAP")
    TAP = get_col("TAP")

    BONUS = get_col("Bonus deltagit")
    PERS  = get_col("Personal deltagit")

    PAPPAN  = get_col(LBL_PAPPAN)
    GRANNAR = get_col(LBL_GRANNAR)
    NVENNER = get_col(LBL_NV)
    NFAMILJ = get_col(LBL_NF)
    BEK     = get_col(LBL_BEK)
    ESK     = get_col(LBL_ESK)

    ALSKAR   = get_col("Älskar")
    SOVERMED = get_col("Sover med")

    SUMMA_TID_SEK = get_col("Summa tid (sek)")
    TID_D_SEK     = get_col("Tid D")  # kolumnen heter "Tid D" (sek)
    TID_PER_KILLE = get_col("Tid per kille (sek)")
    HANDER_KILLE  = get_col("Händer per kille (sek)")
    HANDER_AKTIV  = get_col("Händer aktiv")

    HANGEL_SEK = get_col("Hångel (sek/kille)")

    # Ekonomi
    PREN   = get_col("Prenumeranter")
    INTK   = get_col("Intäkter")
    KOST_M = get_col("Kostnad män")
    INTK_K = get_col("Intäkt Känner")
    INTK_F = get_col("Intäkt företag")
    LON    = get_col("Lön Malin")
    VINST  = get_col("Vinst")

    n_rows = len(rows)

    # ---- Totalt män (statistikbas) ----
    # Def: Män + Svarta + Bonus + Eskilstuna + Personal deltagit + (Pappan + Grannar + Nils vänner + Nils familj + Bekanta)
    TOT_MEN_SERIES = M + S + BONUS + ESK + PERS + PAPPAN + GRANNAR + NVENNER + NFAMILJ + BEK
    TOT_MEN_SUM = float(TOT_MEN_SERIES.sum())

    # ---- GB / Privat GB / Vita & Svarta GB ----
    gb_mask           = (M > 0) | (S > 0)
    antal_gb          = int(gb_mask.sum())

    gb_vita_mask      = (M > 0) & (S == 0)
    antal_gb_vita     = int(gb_vita_mask.sum())

    gb_svarta_mask    = (S > 0) & (M == 0)
    antal_gb_svarta   = int(gb_svarta_mask.sum())

    # Privat GB: Män = 0 och (någon källa > 0)
    kallsum = PAPPAN + GRANNAR + NVENNER + NFAMILJ
    privat_gb_mask    = (M == 0) & (kallsum > 0)
    antal_privat_gb   = int(privat_gb_mask.sum())

    # Snitt GB & Privat GB (Totalt Män / antal respektive grupper)
    snitt_gb      = (TOT_MEN_SERIES[gb_mask].sum() / antal_gb) if antal_gb > 0 else 0.0
    snitt_priv_gb = (TOT_MEN_SERIES[privat_gb_mask].sum() / antal_privat_gb) if antal_privat_gb > 0 else 0.0

    # ---- Andel Svarta ----
    # Numerator: Svarta + (Bonus + Eskilstuna) på rader där Svarta > 0
    svarta_rad_mask = (S > 0)
    svarta_numer = S.sum() + BONUS[svarta_rad_mask].sum() + ESK[svarta_rad_mask].sum()
    svarta_total = float(S.sum())  # visas också som "Summa Svarta"
    andel_svarta = (svarta_numer / TOT_MEN_SUM * 100.0) if TOT_MEN_SUM > 0 else 0.0

    # ---- DP/DPP/DAP/TAP: summor + snitt per scen (def: rader där Totalt män > 0) ----
    scene_mask_totmen = (TOT_MEN_SERIES > 0)
    scene_cnt = int(scene_mask_totmen.sum()) if n_rows > 0 else 0

    DP_sum  = float(DP.sum());  DP_avg  = (DP_sum  / scene_cnt) if scene_cnt > 0 else 0.0
    DPP_sum = float(DPP.sum()); DPP_avg = (DPP_sum / scene_cnt) if scene_cnt > 0 else 0.0
    DAP_sum = float(DAP.sum()); DAP_avg = (DAP_sum / scene_cnt) if scene_cnt > 0 else 0.0
    TAP_sum = float(TAP.sum()); TAP_avg = (TAP_sum / scene_cnt) if scene_cnt > 0 else 0.0

    # ---- Älskar & Sover med: summor + extra ----
    ALSKAR_sum   = float(ALSKAR.sum())
    SOVER_sum    = float(SOVERMED.sum())
    # Sover med / MAX_NILS_FAMILJ
    sover_div_max_nf = (SOVER_sum / MAX_NF) if MAX_NF > 0 else 0.0

    # ---- Tid-summor & tidspresentationer ----
    tot_tid_s = float(SUMMA_TID_SEK.sum())
    tot_tid_d = float(TID_D_SEK.sum())
    tot_tp    = float(TID_PER_KILLE.sum())  # "Summa TP sek"

    # ---- Händer: aktiva/inaktiva (antal + %) ----
    active_cnt   = int((HANDER_AKTIV == 1).sum())
    inactive_cnt = int((HANDER_AKTIV == 0).sum())
    active_pct   = (active_cnt / n_rows * 100.0) if n_rows > 0 else 0.0
    inactive_pct = (inactive_cnt / n_rows * 100.0) if n_rows > 0 else 0.0

    # ---- Summa MAX-värden Känner (Pappan+Grannar+Nils vänner+Nils familj) ----
    summa_max_kanner = float(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ---- Tid per kille – snitt ex/inkl händer ----
    # ex händer: snitt av TID_PER_KILLE över alla rader (sum/antal rader)
    tpk_ex = (TID_PER_KILLE.sum() / n_rows) if n_rows > 0 else 0.0
    # inkl händer: på radnivå, lägg till Händer/kille bara om Händer aktiv==1
    tpk_incl_series = TID_PER_KILLE + HANDER_KILLE.where(HANDER_AKTIV == 1, other=0)
    tpk_incl = (tpk_incl_series.sum() / n_rows) if n_rows > 0 else 0.0

    # ---- Genomsnitt hångel (sek/kille) ----
    hangel_avg_sec = (HANGEL_SEK.sum() / n_rows) if n_rows > 0 else 0.0

    # ---- Älskar snitt Känner = Sum(Älskar) / (MAX_PAPPAN+MAX_GRANNAR+MAX_NV+MAX_NF) ----
    alskar_snitt_kanner = (ALSKAR_sum / summa_max_kanner) if summa_max_kanner > 0 else 0.0

    # ---- Per-fält block: summa, snitt per scen, "antal tillfällen" (summa / max) ----
    def block_sum_snitt_tillfallen(label: str, serie: pd.Series, max_value: float | None) -> Dict[str, str]:
        out = {}
        ssum = float(serie.sum())
        out[f"{label} – summa"] = f2(ssum)
        cnt_pos = int((serie > 0).sum())
        out[f"{label} – snitt per scen"] = f2(ssum / cnt_pos) if cnt_pos > 0 else "0.00"
        if max_value is not None and max_value > 0:
            out[f"{label} – antal tillfällen"] = f2(ssum / max_value)
        return out

    # ---- Ekonomi – summeringar ----
    pren_sum  = float(PREN.sum())
    intk_sum  = float(INTK.sum())
    kost_sum  = float(KOST_M.sum())
    intkK_sum = float(INTK_K.sum())
    intkF_sum = float(INTK_F.sum())
    lon_sum   = float(LON.sum())
    vinst_sum = float(VINST.sum())

    # ---- Snitt på Lön Malin (tre varianter) ----
    lon_per_scen      = (lon_sum / antal_gb) if antal_gb > 0 else 0.0  # "Per scen" = rader där M>0 eller S>0
    lon_per_tot_men   = (lon_sum / TOT_MEN_SUM) if TOT_MEN_SUM > 0 else 0.0
    # Totalt antal tillfällen = M+S+Älskar+Sover med+Bonus+Personal+P+G+NV+NF+Bek+Esk
    TOTAL_TILLFALLEN_SER = M + S + ALSKAR + SOVERMED + BONUS + PERS + PAPPAN + GRANNAR + NVENNER + NFAMILJ + BEK + ESK
    total_tillfallen = float(TOTAL_TILLFALLEN_SER.sum())
    lon_per_tillfalle = (lon_sum / total_tillfallen) if total_tillfallen > 0 else 0.0

    # =========================
    # U T – Stat-dict i önskad ordning
    # =========================
    stats: Dict[str, Any] = {}

    # Toppsektion
    stats["Antal GB"] = antal_gb
    stats["Privat GB"] = antal_privat_gb
    stats["Antal GB vita"] = antal_gb_vita
    stats["Antal GB svarta"] = antal_gb_svarta

    # Snitt-sektion (för allmänna snitt)
    stats["— Snitt —"] = ""
    stats["Snitt GB (Totalt män / GB)"] = f2(snitt_gb)
    stats["Snitt Privat GB (Totalt män / Privat GB)"] = f2(snitt_priv_gb)
    stats["Tid/kille snitt ex händer (m:s)"] = fmt_ms_from_seconds(tpk_ex)
    stats["Tid/kille snitt inkl händer (m:s)"] = fmt_ms_from_seconds(tpk_incl)
    stats["Genomsnitt hångel (m:s/kille)"] = fmt_ms_from_seconds(hangel_avg_sec)
    stats["Älskar snitt Känner"] = f2(alskar_snitt_kanner)

    # Andel svarta + summa svarta
    stats["— Svarta —"] = ""
    stats["Summa Svarta"] = f2(svarta_total)
    stats["Andel Svarta (%)"] = f2(andel_svarta)

    # DP/DPP/DAP/TAP
    stats["— DP/DPP/DAP/TAP —"] = ""
    stats["DP – summa"] = f2(DP_sum)
    stats["DP – snitt per scen"] = f2(DP_avg)
    stats["DPP – summa"] = f2(DPP_sum)
    stats["DPP – snitt per scen"] = f2(DPP_avg)
    stats["DAP – summa"] = f2(DAP_sum)
    stats["DAP – snitt per scen"] = f2(DAP_avg)
    stats["TAP – summa"] = f2(TAP_sum)
    stats["TAP – snitt per scen"] = f2(TAP_avg)

    # Älskar / Sover med
    stats["— Älskar / Sover —"] = ""
    stats["Älskar – summa"] = f2(ALSKAR_sum)
    stats["Sover med – summa"] = f2(SOVER_sum)
    stats["Sover med – / MAX (Nils familj)"] = f2(sover_div_max_nf)

    # Tid-summor
    stats["— Tider —"] = ""
    stats["Summa tid (sek)"] = f2(tot_tid_s)
    stats["Summa tid (timmar:minuter)"] = fmt_hm_from_seconds(tot_tid_s)
    stats["Summa tid (dagar:timmar)"] = fmt_dh_from_seconds(tot_tid_s)
    stats["Summa tid (veckor:dagar)"] = fmt_wd_from_seconds(tot_tid_s)

    stats["Summa D (sek)"] = f2(tot_tid_d)
    stats["Summa D (timmar:minuter)"] = fmt_hm_from_seconds(tot_tid_d)
    stats["Summa D (dagar:timmar)"] = fmt_dh_from_seconds(tot_tid_d)
    stats["Summa D (veckor:dagar)"] = fmt_wd_from_seconds(tot_tid_d)

    stats["Summa TP (sek)"] = f2(tot_tp)
    stats["Summa TP (timmar:minuter)"] = fmt_hm_from_seconds(tot_tp)
    stats["Summa TP (dagar:timmar)"] = fmt_dh_from_seconds(tot_tp)
    stats["Summa TP (veckor:dagar)"] = fmt_wd_from_seconds(tot_tp)

    # Händer aktiva/inaktiva
    stats["— Händer —"] = ""
    stats["Aktiva (antal)"] = active_cnt
    stats["Aktiva (%)"] = f2(active_pct)
    stats["Inaktiva (antal)"] = inactive_cnt
    stats["Inaktiva (%)"] = f2(inactive_pct)

    # Per-fält block: (summa, snitt per scen, antal tillfällen (=summa/max))
    stats["— Källor —"] = ""
    # Personal deltagit: "max" = PROD_STAFF
    stats.update(block_sum_snitt_tillfallen("Personal deltagit", PERS, PROD_STAFF))
    stats.update(block_sum_snitt_tillfallen(LBL_PAPPAN,  PAPPAN,  MAX_PAPPAN))
    stats.update(block_sum_snitt_tillfallen(LBL_GRANNAR, GRANNAR, MAX_GRANNAR))
    stats.update(block_sum_snitt_tillfallen(LBL_NV,      NVENNER, MAX_NV))
    stats.update(block_sum_snitt_tillfallen(LBL_NF,      NFAMILJ, MAX_NF))
    stats.update(block_sum_snitt_tillfallen(LBL_BEK,     BEK,     None))  # inget MAX definierat
    stats.update(block_sum_snitt_tillfallen(LBL_ESK,     ESK,     None))  # inget MAX definierat

    # Summa MAX Känner
    stats["Summa MAX (Känner)"] = f2(summa_max_kanner)

    # Totalt män (statistik-basen)
    stats["— Totalt män —"] = ""
    stats["Totalt män (summa)"] = f2(TOT_MEN_SUM)

    # Ekonomi
    stats["— Ekonomi —"] = ""
    stats["Prenumeranter (summa)"] = f2(pren_sum)
    stats["Intäkter (summa)"] = f2(intk_sum)
    stats["Kostnad män (summa)"] = f2(kost_sum)
    stats["Intäkt Känner (summa)"] = f2(intkK_sum)
    stats["Intäkt företag (summa)"] = f2(intkF_sum)
    stats["Lön Malin (summa)"] = f2(lon_sum)
    stats["Vinst (summa)"] = f2(vinst_sum)

    # Snitt på Lön Malin – direkt under Ekonomi
    stats["— Lön Malin – snitt —"] = ""
    stats["Lön Malin / Per scen"] = f2(lon_per_scen)          # rader där M>0 eller S>0
    stats["Lön Malin / Totalt män"] = f2(lon_per_tot_men)     # dividerat med Totalt män (summa)
    stats["Lön Malin / Totalt antal tillfällen"] = f2(lon_per_tillfalle)

    return stats
