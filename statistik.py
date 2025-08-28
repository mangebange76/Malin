# statistik.py — version 250823-2 (samlad)
import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Returnerar en dict {etikett: värde(str)} för visning i appen.
    - Svensk formatering: mellanslag som tusentalsavskiljare och komma som decimaltecken.
    - Innehåller:
        * Översikt, GB, Svarta, DP/DPP/DAP/TAP, Älskar/Sover, Källor, Händer, Tider, Snitt, Nöjdhet, Ekonomi
        * "Känner tjänar (nu)" = (Intäkt Känner – summa + Vinst – summa) / (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEKANTA)
        * Prognos 365d (baserat på dagens snitt → multiplicerat till 365 rader)
        * Prognos Nöjdhet per vecka (inkl. Nils)
        * Totalt antal män per dag (period)
    Allt numeriskt formatteras med 2 decimaler.
    """
    out = {}

    # ===== Hjälpare =====
    def _fmt2(x) -> str:
        """Svensk formatering med 2 decimaler, t.ex. 113 951 783,33"""
        try:
            v = float(x)
            s = f"{v:,.2f}"              # 113,951,783.33
            s = s.replace(",", " ")      # 113 951 783.33
            s = s.replace(".", ",")      # 113 951 783,33
            return s
        except Exception:
            return "0,00"

    def _fmt0(x) -> str:
        """Svensk formatering heltal, t.ex. 115 718"""
        try:
            v = int(round(float(x)))
            s = f"{v:,}"
            return s.replace(",", " ")
        except Exception:
            return "0"

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

    def _days_in_span() -> int:
        """Antal dagar mellan minsta och största 'Datum' (inklusive båda). Fallback = antal rader."""
        if rows_df is None or rows_df.empty or "Datum" not in rows_df.columns:
            return max(1, len(rows_df) if rows_df is not None else 1)
        dts = pd.to_datetime(rows_df["Datum"], errors="coerce").dropna()
        if dts.empty:
            return max(1, len(rows_df))
        return max(1, int((dts.max().date() - dts.min().date()).days) + 1)

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
    PROD_STAFF   = float(cfg.get("PROD_STAFF", 0) or 0)

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
    NILS   = _col("Nils")

    SUMMA_TID_SEK = _col("Summa tid (sek)")
    TID_D_SEK     = _col("Tid D")  # i appen sparas "Tid D (sek)" som "Tid D"
    TPK_SEK       = _col("Tid per kille (sek)")
    HAND_SEK      = _col("Händer per kille (sek)")
    HAK_SEK       = _col("Hångel (sek/kille)")

    HANDER_AKTIV  = _col("Händer aktiv")

    # Ekonomi
    PREN = _col("Prenumeranter")
    INT  = _col("Intäkter")
    KM   = _col("Kostnad män")
    IK   = _col("Intäkt Känner")
    IF_  = _col("Intäkt företag")
    LM   = _col("Lön Malin")
    V    = _col("Vinst")

    total_rows = int(len(rows_df)) if rows_df is not None else 0
    days_span  = _days_in_span()

    # Fallback "Totalt Män" per rad (om kolumn saknas) – enligt överenskommen totalsumma
    if rows_df is not None and ("Totalt Män" in rows_df.columns):
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
    out["Antal rader"] = _fmt0(total_rows)

    out["— GB —"] = ""
    out["Antal GB"]         = _fmt2(cnt_gb)
    out["Privat GB"]        = _fmt2(cnt_privat)
    out["Antal GB vita"]    = _fmt2(cnt_gb_vita)
    out["Antal GB svarta"]  = _fmt2(cnt_gb_svarta)
    out["Antal GB blandat"] = _fmt2(cnt_gb_blandat)

    # ===== Totalt antal män =====
    total_man_sum = float(TOT_MAN.sum())
    out["— Totalt —"] = ""
    out["Totalt antal män (alla fält)"] = _fmt2(total_man_sum)
    out["Totalt antal män per dag (period)"] = _fmt2(_div(total_man_sum, days_span))

    # ===== Svarta – summa + andel % (med specialregel) =====
    sum_black = float(S.sum())
    # På rader där S>0 räknas ES och BD som svarta
    mask_rows_black = (S > 0)
    sum_black += float(ES[mask_rows_black].sum())
    sum_black += float(BD[mask_rows_black].sum())

    out["— Svarta —"] = ""
    out["Summa Svarta (inkl. regler)"] = _fmt2(sum_black)
    out["Andel Svarta (%)"]            = _fmt2(100.0 * _div(sum_black, total_man_sum))

    # ===== DP / DPP / DAP / TAP =====
    out["— DP/DPP/DAP/TAP —"] = ""
    for col_name in ["DP", "DPP", "DAP", "TAP"]:
        ssum = _sum(col_name)
        # snitt per scen: över rader där Totalt Män > 0
        denom = _count_rows(TOT_MAN > 0)
        avg   = _div(ssum, denom)
        out[f"{col_name} – summa"]          = _fmt2(ssum)
        out[f"{col_name} – snitt per scen"] = _fmt2(avg)

    # ===== Älskar / Sover med =====
    out["— Älskar & Sover —"] = ""
    out["Älskar – summa"]     = _fmt2(float(ALSKAR.sum()))
    out["Sover med – summa"]  = _fmt2(float(SOVER.sum()))

    # ===== Källor – summor, snitt per scen, antal tillfällen (summa/max) =====
    out["— Källor —"] = ""
    def _sum_snitt_tillfallen(label: str, ser: pd.Series, maxv: float):
        ssum = float(ser.sum())
        cnt  = _count_rows(ser > 0)
        avg  = _div(ssum, cnt)
        out[f"{label} – summa"] = _fmt2(ssum)
        out[f"{label} – snitt per scen"] = _fmt2(avg)
        out[f"{label} – antal tillfällen (summa/max)"] = _fmt2(_div(ssum, maxv if maxv > 0 else 1.0))

    _sum_snitt_tillfallen(LBL_PAPPAN,  P,  MAX_PAPPAN)
    _sum_snitt_tillfallen(LBL_GRANNAR, G,  MAX_GRANNAR)
    _sum_snitt_tillfallen(LBL_NV,      NV, MAX_NV)
    _sum_snitt_tillfallen(LBL_NF,      NF, MAX_NF)
    _sum_snitt_tillfallen(LBL_BEK,     BE, MAX_BEK)          # <-- Bekanta delar på MAX_BEKANTA
    _sum_snitt_tillfallen(LBL_ESK,     ES, 1.0)
    _sum_snitt_tillfallen("Bonus deltagit",   BD, 1.0)
    _sum_snitt_tillfallen("Personal deltagit", PD, PROD_STAFF if PROD_STAFF > 0 else 1.0)  # delar på personalbas

    # Summan av MAX (känner-fälten, 4 st)
    out["Summa MAX (källor, inställningar)"] = _fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ===== Händer – antal & % =====
    aktiva  = _count_rows(HANDER_AKTIV > 0)
    inakt   = _count_rows(HANDER_AKTIV <= 0)
    out["— Händer —"] = ""
    out["Händer aktiva (antal)"]   = _fmt2(aktiva)
    out["Händer aktiva (%)"]       = _fmt2(100.0 * _div(aktiva, max(1, total_rows)))
    out["Händer inaktiva (antal)"] = _fmt2(inakt)
    out["Händer inaktiva (%)"]     = _fmt2(100.0 * _div(inakt,  max(1, total_rows)))

    # ===== Tider =====
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

    # ===== Snitt =====
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

    avg_tpk_ex = float(TPK_SEK.mean()) if total_rows>0 else 0.0
    tpk_incl_series = TPK_SEK + (HAND_SEK.where(HANDER_AKTIV > 0, other=0))
    avg_tpk_incl = float(tpk_incl_series.mean()) if total_rows>0 else 0.0
    out["Snitt tid/kille ex händer (sek)"]  = _fmt2(avg_tpk_ex)
    out["Snitt tid/kille inkl händer (sek)"]= _fmt2(avg_tpk_incl)

    # ===== Nöjdhet =====
    sum_pappan  = float(P.sum())
    sum_grannar = float(G.sum())
    sum_nv      = float(NV.sum())
    sum_nf      = float(NF.sum())
    sum_sover   = float(SOVER.sum())
    sum_nils    = float(NILS.sum())
    sum_alskar  = float(ALSKAR.sum())

    denom_kanner4 = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    denom_kanner5 = denom_kanner4 + MAX_BEK

    alskar_snitt_kanner = _div(sum_alskar, denom_kanner4)

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

    out["Älskar snitt känner"] = _fmt2(alskar_snitt_kanner)
    out["Sover med / MAX (Nils familj)"] = _fmt2(sover_div_max_nf)

    # ===== Ekonomi =====
    out["— Ekonomi —"] = ""
    pren_sum = float(PREN.sum())
    int_sum  = float(INT.sum())
    km_sum   = float(KM.sum())
    ik_sum   = float(IK.sum())
    if_sum   = float(IF_.sum())
    lm_sum   = float(LM.sum())
    v_sum    = float(V.sum())

    out["Prenumeranter – summa"] = _fmt2(pren_sum)
    out["Intäkter – summa"]      = _fmt2(int_sum)
    out["Kostnad män – summa"]   = _fmt2(km_sum)
    out["Intäkt Känner – summa"] = _fmt2(ik_sum)
    out["Intäkt företag – summa"]= _fmt2(if_sum)
    out["Lön Malin – summa"]     = _fmt2(lm_sum)
    out["Vinst – summa"]         = _fmt2(v_sum)

    denom_gb_rows = max(1, denom_gb)
    out["Lön Malin / Per scen"]                 = _fmt2(_div(lm_sum, denom_gb_rows))
    out["Lön Malin / Totalt antal män"]         = _fmt2(_div(lm_sum, total_man_sum))
    total_tillfallen = float((M + S + ALSKAR + SOVER + BD + PD + P + G + NV + NF + BE + ES).sum())
    out["Lön Malin / Totalt antal tillfällen"]  = _fmt2(_div(lm_sum, total_tillfallen))

    # Känner tjänar (nu)
    out["Känner tjänar (nu)"] = _fmt2(_div(ik_sum + v_sum, max(1.0, denom_kanner5)))

    # ===== PROGNOS 365d (skala upp efter snitt per rad) =====
    out["— Prognos 365d —"] = ""
    scale = _div(365.0, max(1, total_rows))

    # Tot män och Svarta
    out["Totalt antal män – 365d"]            = _fmt2(total_man_sum * scale)
    out["Summa Svarta (inkl. regler) – 365d"] = _fmt2(sum_black * scale)
    out["Andel Svarta (%) – 365d"]            = _fmt2(100.0 * _div(sum_black * scale, total_man_sum * scale))

    # Super-bonus ack – prognos (365d)
    sb_pct = float(cfg.get("SUPER_BONUS_PCT", 0.1)) / 100.0  # 0.1 => 0.001
    out["Super-bonus ack – prognos (365d)"] = _fmt2(pren_sum * scale * sb_pct)

    # Älskar/Sover
    out["Älskar – summa (365d)"] = _fmt2(float(ALSKAR.sum()) * scale)
    out["Snitt älskar (Älskar snitt känner) – 365d"] = _fmt2(_div(float(ALSKAR.sum()) * scale, max(1.0, denom_kanner4)))
    out["Sover med – summa (365d)"] = _fmt2(float(SOVER.sum()) * scale)
    out["Snitt sover med (Sover med / MAX (Nils familj)) – 365d"] = _fmt2(_div(float(SOVER.sum()) * scale, max(1.0, MAX_NF)))

    # Källor – prognos (summa & snitt per scen)
    # (snitt per scen = (summa/antal_rader) → multiplicera 365 → dividera 365 → = samma som dagens snitt; vi visar båda för symmetri)
    def _prog_src(label: str, ser: pd.Series):
        ssum = float(ser.sum())
        out[f"{label} – summa (365d)"] = _fmt2(ssum * scale)
        avg  = _div(ssum, max(1, _count_rows(ser > 0)))
        out[f"{label} – snitt per scen (365d)"] = _fmt2(avg)

    _prog_src(LBL_PAPPAN,  P)
    _prog_src(LBL_GRANNAR, G)
    _prog_src(LBL_NV,      NV)
    _prog_src(LBL_NF,      NF)
    _prog_src("Bonus deltagit", BD)
    _prog_src("Personal deltagit", PD)
    _prog_src(LBL_BEK,     BE)
    _prog_src(LBL_ESK,     ES)

    # Ekonomi – prognos (365d)
    out["Prenumeranter – summa (365d)"] = _fmt2(pren_sum * scale)
    out["Intäkter – summa (365d)"]      = _fmt2(int_sum  * scale)
    out["Kostnad män – summa (365d)"]   = _fmt2(km_sum   * scale)
    out["Intäkt Känner – summa (365d)"] = _fmt2(ik_sum   * scale)
    out["Intäkt företag – summa (365d)"]= _fmt2(if_sum   * scale)
    out["Lön Malin – summa (365d)"]     = _fmt2(lm_sum   * scale)
    out["Vinst – summa (365d)"]         = _fmt2(v_sum    * scale)

    # Känner tjänar (365d)
    out["Känner tjänar (365d)"] = _fmt2(_div((ik_sum * scale) + (v_sum * scale), max(1.0, denom_kanner5)))

    # GB – prognos 365d (räkna upp frekvens)
    out["— GB (365d) —"] = ""
    out["Antal GB (365d)"]         = _fmt2(cnt_gb * scale)
    out["Privat GB (365d)"]        = _fmt2(cnt_privat * scale)
    out["Antal GB vita (365d)"]    = _fmt2(cnt_gb_vita * scale)
    out["Antal GB svarta (365d)"]  = _fmt2(cnt_gb_svarta * scale)
    out["Antal GB blandat (365d)"] = _fmt2(cnt_gb_blandat * scale)

    # ===== Prognos Nöjdhet (per vecka) =====
    out["— Prognos Nöjdhet (per vecka) —"] = ""
    # Skala upp bas-summor till 365d och använd samma formler -> dividera sedan med 52
    sum_pappan_365  = sum_pappan  * scale
    sum_grannar_365 = sum_grannar * scale
    sum_nv_365      = sum_nv      * scale
    sum_nf_365      = sum_nf      * scale
    sum_sover_365   = sum_sover   * scale
    sum_alskar_365  = sum_alskar  * scale
    sum_nils_365    = sum_nils    * scale

    alskar_snitt_kanner_365 = _div(sum_alskar_365, max(1.0, denom_kanner4))
    til_pap_365 = _div(sum_pappan_365,  max(1.0, MAX_PAPPAN))
    til_gra_365 = _div(sum_grannar_365, max(1.0, MAX_GRANNAR))
    til_nv_365  = _div(sum_nv_365,      max(1.0, MAX_NV))
    til_nf_365  = _div(sum_nf_365,      max(1.0, MAX_NF))
    sover_div_nf_365 = _div(sum_sover_365, max(1.0, MAX_NF))

    week_div = 52.0

    out[f"{LBL_PAPPAN} – nöjdhet/vecka (prognos)"]  = _fmt2(_div(alskar_snitt_kanner_365 + til_pap_365, week_div))
    out[f"{LBL_GRANNAR} – nöjdhet/vecka (prognos)"] = _fmt2(_div(alskar_snitt_kanner_365 + til_gra_365, week_div))
    out[f"{LBL_NV} – nöjdhet/vecka (prognos)"]      = _fmt2(_div(alskar_snitt_kanner_365 + til_nv_365,  week_div))
    out[f"{LBL_NF} – nöjdhet/vecka (prognos)"]      = _fmt2(_div(alskar_snitt_kanner_365 + til_nf_365 + sover_div_nf_365, week_div))
    out["Nils – per vecka (prognos)"]               = _fmt2(_div(sum_nils_365, week_div))

    return out
