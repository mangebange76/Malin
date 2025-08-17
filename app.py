# ---------- Hjälp (etikett) ----------
def _L(txt: str) -> str:
    try:
        return LABELS.get(txt, txt)
    except Exception:
        return txt

# ---------- Scenario-väljare (ingen rerun, inga skrivningar) ----------
def _get_min_max(colname: str):
    """Läser min/max för en kolumn från Data-bladet (enstaka läsning när vi behöver slumpa)."""
    try:
        all_rows = _retry_call(sheet.get_all_records)
    except Exception:
        return 0, 0
    vals = [_safe_int(r.get(colname, 0), 0) for r in all_rows]
    if not vals:
        return 0, 0
    return min(vals), max(vals)

def _rand_40_60_of_max(mx: int) -> int:
    try: mx = int(mx)
    except Exception: mx = 0
    if mx <= 0: return 0
    lo = max(0, int(round(mx * 0.40)))
    hi = max(lo, int(round(mx * 0.60)))
    return random.randint(lo, hi)

def _rand_eskilstuna_20_40() -> int:
    r = random.random()
    return random.randint(20, 30) if r < 0.30 else random.randint(31, 40)

def _suggest_personal_deltagit() -> int:
    return 80  # enligt spec; undantag för dag 6–7 hanteras där rader skapas

