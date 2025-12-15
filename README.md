# 🏥 台灣住院醫師排班系統 (Resident Scheduling System)

這是一個基於 Python 與 Google OR-Tools 開發的自動化排班系統 MVP，專為解決醫療排班的複雜限制而設計。

## ✨ 主要功能

*   **自動化排班**：使用 CSP (Constraint Satisfaction Problem) 演算法計算最佳解。
*   **勞基法/工時合規**：
    *   避免連續值班 (No back-to-back shifts)。
    *   每日確保有一名值班醫師。
*   **公平性原則**：系統會自動將總班數平均分配給每位醫師。
*   **預假機制 (Wish List)**：
    *   每位醫師可指定最多 3 天的「不值班日」。
    *   排班引擎會強制避開這些日期。
*   **資料匯出**：支援將結果匯出為 CSV 格式 (Excel 可開)。

## 🛠 技術架構

*   **前端/介面**：[Streamlit](https://streamlit.io/)
*   **核心演算法**：[Google OR-Tools](https://developers.google.com/optimization)
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

## ☁️ 部署

本專案支援直接部署於 **Streamlit Cloud**。
只要將程式碼推送到 GitHub，Streamlit Cloud 即可自動偵測並更新。

## ⚠️ 免責聲明

此為 MVP (Minimum Viable Product) 版本，僅供輔助排班使用。實際班表發布前，請務必由總醫師 (CR) 人工再次核對。
