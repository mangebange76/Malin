# -*- coding: utf-8 -*-
import math

def _sum_col(df, col):
    try:
        return int(df[col].fillna(0).astype(float).sum())
    except Exception:
        return 0

def compute_stats(rows_df, cfg=None):
    """
    Minimal statistik enligt dina definitioner:
    - Känner sammanlagt: sum av maxvärden (från cfg)
    - Totalt män (statistik):
        SUM över rader av (Män + Svarta + Bonus deltagit + [Eskilstuna-etikett])
        + (MAX_PAPPAN + MAX_GRANNAR + MAX_NILS_VANNER + MAX_NILS_FAMILJ + MAX_BEKANTA + PROD_STAFF)
      (den sista parentesen läggs EN gång)
    - Svarta (statistik): SUM (Svarta + Eskilstuna + Bonus deltagit) för rader där Svarta > 0
    """
    if rows_df is None or rows_df.empty:
        return {}

    # etiketter
    esk_lbl = cfg.get("LBL_ESK", "Eskilstuna killar") if cfg else "Eskilstuna killar"

    # Känner sammanlagt (från cfg maxvärden)
    max_sum = 0
    if cfg:
        max_sum = (int(cfg.get("MAX_PAPPAN",0)) + int(cfg.get("MAX_GRANNAR",0)) +
                   int(cfg.get("MAX_NILS_VANNER",0)) + int(cfg.get("MAX_NILS_FAMILJ",0)))

    # Totalt män (statistik)
    part_rows = (
        _sum_col(rows_df, "Män") +
        _sum_col(rows_df, "Svarta") +
        _sum_col(rows_df, "Bonus deltagit") +
        _sum_col(rows_df, esk_lbl)
    )
    one_off = 0
    if cfg:
        one_off = (int(cfg.get("MAX_PAPPAN",0)) + int(cfg.get("MAX_GRANNAR",0)) +
                   int(cfg.get("MAX_NILS_VANNER",0)) + int(cfg.get("MAX_NILS_FAMILJ",0)) +
                   int(cfg.get("MAX_BEKANTA",0)) + int(cfg.get("PROD_STAFF",0)))
    totalt_man_stat = part_rows + one_off

    # Svarta (statistik) – rader där Svarta > 0
    try:
        mask = rows_df["Svarta"].fillna(0).astype(float) > 0
        svarta_stat = int(
            rows_df.loc[mask, "Svarta"].fillna(0).astype(float).sum()
            + rows_df.loc[mask, esk_lbl].fillna(0).astype(float).sum()
            + rows_df.loc[mask, "Bonus deltagit"].fillna(0).astype(float).sum()
        )
    except Exception:
        svarta_stat = 0

    return {
        "Känner sammanlagt (maxvärden)": max_sum,
        "Totalt män (statistik)": totalt_man_stat,
        "Svarta (statistik)": svarta_stat,
    }
