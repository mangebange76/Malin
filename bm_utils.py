# bm_utils.py
from typing import Dict, Any

def _to_float(x, default: float) -> float:
    """Robust konvertering: stöder '164', '1,64', 1.64, 164, None."""
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    try:
        s = str(x).strip().replace(",", ".")
        return float(s)
    except Exception:
        return default

def compute_bm_fields(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returnerar {'BM mål', 'Mål vikt (kg)', 'Super bonus ack'} baserat på cfg.
    - Längd anges i cm (t.ex. 164). Om användaren råkar ange meter (<=3) konverteras det.
    - BM mål hämtas från cfg['BMI_GOAL'] och tillåter str/komma.
    """
    # Längd
    height_cm = _to_float(cfg.get("HEIGHT_CM", 164), 164.0)
    if height_cm <= 3.0:  # användaren har angett meter (t.ex. 1.64)
        height_cm *= 100.0
    height_m = height_cm / 100.0

    # BMI-mål
    bmi_goal = _to_float(cfg.get("BMI_GOAL", 21.7), 21.7)

    # Målvikt = BMI * längd^2
    target_weight = round(bmi_goal * (height_m ** 2), 1)

    # Superbonus-ack från cfg
    super_acc = int(_to_float(cfg.get("SUPER_BONUS_ACC", 0), 0.0))

    return {
        "BM mål": bmi_goal,
        "Mål vikt (kg)": target_weight,
        "Super bonus ack": super_acc,
    }
