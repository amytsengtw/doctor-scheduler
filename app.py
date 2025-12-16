import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date, timedelta
import json
import hashlib

# ==========================================
# 1. 頁面設定
# ==========================================
st.set_page_config(page_title="耕莘醫院雙軌排班系統 (v5.0 旗艦版)", layout="wide")

st.title("🏥 耕莘醫院婦產科雙軌排班系統 (v5.0 貼心旗艦版)")
st.caption("新增功能：手機行事曆匯入 (.ics) | 國定假日設定 | 公平性圖表 | 嚴格班數限制")

# ==========================================
# 2. Session State 初始化
# ==========================================
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
    "int_wishes": {}, "int_nogo": {},
    "holidays": [] # New: 國定假日
}

for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================
# 3. 側邊欄設定
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

# [New] 國定假日設定
st.sidebar.markdown("---")
st.sidebar.header("🏮 國定假日 (紅字)")
holidays = st.sidebar.multiselect(
    "請勾選平日放假的日子 (視為假日班)",
    options=dates,
    default=st.session_state.get("holidays", []),
    key="holidays_widget"
)
st.session_state["holidays"] = holidays

st.sidebar.markdown("---")
st.sidebar.header("🔢 運算設定")
num_solutions = st.sidebar.slider("產生方案數量", min_value=1, max_value=5, value=1)

# ==========================================
# 4. 主畫面：人員與限制設定
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
# 5. 核心演算法定義 (Functions)
# ==========================================

# 判斷是否為假日 (週六日 OR 國定假日)
def is_holiday(d, custom_holidays):
    is_weekend = date(year, month, d).weekday() >= 5
    is_custom = d in custom_holidays
    return is_weekend or is_custom

def add_fairness_objective(model, shifts, staff_list, days, custom_holidays, obj_terms, weight=500):
    if not staff_list: return
    weekend_days = [d for d in days if is_holiday(d, custom_holidays)]
    weekday_days = [d for d in days if not is_holiday(d, custom_holidays)]
    
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

def add_point_system_constraint(model, shifts, staff_list, days, custom_holidays, obj_terms, sacrifices, limit=8, weight=1000):
    weekend_days = [d for d in days if is_holiday(d, custom_holidays)]
    weekday_days = [d for d in days if not is_holiday(d, custom_holidays)]

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

def solve_big_shift(vs_staff, r_staff, days, vs_leaves, r_leaves, vs_wishes, vs_nogo, r_nogo, r_wishes, custom_holidays, forbidden_patterns=None):
    model = cp_model.CpModel()
    all_staff = vs_staff + r_staff
    shifts = {}
    obj_terms = []
    sacrifices = []

    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_big_{doc}_{d}")

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

    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on: model.Add(shifts[(doc, d)] == 1) 
    
    add_fairness_objective(model, shifts, r_staff, days, custom_holidays, obj_terms, weight=2000)
    add_point_system_constraint(model, shifts, r_staff, days, custom_holidays, obj_terms, sacrifices, limit=8, weight=200)
    add_spacing_preference(model, shifts, r_staff, days, obj_terms, weight=50)

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
                      r_nogo, r_schedule_map, custom_holidays,
                      forbidden_patterns=None):
    
    model = cp_model.CpModel()
    
    shifts = {}
    obj_terms = []
    sacrifices = []

    for doc in pgy_staff + int_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_{doc}_{d}")
    for doc in r_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_Rsupport_{doc}_{d}")

    all_small_candidates = pgy_staff + int_staff + r_staff

    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_small_candidates) == 1)
    
    for doc in pgy_staff + int_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

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

    for doc, dates_off in pgy_leaves.items():
        if doc in pgy_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    for doc, dates_off in int_leaves.items():
        if doc in int_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)

    if forbidden_patterns:
        for pattern in forbidden_patterns:
            relevant = []
            for doc, d in pattern:
                if (doc, d) in shifts: relevant.append(shifts[(doc, d)])
            if relevant: model.Add(sum(relevant) <= len(relevant) - 3)

    # Logic update for Holidays
    weekend_days = [d for d in days if is_holiday(d, custom_holidays)]
    weekday_days = [d for d in days if not is_holiday(d, custom_holidays)]
    month_weeks = calendar.monthcalendar(year, month)

    W_LIMIT_BREAK = 1000000; W_FAIRNESS = 500; W_NOGO = 5000; W_WISH = 10
    
    for doc in pgy_staff + int_staff:
        limit_weight = W_LIMIT_BREAK

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

    add_point_system_constraint(model, shifts, pgy_staff + int_staff, days, custom_holidays, obj_terms, sacrifices, limit=10, weight=1000)

    for doc in r_staff:
        for d in days:
            obj_terms.append(shifts[(doc, d)] * -50000)
            sacrifices.append((shifts[(doc, d)], f"{doc} (R) 支援小班 ({month}/{d})"))

    add_fairness_objective(model, shifts, pgy_staff + int_staff, days, custom_holidays, obj_terms, weight=W_FAIRNESS)

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
                if solver.Value(shifts[(doc, d)]) == 1:
                    result_pattern.append((doc, d))
                    
    return solver, status, shifts, sacrifices, result_pattern

