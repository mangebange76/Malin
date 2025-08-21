# live_ui.py
from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime, date

import streamlit as st


def _safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return default


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _compute_age(on_date: date, birth_date: date) -> int:
    try:
        return on_date.year - birth_date.year - (
            (on_date.month, on_date.day) < (birth_date.month, birth_date.day)
        )
    except Exception:
        return 0


def _parse_iso_date(s: str) -> Optional[date]:
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def render_live(base: Dict[str, Any], preview: Dict[str, Any], cfg: Dict[str, Any], rows_df=None) -> None:
    """
    Ritar upp liven. Kräver:
      - base: rå-inputrad (med käll-etiketter redan mappade till labels)
      - preview: resultatet från calc_row_values(...)
      - cfg: nuvarande inställningar (inkl etiketter, BM-mål, Mål vikt, BONUS osv.)
      - rows_df: valfri DataFrame med samtliga rader (används ej här men finns för framtida behov)
    """

    # ------ Etiketter från cfg (med fallback) ------
    LBL_PAPPAN = str(cfg.get("LBL_PAPPAN", "Pappans vänner"))
    LBL_GRANNAR = str(cfg.get("LBL_GRANNAR", "Grannar"))
    LBL_NV = str(cfg.get("LBL_NILS_VANNER", "Nils vänner"))
    LBL_NF = str(cfg.get("LBL_NILS_FAMILJ", "Nils familj"))
    LBL_BEK = str(cfg.get("LBL_BEKANTA", "Bekanta"))
    LBL_ESK = str(cfg.get("LBL_ESK", "Eskilstuna killar"))

    # ------ Datum / Ålder ------
    rad_datum_str = preview.get("Datum", base.get("Datum", ""))
    veckodag = preview.get("Veckodag", "-")

    if isinstance(rad_datum_str, str):
        _d = _parse_iso_date(rad_datum_str) or date.today()
    elif isinstance(rad_datum_str, date):
        _d = rad_datum_str
    else:
        _d = date.today()

    fd = cfg.get("fodelsedatum", date(1970, 1, 1))
    alder = _compute_age(_d, fd)

    st.markdown(f"**Datum/Veckodag:** {rad_datum_str} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

    # ------ “Totalt män inkl allt” (kontroll) ------
    tot_men_including = (
        _safe_int(base.get("Män", 0))
        + _safe_int(base.get("Svarta", 0))
        + _safe_int(base.get(LBL_PAPPAN, 0))
        + _safe_int(base.get(LBL_GRANNAR, 0))
        + _safe_int(base.get(LBL_NV, 0))
        + _safe_int(base.get(LBL_NF, 0))
        + _safe_int(base.get(LBL_BEK, 0))
        + _safe_int(base.get(LBL_ESK, 0))
        + _safe_int(base.get("Bonus deltagit", 0))
        + _safe_int(base.get("Personal deltagit", 0))
    )

    # ------ Överkant: Tid/Klocka/Män ------
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", preview.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", _safe_int(preview.get("Summa tid (sek)", 0)))
    with c2:
        st.metric("Tid/kille", preview.get("Tid per kille", "-"))  # mm:ss
        st.metric("Tid/kille (sek)", _safe_int(preview.get("Tid per kille (sek)", 0)))
    with c3:
        st.metric("Klockan", preview.get("Klockan", "-"))
        st.metric("Totalt män (beräkningar)", _safe_int(preview.get("Totalt Män", 0)))

    # ------ Hångel / Suger / Händer ------
    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", _safe_int(preview.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger/kille (sek)", _safe_float(preview.get("Suger per kille (sek)", 0)))
        st.metric("Händer aktiv", "Ja" if _safe_int(preview.get("Händer aktiv", 0)) else "Nej")
    with c6:
        st.metric("Händer/kille (sek)", _safe_float(preview.get("Händer per kille (sek)", 0)))
        st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

    # ------ Ekonomi ------
    st.markdown("**💵 Ekonomi (live)**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Prenumeranter", _safe_int(preview.get("Prenumeranter", 0)))
        st.metric("Hårdhet", _safe_int(preview.get("Hårdhet", 0)))
    with e2:
        st.metric("Intäkter", f"${_safe_float(preview.get('Intäkter', 0.0)):,.2f}")
        st.metric("Intäkt Känner", f"${_safe_float(preview.get('Intäkt Känner', 0.0)):,.2f}")
    with e3:
        # Kostnad män kan heta "Kostnad män" (ny) eller "Utgift män" (gammalt)
        kostnad_man = preview.get("Kostnad män", preview.get("Utgift män", 0.0))
        st.metric("Kostnad män", f"${_safe_float(kostnad_man):,.2f}")
        st.metric("Lön Malin", f"${_safe_float(preview.get('Lön Malin', 0.0)):,.2f}")
    with e4:
        # Visar både “Intäkt företag” och “Vinst”
        st.metric("Intäkt företag", f"${_safe_float(preview.get('Intäkt företag', 0.0)):,.2f}")
        st.metric("Vinst", f"${_safe_float(preview.get('Vinst', 0.0)):,.2f}")

    # ------ BM-mål / Mål vikt ------
    st.markdown("**🧮 BM & mål**")
    bm1, bm2, bm3 = st.columns(3)
    with bm1:
        bm_mal = cfg.get("BM-mål", cfg.get("BM_MAL", None))
        st.metric("BM-mål (snitt)", f"{_safe_float(bm_mal):.2f}" if bm_mal is not None else "-")
    with bm2:
        mv = cfg.get("Mål vikt", cfg.get("MAL_VIKT", None))
        st.metric("Mål vikt (kg)", f"{_safe_float(mv):.2f}" if mv is not None else "-")
    with bm3:
        st.metric("Älskar (sek)", _safe_int(preview.get("Tid Älskar (sek)", 0)))

    # ------ Bonus / Super bonus ------
    st.markdown("**🎯 Bonus & Super bonus**")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.metric("Bonus kvar", _safe_int(cfg.get("BONUS_AVAILABLE", 0)))
    with b2:
        st.metric("Bonus % (decimal)", _safe_float(cfg.get("BONUS_PCT", 0.0)))
    with b3:
        st.metric("Super bonus ack", _safe_int(cfg.get("SUPER_BONUS_ACC", 0)))
    with b4:
        st.metric("Super bonus % (decimal)", _safe_float(cfg.get("SUPER_BONUS_PCT", 0.0)))

    # ------ Källor (etiketter) ------
    st.markdown("**👥 Källor (live)**")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric(LBL_PAPPAN, _safe_int(base.get(LBL_PAPPAN, 0)))
    with k2:
        st.metric(LBL_GRANNAR, _safe_int(base.get(LBL_GRANNAR, 0)))
    with k3:
        st.metric(LBL_NV, _safe_int(base.get(LBL_NV, 0)))
    with k4:
        st.metric(LBL_NF, _safe_int(base.get(LBL_NF, 0)))
    with k5:
        st.metric(LBL_BEK, _safe_int(base.get(LBL_BEK, 0)))
    with k6:
        st.metric(LBL_ESK, _safe_int(base.get(LBL_ESK, 0)))

    st.caption("Obs: Älskar/Sover-med-tider ingår inte i scenens 'Summa tid', men påverkar klockan. "
               "Händer per kille visas separat och påverkar inte 'Tid/kille' i denna vy.")
