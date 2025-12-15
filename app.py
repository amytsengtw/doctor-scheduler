import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="住院醫師排班系統", layout="wide")

st.title("🏥 台灣住院醫師排班系統")
st.caption("v1.6 更新版：更新預設醫師名單 | 過勞保護 + 公平分配")

# --- 2. 側邊欄設定 ---
st.sidebar.header("設定參數")

year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, value=2025)
month = st.sidebar.number_input("月份", min_value=1, max_value=12, value=12)

days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.subheader("醫師名單")
# === 這裡更新了名字 ===
default_doctors = "洋洋(R3), 蹦蹦(R2), 小白(R1), 跑跑(R1), 跳跳(NP)"
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

# --- 3. 輔助函式：產生 HTML 日曆 ---
def get_calendar_html(year, month, schedule_map):
    cal = calendar.monthcalendar(year, month)
    
    html_content = """
    <style>
        .calendar-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        .calendar-table th { background-color: #f0f2f6; padding: 8px; border: 1px solid #ddd; text-align: center; color: #333; }
        .calendar-table td { height: 100px; vertical-align: top; padding: 5px; border: 1px solid #ddd; width: 14.28%; background-color: white; }
        .day-number { font-size: 12px; color: #666; margin-bottom: 5px; text-align: right; }
        .doc-badge { background-color: #e8f0fe; color: #1557b0; padding: 4px; border-radius: 4px; font-size: 14px; font-weight: bold; text-align: center; display: block; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .weekend-td { background-color: #fafafa !important; }
        .empty-td { background-color: #f9f9f9; }
    </style>
    <table class="calendar-table">
        <thead>
            <tr>
                <th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color:red">Sat</th><th style="color:red">Sun</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for week in cal:
        html_content += "<tr>"
        for i, day in enumerate(week):
            is_weekend = i >= 5
            td_class = "weekend-td" if is_weekend else ""
            
            if day == 0:
                html_content += f'<td class="empty-td"></td>'
            else:
                doc = schedule_map.get(day, "")
                html_content += f'<td class="{td_class}"><div class="day-number">{day}</div>'
                if doc:
                    html_content += f'<div class="doc-badge">{doc}</div>'
                html_content += '</td>'
        html_content += "</tr>"
    
    html_content += "</tbody></table>"
    return html_content

# --- 4. 核心函式：排班演算法 ---
def solve_schedule(doctors, days_in_month, leave_requests):
    model = cp_model.CpModel()
    shifts = {}

    # 變數定義
    for doc in doctors:
        for day in range(1, days_in_month + 1):
            shifts[(doc, day)] = model.NewBoolVar(f'shift_{doc}_{day}')

    # 硬限制：每天 1 人
    for day in range(1, days_in_month + 1):
        model.Add(sum(shifts[(doc, day)] for doc in doctors) == 1)

    # 硬限制：不連續值班
    for doc in doctors:
        for day in range(1, days_in_month):
            model.Add(shifts[(doc, day)] + shifts[(doc, day + 1)] <= 1)

    # 預假限制
    for doc, days_off in leave_requests.items():
        for day in days_off:
            model.Add(shifts[(doc, day)] == 0)

    # 過勞保護：7天內最多3班
    max_shifts_per_week = 3
    for doc in doctors:
        if days_in_month >= 7:
            for day in range(1, days_in_month - 5): 
                week_window = [shifts[(doc, d)] for d in range(day, day + 7)]
                model.Add(sum(week_window) <= max_shifts_per_week)

    # 假日公平分配
    weekend_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() >= 5]
    if weekend_days:
        max_weekend_shifts = (len(weekend_days) // len(doctors)) + 1
        for doc in doctors:
            model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= max_weekend_shifts)

    # 總班數公平分配
    max_total_shifts = (days_in_month // len(doctors)) + 1
    for doc in doctors:
        model.Add(sum(shifts[(doc, day)] for day in range(1, days_in_month + 1)) <= max_total_shifts)

    # 求解
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    results = []
    schedule_map = {}
    doctor_stats = {doc: {'Total': 0, 'Weekend': 0} for doc in doctors}

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        st.success(f"排班成功！ (Status: {solver.StatusName(status)})")
        
        for day in range(1, days_in_month + 1):
            for doc in doctors:
                if solver.Value(shifts[(doc, day)]) == 1:
                    weekday_int = date(year, month, day).weekday()
                    weekday_str = date(year, month, day).strftime("%a")
                    is_weekend = weekday_int >= 5
                    
                    results.append({
                        "日期": f"{month}/{day}",
                        "星期": weekday_str,
                        "值班醫師": doc,
                        "類型": "週末班" if is_weekend else "平日班"
                    })
                    
                    schedule_map[day] = doc
                    doctor_stats[doc]['Total'] += 1
                    if is_weekend:
                        doctor_stats[doc]['Weekend'] += 1
        
        return pd.DataFrame(results), doctor_stats, schedule_map
    else:
        st.error("排班失敗！限制太嚴格或人力不足。")
        st.info("建議：減少預假天數，或增加人力。")
        return None, None, None

# --- 5. 主程式執行區 ---
st.markdown("---")
st.header("執行排班")

col_btn, col_space = st.columns([1, 4])
with col_btn:
    run_btn = st.button("🚀 開始排班", type="primary", use_container_width=True)

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
                st.subheader("📊 公平性統計")
                stats_df = pd.DataFrame.from_dict(stats, orient='index')
                st.dataframe(stats_df, use_container_width=True)
            
            csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下載 CSV",
                csv,
                f"schedule_{year}_{month}.csv",
                "text/csv",
                key='download-csv'
            )
