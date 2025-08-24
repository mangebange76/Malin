# statistik.py – version 250823-2 (cfg-driven ekonomi + prognoser + svensk formatering)
# Etiketter uppdaterade för att tydligt markera prognoser.

import pandas as pd
from datetime import date, datetime

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Returnerar en dict {etikett: värde(str)} för visning i appen.

    - Vanlig statistik: summerar värden som finns i raderna (bakåtkomp).
    - Ekonomi/prognoser: använder aktuella parametrar i cfg när det behövs.
    - Allt numeriskt formateras med 2 decimaler, med svensk talskrivning: 115 718,52.
    """
    out = {}

    # =========================
    # Hjälpare
    # =========================
    def _fmt2(x) -> str:
        """Svensk formatering: tusentalsavgränsare som mellanslag och kommatecken för decimal."""
        try:
            val = float(x)
        except Exception:
            return "0,00"
        s = f"{val:,.2f}"               # t.ex. 115,718.52
        s = s.replace(",", "X")          # 115X718.52
        s = s.replace(".", ",")          # 115X718,52
        s = s.replace("X", " ")          # 115 718,52
        return s

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
        b = float(b)
        return float(a) / b if b != 0.0 else 0.0

    def _sec_to_hours_days_weeks(sec: float):
        hours = sec / 3600.0
        days  = hours / 24.0
        weeks = days / 7.0
        return _fmt2(hours), _fmt2(days), _fmt2(weeks)

    def _parse_date(s):
        try:
            if isinstance(s, date) and not isinstance(s, datetime):
                return s
            return pd.to_datetime(str(s)).date()
        except Exception:
            return None

    # =========================
    # Dynamiska etiketter & max
    # =========================
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
    MAX_BEK      = float(cfg.get("MAX_BEKANTA", 0) or 0)

    # Ekonomi-parametrar
    AVGIFT_USD   = float(cfg.get("avgift_usd", 30.0))
    COST_RATE    = float(cfg.get("COST_PER_HOUR_PER_PERSON", 15.0))
    REV_KANNER   = float(cfg.get("REVENUE_PER_KANNER", 30.0))
    SAL_BASE_PCT = float(cfg.get("SALARY_BASE_PCT", 0.08))
    SAL_MIN      = float(cfg.get("SALARY_MIN", 150.0))
    SAL_MAX      = float(cfg.get("SALARY_MAX", 800.0))
    PROD_STAFF   = float(cfg.get("PROD_STAFF", 800))

    AGE_PCT = {
        "<=18":  float(cfg.get("AGE_PCT_<=18", 1.00)),
        "19_23": float(cfg.get("AGE_PCT_19_23", 0.90)),
        "24_27": float(cfg.get("AGE_PCT_24_27", 0.85)),
        "28_30": float(cfg.get("AGE_PCT_28_30", 0.80)),
        "31_32": float(cfg.get("AGE_PCT_31_32", 0.75)),
        "33_35": float(cfg.get("AGE_PCT_33_35", 0.70)),
        "36+":   float(cfg.get("AGE_PCT_36PLUS", 0.60)),
    }

    def _age_factor(alder: int) -> float:
        if alder <= 18: return AGE_PCT["<=18"]
        if 19 <= alder <= 23: return AGE_PCT["19_23"]
        if 24 <= alder <= 27: return AGE_PCT["24_27"]
        if 28 <= alder <= 30: return AGE_PCT["28_30"]
        if 31 <= alder <= 32: return AGE_PCT["31_32"]
        if 33 <= alder <= 35: return AGE_PCT["33_35"]
        return AGE_PCT["36+"]

    # =========================
    # Kolumner
    # =========================
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
    NILS   = _col("Nils")

    SUMMA_TID_SEK = _col("Summa tid (sek)")
    TID_D_SEK     = _col("Tid D")
    TPK_SEK       = _col("Tid per kille (sek)")
    HAND_SEK      = _col("Händer per kille (sek)")
    HAK_SEK       = _col("Hångel (sek/kille)")

    HANDER_AKTIV  = _col("Händer aktiv")
    PREN          = _col("Prenumeranter")

    # Fallback "Totalt Män"
    if rows_df is not None and "Totalt Män" in rows_df.columns:
        TOT_MAN = _col("Totalt Män")
    else:
        TOT_MAN = (M + S + BD + ES + PD + P + G + NV + NF + BE)

    # Typ
    TYP_SER = rows_df["Typ"].astype(str) if (rows_df is not None and "Typ" in rows_df.columns) else pd.Series([""]*len(TOT_MAN))

    # =========================
    # GB-sektion (utfall)
    # =========================
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

    # =========================
    # Nöjdhet (utfall)
    # =========================
    sum_pappan  = float(P.sum())
    sum_grannar = float(G.sum())
    sum_nv      = float(NV.sum())
    sum_nf      = float(NF.sum())
    sum_sover   = float(SOVER.sum())
    sum_nils    = float(NILS.sum())
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

    # =========================
    # Totalt & Svarta (utfall)
    # =========================
    total_man_sum = float(TOT_MAN.sum())
    out["— Totalt —"] = ""
    out["Totalt antal män (alla fält)"] = _fmt2(total_man_sum)

    sum_black = float(S.sum())
    mask_rows_black = (S > 0)
    sum_black += float(ES[mask_rows_black].sum())
    sum_black += float(BD[mask_rows_black].sum())
    out["Summa Svarta (inkl. regler)"] = _fmt2(sum_black)
    out["Andel Svarta (%)"]            = _fmt2(100.0 * _div(sum_black, total_man_sum))

    # Prognos av Super-bonus ack (365d) – direkt under Svarta
    sb_pct = float(cfg.get("SUPER_BONUS_PCT", 0.1)) / 100.0
    avg_pren = float(PREN.mean()) if len(PREN) > 0 else 0.0
    super_bonus_365 = 365.0 * avg_pren * sb_pct
    out["Super-bonus (prognos 365d)"] = _fmt2(super_bonus_365)

    # =========================
    # DP/DPP/DAP/TAP (utfall)
    # =========================
    for col_name in ["DP", "DPP", "DAP", "TAP"]:
        ssum = _sum(col_name)
        denom = _count_rows(TOT_MAN > 0)
        avg   = _div(ssum, denom)
        out[f"{col_name} – summa"] = _fmt2(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt2(avg)

    # Älskar / Sover med (utfall)
    out["Älskar – summa"]     = _fmt2(sum_alskar)
    out["Sover med – summa"]  = _fmt2(sum_sover)

    # =========================
    # Källor – summor, snitt/scen, tillfällen (utfall)
    # =========================
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

    # =========================
    # Händer (utfall)
    # =========================
    total_rows = int(len(rows_df)) if rows_df is not None else 0
    aktiva  = _count_rows(HANDER_AKTIV > 0)
    inakt   = _count_rows(HANDER_AKTIV <= 0)
    out["— Händer —"] = ""
    out["Händer aktiva (antal)"]   = _fmt2(aktiva)
    out["Händer aktiva (%)"]       = _fmt2(100.0 * _div(aktiva, total_rows))
    out["Händer inaktiva (antal)"] = _fmt2(inakt)
    out["Händer inaktiva (%)"]     = _fmt2(100.0 * _div(inakt, total_rows))

    # =========================
    # Tider (utfall)
    # =========================
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

    # =========================
    # Snitt (utfall)
    # =========================
    out["— Snitt —"] = ""
    sum_tot_man_gb = float(TOT_MAN[M > 0].sum())
    denom_gb = _count_rows(M > 0)
    out["Snitt GB (Totalt män / antal GB)"] = _fmt2(_div(sum_tot_man_gb, denom_gb))

    sum_tot_man_privat = float(TOT_MAN[mask_privat].sum())
    out["Snitt Privat GB (Totalt män / antal Privat GB)"] = _fmt2(_div(sum_tot_man_privat, cnt_privat))

    mean_tid_gb_h   = _div(float(SUMMA_TID_SEK[M > 0].mean()), 3600.0) if denom_gb>0 else 0.0
    mean_tid_priv_h = _div(float(SUMMA_TID_SEK[mask_privat].mean()), 3600.0) if cnt_privat>0 else 0.0
    out["Snitt tid GB (h)"]        = _fmt2(mean_tid_gb_h)
    out["Snitt tid Privat GB (h)"] = _fmt2(mean_tid_priv_h)

    avg_tpk_ex   = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    tpk_incl_ser = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_ser.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"]   = _fmt2(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"] = _fmt2(avg_tpk_incl)

    out["Snitt Hångel (sek/kille)"] = _fmt2(float(HAK_SEK.mean()) if total_rows>0 else 0.0)
    out["Älskar snitt känner"]      = _fmt2(alskar_snitt_kanner)
    out["Sover med / MAX (Nils familj)"] = _fmt2(sover_div_max_nf)

    # =========================
    # Ekonomi – utfall (med alt-beräkning vid behov)
    # =========================
    INT  = _col("Intäkter")
    KM   = _col("Kostnad män")
    IK   = _col("Intäkt Känner")
    IF_  = _col("Intäkt företag")
    LM   = _col("Lön Malin")
    V    = _col("Vinst")

    need_alt = (len(INT)==0 and len(PREN)>0) or (len(KM)==0) or (len(IK)==0) or (len(IF_)==0) or (len(LM)==0) or (len(V)==0)

    def _recompute_alt_econ():
        timmar = SUMMA_TID_SEK / 3600.0
        man_bas = M + S + BE + ES
        tot_personer = man_bas + PROD_STAFF

        intakter = PREN * AVGIFT_USD
        intakt_kanner = (P + G + NV + NF) * REV_KANNER
        kostnad_man = timmar * tot_personer * COST_RATE
        intakt_foretag = intakter - kostnad_man - intakt_kanner

        bd = cfg.get("fodelsedatum", None)
        try:
            if isinstance(bd, str): bd = pd.to_datetime(bd).date()
        except Exception:
            bd = None

        if rows_df is not None and "Datum" in rows_df.columns:
            dat_series = rows_df["Datum"].apply(_parse_date)
        else:
            dat_series = pd.Series([None]*len(intakter))

        ages = []
        for d in dat_series:
            if isinstance(d, date) and isinstance(bd, date):
                a = d.year - bd.year - ((d.month, d.day) < (bd.month, bd.day))
            else:
                a = 30
            ages.append(a)
        factors = pd.Series([_age_factor(a) for a in ages], index=intakter.index)

        grund = (intakt_foretag * SAL_BASE_PCT).clip(lower=SAL_MIN, upper=SAL_MAX)
        lon = grund * factors

        vila_mask = TYP_SER.str.contains("Vila", case=False, na=False)
        intakter.loc[vila_mask] = 0.0
        intakt_kanner.loc[vila_mask] = 0.0
        kostnad_man.loc[vila_mask] = 0.0
        intakt_foretag.loc[vila_mask] = 0.0
        lon.loc[vila_mask] = 0.0
        vinst = intakt_foretag - lon

        return intakter, kostnad_man, intakt_kanner, intakt_foretag, lon, vinst

    if need_alt:
        INT_alt, KM_alt, IK_alt, IF_alt, LM_alt, V_alt = _recompute_alt_econ()
        INT = INT if len(INT)>0 else INT_alt
        KM  = KM  if len(KM)>0  else KM_alt
        IK  = IK  if len(IK)>0  else IK_alt
        IF_ = IF_ if len(IF_)>0 else IF_alt
        LM  = LM  if len(LM)>0  else LM_alt
        V   = V   if len(V)>0   else V_alt

    out["— Ekonomi —"] = ""
    out["Prenumeranter – summa"] = _fmt2(float(PREN.sum()))
    out["Intäkter – summa"]      = _fmt2(float(INT.sum()))
    out["Kostnad män – summa"]   = _fmt2(float(KM.sum()))
    out["Intäkt Känner – summa"] = _fmt2(float(IK.sum()))
    out["Intäkt företag – summa"]= _fmt2(float(IF_.sum()))
    out["Lön Malin – summa"]     = _fmt2(float(LM.sum()))
    out["Vinst – summa"]         = _fmt2(float(V.sum()))

    denom_kanner_money = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK
    kanner_tjanar_sum = _div(float(IK.sum()) + float(V.sum()), denom_kanner_money)
    out["Känner tjänar (summa)"] = _fmt2(kanner_tjanar_sum)

    total_man_sum = float(TOT_MAN.sum())
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    denom_gb = max(1, _count_rows(M > 0))
    out["Lön Malin / Per scen"]                 = _fmt2(_div(float(LM.sum()), denom_gb))
    out["Lön Malin / Totalt antal män"]         = _fmt2(_div(float(LM.sum()), total_man_sum))
    out["Lön Malin / Totalt antal tillfällen"]  = _fmt2(_div(float(LM.sum()), total_tillfallen))

    # =========================
    # PROGNOS 365d – tydliga etiketter
    # =========================
    out["— Prognos 365d —"] = ""
    n_rows = max(1, len(rows_df) if rows_df is not None else 0)

    def _proj_sum(series: pd.Series) -> float:
        return float(series.mean()) * 365.0 if n_rows > 0 else 0.0

    out["Totalt antal män (prognos 365d)"] = _fmt2(_proj_sum(TOT_MAN))

    sum_black_now = sum_black
    tot_man_now   = float(TOT_MAN.sum())
    black_share = _div(sum_black_now, tot_man_now)
    proj_black   = black_share * float(_proj_sum(TOT_MAN))
    out["Summa Svarta (inkl. regler) (prognos 365d)"] = _fmt2(proj_black)
    out["Andel Svarta (prognos %)"]                   = _fmt2(100.0 * black_share)

    out["Älskar – summa (prognos 365d)"]             = _fmt2(_proj_sum(ALSKAR))
    out["Snitt älskar (känner-bas) (nu)"]            = _fmt2(alskar_snitt_kanner)

    out["Sover med – summa (prognos 365d)"]          = _fmt2(_proj_sum(SOVER))
    out["Snitt sover med / MAX (NF) (nu)"]           = _fmt2(sover_div_max_nf)

    for lbl, ser, mx in [
        (LBL_PAPPAN, P, MAX_PAPPAN),
        (LBL_GRANNAR, G, MAX_GRANNAR),
        (LBL_NV,      NV, MAX_NV),
        (LBL_NF,      NF, MAX_NF),
        ("Bonus deltagit", BD, 1.0),
        ("Personal deltagit", PD, 1.0),
        (LBL_BEK,     BE, 1.0),
        (LBL_ESK,     ES, 1.0),
    ]:
        out[f"{lbl} – summa (prognos 365d)"] = _fmt2(_proj_sum(ser))
        cnt = _count_rows(ser > 0)
        out[f"{lbl} – snitt per scen (nu)"] = _fmt2(_div(float(ser.sum()), cnt))

    avg_pren   = float(PREN.mean()) if n_rows>0 else 0.0
    avg_kanner = float((P + G + NV + NF).mean()) if n_rows>0 else 0.0
    avg_hours  = float((SUMMA_TID_SEK / 3600.0).mean()) if n_rows>0 else 0.0
    avg_manbas = float((M + S + BE + ES).mean()) if n_rows>0 else 0.0
    avg_tot_personer = avg_manbas + PROD_STAFF

    day_int   = avg_pren   * AVGIFT_USD
    day_ik    = avg_kanner * REV_KANNER
    day_kost  = avg_hours  * avg_tot_personer * COST_RATE
    day_if    = day_int - day_kost - day_ik

    try:
        fd = cfg.get("fodelsedatum", None)
        if isinstance(fd, str):
            fd = pd.to_datetime(fd).date()
        today = pd.Timestamp.today().date()
        age_today = today.year - fd.year - ((today.month, today.day) < (fd.month, fd.day)) if isinstance(fd, date) else 30
    except Exception:
        age_today = 30
    factor_today = _age_factor(age_today)
    grund_day = max(SAL_MIN, min(SAL_MAX, SAL_BASE_PCT * day_if))
    day_salary = grund_day * factor_today
    day_vinst  = day_if - day_salary

    out["Prenumeranter – summa (prognos 365d)"] = _fmt2(avg_pren * 365.0)
    out["Intäkter – summa (prognos 365d)"]      = _fmt2(day_int * 365.0)
    out["Kostnad män – summa (prognos 365d)"]   = _fmt2(day_kost * 365.0)
    out["Intäkt Känner – summa (prognos 365d)"] = _fmt2(day_ik * 365.0)
    out["Intäkt företag – summa (prognos 365d)"]= _fmt2(day_if * 365.0)
    out["Lön Malin – summa (prognos 365d)"]     = _fmt2(day_salary * 365.0)
    out["Lön Malin – snitt/dag (prognos)"]      = _fmt2(day_salary)
    out["Vinst – summa (prognos 365d)"]         = _fmt2(day_vinst * 365.0)

    denom_kanner_money = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK
    kanner_tjanar_365 = _div((day_ik * 365.0) + (day_vinst * 365.0), denom_kanner_money)
    out["Känner tjänar (prognos 365d)"] = _fmt2(kanner_tjanar_365)

    out["Antal GB (prognos 365d)"]         = _fmt2(_div(cnt_gb, n_rows) * 365.0)
    out["Privat GB (prognos 365d)"]        = _fmt2(_div(cnt_privat, n_rows) * 365.0)
    out["Antal GB vita (prognos 365d)"]    = _fmt2(_div(cnt_gb_vita, n_rows) * 365.0)
    out["Antal GB svarta (prognos 365d)"]  = _fmt2(_div(cnt_gb_svarta, n_rows) * 365.0)
    out["Antal GB blandat (prognos 365d)"] = _fmt2(_div(cnt_gb_blandat, n_rows) * 365.0)

    # =========================
    # Prognos – Nöjdhet & snitt per vecka (inkl. Nils)
    # =========================
    if rows_df is not None and "Datum" in rows_df.columns:
        dates = rows_df["Datum"].apply(_parse_date)
        uniq_days = len(set([d for d in dates if isinstance(d, date)]))
    else:
        uniq_days = n_rows
    weeks_now = max(1.0, uniq_days / 7.0)

    out["— Prognos Nöjdhet —"] = ""
    out["Nöjdhet – Pappans vänner (snitt/vecka; prognos)"] = _fmt2((alskar_snitt_kanner + tillf_pappan) / weeks_now)
    out["Nöjdhet – Grannar (snitt/vecka; prognos)"]        = _fmt2((alskar_snitt_kanner + tillf_grannar) / weeks_now)
    out["Nöjdhet – Nils vänner (snitt/vecka; prognos)"]    = _fmt2((alskar_snitt_kanner + tillf_nv) / weeks_now)
    out["Nöjdhet – Nils familj (snitt/vecka; prognos)"]    = _fmt2((alskar_snitt_kanner + tillf_nf + sover_div_max_nf) / weeks_now)
    out["Nöjdhet – Nils (summa/vecka; prognos)"]           = _fmt2(_div(sum_nils, weeks_now))

    return out
