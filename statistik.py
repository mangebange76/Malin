import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    def _to_float_series(name: str) -> pd.Series:
        if rows_df is None or rows_df.empty or name not in rows_df.columns:
            return pd.Series([], dtype=float)
        return pd.to_numeric(rows_df[name].fillna(0), errors="coerce").fillna(0)

    def _sum(name: str) -> float:
        return float(_to_float_series(name).sum())

    def _count(mask: pd.Series) -> int:
        try:
            return int(mask.sum())
        except Exception:
            return 0

    def _div(a: float, b: float) -> float:
        return float(a) / float(b) if float(b) != 0.0 else 0.0

    def _fmt(x: float, dec: int = 2) -> str:
        try:
            s = f"{float(x):,.{dec}f}"
        except Exception:
            s = f"{0.0:,.{dec}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", " ")

    def _sec_to(unit: str, sec: float) -> float:
        if unit == "h":  return sec / 3600.0
        if unit == "d":  return sec / 86400.0
        if unit == "w":  return sec / 604800.0
        return sec

    LBL_PAPPAN   = cfg.get("LBL_PAPPAN", "Pappans vänner")
    LBL_GRANNAR  = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV       = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    LBL_NF       = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    LBL_BEK      = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK      = cfg.get("LBL_ESK", "Eskilstuna killar")

    MAX_PAPPAN  = float(cfg.get("MAX_PAPPAN", 0) or 0)
    MAX_GRANNAR = float(cfg.get("MAX_GRANNAR", 0) or 0)
    MAX_NV      = float(cfg.get("MAX_NILS_VANNER", 0) or 0)
    MAX_NF      = float(cfg.get("MAX_NILS_FAMILJ", 0) or 0)
    # >>> NYTT: max för Bekanta och Personal deltagit
    MAX_BEK      = float(cfg.get("MAX_BEKANTA", 0) or 0)
    PROD_STAFFMX = float(cfg.get("PROD_STAFF", 0) or 0)

    M  = _to_float_series("Män")
    S  = _to_float_series("Svarta")
    BD = _to_float_series("Bonus deltagit")
    PD = _to_float_series("Personal deltagit")
    P  = _to_float_series(LBL_PAPPAN)
    G  = _to_float_series(LBL_GRANNAR)
    NVs = _to_float_series(LBL_NV)
    NFs = _to_float_series(LBL_NF)
    BE = _to_float_series(LBL_BEK)
    ES = _to_float_series(LBL_ESK)

    ALSKAR = _to_float_series("Älskar")
    SOVER  = _to_float_series("Sover med")
    NILS   = _to_float_series("Nils")

    SUMMA_TID_SEK = _to_float_series("Summa tid (sek)")
    TID_D_SEK     = _to_float_series("Tid D")
    TPK_SEK       = _to_float_series("Tid per kille (sek)")
    HAND_SEK      = _to_float_series("Händer per kille (sek)")
    HAK_SEK       = _to_float_series("Hångel (sek/kille)")
    HANDER_AKTIV  = _to_float_series("Händer aktiv")

    PREN = _to_float_series("Prenumeranter")
    INT  = _to_float_series("Intäkter")
    KM   = _to_float_series("Kostnad män")
    IK   = _to_float_series("Intäkt Känner")
    IF_  = _to_float_series("Intäkt företag")
    LM   = _to_float_series("Lön Malin")
    V    = _to_float_series("Vinst")

    if rows_df is not None and "Totalt Män" in rows_df.columns:
        TOT_MAN = _to_float_series("Totalt Män")
    else:
        TOT_MAN = (M + S + BD + ES + PD + P + G + NVs + NFs + BE)

    total_rows = int(len(rows_df)) if rows_df is not None else 0

    mask_gb         = (M > 0) | (S > 0)
    mask_privat     = (M == 0) & ((P > 0) | (G > 0) | (NVs > 0) | (NFs > 0))
    mask_gb_vita    = (M > 0) & (S == 0)
    mask_gb_svarta  = (S > 0) & (M == 0)
    mask_gb_blandat = (M > 0) & (S > 0)

    sum_black = float(S.sum())
    mask_rows_black = (S > 0)
    sum_black += float(ES[mask_rows_black].sum())
    sum_black += float(BD[mask_rows_black].sum())

    sum_pappan  = float(P.sum())
    sum_grannar = float(G.sum())
    sum_nv      = float(NVs.sum())
    sum_nf      = float(NFs.sum())
    sum_bek     = float(BE.sum())
    sum_alskar  = float(ALSKAR.sum())
    sum_sover   = float(SOVER.sum())
    sum_nils    = float(NILS.sum())

    denom_kanner = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    alskar_snitt_kanner = _div(sum_alskar, denom_kanner)

    def _tillf(total, mx):
        return _div(total, mx)

    tillf_pappan  = _tillf(sum_pappan,  MAX_PAPPAN)
    tillf_grannar = _tillf(sum_grannar, MAX_GRANNAR)
    tillf_nv      = _tillf(sum_nv,      MAX_NV)
    tillf_nf      = _tillf(sum_nf,      MAX_NF)
    sover_div_max_nf = _div(sum_sover, MAX_NF)

    def _proj_365(series: pd.Series) -> float:
        if total_rows <= 0:
            return 0.0
        return float(series.sum()) * (365.0 / float(total_rows))

    proj_tot_man_365 = _proj_365(TOT_MAN)
    proj_black_365   = _proj_365(S) + _proj_365(ES.where(S > 0, other=0)) + _proj_365(BD.where(S > 0, other=0))
    proj_alskar_365  = _proj_365(ALSKAR)
    proj_sover_365   = _proj_365(SOVER)

    proj_p_365  = _proj_365(P)
    proj_g_365  = _proj_365(G)
    proj_nv_365 = _proj_365(NVs)
    proj_nf_365 = _proj_365(NFs)
    proj_be_365 = _proj_365(BE)
    proj_es_365 = _proj_365(ES)
    proj_bd_365 = _proj_365(BD)
    proj_pd_365 = _proj_365(PD)

    proj_pren_365 = _proj_365(PREN)
    proj_int_365  = _proj_365(INT)
    proj_km_365   = _proj_365(KM)
    proj_ik_365   = _proj_365(IK)
    proj_if_365   = _proj_365(IF_)
    proj_lm_365   = _proj_365(LM)
    proj_v_365    = _proj_365(V)

    andel_black_365 = _div(proj_black_365, proj_tot_man_365) * 100.0 if proj_tot_man_365 > 0 else 0.0
    sb_pct = float(cfg.get("SUPER_BONUS_PCT", 0.1)) / 100.0
    proj_super_bonus_ack_365 = proj_pren_365 * sb_pct

    denom_kanner_inkl_bek = denom_kanner + 1.0
    kanner_tjanar_hist = _div(float(IK.sum()) + float(V.sum()), denom_kanner_inkl_bek)
    kanner_tjanar_365  = _div(proj_ik_365 + proj_v_365, denom_kanner_inkl_bek)

    alskar_snitt_kanner_365 = _div(proj_alskar_365, denom_kanner) if denom_kanner>0 else 0.0
    tillf_pappan_365  = _tillf(proj_p_365,  MAX_PAPPAN)
    tillf_grannar_365 = _tillf(proj_g_365,  MAX_GRANNAR)
    tillf_nv_365      = _tillf(proj_nv_365, MAX_NV)
    tillf_nf_365      = _tillf(proj_nf_365, MAX_NF)
    sover_div_max_nf_365 = _div(proj_sover_365, MAX_NF) if MAX_NF>0 else 0.0

    noj_pappan_365  = alskar_snitt_kanner_365 + tillf_pappan_365
    noj_grannar_365 = alskar_snitt_kanner_365 + tillf_grannar_365
    noj_nv_365      = alskar_snitt_kanner_365 + tillf_nv_365
    noj_nf_365      = alskar_snitt_kanner_365 + tillf_nf_365 + sover_div_max_nf_365
    noj_nils_sum_365 = _proj_365(NILS)

    noj_pappan_w   = noj_pappan_365 / 52.0
    noj_grannar_w  = noj_grannar_365 / 52.0
    noj_nv_w       = noj_nv_365 / 52.0
    noj_nf_w       = noj_nf_365 / 52.0
    noj_nils_w     = noj_nils_sum_365 / 52.0

    def _avg_per_scene_nonzero(series: pd.Series) -> float:
        cnt = _count(series > 0)
        return _div(float(series.sum()), float(cnt)) if cnt > 0 else 0.0

    avg_p_hist   = _avg_per_scene_nonzero(P)
    avg_g_hist   = _avg_per_scene_nonzero(G)
    avg_nv_hist  = _avg_per_scene_nonzero(NVs)
    avg_nf_hist  = _avg_per_scene_nonzero(NFs)
    avg_bd_hist  = _avg_per_scene_nonzero(BD)
    avg_pd_hist  = _avg_per_scene_nonzero(PD)
    avg_be_hist  = _avg_per_scene_nonzero(BE)
    avg_es_hist  = _avg_per_scene_nonzero(ES)

    out = {}
    out["— Översikt —"] = ""
    out["Antal rader"] = _fmt(total_rows, 0)
    out["Totalt antal män (alla fält)"] = _fmt(float((M + S + BD + ES + PD + P + G + NVs + NFs + BE).sum()))

    out["— Svarta —"] = ""
    out["Summa Svarta (inkl. regler)"] = _fmt(sum_black)
    out["Andel Svarta (%)"] = _fmt(100.0 * _div(sum_black, float((M + S + BD + ES + PD + P + G + NVs + NFs + BE).sum())), 2)

    out["— DP/DPP/DAP/TAP —"] = ""
    for col_name in ["DP", "DPP", "DAP", "TAP"]:
        ssum = _sum(col_name)
        scen_cnt = _count(TOT_MAN > 0)
        out[f"{col_name} – summa"] = _fmt(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt(_div(ssum, scen_cnt))

    out["— Älskar & Sover —"] = ""
    out["Älskar – summa"] = _fmt(sum_alskar)
    out["Sover med – summa"] = _fmt(sum_sover)

    out["— Källor —"] = ""
    def _kallgrupp(label: str, ser: pd.Series, maxv: float | None):
        ssum = float(ser.sum())
        cnt  = _count(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt(ssum)
        out[f"{label} – snitt per scen"] = _fmt(avg)
        if maxv and maxv > 0:
            out[f"{label} – antal tillfällen (summa/max)"] = _fmt(_div(ssum, maxv))
        else:
            out[f"{label} – antal tillfällen (summa/max)"] = _fmt(ssum)

    _kallgrupp(LBL_PAPPAN,  P,  MAX_PAPPAN)
    _kallgrupp(LBL_GRANNAR, G,  MAX_GRANNAR)
    _kallgrupp(LBL_NV,      NVs, MAX_NV)
    _kallgrupp(LBL_NF,      NFs, MAX_NF)
    # >>> NYTT: Bekanta & Personal med riktiga max
    _kallgrupp(LBL_BEK,     BE, MAX_BEK)
    _kallgrupp(LBL_ESK,     ES, None)
    _kallgrupp("Bonus deltagit", BD, None)
    _kallgrupp("Personal deltagit", PD, PROD_STAFFMX)

    out["— Händer —"] = ""
    aktiva  = _count(HANDER_AKTIV > 0)
    inakt   = _count(HANDER_AKTIV <= 0)
    out["Händer aktiva (antal)"]   = _fmt(aktiva, 0)
    out["Händer aktiva (%)"]       = _fmt(100.0 * _div(aktiva, total_rows))
    out["Händer inaktiva (antal)"] = _fmt(inakt, 0)
    out["Händer inaktiva (%)"]     = _fmt(100.0 * _div(inakt, total_rows))

    out["— Tider —"] = ""
    out["Summa tid (sek) – timmar"] = _fmt(_sec_to("h", float(SUMMA_TID_SEK.sum())))
    out["Summa tid (sek) – dagar"]  = _fmt(_sec_to("d", float(SUMMA_TID_SEK.sum())))
    out["Summa tid (sek) – veckor"] = _fmt(_sec_to("w", float(SUMMA_TID_SEK.sum())))
    out["Summa D (sek) – timmar"]   = _fmt(_sec_to("h", float(TID_D_SEK.sum())))
    out["Summa TP (sek) – timmar"]  = _fmt(_sec_to("h", float(TPK_SEK.sum())))
    out["Snitt Hångel (sek/kille)"] = _fmt(float(HAK_SEK.mean()) if total_rows>0 else 0.0)

    out["— Snitt —"] = ""
    sum_tot_man_gb = float(TOT_MAN[M > 0].sum())
    out["Snitt GB (Totalt män / antal GB)"] = _fmt(_div(sum_tot_man_gb, _count(M > 0)))
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt(_div(float(TOT_MAN[mask_privat].sum()), _count(mask_privat)))
    out["Snitt tid GB (h)"] = _fmt(_div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if _count(M > 0)>0 else 0.0)
    out["Snitt tid Privat GB (h)"] = _fmt(_div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if _count(mask_privat)>0 else 0.0)
    out["Snitt tid/kille ex händer (sek)"] = _fmt(float(TPK_SEK.mean()) if total_rows>0 else 0.0)
    tpk_incl_series = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    out["Snitt tid/kille inkl händer (sek)"] = _fmt(float(tpk_incl_series.mean()) if total_rows>0 else 0.0)

    out["— Nöjdhet —"] = ""
    out[f"Nöjdhet – {LBL_PAPPAN}"]  = _fmt(alskar_snitt_kanner + tillf_pappan)
    out[f"Nöjdhet – {LBL_GRANNAR}"] = _fmt(alskar_snitt_kanner + tillf_grannar)
    out[f"Nöjdhet – {LBL_NV}"]      = _fmt(alskar_snitt_kanner + tillf_nv)
    out[f"Nöjdhet – {LBL_NF}"]      = _fmt(alskar_snitt_kanner + tillf_nf + sover_div_max_nf)
    out["Nöjdhet – Nils (summa)"]   = _fmt(sum_nils)

    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt(float(PREN.sum()))
    out["Intäkter – summa"]      = _fmt(float(INT.sum()))
    out["Kostnad män – summa"]   = _fmt(float(KM.sum()))
    out["Intäkt Känner – summa"] = _fmt(float(IK.sum()))
    out["Intäkt företag – summa"]= _fmt(float(IF_.sum()))
    out["Lön Malin – summa"]     = _fmt(float(LM.sum()))
    out["Vinst – summa"]         = _fmt(float(V.sum()))
    out["Lön Malin / Per scen"]  = _fmt(_div(float(LM.sum()), _count(TOT_MAN > 0)))
    out["Lön Malin / Totalt antal män"] = _fmt(_div(float(LM.sum()), float((M + S + BD + ES + PD + P + G + NVs + NFs + BE).sum())))
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NVs + NFs + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"] = _fmt(_div(float(LM.sum()), total_tillfallen))
    out["Känner tjänar (nu)"] = _fmt(_div(float(IK.sum()) + float(V.sum()), denom_kanner + 1.0))

    out["— Prognos 365d —"] = ""
    out["Totalt antal män – 365d"] = _fmt(proj_tot_man_365)
    out["Summa Svarta (inkl. regler) – 365d"] = _fmt(proj_black_365)
    out["Andel Svarta (%) – 365d"] = _fmt(andel_black_365)
    out["Super-bonus ack – prognos (365d)"] = _fmt(proj_super_bonus_ack_365)
    out["Älskar – summa (365d)"] = _fmt(proj_alskar_365)
    out["Snitt älskar (Älskar snitt känner) – 365d"] = _fmt(alskar_snitt_kanner_365)
    out["Sover med – summa (365d)"] = _fmt(proj_sover_365)
    out["Snitt sover med (Sover med / MAX (Nils familj)) – 365d"] = _fmt(sover_div_max_nf_365)

    def _proj_pair(label: str, sum_365: float, avg_hist: float):
        out[f"{label} – summa (365d)"] = _fmt(sum_365)
        out[f"{label} – snitt per scen (365d)"] = _fmt(avg_hist)

    _proj_pair(LBL_PAPPAN,  proj_p_365,  avg_p_hist)
    _proj_pair(LBL_GRANNAR, proj_g_365,  avg_g_hist)
    _proj_pair(LBL_NV,      proj_nv_365, avg_nv_hist)
    _proj_pair(LBL_NF,      proj_nf_365, avg_nf_hist)
    _proj_pair("Bonus deltagit", proj_bd_365, avg_bd_hist)
    _proj_pair("Personal deltagit", proj_pd_365, avg_pd_hist)
    _proj_pair(LBL_BEK,     proj_be_365, avg_be_hist)
    _proj_pair(LBL_ESK,     proj_es_365, avg_es_hist)

    out["Prenumeranter – summa (365d)"] = _fmt(proj_pren_365)
    out["Intäkter – summa (365d)"]      = _fmt(proj_int_365)
    out["Kostnad män – summa (365d)"]   = _fmt(proj_km_365)
    out["Intäkt Känner – summa (365d)"] = _fmt(proj_ik_365)
    out["Intäkt företag – summa (365d)"]= _fmt(proj_if_365)
    out["Lön Malin – summa (365d)"]     = _fmt(proj_lm_365)
    out["Vinst – summa (365d)"]         = _fmt(proj_v_365)
    out["Känner tjänar (365d)"]         = _fmt(kanner_tjanar_365)

    out["— GB (365d) —"] = ""
    def _proj_count(mask: pd.Series) -> float:
        return _div(float(_count(mask)), float(max(1, total_rows))) * 365.0
    out["Antal GB (365d)"]         = _fmt(_proj_count(mask_gb), 0)
    out["Privat GB (365d)"]        = _fmt(_proj_count(mask_privat), 0)
    out["Antal GB vita (365d)"]    = _fmt(_proj_count(mask_gb_vita), 0)
    out["Antal GB svarta (365d)"]  = _fmt(_proj_count(mask_gb_svarta), 0)
    out["Antal GB blandat (365d)"] = _fmt(_proj_count(mask_gb_blandat), 0)

    out["— Prognos Nöjdhet (per vecka) —"] = ""
    out[f"{LBL_PAPPAN} – nöjdhet/vecka (prognos)"]  = _fmt(noj_pappan_w)
    out[f"{LBL_GRANNAR} – nöjdhet/vecka (prognos)"] = _fmt(noj_grannar_w)
    out[f"{LBL_NV} – nöjdhet/vecka (prognos)"]      = _fmt(noj_nv_w)
    out[f"{LBL_NF} – nöjdhet/vecka (prognos)"]      = _fmt(noj_nf_w)
    out["Nils – per vecka (prognos)"]               = _fmt(noj_nils_w)

    return out
