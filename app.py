import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date
import json
import hashlib

# ==========================================
# 1. 頁面設定與 Session State
# ==========================================
st.set_page_config(page_title="耕莘醫院雙軌排班系統 (v4.5)", layout="wide")

st.title("🏥 耕莘醫院婦產科雙軌排班系統 (v4.5)")
st.caption("救援機制調整：PGY/Int 點數 > 10 點才啟動 R 支援 | 平日=1點, 假日=2點")

default_state = {
    "year": 2025,
    "month": 12,
    "vs_list": "張醫師(VS), 王醫師(VS)", 
    "r_list": "洋洋(R3), 蹦蹦(R2)",
    "pgy_list": "小明(PGY), 小華(PGY), 小強(PGY)",
    "int_list": "菜鳥A(Int), 菜鳥B(Int)",
    "vs_leaves": {}, "r_leaves": {}, "pgy_leaves": {}, "int_leaves": {},
    "vs_wishes": {},  "vs_nogo": {},
    "r_wishes": {},   "r_nogo": {},
    "pgy_wishes": {}, "pgy_nogo": {},
    "int_wishes": {}, "int_nogo": {}
}

for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================
# 2. 側邊欄設定
# ==========================================
st.sidebar.header("📂 設定檔存取")
def get_current_config():
    return {k: st.session_state[k] for k in default_state.keys()}

config_json = json.dumps(get_current_config(), ensure_ascii=False, indent=2)
st.sidebar.download_button("💾 下載設定 (JSON)", config_json, "roster_config.json", "application/json")

uploaded_file = st.sidebar.file_uploader("📂 讀取設定 (JSON)", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        for key in default_state.keys():
            if key in data:
                st.session_state[key] = data[key]
        st.sidebar.success("讀取成功！")
    except Exception as e:
        st.sidebar.error(f"讀取失敗: {e}")

st.sidebar.markdown("---")
st.sidebar.header("📅 時間設定")
year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, key="year")
month = st.sidebar.number_input("月份", min_value=1, max_value=12, key="month")
days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.markdown("---")
st.sidebar.header("🔢 運算設定")
num_solutions = st.sidebar.slider("產生方案數量", min_value=1, max_value=5, value=1)

# ==========================================
# 3. 人員與限制介面
# ==========================================
st.subheader("1. 人員與限制設定")
tab1, tab2 = st.tabs(["🔴 大班 (產房)", "🔵 小班 (一般)"])
with tab1:
    c1, c2 = st.columns(2)
    vs_staff = [x.strip() for x in st.text_area("VS 主治醫師名單", key="vs_list").split(",") if x.strip()]
    r_staff = [x.strip() for x in st.text_area("R 住院醫師名單", key="r_list").split(",") if x.strip()]
with tab2:
    c3, c4 = st.columns(2)
    pgy_staff = [x.strip() for x in st.text_area("PGY 名單", key="pgy_list").split(",") if x.strip()]
    int_staff = [x.strip() for x in st.text_area("Intern 實習醫師名單", key="int_list").split(",") if x.strip()]

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

with st.expander("⛔️ 請假/未到職設定 (絕對排除)", expanded=True):
    st.error("注意：此區為硬限制，系統絕對不會排班。")
    col_l, col_r = st.columns(2)
    with col_l:
        update_pref("vs_leaves", vs_staff, "VS 請假", "")
        update_pref("r_leaves", r_staff, "R 請假", "")
    with col_r:
        update_pref("pgy_leaves", pgy_staff, "PGY 請假", "")
        update_pref("int_leaves", int_staff, "Int 請假", "")

st.markdown("#### 排班意願 (軟限制)")
c1, c2 = st.columns(2)
with c1:
    with st.expander("🔴 大班意願", expanded=False):
        update_pref("vs_wishes", vs_staff, "VS 指定值班", "優先排入")
        update_pref("vs_nogo", vs_staff, "VS 不想值", "盡量避開")
        st.markdown("---")
        update_pref("r_nogo", r_staff, "R 不想值", "盡量避開")
        update_pref("r_wishes", r_staff, "R 想值", "額外加分")
