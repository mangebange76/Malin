# live_ui.py
import streamlit as st
from datetime import datetime
from berakningar import calc_row_values

# Keys used by app.py
CFG_KEY = "CFG"
SCENEINFO_KEY = "CURRENT_SCENE"

def _get_label(cfg, key, fallback):
    return cfg.get(key, fallback)

def _safe_get_state(key, default=0):
    return int(st.session_state.get(key, default))

def _build_base(cfg: dict) -> dict:
    """Build base row from current inputs + scene info (no Sheets I/O)."""
    # scene/date/weekday (prepared by app)
    scen_nr, d, veckodag = st.session_state.get(
        SCENEINFO_KEY,
        (1, datetime.today().date(), ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][datetime.today().weekday()])
    )

    # labels (rename-safe)
    LBL_PAPPAN = _get_label(cfg, "LBL_PAPPAN", "Pappans vänner")
    LBL_GRANNAR = _get_label(cfg, "LBL_GRANNAR", "Grannar")
    LBL_NV = _get_label(cfg, "LBL_NILS_VANNER", "Nils vänner")
    LBL_NF = _get_label(cfg, "LBL_NILS_FAMILJ", "Nils familj")
    LBL_BEK = _get_label(cfg, "LBL_BEKANTA", "Bekanta")
    LBL_ESK = _get_label(cfg, "LBL_ESK", "Eskilstuna killar")

    base = {
        "Datum": d.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen_nr,
        "Typ": st.session_state.get("SCENARIO", "Ny scen"),

        "Män": _safe_get_state("in_man"),
        "Svarta": _safe_get_state("in_svarta"),
        "Fitta": _safe_get_state("in_fitta"),
        "Rumpa": _safe_get_state("in_rumpa"),
        "DP": _safe_get_state("in_dp"),
        "DPP": _safe_get_state("in_dpp"),
        "DAP": _safe_get_state("in_dap"),
        "TAP": _safe_get_state("in_tap"),

        "Tid S": _safe_get_state("in_tid_s"),
        "Tid D": _safe_get_state("in_tid_d"),
        "Vila":  _safe_get_state("in_vila"),

        "DT tid (sek/kille)":  _safe_get_state("in_dt_tid"),
        "DT vila (sek/kille)": _safe_get_state("in_dt_vila"),

        "Älskar":    _safe_get_state("in_alskar"),
        "Sover med": _safe_get_state("in_sover"),

        # rename-safe sources
        LBL_PAPPAN: _safe_get_state("in_pappan"),
        LBL_GRANNAR: _safe_get_state("in_grannar"),
        LBL_NV: _safe_get_state("in_nils_vanner"),
        LBL_NF: _safe_get_state("in_nils_familj"),
        LBL_BEK: _safe_get_state("in_bekanta"),
        LBL_ESK: _safe_get_state("in_eskilstuna"),

        "Bonus deltagit":    _safe_get_state("in_bonus_deltagit"),
        "Personal deltagit": _safe_get_state("in_personal_deltagit"),

        # ekonomi/meta
        "Avgift": float(cfg.get("avgift_usd", 30.0)),
        "PROD_STAFF": int(cfg.get("PROD_STAFF", 0)),

        # labels in base so beräkningar hittar dem
        "LBL_PAPPAN": LBL_PAPPAN,
        "LBL_GRANNAR": LBL_GRANNAR,
        "LBL_NILS_VANNER": LBL_NV,
        "LBL_NILS_FAMILJ": LBL_NF,
        "LBL_BEKANTA": LBL_BEK,
        "LBL_ESK": LBL_ESK,

        # Händer aktiv: read if present, else default 1 (på)
        "Händer aktiv": int(st.session_state.get("in_hander_aktiv", 1)),
    }

    # aggregate “Känner”
    base["Känner"] = int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) + int(base[LBL_NV]) + int(base[LBL_NF])

    # meta for calc
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = cfg.get("fodelsedatum")
    base["_starttid"]     = cfg.get("starttid")

    # also pass max-values if they exist in cfg (for Känner sammanlagt)
    base["MAX_PAPPAN"]       = int(cfg.get("MAX_PAPPAN", 0))
    base["MAX_GRANNAR"]      = int(cfg.get("MAX_GRANNAR", 0))
    base["MAX_NILS_VANNER"]  = int(cfg.get("MAX_NILS_VANNER", 0))
    base["MAX_NILS_FAMILJ"]  = int(cfg.get("MAX_NILS_FAMILJ", 0))

    return base, (LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK)

