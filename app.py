import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date, timedelta
import json
import hashlib
import base64
import urllib.parse
import zipfile
import io

# ==========================================
# 0. 基礎設定與共用函式 (定義在最上方)
# ==========================================
st.set_page_config(page_title="耕莘醫院雙軌排班系統 (v6.2)", layout="wide")

def get_doctor_color(name):
    palette = ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF", "#E6B3FF", "#FFB3E6", "#C9C9FF", "#FFD1DC", "#E0F7FA", "#F0F4C3", "#D7CCC8", "#F8BBD0", "#C5CAE9", "#B2DFDB"]
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(palette)
    return palette[idx]

def generate_ics_content(schedule_data, year, month):
    """用於生成 .ics 檔案內容"""
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//CTH//Roster//TW\nCALSCALE:GREGORIAN\n"
    for item in schedule_data:
        day = item['d']
        shift_type = item['t']
        start_date = date(year, month, day)
        end_date = start_date + timedelta(days=1)
        dtstart = start_date.strftime("%Y%m%d")
        dtend = end_date.strftime("%Y%m%d")
        ics += f"BEGIN:VEVENT\nSUMMARY:值班: {shift_type}\nDTSTART;VALUE=DATE:{dtstart}\nDTEND;VALUE=DATE:{dtend}\nDESCRIPTION:耕莘醫院 {shift_type}值班\nEND:VEVENT\n"
    ics += "END:VCALENDAR"
    return ics

# ==========================================
# 1. 路由判斷 (醫師檢視 vs 總醫師管理)
# ==========================================
query_params = st.query_params
if "payload" in query_params:
    # --- [模式 A] 醫師個人檢視模式 ---
    try:
        payload = query_params["payload"]
        json_str = base64.b64decode(payload).decode('utf-8')
        data = json.loads(json_str)
        
        doc_name = data['n']
        year = data['y']
        month = data['m']
        shifts = data['s'] # list of {'d': day, 't': type}

        st.title(f"👋 您好，{doc_name}")
        st.info(f"這是您 {year} 年 {month} 月的專屬值班表")
        
        df_show = pd.DataFrame(shifts)
        if not df_show.empty:
            df_show['日期'] = df_show['d'].apply(lambda x: f"{month}/{x}")
            df_show['班別'] = df_show['t']
            st.table(df_show[['日期', '班別']])
            
            ics_content = generate_ics_content(shifts, year, month)
            st.download_button(
                label="📅 加入手機行事曆 (下載 .ics)",
                data=ics_content,
                file_name=f"{doc_name}_{year}_{month}_roster.ics",
                mime="text/calendar",
                type="primary",
                use_container_width=True
            )
            st.success("💡 說明：下載後請直接開啟檔案，即可將班表匯入手機行事曆。")
        else:
            st.success("🎉 這個月沒有值班！")

    except Exception as e:
        st.error("連結無效或已過期。")
    
    st.stop() # 停止執行後續程式碼，只顯示個人頁面

# ==========================================
# [模式 B] 總醫師管理模式 (Admin View)
# ==========================================

st.title("🏥 耕莘醫院婦產科雙軌排班系統 (v6.2)")
st.caption("修復版：預設網址更新 | 功能：魔術連結分發 + 點數制 + R救援")

# --- Session State 初始化 ---
default_state = {
    "year": 2025,
    "month": 12,
    "vs_list": "張醫師(VS), 王醫師(VS)", 
    "r_list": "洋洋(R3), 蹦蹦(R2)",
    "pgy_list": "小明(PGY), 小華(PGY), 小強(PGY)",
    "int_list": "菜鳥A(Int), 菜鳥B(Int)",
    "vs_leaves": {}, "r_leaves": {}, "pgy_leaves": {}, "int_leaves": {},
    "vs_wishes": {},  "vs_nogo": {},
    "r_wishes": {},   "r_nogo": {},
    "pgy_wishes": {}, "pgy_nogo": {},
    "int_wishes": {}, "int_nogo": {},
    "holidays": []
}

for key, val in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 側邊欄設定 ---
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

st.sidebar.markdown("---")
st.sidebar.header("🏮 國定假日")
holidays = st.sidebar.multiselect(
    "請勾選平日放假的日子",
    options=dates,
    default=st.session_state.get("holidays", []),
    key="holidays_widget"
)
st.session_state["holidays"] = holidays

