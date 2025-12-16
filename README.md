# Cardinal Tien Hospital Dual-Track Rostering System (v5.0)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)](https://streamlit.io/)
[![Organization](https://img.shields.io/badge/Organization-Cardinal%20Tien%20Hospital-purple)](https://www.cth.org.tw/)

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

### 🚀 Key Features (v5.0 Flagship)

1.  **ICS Calendar Export**: 
    *   One-click download of `.ics` files.
    *   Doctors can import their shifts directly into Google Calendar or Apple Calendar.

2.  **Taiwan Holiday Support**:
    *   Manual selection of "National Holidays" (Red letter days).
    *   System treats these days as **Weekend Shifts** (2 Points) and applies strict holiday limits.

3.  **Visual Analytics**:
    *   Interactive bar charts to visualize workload distribution (Points/Shifts) for fairness verification.

4.  **Strict Shift Limits & Rescue**:
    *   PGY/Int strictly limited to 6 Weekday / 2 Weekend shifts.
    *   Residents (R) automatically support if limits are reached.

---

## 中文說明

這是一套專為 **耕莘醫院** 設計的旗艦級排班系統，v5.0 版本加入了貼心的使用者體驗功能。

### ✨ v5.0 旗艦功能

1.  **📅 手機行事曆匯入 (.ics)**
    *   **痛點解決**：不用再看著 Excel 一筆一筆手動輸入手機。
    *   **功能**：點擊下載 `.ics` 檔，手機開啟即可將所有值班匯入行事曆。

2.  **🏮 國定假日支援**
    *   **彈性設定**：在側邊欄可勾選「平日的紅字」（如國慶日、中秋節）。
    *   **邏輯變更**：被勾選的日子會自動算成 **假日班 (2點)**，並計入假日班數限額。

3.  **📊 公平性視覺化**
    *   **長條圖**：直接秀出每位醫師的總點數高低。
    *   **用途**：開會時投影出來，證明排班的公平性。

### 🏗 核心邏輯回顧 (v4.8)

*   **天條**：PGY/Intern 平日限 6 班，假日限 2 班。絕對不可違反。
*   **救援**：若滿班還有空缺，住院醫師 (R) 必須支援。
*   **點數**：平日=1，假日=2。點數可超過 10 (軟限制)。

### 🚀 使用教學

1.  **輸入**：人員名單。
2.  **設定假日**：在側邊欄勾選本月的國定假日。
3.  **限制**：設定請假 (Hard) 與意願 (Soft)。
4.  **運算 & 下載**：
    *   檢查圖表確認公平性。
    *   下載 **Excel 格式** 用於公告。
    *   下載 **ICS 格式** 傳給醫師。

### 📜 授權
MIT License