with c2:
    with st.expander("🔵 小班意願", expanded=False):
        update_pref("pgy_nogo", pgy_staff, "PGY 不想值", "盡量避開")
        update_pref("pgy_wishes", pgy_staff, "PGY 想值", "額外加分")
        st.markdown("---")
        update_pref("int_nogo", int_staff, "Int 不想值", "盡量避開")
        update_pref("int_wishes", int_staff, "Int 想值", "額外加分")

# ==========================================
# 4. 核心演算法
# ==========================================

def add_fairness_objective(model, shifts, staff_list, days, obj_terms, weight=500):
    if not staff_list: return
    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    
    avg_wd = len(weekday_days) // len(staff_list)
    avg_we = len(weekend_days) // len(staff_list)

    for doc in staff_list:
        wd_count = model.NewIntVar(0, 31, f"wd_cnt_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        dev_wd = model.NewIntVar(0, 31, f"dev_wd_{doc}")
        model.Add(dev_wd >= wd_count - avg_wd)
        model.Add(dev_wd >= avg_wd - wd_count)
        obj_terms.append(dev_wd * -weight)

        we_count = model.NewIntVar(0, 31, f"we_cnt_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        dev_we = model.NewIntVar(0, 31, f"dev_we_{doc}")
        model.Add(dev_we >= we_count - avg_we)
        model.Add(dev_we >= avg_we - we_count)
        obj_terms.append(dev_we * -weight)

def add_point_system_constraint(model, shifts, staff_list, days, obj_terms, sacrifices, limit=8, weight=1000):
    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]

    for doc in staff_list:
        total_points = model.NewIntVar(0, 100, f"pts_{doc}")
        model.Add(total_points == sum(shifts[(doc, d)] for d in weekday_days) * 1 + 
                                  sum(shifts[(doc, d)] for d in weekend_days) * 2)
        slack = model.NewIntVar(0, 50, f"slack_pts_{doc}")
        model.Add(total_points <= limit + slack)
        obj_terms.append(slack * -weight)
        sacrifices.append((slack, f"{doc} 點數超標 (>{limit}點)"))

def add_spacing_preference(model, shifts, staff_list, days, obj_terms, weight=100):
    for doc in staff_list:
        for d in range(1, len(days) - 1):
            q2_violation = model.NewBoolVar(f"q2_{doc}_{d}")
            model.Add(shifts[(doc, d)] + shifts[(doc, d+2)] <= 1 + q2_violation)
            obj_terms.append(q2_violation * -weight)

def solve_big_shift(vs_staff, r_staff, days, vs_leaves, r_leaves, vs_wishes, vs_nogo, r_nogo, r_wishes, forbidden_patterns=None):
    model = cp_model.CpModel()
    all_staff = vs_staff + r_staff
    shifts = {}
    obj_terms = []
    sacrifices = []

    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_big_{doc}_{d}")

    # Coverage & Hard Constraints
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)
    for doc, dates_off in vs_leaves.items():
        if doc in vs_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    for doc, dates_off in r_leaves.items():
        if doc in r_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)

    if forbidden_patterns:
        for pattern in forbidden_patterns:
            model.Add(sum([shifts[(doc, d)] for doc, d in pattern]) <= len(pattern) - 3)

    # VS Wishes
    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on: model.Add(shifts[(doc, d)] == 1) 
    
    # Objectives
    add_fairness_objective(model, shifts, r_staff, days, obj_terms, weight=2000)
    add_point_system_constraint(model, shifts, r_staff, days, obj_terms, sacrifices, limit=8, weight=200)
    add_spacing_preference(model, shifts, r_staff, days, obj_terms, weight=50)

    # Preferences
    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -5000)
                sacrifices.append((shifts[(doc, d)], f"{doc} (R) 排入 No-Go ({month}/{d})"))
    
    for doc, dates_off in vs_nogo.items():
        if doc in vs_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -5000)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 排入 No-Go ({month}/{d})"))

    for doc in vs_staff:
        wished_days = vs_wishes.get(doc, [])
        for d in days:
            if d not in wished_days:
                obj_terms.append(shifts[(doc, d)] * -5000)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 支援非指定班 ({month}/{d})"))

    for doc, dates_on in r_wishes.items():
        if doc in r_staff:
            for d in dates_on:
                obj_terms.append(shifts[(doc, d)] * 10)

    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = len(forbidden_patterns) if forbidden_patterns else 0
    status = solver.Solve(model)
    
    result_pattern = []
    r_schedule_map = {r: [] for r in r_staff}

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for doc in all_staff:
            for d in days:
                if solver.Value(shifts[(doc, d)]) == 1:
                    result_pattern.append((doc, d))
                    if doc in r_staff:
                        r_schedule_map[doc].append(d)

    return solver, status, shifts, sacrifices, result_pattern, r_schedule_map