def _fill_inputs_from_scenario(scen: str):
    """Sätter enbart session_state – inga Sheets-skrivningar, ingen rerun."""
    if scen == "Ny scen":
        st.session_state.update({
            "in_man": 0, "in_svarta": 0, "in_fitta": 0, "in_rumpa": 0,
            "in_dp": 0, "in_dpp": 0, "in_dap": 0, "in_tap": 0,
            "input_pappan": 0, "input_grannar": 0, "input_nils_vanner": 0, "input_nils_familj": 0,
            "input_bekanta": 0, "input_eskilstuna": 0,
            "input_bonus_deltagit": 0, "input_personal_deltagit": _suggest_personal_deltagit(),
            "in_alskar": 0, "in_sover": 0,
            "in_tid_s": 60, "in_tid_d": 60, "in_vila": 7, "in_dt_tid": 60, "in_dt_vila": 3,
        })

    elif scen == "Vila på jobbet":
        st.session_state.update({
            "in_man": 0, "in_svarta": 0, "in_fitta": 0, "in_rumpa": 0,
            "in_dp": 0, "in_dpp": 0, "in_dap": 0, "in_tap": 0,
            "input_pappan": _rand_40_60_of_max(CFG["MAX_PAPPAN"]),
            "input_grannar": _rand_40_60_of_max(CFG["MAX_GRANNAR"]),
            "input_nils_vanner": _rand_40_60_of_max(CFG["MAX_NILS_VANNER"]),
            "input_nils_familj": _rand_40_60_of_max(CFG["MAX_NILS_FAMILJ"]),
            "input_bekanta": _rand_40_60_of_max(CFG["MAX_BEKANTA"]),
            "input_eskilstuna": _rand_eskilstuna_20_40(),
            "input_bonus_deltagit": 0,
            "input_personal_deltagit": 80,
            "in_alskar": 12, "in_sover": 1,
            "in_tid_s": 0, "in_tid_d": 0, "in_vila": 0, "in_dt_tid": 60, "in_dt_vila": 3,
        })

    elif scen == "Vila i hemmet":
        st.session_state.update({
            "in_man": 0, "in_svarta": 0, "in_fitta": 0, "in_rumpa": 0,
            "in_dp": 0, "in_dpp": 0, "in_dap": 0, "in_tap": 0,
            "input_pappan": _rand_40_60_of_max(CFG["MAX_PAPPAN"]),
            "input_grannar": _rand_40_60_of_max(CFG["MAX_GRANNAR"]),
            "input_nils_vanner": _rand_40_60_of_max(CFG["MAX_NILS_VANNER"]),
            "input_nils_familj": _rand_40_60_of_max(CFG["MAX_NILS_FAMILJ"]),
            "input_bekanta": _rand_40_60_of_max(CFG["MAX_BEKANTA"]),
            "input_eskilstuna": _rand_eskilstuna_20_40(),
            "input_bonus_deltagit": 0,
            "input_personal_deltagit": 80,  # (dag 6–7 = 0 hanteras i skapandet sedan)
            "in_alskar": 6, "in_sover": 0,
            "in_tid_s": 0, "in_tid_d": 0, "in_vila": 0, "in_dt_tid": 60, "in_dt_vila": 3,
        })

    elif scen == "Slumpa scen vit":
        st.session_state["in_man"] = random.randint(*_get_min_max("Män"))
        st.session_state["in_fitta"] = random.randint(*_get_min_max("Fitta"))
        st.session_state["in_rumpa"] = random.randint(*_get_min_max("Rumpa"))
        st.session_state["in_dp"] = random.randint(*_get_min_max("DP"))
        st.session_state["in_dpp"] = random.randint(*_get_min_max("DPP"))
        st.session_state["in_dap"] = random.randint(*_get_min_max("DAP"))
        st.session_state["in_tap"] = random.randint(*_get_min_max("TAP"))
        st.session_state["input_pappan"] = random.randint(*_get_min_max("Pappans vänner"))
        st.session_state["input_grannar"] = random.randint(*_get_min_max("Grannar"))
        st.session_state["input_nils_vanner"] = random.randint(*_get_min_max("Nils vänner"))
        st.session_state["input_nils_familj"] = random.randint(*_get_min_max("Nils familj"))
        st.session_state["input_bekanta"] = random.randint(*_get_min_max("Bekanta"))
        st.session_state["input_eskilstuna"] = random.randint(*_get_min_max("Eskilstuna killar"))
        st.session_state["in_svarta"] = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"] = 1
        st.session_state["input_personal_deltagit"] = 80

    elif scen == "Slumpa scen svart":
        st.session_state["in_fitta"] = random.randint(*_get_min_max("Fitta"))
        st.session_state["in_rumpa"] = random.randint(*_get_min_max("Rumpa"))
        st.session_state["in_dp"] = random.randint(*_get_min_max("DP"))
        st.session_state["in_dpp"] = random.randint(*_get_min_max("DPP"))
        st.session_state["in_dap"] = random.randint(*_get_min_max("DAP"))
        st.session_state["in_tap"] = random.randint(*_get_min_max("TAP"))
        st.session_state["in_svarta"] = random.randint(*_get_min_max("Svarta"))
        st.session_state.update({
            "in_man": 0,
            "input_pappan": 0, "input_grannar": 0, "input_nils_vanner": 0, "input_nils_familj": 0,
            "input_bekanta": 0, "input_eskilstuna": 0,
            "in_alskar": 8, "in_sover": 1,
            "input_personal_deltagit": 80
        })

# UI: rullista + knapp
scenario = st.selectbox(
    "Välj scenario",
    ["Ny scen", "Vila på jobbet", "Vila i hemmet", "Slumpa scen vit", "Slumpa scen svart"],
    index=0
)
if st.button("Fyll fält enligt scenario"):
    _fill_inputs_from_scenario(scenario)

