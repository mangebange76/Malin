# statistik.py
from typing import List, Dict

def totalt_man_stat(row: Dict, max_cfg: Dict) -> int:
    """
    Totalt Män (statistik-nivå):
    = kolumn Män
    + SUM(maxvärden för Känner) från inställningar
    + kolumn Svarta
    + maxvärde Bekanta (inställningar)
    + kolumn Eskilstuna killar
    + kolumn Bonus deltagit
    + maxvärde Personal (inställningar)
    """
    man   = int(row.get("Män", 0) or 0)
    svart = int(row.get("Svarta", 0) or 0)
    esk   = int(row.get("Eskilstuna killar", 0) or 0)
    bonus = int(row.get("Bonus deltagit", 0) or 0)

    max_p = int(max_cfg.get("MAX_PAPPAN", 0) or 0)
    max_g = int(max_cfg.get("MAX_GRANNAR", 0) or 0)
    max_nv= int(max_cfg.get("MAX_NILS_VANNER", 0) or 0)
    max_nf= int(max_cfg.get("MAX_NILS_FAMILJ", 0) or 0)
    max_kanner = max_p + max_g + max_nv + max_nf

    max_bek = int(max_cfg.get("MAX_BEKANTA", 0) or 0)
    max_pers= int(max_cfg.get("MAX_PERSONAL", 0) or 0)

    return man + max_kanner + svart + max_bek + esk + bonus + max_pers


def andel_svarta_procent_stat(row: Dict, max_cfg: Dict) -> float:
    """
    Andel Svarta (%) på statistik-nivå:
    = Svarta / Totalt Män (stat) * 100
    """
    svart = int(row.get("Svarta", 0) or 0)
    tot   = totalt_man_stat(row, max_cfg)
    return 0.0 if tot <= 0 else (100.0 * svart / tot)


def kanner_sammanlagt_stat(max_cfg: Dict) -> int:
    """
    Känner sammanlagt (stat) = SUM(maxvärden) för pappan/grannar/nils vänner/nils familj.
    """
    return int(max_cfg.get("MAX_PAPPAN", 0) or 0) \
         + int(max_cfg.get("MAX_GRANNAR", 0) or 0) \
         + int(max_cfg.get("MAX_NILS_VANNER", 0) or 0) \
         + int(max_cfg.get("MAX_NILS_FAMILJ", 0) or 0)


def berakna_statistik_for_rad(row: Dict, max_cfg: Dict) -> Dict:
    """
    Returnerar ett litet paket med statistiknyckeltal för EN rad.
    max_cfg kommer från dina Inställningar (maxvärden, personal, bekanta etc.)
    """
    return {
        "Totalt Män (stat)": totalt_man_stat(row, max_cfg),
        "Andel Svarta (%)":  andel_svarta_procent_stat(row, max_cfg),
        "Känner sammanlagt": kanner_sammanlagt_stat(max_cfg),
    }


def berakna_statistik_for_df(rows: List[Dict], max_cfg: Dict) -> Dict:
    """
    Summerar/medelvärden över många rader (om du vill ha aggregerad statistik).
    """
    out = {
        "Sum Totalt Män (stat)": 0,
        "Medel Andel Svarta (%)": 0.0,
        "Känner sammanlagt": kanner_sammanlagt_stat(max_cfg),
        "Antal rader": len(rows),
    }
    if not rows:
        return out

    tot_stat_sum = 0
    andel_list = []
    for r in rows:
        tot_stat = totalt_man_stat(r, max_cfg)
        tot_stat_sum += tot_stat
        andel_list.append(andel_svarta_procent_stat(r, max_cfg))

    out["Sum Totalt Män (stat)"] = tot_stat_sum
    out["Medel Andel Svarta (%)"] = sum(andel_list)/len(andel_list) if andel_list else 0.0
    return out
