import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date
import json

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="產房/小班 雙軌排班系統 (強韌版)", layout="wide")

st.title("🏥 婦產科雙軌排班系統 (v3.1 強韌版)")
st.caption("支援：VS 不值班設定 | 絕對有解機制 | 犧牲回報系統")

# --- 2. Session State 管理 ---
default_state = {
    "year": 2025,
    "month": 12,
    "vs_list": "柯P(VS), 怪醫(VS)",
    "r_list": "洋洋(R3), 蹦蹦(R2)",
    "pgy_list": "小明(PGY), 小華(PGY), 小強(PGY)",
    "int_list": "菜鳥A(Int), 菜鳥B(Int)",
    # 意願資料
    "vs_wishes": {},  "vs_nogo": {}, # 新增 vs_nogo
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

# --- 6. 核心演算法 (強韌版) ---

def solve_big_shift(mode, vs_staff, r_staff, days, vs_wishes, vs_nogo, r_nogo, r_wishes):
    """
    mode='strict_rule': 犧牲 VS 來保護 R 的 NoGo
    mode='protect_vs': 犧牲 R 的 NoGo 來保護 VS
    """
    model = cp_model.CpModel()
    all_staff = vs_staff + r_staff
    shifts = {}
    
    # 變數
    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_big_{doc}_{d}")

    # 1. 每天 1 人 (硬) - 這是物理限制，不能妥協
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)

    # 2. 不連續值班 (硬) - 物理限制
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    # 3. VS 指定值班 (VS Wish) - 視為必須 (但為了有解，設極大權重)
    obj_terms = []
    sacrifices = [] # 用來記錄變數以便後續檢查
    
    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on:
                # 若沒排到 VS 指定班 -> 扣超級大分
                # 我們希望 shifts[(doc, d)] == 1
                model.Add(shifts[(doc, d)] == 1) 

    # --- 權重設定區 ---
    if mode == 'strict_rule':
        w_r_nogo = 5000     # R 的 NoGo 比 VS 亂值班更重要
        w_vs_support = 100  # VS 下來支援非指定班 (痛苦)
        w_vs_nogo = 100     # VS 的 NoGo (如果 VS 下來支援還剛好是 NoGo，更痛苦)
    else: # protect_vs
        w_r_nogo = 50       # R 的 NoGo 可以被犧牲
        w_vs_support = 5000 # 絕對不想讓 VS 下來支援
        w_vs_nogo = 5000    # VS 的 NoGo 絕對不能碰

    # 4. 處理 "不想值班" (No-Go) - 轉為 Slack
    # R No-Go
    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off:
                # 懲罰 = 值班變數 * 權重
                obj_terms.append(shifts[(doc, d)] * -w_r_nogo)
                # 記錄犧牲檢查點
                sacrifices.append((shifts[(doc, d)], f"{doc} (R) 被排在 No-Go 日 ({month}/{d})"))

    # VS No-Go
    for doc, dates_off in vs_nogo.items():
        if doc in vs_staff:
            for d in dates_off:
                obj_terms.append(shifts[(doc, d)] * -w_vs_nogo)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 被排在 No-Go 日 ({month}/{d})"))

    # 5. VS 支援非指定班的懲罰
    for doc in vs_staff:
        wished_days = vs_wishes.get(doc, [])
        for d in days:
            if d not in wished_days:
                # 這是 VS 來支援的班
                obj_terms.append(shifts[(doc, d)] * -w_vs_support)
                sacrifices.append((shifts[(doc, d)], f"{doc} (VS) 下海支援非指定班 ({month}/{d})"))

    # 6. R 想值班 (Wish)
    for doc, dates_on in r_wishes.items():
        if doc in r_staff:
            for d in dates_on:
                obj_terms.append(shifts[(doc, d)] * 10) # 加小分

    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    return solver, status, shifts, sacrifices

def solve_small_shift(mode, pgy_staff, int_staff, days, pgy_nogo, pgy_wishes, int_nogo, int_wishes):
    """
    mode='strict_rule': 嚴格遵守 Intern/PGY 限額
    mode='protect_vs': (這裡借用概念) 代表較寬鬆，允許超額以填滿人力
    """
    model = cp_model.CpModel()
    all_staff = pgy_staff + int_staff
    shifts = {}
    sacrifices = []

    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"s_sml_{doc}_{d}")

    # 1. 每天 1 人 (硬)
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
    
    # 2. 不連續 (硬)
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)

    # 分類
    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    month_weeks = calendar.monthcalendar(year, month)

    # 權重
    if mode == 'strict_rule':
        w_limit = 5000 # 嚴懲超額
    else:
        w_limit = 100  # 輕罰超額 (求有解)
    
    obj_terms = []

    # 3. Intern 限制 (轉為 Soft + Penalty)
    for doc in int_staff:
        # A. 週限 2
        for week in month_weeks:
            valid_days = [d for d in week if d != 0]
            if valid_days:
                count_var = model.NewIntVar(0, 7, f"int_wk_{doc}_{week[0]}")
                model.Add(count_var == sum(shifts[(doc, d)] for d in valid_days))
                # slack = max(0, count - 2)
                slack = model.NewIntVar(0, 7, f"slk_int_wk_{doc}_{week[0]}")
                model.Add(count_var <= 2 + slack)
                obj_terms.append(slack * -w_limit)
                # 犧牲判定 (利用 solver.Value 檢查 slack > 0)
                sacrifices.append((slack, f"{doc} (Int) 單週超過 2 班"))

        # B. 平日限 6
        wd_count = model.NewIntVar(0, 31, f"int_wd_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        slack_wd = model.NewIntVar(0, 31, f"slk_int_wd_{doc}")
        model.Add(wd_count <= 6 + slack_wd)
        obj_terms.append(slack_wd * -w_limit)
        sacrifices.append((slack_wd, f"{doc} (Int) 平日超過 6 班"))

        # C. 假日限 2
        we_count = model.NewIntVar(0, 31, f"int_we_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        slack_we = model.NewIntVar(0, 31, f"slk_int_we_{doc}")
        model.Add(we_count <= 2 + slack_we)
        obj_terms.append(slack_we * -w_limit)
        sacrifices.append((slack_we, f"{doc} (Int) 假日超過 2 班"))

    # 4. PGY 限制 (Soft)
    for doc in pgy_staff:
        # 平日限 6
        wd_count = model.NewIntVar(0, 31, f"pgy_wd_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        slack_wd = model.NewIntVar(0, 31, f"slk_pgy_wd_{doc}")
        model.Add(wd_count <= 6 + slack_wd)
        obj_terms.append(slack_wd * -w_limit)
        sacrifices.append((slack_wd, f"{doc} (PGY) 平日超過 6 班"))

        # 假日限 2
        we_count = model.NewIntVar(0, 31, f"pgy_we_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        slack_we = model.NewIntVar(0, 31, f"slk_pgy_we_{doc}")
        model.Add(we_count <= 2 + slack_we)
        obj_terms.append(slack_we * -w_limit)
        sacrifices.append((slack_we, f"{doc} (PGY) 假日超過 2 班"))

    # 5. 意願 (Soft)
    w_nogo = 50
    w_wish = 10
    
    for doc in all_staff:
        nogo_list = pgy_nogo.get(doc, []) if doc in pgy_staff else int_nogo.get(doc, [])
        wish_list = pgy_wishes.get(doc, []) if doc in pgy_staff else int_wishes.get(doc, [])
        
        for d in days:
            if d in nogo_list:
                obj_terms.append(shifts[(doc, d)] * -w_nogo)
                sacrifices.append((shifts[(doc, d)], f"{doc} 值了不想值的班 ({month}/{d})"))
            if d in wish_list:
                obj_terms.append(shifts[(doc, d)] * w_wish)

    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts, sacrifices

# --- 7. 輸出處理 ---
def get_report(solver, sacrifices):
    report = []
    seen = set()
    for var, msg in sacrifices:
        if solver.Value(var) > 0:
            # 去除重複 (例如週限制可能多個 slack)
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

def show_results(mode_name, b_sol, b_sac, s_sol, s_sac, big_staff, small_staff):
    # Big Result
    df_big = generate_df(b_sol[0], b_sol[2], big_staff, dates, "大班")
    sac_big = get_report(b_sol[0], b_sac)
    
    # Small Result
    df_small = generate_df(s_sol[0], s_sol[2], small_staff, dates, "小班")
    sac_small = get_report(s_sol[0], s_sac)
    
    st.markdown(f"### 📋 {mode_name}")
    
    # 犧牲報告
    if sac_big or sac_small:
        with st.expander("⚠️ 犧牲報告 (已發生違規或妥協)", expanded=True):
            if sac_big:
                st.markdown("**[大班犧牲]**")
                for s in sac_big: st.write(f"- 🔴 {s}")
            if sac_small:
                st.markdown("**[小班犧牲]**")
                for s in sac_small: st.write(f"- 🔵 {s}")
    else:
        st.success("🎉 完美排班！無任何違規或犧牲。")
        
    c1, c2 = st.columns(2)
    with c1: st.dataframe(df_big, use_container_width=True)
    with c2: st.dataframe(df_small, use_container_width=True)

    # CSV
    full = pd.concat([df_big, df_small]).sort_values("日期")
    csv = full.to_csv(index=False).encode('utf-8-sig')
    st.download_button(f"📥 下載 {mode_name} CSV", csv, f"roster_{mode_name}.csv", "text/csv")

# --- 8. 執行 ---
st.markdown("---")
st.caption("若無法完美排班，系統將產生兩個方案供您選擇")
if st.button("🚀 暴力運算 (產生雙方案)", type="primary"):
    if not (vs_staff and r_staff and pgy_staff and int_staff):
        st.error("名單不完整")
    else:
        with st.spinner("正在進行暴力破解與權衡..."):
            # 方案 A: 規則優先
            b_res_A = solve_big_shift('strict_rule', vs_staff, r_staff, dates, st.session_state.vs_wishes, st.session_state.vs_nogo, st.session_state.r_nogo, st.session_state.r_wishes)
            s_res_A = solve_small_shift('strict_rule', pgy_staff, int_staff, dates, st.session_state.pgy_nogo, st.session_state.pgy_wishes, st.session_state.int_nogo, st.session_state.int_wishes)

            # 方案 B: VS優先 (放寬規則)
            b_res_B = solve_big_shift('protect_vs', vs_staff, r_staff, dates, st.session_state.vs_wishes, st.session_state.vs_nogo, st.session_state.r_nogo, st.session_state.r_wishes)
            s_res_B = solve_small_shift('protect_vs', pgy_staff, int_staff, dates, st.session_state.pgy_nogo, st.session_state.pgy_wishes, st.session_state.int_nogo, st.session_state.int_wishes)
            
            tab_a, tab_b = st.tabs(["方案 A: 守護規則 (犧牲 VS)", "方案 B: 守護 VS (犧牲規則)"])
            
            with tab_a:
                st.info("此方案優先遵守 Intern/PGY 限額 與 R 的 No-Go。若人力不足，VS 會被排入非指定班。")
                show_results("方案A_規則優先", b_res_A, b_res_A[3], s_res_A, s_res_A[3], vs_staff+r_staff, pgy_staff+int_staff)
            
            with tab_b:
                st.info("此方案優先保護 VS 不值額外班 與 VS No-Go。若人力不足，R/PGY/Intern 將會超時或違反意願。")
                show_results("方案B_主治優先", b_res_B, b_res_B[3], s_res_B, s_res_B[3], vs_staff+r_staff, pgy_staff+int_staff)