st.sidebar.markdown("---")
st.sidebar.header("🔢 運算設定")
num_solutions = st.sidebar.slider("產生方案數量", min_value=1, max_value=5, value=1)

# === [修改] 這裡預設您的正確網址 ===
base_app_url = st.sidebar.text_input(
    "🔗 App 網址 (用於連結)", 
    value="https://doctor-scheduler-fkbdrtumuypcmcedntjvts.streamlit.app"
)

# --- 主畫面 UI ---
st.subheader("1. 人員與限制設定")
tab1, tab2 = st.tabs(["🔴 大班 (產房)", "🔵 小班 (一般)"])
with tab1:
    c1, c2 = st.columns(2)
    vs_staff = [x.strip() for x in st.text_area("VS 主治醫師名單", key="vs_list").split(",") if x.strip()]
    r_staff = [x.strip() for x in st.text_area("R 住院醫師名單", key="r_list").split(",") if x.strip()]
with tab2:
    c3, c4 = st.columns(2)
    pgy_staff = [x.strip() for x in st.text_area("PGY 名單", key="pgy_list").split(",") if x.strip()]
    int_staff = [x.strip() for x in st.text_area("Intern 實習醫師名單", key="int_list").split(",") if x.strip()]

def update_pref(key, staff, label, help_t):
    prefs = st.session_state.get(key, {})
    new_prefs = {}
    st.markdown(f"**{label}**")
    if help_t: st.caption(help_t)
    for doc in staff:
        default = [d for d in prefs.get(doc, []) if d in dates]
        selection = st.multiselect(doc, dates, default=default, key=f"{key}_{doc}_w")
        new_prefs[doc] = selection
    st.session_state[key] = new_prefs

with st.expander("⛔️ 請假/未到職設定 (絕對排除)", expanded=True):
    col_l, col_r = st.columns(2)
    with col_l:
        update_pref("vs_leaves", vs_staff, "VS 請假", "")
        update_pref("r_leaves", r_staff, "R 請假", "")
    with col_r:
        update_pref("pgy_leaves", pgy_staff, "PGY 請假", "")
        update_pref("int_leaves", int_staff, "Int 請假", "")

st.markdown("#### 排班意願 (軟限制)")
c1, c2 = st.columns(2)
with c1:
    with st.expander("🔴 大班意願", expanded=False):
        update_pref("vs_wishes", vs_staff, "VS 指定值班", "優先")
        update_pref("vs_nogo", vs_staff, "VS 不想值", "避開")
        st.markdown("---")
        update_pref("r_nogo", r_staff, "R 不想值", "避開")
        update_pref("r_wishes", r_staff, "R 想值", "加分")
with c2:
    with st.expander("🔵 小班意願", expanded=False):
        update_pref("pgy_nogo", pgy_staff, "PGY 不想值", "避開")
        update_pref("pgy_wishes", pgy_staff, "PGY 想值", "加分")
        st.markdown("---")
        update_pref("int_nogo", int_staff, "Int 不想值", "避開")
        update_pref("int_wishes", int_staff, "Int 想值", "加分")

# --- 演算法與輔助函式定義區 ---

def is_holiday(d, custom_holidays):
    return (date(year, month, d).weekday() >= 5) or (d in custom_holidays)

def add_fairness_objective(model, shifts, staff_list, days, custom_holidays, obj_terms, weight=500):
    if not staff_list: return
    weekend_days = [d for d in days if is_holiday(d, custom_holidays)]
    weekday_days = [d for d in days if not is_holiday(d, custom_holidays)]
    avg_wd = len(weekday_days) // len(staff_list)
    avg_we = len(weekend_days) // len(staff_list)
    for doc in staff_list:
        wd_count = model.NewIntVar(0, 31, f"wd_cnt_{doc}")
        model.Add(wd_count == sum(shifts[(doc, d)] for d in weekday_days))
        dev_wd = model.NewIntVar(0, 31, f"dev_wd_{doc}")
        model.Add(dev_wd >= wd_count - avg_wd); model.Add(dev_wd >= avg_wd - wd_count)
        obj_terms.append(dev_wd * -weight)
        we_count = model.NewIntVar(0, 31, f"we_cnt_{doc}")
        model.Add(we_count == sum(shifts[(doc, d)] for d in weekend_days))
        dev_we = model.NewIntVar(0, 31, f"dev_we_{doc}")
        model.Add(dev_we >= we_count - avg_we); model.Add(dev_we >= avg_we - we_count)
        obj_terms.append(dev_we * -weight)

