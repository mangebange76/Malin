# statistik.py
import pandas as pd

def compute_stats(df: pd.DataFrame, cfg: dict):
    """
    Sammanfattning på enkel nivå. Robust mot tomma/ickematchande kolumner.
    df: DataFrame med raderna (t.ex. från ROWS eller Data_<profil>)
    cfg: nuvarande CFG (för att hämta namn-etiketten till lönkolumnen)
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "Totalt antal rader": 0,
            "Summa intäkter": 0.0,
            "Summa intäkt företag": 0.0,
            "Summa vinst": 0.0,
        }

    def col_sum(name: str) -> float:
        return df[name].fillna(0).astype(float).sum() if name in df.columns else 0.0

    name_label = cfg.get("NAME_LABEL", "Malin")
    lon_col = f"Lön {name_label}"

    stats = {
        "Totalt antal rader": len(df),
        "Totalt män (summa)": col_sum("Totalt Män"),
        "Summa intäkter": col_sum("Intäkter"),
        "Summa utgift män": col_sum("Utgift män"),
        f"Summa lön {name_label}": col_sum(lon_col),
        "Summa intäkt Känner": col_sum("Intäkt Känner"),
        "Summa intäkt företag": col_sum("Intäkt företag"),
        "Summa vinst": col_sum("Vinst"),
    }

    return stats