# ---------- Inmatning i begärd ordning (läser/uppdaterar bara session_state) ----------
män    = st.number_input(_L("Män"), min_value=0, step=1, value=st.session_state.get("in_man", 0), key="in_man")
svarta = st.number_input(_L("Svarta"), min_value=0, step=1, value=st.session_state.get("in_svarta", 0), key="in_svarta")
fitta  = st.number_input("Fitta",  min_value=0, step=1, value=st.session_state.get("in_fitta", 0), key="in_fitta")
rumpa  = st.number_input("Rumpa",  min_value=0, step=1, value=st.session_state.get("in_rumpa", 0), key="in_rumpa")
dp     = st.number_input("DP",     min_value=0, step=1, value=st.session_state.get("in_dp", 0), key="in_dp")
dpp    = st.number_input("DPP",    min_value=0, step=1, value=st.session_state.get("in_dpp", 0), key="in_dpp")
dap    = st.number_input("DAP",    min_value=0, step=1, value=st.session_state.get("in_dap", 0), key="in_dap")
tap    = st.number_input("TAP",    min_value=0, step=1, value=st.session_state.get("in_tap", 0), key="in_tap")

lbl_p  = f"{_L('Pappans vänner')} (max {int(CFG['MAX_PAPPAN'])})"
lbl_g  = f"{_L('Grannar')} (max {int(CFG['MAX_GRANNAR'])})"
lbl_nv = f"{_L('Nils vänner')} (max {int(CFG['MAX_NILS_VANNER'])})"
lbl_nf = f"{_L('Nils familj')} (max {int(CFG['MAX_NILS_FAMILJ'])})"
lbl_bk = f"{_L('Bekanta')} (max {int(CFG['MAX_BEKANTA'])})"

pappans_vänner = st.number_input(lbl_p,  min_value=0, step=1, value=st.session_state.get("input_pappan", 0), key="input_pappan")
grannar        = st.number_input(lbl_g,  min_value=0, step=1, value=st.session_state.get("input_grannar", 0), key="input_grannar")
nils_vänner    = st.number_input(lbl_nv, min_value=0, step=1, value=st.session_state.get("input_nils_vanner", 0), key="input_nils_vanner")
nils_familj    = st.number_input(lbl_nf, min_value=0, step=1, value=st.session_state.get("input_nils_familj", 0), key="input_nils_familj")
bekanta        = st.number_input(_L("Bekanta"), min_value=0, step=1, value=st.session_state.get("input_bekanta", 0), key="input_bekanta")
eskilstuna_killar = st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, value=st.session_state.get("input_eskilstuna", 0), key="input_eskilstuna")

# Bonus deltagit (radnivå) + Personal deltagit
bonus_deltagit    = st.number_input(_L("Bonus deltagit"), min_value=0, step=1, value=st.session_state.get("input_bonus_deltagit", 0), key="input_bonus_deltagit")
personal_deltagit = st.number_input(_L("Personal deltagit"), min_value=0, step=1, value=st.session_state.get("input_personal_deltagit", 80), key="input_personal_deltagit")

# Älskar / Sover
älskar    = st.number_input("Älskar",                min_value=0, step=1, value=st.session_state.get("in_alskar", 0), key="in_alskar")
sover_med = st.number_input("Sover med (0 eller 1)", min_value=0, max_value=1, step=1, value=st.session_state.get("in_sover", 0), key="in_sover")

# Tider
tid_s  = st.number_input("Tid S (sek)",         min_value=0, step=1, value=st.session_state.get("in_tid_s", 60), key="in_tid_s")
tid_d  = st.number_input("Tid D (sek)",         min_value=0, step=1, value=st.session_state.get("in_tid_d", 60), key="in_tid_d")
vila   = st.number_input("Vila (sek)",          min_value=0, step=1, value=st.session_state.get("in_vila", 7), key="in_vila")
dt_tid = st.number_input("DT tid (sek/kille)",  min_value=0, step=1, value=st.session_state.get("in_dt_tid", 60), key="in_dt_tid")
dt_vila= st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=st.session_state.get("in_dt_vila", 3),  key="in_dt_vila")

# ---------- Live-beräkning & visning (ingen skrivning till Sheets) ----------

# Hjälpare: radräkning (en gång) för att få scen-nummer och datum
def _ensure_rowcount():
    if "ROW_COUNT" not in st.session_state:
        try:
            vals = _retry_call(sheet.col_values, 1)  # A-kolumn (Datum)
            st.session_state.ROW_COUNT = max(0, len(vals) - 1) if (vals and vals[0] == "Datum") else len(vals)
        except Exception:
            st.session_state.ROW_COUNT = 0

