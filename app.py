import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="分級排班系統", layout="wide")

st.title("🏥 台灣醫護分級排班系統")
st.caption("v2.2 智慧救援版：三段式排班邏輯 (完美 -> 放寬工時 -> 放寬預排)")

# --- 2. 側邊欄設定 ---
st.sidebar.header("設定參數")

year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, value=2025)
month = st.sidebar.number_input("月份", min_value=1, max_value=12, value=12)

days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.subheader("1. 人員名單")
default_doctors = "洋洋(R3), 蹦蹦(R2), 小白(Int), 跑跑(Int), 跳跳(NP)"
doc_input = st.sidebar.text_area("所有人員 (用逗號分隔)", default_doctors)
all_staff = [x.strip() for x in doc_input.split(",") if x.strip()]

# 區分身份
st.sidebar.subheader("2. 身份設定")
interns = st.sidebar.multiselect(
    "誰是實習醫師 (Intern)?",
    options=all_staff,
    help="實習醫師保護：單週限2班、月限6平日2假日"
)
residents = [d for d in all_staff if d not in interns]

st.sidebar.markdown("---")
st.sidebar.header("3. 排班許願池")

leave_requests = {}
duty_requests = {}

if all_staff:
    with st.sidebar.expander("🚫 預假 (不想值班)", expanded=True):
        st.caption("除非沒人可值，否則系統會避開")
        for doc in all_staff:
            leaves = st.multiselect(f"{doc} 預假", options=dates, key=f"leave_{doc}")
            leave_requests[doc] = leaves

    with st.sidebar.expander("✅ 指定值班 (預排)", expanded=False):
        st.caption("優先滿足。若發生衝突，第三階段排班會自動取捨")
        for doc in all_staff:
            duties = st.multiselect(f"{doc} 指定值班", options=dates, key=f"duty_{doc}")
            duty_requests[doc] = duties
else:
    st.sidebar.warning("請先輸入人員名單")

