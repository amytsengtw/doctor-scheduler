# Cardinal Tien Hospital Dual-Track Rostering System (v4.5)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)](https://streamlit.io/)
[![Organization](https://img.shields.io/badge/Organization-Cardinal%20Tien%20Hospital-purple)](https://www.cth.org.tw/)

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

### 🏥 System Overview
This is a customized intelligent rostering system designed for the **OB/GYN Department of Cardinal Tien Hospital (CTH)**. It solves the complex "Dual-Track" scheduling problem (Delivery Room vs. General Wards) using **Google OR-Tools**.

### 🚀 Key Features (v4.5)

1.  **Automatic Resident Rescue Mechanism**
    *   **Trigger**: When a PGY/Intern's workload exceeds **10 points** (previously 8).
    *   **Action**: Residents (R) are automatically assigned to support "Small Shifts" to prevent burnout.
    *   **Constraint**: Support shifts strictly follow Q3 spacing (2-day gap) and respect Residents' "No-Go" preferences.

2.  **Weighted Point System**
    *   **Weekday Shift**: 1 Point.
    *   **Weekend Shift**: 2 Points.
    *   **Load Balancing**: The solver minimizes the variance of total points among doctors.

3.  **Excel Calendar Export**
    *   Generates a formatted CSV that mimics a weekly calendar layout, ready for direct printing or manual adjustment in Excel.

4.  **Multi-Solution Generation**
    *   Produces 1 to 5 distinct feasible schedules for decision support.

---

## 中文說明

這是一套專為 **耕莘醫院婦產科** 量身打造的智慧排班系統。系統採用雙軌制運算，並具備自動救援機制，確保在人力吃緊時能自動調度資源，同時兼顧公平性與生活品質。

### ✨ v4.5 核心功能

1.  **自動救援機制 (Automatic Rescue)**
    *   **觸發條件**：當 PGY 或 Intern 的月負載點數 **超過 10 點** 時。
    *   **運作邏輯**：系統會判斷「讓住院醫師 (R) 下來支援 (扣100分)」優於「讓 PGY 過勞 (扣1000分)」。
    *   **保護機制**：救援的住院醫師絕不撞期、不違反 Q3 間隔、不排入「不想值班」的日子。

2.  **點數負載平衡**
    *   **平日班** = 1 點。
    *   **假日班** = 2 點。
    *   系統目標是讓每位醫師的總點數盡量平均，並控制在合理範圍內。

3.  **雙軌排班邏輯**
    *   **大班 (產房)**：主治醫師 (VS) + 住院醫師 (R)。優先滿足 VS 指定班。
    *   **小班 (一般)**：PGY + 實習醫師 (Intern)。嚴格遵守工時規範。

4.  **Excel 日曆格式輸出**
    *   下載的 CSV 檔案已排版為「週曆格式」，開啟後即可直接檢視與微調，無須二次加工。

### 🏗 系統設計文件 (Design Doc)

#### 1. 權重決策矩陣 (Decision Matrix)
系統依據以下權重來決定排班的優先順序：

| 優先級 | 規則名稱 | 權重 (Penalty) | 設計意涵 |
| :--- | :--- | :--- | :--- |
| **1 (最高)** | **絕對請假 / 法規** | **$\infty$** | 婚喪喜慶、未到職、連續值班。絕對不可違反。 |
| **2** | **不想值班 (No-Go)** | **5000** | 保護醫師的生活品質，除非無人可用，否則不排。 |
| **3** | **PGY/Int 點數 > 10** | **1000** | **v4.5 更新**：容忍度提升至 10 點，超過才視為嚴重過勞。 |
| **4** | **公平性 (變異數)** | **500** | 盡量讓大家的班數平均。 |
| **5** | **R 支援代價** | **100** | 優先讓 R 支援 (扣100)，也不要讓 PGY 嚴重過勞 (扣1000)。 |

#### 2. 資料流架構
```mermaid
graph TD
    User[用戶輸入] --> Config[JSON 設定檔]
    Config --> BigSolver[階段一：大班運算 (VS/R)]
    BigSolver --> R_Schedule[R 值班表]
    R_Schedule --> SmallSolver[階段二：小班運算 (PGY/Int)]
    SmallSolver --> RescueLogic{需要救援?}
    RescueLogic -->|Yes| R_Support[R 支援小班]
    RescueLogic -->|No| NormalSchedule[正常排班]
    R_Support --> FinalOutput[最終班表]
    NormalSchedule --> FinalOutput
