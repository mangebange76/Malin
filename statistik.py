import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Returnerar en dict {etikett: värde(str)} för visning i appen.
    Allt numeriskt formatteras med 2 decimaler i svensk stil:
      115 718,52  (mellanslag som tusentalsavskiljare, komma som decimal)

    Innehåll:
    - Vanlig statistik (GB, Nöjdhet, Totalt/Svarta, DP/DPP/DAP/TAP, Källor, Händer, Tider, Snitt, Ekonomi).
    - Ekonomi: "Känner tjänar" = (Intäkt Känner – summa + Vinst – summa) /
      (MAX_PAPPAN + MAX_GRANNAR + MAX_NILS_VANNER + MAX_NILS_FAMILJ + MAX_BEKANTA)
    - Prognos 365 dagar: enligt dina punkter + Nöjdhet (365d) och Nöjdhet / vecka (inkl. Nils).
    """
    out = {}

    # ===== Hjälpare =====
    def _fmt_sv(x, decimals: int = 2) -> str:
        """Svensk formatering: tusental med mellanslag, decimal med komma."""
        try:
            s = f"{float(x):,.{decimals}f}"
            return s.replace(",", " ").replace(".", ",")
        except Exception:
            return "0,00" if decimals == 2 else "0"

    def _col(name: str) -> pd.Series:
        if rows_df is None or rows_df.empty or name not in rows_df.columns:
            return pd.Series([], dtype=float)
        return pd.to_numeric(rows_df[name].fillna(0), errors="coerce").fillna(0)

    def _sum(name: str) -> float:
        return float(_col(name).sum())

    def _count_rows(mask: pd.Series) -> int:
        try:
            return int(mask.sum())
        except Exception:
            return 0

    def _div(a: float, b: float) -> float:
        return float(a) / float(b) if float(b) != 0.0 else 0.0

    def _sec_to_hours_days_weeks(sec: float):
        hours = sec / 3600.0
        days  = hours / 24.0
        weeks = days / 7.0
        return hours, days, weeks

    def _covered_days(df: pd.DataFrame) -> int:
        """Antal unika datum i 'Datum'. Fallback: antal rader (min 1)."""
        try:
            if df is not None and not df.empty and "Datum" in df.columns:
                d = pd.to_datetime(df["Datum"], errors="coerce").dropna().dt.date
                n = int(d.nunique())
                if n > 0:
                    return n
        except Exception:
            pass
        return max(1, int(len(df) if df is not None else 1))

    # Dynamiska etiketter
    LBL_PAPPAN   = cfg.get("LBL_PAPPAN", "Pappans vänner")
    LBL_GRANNAR  = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV       = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    LBL_NF       = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    LBL_BEK      = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK      = cfg.get("LBL_ESK", "Eskilstuna killar")

    # Maxvärden från inställningar
    MAX_PAPPAN   = float(cfg.get("MAX_PAPPAN", 0) or 0)
    MAX_GRANNAR  = float(cfg.get("MAX_GRANNAR", 0) or 0)
    MAX_NV       = float(cfg.get("MAX_NILS_VANNER", 0) or 0)
    MAX_NF       = float(cfg.get("MAX_NILS_FAMILJ", 0) or 0)
    MAX_BEK      = float(cfg.get("MAX_BEKANTA", 0) or 0)

    # ===== Utgångskolumner =====
    M  = _col("Män")
    S  = _col("Svarta")
    BD = _col("Bonus deltagit")
    PD = _col("Personal deltagit")
    P  = _col(LBL_PAPPAN)
    G  = _col(LBL_GRANNAR)
    NV = _col(LBL_NV)
    NF = _col(LBL_NF)
    BE = _col(LBL_BEK)
    ES = _col(LBL_ESK)

    ALSKAR = _col("Älskar")
    SOVER  = _col("Sover med")

    SUMMA_TID_SEK = _col("Summa tid (sek)")
    TID_D_SEK     = _col("Tid D")  # sparas som "Tid D" i appen
    TPK_SEK       = _col("Tid per kille (sek)")
    HAND_SEK      = _col("Händer per kille (sek)")
    HAK_SEK       = _col("Hångel (sek/kille)")

    HANDER_AKTIV  = _col("Händer aktiv")

    # Fallback "Totalt Män" (om kolumn saknas) – enligt totalsumma i appen
    if rows_df is not None and "Totalt Män" in rows_df.columns:
        TOT_MAN = _col("Totalt Män")
    else:
        TOT_MAN = (M + S + BD + ES + PD + P + G + NV + NF + BE)

    # ===== GB-sektion =====
    mask_gb         = (M > 0) | (S > 0)
    mask_privat     = (M == 0) & ((P > 0) | (G > 0) | (NV > 0) | (NF > 0))
    mask_gb_vita    = (M > 0) & (S == 0)
    mask_gb_svarta  = (S > 0) & (M == 0)
    mask_gb_blandat = (M > 0) & (S > 0)

    cnt_gb         = _count_rows(mask_gb)
    cnt_privat     = _count_rows(mask_privat)
    cnt_gb_vita    = _count_rows(mask_gb_vita)
    cnt_gb_svarta  = _count_rows(mask_gb_svarta)
    cnt_gb_blandat = _count_rows(mask_gb_blandat)

    out["— GB —"] = ""
    out["Antal GB"]         = _fmt_sv(cnt_gb)
    out["Privat GB"]        = _fmt_sv(cnt_privat)
    out["Antal GB vita"]    = _fmt_sv(cnt_gb_vita)
    out["Antal GB svarta"]  = _fmt_sv(cnt_gb_svarta)
    out["Antal GB blandat"] = _fmt_sv(cnt_gb_blandat)

    # ===== Nöjdhet =====
    sum_pappan  = float(P.sum())
    sum_grannar = float(G.sum())
    sum_nv      = float(NV.sum())
    sum_nf      = float(NF.sum())
    sum_bek     = float(BE.sum())
    sum_sover   = float(SOVER.sum())
    sum_nils    = float(_col("Nils").sum())
    sum_alskar  = float(ALSKAR.sum())

    denom_kanner_core = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    alskar_snitt_kanner = _div(sum_alskar, denom_kanner_core)

    def _antal_tillfallen(total, mx):  # summa / max
        return _div(total, mx)

    tillf_pappan  = _antal_tillfallen(sum_pappan,  MAX_PAPPAN)
    tillf_grannar = _antal_tillfallen(sum_grannar, MAX_GRANNAR)
    tillf_nv      = _antal_tillfallen(sum_nv,      MAX_NV)
    tillf_nf      = _antal_tillfallen(sum_nf,      MAX_NF)
    sover_div_max_nf = _div(sum_sover, MAX_NF)

    out["— Nöjdhet —"] = ""
    out[f"Nöjdhet – {LBL_PAPPAN}"]  = _fmt_sv(alskar_snitt_kanner + tillf_pappan)
    out[f"Nöjdhet – {LBL_GRANNAR}"] = _fmt_sv(alskar_snitt_kanner + tillf_grannar)
    out[f"Nöjdhet – {LBL_NV}"]      = _fmt_sv(alskar_snitt_kanner + tillf_nv)
    out[f"Nöjdhet – {LBL_NF}"]      = _fmt_sv(alskar_snitt_kanner + tillf_nf + sover_div_max_nf)
    out["Nöjdhet – Nils (summa)"]   = _fmt_sv(sum_nils)

    # ===== Totalt / Svarta =====
    total_man_sum = float((M + S + BD + ES + PD + P + G + NV + NF + BE).sum())
    out["— Totalt —"] = ""
    out["Totalt antal män (alla fält)"] = _fmt_sv(total_man_sum)

    sum_black = float(S.sum())
    mask_rows_black = (S > 0)
    sum_black += float(ES[mask_rows_black].sum())
    sum_black += float(BD[mask_rows_black].sum())
    out["Summa Svarta (inkl. regler)"] = _fmt_sv(sum_black)
    out["Andel Svarta (%)"] = _fmt_sv(100.0 * _div(sum_black, total_man_sum))

    # ===== DP / DPP / DAP / TAP =====
    dp_sum  = _sum("DP")
    dpp_sum = _sum("DPP")
    dap_sum = _sum("DAP")
    tap_sum = _sum("TAP")
    mask_scen = (TOT_MAN > 0)
    denom_scen = _count_rows(mask_scen)

    for col_name, ssum in [("DP", dp_sum), ("DPP", dpp_sum), ("DAP", dap_sum), ("TAP", tap_sum)]:
        avg = _div(ssum, denom_scen)
        out[f"{col_name} – summa"] = _fmt_sv(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt_sv(avg)

    # ===== Älskar / Sover med =====
    out["Älskar – summa"]     = _fmt_sv(sum_alskar)
    out["Sover med – summa"]  = _fmt_sv(sum_sover)

    # ===== Källor – summor + snitt per scen (fält>0) + antal tillfällen =====
    out["— Källor —"] = ""
    def _sum_snitt_tillfallen(label: str, ser: pd.Series, maxv: float):
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt_sv(ssum)
        out[f"{label} – snitt per scen"] = _fmt_sv(avg)
        out[f"{label} – antal tillfällen"] = _fmt_sv(_div(ssum, maxv))

    _sum_snitt_tillfallen("Bonus deltagit",     BD, 1.0)
    _sum_snitt_tillfallen("Personal deltagit",  PD, 1.0)
    _sum_snitt_tillfallen(LBL_PAPPAN,           P,  MAX_PAPPAN)
    _sum_snitt_tillfallen(LBL_GRANNAR,          G,  MAX_GRANNAR)
    _sum_snitt_tillfallen(LBL_NV,               NV, MAX_NV)
    _sum_snitt_tillfallen(LBL_NF,               NF, MAX_NF)
    _sum_snitt_tillfallen(LBL_BEK,              BE, 1.0)
    _sum_snitt_tillfallen(LBL_ESK,              ES, 1.0)

    # Summan av MAX (känner-fälten)
    out["Summa MAX (källor, inställningar)"] = _fmt_sv(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ===== Händer =====
    total_rows = int(len(rows_df)) if rows_df is not None else 0
    aktiva  = _count_rows(HANDER_AKTIV > 0)
    inakt   = _count_rows(HANDER_AKTIV <= 0)
    out["— Händer —"] = ""
    out["Händer aktiva (antal)"]   = _fmt_sv(aktiva)
    out["Händer aktiva (%)"]       = _fmt_sv(100.0 * _div(aktiva, total_rows))
    out["Händer inaktiva (antal)"] = _fmt_sv(inakt)
    out["Händer inaktiva (%)"]     = _fmt_sv(100.0 * _div(inakt, total_rows))

    # ===== Tider =====
    sum_tid_sec  = float(SUMMA_TID_SEK.sum())
    sum_tidD_sec = float(TID_D_SEK.sum())
    sum_tpk_sec  = float(TPK_SEK.sum())

    out["— Tider —"] = ""
    h, d, w = _sec_to_hours_days_weeks(sum_tid_sec)
    out["Summa tid (sek) – timmar"] = _fmt_sv(h)
    out["Summa tid (sek) – dagar"]  = _fmt_sv(d)
    out["Summa tid (sek) – veckor"] = _fmt_sv(w)

    h, d, w = _sec_to_hours_days_weeks(sum_tidD_sec)
    out["Summa D (sek) – timmar"] = _fmt_sv(h)
    out["Summa D (sek) – dagar"]  = _fmt_sv(d)
    out["Summa D (sek) – veckor"] = _fmt_sv(w)

    h, d, w = _sec_to_hours_days_weeks(sum_tpk_sec)
    out["Summa TP (sek) – timmar"] = _fmt_sv(h)
    out["Summa TP (sek) – dagar"]  = _fmt_sv(d)
    out["Summa TP (sek) – veckor"] = _fmt_sv(w)

    # ===== Snitt =====
    out["— Snitt —"] = ""
    sum_tot_man_gb = float(TOT_MAN[M > 0].sum())
    denom_gb = _count_rows(M > 0)
    out["Snitt GB (Totalt män / antal GB)"] = _fmt_sv(_div(sum_tot_man_gb, denom_gb))

    sum_tot_man_privat = float(TOT_MAN[mask_privat].sum())
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt_sv(_div(sum_tot_man_privat, cnt_privat))

    mean_tid_gb_h   = _div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if denom_gb>0 else 0.0
    mean_tid_priv_h = _div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if cnt_privat>0 else 0.0
    out["Snitt tid GB (h)"]        = _fmt_sv(mean_tid_gb_h)
    out["Snitt tid Privat GB (h)"] = _fmt_sv(mean_tid_priv_h)

    avg_tpk_ex = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    tpk_incl_series = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_series.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"]   = _fmt_sv(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"] = _fmt_sv(avg_tpk_incl)

    out["Snitt Hångel (sek/kille)"] = _fmt_sv(float(HAK_SEK.mean()) if total_rows>0 else 0.0)
    out["Älskar snitt känner"]      = _fmt_sv(alskar_snitt_kanner)
    out["Sover med / MAX (Nils familj)"] = _fmt_sv(sover_div_max_nf)

    # ===== Ekonomi (vanlig) + Känner tjänar =====
    PREN = _col("Prenumeranter")
    INT  = _col("Intäkter")
    KM   = _col("Kostnad män")
    IK   = _col("Intäkt Känner")
    IF_  = _col("Intäkt företag")
    LM   = _col("Lön Malin")
    V    = _col("Vinst")

    pren_sum = float(PREN.sum())
    int_sum  = float(INT.sum())
    km_sum   = float(KM.sum())
    ik_sum   = float(IK.sum())
    if_sum   = float(IF_.sum())
    lm_sum   = float(LM.sum())
    v_sum    = float(V.sum())

    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt_sv(pren_sum)
    out["Intäkter – summa"]      = _fmt_sv(int_sum)
    out["Kostnad män – summa"]   = _fmt_sv(km_sum)
    out["Intäkt Känner – summa"] = _fmt_sv(ik_sum)
    out["Intäkt företag – summa"]= _fmt_sv(if_sum)
    out["Lön Malin – summa"]     = _fmt_sv(lm_sum)
    out["Vinst – summa"]         = _fmt_sv(v_sum)

    out["Lön Malin / Per scen"]               = _fmt_sv(_div(lm_sum, denom_gb))
    out["Lön Malin / Totalt antal män"]       = _fmt_sv(_div(lm_sum, total_man_sum))
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"] = _fmt_sv(_div(lm_sum, total_tillfallen))

    # Känner tjänar (vanlig)
    denom_kanner_all = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK
    kanner_tjanar = _div(ik_sum + v_sum, denom_kanner_all)
    out["Känner tjänar"] = _fmt_sv(kanner_tjanar)

    # ===== Prognos 365 dagar =====
    days = _covered_days(rows_df)
    factor_365 = 365.0 / float(days) if days > 0 else 0.0
    weeks_per_year = 365.0 / 7.0  # ~52.14

    # Grundsummor 365d
    total_man_sum_365 = total_man_sum * factor_365
    sum_black_365     = sum_black * factor_365
    alskar_365        = sum_alskar * factor_365
    sover_365         = sum_sover * factor_365
    p_365             = sum_pappan * factor_365
    g_365             = sum_grannar * factor_365
    nv_365            = sum_nv * factor_365
    nf_365            = sum_nf * factor_365
    bd_365            = float(BD.sum()) * factor_365
    pd_365            = float(PD.sum()) * factor_365
    bek_365           = float(BE.sum()) * factor_365
    esk_365           = float(ES.sum()) * factor_365
    nils_365          = sum_nils * factor_365  # <-- Nils i prognosen

    pren_365 = pren_sum * factor_365
    int_365  = int_sum  * factor_365
    km_365   = km_sum   * factor_365
    ik_365   = ik_sum   * factor_365
    if_365   = if_sum   * factor_365
    lm_365   = lm_sum   * factor_365
    v_365    = v_sum    * factor_365

    # GB-antal 365d (frekvens * 365)
    gb_365         = _div(cnt_gb, days) * 365.0
    privat_gb_365  = _div(cnt_privat, days) * 365.0
    gb_vita_365    = _div(cnt_gb_vita, days) * 365.0
    gb_svarta_365  = _div(cnt_gb_svarta, days) * 365.0
    gb_blandat_365 = _div(cnt_gb_blandat, days) * 365.0

    # Snitt per scen (nuvarande) för källor + Lön Malin
    def _avg_per_scen(ser: pd.Series) -> float:
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        return _div(ssum, cnt)

    p_avg   = _avg_per_scen(P)
    g_avg   = _avg_per_scen(G)
    nv_avg  = _avg_per_scen(NV)
    nf_avg  = _avg_per_scen(NF)
    bd_avg  = _avg_per_scen(BD)
    pd_avg  = _avg_per_scen(PD)
    bek_avg = _avg_per_scen(BE)
    lm_avg_per_scen = _div(lm_sum, denom_gb)

    # Känner tjänar 365d
    kanner_tjanar_365 = _div(ik_365 + v_365, denom_kanner_all)

    out["— Prognos 365 dagar —"] = ""

    # Totalt män
    out["Totalt antal män – 365d"] = _fmt_sv(total_man_sum_365)

    # Svarta
    out["Summa Svarta (inkl. regler) – 365d"] = _fmt_sv(sum_black_365)
    out["Andel Svarta (%)"] = _fmt_sv(100.0 * _div(sum_black, total_man_sum))

    # Älskar + snitt
    out["Älskar – summa (365d)"] = _fmt_sv(alskar_365)
    out["Snitt Älskar (känner)"] = _fmt_sv(_div(alskar_365, denom_kanner_core))

    # Sover med + snitt
    out["Sover med – summa (365d)"] = _fmt_sv(sover_365)
    out["Snitt Sover med / MAX (Nils familj)"] = _fmt_sv(_div(sover_365, MAX_NF))

    # Källor (summa 365d + snitt per scen)
    out[f"{LBL_PAPPAN} – summa (365d)"]   = _fmt_sv(p_365)
    out[f"{LBL_PAPPAN} – snitt per scen"] = _fmt_sv(p_avg)

    out[f"{LBL_GRANNAR} – summa (365d)"]   = _fmt_sv(g_365)
    out[f"{LBL_GRANNAR} – snitt per scen"] = _fmt_sv(g_avg)

    out[f"{LBL_NV} – summa (365d)"]        = _fmt_sv(nv_365)
    out[f"{LBL_NV} – snitt per scen"]      = _fmt_sv(nv_avg)

    out[f"{LBL_NF} – summa (365d)"]        = _fmt_sv(nf_365)
    out[f"{LBL_NF} – snitt per scen"]      = _fmt_sv(nf_avg)

    out["Bonus deltagit – summa (365d)"]    = _fmt_sv(bd_365)
    out["Bonus deltagit – snitt per scen"]  = _fmt_sv(bd_avg)

    out["Personal deltagit – summa (365d)"]   = _fmt_sv(pd_365)
    out["Personal deltagit – snitt per scen"] = _fmt_sv(pd_avg)

    out[f"{LBL_BEK} – summa (365d)"]        = _fmt_sv(bek_365)
    out[f"{LBL_BEK} – snitt per scen"]      = _fmt_sv(bek_avg)

    out[f"{LBL_ESK} – summa (365d)"]        = _fmt_sv(esk_365)

    # ===== Nöjdhet 365d + per vecka (inkl. Nils) =====
    alskar_snitt_kanner_365 = _div(alskar_365, denom_kanner_core)
    tillf_pappan_365        = _div(p_365,  MAX_PAPPAN)
    tillf_grannar_365       = _div(g_365,  MAX_GRANNAR)
    tillf_nv_365            = _div(nv_365, MAX_NV)
    tillf_nf_365            = _div(nf_365, MAX_NF)
    sover_div_max_nf_365    = _div(sover_365, MAX_NF)

    noj_pappan_365  = alskar_snitt_kanner_365 + tillf_pappan_365
    noj_grannar_365 = alskar_snitt_kanner_365 + tillf_grannar_365
    noj_nv_365      = alskar_snitt_kanner_365 + tillf_nv_365
    noj_nf_365      = alskar_snitt_kanner_365 + tillf_nf_365 + sover_div_max_nf_365
    # Nils: i "vanlig" nöjdhet använder vi bara summan av kolumnen Nils, så vi skalar den till 365 dagar.
    noj_nils_365    = nils_365

    out[f"Nöjdhet – {LBL_PAPPAN} (365d)"]  = _fmt_sv(noj_pappan_365)
    out[f"Nöjdhet – {LBL_PAPPAN} / vecka"] = _fmt_sv(_div(noj_pappan_365, weeks_per_year))

    out[f"Nöjdhet – {LBL_GRANNAR} (365d)"]  = _fmt_sv(noj_grannar_365)
    out[f"Nöjdhet – {LBL_GRANNAR} / vecka"] = _fmt_sv(_div(noj_grannar_365, weeks_per_year))

    out[f"Nöjdhet – {LBL_NV} (365d)"]       = _fmt_sv(noj_nv_365)
    out[f"Nöjdhet – {LBL_NV} / vecka"]      = _fmt_sv(_div(noj_nv_365, weeks_per_year))

    out[f"Nöjdhet – {LBL_NF} (365d)"]       = _fmt_sv(noj_nf_365)
    out[f"Nöjdhet – {LBL_NF} / vecka"]      = _fmt_sv(_div(noj_nf_365, weeks_per_year))

    out["Nöjdhet – Nils (365d)"]            = _fmt_sv(noj_nils_365)
    out["Nöjdhet – Nils / vecka"]           = _fmt_sv(_div(noj_nils_365, weeks_per_year))

    # Ekonomi 365d
    out["Prenumeranter – summa (365d)"] = _fmt_sv(pren_365)
    out["Intäkter – summa (365d)"]      = _fmt_sv(int_365)
    out["Kostnad män – summa (365d)"]   = _fmt_sv(km_365)
    out["Intäkt Känner – summa (365d)"] = _fmt_sv(ik_365)
    out["Intäkt företag – summa (365d)"]= _fmt_sv(if_365)
    out["Lön Malin – summa (365d)"]     = _fmt_sv(lm_365)
    out["Lön Malin – snitt per scen"]   = _fmt_sv(lm_avg_per_scen)

    # Känner tjänar – 365d
    out["Känner tjänar – (365d)"] = _fmt_sv(kanner_tjanar_365)

    out["Vinst – summa (365d)"]   = _fmt_sv(v_365)

    # GB-frekvenser 365d
    out["Antal GB (365d)"]         = _fmt_sv(gb_365)
    out["Privat GB (365d)"]        = _fmt_sv(privat_gb_365)
    out["Antal GB vita (365d)"]    = _fmt_sv(gb_vita_365)
    out["Antal GB svarta (365d)"]  = _fmt_sv(gb_svarta_365)
    out["Antal GB blandat (365d)"] = _fmt_sv(gb_blandat_365)

    return out
