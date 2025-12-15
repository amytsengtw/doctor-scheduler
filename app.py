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
default_doctors = "繃繃(R3), 跳跳(R2), 小白(R1), 洋洋(R1), 跑跑(NP)"
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

def get_calendar_html(year, month, schedule_map):
    cal = calendar.monthcalendar(year, month)
    html = """
    <style>
        .calendar-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        .calendar-table th { background-color: #f0f2f6; padding: 8px; border: 1px solid #ddd; text-align: center; color: #333; }
        .calendar-table td { height: 100px; vertical-align: top; padding: 5px; border: 1px solid #ddd; width: 14.28%; background-color: white; }
        .day-number { font-size: 12px; color: #666; margin-bottom: 5px; text-align: right; }
        .doc-badge { background-color: #e8f0fe; color: #1557b0; padding: 4px; border-radius: 4px; font-size: 14px; font-weight: bold; text-align: center; display: block; }
        .weekend-td { background-color: #fafafa !important; }
        .empty-td { background-color: #f9f9f9; }
    </style>
    <table class="calendar-table">
        <thead>
            <tr>
                <th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th><th>Sun</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for week in cal:
        html += "<tr>"
        for i, day in enumerate(week):
            is_weekend = i >= 5
            td_class = "weekend-td" if is_weekend else ""
            
            if day == 0:
                html += f'<td class="empty-td"></td>'
            else:
                doc = schedule_map.get(day, "")
                html += f'<td class="{td_class}"><div class="day-number">{day}</div>'
                if doc:
                    html += f'<div class="doc-badge">{doc}</div>'
                html += '</td>'
        html += "</tr>"
    
    html += "</tbody></table>"
    return html

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
    schedule_map = {}

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
                    schedule_map[day] = doc
        
        return pd.DataFrame(results), doctor_shift_counts, schedule_map
    else:
        st.error("排班失敗，請檢查人力或預假衝突。")
        return None, None, None

st.markdown("---")
col1, col2 = st.columns([1, 4])
with col1:
    run_btn = st.button("開始排班", type="primary", use_container_width=True)

if run_btn:
    if not doctors:
        st.warning("請先輸入醫師名單")
    else:
        with st.spinner("運算中..."):
            df_schedule, stats, schedule_map = solve_schedule(doctors, days_in_month, leave_requests)
        
        if df_schedule is not None:
            st.subheader(f"📅 {year}年{month}月 排班月曆")
            cal_html = get_calendar_html(year, month, schedule_map)
            st.markdown(cal_html, unsafe_allow_html=True)

            st.markdown("---")
            
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader("詳細清單")
                st.dataframe(df_schedule, use_container_width=True)
            with col_b:
                st.subheader("班數統計")
                st.bar_chart(pd.Series(stats))
            
            csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "下載 CSV",
                csv,
                f"schedule_{year}_{month}.csv",
                "text/csv",
                key='download-csv'
            )
