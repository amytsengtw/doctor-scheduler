import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import calendar
from datetime import date

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="住院醫師排班系統", layout="wide")

st.title("🏥 台灣住院醫師排班系統")
st.caption("v1.4 修復版：確保按鈕顯示正常 | 過勞保護 + 公平分配")

# --- 2. 側邊欄設定 ---
st.sidebar.header("設定參數")

year = st.sidebar.number_input("年份", min_value=2024, max_value=2030, value=2025)
month = st.sidebar.number_input("月份", min_value=1, max_value=12, value=12)

days_in_month = calendar.monthrange(year, month)[1]
dates = [d for d in range(1, days_in_month + 1)]

st.sidebar.subheader("醫師名單")
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
                <th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color:red">Sat</
