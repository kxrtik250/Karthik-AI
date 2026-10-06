# Database Schema Documentation — Karthik AI

This document outlines the relational database schema implemented in **Phase 2** for Karthik AI using **PostgreSQL** and **SQLAlchemy**.

---

## 1. Entity-Relationship Overview

```mermaid
erDiagram
    PROFILES ||--o{ SKILLS : "has"
    PROFILES ||--o{ PROJECTS : "has"
    PROFILES ||--o{ CERTIFICATIONS : "has"
    PROFILES ||--o{ PLACEMENT_DRIVES : "tracks"
    COMPANIES ||--o{ PLACEMENT_DRIVES : "participates in"

    PROFILES {
        uuid id PK
        varchar name
        varchar email UK
        varchar phone
        varchar university
        varchar degree
        varchar branch
        int graduation_year
        numeric cgpa
        text career_goals
        text summary
        timestamptz created_at
        timestamptz updated_at
    }

    SKILLS {
        uuid id PK
        uuid profile_id FK
        varchar name
        varchar category
        varchar proficiency
        timestamptz created_at
        timestamptz updated_at
    }

    PROJECTS {
        uuid id PK
        uuid profile_id FK
        varchar name
        text description
        jsonb technologies
        varchar status
        varchar role
        varchar url
        date start_date
        date end_date
        timestamptz created_at
        timestamptz updated_at
    }

    CERTIFICATIONS {
        uuid id PK
        uuid profile_id FK
        varchar name
        varchar issuer
        date issue_date
        date expiry_date
        varchar credential_url
        timestamptz created_at
        timestamptz updated_at
    }

    COMPANIES {
        uuid id PK
        varchar name UK
        varchar industry
        varchar website
        varchar location
        text notes
        timestamptz created_at
        timestamptz updated_at
    }

    PLACEMENT_DRIVES {
        uuid id PK
        uuid profile_id FK
        uuid company_id FK
        varchar role
        varchar status
        date deadline
        varchar compensation
        varchar employment_type
        varchar location
        text notes
        date applied_date
        timestamptz created_at
        timestamptz updated_at
    }
```

---

## 2. Table Specifications

### `profiles`
Stores user profile information, educational background, academic metrics, and career ambitions.
- **Primary Key:** `id` (UUID)
- **Unique Constraint:** `email`
- **Cascade Behavior:** Deleting a profile cascades to associated skills, projects, certifications, and placement drives.

### `skills`
Stores competencies, tools, languages, and frameworks.
- **Primary Key:** `id` (UUID)
- **Foreign Key:** `profile_id` references `profiles.id` (ON DELETE CASCADE)
- **Unique Constraint:** `(profile_id, name)` prevents duplicate entries per profile.

### `projects`
Tracks portfolio and academic projects.
- **Primary Key:** `id` (UUID)
- **Foreign Key:** `profile_id` references `profiles.id` (ON DELETE CASCADE)
- **Technologies:** JSONB array (e.g. `["Python", "FastAPI", "React", "PostgreSQL"]`).
- **Status values:** `planned`, `in_progress`, `completed`.

### `certifications`
Tracks professional certifications, licenses, and badges.
- **Primary Key:** `id` (UUID)
- **Foreign Key:** `profile_id` references `profiles.id` (ON DELETE CASCADE)

### `companies`
Reference dictionary of employers and target companies.
- **Primary Key:** `id` (UUID)
- **Unique Constraint:** `name`

### `placement_drives`
Tracks recruitment rounds, applications, status, compensation, and deadlines.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:**
  - `profile_id` references `profiles.id` (ON DELETE CASCADE)
  - `company_id` references `companies.id` (ON DELETE CASCADE)
- **Status Progression:** `interested` -> `applied` -> `shortlisted` -> `interview_scheduled` -> `interviewed` -> `offered` -> `accepted` / `rejected` / `withdrawn`.

---

## 3. Database Migrations
Migrations are managed with **Alembic**.

To generate a new migration:
```bash
alembic revision --autogenerate -m "description"
```

To apply migrations:
```bash
alembic upgrade head
```