# --- 3. 輔助函式：產生 HTML 日曆 ---
def get_calendar_html(year, month, schedule_map, broken_duties=None):
    if broken_duties is None:
        broken_duties = []
        
    cal = calendar.monthcalendar(year, month)
    html_content = """
    <style>
        .calendar-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        .calendar-table th { background-color: #f0f2f6; padding: 8px; border: 1px solid #ddd; text-align: center; color: #333; }
        .calendar-table td { height: 100px; vertical-align: top; padding: 5px; border: 1px solid #ddd; width: 14.28%; background-color: white; }
        .day-number { font-size: 12px; color: #666; margin-bottom: 5px; text-align: right; }
        .doc-badge { background-color: #e8f0fe; color: #1557b0; padding: 4px; border-radius: 4px; font-size: 14px; font-weight: bold; text-align: center; display: block; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .doc-badge.intern { background-color: #fce8e6; color: #c5221f; }
        .doc-badge.broken { border: 2px dashed orange; } /* 未滿足預排的標示 */
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
                    badge_class = "doc-badge intern" if doc in interns else "doc-badge"
                    html_content += f'<div class="{badge_class}">{doc}</div>'
                html_content += '</td>'
        html_content += "</tr>"
    html_content += "</tbody></table>"
    return html_content

# --- 4. 核心函式：排班演算法 ---
def solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, 
                strict_resident_limit=True, enforce_duty_requests=True):
    model = cp_model.CpModel()
    shifts = {}

    # 定義變數
    for doc in all_staff:
        for day in range(1, days_in_month + 1):
            shifts[(doc, day)] = model.NewBoolVar(f'shift_{doc}_{day}')

    # 1. 每天必須有 1 人值班
    for day in range(1, days_in_month + 1):
        model.Add(sum(shifts[(doc, day)] for doc in all_staff) == 1)

    # 2. 所有人：不能連續值班
    for doc in all_staff:
        for day in range(1, days_in_month):
            model.Add(shifts[(doc, day)] + shifts[(doc, day + 1)] <= 1)

    # 3. 預假 (Leave) - 視為硬限制 (除非連這都拿掉，但通常不想值班就是不想)
    for doc, days_off in leave_requests.items():
        for day in days_off:
            model.Add(shifts[(doc, day)] == 0)

    # 4. 指定值班 (Duty) - 根據參數決定是否為硬限制
    if enforce_duty_requests:
        # 硬限制：一定要排
        for doc, days_on in duty_requests.items():
            for day in days_on:
                model.Add(shifts[(doc, day)] == 1)
    else:
        # 軟限制：盡量排 (加入目標函式 Maximize)
        # 我們希望滿足越多越好
        requested_shifts = []
        for doc, days_on in duty_requests.items():
            for day in days_on:
                requested_shifts.append(shifts[(doc, day)])
        if requested_shifts:
            model.Maximize(sum(requested_shifts))

    # 5. 實習醫師 (Intern) 限制
    if interns:
        weekend_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() >= 5]
        weekday_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() < 5]
        month_weeks = calendar.monthcalendar(year, month)

        for doc in interns:
            for week in month_weeks:
                valid_days_in_week = [d for d in week if d != 0]
                if valid_days_in_week:
                     model.Add(sum(shifts[(doc, d)] for d in valid_days_in_week) <= 2)
            model.Add(sum(shifts[(doc, d)] for d in weekday_days) <= 6)
            model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= 2)

    # 6. 住院醫師 (Resident) 限制
    if residents:
        weekend_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() >= 5]
        if weekend_days:
            max_weekend = (len(weekend_days) // len(residents + interns)) + 2 
            for doc in residents:
                model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= max_weekend)

        if strict_resident_limit:
            for doc in residents:
                model.Add(sum(shifts[(doc, d)] for d in range(1, days_in_month + 1)) <= 8)

    # 求解
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts

def solve_schedule_logic(all_staff, interns, residents, days_in_month, leave_requests, duty_requests):
    warning_level = 0
    warning_msg = None
    
    # [Level 1] 完美模式：限 8 班 + 強制預排
    solver, status, shifts = solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, 
                                         strict_resident_limit=True, enforce_duty_requests=True)
    
    # [Level 2] 救援模式 A：放寬 8 班限制 + 強制預排
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        warning_level = 1
        warning_msg = "⚠️ 警告：人力不足，已放寬住院醫師「每月 8 班」限制。"
        solver, status, shifts = solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, 
                                             strict_resident_limit=False, enforce_duty_requests=True)

    # [Level 3] 救援模式 B：放寬 8 班限制 + 放寬預排 (盡力而為)
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        warning_level = 2
        warning_msg = "⛔️ 嚴重警告：無法滿足「指定值班」需求！系統已自動犧牲部分預排以確保產出班表。"
        solver, status, shifts = solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, 
                                             strict_resident_limit=False, enforce_duty_requests=False)

    results = []
    schedule_map = {}
    doctor_stats = {doc: {'Total': 0, 'Weekend': 0, 'Weekday': 0} for doc in all_staff}
    unmet_duties = []

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for day in range(1, days_in_month + 1):
            for doc in all_staff:
                is_shift = solver.Value(shifts[(doc, day)]) == 1
                
                # 檢查 Level 3 是否有犧牲掉預排
                if warning_level == 2:
                    # 如果這天是 doc 指定的，但他沒排到
                    if doc in duty_requests and day in duty_requests[doc] and not is_shift:
                        unmet_duties.append(f"{month}/{day} {doc}")

                if is_shift:
                    weekday_int = date(year, month, day).weekday()
                    weekday_str = date(year, month, day).strftime("%a")
                    is_weekend = weekday_int >= 5
                    role = "Intern" if doc in interns else "Resident"

                    results.append({
                        "日期": f"{month}/{day}",
                        "星期": weekday_str,
                        "值班醫師": doc,
                        "身份": role,
                        "類型": "週末班" if is_weekend else "平日班"
                    })
                    schedule_map[day] = doc
                    doctor_stats[doc]['Total'] += 1
                    if is_weekend:
                        doctor_stats[doc]['Weekend'] += 1
                    else:
                        doctor_stats[doc]['Weekday'] += 1
        
        return pd.DataFrame(results), doctor_stats, schedule_map, warning_msg, unmet_duties
    else:
        return None, None, None, "❌ 徹底失敗：即使放寬所有條件仍無解 (可能是預假太多導致某天沒人)", []

# --- 5. 主程式執行區 ---
st.markdown("---")
st.header("執行排班")

col_btn, col_space = st.columns([1, 4])
with col_btn:
    run_btn = st.button("🚀 開始排班", type="primary", use_container_width=True)

if run_btn:
    if not all_staff:
        st.warning("請先輸入醫師名單")
    else:
        with st.spinner("智慧運算中 (嘗試三段式救援邏輯)..."):
            df_schedule, stats, schedule_map, warning, unmet = solve_schedule_logic(
                all_staff, interns, residents, days_in_month, leave_requests, duty_requests
            )
        
        if df_schedule is not None:
            if warning:
                if "嚴重" in warning:
                    st.error(warning)
                else:
                    st.warning(warning)
            else:
                st.success("✅ 完美排班：符合所有限制與需求！")

            if unmet:
                st.write("### 📉 遺憾清單 (無法滿足的預排)")
                st.write(", ".join(unmet))

            st.subheader(f"📅 {year}年{month}月 排班月曆")
            st.caption("🟥 紅色: Intern | ⬜ 一般: Resident")
            cal_html = get_calendar_html(year, month, schedule_map)
            st.markdown(cal_html, unsafe_allow_html=True)

            st.markdown("---")
            
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader("詳細清單")
                st.dataframe(df_schedule, use_container_width=True)
            with col_b:
                st.subheader("📊 班數統計")
                stats_df = pd.DataFrame.from_dict(stats, orient='index')
                st.dataframe(stats_df, use_container_width=True)
                if interns:
                    st.info("ℹ️ Intern 限制：\n- 單週 (Mon-Sun) <= 2\n- 月平日 <= 6\n- 月假日 <= 2")
            
            csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下載 CSV",
                csv,
                f"schedule_{year}_{month}.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.error(warning)
