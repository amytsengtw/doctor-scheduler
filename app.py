import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="分級排班系統", layout="wide")

st.title("🏥 台灣醫護分級排班系統")
st.caption("v2.0 分級版：實習醫師保護機制 + 住院醫師彈性上限 (Max 8)")

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
    help="實習醫師將受到嚴格保護：7天限2班、月限6平日2假日"
)
# 剩下的是住院醫師 (Residents)
residents = [d for d in all_staff if d not in interns]

st.sidebar.markdown("---")
st.sidebar.header("3. 排班許願池")

leave_requests = {}
duty_requests = {}

if all_staff:
    with st.sidebar.expander("🚫 預假 (不想值班)", expanded=True):
        for doc in all_staff:
            leaves = st.multiselect(f"{doc} 預假", options=dates, key=f"leave_{doc}")
            leave_requests[doc] = leaves

    with st.sidebar.expander("✅ 指定值班 (預排)", expanded=False):
        for doc in all_staff:
            duties = st.multiselect(f"{doc} 指定值班", options=dates, key=f"duty_{doc}")
            duty_requests[doc] = duties
else:
    st.sidebar.warning("請先輸入人員名單")

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
        .doc-badge.intern { background-color: #fce8e6; color: #c5221f; } /* 實習醫師紅色標示 */
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
                    # 如果是 Intern，給不同的 CSS class
                    badge_class = "doc-badge intern" if doc in interns else "doc-badge"
                    html_content += f'<div class="{badge_class}">{doc}</div>'
                html_content += '</td>'
        html_content += "</tr>"
    html_content += "</tbody></table>"
    return html_content

# --- 4. 核心函式：排班演算法 ---
def solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, strict_resident_limit=True):
    model = cp_model.CpModel()
    shifts = {}

    # 定義變數
    for doc in all_staff:
        for day in range(1, days_in_month + 1):
            shifts[(doc, day)] = model.NewBoolVar(f'shift_{doc}_{day}')

    # 1. 每天必須有 1 人值班
    for day in range(1, days_in_month + 1):
        model.Add(sum(shifts[(doc, day)] for doc in all_staff) == 1)

    # 2. 所有人：不能連續值班 (No back-to-back)
    for doc in all_staff:
        for day in range(1, days_in_month):
            model.Add(shifts[(doc, day)] + shifts[(doc, day + 1)] <= 1)

    # 3. 處理預假與指定值班
    for doc, days_off in leave_requests.items():
        for day in days_off:
            model.Add(shifts[(doc, day)] == 0)
    for doc, days_on in duty_requests.items():
        for day in days_on:
            model.Add(shifts[(doc, day)] == 1)

    # ==========================================
    # 4. 實習醫師 (Intern) 專屬限制 - 嚴格保護
    # ==========================================
    if interns:
        weekend_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() >= 5]
        weekday_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() < 5]

        for doc in interns:
            # A. 7天內最多2班
            if days_in_month >= 7:
                for day in range(1, days_in_month - 5):
                    week_window = [shifts[(doc, d)] for d in range(day, day + 7)]
                    model.Add(sum(week_window) <= 2)
            
            # B. 每月平日最多 6 班
            model.Add(sum(shifts[(doc, d)] for d in weekday_days) <= 6)

            # C. 每月假日最多 2 班
            model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= 2)

    # ==========================================
    # 5. 住院醫師 (Resident) 限制
    # ==========================================
    if residents:
        # 為了公平，還是要有個基本的假日平均分配，但放寬一點
        weekend_days = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() >= 5]
        if weekend_days:
             # 平均數向上取整 + 1 (寬鬆一點)
            max_weekend = (len(weekend_days) // len(residents + interns)) + 2 
            for doc in residents:
                model.Add(sum(shifts[(doc, d)] for d in weekend_days) <= max_weekend)

        # 關鍵：是否開啟「嚴格 8 班限制」
        if strict_resident_limit:
            for doc in residents:
                model.Add(sum(shifts[(doc, d)] for d in range(1, days_in_month + 1)) <= 8)

    # 求解
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return solver, status, shifts

def solve_schedule_logic(all_staff, interns, residents, days_in_month, leave_requests, duty_requests):
    # 第一階段：嘗試嚴格限制 (住院醫師 <= 8)
    solver, status, shifts = solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, strict_resident_limit=True)
    
    warning_msg = None

    # 如果失敗，進入第二階段：放寬住院醫師限制
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        warning_msg = "⚠️ 注意：人力吃緊，無法滿足「每人 8 班」限制。系統已自動放寬上限以產出班表。"
        solver, status, shifts = solve_model(all_staff, interns, residents, days_in_month, leave_requests, duty_requests, strict_resident_limit=False)

    results = []
    schedule_map = {}
    doctor_stats = {doc: {'Total': 0, 'Weekend': 0, 'Weekday': 0} for doc in all_staff}

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for day in range(1, days_in_month + 1):
            for doc in all_staff:
                if solver.Value(shifts[(doc, day)]) == 1:
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
        
        return pd.DataFrame(results), doctor_stats, schedule_map, warning_msg
    else:
        return None, None, None, "❌ 排班失敗：即使放寬住院醫師限制，仍無法滿足實習醫師的保護條款或指定值班衝突。"

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
        with st.spinner("運算中 (優先嘗試 8 班限制)..."):
            df_schedule, stats, schedule_map, warning = solve_schedule_logic(
                all_staff, interns, residents, days_in_month, leave_requests, duty_requests
            )
        
        if df_schedule is not None:
            # 顯示警告訊息 (如果有)
            if warning:
                st.warning(warning)
            else:
                st.success("✅ 完美排班：所有住院醫師皆在 8 班以內！")

            # 顯示日曆
            st.subheader(f"📅 {year}年{month}月 排班月曆")
            st.caption("🟥 紅色底色代表實習醫師 (Intern)")
            cal_html = get_calendar_html(year, month, schedule_map)
            st.markdown(cal_html, unsafe_allow_html=True)

            st.markdown("---")
            
            # 顯示表格與統計
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader("詳細清單")
                st.dataframe(df_schedule, use_container_width=True)
            with col_b:
                st.subheader("📊 班數統計")
                stats_df = pd.DataFrame.from_dict(stats, orient='index')
                st.dataframe(stats_df, use_container_width=True)
                st.caption("Intern 限制：平日<=6, 假日<=2")
            
            # 下載按鈕
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
