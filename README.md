# 🏥 台灣住院醫師排班系統 (Resident Scheduling System)

這是一個基於 **Python** 與 **Google OR-Tools** 開發的自動化排班系統，專為解決台灣醫療現場複雜的排班限制而設計。

本系統採用 **CSP (Constraint Satisfaction Problem)** 演算法，能在滿足勞基法與醫院內規的前提下，自動算出最公平的班表。

## ✨ 核心功能 (Features)

### 1. 🛡️ 智慧過勞保護 (Safety First)
系統內建嚴格的工時保護機制，防止極端班表產生：
*   **不連續值班**：絕對禁止連續兩天值班 (No back-to-back shifts)。
*   **7 天限 3 班**：採用滑動視窗 (Sliding Window) 偵測，任意連續 7 天內，值班數不得超過 3 班。避免出現 Q2 (隔日值) 的高強度排班。

### 2. ⚖️ 假日公平分配 (Weekend Equity)
解決「大家都想休週末」的難題：
*   系統會自動計算當月週末 (週六、週日) 總數。
*   強制設定每位醫師的**週末班上限**。
*   確保沒有人會因為運氣不好而包辦所有週末班。

### 3. 📅 預假許願池 (Leave Requests)
*   每位醫師可預先勾選 **最多 3 天** 的不值班日 (Wish List)。
*   排班引擎會將其視為「硬限制」，絕對避開這些日期。

### 4. 📊 自動化與視覺化
*   **一鍵排班**：運算時間通常小於 5 秒。
*   **日曆視圖**：直接生成視覺化的月曆，清楚標示平日與假日。
*   **數據統計**：即時顯示每人的總班數與週末班數，公平性一目了然。
*   **匯出報表**：支援下載 CSV 格式，可直接用 Excel 開啟微調。

## 🛠 技術架構

*   **前端/介面**：[Streamlit](https://streamlit.io/)
*   **核心演算法**：[Google OR-Tools](https://developers.google.com/optimization) (CP-SAT Solver)
*   **資料處理**：Pandas

## 🚀 如何執行 (本地端)

1.  安裝相依套件：
    ```bash
    pip install -r requirements.txt
    ```

2.  啟動應用程式：
    ```bash
    streamlit run app.py
    ```

## ☁️ 部署 (Deployment)

本專案支援 **Streamlit Cloud** 一鍵部署：
1.  將程式碼 Push 到 GitHub。
2.  在 Streamlit Cloud 連結此 Repository。
3.  每次 Push 更新，網站會自動重新部署。

## ⚠️ 免責聲明

此系統僅供輔助排班使用，產出結果仍需由總醫師 (CR) 針對特殊狀況 (如：急診支援、外訓人力) 進行最終核對。
