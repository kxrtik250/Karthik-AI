# Phase 7: Placement Intelligence

## 1. Overview & Objective

Phase 7 upgrades Karthik AI from a personal-context-aware assistant into an intelligent **Placement Intelligence Engine**. The system evaluates placement opportunities, checks candidate eligibility, identifies skill gaps, ranks upcoming recruitment drives, and generates customized interview preparation plans.

### Core Architectural Principle

Placement Intelligence follows a strict division of responsibility:

```
User Query / React UI
          ↓
  FastAPI Endpoints
          ↓
┌────────────────────────────────────────────────────────┐
│             Placement Intelligence Service             │
│                                                        │
│  1. Structured Drive & Company Data (PostgreSQL)       │
│  2. Profile, Skills, Projects, Certs (PostgreSQL)      │
│  3. Company Documents / Brochures (pgvector RAG)       │
│  4. Deterministic Business Logic (Python Rules Engine) │
└────────────────────────────────────────────────────────┘
          ↓
┌────────────────────────────────────────────────────────┐
│            Grounded LLM Reasoning & Advice             │
│      (Only invoked AFTER verified factual retrieval)   │
└────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Deterministic Business Logic Rule**: Mathematical checks (e.g., `cgpa >= min_cgpa`), branch string comparisons, and skill overlap calculations are performed by deterministic Python algorithms—**never** delegated to LLM hallucination or imprecise token sampling.
>
> **Missing Data Safeguard**: When profile or drive facts are absent, the engine reports an explicit `"UNKNOWN"` / `"insufficient_data"` status. It **never** converts missing information into a pass.

---

## 2. Data Models & Schema Extensions

### `PlacementDrive` Extended Attributes (`backend/app/models/placement.py`)

| Field | Type | Description |
|---|---|---|
| `min_cgpa` | `Numeric(4, 2)` | Minimum qualifying CGPA required by recruiter |
| `eligible_branches` | `JSONB` | List of allowed academic departments (e.g., `["CSE", "IT"]`) |
| `graduation_year` | `Integer` | Eligible batch graduation year (e.g., `2027`) |
| `required_skills` | `JSONB` | Mandatory technical competencies (e.g., `["Python", "FastAPI"]`) |
| `preferred_skills` | `JSONB` | Good-to-have technologies (e.g., `["Docker", "PostgreSQL"]`) |
| `backlog_allowed` | `Boolean` | Whether active backlogs / standing arrears are permitted |
| `selection_process` | `JSONB` | Ordered interview rounds (e.g., `["OA", "Technical 1", "HR"]`) |
| `tier` | `String(50)` | Institutional placement category (`Super Dream`, `Dream`, etc.) |

---

## 3. Intelligence Engines

### A. Deterministic Eligibility Engine

Evaluates candidate profile against drive criteria across 4 dimensions:

1. **CGPA**:
   - `candidate_cgpa >= drive.min_cgpa` $\rightarrow$ `eligible`
   - `candidate_cgpa < drive.min_cgpa` $\rightarrow$ `not_eligible`
   - `candidate_cgpa is None` and requirement exists $\rightarrow$ `unknown`
   - No requirement specified $\rightarrow$ `na`
2. **Branch**:
   - Normalizes branch synonyms using canonical mappings (e.g., `{"cse", "computer science and engineering", "cs", "b.e cse"}`).
   - Matched $\rightarrow$ `eligible`
   - Not in list $\rightarrow$ `not_eligible`
   - Profile branch missing $\rightarrow$ `unknown`
3. **Graduation Year**:
   - `candidate_year == drive.graduation_year` $\rightarrow$ `eligible`
   - `candidate_year != drive.graduation_year` $\rightarrow$ `not_eligible`
   - Missing profile year $\rightarrow$ `unknown`
4. **Backlog Policy**:
   - `drive.backlog_allowed is False` $\rightarrow$ `unknown` (flags requirement for candidate to verify 0 standing arrears).
   - `drive.backlog_allowed is True` or unspecified $\rightarrow$ `na`.

**Overall Status Classification**:
- If any criterion is `not_eligible` $\rightarrow$ **`NOT_ELIGIBLE`** (`is_eligible = False`)
- Else if any criterion is `unknown` $\rightarrow$ **`UNKNOWN`** (`is_eligible = None`)
- Else $\rightarrow$ **`ELIGIBLE`** (`is_eligible = True`)

### B. Skill Matching Engine

1. Normalizes skill aliases (e.g., `fast-api` $\leftrightarrow$ `fastapi`, `postgres` $\leftrightarrow$ `postgresql`, `react.js` $\leftrightarrow$ `react`).
2. Calculates exact and fuzzy sub-string overlaps for:
   - `matching_required` vs `missing_required`
   - `matching_preferred` vs `missing_preferred`
3. Computes weighted match percentage:
   $$\text{Overall Match \%} = 0.75 \times \text{Required Match \%} + 0.25 \times \text{Preferred Match \%}$$

### C. Opportunity Prioritization Ranking

Composite explainable scoring formula on a 0–100 scale:

| Component | Weight | Criteria |
|---|---|---|
| **Eligibility** | **40 pts** | `ELIGIBLE`: 40 pts, `UNKNOWN`: 20 pts, `NOT_ELIGIBLE`: 0 pts |
| **Skill Match** | **30 pts** | $\text{Match Percentage} \times 0.30$ |
| **Deadline Urgency** | **15 pts** | $\le 7$ days: 15 pts, $\le 14$ days: 12 pts, $\le 30$ days: 8 pts, $>30$ days: 4 pts |
| **Role Value / Tier** | **15 pts** | `Super Dream` / $\ge 18$ LPA: 15 pts, `Dream` / $\ge 9$ LPA: 10 pts, Standard: 5–6 pts |

- **`HIGH` Priority**: Composite score $\ge 70.0$
- **`MEDIUM` Priority**: Composite score $45.0 \le \text{score} < 70.0$
- **`LOW` Priority**: Composite score $< 45.0$

### D. Targeted Interview Preparation Generation

Generates structured roadmaps by combining:
- Drive requirements & selection rounds
- Overlapping portfolio projects candidate can present
- Missing technical skills requiring study
- Document context retrieved via pgvector from uploaded recruitment documents
- LLM inference at `temperature=0.0` for grounded strategy

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/placements/open` | Lists all active, non-closed placement drives |
| `GET` | `/api/placements/upcoming` | Drives with deadlines approaching within `days` (default 30) |
| `GET` | `/api/placements/eligible` | Evaluates and filters drives where candidate is `ELIGIBLE` |
| `GET` | `/api/placements/priorities` | Returns opportunities ranked by composite priority score |
| `GET` | `/api/placements/{id}/eligibility` | Detailed 4-point eligibility assessment for a drive |
| `GET` | `/api/placements/{id}/match` | Required and preferred skill breakdown |
| `GET` | `/api/placements/{id}/comparison` | Profile vs drive comparison with matching projects and certs |
| `POST` | `/api/placements/{id}/prepare` | Generates targeted interview preparation strategy |