def _next_scene_number():
    return st.session_state.ROW_COUNT + 1

def _scene_date_and_weekday(scene_no: int):
    d = CFG["startdatum"] + timedelta(days=scene_no - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

_ensure_rowcount()
scen = _next_scene_number()
rad_datum, veckodag = _scene_date_and_weekday(scen)

# Här bygger vi en "grund"-rad baserat på inputfälten (utan att spara).
kanner = (pappans_vänner or 0) + (grannar or 0) + (nils_vänner or 0) + (nils_familj or 0)

grund_preview = {
    "Typ": "",  # sätts vid spar/knapp om du vill
    "Veckodag": veckodag, "Scen": scen,
    "Män": män, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
    "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
    "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
    "Älskar": älskar, "Sover med": sover_med,
    "Känner": kanner,
    "Pappans vänner": pappans_vänner, "Grannar": grannar,
    "Nils vänner": nils_vänner, "Nils familj": nils_familj, "Bekanta": bekanta, "Eskilstuna killar": eskilstuna_killar,
    "Bonus deltagit": bonus_deltagit, "Personal deltagit": personal_deltagit,
    "Nils": 0,
    "Avgift": float(CFG["avgift_usd"]),
}

def _calc_preview(grund):
    if not callable(calc_row_values):
        return {}
    try:
        return calc_row_values(grund, rad_datum, CFG["födelsedatum"], CFG["starttid"])
    except Exception as e:
        st.warning(f"Förhandsberäkning misslyckades: {e}")
        return {}

preview = _calc_preview(grund_preview)

# Malins ålder vid rad_datum
def _age_on(dob: date, on_date: date) -> int:
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))

malins_alder = _age_on(CFG["födelsedatum"], rad_datum)

st.markdown("---")
st.subheader("🔎 Förhandsvisning (innan spar)")
cA, cB, cC = st.columns(3)
with cA:
    st.metric("Datum / veckodag", f"{rad_datum} / {veckodag}")
    st.metric("Malins ålder (år)", malins_alder)
    st.metric("Totalt män (raden)", int(preview.get("Totalt Män", 0)))
