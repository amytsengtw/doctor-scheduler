import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date
import json
import hashlib

# --- 1. Page Configuration ---
st.set_page_config(page_title="耕莘醫院雙軌排班系統 (v4.5)", layout="wide")

st.title("🏥 耕莘醫院婦產科雙軌排班系統 (v4.5)")
st.caption("救援機制調整：PGY/Int 點數 > 10 點才啟動 R 支援 | 平日=1點, 假日=2點")

# --- 2. Session State Management ---
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

# --- 3. Sidebar: JSON I/O ---
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

# --- 4. Staff & Constraints UI ---
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

# Absolute Leaves
with st.expander("⛔️ 請假/未到職設定 (絕對排除)", expanded=True):
    st.error("注意：此區為硬限制，系統絕對不會排班。")
    col_l, col_r = st.columns(2)
    with col_l:
        update_pref("vs_leaves", vs_staff, "VS 請假", "")
        update_pref("r_leaves", r_staff, "R 請假", "")
    with col_r:
        update_pref("pgy_leaves", pgy_staff, "PGY 請假", "")
        update_pref("int_leaves", int_staff, "Int 請假", "")

# Soft Constraints
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

# --- 5. Core Algorithms ---

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
        
        # Penalize exceeding the limit
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
    
    # R Point Limit (Still strict around 8 for Big Shift, but low weight)
    add_point_system_constraint(model, shifts, r_staff, days, obj_terms, sacrifices, limit=8, weight=200)
    add_spacing_preference(model, shifts, r_staff, days, obj_terms, weight=50)

    # Preferences
    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off:
                obj_terms.append(shifts[(
