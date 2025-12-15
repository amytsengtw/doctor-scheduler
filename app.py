import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date
import json
import hashlib

# --- 1. Page Configuration ---
st.set_page_config(page_title="Dual-Track Rostering System (Points Edition)", layout="wide")

st.title("🏥 OB/GYN Dual-Track Rostering System (v4.0)")
st.caption("Feature: Weighted Point System (Weekday=1, Weekend=2, Target<=8) | English Codebase")

# --- 2. Session State Management ---
default_state = {
    "year": 2025,
    "month": 12,
    "vs_list": "Dr.Ko(VS), Dr.Strange(VS)",
    "r_list": "Yang(R3), Bon(R2)",
    "pgy_list": "Ming(PGY), Hua(PGY), John(PGY)",
    "int_list": "RookieA(Int), RookieB(Int)",
    # Hard Constraints (Absolute Leaves)
    "vs_leaves": {}, "r_leaves": {}, "pgy_leaves": {}, "int_leaves": {},
    # Soft Constraints (Wishes/No-Go)
    "vs_wishes": {},  "vs_nogo": {},
    "r_wishes": {},   "r_nogo": {},
    "pgy_wishes": {}, "pgy_nogo": {},
    "int_wishes": {}, "int_nogo": {}
}

for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. Sidebar: JSON I/O ---
st.sidebar.header("📂 Config I/O")
def get_current_config():
    return {k: st.session_state[k] for k in default_state.keys()}

config_json = json.dumps(get_current_config(), ensure_ascii=False, indent=2)
st.sidebar.download_button("💾 Download Config (JSON)", config_json, "roster_config.json", "application/json")