def render_live_and_preview(cfg: dict, rows_df):
    """Build preview via calc_row_values and render the live metrics block.
    Returns (base, preview) so app.py can save/export the same dict.
    """
    base, lbls = _build_base(cfg)
    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK = lbls

    try:
        preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
    except TypeError:
        preview = calc_row_values(base, base["_rad_datum"], cfg.get("fodelsedatum"), cfg.get("starttid"))

    # ---------------- Live UI ----------------
    st.markdown("---")
    st.subheader("🔎 Live")

    # Date / age line
    rad_datum = preview.get("Datum", base["Datum"])
    veckodag = preview.get("Veckodag", "-")
    try:
        _d = datetime.fromisoformat(rad_datum).date() if isinstance(rad_datum, str) else base["_rad_datum"]
    except Exception:
        _d = base["_rad_datum"]
    fd = cfg.get("fodelsedatum")
    if fd:
        alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
    else:
        alder = "-"
    st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder}")

    # Time & totals
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", preview.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    with c2:
        # show both times (utan/med händer)
        st.metric("Tid/kille (utan händer)", preview.get("Tid per kille (utan händer)", "-"))
        st.metric("Tid/kille (sek, utan händer)", int(preview.get("Tid per kille (sek, utan händer)", 0)))
    with c3:
        st.metric("Tid/kille (med händer)", preview.get("Tid per kille", "-"))
        st.metric("Tid/kille (sek, med händer)", int(preview.get("Tid per kille (sek)", 0)))

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger/kille (sek) (0.8-regel)", int(preview.get("Suger per kille (sek)", 0)))
        st.metric("Händer/kille (sek) (2× suger)", int(preview.get("Händer per kille (sek)", 0)))
    with c6:
        st.metric("Klockan", preview.get("Klockan", "-"))
        st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män", 0)))

    # Economy
    st.markdown("**💵 Ekonomi (live)**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Prenumeranter", int(preview.get("Prenumeranter", 0)))
        st.metric("Hårdhet", int(preview.get("Hårdhet", 0)))
    with e2:
        st.metric("Intäkter", f"${float(preview.get('Intäkter', 0)):,.2f}")
        st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner', 0)):,.2f}")
    with e3:
        st.metric("Kostnad män", f"${float(preview.get('Kostnad män', 0)):,.2f}")
        st.metric("Lön Malin", f"${float(preview.get('Lön Malin', 0)):,.2f}")
    with e4:
        st.metric("Vinst", f"${float(preview.get('Vinst', 0)):,.2f}")
        st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

    # Sources breakdown with labels
    st.markdown("**👥 Källor (live)**")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: st.metric(LBL_PAPPAN, int(base.get(LBL_PAPPAN, 0)))
    with k2: st.metric(LBL_GRANNAR, int(base.get(LBL_GRANNAR, 0)))
    with k3: st.metric(LBL_NV, int(base.get(LBL_NV, 0)))
    with k4: st.metric(LBL_NF, int(base.get(LBL_NF, 0)))
    with k5: st.metric(LBL_BEK, int(base.get(LBL_BEK, 0)))
    with k6: st.metric(LBL_ESK, int(base.get(LBL_ESK, 0)))

    st.caption("Obs: Älskar/Sover-med-tider ingår inte i 'Summa tid' men påverkar 'Klockan inkl älskar/sover' som visas i beräkningar.")

    return base, preview
