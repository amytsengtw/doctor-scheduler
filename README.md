# Dual-Track Medical Rostering System (v4.2 Q3 Edition)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)](https://streamlit.io/)

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

A medical rostering system optimized for **Shift Spacing (Q3 Principle)** and **Fairness**. It ensures doctors have adequate rest between shifts while adhering to labor laws and hospital regulations.

### 🚀 Key Features (v4.2)

1.  **Q3 Spacing Preference (Smart Rest)**
    *   **Goal**: Minimize "Shift-Off-Shift" (Q2) patterns.
    *   **Strategy**: Incentivize "Shift-Off-Off-Shift" (Q3) patterns to ensure at least 2 days of rest between duties.
    *   *Note: This is a soft constraint. Coverage and fairness still take precedence.*

2.  **Weighted Point System (Load Balancing)**
    *   **Weekday Shift**: 1 Point.
    *   **Weekend Shift**: 2 Points.
    *   **Target**: $\le 8$ points per month per doctor.

3.  **Dual-Track & Multi-Solution**
    *   Separates **Delivery Room (Big Shift)** and **General Ward (Small Shift)** logic.
    *   Generates 1~5 distinct feasible schedules for decision support.

### 🧮 Mathematical Model

*   **Variables**: $X_{d, s} \in \{0, 1\}$ (Doctor $s$ works on day $d$).
*   **Spacing Constraint**: 
    To discourage Q2 patterns (1-0-1), we apply a penalty if $X_{d, s} + X_{d+2, s} = 2$.
    $$
    \text{Minimize } \sum_{d, s} (X_{d, s} \land X_{d+2, s}) \times W_{spacing}
    $$

---

## 中文說明

這是一套具備 **智慧間隔優化 (Smart Spacing)** 的雙軌排班系統。v4.2 版本特別強化了對「生活品質」的重視，盡量避免過於密集的排班。

### ✨ v4.2 核心功能

1.  **Q3 排班原則 (Q3 Preference)**
    *   **痛點**：傳統排班常出現「值1休1值1」(Q2) 的地獄班表。
    *   **解法**：系統內建軟限制，**盡量讓值班日之間隔開兩天** (Q3)。
    *   *說明：這是一個加分項目。若人力吃緊，系統仍會以「把班排出來」為優先，但會盡量減少 Q2 的發生。*

2.  **點數負載平衡**
    *   **平日 = 1 點** / **假日 = 2 點**。
    *   系統會監控每位醫師的總點數，目標控制在 **8 點** 以內。若超過，會在犧牲報告中紅字警示。

3.  **雙軌與多方案**
    *   針對 **大班 (VS+R)** 與 **小班 (PGY+Int)** 分開運算。
    *   一次提供 1~5 種不同的班表方案，供總醫師挑選。

4.  **Excel 日曆格式輸出**
    *   下載後的 CSV 檔案直接呈現週曆排版，方便人工微調。

### 🚀 使用教學

1.  **輸入名單**：填寫四類醫師名單。
2.  **設定請假**：勾選「絕對無法值班」的日期 (Hard Constraints)。
3.  **設定意願**：勾選「指定值班」或「不想值班」 (Soft Constraints)。
4.  **運算**：按下開始，等待系統生成多組方案。
5.  **決策**：
    *   查看 **犧牲報告**：確認是否有醫師點數爆表。
    *   查看 **日曆**：確認是否有過多的 Q2 (隔日值) 班表。
    *   下載最滿意的方案。

### 📜 授權
MIT License
