# statistik.py — version 250823-2 + prognos för super-bonus
import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Returnerar en dict {etikett: värde(str)} för visning i appen.
    Innehåller vanlig statistik + prognos för 365 dagar baserad på
    snitt per rad i nuvarande data (”som om man fyllde databasen med
    samma rader i 365 dagar”).
    """

    out = {}

    # ======= Hjälpare (svensk formatering) =======
    def _fmt_sv(x, decimals=2) -> str:
        try:
            n = float(x)
        except Exception:
            return "0,00" if decimals == 2 else "0"
        s = f"{n:,.{decimals}f}"
        # USA-format -> svenskt: mellanslag som tusensep, komma som decimal
        return s.replace(",", "X").replace(".", ",").replace("X", " ")

    def _fmt2(x) -> str:
        return _fmt_sv(x, 2)

    def _fmt0(x) -> str:
        return _fmt_sv(x, 0)

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
        b2 = float(b)
        return float(a) / b2 if b2 != 0.0 else 0.0

    def _sec_to_hours_days_weeks(sec: float):
        hours = sec / 3600.0
        days  = hours / 24.0
        weeks = days / 7.0
        return _fmt2(hours), _fmt2(days), _fmt2(weeks)

    # ======= Dynamiska etiketter + max =======
    LBL_PAPPAN   = cfg.get("LBL_PAPPAN", "Pappans vänner")
    LBL_GRANNAR  = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV       = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    LBL_NF       = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    LBL_BEK      = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK      = cfg.get("LBL_ESK", "Eskilstuna killar")

    MAX_PAPPAN   = float(cfg.get("MAX_PAPPAN", 0) or 0)
    MAX_GRANNAR  = float(cfg.get("MAX_GRANNAR", 0) or 0)
    MAX_NV       = float(cfg.get("MAX_NILS_VANNER", 0) or 0)
    MAX_NF       = float(cfg.get("MAX_NILS_FAMILJ", 0) or 0)

    # ======= Kolumner =======
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

    # Ekonomi
    PREN = _col("Prenumeranter")
    INT  = _col("Intäkter")
    KM   = _col("Kostnad män")
    IK   = _col("Intäkt Känner")
    IFK  = _col("Intäkt företag")
    LM   = _col("Lön Malin")
    V    = _col("Vinst")

    # Fallback "Totalt Män"
    if rows_df is not None and not rows_df.empty and "Totalt Män" in rows_df.columns:
        TOT_MAN = _col("Totalt Män")
    else:
        TOT_MAN = (M + S + BD + ES + PD + P + G + NV + NF + BE)

    total_rows = int(len(rows_df)) if rows_df is not None else 0

    # ======= GB/Privat-masker =======
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
    out["Antal GB"]         = _fmt0(cnt_gb)
    out["Privat GB"]        = _fmt0(cnt_privat)
    out["Antal GB vita"]    = _fmt0(cnt_gb_vita)
    out["Antal GB svarta"]  = _fmt0(cnt_gb_svarta)
    out["Antal GB blandat"] = _fmt0(cnt_gb_blandat)

    # ======= Nöjdhet =======
    sum_pappan  = float(P.sum())
    sum_grannar = float(G.sum())
    sum_nv      = float(NV.sum())
    sum_nf      = float(NF.sum())
    sum_sover   = float(SOVER.sum())
    sum_nils    = float(_col("Nils").sum())
    sum_alskar  = float(ALSKAR.sum())

    denom_kanner = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    alskar_snitt_kanner = _div(sum_alskar, denom_kanner)

    def _antal_tillfallen(total, mx):
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

    # ======= Totalt & Svarta (regler) =======
    total_man_sum = float(TOT_MAN.sum())
    out["— Totalt —"] = ""
    out["Totalt antal män (alla fält)"] = _fmt2(total_man_sum)

    # Svarta inklusive regel: på rader där S>0 räknas ES och BD som svarta
    row_black = S + ES.where(S > 0, 0) + BD.where(S > 0, 0)
    sum_black = float(row_black.sum())
    out["Summa Svarta (inkl. regler)"] = _fmt2(sum_black)
    out["Andel Svarta (%)"] = _fmt2(100.0 * _div(sum_black, total_man_sum))

    # ======= DP/DPP/DAP/TAP – summa + snitt per scen (där TOT_MAN>0) =======
    mask_scen = (TOT_MAN > 0)
    denom_scen = _count_rows(mask_scen)

    for col_name in ["DP", "DPP", "DAP", "TAP"]:
        ssum = _sum(col_name)
        avg  = _div(ssum, denom_scen)
        out[f"{col_name} – summa"] = _fmt2(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt2(avg)

    # ======= Älskar / Sover med =======
    out["Älskar – summa"]    = _fmt2(sum_alskar)
    out["Sover med – summa"] = _fmt2(sum_sover)

    # ======= Källor – summa / snitt / tillfällen =======
    out["— Källor —"] = ""
    def _sum_snitt_tillfallen(label: str, ser: pd.Series, maxv: float):
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt2(ssum)
        out[f"{label} – snitt per scen"] = _fmt2(avg)
        out[f"{label} – antal tillfällen"] = _fmt2(_div(ssum, maxv))

    _sum_snitt_tillfallen("Bonus deltagit", BD, 1.0)
    _sum_snitt_tillfallen("Personal deltagit", PD, 1.0)
    _sum_snitt_tillfallen(LBL_PAPPAN,  P,  MAX_PAPPAN)
    _sum_snitt_tillfallen(LBL_GRANNAR, G,  MAX_GRANNAR)
    _sum_snitt_tillfallen(LBL_NV,      NV, MAX_NV)
    _sum_snitt_tillfallen(LBL_NF,      NF, MAX_NF)
    _sum_snitt_tillfallen(LBL_BEK,     BE, 1.0)
    _sum_snitt_tillfallen(LBL_ESK,     ES, 1.0)

    out["Summa MAX (källor, inställningar)"] = _fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ======= Händer =======
    aktiva = _count_rows(HANDER_AKTIV > 0)
    inakt  = _count_rows(HANDER_AKTIV <= 0)
    out["— Händer —"] = ""
    out["Händer aktiva (antal)"]   = _fmt0(aktiva)
    out["Händer aktiva (%)"]       = _fmt2(100.0 * _div(aktiva, total_rows))
    out["Händer inaktiva (antal)"] = _fmt0(inakt)
    out["Händer inaktiva (%)"]     = _fmt2(100.0 * _div(inakt, total_rows))

    # ======= Tider =======
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

    # ======= Snitt =======
    out["— Snitt —"] = ""
    sum_tot_man_gb = float(TOT_MAN[M > 0].sum())
    denom_gb = _count_rows(M > 0)
    out["Snitt GB (Totalt män / antal GB)"] = _fmt2(_div(sum_tot_man_gb, denom_gb))

    sum_tot_man_privat = float(TOT_MAN[mask_privat].sum())
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt2(_div(sum_tot_man_privat, cnt_privat))

    mean_tid_gb_h   = _div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if denom_gb>0 else 0.0
    mean_tid_priv_h = _div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if cnt_privat>0 else 0.0
    out["Snitt tid GB (h)"]       = _fmt2(mean_tid_gb_h)
    out["Snitt tid Privat GB (h)"] = _fmt2(mean_tid_priv_h)

    avg_tpk_ex   = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    tpk_incl_ser = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_ser.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"]   = _fmt2(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"] = _fmt2(avg_tpk_incl)

    out["Snitt Hångel (sek/kille)"] = _fmt2(float(HAK_SEK.mean()) if total_rows>0 else 0.0)
    out["Älskar snitt känner"]      = _fmt2(alskar_snitt_kanner)
    out["Sover med / MAX (Nils familj)"] = _fmt2(sover_div_max_nf)

    # ======= Ekonomi =======
    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt2(float(PREN.sum()))
    out["Intäkter – summa"]      = _fmt2(float(INT.sum()))
    out["Kostnad män – summa"]   = _fmt2(float(KM.sum()))
    out["Intäkt Känner – summa"] = _fmt2(float(IK.sum()))
    out["Intäkt företag – summa"]= _fmt2(float(IFK.sum()))
    out["Lön Malin – summa"]     = _fmt2(float(LM.sum()))
    out["Vinst – summa"]         = _fmt2(float(V.sum()))

    out["Lön Malin / Per scen"]             = _fmt2(_div(float(LM.sum()), denom_scen))
    out["Lön Malin / Totalt antal män"]     = _fmt2(_div(float(LM.sum()), total_man_sum))
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"] = _fmt2(_div(float(LM.sum()), total_tillfallen))

    # Vännerna (Känner) tjänar = (Intäkt Känner + Vinst – summa) / (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + BEKANTA)
    denom_kar = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + float(BE.sum()*0) + 0  # BEKANTA ingår som ”antal”; inget max => använd 1.0 i divisor?
    # Tolkning: ”/ (max värden för pappans vänner+grannar+nils vänner+nils familj+bekanta)”
    # Bekanta saknar max i cfg -> behandla som 1 för att inte sänka kvoten; alternativt utesluta. Vi utesluter i max-summan:
    denom_kar = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    vanner_tjanar = _div(float(IK.sum()) + float(V.sum()), denom_kar)
    out["Vännerna (Känner) tjänar"] = _fmt2(vanner_tjanar)

    # ======= PROGNOS — 365 dagar =======
    out["— Prognos — 365 dagar"] = ""

    def _forecast_sum(series: pd.Series) -> float:
        if total_rows <= 0:
            return 0.0
        return float(series.mean()) * 365.0

    # Totalt antal män – 365d
    out["Totalt antal män – 365d"] = _fmt2(_forecast_sum(TOT_MAN))

    # Summa Svarta inkl regler – 365d
    forecast_black = _forecast_sum(row_black)
    out["Summa Svarta (inkl. regler) – 365d"] = _fmt2(forecast_black)
    out["Andel Svarta (%) – 365d"] = _fmt2(100.0 * _div(forecast_black, _forecast_sum(TOT_MAN)))

    # >>> Super-bonus ack (365d) – placeras direkt under ”Summa Svarta (inkl. regler)”
    sb_pct = float(cfg.get("SUPER_BONUS_PCT", 0.1) or 0.1) / 100.0
    # I appen: per rad int(pren * sb_pct). Vi approximerar med golv per rad:
    per_row_sb = (PREN * sb_pct).apply(lambda x: float(int(x)))
    forecast_sb = _forecast_sum(per_row_sb)
    out["Super-bonus ack (365d)"] = _fmt0(forecast_sb)

    # Älskar / Sover med – 365d + snittmått
    out["Älskar – summa (365d)"] = _fmt2(_forecast_sum(ALSKAR))
    out["Snitt älskar (Älskar snitt känner)"] = _fmt2(alskar_snitt_kanner)

    out["Sover med – summa (365d)"] = _fmt2(_forecast_sum(SOVER))
    out["Snitt sover med (Sover med / MAX (Nils familj))"] = _fmt2(sover_div_max_nf)

    # Källor – 365d (summa + snitt per scen)
    def _forecast_block(label: str, ser: pd.Series, maxv: float):
        out[f"{label} – summa (365d)"] = _fmt2(_forecast_sum(ser))
        cnt = _count_rows(ser > 0)
        avg = _div(float(ser.sum()), cnt)
        out[f"{label} – snitt per scen"] = _fmt2(avg)

    _forecast_block(LBL_PAPPAN,  P,  MAX_PAPPAN)
    _forecast_block(LBL_GRANNAR, G,  MAX_GRANNAR)
    _forecast_block(LBL_NV,      NV, MAX_NV)
    _forecast_block(LBL_NF,      NF, MAX_NF)

    _forecast_block("Bonus deltagit",    BD, 1.0)
    _forecast_block("Personal deltagit", PD, 1.0)
    _forecast_block(LBL_BEK, BE, 1.0)

    out[f"{LBL_ESK} – summa (365d)"] = _fmt2(_forecast_sum(ES))

    # Ekonomi – 365d
    out["Prenumeranter – summa (365d)"] = _fmt2(_forecast_sum(PREN))
    out["Intäkter – summa (365d)"]      = _fmt2(_forecast_sum(INT))
    out["Kostnad män – summa (365d)"]   = _fmt2(_forecast_sum(KM))
    out["Intäkt Känner – summa (365d)"] = _fmt2(_forecast_sum(IK))
    out["Intäkt företag – summa (365d)"]= _fmt2(_forecast_sum(IFK))
    out["Lön Malin – summa (365d)"]     = _fmt2(_forecast_sum(LM))
    out["Vinst – summa (365d)"]         = _fmt2(_forecast_sum(V))

    # Vännerna (Känner) tjänar – 365d (estimat)
    vanner_tjanar_365 = _div(_forecast_sum(IK) + _forecast_sum(V), denom_kar)
    out["Vännerna (Känner) tjänar – (365d)"] = _fmt2(vanner_tjanar_365)

    # Prognos: Nöjdhet + snitt per vecka (inkl. Nils)
    out["— Prognos Nöjdhet — 365 dagar"] = ""
    out[f"Nöjdhet – {LBL_PAPPAN} (vecko-snitt)"]  = _fmt2((alskar_snitt_kanner + tillf_pappan) / 7.0)
    out[f"Nöjdhet – {LBL_GRANNAR} (vecko-snitt)"] = _fmt2((alskar_snitt_kanner + tillf_grannar) / 7.0)
    out[f"Nöjdhet – {LBL_NV} (vecko-snitt)"]      = _fmt2((alskar_snitt_kanner + tillf_nv) / 7.0)
    out[f"Nöjdhet – {LBL_NF} (vecko-snitt)"]      = _fmt2((alskar_snitt_kanner + tillf_nf + sover_div_max_nf) / 7.0)
    # Nils nöjdhet behandlas som summa -> veckosnitt = (sum_nils / 365) * 7
    nils_veckosnitt = _div(sum_nils, 365.0) * 7.0 if total_rows>0 else 0.0
    out["Nöjdhet – Nils (vecko-snitt)"] = _fmt2(nils_veckosnitt)

    # Antal GB/Privat/typer – 365d
    out["Antal GB (365d)"]         = _fmt2(_forecast_sum(mask_gb.astype(float)))
    out["Privat GB (365d)"]        = _fmt2(_forecast_sum(mask_privat.astype(float)))
    out["Antal GB vita (365d)"]    = _fmt2(_forecast_sum(mask_gb_vita.astype(float)))
    out["Antal GB svarta (365d)"]  = _fmt2(_forecast_sum(mask_gb_svarta.astype(float)))
    out["Antal GB blandat (365d)"] = _fmt2(_forecast_sum(mask_gb_blandat.astype(float)))

    return out
