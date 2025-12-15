# Dual-Track Medical Rostering System (v4.3 Priority Update)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)](https://streamlit.io/)

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

A medical rostering system with a refined **priority logic**: It prioritizes avoiding "No-Go" preferences over strictly adhering to the 8-point limit.

### 🚀 Key Features (v4.3)

1.  **Priority Shift: No-Go > Points**
    *   **Goal**: If forced to choose between assigning a doctor to a "No-Go" day or making them exceed 8 points, the system will **exceed the points**.
    *   **Logic**: Violating a "No-Go" preference carries a penalty of **5000**, while exceeding the point limit carries a penalty of **200**.

2.  **Weighted Point System**
    *   **Weekday Shift**: 1 Point.
    *   **Weekend Shift**: 2 Points.
    *   **Target**: $\le 8$ points per month.

3.  **Q3 Spacing Preference**
    *   Soft constraint to encourage at least 2 days off between shifts.

---

## 中文說明

這是一套邏輯經過微調的排班系統，v4.3 版本調整了決策優先順序，更貼近人性化排班需求。

### ✨ v4.3 核心優先級調整

系統在遇到排班衝突時，會依據以下權重進行取捨：

1.  **⛔️ 絕對請假 (Hard Constraints)**：權重 $\infty$。
    *   婚喪喜慶、未到職。絕對不會排入。
2.  **🚫 不想值班 (No-Go Preference)**：權重 **5000**。
    *   醫師標示「不想值」的日子，系統會盡全力避開。
3.  **⚖️ 公平性 (Fairness)**：權重 **2000**。
    *   在避開不想值班日子的前提下，盡量讓大家勞逸不均。
4.  **📉 點數上限 (Point Limit <= 8)**：權重 **200**。
    *   **重要變更**：若為了避開某人的 No-Go，導致必須讓另一人點數變為 9 點，系統現在會**選擇讓點數超標**。
    *   *因為多值一班雖然累，但比在「絕對不想值的日子」值班來得好一點。*

### 🚀 使用教學

1.  **設定請假**：勾選「絕對無法值班」的日期。
2.  **設定意願**：
    *   勾選 **「不想值班 (No-Go)」**：這是除了請假之外最強力的保護。
3.  **運算**：按下開始。
4.  **檢查**：
    *   如果看到犧牲報告顯示「點數超標」，代表系統為了保護大家的 No-Go 而做出的妥協。

### 📜 授權
MIT License
