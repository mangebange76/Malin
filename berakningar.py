# berakningar.py
from __future__ import annotations
from datetime import datetime, timedelta, date, time

# =========================
# Hjälpfunktioner (rena)
# =========================
def _safe_int(x, default=0):
    try:
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default

def _calc_u(rad_in: dict) -> int:
    """U = Känner = Pappans vänner + Grannar + Nils vänner + Nils familj."""
    return (
        _safe_int(rad_in.get("Pappans vänner", 0)) +
        _safe_int(rad_in.get("Grannar", 0)) +
        _safe_int(rad_in.get("Nils vänner", 0)) +
        _safe_int(rad_in.get("Nils familj", 0))
    )

def _hm_str_from_seconds(q_sec: int) -> str:
    """Returnera t.ex. '4h 49 min' från sekunder (avrundar minuter)."""
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    """Returnera 'Xm Ys' från sekunder (minuter & sekunder)."""
    if sec < 0: sec = 0
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"


# =========================================
# Huvudberäkning (används av app.py)
# =========================================
def berakna_radvarden(rad_in: dict, rad_datum: date, födelsedatum: date, starttid: time) -> dict:
    """
    - U (Känner) ingår i Summa S/D/TP/Vila.
    - Älskar → +30 min/st (1800 s), Sover med (0/1) → +60 min (3600 s).
    - Suger_total (sek) = 60% av (Summa D + Summa TP). Suger/kille = Suger_total / Z.
    - Tid/kille (sek) = (S/Z) + 2*(D/Z) + 3*(TP/Z) + (Suger_total/Z), Z = Män + Känner.
    - Hångel = 3h totalt (10 800 s) / Män → sek/kille och m:s/kille (påverkar ej Summa tid).
    - Hårdhet = (+3 om DP>0) + (+4 om DPP>0) + (+6 om DAP>0) + (+8 om TAP>0).
    - Prenumeranter (rad) = (Män+Fitta+Rumpa+DP+DPP+DAP+TAP+Känner) × Hårdhet.
    - Avgift (USD) kommer från rad_in["Avgift"] (default 30) och gäller endast för denna rad.
    - Intäkter (rad) = Prenumeranter × Avgift. Lön Malin = 10% av pren. (min 150 / max 800) med åldersfaktor.
    - SPECIALFALL (exkludera från subs + all ekonomi):
        * Typ == "Vila på jobbet": Prenumeranter = 0, ekonomi = 0.
        * Typ == "Vila i hemmet" : Prenumeranter = 0, ekonomi = 0.
    """

    typ = (rad_in.get("Typ") or "").strip()

    # Indata
    c = _safe_int(rad_in.get("Män", 0))
    d = _safe_int(rad_in.get("Fitta", 0))
    e = _safe_int(rad_in.get("Rumpa", 0))
    f = _safe_int(rad_in.get("DP", 0))
    g = _safe_int(rad_in.get("DPP", 0))
    h = _safe_int(rad_in.get("DAP", 0))
    i = _safe_int(rad_in.get("TAP", 0))

    j = _safe_int(rad_in.get("Tid S", 0))  # sek
    k = _safe_int(rad_in.get("Tid D", 0))  # sek
    l = _safe_int(rad_in.get("Vila", 0))   # sek

    alskar    = _safe_int(rad_in.get("Älskar", 0))     # 30 min/st
    sover_med = _safe_int(rad_in.get("Sover med", 0))  # 0/1 → 60 min/st
    if sover_med < 0: sover_med = 0
    if sover_med > 1: sover_med = 1

    # U = Känner
    u = _calc_u(rad_in)

    # Summor – inkluderar U (sekunder)
    m = (c + d + e + u) * j                 # Summa S
    n = (f + g + h + u) * k                 # Summa D
    o = (i + u) * k                         # Summa TP
    p = (c + d + e + f + g + h + i + u) * l # Summa Vila

    # Extra tid från Älskar & Sover med
    extra_alskar_sec    = alskar * 1800     # 30 min/st
    extra_sover_med_sec = sover_med * 3600  # 60 min/st

    # Totaltid
    q_sec = int(m + n + o + p + extra_alskar_sec + extra_sover_med_sec)
    q_hours = q_sec / 3600.0
    summa_tid_str = _hm_str_from_seconds(q_sec)

    # Klockan (utifrån starttid)
    klockan_str = (
        datetime.combine(rad_datum, starttid)
        + timedelta(hours=3)
        + timedelta(hours=q_hours)
        + timedelta(hours=1)
    ).strftime("%H:%M")

    # Totalt män Z = Män + Känner
    z = int(c + u)

    # Suger & Tid per kille
    suger_total_sec = int(round(0.60 * (n + o)))
    suger_per_kille_sec = int(round(suger_total_sec / z)) if z > 0 else 0

    if z > 0:
        tid_per_kille_sec = int(round(
            (m / z) + 2 * (n / z) + 3 * (o / z) + (suger_total_sec / z)
        ))
    else:
        tid_per_kille_sec = 0
    tid_per_kille_str = _ms_str_from_seconds(tid_per_kille_sec)

    # Hångel
    hangel_total_sec = 10800
    hangel_per_kille_sec = int(round(hangel_total_sec / c)) if c > 0 else 0
    hangel_per_kille_str = _ms_str_from_seconds(hangel_per_kille_sec)

    # Hårdhet
    hardhet = (3 if f > 0 else 0) + (4 if g > 0 else 0) + (6 if h > 0 else 0) + (8 if i > 0 else 0)

    # Prenumeranter & ekonomi
    af = _safe_float(rad_in.get("Avgift", 30.0))  # pris per pren (rad)

    if typ in ("Vila på jobbet", "Vila i hemmet"):
        # Exkludera helt
        ae = 0.0
        ag = ah = ai = aj = ak = al = 0.0
        hardhet = 0
    else:
        # Prenumeranter (inkl Känner)
        pren_actions = c + d + e + f + g + h + i + u
        ae = pren_actions * hardhet

        ag = ae * af             # Intäkter (rad)
        ah = c * 120             # Intäkt män (i appen visas som "Kostnad män")

        # Lön Malin – ålder
        ålder = (rad_datum.year - födelsedatum.year
                 - ((rad_datum.month, rad_datum.day) < (födelsedatum.month, födelsedatum.day)))
        if ålder < 18:
            raise ValueError("Ålder < 18 — spärrad rad.")
        if   18 <= ålder <= 25: faktor = 1.20
        elif 26 <= ålder <= 30: faktor = 1.10
        elif 31 <= ålder <= 40: faktor = 1.00
        else:                    faktor = 0.90
        aj_base = max(150, min(800, ae * 0.10))
        aj = max(150, min(800, aj_base * faktor))
        ai = (aj + 120) * u
        ak = ag * 0.20
        al = ag - ah - ai - aj - ak

    return {
        **rad_in,
        "Typ": typ,
        "Känner": u,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Tid Älskar (sek)": extra_alskar_sec,
        "Tid Älskar": _hm_str_from_seconds(extra_alskar_sec),
        "Tid Sover med (sek)": extra_sover_med_sec,
        "Tid Sover med": _hm_str_from_seconds(extra_sover_med_sec),
        "Summa tid (sek)": q_sec,
        "Summa tid": summa_tid_str,
        "Klockan": klockan_str,
        "Totalt Män": z,
        "Suger": suger_total_sec,
        "Suger per kille (sek)": suger_per_kille_sec,
        "Tid per kille (sek)": tid_per_kille_sec,
        "Tid per kille": tid_per_kille_str,
        "Tid kille": tid_per_kille_sec / 60,
        "Hångel (sek/kille)": hangel_per_kille_sec,
        "Hångel (m:s/kille)": hangel_per_kille_str,
        "Hårdhet": hardhet,
        "Prenumeranter": ae,
        "Avgift": af,
        "Intäkter": ag,
        "Intäkt män": ah,
        "Intäkt Känner": ai,
        "Lön Malin": aj,
        "Intäkt Företaget": ak,
        "Vinst": al,
        "Känner Sammanlagt": u,
    }

# Alias med prickar (om någon importerar det namnet).
beräkna_radvärden = berakna_radvarden
