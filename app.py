import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

# --- 設定頁面 ---
st.set_page_config(page_title="住院醫師極速排班系統 v1.1", layout="wide")

st.title("🏥 台灣住院醫師排班系統 (預假版)")
st.markdown("### 自動化排班引擎 | 支援：不連續值班、平均分配、個人預假")

# --- 側邊欄：輸入參數 ---
st.sidebar.header("1. 基本設定")

# 選擇年份與月份
year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, value=2025)
month = st.sidebar.number_input("月份", min_value=1, max_value=12, value=12)

# 計算該月天數
days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

# 輸入醫師名單
st.sidebar.subheader("醫師名單")
default_doctors = "王大明(R3), 李小華(R2), 張志明(R1), 陳春嬌(R1), 林醫師(NP)"
doc_input = st.sidebar.text_area("用逗號分隔", default_doctors)
doctors = [x.strip() for x in doc_input.split(",") if x.strip()]

# --- 新增功能：預假設定 ---
st.sidebar.markdown("---")
st.sidebar.header("2. 預假許願池")
st.sidebar.caption("每人最多可許願 3 天不值班")

leave_requests = {}

if doctors:
    with st.sidebar.expander("點擊展開填寫預假", expanded=True):
        for doc in doctors:
            # max_selections=3 限制最多選三天
            leaves = st.multiselect(
                f"{doc} 不想值班的日子",
                options=dates,
                max_selections=3,
                key=f"leave_{doc}"
            )
            leave_requests[doc] = leaves
else:
    st.sidebar.warning("請先輸入醫師名單")

# --- 核心演算法 (Google OR-Tools) ---
def solve_schedule(doctors, days_in_month, leave_requests):
    model = cp_model.CpModel()
    shifts = {}

    # 1. 定義變數
    for doc in doctors:
        for day in range(1, days_in_month + 1):
            shifts[(doc, day)] = model.NewBoolVar(f'shift_{doc}_{day}')

    # 2. 硬限制：每天必須且只能有 1 個人值班
    for day in range(1, days_in_month + 1):
        model.Add(sum(shifts[(doc, day)] for doc in doctors) == 1)

    # 3. 硬限制：不能連續值班 (PM Off 需求)
    for doc in doctors:
        for day in range(1, days_in_month):
            model.Add(shifts[(doc, day)] + shifts[(doc, day + 1)] <= 1)

    # === 新增功能：預假限制 ===
    # 如果 doc 在 day 有預假，則 shifts[(doc, day)] 必須為 0
    for doc, days_off in leave_requests.items():
        for day in days_off:
            model.Add(shifts[(doc, day)] == 0)

    # 4. 軟限制：盡量平均分配班數
    max_shifts_per_doc = (days_in_month // len(doctors)) + 1
    for doc in doctors:
        model.Add(sum(shifts[(doc, day)] for day in range(1, days_in_month + 1)) <= max_shifts_per_doc)

    # 求解
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    results = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        st.success(f"✅ 排班成功！ (狀態: {solver.StatusName(status)})")
        
        # 整理數據
        doctor_shift_counts = {doc: 0 for doc in doctors}
        
        for day in range(1, days_in_month + 1):
            for doc in doctors:
                if solver.Value(shifts[(doc, day)]) == 1:
                    weekday = date(year, month, day).strftime("%a")
                    is_weekend = "週末" if weekday in ["Sat", "Sun"] else "平日"
                    
                    results.append({
                        "日期": f"{month}/{day}",
                        "星期": weekday,
                        "值班醫師": doc,
                        "備註": is_weekend
                    })
                    doctor_shift_counts[doc] += 1
        
        return pd.DataFrame(results), doctor_shift_counts
    else:
        st.error("❌ 排班失敗！原因可能是：")
        st.markdown("""
        1. **預假衝突**：太多人同時要在同一天休假，導致那天沒人值班。
        2. **人力不足**：醫師太少，無法滿足排班規則。
        
        👉 請嘗試減少預假天數，或協調大家錯開休假。
        """)
        return None, None

# --- 執行排班按鈕 ---
st.markdown("---")
col1, col2 = st.columns([1, 4])
with col1:
    run_btn = st.button("🚀 開始排班", type="primary", use_container_width=True)

if run_btn:
    if not doctors:
        st.warning("請先輸入醫師名單")
    else:
        with st.spinner("正在運算最佳解 (考量勞基法 + 預假)..."):
            df_schedule, stats = solve_schedule(doctors, days_in_month, leave_requests)
        
        if df_schedule is not None:
            # 顯示統計
            st.subheader("📊 班數統計")
            st.bar_chart(pd.Series(stats))
            
            # 顯示是否有人有預假
            has_requests = any(len(v) > 0 for v in leave_requests.values())
            if has_requests:
                with st.expander("查看已核准的預假"):
                    st.write(leave_requests)

            # 顯示班表
            st.subheader(f"📅 {year}年{month}月 值班表")
            st.dataframe(df_schedule, use_container_width=True)
            
            # 下載按鈕
            csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下載 Excel/CSV",
                csv,
                f"schedule_{year}_{month}_v1.csv",
                "text/csv",
                key='download-csv'
            )
