import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date
import json
import hashlib

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="產房/小班 雙軌排班系統 (統計版)", layout="wide")

st.title("🏥 婦產科雙軌排班系統 (v3.2 統計視覺化版)")
st.caption("新增：個人專屬顏色 | 即時班數統計 (Total/平日/假日)")

# --- 2. Session State 管理 ---
default_state = {
    "year": 2025,
    "month": 12,
    "vs_list": "柯P(VS), 怪醫(VS)",
    "r_list": "洋洋(R3), 蹦蹦(R2)",
    "pgy_list": "小明(PGY), 小華(PGY), 小強(PGY)",
    "int_list": "菜鳥A(Int), 菜鳥B(Int)",
    # 意願資料
    "vs_wishes": {},  "vs_nogo": {},
    "r_wishes": {},   "r_nogo": {},
    "pgy_wishes": {}, "pgy_nogo": {},
    "int_wishes": {}, "int_nogo": {}
}

for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. 側邊欄：JSON I/O ---
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

# --- 4. 人員名單設定 ---
st.subheader("1. 人員設定")
tab1, tab2 = st.tabs(["🔴 大班 (產房)", "🔵 小班 (一般)"])
with tab1:
    c1, c2 = st.columns(2)
    vs_staff = [x.strip() for x in st.text_area("VS 名單", key="vs_list").split(",") if x.strip()]
    r_staff = [x.strip() for x in st.text_area("R 名單", key="r_list").split(",") if x.strip()]
with tab2:
    c3, c4 = st.columns(2)
    pgy_staff = [x.strip() for x in st.text_area("PGY 名單", key="pgy_list").split(",") if x.strip()]
    int_staff = [x.strip() for x in st.text_area("Intern 名單", key="int_list").split(",") if x.strip()]

# --- 5. 意願設定 ---
st.subheader("2. 意願設定")
def update_pref(key, staff, label, help_t):
    prefs = st.session_state.get(key, {})
    new_prefs = {}
    st.markdown(f"**{label}**")
    st.caption(help_t)
    for doc in staff:
        default = [d for d in prefs.get(doc, []) if d in dates]
        selection = st.multiselect(doc, dates, default=default, key=f"{key}_{doc}_w")
        new_prefs[doc] = selection
    st.session_state[key] = new_prefs

with st.expander("🔴 大班意願 (VS & R)", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        st.info("VS 主治醫師")
        update_pref("vs_wishes", vs_staff, "✅ 指定值班 (優先)", "一定要排")
        update_pref("vs_nogo", vs_staff, "🚫 不想值班 (No-Go)", "若被排入代表犧牲了 VS")
    with c2:
        st.info("R 住院醫師")
        update_pref("r_nogo", r_staff, "🚫 絕對不值 (No-Go)", "若被排入代表犧牲了 R")
        update_pref("r_wishes", r_staff, "💖 想要值班 (Option)", "加分項目")

with st.expander("🔵 小班意願 (PGY & Int)", expanded=True):
    c3, c4 = st.columns(2)
    with c3:
        st.info("PGY")
        update_pref("pgy_nogo", pgy_staff, "💔 不想值", "若排入會扣分")
        update_pref("pgy_wishes", pgy_staff, "💖 想值", "加分")
    with c4:
        st.info("Intern")
        update_pref("int_nogo", int_staff, "💔 不想值", "若排入會扣分")
        update_pref("int_wishes", int_staff, "💖 想值", "加分")

# --- 6. 核心演算法 ---
def solve_big_shift(mode, vs_staff, r_staff, days, vs_wishes, vs_nogo, r_nogo, r_wishes):
    model = cp_model.CpModel()
    all_staff = vs_staff + r_staff
    shifts = {}
    
    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_big_{doc}_{d}")

    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)

    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    obj_terms = []
    sacrifices = []
    
    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on:
                model.Add(shifts[(doc, d)] == 1) 

    if mode == 'strict_rule':
        w_r_nogo = 5000; w_vs_support = 100; w_vs_nogo = 100
    else: 
        w_r_nogo = 50; w_vs_support = 5000; w_vs_nogo = 5000

    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -w_r_nogo)
                sacrifices.append((shifts[(doc, d)], f"{doc} (R) 排入 No-Go ({month}/{d})"))

    for doc, dates_off in vs_nogo.items():
        if doc in vs_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -w_vs_nogo)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 排入 No-Go ({month}/{d})"))

    for doc in vs_staff:
        wished_days = vs_wishes.get(doc, [])
        for d in days:
            if d not in wished_days:
                obj_terms.append(shifts[(doc, d)] * -w_vs_support)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 支援非指定班 ({month}/{d})"))

    for doc, dates_on in r_wishes.items():
        if doc in r_staff:
            for d in dates_on:
                obj_terms.append(shifts[(doc, d)] * 10)

    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts, sacrifices