def add_point_system_constraint(model, shifts, staff_list, days, custom_holidays, obj_terms, sacrifices, limit=8, weight=1000):
    weekend_days = [d for d in days if is_holiday(d, custom_holidays)]
    weekday_days = [d for d in days if not is_holiday(d, custom_holidays)]
    for doc in staff_list:
        total_points = model.NewIntVar(0, 100, f"pts_{doc}")
        model.Add(total_points == sum(shifts[(doc, d)] for d in weekday_days) * 1 + sum(shifts[(doc, d)] for d in weekend_days) * 2)
        slack = model.NewIntVar(0, 50, f"slack_pts_{doc}")
        model.Add(total_points <= limit + slack)
        obj_terms.append(slack * -weight)
        sacrifices.append((slack, f"{doc} 點數超標 (>{limit}點)"))

def add_spacing_preference(model, shifts, staff_list, days, obj_terms, weight=100):
    for doc in staff_list:
        for d in range(1, len(days) - 1):
            q2_violation = model.NewBoolVar(f"q2_{doc}_{d}")
            model.Add(shifts[(doc, d)] + shifts[(doc, d+2)] <= 1 + q2_violation)
            obj_terms.append(q2_violation * -weight)

def calculate_stats(df, custom_holidays):
    if df.empty: return pd.DataFrame()
    df['Type'] = df['日期'].apply(lambda x: '假日' if is_holiday(int(x.split('/')[1]), custom_holidays) else '平日')
    stats = df.groupby('醫師')['Type'].value_counts().unstack(fill_value=0)
    if '平日' not in stats.columns: stats['平日'] = 0
    if '假日' not in stats.columns: stats['假日'] = 0
    stats['總班數'] = stats['平日'] + stats['假日']
    stats['總點數'] = stats['平日'] * 1 + stats['假日'] * 2
    return stats[['總班數', '總點數', '平日', '假日']].sort_values(by='總點數', ascending=False)

def get_html_calendar(df_big, df_small, custom_holidays):
    cal = calendar.monthcalendar(year, month)
    map_big = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_big.iterrows()}
    map_small = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_small.iterrows()}
    html = """<style>.cal-table {width:100%; border-collapse:collapse; table-layout:fixed;}.cal-table td {height:120px; border:1px solid #ddd; vertical-align:top; padding:4px; background:#fff;}.cal-table th {background:#f0f2f6; border:1px solid #ddd; padding:5px;}.day-num {font-size:12px; color:#666; text-align:right; margin-bottom:5px;}.badge {padding:4px 6px; border-radius:6px; font-size:13px; margin-bottom:4px; display:block; font-weight:bold; color: #333; text-shadow: 0 0 2px #fff; border: 1px solid rgba(0,0,0,0.1);}.weekend {background-color:#fafafa !important;}.holiday {background-color:#ffebee !important;}.shift-label {font-size: 10px; color: #666; margin-right: 3px;}</style><table class="cal-table"><thead><tr><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color:red">Sat</th><th style="color:red">Sun</th></tr></thead><tbody>"""
    for week in cal:
        html += "<tr>"
        for i, day in enumerate(week):
            cls = ""
            if day != 0:
                if is_holiday(day, custom_holidays): cls = "holiday" if day in custom_holidays else "weekend"
            if day == 0: html += f'<td class="empty"></td>'
            else:
                b_doc = map_big.get(day, ""); s_doc = map_small.get(day, "")
                html += f'<td class="{cls}"><div class="day-num">{day}</div>'
                if b_doc: html += f'<div class="badge" style="background-color:{get_doctor_color(b_doc)};"><span class="shift-label">產:</span>{b_doc}</div>'
                if s_doc: html += f'<div class="badge" style="background-color:{get_doctor_color(s_doc)};"><span class="shift-label">小:</span>{s_doc}</div>'
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
                res.append({"日期": f"{month}/{d}", "星期": w, "班別": name, "醫師": doc})
    return pd.DataFrame(res)

def generate_excel_calendar_df(df_big, df_small):
    map_big = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_big.iterrows()}
    map_small = {int(r["日期"].split("/")[1]): r["醫師"] for _, r in df_small.iterrows()}
    cal = calendar.monthcalendar(year, month)
    csv_rows = []
    headers = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
    csv_rows.append(headers)
    for week in cal:
        row_date = []; row_big = []; row_small = []
        for day in week:
            if day == 0:
