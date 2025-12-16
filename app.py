import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date, timedelta
import json
import hashlib
import base64
import urllib.parse

# ==========================================
# 0. 共用函式 (定義在最上方以便雙模式調用)
# ==========================================

def get_doctor_color(name):
    palette = ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF", "#E6B3FF", "#FFB3E6", "#C9C9FF", "#FFD1DC", "#E0F7FA", "#F0F4C3", "#D7CCC8", "#F8BBD0", "#C5CAE9", "#B2DFDB"]
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(palette)
    return palette[idx]

def generate_ics_content(schedule_data, year, month):
    """
    schedule_data: list of {'d': day, 't': shift_type}
    """
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//CTH//Roster//TW\nCALSCALE:GREGORIAN\n"
    for item in schedule_data:
        day = item['d']
        shift_type = item['t']
        start_date = date(year, month, day)
        end_date = start_date + timedelta(days=1)
        dtstart = start_date.strftime("%Y%m%d")
        dtend = end_date.strftime("%Y%m%d")
        # 產生事件
        ics += f"BEGIN:VEVENT\nSUMMARY:值班: {shift_type}\nDTSTART;VALUE=DATE:{dtstart}\nDTEND;VALUE=DATE:{dtend}\nDESCRIPTION:耕莘醫院 {shift_type}值班\nEND:VEVENT\n"
    ics += "END:VCALENDAR"
    return ics

# ==========================================
# 1. 頁面模式判斷 (醫師檢視模式 vs 總醫師管理模式)
# ==========================================
st.set_page_config(page_title="耕莘醫院雙軌排班系統", layout="wide")

# 檢查網址參數
query_params = st.query_params
if "payload" in query_params:
    # ---------------------------
    # [模式 A] 醫師個人下載頁面
    # ---------------------------
    try:
        # 1. 解碼資料
        payload = query_params["payload"]
        json_str = base64.b64decode(payload).decode('utf-8')
        data = json.loads(json_str)
        
        doc_name = data['n']
        year = data['y']
        month = data['m']
        shifts = data['s'] # list of {'d': day, 't': type}

        # 2. 顯示個人頁面
        st.title(f"👋 您好，{doc_name}")
        st.info(f"這是您 {year} 年 {month} 月的專屬值班表")
        
        # 顯示簡單表格
        df_show = pd.DataFrame(shifts)
        if not df_show.empty:
            df_show['日期'] = df_show['d'].apply(lambda x: f"{month}/{x}")
            df_show['班別'] = df_show['t']
            st.table(df_show[['日期', '班別']])
            
            # 3. 下載按鈕
            ics_content = generate_ics_content(shifts, year, month)
            st.download_button(
                label="📅 加入手機行事曆 (下載 .ics)",
                data=ics_content,
                file_name=f"{doc_name}_{year}_{month}_roster.ics",
                mime="text/calendar",
                type="primary",
                use_container_width=True
            )
            st.success("💡 下載後請直接開啟檔案，即可匯入行事曆。")
        else:
            st.success("🎉 這個月沒有值班！好好休息！")

    except Exception as e:
        st.error("連結無效或已過期。")
        st.error(f"Debug: {e}")
    
    # 停止執行後續程式碼 (只顯示下載頁)
    st.stop()


# ---------------------------
# [模式 B] 總醫師管理介面 (原本的程式碼)
# ---------------------------

st.title("🏥 耕莘醫院婦產科雙軌排班系統 (v6.0 分發連結版)")
st.caption("新增功能：生成每位醫師的專屬下載連結 | 請先複製網址列的 Base URL")

# ... (以下是原本的 Session State, 側邊欄, 演算法, 全部保留) ...

# 2. Session State 初始化
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
    "holidays": []
}

for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# 3. 側邊欄設定
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

# 4. 主畫面：人員與限制設定
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

# 5. 核心演算法 (保持 v4.8 的權重與邏輯)
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
        model.Add(dev_wd >= wd_count - avg_wd); model.Add(dev_wd >= avg_wd - wd_count)
        obj_terms.append(dev_wd * -weight)
        we_count = model.NewIntVar(0, 31, f"we_cnt_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        dev_we = model.NewIntVar(0, 31, f"dev_we_{doc}")
        model.Add(dev_we >= we_count - avg_we); model.Add(dev_we >= avg_we - we_count)
        obj_terms.append(dev_we * -weight)

def add_point_system_constraint(model, shifts, staff_list, days, custom_holidays, obj_terms, sacrifices, limit=8, weight=1000):
    weekend_days = [d for d in days if is_holiday(d, custom_holidays)]
    weekday_days = [d for d in days if not is_holiday(d, custom_holidays)]
    for doc in staff_list:
        total_points = model.NewIntVar(0, 100, f"pts_{doc}")
        model.Add(total_points == sum(shifts[(doc, d)] for d in weekday_days) * 1 + sum(shifts[(doc, d)] for d in weekend_days) * 2)
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
        for d in days: shifts[(doc, d)] = model.NewBoolVar(f"s_big_{doc}_{d}")
    for d in days: model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
    for doc in all_staff:
        for d in range(1, len(days)): model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)
    for doc, dates_off in vs_leaves.items():
        if doc in vs_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    for doc, dates_off in r_leaves.items():
        if doc in r_staff:
            for d in dates_off: model.Add(shifts[(doc, d)] == 0)
    if forbidden_patterns:
        for pattern in forbidden_patterns: model.Add(sum([shifts[(doc, d)] for doc, d in pattern]) <= len(pattern) - 3)
    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on: model.Add(shifts[(doc, d)] == 1) 
    
    add_fairness_objective(model, shifts, r_staff, days, custom_holidays, obj_terms, weight=2000)
    add_point_system_constraint(model, shifts, r_staff, days, custom_holidays, obj_terms, sacrifices, limit=8, weight=200)
    add_spacing_preference(model, shifts, r_staff, days, obj_terms, weight=50)

    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off: obj_terms.append(shifts[(doc, d)] * -5000); sacrifices.append((shifts[(doc, d)], f"{doc} (R) 排入 No-Go ({month}/{d})"))
    for doc, dates_off in vs_nogo.items():
        if doc in vs_staff:
            for d in dates_off: obj_terms.append(shifts[(doc, d)] * -5000); sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 排入 No-Go ({month}/{d})"))
    for doc in vs_staff:
        wished_days = vs_wishes.get(doc, [])
        for d in days:
            if d not in wished_days: obj_terms.append(shifts[(doc, d)] * -5000); sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 支援非指定班 ({month}/{d})"))
    for doc, dates_on in r_wishes.items():
        if doc in r_staff:
            for d in dates_on: obj_terms.append(shifts[(doc, d)] * 10)

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
                    if doc in r_staff: r_schedule_map[doc].append(d)
    return solver, status, shifts, sacrifices, result_pattern, r_schedule_map

def solve_small_shift(pgy_staff, int_staff, r_staff, days, pgy_leaves, int_leaves, pgy_nogo, pgy_wishes, int_nogo, int_wishes, r_nogo, r_schedule_map, custom_holidays, forbidden_patterns=None):
    model = cp_model.CpModel()
    shifts = {}
    obj_terms = []
    sacrifices = []
    for doc in pgy_staff + int_staff:
        for d in days: shifts[(doc, d)] = model.NewBoolVar(f"s_sml_{doc}_{d}")
    for doc in r_staff:
        for d in days: shifts[(doc, d)] = model.NewBoolVar(f"s_sml_Rsupport_{doc}_{d}")
    all_small_candidates = pgy_staff + int_staff + r_staff
    for d in days: model.Add(sum(shifts[(doc, d)] for doc in all_small_candidates) == 1)
    for doc in pgy_staff + int_staff:
        for d in range(1, len(days)): model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)
    for doc in r_staff:
        big_shift_days = r_schedule_map.get(doc, [])
        r_nogo_days = r_nogo.get(doc, [])
        for d in days:
            if d in big_shift_days: model.Add(shifts[(doc, d)] == 0)
            is_too_close = False
            for b_day in big_shift_days:
                if abs(b_day - d) <= 2: is_too_close = True; break
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
                obj_terms.append(slack * -limit_weight); sacrifices.append((slack, f"{doc} 單週超過 2 班"))
        wd_cnt = sum(shifts[(doc, d)] for d in weekday_days)
        slack_wd = model.NewIntVar(0, 31, f"slk_wd_{doc}")
        model.Add(wd_cnt <= 6 + slack_wd)
        obj_terms.append(slack_wd * -limit_weight); sacrifices.append((slack_wd, f"{doc} 平日超過 6 班"))
        we_cnt = sum(shifts[(doc, d)] for d in weekend_days)
        slack_we = model.NewIntVar(0, 31, f"slk_we_{doc}")
        model.Add(we_cnt <= 2 + slack_we)
        obj_terms.append(slack_we * -limit_weight); sacrifices.append((slack_we, f"{doc} 假日超過 2 班"))

    add_point_system_constraint(model, shifts, pgy_staff + int_staff, days, custom_holidays, obj_terms, sacrifices, limit=10, weight=1000)
    for doc in r_staff:
        for d in days: obj_terms.append(shifts[(doc, d)] * -50000); sacrifices.append((shifts[(doc, d)], f"{doc} (R) 支援小班 ({month}/{d})"))
    add_fairness_objective(model, shifts, pgy_staff + int_staff, days, custom_holidays, obj_terms, weight=W_FAIRNESS)
    for doc in pgy_staff + int_staff:
        nogo_list = pgy_nogo.get(doc, []) if doc in pgy_staff else int_nogo.get(doc, [])
        wish_list = pgy_wishes.get(doc, []) if doc in pgy_staff else int_wishes.get(doc, [])
        for d in days:
            if d in nogo_list: obj_terms.append(shifts[(doc, d)] * -W_NOGO); sacrifices.append((shifts[(doc, d)], f"{doc} 排入不想值的班 ({month}/{d})"))
            if d in wish_list: obj_terms.append(shifts[(doc, d)] * W_WISH)