---

## 5. Frontend UI Implementation

- **Navigation**: Dedicated "Placement Intelligence" 🎓 tab in sidebar.
- **Placements Dashboard (`PlacementsView.jsx`)**:
  - Summary KPI cards: Active Drives, Verified Eligible, Deadlines Approaching, High Priority.
  - Tab views: "Prioritized Pipeline", "All Open Drives", "Upcoming Deadlines".
  - Search & filter: Real-time search by company/role, filter by eligibility status.
- **Drive Cards (`PlacementCard.jsx`)**:
  - Visual badges: `✓ ELIGIBLE` (green), `✕ NOT ELIGIBLE` (red), `? UNKNOWN` (yellow).
  - Priority badge with composite score (e.g., `HIGH PRIORITY (88)`).
  - Skill match progress bar and top required skills tags.
  - Actions: "Compare Profile" and "Prep Strategy".
- **Comparison Modal (`ComparisonModal.jsx`)**:
  - Full criteria assessment table with candidate values vs requirements.
  - Matching vs missing skill chips (color-coded).
  - Relevant portfolio projects with overlapping technology tags.
- **Preparation Modal (`PreparationModal.jsx`)**:
  - Selection rounds quick-bar.
  - Skills to revise and projects to highlight chips.
  - Formatted comprehensive preparation strategy.
  - Document sources citation footer.

---

## 6. Verification & Test Suite

All tests execute against the isolated test database `karthik_ai_test`. The live development database `karthik_ai_db` remains 100% untouched and authoritative (`Karthik`, Sathyabama Institute of Science and Technology, CGPA 7.52).

```bash
# Backend pytest suite (18/18 passing)
pytest -v
```

Tests cover:
- Deterministic eligibility passing, failing, and unknown handling
- Normalized skill matching and match percentages
- Prioritization ranking and composite score breakdown
- Comparison and preparation REST endpoints
- Multi-turn conversational chat intent routing
- Zero database pollution on `karthik_ai_db`