def solve_small_shift(pgy_staff, int_staff, r_staff, days, 
                      pgy_leaves, int_leaves, 
                      pgy_nogo, pgy_wishes, int_nogo, int_wishes,
                      r_nogo, r_schedule_map, 
                      forbidden_patterns=None):
    
    model = cp_model.CpModel()
    
    shifts = {}
    obj_terms = []
    sacrifices = []

    # Variables
    for doc in pgy_staff + int_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_{doc}_{d}")

    for doc in r_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_Rsupport_{doc}_{d}")

    all_small_candidates = pgy_staff + int_staff + r_staff

    # Coverage
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_small_candidates) == 1)
    
    # No Back-to-Back
    for doc in pgy_staff + int_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    # R Support Constraints
    for doc in r_staff:
        big_shift_days = r_schedule_map.get(doc, [])
        r_nogo_days = r_nogo.get(doc, [])
        for d in days:
            if d in big_shift_days: model.Add(shifts[(doc, d)] == 0)
            is_too_close = False
            for b_day in big_shift_days:
                if abs(b_day - d) <= 2: 
                    is_too_close = True
                    break
            if is_too_close: model.Add(shifts[(doc, d)] == 0)
            if d in r_nogo_days: model.Add(shifts[(doc, d)] == 0)
            if d < len(days): model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    # Absolute Leaves
    for doc, dates_off in pgy_leaves.items():
        if doc in pgy_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    for doc, dates_off in int_leaves.items():
        if doc in int_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)

    # Diversity
    if forbidden_patterns:
        for pattern in forbidden_patterns:
            relevant = []
            for doc, d in pattern:
                if (doc, d) in shifts: relevant.append(shifts[(doc, d)])
            if relevant: model.Add(sum(relevant) <= len(relevant) - 3)

    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    month_weeks = calendar.monthcalendar(year, month)

    W_LIMIT_BREAK = 5000; W_FAIRNESS = 1000; W_NOGO = 5000; W_WISH = 10
    
    # Limits
    for doc in pgy_staff + int_staff:
        is_intern = doc in int_staff
        limit_weight = W_LIMIT_BREAK if is_intern else (W_LIMIT_BREAK / 2)
        for week in month_weeks:
            valid_days = [d for d in week if d != 0]
            if valid_days:
                count = sum(shifts[(doc, d)] for d in valid_days)
                slack = model.NewIntVar(0, 7, f"slk_wk_{doc}_{week[0]}")
                model.Add(count <= 2 + slack)
                obj_terms.append(slack * -limit_weight)
                sacrifices.append((slack, f"{doc} 單週超過 2 班"))
        wd_cnt = sum(shifts[(doc, d)] for d in weekday_days)
        slack_wd = model.NewIntVar(0, 31, f"slk_wd_{doc}")
        model.Add(wd_cnt <= 6 + slack_wd)
        obj_terms.append(slack_wd * -limit_weight)
        sacrifices.append((slack_wd, f"{doc} 平日超過 6 班"))
        we_cnt = sum(shifts[(doc, d)] for d in weekend_days)
        slack_we = model.NewIntVar(0, 31, f"slk_we_{doc}")
        model.Add(we_cnt <= 2 + slack_we)
        obj_terms.append(slack_we * -limit_weight)
        sacrifices.append((slack_we, f"{doc} 假日超過 2 班"))

    add_point_system_constraint(model, shifts, pgy_staff + int_staff, days, obj_terms, sacrifices, limit=10, weight=1000)

    for doc in r_staff:
        for d in days:
            obj_terms.append(shifts[(doc, d)] * -100)
            sacrifices.append((shifts[(doc, d)], f"{doc} (R) 支援小班 ({month}/{d})"))

    add_fairness_objective(model, shifts, pgy_staff + int_staff, days, obj_terms, weight=W_FAIRNESS)

    for doc in pgy_staff + int_staff:
        nogo_list = pgy_nogo.get(doc, []) if doc in pgy_staff else int_nogo.get(doc, [])
        wish_list = pgy_wishes.get(doc, []) if doc in pgy_staff else int_wishes.get(doc, [])
        for d in days:
            if d in nogo_list:
                obj_terms.append(shifts[(doc, d)] * -W_NOGO)
                sacrifices.append((shifts[(doc, d)], f"{doc} 排入不想值的班 ({month}/{d})"))
            if d in wish_list:
                obj_terms.append(shifts[(doc, d)] * W_WISH)

    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = len(forbidden_patterns) if forbidden_patterns else 0
    status = solver.Solve(model)
    
    result_pattern = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for doc in all_small_candidates:
            for d in days:
                if solver.Value(shifts[(doc, d)]) == 1: result_pattern.append((doc, d))
    return solver, status, shifts, sacrifices, result_pattern

