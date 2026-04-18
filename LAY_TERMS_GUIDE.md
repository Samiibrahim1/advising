# Advising V2 — Plain-Language Guide
### "If you had to rebuild this app from scratch, here's what it is and what it does"

---

## What Is This App?

This is a **university academic advising tool**. Its job is to help academic advisers (and administrators) manage the process of telling students which courses they should register for each semester.

Without this app, advisers would manually go through spreadsheets for every student, check what courses they've completed, figure out which ones they're allowed to take next (based on prerequisites), and then track who's been advised and who hasn't. This app automates all of that.

---

## Who Uses It?

There are two types of users:

### 1. Administrators
Admins set everything up and keep it running. They:
- Upload the data (student transcripts and course catalogs) at the start of each semester
- Create the "advising period" (basically declare "we are now doing Spring 2026 advising")
- Manage which advisers exist and which programs they can see
- Configure the email templates used to notify students
- Download backups and view audit logs

### 2. Advisers
Advisers do the actual student-facing work. They:
- Look up a student by name or ID
- See the student's academic standing, credits completed, and remaining credits
- See a list of all courses the student is eligible (or ineligible) to take, with reasons
- Mark courses as "Advised" (must take), "Optional" (may take), or "Repeat" (retaking a failed course)
- Save the advising record
- Send the student an email with their course selections
- View dashboards showing overall progress (how many students have been advised so far)

---

## What Programs Does It Support?

The app is designed for multiple academic programs ("majors"), each with its own student data and course catalog. Out of the box the defaults are:

- **PBHL** — Public Health
- **SPTH-New** — Speech Therapy (new curriculum)
- **SPTH-Old** — Speech Therapy (old curriculum)
- **NURS** — Nursing

Each program runs completely independently — separate student lists, separate courses, separate advising periods.

---

## The Core Concept: Eligibility

The most important thing this app does is determine **whether a student is eligible to take a course**. It checks:

- Has the student **already completed** the course? → Mark it done, offer "repeat" option only
- Is the student **already registered** for it? → Show as registered
- Has the student completed the **prerequisites** (required prior courses)?
- Are **co-requisites** (courses that must be taken simultaneously) satisfied?
- Has the adviser given the student a **bypass** (an exception that overrides missing prerequisites)?

The result for each course is one of: Completed, Registered, Eligible, or Not Eligible — with a plain-language reason.

---

## The Data: Two Key Spreadsheets

The whole system runs on two Excel files that an admin uploads per program:

### 1. Courses File
A list of every course in the program. For each course it records:
- Course code and title
- How many credits it's worth
- Whether it's a "Required" or "Intensive" type course
- What semester it's typically offered (e.g., Fall-1, Spring-2)
- Prerequisites (what must be done before) and co-requisites (what must be done alongside)

### 2. Progress File
A snapshot of every student's transcript. For each student it records:
- Student ID and name
- Which courses they've completed (with grades)
- Which courses they're currently registered for
- Credit totals (completed, registered, remaining)

The app reads these two files and automatically computes eligibility for every student in real time.

---

## The Advising Workflow (Step by Step)

1. **Admin uploads** the semester's courses file and progress file for a program.
2. **Admin creates an advising period** (e.g., "Spring 2026, Dr. Smith"). The app takes a snapshot of the current data (student progress and course configuration) so it can be restored later.
3. **Adviser logs in** and sees their Dashboard — showing how many students still need advising.
4. **Adviser opens the Workspace** and searches for a student.
5. The app shows the student's profile: standing, credits left, course completion counts (completed, registered, eligible), and a full-width grid of courses.
6. Courses are **grouped by semester** (e.g., "Fall-1", "Spring-2") so the adviser can quickly find what's relevant. A **search bar** lets the adviser filter by course code or title instantly. A **"Show not offered" toggle** reveals courses not available this semester — they appear greyed out so the adviser knows they exist but can't be selected.
7. Each course card is **color-coded** — green tint for completed, yellow for registered, white for eligible, grey for ineligible or not offered. Ineligible courses show the missing prerequisites right on the card.
8. **Adviser clicks "Advise"** on courses they recommend, "Optional" for optional ones, or "Repeat" for repeated courses.
9. The selected courses appear in a **horizontal row below the course grid** — showing Advised, Optional, Repeat, and an Advisor Note box side by side. A running credit counter with a **per-category breakdown** (Advised / Optional / Repeat) warns if the total exceeds the student's remaining credits or looks unusually heavy (more than 18 credits).
10. **Adviser clicks "Recommend"** (optional) — the app suggests courses automatically and shows a **preview** of what will be added. The adviser reviews and clicks Accept or Cancel.
11. **Adviser clicks Save** — the selection is stored in the database.
12. **Adviser clicks Email** (optional) — the app generates an email using the configured template and sends it to the student's email address.
13. The dashboard updates to show one more advised student.
14. When switching between students, the **currently viewed tab** (Schedule, Academic Record, Degree Plan, etc.) stays the same — no need to re-navigate each time.

