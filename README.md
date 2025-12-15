# Dual-Track Medical Rostering System

An advanced constraint satisfaction solver for medical resident scheduling, powered by **Google OR-Tools** and **Streamlit**.

This system implements a dual-track scheduling logic ("Big Shift" for Delivery Room, "Small Shift" for General Wards) to optimize workforce allocation while strictly adhering to hospital regulations and maximizing fairness.

## 🚀 Features at a Glance

### 1. Mathematical Optimization
*   **Constraint Satisfaction Problem (CSP):** Models staffing requirements, labor laws, and personal preferences as mathematical constraints.
*   **Weighted Objective Function:** Balances conflicting goals (Fairness > Preferences) using penalty weights.
*   **Heuristic Search:** Generates multiple distinct feasible solutions using diversity constraints.

### 2. Weighted Point System (New in v4.0)
To ensure equitable workload distribution:
*   **Weekday Shift:** 1 Point
*   **Weekend Shift:** 2 Points
*   **Target:** $\sum Points \le 8$ per month.
*   **Soft Limit:** If a doctor exceeds 8 points due to labor shortage, the system allows it but flags the violation in the **Sacrifice Report**.

### 3. Dual-Track Logic
*   **Big Shift (Delivery Room):**
    *   **Attending (VS):** High-priority designated shifts.
    *   **Resident (R):** Fills gaps; protected by "No-Go" constraints.
*   **Small Shift (General Ward):**
    *   **Intern/PGY:** Subject to strict limits (max 2 shifts/week, 6 weekdays/month, 2 weekends/month).

## 🧮 Algorithmic Details

The core solver uses the **CP-SAT** (Constraint Programming - SATisfiability) solver from Google OR-Tools.

### Decision Variables
Let $X_{d, s}$ be a boolean variable where:
*   $d \in \{1, ..., DaysInMonth\}$
*   $s \in \{StaffMembers\}$
*   $X_{d, s} = 1$ if staff $s$ is assigned to day $d$, else $0$.

### Constraints
1.  **Coverage:** $\sum_{s} X_{d, s} = 1$ for all $d$. (One doctor per day)
2.  **Recovery:** $X_{d, s} + X_{d+1, s} \le 1$. (No back-to-back shifts)
3.  **Hard Leaves:** $X_{d, s} = 0$ for absolute leave dates.
4.  **Workload Limits:** $\sum_{d \in Week} X_{d, s} \le 2$ (for Interns).

### Objective Function ($Max$)
$$
\text{Maximize } \sum (W_{fairness} \times Fairness) - \sum (W_{penalty} \times Violations) + \sum (W_{wish} \times Preferences)
$$
*   **Fairness:** Minimizes variance in shift counts (Weekday/Weekend) across staff.
*   **Violations:** Penalties for exceeding point limits or assigning "No-Go" shifts.

## 📦 Installation & Usage

### Prerequisites
*   Python 3.8+
*   `pip install -r requirements.txt`

### Running the Application
```bash
streamlit run app.py
