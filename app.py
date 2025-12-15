import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

st.set_page_config(page_title="住院醫師排班系統", layout="wide")

st.title("🏥 台灣住院醫師排班系統")

st.sidebar.header("設定")

year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, value=2025)
month = st.sidebar.number_input("月份", min_value=1, max_value=12, value=12)

days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.subheader("醫師名單")
default_doctors = "跳跳(R3), 蹦蹦(R2), 跑跑(R1), 小白(R1), 洋洋(NP)"
doc_input = st.sidebar.text_area("用逗號分隔", default_doctors)
doctors = [x.strip() for x in doc_input.split(",") if x.strip()]

st.sidebar.markdown("---")
st.sidebar.header("預假設定")

leave_requests = {}

if doctors:
    with st.sidebar.expander("點擊展開填寫預假", expanded=True):
        for doc in doctors:
            leaves = st.multiselect(
                f"{doc} 預假日期",
                options=dates,
                max_selections=3,
                key=f"leave_{doc}"
            )
            leave_requests[doc] = leaves
else:
    st.sidebar.warning("請先輸入醫師名單")

def solve_schedule(doctors, days_in_month, leave_requests):
    model = cp_model.CpModel()
    shifts = {}

    for doc in doctors:
        for day in range(1, days_in_month + 1):
            shifts[(doc, day)] = model.NewBoolVar(f'shift_{doc}_{day}')

    for day in range(1, days_in_month + 1):
        model.Add(sum(shifts[(doc, day)] for doc in doctors) == 1)

    for doc in doctors:
        for day in range(1, days_in_month):
            model.Add(shifts[(doc, day)] + shifts[(doc, day + 1)] <= 1)

    for doc, days_off in leave_requests.items():
        for day in days_off:
            model.Add(shifts[(doc, day)] == 0)

    max_shifts_per_doc = (days_in_month // len(doctors)) + 1
    for doc in doctors:
        model.Add(sum(shifts[(doc, day)] for day in range(1, days_in_month + 1)) <= max_shifts_per_doc)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    results = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        st.success(f"排班成功！ (Status: {solver.StatusName(status)})")
        
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
        st.error("排班失敗，請檢查人力或預假衝突。")
        return None, None

st.markdown("---")
col1, col2 = st.columns([1, 4])
with col1:
    run_btn = st.button("開始排班", type="primary", use_container_width=True)

if run_btn:
    if not doctors:
        st.warning("請先輸入醫師名單")
    else:
        with st.spinner("運算中..."):
            df_schedule, stats = solve_schedule(doctors, days_in_month, leave_requests)
        
        if df_schedule is not None:
            st.subheader("班數統計")
            st.bar_chart(pd.Series(stats))
            
            st.subheader(f"{year}年{month}月 值班表")
            st.dataframe(df_schedule, use_container_width=True)
            
            csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "下載 CSV",
                csv,
                f"schedule_{year}_{month}.csv",
                "text/csv",
                key='download-csv'
            )