When a new semester starts and new data is uploaded, creating a new period captures the new data. **Switching back to an older period automatically restores the student progress and course configuration that were active at that time** — so graduated students and old course setups are preserved in their original periods.

---

## What Happens When You Save?

Every time a selection is saved, the app:
- Records the course selections (advised, optional, repeat lists) and any notes
- Saves a **session snapshot** — a historical record of what was advised and when
- Associates it all with the current advising period

Old snapshots can be viewed or restored later. This means if an adviser accidentally overwrites a student's data, they can roll back.

---

## Insights and Analytics

The **Insights page** gives advisers and admins analytical tools:

### All Students Matrix
A grid showing every student (rows) and every course (columns). Each cell shows a color-coded status code. At a glance, you can see the entire cohort's progress. You can filter by semester, filter by remaining credits, and even "simulate" what would happen if certain courses were added as prerequisites.

### QAA Sheet
Lists students who are close to graduating (under a configurable credit threshold) along with their course status details. Used to prioritize advising for students who are almost done.

### Schedule Conflict Analysis
Groups courses that tend to have the same students eligible for them, helping identify courses that might conflict if scheduled at the same time.

### Course Offering Planner
Recommends which courses to actually offer next semester based on how many students are eligible for them. It scores courses by how many students need them, how many are close to graduating, and whether blocking this course would cascade into blocking other courses.

### Degree Plan View
Shows a student-specific view of their full program, organized by suggested semesters — a roadmap to graduation.

---

## Reports and Exports

The app can export Excel workbooks for:
- An individual student's advising summary
- All advised students in the current period
- The QAA sheet
- The schedule conflict analysis

---

## Email System

The app sends emails via Microsoft Office 365 SMTP. Email bodies are generated from **templates** that admins configure. Templates use variables like `{student_name}`, `{semester}`, `{year}`, and `{advisor_name}`. There's a "Default" template and a "Probation" template out of the box, and admins can create custom ones per program.

Before sending, advisers can **preview** exactly what the email will look like for a specific student.

---

## Bypasses and Exceptions

Sometimes a student needs to take a course even if they haven't technically met all prerequisites. Advisers can create a **bypass** — a per-student, per-course override with a note explaining why it was granted. Bypassed courses show as "Eligible (Bypass)" in the eligibility list.

Advisers can also **hide** specific courses from a student's view (if the course is irrelevant for that student) or **exclude** entire sets of courses from multiple students at once (useful for electives that a cohort won't be taking).

---

## Legacy Import

The app can read data from the older version of the advising tool (a Python/Streamlit app). Admins can point it at the legacy data folders and it will import course files, student progress data, historical advising sessions, and period history — migrating everything into the new system.

---

## Backups

The admin panel has a Backups page. Triggering a backup runs `pg_dump` on the database and stores a compressed copy to the configured storage (either Cloudflare R2 cloud storage or the local filesystem).

---

## Audit Log

Every important action is recorded in an audit log: dataset uploads, period changes, course planner saves, dataset deletions. Admins can review this log to see who did what and when.

---

## How to Run It (Short Version)

To spin up your own copy:

1. **Set up the backend**: Python 3.12+, create a virtual environment, install dependencies (`pip install -r requirements.txt`), configure a `.env` file with a database URL and JWT secret, then run `uvicorn app.main:app --reload`.

2. **Set up the frontend**: Node.js 18+, `npm install`, configure `VITE_API_BASE_URL` to point at the backend, then `npm run dev`.

3. **Log in** with the default credentials (admin@example.com / admin1234 or adviser@example.com / adviser1234 — change these immediately in production).

4. **Upload data**: Go to Admin → Datasets, upload a courses Excel file and a progress Excel file for your program.

5. **Create a period**: Go to Admin → Periods and create the current semester's advising period.

6. **Start advising**: Switch to the Adviser interface and begin working through students.

---

## Key Things to Know If Rebuilding

- The **eligibility engine** (the core logic that checks prerequisites) lives in `eligibility_utils.py` in the root of the project. It's shared code inherited from the legacy app. The V2 backend calls into it directly.
- The **reporting logic** (Excel export formatting) lives in `reporting.py`, also in the root, also shared with the legacy app.
- The app is designed so each "major" is completely isolated — different datasets, different periods, different selections.
- User access control is granular: an adviser can be restricted to only see certain majors.
- The database schema uses a single SQLite file locally, or can be pointed at a PostgreSQL database (e.g., Neon cloud Postgres) in production.
- File storage works in two modes: local folder or Cloudflare R2 (S3-compatible cloud storage).