uploaded_file = st.sidebar.file_uploader("📂 Upload Config (JSON)", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        for key in default_state.keys():
            if key in data:
                st.session_state[key] = data[key]
        st.sidebar.success("Config loaded successfully!")
    except Exception as e:
        st.sidebar.error(f"Error loading config: {e}")

st.sidebar.markdown("---")
st.sidebar.header("📅 Date Settings")
year = st.sidebar.number_input("Year", min_value=2024, max_value=2030, key="year")
month = st.sidebar.number_input("Month", min_value=1, max_value=12, key="month")
days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.markdown("---")
st.sidebar.header("🔢 Solver Settings")
num_solutions = st.sidebar.slider("Number of Solutions", min_value=1, max_value=5, value=1)

# --- 4. Staff & Constraints UI ---
st.subheader("1. Staff & Constraints")
tab1, tab2 = st.tabs(["🔴 Big Shift (Delivery)", "🔵 Small Shift (General)"])
with tab1:
    c1, c2 = st.columns(2)
    vs_staff = [x.strip() for x in st.text_area("VS List", key="vs_list").split(",") if x.strip()]
    r_staff = [x.strip() for x in st.text_area("R List", key="r_list").split(",") if x.strip()]
with tab2:
    c3, c4 = st.columns(2)
    pgy_staff = [x.strip() for x in st.text_area("PGY List", key="pgy_list").split(",") if x.strip()]
    int_staff = [x.strip() for x in st.text_area("Intern List", key="int_list").split(",") if x.strip()]

def update_pref(key, staff, label, help_t):
    prefs = st.session_state.get(key, {})
    new_prefs = {}
    st.markdown(f"**{label}**")
    if help_t: st.caption(help_t)
    for doc in staff:
        default = [d for d in prefs.get(doc, []) if d in dates]
        selection = st.multiselect(doc, dates, default=default, key=f"{key}_{doc}_w")
        new_prefs[doc] = selection
    st.session_state[key] = new_prefs

with st.expander("⛔️ Absolute Leaves (Hard Constraint)", expanded=True):
    col_l, col_r = st.columns(2)
    with col_l:
        update_pref("vs_leaves", vs_staff, "VS Leaves", "Strictly excluded")
        update_pref("r_leaves", r_staff, "R Leaves", "Strictly excluded")
    with col_r:
        update_pref("pgy_leaves", pgy_staff, "PGY Leaves", "Strictly excluded")
        update_pref("int_leaves", int_staff, "Int Leaves", "Strictly excluded")

st.markdown("#### Preferences (Soft Constraints)")
c1, c2 = st.columns(2)
with c1:
    with st.expander("🔴 Big Shift Prefs", expanded=False):
        update_pref("vs_wishes", vs_staff, "VS Wishes", "High priority")
        update_pref("vs_nogo", vs_staff, "VS No-Go", "Try to avoid")
        st.markdown("---")
        update_pref("r_nogo", r_staff, "R No-Go", "Try to avoid")
        update_pref("r_wishes", r_staff, "R Wishes", "Bonus points")
with c2:
    with st.expander("🔵 Small Shift Prefs", expanded=False):
        update_pref("pgy_nogo", pgy_staff, "PGY No-Go", "Try to avoid")
        update_pref("pgy_wishes", pgy_staff, "PGY Wishes", "Bonus points")
        st.markdown("---")
        update_pref("int_nogo", int_staff, "Int No-Go", "Try to avoid")
        update_pref("int_wishes", int_staff, "Int Wishes", "Bonus points")

# --- 5. Core Algorithms ---

def add_fairness_objective(model, shifts, staff_list, days, obj_terms, weight=500):
    """
    Minimizes the variance of shifts assigned to each doctor.
    Ensures load balancing for both weekdays and weekends.
    """
    if not staff_list: return
    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    
    avg_wd = len(weekday_days) // len(staff_list)
    avg_we = len(weekend_days) // len(staff_list)

    for doc in staff_list:
        # Weekday Fairness
        wd_count = model.NewIntVar(0, 31, f"wd_cnt_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        # Deviation calculation: dev >= x - avg AND dev >= avg - x (Absolute value logic)
        dev_wd = model.NewIntVar(0, 31, f"dev_wd_{doc}")
        model.Add(dev_wd >= wd_count - avg_wd)
        model.Add(dev_wd >= avg_wd - wd_count)
        obj_terms.append(dev_wd * -weight)

        # Weekend Fairness
        we_count = model.NewIntVar(0, 31, f"we_cnt_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        dev_we = model.NewIntVar(0, 31, f"dev_we_{doc}")
        model.Add(dev_we >= we_count - avg_we)
        model.Add(dev_we >= avg_we - we_count)
        obj_terms.append(dev_we * -weight)

def add_point_system_constraint(model, shifts, staff_list, days, obj_terms, sacrifices, limit=8, weight=1000):
    """
    Implements a weighted point system: Weekday=1, Weekend=2.
    Soft Constraint: Total Points <= limit (default 8).
    """
    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]

    for doc in staff_list:
        # Calculate points
        total_points = model.NewIntVar(0, 100, f"pts_{doc}")
        
        # Points = Sum(Weekday shifts)*1 + Sum(Weekend shifts)*2
        model.Add(total_points == sum(shifts[(doc, d)] for d in weekday_days) * 1 + 
                                  sum(shifts[(doc, d)] for d in weekend_days) * 2)
        
        # Slack variable for exceeding the limit
        slack = model.NewIntVar(0, 50, f"slack_pts_{doc}")
        model.Add(total_points <= limit + slack)
        
        # Penalize exceeding the limit
        obj_terms.append(slack * -weight)
        
        # Record sacrifice if limit is exceeded
        sacrifices.append((slack, f"{doc} Points > {limit} (Wd=1/We=2)"))

def solve_big_shift(vs_staff, r_staff, days, vs_leaves, r_leaves, vs_wishes, vs_nogo, r_nogo, r_wishes, forbidden_patterns=None):
    model = cp_model.CpModel()
    all_staff = vs_staff + r_staff
    shifts = {}
    obj_terms = []
    sacrifices = []

    # Initialize variables
    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_big_{doc}_{d}")

    # 1. Coverage: Exactly one doctor per day
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)

    # 2. Hard Constraint: No back-to-back shifts
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    # 3. Hard Constraint: Absolute Leaves
    for doc, dates_off in vs_leaves.items():
        if doc in vs_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    for doc, dates_off in r_leaves.items():
        if doc in r_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)

    # 4. Diversity Constraint (for multi-solution generation)
    if forbidden_patterns:
        for pattern in forbidden_patterns:
            model.Add(sum([shifts[(doc, d)] for doc, d in pattern]) <= len(pattern) - 3)

    # 5. VS Wishes (Highest Priority Soft Constraint - treated as Hard if possible)
    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on:
                model.Add(shifts[(doc, d)] == 1) 
    
    # 6. Objective: Fairness (Load Balancing)
    W_FAIRNESS = 2000
    add_fairness_objective(model, shifts, r_staff, days, obj_terms, weight=W_FAIRNESS)

    # 7. [NEW] Point System Limit (<= 8 points)
    # Apply primarily to Residents (R), VS usually have their own rules but can be added if needed
    add_point_system_constraint(model, shifts, r_staff, days, obj_terms, sacrifices, limit=8, weight=3000)

    # 8. Preferences & Penalties
    W_R_NOGO = 200; W_VS_NOGO = 500; W_VS_SUPPORT = 500; W_R_WISH = 10
    
    # R No-Go
    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -W_R_NOGO)
                sacrifices.append((shifts[(doc, d)], f"{doc} (R) assigned on No-Go ({month}/{d})"))
    
    # VS No-Go
    for doc, dates_off in vs_nogo.items():
        if doc in vs_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -W_VS_NOGO)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) assigned on No-Go ({month}/{d})"))

    # Penalty for VS supporting non-wish days
    for doc in vs_staff:
        wished_days = vs_wishes.get(doc, [])
        for d in days:
            if d not in wished_days:
                obj_terms.append(shifts[(doc, d)] * -W_VS_SUPPORT)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) covering extra shift ({month}/{d})"))

    # R Wishes
    for doc, dates_on in r_wishes.items():
        if doc in r_staff:
            for d in dates_on:
                obj_terms.append(shifts[(doc, d)] * W_R_WISH)

    # Solve
    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = len(forbidden_patterns) if forbidden_patterns else 0
    status = solver.Solve(model)
    
    result_pattern = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for doc in all_staff:
            for d in days:
                if solver.Value(shifts[(doc, d)]) == 1:
                    result_pattern.append((doc, d))

    return solver, status, shifts, sacrifices, result_pattern