# ==========================================
# 5. 視覺化工具
# ==========================================

def get_doctor_color(name):
    palette = ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF", "#E6B3FF", "#FFB3E6", "#C9C9FF", "#FFD1DC", "#E0F7FA", "#F0F4C3", "#D7CCC8", "#F8BBD0", "#C5CAE9", "#B2DFDB"]
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(palette)
    return palette[idx]

def calculate_stats(df):
    if df.empty: return pd.DataFrame()
    stats = df.groupby('醫師')['類型'].value_counts().unstack(fill_value=0)
    if '平日' not in stats.columns: stats['平日'] = 0
    if '假日' not in stats.columns: stats['假日'] = 0
    stats['總班數'] = stats['平日'] + stats['假日']
    stats['總點數'] = stats['平日'] * 1 + stats['假日'] * 2
    return stats[['總班數', '總點數', '平日', '假日']].sort_values(by='總點數', ascending=False)

def get_html_calendar(df_big, df_small):
    cal = calendar.monthcalendar(year, month)
    map_big = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_big.iterrows()}
    map_small = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_small.iterrows()}
    
    html = """
    <style>
        .cal-table {width:100%; border-collapse:collapse; table-layout:fixed;}
        .cal-table td {height:120px; border:1px solid #ddd; vertical-align:top; padding:4px; background:#fff;}
        .cal-table th {background:#f0f2f6; border:1px solid #ddd; padding:5px;}
        .day-num {font-size:12px; color:#666; text-align:right; margin-bottom:5px;}
        .badge {padding:4px 6px; border-radius:6px; font-size:13px; margin-bottom:4px; display:block; font-weight:bold; color: #333; text-shadow: 0 0 2px #fff; border: 1px solid rgba(0,0,0,0.1);}
        .weekend {background-color:#fafafa !important;}
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
                if b_doc: html += f'<div class="badge" style="background-color:{get_doctor_color(b_doc)};"><span class="shift-label">產:</span>{b_doc}</div>'
                if s_doc: html += f'<div class="badge" style="background-color:{get_doctor_color(s_doc)};"><span class="shift-label">小:</span>{s_doc}</div>'
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
                res.append({"日期": f"{month}/{d}", "星期": w, "班別": name, "醫師": doc, "類型": "假日" if is_weekend else "平日"})
    return pd.DataFrame(res)

def generate_excel_calendar_df(df_big, df_small):
    map_big = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_big.iterrows()}
    map_small = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_small.iterrows()}
    
    cal = calendar.monthcalendar(year, month)
    csv_rows = []
    headers = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
    csv_rows.append(headers)
    
    for week in cal:
        row_date = []; row_big = []; row_small = []
        for day in week:
            if day == 0:
                row_date.append(""); row_big.append(""); row_small.append("")
            else:
                row_date.append(f"{month}/{day}")
                row_big.append(f"[產] {map_big.get(day, '')}")
                row_small.append(f"[小] {map_small.get(day, '')}")
        csv_rows.append(row_date); csv_rows.append(row_big); csv_rows.append(row_small)
        csv_rows.append([""] * 7)
    return pd.DataFrame(csv_rows)

# ==========================================
# 6. 主程式執行 (確保按鈕在最外層)
# ==========================================
st.markdown("---")
st.caption("系統將產生 N 組不同的方案供您選擇")

# 👇 這是按鈕，一定要在最外層 (沒有縮排)
if st.button(f"🚀 開始排班 (生成 {num_solutions} 組方案)", type="primary"):
    if not (vs_staff and r_staff and pgy_staff and int_staff):
        st.error("錯誤：醫師名單不能為空！")
    else:
        big_solutions = []
        small_solutions = []
        forbidden_big = []
        forbidden_small = []
        progress = st.empty()
        
        for i in range(num_solutions):
            progress.text(f"運算中... ({i+1}/{num_solutions})")
            
            b_sol, b_stat, b_shifts, b_sac, b_pat, r_schedule_map = solve_big_shift(
                vs_staff, r_staff, dates, 
                st.session_state.vs_leaves, st.session_state.r_leaves,
                st.session_state.vs_wishes, st.session_state.vs_nogo, 
                st.session_state.r_nogo, st.session_state.r_wishes,
                forbidden_patterns=forbidden_big
            )
            
            s_sol, s_stat, s_shifts, s_sac, s_pat = solve_small_shift(
                pgy_staff, int_staff, r_staff, dates, 
                st.session_state.pgy_leaves, st.session_state.int_leaves,
                st.session_state.pgy_nogo, st.session_state.pgy_wishes, 
                st.session_state.int_nogo, st.session_state.int_wishes,
                st.session_state.r_nogo, r_schedule_map, 
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
            st.error("無法找出可行解！請嘗試減少「絕對請假」的日期。")
        else:
            st.success(f"成功生成 {min(len(big_solutions), len(small_solutions))} 組方案！")
            tabs = st.tabs([f"方案 {i+1}" for i in range(min(len(big_solutions), len(small_solutions)))])
            
            for i, tab in enumerate(tabs):
                with tab:
                    b_data = big_solutions[i]
                    s_data = small_solutions[i]
                    
                    df_big = generate_df(b_data[0], b_data[1], vs_staff+r_staff, dates, "大班")
                    df_small = generate_df(s_data[0], s_data[1], pgy_staff+int_staff+r_staff, dates, "小班")
                    
                    sac_big = get_report(b_data[0], b_data[2])
                    sac_small = get_report(s_data[0], s_data[2])
                    
                    if sac_big or sac_small:
                        with st.expander("⚠️ 犧牲報告 (點數超標/違反意願/R支援)", expanded=True):
                            if sac_big: 
                                st.write("**[大班 (產房)]**")
                                for s in sac_big: st.write(f"- 🔴 {s}")
                            if sac_small: 
                                st.write("**[小班 (一般)]**")
                                for s in sac_small: st.write(f"- 🔵 {s}")
                    else:
                        st.info("✨ 完美方案 (無犧牲)")

                    c1, c2 = st.columns(2)
                    with c1: 
                        st.markdown("**大班統計**")
                        st.dataframe(calculate_stats(df_big), use_container_width=True)
                    with c2: 
                        st.markdown("**小班統計 (含 R 支援)**")
                        st.dataframe(calculate_stats(df_small), use_container_width=True)

                    st.markdown(get_html_calendar(df_big, df_small), unsafe_allow_html=True)
                    
                    excel_df = generate_excel_calendar_df(df_big, df_small)
                    csv = excel_df.to_csv(index=False, header=False).encode('utf-8-sig')
                    st.download_button(f"📥 下載 Excel 日曆格式 (CSV)", csv, f"roster_cal_{i+1}.csv", "text/csv", key=f"dl_{i}")
