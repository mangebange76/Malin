# statistik.py
import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Returnerar en dict {etikett: värde(str)} för visning i appen.
    Allt numeriskt formatteras med 2 decimaler. Tider summeras i sekunder
    och visas som timmar/dagar/veckor (decimalt).
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

    # Fallback "Totalt Män" per rad (om kolumn saknas) – enligt överenskommen totalsumma
    if "Totalt Män" in rows_df.columns:
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
    for col_name in ["DP", "DPP", "DAP", "TAP"]:
        ssum = _sum(col_name)
        # snitt per scen: över rader där Totalt Män > 0
        mask_scen = (TOT_MAN > 0)
        denom = _count_rows(mask_scen)
        avg   = _div(ssum, denom)
        out[f"{col_name} – summa"] = _fmt2(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt2(avg)

    # ===== Älskar / Sover med (separata) =====
    out["Älskar – summa"]   = _fmt2(float(ALSKAR.sum()))
    out["Sover med – summa"] = _fmt2(float(SOVER.sum()))

    # ===== Källor – enskilda summor + snitt per scen (fält>0) + 'antal tillfällen' (summa/max) =====
    out["— Källor —"] = ""
    def _sum_snitt_tillfallen(label: str, ser: pd.Series, maxv: float):
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt2(ssum)
        out[f"{label} – snitt per scen"] = _fmt2(avg)
        out[f"{label} – antal tillfällen"] = _fmt2(_div(ssum, maxv))  # "summa / max" enligt din senaste nomenklatur

    _sum_snitt_tillfallen("Bonus deltagit", BD, 1.0)  # här är "max" ej relevant – lämnas 1.0 så att värdet blir ssum
    _sum_snitt_tillfallen("Personal deltagit", PD, 1.0)
    _sum_snitt_tillfallen(LBL_PAPPAN,  P,  MAX_PAPPAN)
    _sum_snitt_tillfallen(LBL_GRANNAR, G,  MAX_GRANNAR)
    _sum_snitt_tillfallen(LBL_NV,      NV, MAX_NV)
    _sum_snitt_tillfallen(LBL_NF,      NF, MAX_NF)
    _sum_snitt_tillfallen(LBL_BEK,     BE, 1.0)
    _sum_snitt_tillfallen(LBL_ESK,     ES, 1.0)

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
    sum_tid_sec = float(SUMMA_TID_SEK.sum())
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
    # Snitt GB = (sum Totalt män på rader med Män>0) / antal GB (def. för GB enligt överenskommelse: Män>0)
    sum_tot_man_gb = float(TOT_MAN[ M > 0 ].sum())
    denom_gb = _count_rows(M > 0)
    out["Snitt GB (Totalt män / antal GB)"] = _fmt2(_div(sum_tot_man_gb, denom_gb))

    # Snitt Privat GB = (sum Totalt män där Män==0 & privatmask) / antal Privat GB
    sum_tot_man_privat = float(TOT_MAN[mask_privat].sum())
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt2(_div(sum_tot_man_privat, cnt_privat))

    # Snitt tid GB/Privat GB (h) – baserat på Summa tid (sek) på respektive rader
    mean_tid_gb_h = _div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if denom_gb>0 else 0.0
    mean_tid_priv_h = _div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if cnt_privat>0 else 0.0
    out["Snitt tid GB (h)"] = _fmt2(mean_tid_gb_h)
    out["Snitt tid Privat GB (h)"] = _fmt2(mean_tid_priv_h)

    # Tid per kille snitt – ex händer / inkl händer (sek)
    avg_tpk_ex = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    # inkl händer: per rad (TPK + Händer/kille när Händer aktiv==1), snitt över rader
    tpk_incl_series = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_series.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"] = _fmt2(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"] = _fmt2(avg_tpk_incl)

    # Genomsnitt hångel (sek/kille)
    out["Snitt Hångel (sek/kille)"] = _fmt2(float(HAK_SEK.mean()) if total_rows>0 else 0.0)

    # Älskar snitt känner = sum(Älskar) / (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)
    out["Älskar snitt känner"] = _fmt2(alskar_snitt_kanner)

    # Sover med – snitt mot MAX (Nils familj)
    out["Sover med / MAX (Nils familj)"] = _fmt2(sover_div_max_nf)

    # ===== Ekonomi =====
    PREN = _col("Prenumeranter")
    INT  = _col("Intäkter")
    KM   = _col("Kostnad män")
    IK   = _col("Intäkt Känner")
    IF   = _col("Intäkt företag")
    LM   = _col("Lön Malin")
    V    = _col("Vinst")

    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt2(float(PREN.sum()))
    out["Intäkter – summa"]      = _fmt2(float(INT.sum()))
    out["Kostnad män – summa"]   = _fmt2(float(KM.sum()))
    out["Intäkt Känner – summa"] = _fmt2(float(IK.sum()))
    out["Intäkt företag – summa"]= _fmt2(float(IF.sum()))
    out["Lön Malin – summa"]     = _fmt2(float(LM.sum()))
    out["Vinst – summa"]         = _fmt2(float(V.sum()))

    # Snitt på Lön Malin – tre varianter
    # 1) Per scen (Lön / antal rader där Män>0)
    out["Lön Malin / Per scen"] = _fmt2(_div(float(LM.sum()), denom_gb))

    # 2) / totalt antal män (global totalsumma)
    out["Lön Malin / Totalt antal män"] = _fmt2(_div(float(LM.sum()), total_man_sum))

    # 3) / totalt antal tillfällen = summan av
    # (män+svarta+älskar+sover med+bonus deltagit+personal deltagit+pappans vänner+grannar+nils vänner+nils familj+bekanta+eskilstuna killar)
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"] = _fmt2(_div(float(LM.sum()), total_tillfallen))

    return out