def solve_small_shift(pgy_staff, int_staff, days, pgy_leaves, int_leaves, pgy_nogo, pgy_wishes, int_nogo, int_wishes, forbidden_patterns=None):
    model = cp_model.CpModel()
    all_staff = pgy_staff + int_staff
    shifts = {}
    obj_terms = []
    sacrifices = []

    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_{doc}_{d}")

    # 1. Coverage
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
    
    # 2. No Back-to-Back
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    # 3. Absolute Leaves
    for doc, dates_off in pgy_leaves.items():
        if doc in pgy_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    for doc, dates_off in int_leaves.items():
        if doc in int_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)

    # 4. Diversity
    if forbidden_patterns:
        for pattern in forbidden_patterns:
            model.Add(sum([shifts[(doc, d)] for doc, d in pattern]) <= len(pattern) - 3)

    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    month_weeks = calendar.monthcalendar(year, month)

    W_LIMIT_BREAK = 5000; W_FAIRNESS = 1000; W_NOGO = 100; W_WISH = 10

    # 5. Intern/PGY Specific Limits (Soft Constraints)
    for doc in all_staff:
        is_intern = doc in int_staff
        limit_weight = W_LIMIT_BREAK if is_intern else (W_LIMIT_BREAK / 2)

        # Weekly Limit: <= 2
        for week in month_weeks:
            valid_days = [d for d in week if d != 0]
            if valid_days:
                count = sum(shifts[(doc, d)] for d in valid_days)
                slack = model.NewIntVar(0, 7, f"slk_wk_{doc}_{week[0]}")
                model.Add(count <= 2 + slack)
                obj_terms.append(slack * -limit_weight)
                sacrifices.append((slack, f"{doc} >2 shifts/week"))

        # Monthly Weekday Limit: <= 6
        wd_cnt = sum(shifts[(doc, d)] for d in weekday_days)
        slack_wd = model.NewIntVar(0, 31, f"slk_wd_{doc}")
        model.Add(wd_cnt <= 6 + slack_wd)
        obj_terms.append(slack_wd * -limit_weight)
        sacrifices.append((slack_wd, f"{doc} >6 weekday shifts"))

        # Monthly Weekend Limit: <= 2
        we_cnt = sum(shifts[(doc, d)] for d in weekend_days)
        slack_we = model.NewIntVar(0, 31, f"slk_we_{doc}")
        model.Add(we_cnt <= 2 + slack_we)
        obj_terms.append(slack_we * -limit_weight)
        sacrifices.append((slack_we, f"{doc} >2 weekend shifts"))

    # 6. [NEW] Point System Limit (<= 8 points)
    # Applied to both PGY and Interns
    add_point_system_constraint(model, shifts, all_staff, days, obj_terms, sacrifices, limit=8, weight=3000)

    # 7. Fairness Objective
    add_fairness_objective(model, shifts, all_staff, days, obj_terms, weight=W_FAIRNESS)

    # 8. Preferences
    for doc in all_staff:
        nogo_list = pgy_nogo.get(doc, []) if doc in pgy_staff else int_nogo.get(doc, [])
        wish_list = pgy_wishes.get(doc, []) if doc in pgy_staff else int_wishes.get(doc, [])
        
        for d in days:
            if d in nogo_list:
                obj_terms.append(shifts[(doc, d)] * -W_NOGO)
                sacrifices.append((shifts[(doc, d)], f"{doc} assigned on No-Go ({month}/{d})"))
            if d in wish_list:
                obj_terms.append(shifts[(doc, d)] * W_WISH)

    # Solve
    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = len(forbidden_patterns) if forbidden_patterns else 0
    status = solver.Solve(model)
    
    result_pattern = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for doc in all_staff:
            for d in days:
                if solver.Value(shifts[(doc, d)]) == 1:
                    result_pattern.append((doc, d))
                    
    return solver, status, shifts, sacrifices, result_pattern

