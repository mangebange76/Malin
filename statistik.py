# statistik.py
# Enkel, robust statistikmotor som tål saknade kolumner och blandade typer.

from __future__ import annotations
from typing import Dict, Any, Iterable, List
import pandas as pd


def _col_sum(df: pd.DataFrame, col: str) -> float:
    """Summerar kolumn (tyst om den saknas) med numerisk tvingning."""
    if col not in df.columns:
        return 0.0
    s = pd.to_numeric(df[col], errors="coerce")
    return float(s.fillna(0).sum())


def _get_label(cfg: Dict[str, Any], key: str, default: str) -> str:
    return str(cfg.get(key, default))


def compute_stats(rows: Iterable[Dict[str, Any]] | pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tar emot alla rader (list[dict] eller DataFrame) och nuvarande cfg,
    och returnerar en dict med sammanfattningar.
    """
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    else:
        df = pd.DataFrame(list(rows) if rows is not None else [])

    stats: Dict[str, Any] = {}

    if df.empty:
        stats["Totalt antal scener"] = 0
        return stats

    # Etiketter som kan vara omdöpta
    LBL_ESK = _get_label(cfg, "LBL_ESK", "Eskilstuna killar")

    # --- Bas ---
    stats["Totalt antal scener"] = int(len(df))

    # --- Summerade pengar ---
    for col, label in [
        ("Intäkt företag", "Totalt intäkt företag (USD)"),
        ("Intäkt Känner",  "Totalt intäkt känner (USD)"),
        ("Intäkter",       "Totalt intäkt (USD)"),
        ("Kostnad män",    "Totalt kostnad män (USD)"),
        ("Lön Malin",      "Totalt lön Malin (USD)"),
        ("Vinst",          "Totalt vinst (USD)"),
    ]:
        stats[label] = round(_col_sum(df, col), 2)

    # --- Prenumeranter ---
    stats["Totalt antal prenumeranter"] = int(_col_sum(df, "Prenumeranter"))

    # --- Känner sammanlagt (från MAX i cfg) ---
    max_p = int(cfg.get("MAX_PAPPAN", 0) or 0)
    max_g = int(cfg.get("MAX_GRANNAR", 0) or 0)
    max_nv = int(cfg.get("MAX_NILS_VANNER", 0) or 0)
    max_nf = int(cfg.get("MAX_NILS_FAMILJ", 0) or 0)
    kanner_sammanlagt = max_p + max_g + max_nv + max_nf
    stats["Känner Sammanlagt (MAX)"] = int(kanner_sammanlagt)

    # --- Andel svarta (%), enligt din statistik-formel ---
    svarta_sum = _col_sum(df, "Svarta")
    denominator = (
        _col_sum(df, "Män")
        + kanner_sammanlagt
        + svarta_sum
        + int(cfg.get("MAX_BEKANTA", 0) or 0)
        + _col_sum(df, LBL_ESK)
        + _col_sum(df, "Bonus deltagit")
        + int(cfg.get("PROD_STAFF", 0) or 0)
    )
    stats["Andel svarta (%)"] = round(100.0 * svarta_sum / denominator, 2) if denominator > 0 else 0.0

    # --- BM-mål (om finns i cfg) ---
    # Stöd både 'BM-mål'/'BM_MAL' och 'Mål vikt'/'MAL_VIKT'
    if "BM-mål" in cfg or "BM_MAL" in cfg:
        bm = float(cfg.get("BM-mål", cfg.get("BM_MAL", 0.0)) or 0.0)
        stats["BM-mål (snitt)"] = round(bm, 2)
    if "Mål vikt" in cfg or "MAL_VIKT" in cfg:
        mv = float(cfg.get("Mål vikt", cfg.get("MAL_VIKT", 0.0)) or 0.0)
        stats["Mål vikt (kg)"] = round(mv, 2)

    # --- Bonus & superbonus (om ni använder dem i appens CFG) ---
    if "BONUS_AVAILABLE" in cfg:
        stats["Bonus kvar (antal)"] = int(cfg.get("BONUS_AVAILABLE", 0) or 0)
    if "BONUS_PCT" in cfg:
        stats["Bonus % (decimal)"] = float(cfg.get("BONUS_PCT", 0.0) or 0.0)
    if "SUPER_BONUS_ACC" in cfg:
        stats["Super bonus ack"] = int(cfg.get("SUPER_BONUS_ACC", 0) or 0)
    if "SUPER_BONUS_PCT" in cfg:
        stats["Super bonus % (decimal)"] = float(cfg.get("SUPER_BONUS_PCT", 0.0) or 0.0)

    # --- Händer (antal rader där det är aktivt) ---
    if "Händer aktiv" in df.columns:
        stats["Händer aktiva (antal rader)"] = int((pd.to_numeric(df["Händer aktiv"], errors="coerce").fillna(0) > 0).sum())

    return stats