with cB:
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    st.metric("Summa tid (h:m)", preview.get("Summa tid", "-"))
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with cC:
    st.metric("Tid per kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    st.metric("Tid per kille", preview.get("Tid per kille", "-"))
    st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

st.caption(f"Klockan blir: {preview.get('Klockan','-')} (start {CFG['starttid']})")

# Ekonomi – bara livevisning
st.markdown("#### 💵 Ekonomi (live)")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Avgift (rad)", _usd(preview.get("Avgift", CFG['avgift_usd'])))
with e2:
    st.metric("Intäkter (rad)", _usd(preview.get("Intäkter", 0)))
    st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
with e3:
    st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
    st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
with e4:
    st.metric("Vinst (rad)", _usd(preview.get("Vinst", 0)))

# ---------- Spara / Auto-Max (skriver ENDAST när du trycker på "Spara raden") ----------

def _store_pending(grund, scen, rad_datum, veckodag, over_max):
    st.session_state["PENDING_SAVE"] = {
        "grund": grund,
        "scen": scen,
        "rad_datum": str(rad_datum),
        "veckodag": veckodag,
        "over_max": over_max
    }

def _parse_date_for_save(d):
    return d if isinstance(d, date) else datetime.strptime(d, "%Y-%m-%d").date()

def _save_row(grund, rad_datum, veckodag):
    try:
        base = dict(grund)
        # säkerställ avgift vid spar
        base.setdefault("Avgift", float(CFG["avgift_usd"]))
        ber = calc_row_values(base, rad_datum, CFG["födelsedatum"], CFG["starttid"])
        ber["Datum"] = rad_datum.isoformat()
    except Exception as e:
        st.error(f"Beräkningen misslyckades vid sparning: {e}")
        return

    row = [ber.get(col, "") for col in KOLUMNER]
    _retry_call(sheet.append_row, row)
    # håll endast lokal räkning – ingen extra läsning
    st.session_state.ROW_COUNT = st.session_state.get("ROW_COUNT", 0) + 1

    # Kvitto
    ålder = rad_datum.year - CFG["födelsedatum"].year - (
        (rad_datum.month, rad_datum.day) < (CFG["födelsedatum"].month, CFG["födelsedatum"].day)
    )
    typ_label = ber.get("Typ") or "Händelse"
    st.success(
        f"✅ Rad sparad ({typ_label}). Datum {rad_datum} ({veckodag}), "
        f"Ålder {ålder} år, Klockan {ber.get('Klockan','-')}"
    )

# uppdatera Inställningar bara om användaren accepterar auto-max
def _save_setting(key: str, value: str, label: str|None=None):
    recs = _retry_call(settings_ws.get_all_records)
    keys = [ (r.get("Key") or "") for r in recs ]
    try:
        idx = keys.index(key)  # 0-baserat (A2..)
        rowno = idx + 2
    except ValueError:
        rowno = len(recs) + 2
        _retry_call(settings_ws.update, f"A{rowno}:C{rowno}", [[key, value, label or ""]])
        return
    _retry_call(settings_ws.update, f"B{rowno}", [[value]])
    if label is not None:
        _retry_call(settings_ws.update, f"C{rowno}", [[label]])

def _apply_auto_max_and_save(pending):
    for _, info in pending["over_max"].items():
        key = info["max_key"]
        new_val = int(info["new_value"])
        _save_setting(key, str(new_val))
        CFG[key] = new_val
    _save_row(pending["grund"], _parse_date_for_save(pending["rad_datum"]), pending["veckodag"])

# Spara-knapp
save_clicked = st.button("💾 Spara raden")
if save_clicked:
    over_max = {}
    # kolla bara källor med max
    if grund_preview.get("Pappans vänner", 0) > int(CFG["MAX_PAPPAN"]):
        over_max[ LABELS.get('Pappans vänner','Pappans vänner') ] = {
            "current_max": int(CFG["MAX_PAPPAN"]), "new_value": grund_preview["Pappans vänner"], "max_key": "MAX_PAPPAN"
        }
    if grund_preview.get("Grannar", 0) > int(CFG["MAX_GRANNAR"]):
        over_max[ LABELS.get('Grannar','Grannar') ] = {
            "current_max": int(CFG["MAX_GRANNAR"]), "new_value": grund_preview["Grannar"], "max_key": "MAX_GRANNAR"
        }
    if grund_preview.get("Nils vänner", 0) > int(CFG["MAX_NILS_VANNER"]):
        over_max[ LABELS.get('Nils vänner','Nils vänner') ] = {
            "current_max": int(CFG["MAX_NILS_VANNER"]), "new_value": grund_preview["Nils vänner"], "max_key": "MAX_NILS_VANNER"
        }
    if grund_preview.get("Nils familj", 0) > int(CFG["MAX_NILS_FAMILJ"]):
        over_max[ LABELS.get('Nils familj','Nils familj') ] = {
            "current_max": int(CFG["MAX_NILS_FAMILJ"]), "new_value": grund_preview["Nils familj"], "max_key": "MAX_NILS_FAMILJ"
        }
    if grund_preview.get("Bekanta", 0) > int(CFG["MAX_BEKANTA"]):
        over_max[ LABELS.get('Bekanta','Bekanta') ] = {
            "current_max": int(CFG["MAX_BEKANTA"]), "new_value": grund_preview["Bekanta"], "max_key": "MAX_BEKANTA"
        }

    if over_max:
        _store_pending(grund_preview, scen, rad_datum, veckodag, over_max)
    else:
        _save_row(grund_preview, rad_datum, veckodag)

# Auto-Max dialog (visas bara om något överskred max)
if "PENDING_SAVE" in st.session_state:
    pending = st.session_state["PENDING_SAVE"]
    st.warning("Du har angett värden som överstiger max. Vill du uppdatera maxvärden och spara raden?")
    for f, info in pending["over_max"].items():
        st.write(f"- **{f}**: max {info['current_max']} → **{info['new_value']}**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Ja, uppdatera max och spara"):
            try:
                _apply_auto_max_and_save(pending)
            except Exception as e:
                st.error(f"Kunde inte spara: {e}")
            finally:
                st.session_state.pop("PENDING_SAVE", None)
                st.experimental_rerun()
    with c2:
        if st.button("✋ Nej, avbryt"):
            st.session_state.pop("PENDING_SAVE", None)
            st.info("Sparning avbröts. Justera värden eller max i sidopanelen.")

# ---------- Scenario-knappar (fyller inputs, sparar inte direkt) ----------

def _fill_inputs_from_dict(vals: dict, scen: str):
    for key, val in vals.items():
        if key in st.session_state["inputs"]:
            st.session_state["inputs"][key] = val
    st.session_state["inputs"]["Typ"] = scen
    st.experimental_rerun()

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    if st.button("🎬 Ny scen"):
        vals = {k: 0 for k in st.session_state["inputs"].keys()}
        vals["Typ"] = "Ny scen"
        vals["Tid Älskar?"] = 1800
        vals["Tid Sover med (sek)"] = 3600
        vals["Bonus deltagit"] = int(int(CFG["nya_prenumeranter"])*0.4)
        vals["Personal deltagit"] = 80
        _fill_inputs_from_dict(vals, "Ny scen")

with c2:
    if st.button("🛠️ Vila jobbet"):
        vals = {k: 0 for k in st.session_state["inputs"].keys()}
        vals["Typ"] = "Vila jobbet"
        vals["DT vila (sek/kille)"] = 900
        vals["Personal deltagit"] = 80
        _fill_inputs_from_dict(vals, "Vila jobbet")

with c3:
    if st.button("🏠 Vila hemmet"):
        vals = {k: 0 for k in st.session_state["inputs"].keys()}
        vals["Typ"] = "Vila hemmet"
        vals["Tid Sover med (sek)"] = 3600
        vals["Personal deltagit"] = 0
        vals["Bonus deltagit"] = int(int(CFG["nya_prenumeranter"])*0.4)
        _fill_inputs_from_dict(vals, "Vila hemmet")

with c4:
    if st.button("⚪ Slumpa vit"):
        vals = {k: 0 for k in st.session_state["inputs"].keys()}
        vals["Typ"] = "Slump vit"
        vals["Tid Älskar?"] = random.choice([600,1200,1800])
        vals["Tid Sover med (sek)"] = random.choice([1800,2400,3000])
        vals["Bonus deltagit"] = int(int(CFG["nya_prenumeranter"])*0.4)
        vals["Personal deltagit"] = 80
        _fill_inputs_from_dict(vals, "Slump vit")

with c5:
    if st.button("⚫ Slumpa svart"):
        vals = {k: 0 for k in st.session_state["inputs"].keys()}
        vals["Typ"] = "Slump svart"
        vals["Tid Älskar?"] = random.choice([1200,1800,2400])
        vals["Tid Sover med (sek)"] = random.choice([2400,3000,3600])
        vals["Bonus deltagit"] = int(int(CFG["nya_prenumeranter"])*0.4)
        vals["Personal deltagit"] = 80
        # BONUS = alltid svarta i statistiken
        vals["Svarta"] = vals.get("Bonus deltagit", 0)
        _fill_inputs_from_dict(vals, "Slump svart")