# --- 6. Visualization & Helpers ---
def get_doctor_color(name):
    palette = ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF", "#E6B3FF", "#FFB3E6", "#C9C9FF", "#FFD1DC", "#E0F7FA", "#F0F4C3", "#D7CCC8", "#F8BBD0", "#C5CAE9", "#B2DFDB"]
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(palette)
    return palette[idx]

def calculate_stats(df):
    if df.empty: return pd.DataFrame()
    stats = df.groupby('Doctor')['Type'].value_counts().unstack(fill_value=0)
    if 'Weekday' not in stats.columns: stats['Weekday'] = 0
    if 'Weekend' not in stats.columns: stats['Weekend'] = 0
    stats['Total Shifts'] = stats['Weekday'] + stats['Weekend']
    stats['Total Points'] = stats['Weekday'] * 1 + stats['Weekend'] * 2
    return stats[['Total Shifts', 'Total Points', 'Weekday', 'Weekend']].sort_values(by='Total Points', ascending=False)

def get_html_calendar(df_big, df_small):
    cal = calendar.monthcalendar(year, month)
    map_big = {int(r["Date"].split("/")[1]): r["Doctor"] for _, r in df_big.iterrows()}
    map_small = {int(r["Date"].split("/")[1]): r["Doctor"] for _, r in df_small.iterrows()}
    
    html = """
    <style>
        .cal-table {width:100%; border-collapse:collapse; table-layout:fixed;}
        .cal-table td {height:120px; border:1px solid #ddd; vertical-align:top; padding:4px; background:#fff;}
        .cal-table th {background:#f0f2f6; border:1px solid #ddd; padding:5px;}
        .day-num {font-size:12px; color:#666; text-align:right; margin-bottom:5px;}
        .badge {padding:4px 6px; border-radius:6px; font-size:13px; margin-bottom:4px; display:block; font-weight:bold; color: #333; text-shadow: 0 0 2px #fff; border: 1px solid rgba(0,0,0,0.1);}
        .weekend {background-color:#fafafa !important;}
        .shift-label {font-size: 10px; color: #666; margin-right: 3px;}
    </style>
    <table class="cal-table"><thead><tr><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color:red">Sat</th><th style="color:red">Sun</th></tr></thead><tbody>
    """
    for week in cal:
        html += "<tr>"
        for i, day in enumerate(week):
            cls = "weekend" if i >= 5 else ""
            if day == 0: html += f'<td class="empty"></td>'
            else:
                b_doc = map_big.get(day, "")
                s_doc = map_small.get(day, "")
                html += f'<td class="{cls}"><div class="day-num">{day}</div>'
                if b_doc: html += f'<div class="badge" style="background-color:{get_doctor_color(b_doc)};"><span class="shift-label">Big:</span>{b_doc}</div>'
                if s_doc: html += f'<div class="badge" style="background-color:{get_doctor_color(s_doc)};"><span class="shift-label">Sml:</span>{s_doc}</div>'
                html += "</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

def get_report(solver, sacrifices):
    report = []
    seen = set()
    for var, msg in sacrifices:
        if solver.Value(var) > 0:
            if msg not in seen:
                report.append(msg)
                seen.add(msg)
    return report

def generate_df(solver, shifts, staff, days, name):
    res = []
    for d in days:
        for doc in staff:
            if solver.Value(shifts[(doc, d)]) == 1:
                w = date(year, month, d).strftime("%a")
                is_weekend = date(year, month, d).weekday() >= 5
                res.append({"Date": f"{month}/{d}", "Weekday": w, "Shift": name, "Doctor": doc, "Type": "Weekend" if is_weekend else "Weekday"})
    return pd.DataFrame(res)

