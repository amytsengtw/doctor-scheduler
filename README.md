# Dual-Track Medical Rostering System (v4.4 R Rescue Edition)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/Solver-Google%20OR--Tools-green)](https://developers.google.com/optimization)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)](https://streamlit.io/)
[![Architecture](https://img.shields.io/badge/Architecture-Event--Driven-orange)]()

[English](#english-documentation) | [中文說明](#中文說明)

---

## English Documentation

### 🏗 System Architecture & Design

This system implements a **Multi-Stage Constraint Programming** approach to solve the complex medical rostering problem. Unlike simple heuristic scripts, we model the roster as a global optimization problem using **Google OR-Tools (CP-SAT)**.

#### 1. Architecture Diagram
The system follows a sequential dependency flow, ensuring that "Big Shift" constraints are propagated to the "Small Shift" solver to enable the **Automatic Rescue Mechanism**.

```mermaid
graph TD
    User[User Input] --> State[Session State Manager]
    State --> Config[JSON Config Loader]
    
    subgraph "Solver Pipeline"
        BigSolver[Step 1: Big Shift Solver]
        BigSolver --> |Output: R Schedule| Inter[Intermediate State]
        Inter --> |Input: R Availability| SmallSolver[Step 2: Small Shift Solver]
        SmallSolver --> |Logic: R Rescue| Final[Final Schedule]
    end
    
    User --> BigSolver
    Final --> Viz[Visualization Engine]
    Viz --> Excel[Excel/CSV Export]
