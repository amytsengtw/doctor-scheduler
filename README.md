# Cardinal Tien Hospital Dual-Track Rostering System (v6.0)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)](https://streamlit.io/)
[![Organization](https://img.shields.io/badge/Organization-Cardinal%20Tien%20Hospital-purple)](https://www.cth.org.tw/)

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

### 🚀 Key Features (v6.0 Magic Link)

1.  **Magic Link Distribution**: 
    *   Generates a unique, personalized URL for each doctor.
    *   When the doctor opens the link, the app renders a **Personal View** with only their schedule and a "Download to Calendar" button.
    *   No database required; data is encoded in the URL.

2.  **Strict Shift Limits (v4.8 Logic)**
    *   PGY/Interns strictly limited to 6 Weekdays / 2 Weekends.
    *   Residents (R) automatically support if limits are reached.

---

## 中文說明

本版本 (v6.0) 為 **耕莘醫院** 帶來了革命性的 **「魔術連結分發」** 功能。

### ✨ v6.0 核心功能：魔術連結 (Magic Link)

總醫師不再需要傳送檔案，只需傳送連結！

1.  **一鍵生成**：排班完成後，系統會為每位醫師生成一個專屬網址。
2.  **複製分享**：總醫師點擊「複製」，將連結貼到 Line 給王醫師。
3.  **個人視角**：王醫師點開連結，只會看到 **他自己的班表**，並且有一個巨大的 **「加入行事曆」** 按鈕。
4.  **隱私安全**：網址內含加密編碼的班表資料，無需登入，即開即用。

*(注意：請在側邊欄確認您的 App 網址是否正確，例如 `https://doctor-scheduler.streamlit.app`)*

### 🏗 核心邏輯 (v4.8)

*   **天條**：PGY/Intern 平日限 6 班，假日限 2 班。
*   **救援**：若滿班還有空缺，住院醫師 (R) 必須支援 (扣5萬分)。
*   **點數**：平日=1，假日=2。點數可超過 10 (軟限制)。

### 🚀 使用教學

1.  **排班**：輸入資料並點擊運算。
2.  **分發**：
    *   滑到下方的 **「🔗 班表分發連結」** 區塊。
    *   展開 **「張醫師的專屬連結」**。
    *   複製連結，傳送給張醫師。
3.  **接收**：
    *   張醫師點開連結 -> 點擊 **「加入手機行事曆」** -> 完成！

### 📜 授權
MIT License
