import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date
import json
import io

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="產房/小班 雙軌排班系統", layout="wide")

st.title("🏥 婦產科雙軌排班系統 (Big/Small Shift)")
st.caption("v3.0 JSON版：主治/住院/PGY/實習 分流排班 | 支援設定檔存取")

# --- 2. Session State 管理 (用於 JSON 存取) ---
# 初始化預設值
default_state = {
    "year": 2025,
    "month": 12,
    "vs_list": "柯P(VS), 怪醫(VS)",
    "r_list": "洋洋(R3), 蹦蹦(R2)",
    "pgy_list": "小明(PGY), 小華(PGY), 小強(PGY)",
    "int_list": "菜鳥A(Int), 菜鳥B(Int)",
    # 預假與指定 (Dictionary keys must be strings for JSON)
    "vs_wishes": {},  # VS 指定值班
    "r_wishes": {},   # R 想值班 (Option)
    "r_nogo": {},     # R 絕對不值
    "pgy_wishes": {}, # PGY 想值 (Option)
    "pgy_nogo": {},   # PGY 不想值 (Soft)
    "int_wishes": {}, # Int 想值 (Option)
    "int_nogo": {}    # Int 不想值 (Soft)
}

# 如果 session_state 還沒有這些 key，就初始化
for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. 側邊欄：JSON I/O 與 時間設定 ---
st.sidebar.header("📂 檔案存取")

# 下載按鈕
def get_current_config():
    return {k: st.session_state[k] for k in default_state.keys()}

config_json = json.dumps(get_current_config(), ensure_ascii=False, indent=2)
st.sidebar.download_button(
    label="💾 下載設定檔 (JSON)",
    data=config_json,
    file_name="roster_config.json",
    mime="application/json"
)

# 上傳功能
uploaded_file = st.sidebar.file_uploader("📂 讀取設定檔 (JSON)", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        for key in default_state.keys():
            if key in data:
                st.session_state[key] = data[key]
        st.sidebar.success("讀取成功！畫面已更新")
    except Exception as e:
        st.sidebar.error(f"讀取失敗: {e}")

st.sidebar.markdown("---")
st.sidebar.header("📅 時間設定")
year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, key="year")
month = st.sidebar.number_input("月份", min_value=1, max_value=12, key="month")

days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

# --- 4. 人員名單設定 (Tab 分頁) ---
st.subheader("1. 人員與班別設定")
tab1, tab2 = st.tabs(["🔴 大班 (產房班)", "🔵 小班 (一般班)"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 👨‍⚕️ 主治醫師 (VS)")
        vs_input = st.text_area("名單 (逗號分隔)", key="vs_list")
        vs_staff = [x.strip() for x in vs_input.split(",") if x.strip()]
    with col2:
        st.markdown("#### 🧑‍⚕️ 住院醫師 (R)")
        r_input = st.text_area("名單 (逗號分隔)", key="r_list")
        r_staff = [x.strip() for x in r_input.split(",") if x.strip()]

with tab2:
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("#### 🎓 PGY 醫師")
        pgy_input = st.text_area("名單 (逗號分隔)", key="pgy_list")
        pgy_staff = [x.strip() for x in pgy_input.split(",") if x.strip()]
    with col4:
        st.markdown("#### 🐣 實習醫師 (Intern)")
        int_input = st.text_area("名單 (逗號分隔)", key="int_list")
        int_staff = [x.strip() for x in int_input.split(",") if x.strip()]

# --- 5. 意願調查 (連動 Session State) ---
st.subheader("2. 排班意願")

# 輔助函式：處理 multiselect 的 key 與 session state 同步
def update_pref(key_prefix, staff_list, label_suffix, help_text):
    prefs = st.session_state.get(key_prefix, {})
    new_prefs = {}
    st.markdown(f"**{label_suffix}**")
    if help_text: st.caption(help_text)
    
    for doc in staff_list:
        # 確保 key 存在且為 list
        default = prefs.get(doc, []) if isinstance(prefs.get(doc), list) else []
        # 過濾掉不在 dates 裡的無效日期
        default = [d for d in default if d in dates]
        
        selection = st.multiselect(f"{doc}", options=dates, default=default, key=f"{key_prefix}_{doc}_widget")
        new_prefs[doc] = selection
    
    st.session_state[key_prefix] = new_prefs

with st.expander("🔴 大班意願設定 (VS & R)", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        st.info("主治醫師 (VS)")
        # VS 只有「想要值」 (優先排)
        update_pref("vs_wishes", vs_staff, "✅ 指定值班 (優先權 Max)", "系統會先排這些班，剩下的才給 R")
    with c2:
        st.info("住院醫師 (R)")
        # R 有「不想值」(絕對不行) 和 「想值」(Option)
        update_pref("r_nogo", r_staff, "🚫 絕對不值 (Hard Limit)", "這些日子絕對不會排班")
        st.markdown("---")
        update_pref("r_wishes", r_staff, "💖 想要值班 (Option)", "行有餘力會盡量滿足")

with st.expander("🔵 小班意願設定 (PGY & Int)", expanded=True):
    c3, c4 = st.columns(2)
    with c3:
        st.info("PGY 醫師")
        update_pref("pgy_nogo", pgy_staff, "💔 不想值班 (盡量滿足)", "系統會盡量避開")
        update_pref("pgy_wishes", pgy_staff, "💖 想要值班 (不一定滿足)", "沒衝突時會優先排")
    with c4:
        st.info("實習醫師 (Intern)")
        update_pref("int_nogo", int_staff, "💔 不想值班 (盡量滿足)", "系統會盡量避開")
        update_pref("int_wishes", int_staff, "💖 想要值班 (不一定滿足)", "沒衝突時會優先排")

# --- 6. 核心演算法 ---

# A. 大班演算法 (Big Shift)
def solve_big_shift(vs_staff, r_staff, days, vs_wishes, r_nogo, r_wishes):
    model = cp_model.CpModel()
    all_staff = vs_staff + r_staff
    shifts = {}
    
    # 變數
    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"shift_big_{doc}_{d}")
            
    # 1. 每天 1 人
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
        
    # 2. 不連續值班
    for doc in all_staff:
        for d in range(1, len(days)): # days are 1-based
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)
             
    # 3. VS 指定值班 (Hard) - 必須滿足
    for doc, dates_on in vs_wishes.items():
        if doc in vs_staff:
            for d in dates_on:
                model.Add(shifts[(doc, d)] == 1)
                
    # 4. R 絕對不值 (Hard)
    for doc, dates_off in r_nogo.items():
        if doc in r_staff:
            for d in dates_off:
                model.Add(shifts[(doc, d)] == 0)
                
    # 5. 目標函式 (Soft)
    # 優先順序：滿足 R Wish > 減少 VS 非指定班 (讓 R 填空) > VS 支援
    obj_terms = []
    
    # R 想要值班 (+2 分)
    for doc, dates_on in r_wishes.items():
        if doc in r_staff:
            for d in dates_on:
                obj_terms.append(shifts[(doc, d)] * 2)
                
    # VS 如果值了「非指定」的班，扣大分 (-100 分) -> 迫使 R 去值，除非 R 真的沒辦法
    for doc in vs_staff:
        wished_days = vs_wishes.get(doc, [])
        for d in days:
            if d not in wished_days:
                # 這是 VS 來支援的班，盡量不要發生
                obj_terms.append(shifts[(doc, d)] * -100)
                
    model.Maximize(sum(obj_terms))
    
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts

# B. 小班演算法 (Small Shift)
def solve_small_shift(pgy_staff, int_staff, days, 
                      pgy_nogo, pgy_wishes, int_nogo, int_wishes):
    model = cp_model.CpModel()
    all_staff = pgy_staff + int_staff
    shifts = {}
    
    for doc in all_staff:
        for d in days:
            shifts[(doc, d)] = model.NewBoolVar(f"shift_small_{doc}_{d}")
            
    # 1. 每天 1 人
    for d in days:
        model.Add(sum(shifts[(doc, d)] for doc in all_staff) == 1)
        
    # 2. 不連續值班
    for doc in all_staff:
        for d in range(1, len(days)):
             model.Add(shifts[(doc, d)] + shifts[(doc, d+1)] <= 1)
             
    # 日期分類
    weekend_days = [d for d in days if date(year, month, d).weekday() >= 5]
    weekday_days = [d for d in days if date(year, month, d).weekday() < 5]
    month_weeks = calendar.monthcalendar(year, month)
    
    # 3. Intern 限制 (Hard)
    # - 單週 <= 2
    # - 月平日 <= 6
    # - 月假日 <= 2
    for doc in int_staff:
        # 週限制
        for week in month_weeks:
            valid_days = [d for d in week if d != 0]
            if valid_days:
                model.Add(sum(shifts[(doc, d)] for d in valid_days) <= 2)
        # 月限制
        model.Add(sum(shifts[(doc, d)] for d in weekday_days) <= 6)
        model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= 2)
        
    # 4. PGY 限制 (Soft Basis) -> 目標函式處理
    # "如果真的不行才能打破這個規則" -> 給予打破規則極高的扣分
    obj_terms = []
    
    # 變數：PGY 是否超出限制
    # 這邊簡化處理：直接給予遵守規則加分，違反則不加分(相對扣分)
    # 更好的做法是用 Soft Upper Bound，但為了效能，我們用 Penalty 方式
    
    penalty_weight = 500 # 違反限制扣大分
    pref_weight = 10     # 滿足意願加小分
    
    for doc in pgy_staff:
        # 建立懲罰變數：超過 6 平日?
        # 使用 NewIntVar 統計平日班數
        weekday_count = model.NewIntVar(0, 31, f"wd_count_{doc}")
        model.Add(weekday_count == sum(shifts[(doc, d)] for d in weekday_days))
        
        # 建立懲罰變數：超過 2 假日?
        weekend_count = model.NewIntVar(0, 31, f"we_count_{doc}")
        model.Add(weekend_count == sum(shifts[(doc, d)] for d in weekend_days))

        # 我們希望 weekday_count <= 6, weekend_count <= 2
        # 在 OR-Tools 若要實作 soft constraint，可以引入 slack 變數
        # weekday_count <= 6 + slack_wd
        slack_wd = model.NewIntVar(0, 31, f"slack_wd_{doc}")
        model.Add(weekday_count <= 6 + slack_wd)
        
        slack_we = model.NewIntVar(0, 31, f"slack_we_{doc}")
        model.Add(weekend_count <= 2 + slack_we)
        
        # 目標：最小化 slack (也就是盡量不要超過)
        obj_terms.append(slack_wd * -penalty_weight)
        obj_terms.append(slack_we * -penalty_weight)
        
    # 5. 意願處理 (Soft) - 盡量滿足
    for doc in all_staff:
        # 取得 NoGo 和 Wish
        nogo_list = pgy_nogo.get(doc, []) if doc in pgy_staff else int_nogo.get(doc, [])
        wish_list = pgy_wishes.get(doc, []) if doc in pgy_staff else int_wishes.get(doc, [])
        
        for d in days:
            if d in nogo_list:
                # 不想值卻值了 -> 扣分
                obj_terms.append(shifts[(doc, d)] * -pref_weight)
            if d in wish_list:
                # 想值且值了 -> 加分
                obj_terms.append(shifts[(doc, d)] * pref_weight)
                
    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts

# --- 7. 結果顯示與下載 ---
def generate_result_df(solver, shifts, staff_list, days, shift_name):
    results = []
    for d in days:
        for doc in staff_list:
            if solver.Value(shifts[(doc, d)]) == 1:
                weekday_str = date(year, month, d).strftime("%a")
                is_weekend = date(year, month, d).weekday() >= 5
                results.append({
                    "日期": f"{month}/{d}",
                    "星期": weekday_str,
                    "班別": shift_name,
                    "醫師": doc,
                    "類型": "假日" if is_weekend else "平日"
                })
    return pd.DataFrame(results)

def get_html_calendar(df_big, df_small):
    cal = calendar.monthcalendar(year, month)
    
    # 建立查找表 day -> (big_doc, small_doc)
    map_big = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_big.iterrows()}
    map_small = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_small.iterrows()}
    
    html = """
    <style>
        .cal-table {width:100%; border-collapse:collapse; table-layout:fixed;}
        .cal-table td {height:110px; border:1px solid #ddd; vertical-align:top; padding:4px; background:#fff;}
        .cal-table th {background:#f0f2f6; border:1px solid #ddd; padding:5px;}
        .day-num {font-size:12px; color:#666; text-align:right;}
        .badge {padding:2px 4px; border-radius:4px; font-size:12px; margin-bottom:2px; display:block; font-weight:bold;}
        .big-badge {background:#ffebee; color:#c62828;} /* 紅色系 */
        .small-badge {background:#e3f2fd; color:#1565c0;} /* 藍色系 */
        .weekend {background-color:#fafafa !important;}
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
                if b_doc: html += f'<div class="badge big-badge">產: {b_doc}</div>'
                if s_doc: html += f'<div class="badge small-badge">小: {s_doc}</div>'
                html += "</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# --- 8. 執行按鈕 ---
st.markdown("---")
if st.button("🚀 開始雙軌排班", type="primary"):
    if not (vs_staff and r_staff and pgy_staff and int_staff):
        st.error("❌ 所有類別的醫師名單都不能為空！")
    else:
        with st.spinner("正在運算大班與小班模型..."):
            # 1. 算大班
            solver_b, status_b, shifts_b = solve_big_shift(
                vs_staff, r_staff, dates, 
                st.session_state["vs_wishes"], 
                st.session_state["r_nogo"], 
                st.session_state["r_wishes"]
            )
            
            # 2. 算小班
            solver_s, status_s, shifts_s = solve_small_shift(
                pgy_staff, int_staff, dates,
                st.session_state["pgy_nogo"], st.session_state["pgy_wishes"],
                st.session_state["int_nogo"], st.session_state["int_wishes"]
            )
            
            if (status_b == cp_model.OPTIMAL or status_b == cp_model.FEASIBLE) and \
               (status_s == cp_model.OPTIMAL or status_s == cp_model.FEASIBLE):
                
                df_big = generate_result_df(solver_b, shifts_b, vs_staff + r_staff, dates, "大班(產房)")
                df_small = generate_result_df(solver_s, shifts_s, pgy_staff + int_staff, dates, "小班")
                
                st.success("✅ 排班成功！")
                
                # 顯示月曆
                st.subheader(f"📅 {year}年{month}月 總班表")
                st.markdown(get_html_calendar(df_big, df_small), unsafe_allow_html=True)
                
                st.markdown("---")
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🔴 大班清單")
                    st.dataframe(df_big, use_container_width=True)
                with c2:
                    st.subheader("🔵 小班清單")
                    st.dataframe(df_small, use_container_width=True)
                    
                # 下載 CSV
                full_df = pd.concat([df_big, df_small]).sort_values(by=["日期"])
                csv = full_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載完整班表 (CSV)", csv, "full_roster.csv", "text/csv")
                
            else:
                st.error("排班失敗！可能限制過於嚴格 (例如 R 不值班日太多，或 Intern 人力不足)。")
