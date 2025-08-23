import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Returnerar en dict {etikett: värde(str)} för visning i appen.
    Allt numeriskt formatteras med 2 decimaler. Tider summeras i sekunder
    och visas som timmar/dagar/veckor (decimalt).

    NYTT:
    — Prognos 365 dagar —
      Estimerar vad alla SUMMOR skulle bli på 365 dagar om man fortsätter i samma
      dagstakt som i nuvarande data (dagstakt = summa / antal unika Datum).
      Om 'Datum' saknas används antal rader som proxy för dagar.
    """
    out = {}

    # ===== Hjälpare =====
    def _fmt2(x) -> str:
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "0.00"

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
        # Allt tillbaka som decimala enheter med två decimaler
        hours = sec / 3600.0
        days  = hours / 24.0
        weeks = days / 7.0
        return _fmt2(hours), _fmt2(days), _fmt2(weeks)

    def _covered_days(df: pd.DataFrame) -> int:
        """Antal unika datum i kolumnen 'Datum'. Fallback: antal rader (min 1)."""
        try:
            if df is not None and not df.empty and "Datum" in df.columns:
                d = pd.to_datetime(df["Datum"], errors="coerce").dropna().dt.date
                n = int(d.nunique())
                if n > 0:
                    return n
        except Exception:
            pass
        # Fallback om 'Datum' saknas/inte går att tolka
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
    TID_D_SEK     = _col("Tid D")  # "Tid D (sek)" sparas som "Tid D" i appen
    TPK_SEK       = _col("Tid per kille (sek)")
    HAND_SEK      = _col("Händer per kille (sek)")
    HAK_SEK       = _col("Hångel (sek/kille)")

    HANDER_AKTIV  = _col("Händer aktiv")

    # Fallback "Totalt Män" per rad (om kolumn saknas) – enligt totalsumma i appen
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
    out["Antal GB"]         = _fmt2(cnt_gb)
    out["Privat GB"]        = _fmt2(cnt_privat)
    out["Antal GB vita"]    = _fmt2(cnt_gb_vita)
    out["Antal GB svarta"]  = _fmt2(cnt_gb_svarta)
    out["Antal GB blandat"] = _fmt2(cnt_gb_blandat)

    # ===== Nöjdhet (direkt efter GB blandat) =====
    sum_pappan  = float(P.sum())
    sum_grannar = float(G.sum())
    sum_nv      = float(NV.sum())
    sum_nf      = float(NF.sum())
    sum_sover   = float(SOVER.sum())
    sum_nils    = float(_col("Nils").sum())
    sum_alskar  = float(ALSKAR.sum())

    denom_kanner = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    alskar_snitt_kanner = _div(sum_alskar, denom_kanner)

    def _antal_tillfallen(total, mx):  # summa / max
        return _div(total, mx)

    tillf_pappan  = _antal_tillfallen(sum_pappan,  MAX_PAPPAN)
    tillf_grannar = _antal_tillfallen(sum_grannar, MAX_GRANNAR)
    tillf_nv      = _antal_tillfallen(sum_nv,      MAX_NV)
    tillf_nf      = _antal_tillfallen(sum_nf,      MAX_NF)
    sover_div_max_nf = _div(sum_sover, MAX_NF)

    out["— Nöjdhet —"] = ""
    out[f"Nöjdhet – {LBL_PAPPAN}"]  = _fmt2(alskar_snitt_kanner + tillf_pappan)
    out[f"Nöjdhet – {LBL_GRANNAR}"] = _fmt2(alskar_snitt_kanner + tillf_grannar)
    out[f"Nöjdhet – {LBL_NV}"]      = _fmt2(alskar_snitt_kanner + tillf_nv)
    out[f"Nöjdhet – {LBL_NF}"]      = _fmt2(alskar_snitt_kanner + tillf_nf + sover_div_max_nf)
    out["Nöjdhet – Nils (summa)"]   = _fmt2(sum_nils)

    # ===== Totalt antal män (global totalsumma) =====
    total_man_sum = float((M + S + BD + ES + PD + P + G + NV + NF + BE).sum())
    out["— Totalt —"] = ""
    out["Totalt antal män (alla fält)"] = _fmt2(total_man_sum)

    # Svarta – summa (enligt specialregeln) + andel %
    sum_black = float(S.sum())
    # På rader där S>0 räknas ES och BD som svarta
    mask_rows_black = (S > 0)
    sum_black += float(ES[mask_rows_black].sum())
    sum_black += float(BD[mask_rows_black].sum())

    out["Summa Svarta (inkl. regler)"] = _fmt2(sum_black)
    out["Andel Svarta (%)"] = _fmt2(100.0 * _div(sum_black, total_man_sum))

    # ===== DP / DPP / DAP / TAP =====
    dp_sum  = _sum("DP")
    dpp_sum = _sum("DPP")
    dap_sum = _sum("DAP")
    tap_sum = _sum("TAP")

    # snitt per scen: över rader där Totalt Män > 0
    mask_scen = (TOT_MAN > 0)
    denom_scen = _count_rows(mask_scen)

    for col_name, ssum in [("DP", dp_sum), ("DPP", dpp_sum), ("DAP", dap_sum), ("TAP", tap_sum)]:
        avg = _div(ssum, denom_scen)
        out[f"{col_name} – summa"] = _fmt2(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt2(avg)

    # ===== Älskar / Sover med (separata) =====
    out["Älskar – summa"]     = _fmt2(sum_alskar)
    out["Sover med – summa"]  = _fmt2(sum_sover)

    # ===== Källor – enskilda summor + snitt per scen (fält>0) + 'antal tillfällen' =====
    out["— Källor —"] = ""
    def _sum_snitt_tillfallen(label: str, ser: pd.Series, maxv: float):
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt2(ssum)
        out[f"{label} – snitt per scen"] = _fmt2(avg)
        out[f"{label} – antal tillfällen"] = _fmt2(_div(ssum, maxv))  # "summa / max"

    _sum_snitt_tillfallen("Bonus deltagit",     BD, 1.0)
    _sum_snitt_tillfallen("Personal deltagit",  PD, 1.0)
    _sum_snitt_tillfallen(LBL_PAPPAN,           P,  MAX_PAPPAN)
    _sum_snitt_tillfallen(LBL_GRANNAR,          G,  MAX_GRANNAR)
    _sum_snitt_tillfallen(LBL_NV,               NV, MAX_NV)
    _sum_snitt_tillfallen(LBL_NF,               NF, MAX_NF)
    _sum_snitt_tillfallen(LBL_BEK,              BE, 1.0)
    _sum_snitt_tillfallen(LBL_ESK,              ES, 1.0)

    # Summan av MAX (känner-fälten)
    out["Summa MAX (källor, inställningar)"] = _fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ===== Händer – antal & % =====
    total_rows = int(len(rows_df)) if rows_df is not None else 0
    aktiva  = _count_rows(HANDER_AKTIV > 0)
    inakt   = _count_rows(HANDER_AKTIV <= 0)
    out["— Händer —"] = ""
    out["Händer aktiva (antal)"]   = _fmt2(aktiva)
    out["Händer aktiva (%)"]       = _fmt2(100.0 * _div(aktiva, total_rows))
    out["Händer inaktiva (antal)"] = _fmt2(inakt)
    out["Händer inaktiva (%)"]     = _fmt2(100.0 * _div(inakt, total_rows))

    # ===== Tidssummor – Summa tid sek + Tid D + Tid per kille =====
    sum_tid_sec  = float(SUMMA_TID_SEK.sum())
    sum_tidD_sec = float(TID_D_SEK.sum())
    sum_tpk_sec  = float(TPK_SEK.sum())

    out["— Tider —"] = ""
    h, d, w = _sec_to_hours_days_weeks(sum_tid_sec)
    out["Summa tid (sek) – timmar"] = h
    out["Summa tid (sek) – dagar"]  = d
    out["Summa tid (sek) – veckor"] = w

    h, d, w = _sec_to_hours_days_weeks(sum_tidD_sec)
    out["Summa D (sek) – timmar"] = h
    out["Summa D (sek) – dagar"]  = d
    out["Summa D (sek) – veckor"] = w

    h, d, w = _sec_to_hours_days_weeks(sum_tpk_sec)
    out["Summa TP (sek) – timmar"] = h
    out["Summa TP (sek) – dagar"]  = d
    out["Summa TP (sek) – veckor"] = w

    # ===== Snitt-sektion =====
    out["— Snitt —"] = ""
    # Snitt GB = (sum Totalt män på rader med Män>0) / antal GB
    sum_tot_man_gb = float(TOT_MAN[M > 0].sum())
    denom_gb = _count_rows(M > 0)
    out["Snitt GB (Totalt män / antal GB)"] = _fmt2(_div(sum_tot_man_gb, denom_gb))

    # Snitt Privat GB = (sum Totalt män där privatmask) / antal Privat GB
    sum_tot_man_privat = float(TOT_MAN[mask_privat].sum())
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt2(_div(sum_tot_man_privat, cnt_privat))

    # Snitt tid GB/Privat GB (h)
    mean_tid_gb_h   = _div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if denom_gb>0 else 0.0
    mean_tid_priv_h = _div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if cnt_privat>0 else 0.0
    out["Snitt tid GB (h)"]       = _fmt2(mean_tid_gb_h)
    out["Snitt tid Privat GB (h)"] = _fmt2(mean_tid_priv_h)

    # Tid per kille snitt – ex händer / inkl händer (sek)
    avg_tpk_ex = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    tpk_incl_series = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_series.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"]   = _fmt2(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"] = _fmt2(avg_tpk_incl)

    # Genomsnitt hångel (sek/kille)
    out["Snitt Hångel (sek/kille)"] = _fmt2(float(HAK_SEK.mean()) if total_rows>0 else 0.0)

    # Älskar snitt känner & sover/max
    out["Älskar snitt känner"]              = _fmt2(alskar_snitt_kanner)
    out["Sover med / MAX (Nils familj)"]    = _fmt2(sover_div_max_nf)

    # ===== Ekonomi =====
    PREN = _col("Prenumeranter")
    INT  = _col("Intäkter")
    KM   = _col("Kostnad män")
    IK   = _col("Intäkt Känner")
    IF   = _col("Intäkt företag")
    LM   = _col("Lön Malin")
    V    = _col("Vinst")

    pren_sum = float(PREN.sum())
    int_sum  = float(INT.sum())
    km_sum   = float(KM.sum())
    ik_sum   = float(IK.sum())
    if_sum   = float(IF.sum())
    lm_sum   = float(LM.sum())
    v_sum    = float(V.sum())

    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt2(pren_sum)
    out["Intäkter – summa"]      = _fmt2(int_sum)
    out["Kostnad män – summa"]   = _fmt2(km_sum)
    out["Intäkt Känner – summa"] = _fmt2(ik_sum)
    out["Intäkt företag – summa"]= _fmt2(if_sum)
    out["Lön Malin – summa"]     = _fmt2(lm_sum)
    out["Vinst – summa"]         = _fmt2(v_sum)

    # Snitt på Lön Malin – tre varianter
    out["Lön Malin / Per scen"]               = _fmt2(_div(lm_sum, denom_gb))
    out["Lön Malin / Totalt antal män"]       = _fmt2(_div(lm_sum, total_man_sum))
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"] = _fmt2(_div(lm_sum, total_tillfallen))

    # ===== NYTT: Prognos 365 dagar =====
    days = _covered_days(rows_df)
    factor_365 = 365.0 / float(days) if days > 0 else 0.0

    scenes_total = float(total_rows)
    scenes_per_day = _div(scenes_total, days)
    scenes_365 = scenes_per_day * 365.0

    out["— Prognos 365 dagar —"] = ""
    out["Täckta dagar (data)"]     = _fmt2(days)
    out["Scener per dag (est)"]    = _fmt2(scenes_per_day)
    out["Scener – 365 dagar (est)"] = _fmt2(scenes_365)

    # Räknas upp som SUMMOR * faktor
    out["Totalt antal män – 365d"]             = _fmt2(total_man_sum * factor_365)
    out["Summa Svarta (inkl. regler) – 365d"]  = _fmt2(sum_black * factor_365)

    out["DP – summa (365d)"]   = _fmt2(dp_sum * factor_365)
    out["DPP – summa (365d)"]  = _fmt2(dpp_sum * factor_365)
    out["DAP – summa (365d)"]  = _fmt2(dap_sum * factor_365)
    out["TAP – summa (365d)"]  = _fmt2(tap_sum * factor_365)

    out["Älskar – summa (365d)"]    = _fmt2(sum_alskar * factor_365)
    out["Sover med – summa (365d)"] = _fmt2(sum_sover * factor_365)

    out[f"{LBL_PAPPAN} – summa (365d)"]  = _fmt2(sum_pappan * factor_365)
    out[f"{LBL_GRANNAR} – summa (365d)"] = _fmt2(sum_grannar * factor_365)
    out[f"{LBL_NV} – summa (365d)"]      = _fmt2(sum_nv * factor_365)
    out[f"{LBL_NF} – summa (365d)"]      = _fmt2(sum_nf * factor_365)
    out["Bonus deltagit – summa (365d)"]     = _fmt2(float(BD.sum()) * factor_365)
    out["Personal deltagit – summa (365d)"]  = _fmt2(float(PD.sum()) * factor_365)
    out[f"{LBL_BEK} – summa (365d)"]         = _fmt2(float(BE.sum()) * factor_365)
    out[f"{LBL_ESK} – summa (365d)"]         = _fmt2(float(ES.sum()) * factor_365)

    # Tider – prognos 365d (visas i timmar/dagar/veckor)
    h, d, w = _sec_to_hours_days_weeks(sum_tid_sec * factor_365)
    out["Summa tid (sek) – timmar (365d)"]  = h
    out["Summa tid (sek) – dagar (365d)"]   = d
    out["Summa tid (sek) – veckor (365d)"]  = w

    h, d, w = _sec_to_hours_days_weeks(sum_tidD_sec * factor_365)
    out["Summa D (sek) – timmar (365d)"]    = h
    out["Summa D (sek) – dagar (365d)"]     = d
    out["Summa D (sek) – veckor (365d)"]    = w

    h, d, w = _sec_to_hours_days_weeks(sum_tpk_sec * factor_365)
    out["Summa TP (sek) – timmar (365d)"]   = h
    out["Summa TP (sek) – dagar (365d)"]    = d
    out["Summa TP (sek) – veckor (365d)"]   = w

    # Ekonomi – prognos 365d
    out["Prenumeranter – summa (365d)"] = _fmt2(pren_sum * factor_365)
    out["Intäkter – summa (365d)"]      = _fmt2(int_sum * factor_365)
    out["Kostnad män – summa (365d)"]   = _fmt2(km_sum * factor_365)
    out["Intäkt Känner – summa (365d)"] = _fmt2(ik_sum * factor_365)
    out["Intäkt företag – summa (365d)"]= _fmt2(if_sum * factor_365)
    out["Lön Malin – summa (365d)"]     = _fmt2(lm_sum * factor_365)
    out["Vinst – summa (365d)"]         = _fmt2(v_sum * factor_365)

    # Händer – prognos 365d (antal scenhändelser)
    out["Händer aktiva (antal, 365d)"]   = _fmt2(_div(aktiva, days) * 365.0)
    out["Händer inaktiva (antal, 365d)"] = _fmt2(_div(inakt,  days) * 365.0)

    # GB-antal – prognos 365d
    out["Antal GB (365d)"]         = _fmt2(_div(cnt_gb, days) * 365.0)
    out["Privat GB (365d)"]        = _fmt2(_div(cnt_privat, days) * 365.0)
    out["Antal GB vita (365d)"]    = _fmt2(_div(cnt_gb_vita, days) * 365.0)
    out["Antal GB svarta (365d)"]  = _fmt2(_div(cnt_gb_svarta, days) * 365.0)
    out["Antal GB blandat (365d)"] = _fmt2(_div(cnt_gb_blandat, days) * 365.0)

    return out