def generate_excel_calendar_df(df_big, df_small):
    map_big = {int(r["Date"].split("/")[1]): r["Doctor"] for _, r in df_big.iterrows()}
    map_small = {int(r["Date"].split("/")[1]): r["Doctor"] for _, r in df_small.iterrows()}
    
    cal = calendar.monthcalendar(year, month)
    csv_rows = []
    headers = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    csv_rows.append(headers)
    
    for week in cal:
        row_date = []; row_big = []; row_small = []
        for day in week:
            if day == 0:
                row_date.append(""); row_big.append(""); row_small.append("")
            else:
                row_date.append(f"{month}/{day}")
                row_big.append(f"[Big] {map_big.get(day, '')}")
                row_small.append(f"[Sml] {map_small.get(day, '')}")
        csv_rows.append(row_date); csv_rows.append(row_big); csv_rows.append(row_small)
        csv_rows.append([""] * 7)
        
    return pd.DataFrame(csv_rows)

# --- 7. Main Execution ---
st.markdown("---")
st.caption("Generate N different feasible solutions. Toggle tabs to compare.")

if st.button(f"🚀 Generate {num_solutions} Solutions", type="primary"):
    if not (vs_staff and r_staff and pgy_staff and int_staff):
        st.error("Error: Staff lists cannot be empty.")
    else:
        big_solutions = []
        small_solutions = []
        forbidden_big = []
        forbidden_small = []
        progress = st.empty()
        
        for i in range(num_solutions):
            progress.text(f"Solving... ({i+1}/{num_solutions})")
            
            # Solve Big Shift
            b_sol, b_stat, b_shifts, b_sac, b_pat = solve_big_shift(
                vs_staff, r_staff, dates, 
                st.session_state.vs_leaves, st.session_state.r_leaves,
                st.session_state.vs_wishes, st.session_state.vs_nogo, 
                st.session_state.r_nogo, st.session_state.r_wishes,
                forbidden_patterns=forbidden_big
            )
            
            # Solve Small Shift
            s_sol, s_stat, s_shifts, s_sac, s_pat = solve_small_shift(
                pgy_staff, int_staff, dates, 
                st.session_state.pgy_leaves, st.session_state.int_leaves,
                st.session_state.pgy_nogo, st.session_state.pgy_wishes, 
                st.session_state.int_nogo, st.session_state.int_wishes,
                forbidden_patterns=forbidden_small
            )

            if b_stat in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                big_solutions.append((b_sol, b_shifts, b_sac))
                forbidden_big.append(b_pat)
            
            if s_stat in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                small_solutions.append((s_sol, s_shifts, s_sac))
                forbidden_small.append(s_pat)

        progress.empty()
        
        if not big_solutions or not small_solutions:
            st.error("No feasible solution found. Please reduce absolute leave constraints.")
        else:
            st.success(f"Successfully generated {min(len(big_solutions), len(small_solutions))} solutions!")
            tabs = st.tabs([f"Solution {i+1}" for i in range(min(len(big_solutions), len(small_solutions)))])
            
            for i, tab in enumerate(tabs):
                with tab:
                    b_data = big_solutions[i]
                    s_data = small_solutions[i]
                    
                    df_big = generate_df(b_data[0], b_data[1], vs_staff+r_staff, dates, "Big")
                    df_small = generate_df(s_data[0], s_data[1], pgy_staff+int_staff, dates, "Small")
                    
                    sac_big = get_report(b_data[0], b_data[2])
                    sac_small = get_report(s_data[0], s_data[2])
                    
                    if sac_big or sac_small:
                        with st.expander("⚠️ Sacrifice Report (Points/Constraints Exceeded)", expanded=True):
                            if sac_big: 
                                st.write("**[Big Shift]**")
                                for s in sac_big: st.write(f"- 🔴 {s}")
                            if sac_small: 
                                st.write("**[Small Shift]**")
                                for s in sac_small: st.write(f"- 🔵 {s}")
                    else:
                        st.info("✨ Perfect Solution")

                    c1, c2 = st.columns(2)
                    with c1: 
                        st.markdown("**Big Shift Stats**")
                        st.dataframe(calculate_stats(df_big), use_container_width=True)
                    with c2: 
                        st.markdown("**Small Shift Stats**")
                        st.dataframe(calculate_stats(df_small), use_container_width=True)

                    st.markdown(get_html_calendar(df_big, df_small), unsafe_allow_html=True)
                    
                    # Excel Format CSV
                    excel_df = generate_excel_calendar_df(df_big, df_small)
                    csv = excel_df.to_csv(index=False, header=False).encode('utf-8-sig')
                    st.download_button(f"📥 Download Excel-Format CSV", csv, f"roster_cal_{i+1}.csv", "text/csv", key=f"dl_{i}")
