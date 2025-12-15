import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

st.set_page_config(page_title="住院醫師排班系統", layout="wide")

st.title("🏥 台灣住院醫師排班系統")
st.caption("v1.3 更新：加入「7天限3班」過勞保護機制 ＆ 「假日班公平」分配")

st.sidebar.header("設定")

year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, value=2025)
month = st.sidebar.number_input("月份", min_value=1, max_value=12, value=12)

days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.subheader("醫師名單")
default_doctors = "洋洋(R3), 蹦蹦(R2), 跳跳(R1), 小白(R1), 跑跑(NP)"
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

# --- HTML 日曆生成器 ---
def get_calendar_html(year, month, schedule_map):
    cal = calendar.monthcalendar(year, month)
    html = """
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

# --- 核心排班邏輯 ---
def solve_schedule(doctors, days_in_month, leave_requests):
    model = cp_model.CpModel()
    shifts = {}

    # 1. 定義變數
    for doc in doctors:
        for day in range(1, days_in_month + 1):
            shifts[(doc, day)] = model.NewBoolVar(f'shift_{doc}_{day}')

    # 2. 基本限制：每天 1 人
    for day in range(1, days_in_month + 1):
        model.Add(sum(shifts[(doc, day)] for doc in doctors) == 1)

    # 3. 基本限制：不能連續值班
    for doc in doctors:
        for day in range(1, days_in_month):
            model.Add(shifts[(doc, day)] + shifts[(doc, day + 1)] <= 1)

    # 4. 預假限制
    for doc, days_off in leave_requests.items():
        for day in days_off:
            model.Add(shifts[(doc, day)] == 0)

    # ==========================
    # 新增限制區域
    # ==========================

    # 5. 過勞保護：任意連續 7 天內，最多值 3 班
    # 這是為了防止類似 Mon, Wed, Fri, Sun 這種 Q2 雖然合法但會過勞的排法
    max_shifts_per_week = 3
    for doc in doctors:
        # 視窗滑動範圍：從第1天 到 月底-6天
        for day in range(1, days_in_month - 5): 
            # 建立 7 天的視窗
            week_window = [shifts[(doc, d)] for d in range(day, day + 7)]
            model.Add(sum(week_window) <= max_shifts_per_week)

    # 6. 假日公平性：每個人值的「週末班」數量要受到限制
    # 找出所有週六(5)和週日(6)
    weekend_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() >= 5]
    
    if weekend_days:
        # 計算平均假日班數上限 (無條件進位)
        # 例如 9 個假日，5 個人 -> 每人上限 2 班
        max_weekend_shifts = (len(weekend_days) // len(doctors)) + 1
        
        for doc in doctors:
            model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= max_weekend_shifts)

    # 7. 總班數公平性：每個人總班數上限
    max_total_shifts = (days_in_month // len(doctors)) + 1
    for doc in doctors:
        model.Add(sum(shifts[(doc, day)] for day in range(1, days_in_month + 1)) <= max_total_shifts)

    # ==========================
    # 求解
    # ==========================
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
                    is_weekend = weekday_int >= 5  # 5=Sat, 6=Sun
                    
                    results.append({
                        "日期": f"{month}/{day}",
                        "星期": weekday_str,
                        "值班醫師": doc,
                        "類型": "週末班" if is_weekend else "平日班"
                    })
                    
                    # 統計數據
                    schedule_map[day] = doc
                    doctor_stats[doc]['Total'] += 1
                    if is_weekend:
                        doctor_stats[doc]['Weekend']
