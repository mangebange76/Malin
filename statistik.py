# statistik.py — lägger till "Dagar i databasen (från startdatum)" under Privat GB

from datetime import date
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
            # svensk gruppvisning med mellanrum + komma
            v = float(x)
            s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
            return s
        except Exception:
            return "0,00"

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
        return _fmt2(hours), _fmt2(days), _fmt2(weeks)

    # Dynamiska etiketter
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

    # ===== Utgångskolumner =====
    M  = _col("Män"); S = _col("Svarta")
    BD = _col("Bonus deltagit"); PD = _col("Personal deltagit")
    P  = _col(LBL_PAPPAN); G = _col(LBL_GRANNAR); NV = _col(LBL_NV); NF = _col(LBL_NF)
    BE = _col(LBL_BEK); ES = _col(LBL_ESK)

    ALSKAR = _col("Älskar"); SOVER = _col("Sover med")

    SUMMA_TID_SEK = _col("Summa tid (sek)")
    TID_D_SEK     = _col("Tid D")  # i appen sparas "Tid D (sek)" som "Tid D"
    TPK_SEK       = _col("Tid per kille (sek)")
    HAND_SEK      = _col("Händer per kille (sek)")
    HAK_SEK       = _col("Hångel (sek/kille)")

    HANDER_AKTIV  = _col("Händer aktiv")

    if "Totalt Män" in (rows_df.columns if rows_df is not None else []):
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

    out["— Översikt —"] = ""
    out["Antal rader"] = _fmt2(len(rows_df) if rows_df is not None else 0)
    out["Totalt antal män (alla fält)"] = _fmt2(float((M + S + BD + ES + PD + P + G + NV + NF + BE).sum()))

    out["— GB —"] = ""
    out["Antal GB"]         = _fmt2(cnt_gb)
    out["Privat GB"]        = _fmt2(cnt_privat)

    # >>> NYTT: dagar i databasen direkt under "Privat GB"
    try:
        start = cfg.get("startdatum")
        if isinstance(start, str) and start:
            start = pd.to_datetime(start).date()
        days_passed = (date.today() - start).days if start else 0
        days_passed = max(0, int(days_passed))
    except Exception:
        days_passed = 0
    out["Dagar i databasen (från startdatum)"] = f"{days_passed}"

    out["Antal GB vita"]    = _fmt2(cnt_gb_vita)
    out["Antal GB svarta"]  = _fmt2(cnt_gb_svarta)
    out["Antal GB blandat"] = _fmt2(cnt_gb_blandat)

    # ===== Nöjdhet (efter GB) =====
    sum_pappan  = float(P.sum()); sum_grannar = float(G.sum())
    sum_nv      = float(NV.sum()); sum_nf      = float(NF.sum())
    sum_sover   = float(SOVER.sum()); sum_nils = float(_col("Nils").sum())
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

    # ===== Totalt antal män (global totalsumma) =====
    total_man_sum = float((M + S + BD + ES + PD + P + G + NV + NF + BE).sum())
    out["— Totalt —"] = ""
    out["Totalt antal män (alla fält)"] = _fmt2(total_man_sum)

    # Svarta – summa + andel
    sum_black = float(S.sum())
    mask_rows_black = (S > 0)
    sum_black += float(ES[mask_rows_black].sum())
    sum_black += float(BD[mask_rows_black].sum())
    out["Summa Svarta (inkl. regler)"] = _fmt2(sum_black)
    out["Andel Svarta (%)"] = _fmt2(100.0 * _div(sum_black, total_man_sum))

    # ===== DP / DPP / DAP / TAP =====
    for col_name in ["DP", "DPP", "DAP", "TAP"]:
        ssum = _sum(col_name)
        mask_scen = (TOT_MAN > 0)
        denom = _count_rows(mask_scen)
        avg   = _div(ssum, denom)
        out[f"{col_name} – summa"] = _fmt2(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt2(avg)

    # ===== Älskar / Sover med =====
    out["Älskar – summa"]    = _fmt2(float(ALSKAR.sum()))
    out["Sover med – summa"] = _fmt2(float(SOVER.sum()))

    # ===== Källor =====
    out["— Källor —"] = ""
    def _sum_snitt_tillfallen(label: str, ser: pd.Series, maxv: float):
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt2(ssum)
        out[f"{label} – snitt per scen"] = _fmt2(avg)
        out[f"{label} – antal tillfällen (summa/max)"] = _fmt2(_div(ssum, maxv) if maxv else 0.0)

    _sum_snitt_tillfallen("Bonus deltagit", BD, 1.0)
    _sum_snitt_tillfallen("Personal deltagit", PD, float(cfg.get("MAX_BEKANTA", 1)) or 1.0)  # eller 1.0 om du vill låsa
    _sum_snitt_tillfallen(LBL_PAPPAN,  P,  MAX_PAPPAN)
    _sum_snitt_tillfallen(LBL_GRANNAR, G,  MAX_GRANNAR)
    _sum_snitt_tillfallen(LBL_NV,      NV, MAX_NV)
    _sum_snitt_tillfallen(LBL_NF,      NF, MAX_NF)
    _sum_snitt_tillfallen(LBL_BEK,     BE, float(cfg.get("MAX_BEKANTA", 1)) or 1.0)
    _sum_snitt_tillfallen(LBL_ESK,     ES, 1.0)

    out["Summa MAX (källor, inställningar)"] = _fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ===== Händer =====
    total_rows = int(len(rows_df)) if rows_df is not None else 0
    aktiva  = _count_rows(HANDER_AKTIV > 0)
    inakt   = _count_rows(HANDER_AKTIV <= 0)
    out["— Händer —"] = ""
    out["Händer aktiva (antal)"]   = _fmt2(aktiva)
    out["Händer aktiva (%)"]       = _fmt2(100.0 * _div(aktiva, total_rows))
    out["Händer inaktiva (antal)"] = _fmt2(inakt)
    out["Händer inaktiva (%)"]     = _fmt2(100.0 * _div(inakt, total_rows))

    # ===== Tider =====
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

    # ===== Snitt =====
    out["— Snitt —"] = ""
    sum_tot_man_gb = float(TOT_MAN[ M > 0 ].sum())
    denom_gb = _count_rows(M > 0)
    out["Snitt GB (Totalt män / antal GB)"] = _fmt2(_div(sum_tot_man_gb, denom_gb))

    sum_tot_man_privat = float(TOT_MAN[mask_privat].sum())
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt2(_div(sum_tot_man_privat, cnt_privat))

    mean_tid_gb_h = _div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if denom_gb>0 else 0.0
    mean_tid_priv_h = _div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if cnt_privat>0 else 0.0
    out["Snitt tid GB (h)"] = _fmt2(mean_tid_gb_h)
    out["Snitt tid Privat GB (h)"] = _fmt2(mean_tid_priv_h)

    avg_tpk_ex = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    tpk_incl_series = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_series.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"] = _fmt2(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"] = _fmt2(avg_tpk_incl)

    out["Snitt Hångel (sek/kille)"] = _fmt2(float(HAK_SEK.mean()) if total_rows>0 else 0.0)

    # ===== Ekonomi =====
    PREN = _col("Prenumeranter"); INT = _col("Intäkter")
    KM   = _col("Kostnad män");   IK  = _col("Intäkt Känner")
    IF   = _col("Intäkt företag"); LM  = _col("Lön Malin"); V = _col("Vinst")

    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt2(float(PREN.sum()))
    out["Intäkter – summa"]      = _fmt2(float(INT.sum()))
    out["Kostnad män – summa"]   = _fmt2(float(KM.sum()))
    out["Intäkt Känner – summa"] = _fmt2(float(IK.sum()))
    out["Intäkt företag – summa"]= _fmt2(float(IF.sum()))
    out["Lön Malin – summa"]     = _fmt2(float(LM.sum()))
    out["Vinst – summa"]         = _fmt2(float(V.sum()))

    out["Lön Malin / Per scen"] = _fmt2(_div(float(LM.sum()), denom_gb))
    out["Lön Malin / Totalt antal män"] = _fmt2(_div(float(LM.sum()), float((M + S + BD + ES + PD + P + G + NV + NF + BE).sum())))
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"] = _fmt2(_div(float(LM.sum()), total_tillfallen))

    return out
