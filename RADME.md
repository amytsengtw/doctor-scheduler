# Cardinal Tien Hospital Dual-Track Rostering System (v4.8)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Organization](https://img.shields.io/badge/Organization-Cardinal%20Tien%20Hospital-purple)](https://www.cth.org.tw/)

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

### 🚀 Key Features (v4.8 Update)

1.  **Strict Shift Limits (The Iron Rule)**
    *   **PGY/Interns** strictly limited to **Max 6 Weekday Shifts** and **Max 2 Weekend Shifts**.
    *   Penalty for violation: **1,000,000** (Highest priority, practically impossible to break).

2.  **Rescue Mechanism Logic**
    *   If PGY/Interns hit their shift limit (6/2) and slots are still open, **Residents (R)** MUST support.
    *   R Support Cost: **50,000**.
    *   Logic: Since 50,000 < 1,000,000, the solver forces R support rather than allowing PGY to work a 7th weekday shift.

3.  **Point System (Relaxed)**
    *   Points (Weekday=1, Weekend=2) can exceed 10 if necessary (Low penalty: 100).
    *   This ensures "Fairness via Points" is secondary to "Strict Shift Counts".

---

## 中文說明

本版本 (v4.8) 針對 **耕莘醫院** 需求進行了核心邏輯調整，確立了「班數限制」的絕對權威。

### ✨ v4.8 核心變更：權重翻轉

我們重新定義了排班的優先順序，確保 PGY/Intern 不會因為點數計算而多值班。

#### 1. 班數限制是「天條」
*   **平日班**：PGY/Intern 絕對不可超過 **6 班**。
*   **假日班**：PGY/Intern 絕對不可超過 **2 班**。
*   **機制**：違反此規則的扣分設為 **1,000,000 (一百萬分)**。系統寧可讓程式崩潰也不會主動違反此條款。

#### 2. R 支援機制 (Rescue)
*   當 PGY/Intern 的班數額度 (6+2) 用完，而當月還有空缺時，住院醫師 (R) **必須** 下來支援。
*   **代價**：R 支援扣分為 **50,000 (五萬分)**。
*   **決策**：因為 5 萬 < 100 萬，系統會毫不猶豫地選擇「叫學長姐下來」，而不是「讓學弟妹多值一班」。

#### 3. 點數為輔
*   總點數 (Target 10) 僅作為參考指標，超標扣分極低 (100分)。
*   這意味著，只要班數不爆 (例如 2 假日 + 6 平日 = 10 點)，點數稍微高一點是可以接受的。

### 🏗 決策權重表 (Decision Matrix)

| 優先級 | 規則名稱 | 權重 (Penalty) | 結果 |
| :--- | :--- | :--- | :--- |
| **1** | **班數超標 (Shift Limit)** | **1,000,000** | **絕不發生** (PGY 最多 6平/2假) |
| **2** | **R 支援小班** | **50,000** | **必要時發生** (當 PGY 滿班時) |
| **3** | **不想值班 (No-Go)** | **5,000** | 盡量避開 |
| **4** | **點數超標 (>10)** | **100** | 可以接受 |

### 🚀 使用建議
請總醫師在設定時，務必確認 **R (住院醫師)** 的人數與意願，因為在 v4.8 邏輯下，一旦 PGY 滿班，R 將會承擔所有剩餘的壓力。