def solve_small_shift(mode, pgy_staff, int_staff, days, pgy_nogo, pgy_wishes, int_nogo, int_wishes):
    model = cp_model.CpModel()
    all_staff = pgy_staff + int_staff
    shifts = {}
    sacrifices = []

    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_{doc}_{d}")

    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
    
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    month_weeks = calendar.monthcalendar(year, month)

    w_limit = 5000 if mode == 'strict_rule' else 100
    obj_terms = []

    for doc in int_staff:
        for week in month_weeks:
            valid_days = [d for d in week if d != 0]
            if valid_days:
                count_var = model.NewIntVar(0, 7, f"int_wk_{doc}_{week[0]}")
                model.Add(count_var == sum(shifts[(doc, d)] for d in valid_days))
                slack = model.NewIntVar(0, 7, f"slk_int_wk_{doc}_{week[0]}")
                model.Add(count_var <= 2 + slack)
                obj_terms.append(slack * -w_limit)
                sacrifices.append((slack, f"{doc} (Int) 週超 2 班"))

        wd_count = model.NewIntVar(0, 31, f"int_wd_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        slack_wd = model.NewIntVar(0, 31, f"slk_int_wd_{doc}")
        model.Add(wd_count <= 6 + slack_wd)
        obj_terms.append(slack_wd * -w_limit)
        sacrifices.append((slack_wd, f"{doc} (Int) 平日超 6 班"))

        we_count = model.NewIntVar(0, 31, f"int_we_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        slack_we = model.NewIntVar(0, 31, f"slk_int_we_{doc}")
        model.Add(we_count <= 2 + slack_we)
        obj_terms.append(slack_we * -w_limit)
        sacrifices.append((slack_we, f"{doc} (Int) 假日超 2 班"))

    for doc in pgy_staff:
        wd_count = model.NewIntVar(0, 31, f"pgy_wd_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        slack_wd = model.NewIntVar(0, 31, f"slk_pgy_wd_{doc}")
        model.Add(wd_count <= 6 + slack_wd)
        obj_terms.append(slack_wd * -w_limit)
        sacrifices.append((slack_wd, f"{doc} (PGY) 平日超 6 班"))

        we_count = model.NewIntVar(0, 31, f"pgy_we_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        slack_we = model.NewIntVar(0, 31, f"slk_pgy_we_{doc}")
        model.Add(we_count <= 2 + slack_we)
        obj_terms.append(slack_we * -w_limit)
        sacrifices.append((slack_we, f"{doc} (PGY) 假日超 2 班"))

    w_nogo = 50; w_wish = 10
    for doc in all_staff:
        nogo_list = pgy_nogo.get(doc, []) if doc in pgy_staff else int_nogo.get(doc, [])
        wish_list = pgy_wishes.get(doc, []) if doc in pgy_staff else int_wishes.get(doc, [])
        
        for d in days:
            if d in nogo_list:
                obj_terms.append(shifts[(doc, d)] * -w_nogo)
                sacrifices.append((shifts[(doc, d)], f"{doc} 排入不想值的班 ({month}/{d})"))
            if d in wish_list:
                obj_terms.append(shifts[(doc, d)] * w_wish)

    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts, sacrifices

# --- 7. 視覺化與統計工具 ---

def get_doctor_color(name):
    """根據名字產生固定的柔和背景色"""
    # 定義一組柔和的 pastel colors
    palette = [
        "#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF", 
        "#E6B3FF", "#FFB3E6", "#C9C9FF", "#FFD1DC", "#E0F7FA",
        "#F0F4C3", "#D7CCC8", "#F8BBD0", "#C5CAE9", "#B2DFDB"
    ]
    # 用 hash 決定顏色
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(palette)
    return palette[idx]

def calculate_stats(df):
    """計算每個醫師的總班數、平日、假日"""
    if df.empty:
        return pd.DataFrame()
    
    # 建立統計表
    stats = df.groupby('醫師')['類型'].value_counts().unstack(fill_value=0)
    
    # 確保有 '平日' 和 '假日' 欄位
    if '平日' not in stats.columns: stats['平日'] = 0
    if '假日' not in stats.columns: stats['假日'] = 0
    
    stats['Total'] = stats['平日'] + stats['假日']
    
    # 重新排序欄位
    return stats[['Total', '平日', '假日']].sort_values(by='Total', ascending=False)

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
        .badge {
            padding:4px 6px; border-radius:6px; font-size:13px; 
            margin-bottom:4px; display:block; font-weight:bold;
            color: #333; text-shadow: 0 0 2px #fff;
            border: 1px solid rgba(0,0,0,0.1);
        }
        .weekend {background-color:#fafafa !important;}
        .shift-label {font-size: 10px; color: #666; margin-right: 3px;}
    </style>
    <table class="cal-table"><thead><tr>
    <th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color:red">Sat</th><th style="color:red">Sun</th>
    </tr></thead><tbody>
    """
    
    for week in cal:
        html += "<tr>"
        for i, day in enumerate(week):
            cls = "weekend" if i >= 5 else ""
            if day == 0:
                html += f'<td class="empty"></td>'
            else:
                b_doc = map_big.get(day, "")
                s_doc = map_small.get(day, "")
                
                html += f'<td class="{cls}"><div class="day-num">{day}</div>'
                
                if b_doc: 
                    color = get_doctor_color(b_doc)
                    html += f'<div class="badge" style="background-color:{color};"><span class="shift-label">產:</span>{b_doc}</div>'
                
                if s_doc: 
                    color = get_doctor_color(s_doc)
                    html += f'<div class="badge" style="background-color:{color};"><span class="shift-label">小:</span>{s_doc}</div>'
                
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

def show_results(mode_name, b_sol, b_sac, s_sol, s_sac, big_staff, small_staff):
    df_big = generate_df(b_sol[0], b_sol[2], big_staff, dates, "大班")
    sac_big = get_report(b_sol[0], b_sac)
    
    df_small = generate_df(s_sol[0], s_sol[2], small_staff, dates, "小班")
    sac_small = get_report(s_sol[0], s_sac)
    
    st.markdown(f"### 📋 {mode_name}")
    
    if sac_big or sac_small:
        with st.expander("⚠️ 犧牲報告", expanded=True):
            if sac_big:
                st.write("**[大班]**")
                for s in sac_big: st.write(f"- 🔴 {s}")
            if sac_small:
                st.write("**[小班]**")
                for s in sac_small: st.write(f"- 🔵 {s}")
    else:
        st.success("🎉 完美排班！")
        
    st.markdown("#### 📊 班表與統計")
    
    # 顯示統計
    stats_big = calculate_stats(df_big)
    stats_small = calculate_stats(df_small)
    
    c1, c2 = st.columns([1, 1])
    with c1: 
        st.markdown("**大班 (VS & R) 統計**")
        st.dataframe(stats_big, use_container_width=True)
    with c2: 
        st.markdown("**小班 (PGY & Int) 統計**")
        st.dataframe(stats_small, use_container_width=True)

    # 顯示詳細清單
    with st.expander("🔍 查看詳細班表清單"):
        col_l, col_r = st.columns(2)
        with col_l: st.dataframe(df_big, use_container_width=True)
        with col_r: st.dataframe(df_small, use_container_width=True)

    # 顯示月曆
    st.markdown("#### 📅 視覺化日曆")
    st.markdown(get_html_calendar(df_big, df_small), unsafe_allow_html=True)

    # CSV
    full = pd.concat([df_big, df_small]).sort_values("日期")
    csv = full.to_csv(index=False).encode('utf-8-sig')
    st.download_button(f"📥 下載 {mode_name} CSV", csv, f"roster_{mode_name}.csv", "text/csv")

# --- 8. 執行 ---
st.markdown("---")
st.caption("系統將產生兩個方案：A方案遵守工時規則，B方案保護主治醫師")
if st.button("🚀 暴力運算 (產生雙方案)", type="primary"):
    if not (vs_staff and r_staff and pgy_staff and int_staff):
        st.error("名單不完整")
    else:
        with st.spinner("正在進行權衡運算..."):
            b_res_A = solve_big_shift('strict_rule', vs_staff, r_staff, dates, st.session_state.vs_wishes, st.session_state.vs_nogo, st.session_state.r_nogo, st.session_state.r_wishes)
            s_res_A = solve_small_shift('strict_rule', pgy_staff, int_staff, dates, st.session_state.pgy_nogo, st.session_state.pgy_wishes, st.session_state.int_nogo, st.session_state.int_wishes)

            b_res_B = solve_big_shift('protect_vs', vs_staff, r_staff, dates, st.session_state.vs_wishes, st.session_state.vs_nogo, st.session_state.r_nogo, st.session_state.r_wishes)
            s_res_B = solve_small_shift('protect_vs', pgy_staff, int_staff, dates, st.session_state.pgy_nogo, st.session_state.pgy_wishes, st.session_state.int_nogo, st.session_state.int_wishes)
            
            tab_a, tab_b = st.tabs(["方案 A: 守護規則 (犧牲 VS)", "方案 B: 守護 VS (犧牲規則)"])
            
            with tab_a:
                st.info("優先保護 R/PGY/Int 的工時與意願。若人力不足，VS 可能需要支援。")
                show_results("方案A_規則優先", b_res_A, b_res_A[3], s_res_A, s_res_A[3], vs_staff+r_staff, pgy_staff+int_staff)
            
            with tab_b:
                st.info("優先保護 VS 不值額外班與休假。若人力不足，R/PGY/Intern 可能會超時。")
                show_results("方案B_主治優先", b_res_B, b_res_B[3], s_res_B, s_res_B[3], vs_staff+r_staff, pgy_staff+int_staff)