# --- 6. Visualization & Helpers ---
def get_doctor_color(name):
    palette = ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF", "#E6B3FF", "#FFB3E6", "#C9C9FF", "#FFD1DC", "#E0F7FA", "#F0F4C3", "#D7CCC8", "#F8BBD0", "#C5CAE9", "#B2DFDB"]
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(palette)
    return palette[idx]

def calculate_stats(df, custom_holidays):
    if df.empty: return pd.DataFrame()
    
    # Recalculate type based on holidays
    df['Type'] = df['日期'].apply(lambda x: '假日' if is_holiday(int(x.split('/')[1]), custom_holidays) else '平日')
    
    stats = df.groupby('醫師')['Type'].value_counts().unstack(fill_value=0)
    if '平日' not in stats.columns: stats['平日'] = 0
    if '假日' not in stats.columns: stats['假日'] = 0
    stats['總班數'] = stats['平日'] + stats['假日']
    stats['總點數'] = stats['平日'] * 1 + stats['假日'] * 2
    return stats[['總班數', '總點數', '平日', '假日']].sort_values(by='總點數', ascending=False)

def get_html_calendar(df_big, df_small, custom_holidays):
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
        .holiday {background-color:#ffebee !important;} /* 紅色背景給國定假日 */
        .shift-label {font-size: 10px; color: #666; margin-right: 3px;}
    </style>
    <table class="cal-table"><thead><tr><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color:red">Sat</th><th style="color:red">Sun</th></tr></thead><tbody>
    """
    for week in cal:
        html += "<tr>"
        for i, day in enumerate(week):
            cls = ""
            if day != 0:
                if is_holiday(day, custom_holidays):
                    cls = "holiday" if day in custom_holidays else "weekend"
            
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
                res.append({"日期": f"{month}/{d}", "星期": w, "班別": name, "醫師": doc})
    return pd.DataFrame(res)

# [New] ICS 產生器
def generate_ics(df_big, df_small, year, month):
    ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//CTH//Roster//TW\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\n"
    
    # 合併兩個 Dataframe
    full_df = pd.concat([df_big, df_small])
    
    for _, row in full_df.iterrows():
        day = int(row['日期'].split('/')[1])
        shift_type = row['班別']
        doctor = row['醫師']
        
        # 設定時間：產房班 08:00 - 隔日 08:00 (範例)
        start_date = date(year, month, day)
        end_date = start_date + timedelta(days=1)
        
        dtstart = start_date.strftime("%Y%m%d")
        dtend = end_date.strftime("%Y%m%d")
        
        ics_content += "BEGIN:VEVENT\n"
        ics_content += f"SUMMARY:值班: {doctor} ({shift_type})\n"
        ics_content += f"DTSTART;VALUE=DATE:{dtstart}\n"
        ics_content += f"DTEND;VALUE=DATE:{dtend}\n"
        ics_content += f"DESCRIPTION:{shift_type}值班\n"
        ics_content += "END:VEVENT\n"
        
    ics_content += "END:VCALENDAR"
    return ics_content

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
# 7. 主程式執行
# ==========================================
st.markdown("---")
st.caption(f"目前設定將產生 {num_solutions} 組方案供您選擇")

if st.button("🚀 開始排班", type="primary"):
    
    if not (vs_staff and r_staff and pgy_staff and int_staff):
        st.error("錯誤：醫師名單不能為空！")
    else:
        big_solutions = []
        small_solutions = []
        forbidden_big = []
        forbidden_small = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(num_solutions):
            progress = (i + 1) / num_solutions
            progress_bar.progress(progress)
            status_text.text(f"正在運算第 {i+1} / {num_solutions} 個方案...")
            
            # 1. Big Shift
            b_sol, b_stat, b_shifts, b_sac, b_pat, r_schedule_map = solve_big_shift(
                vs_staff, r_staff, dates, 
                st.session_state.vs_leaves, st.session_state.r_leaves,
                st.session_state.vs_wishes, st.session_state.vs_nogo, 
                st.session_state.r_nogo, st.session_state.r_wishes,
                st.session_state.holidays, # 傳入國定假日
                forbidden_patterns=forbidden_big
            )
            
            # 2. Small Shift
            s_sol, s_stat, s_shifts, s_sac, s_pat = solve_small_shift(
                pgy_staff, int_staff, r_staff, dates, 
                st.session_state.pgy_leaves, st.session_state.int_leaves,
                st.session_state.pgy_nogo, st.session_state.pgy_wishes, 
                st.session_state.int_nogo, st.session_state.int_wishes,
                st.session_state.r_nogo, r_schedule_map, 
                st.session_state.holidays, # 傳入國定假日
                forbidden_patterns=forbidden_small
            )

            if b_stat in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                big_solutions.append((b_sol, b_shifts, b_sac))
                forbidden_big.append(b_pat)
            
            if s_stat in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                small_solutions.append((s_sol, s_shifts, s_sac))
                forbidden_small.append(s_pat)

        status_text.empty()
        progress_bar.empty()
        
        if not big_solutions or not small_solutions:
            st.error("❌ 無法找出可行解！請檢查是否設定了太多的「絕對請假」。")
        else:
            st.success(f"✅ 成功生成 {min(len(big_solutions), len(small_solutions))} 組方案！")
            
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
                        st.markdown("### 大班統計")
                        stats_b = calculate_stats(df_big, st.session_state.holidays)
                        st.dataframe(stats_b, use_container_width=True)
                        st.bar_chart(stats_b['總點數']) # 視覺化
                        
                    with c2: 
                        st.markdown("### 小班統計 (含 R 支援)")
                        stats_s = calculate_stats(df_small, st.session_state.holidays)
                        st.dataframe(stats_s, use_container_width=True)
                        st.bar_chart(stats_s['總點數']) # 視覺化

                    st.markdown("### 📅 排班月曆")
                    st.markdown(get_html_calendar(df_big, df_small, st.session_state.holidays), unsafe_allow_html=True)
                    
                    # 檔案下載區
                    col_d1, col_d2 = st.columns(2)
                    
                    with col_d1:
                        excel_df = generate_excel_calendar_df(df_big, df_small)
                        csv = excel_df.to_csv(index=False, header=False).encode('utf-8-sig')
                        st.download_button(
                            label=f"📥 下載 Excel 日曆格式 (CSV)",
                            data=csv,
                            file_name=f"roster_solution_{i+1}.csv",
                            mime="text/csv",
                            key=f"dl_csv_{i}"
                        )
                    
                    with col_d2:
                        ics_data = generate_ics(df_big, df_small, year, month)
                        st.download_button(
                            label=f"📅 下載手機行事曆 (.ics)",
                            data=ics_data,
                            file_name=f"roster_solution_{i+1}.ics",
                            mime="text/calendar",
                            key=f"dl_ics_{i}"
                        )
