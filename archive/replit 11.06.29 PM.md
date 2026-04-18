# Advising Dashboard

## Overview
The Advising Dashboard is a Streamlit application for Phoenix University academic advisors. It aims to streamline academic advising by providing tools for student progress tracking, course eligibility checks, advising session management, and Google Drive data synchronization. It supports multiple majors (PBHL, SPTH-New, SPTH-Old) and includes features like a Course Offering Planner for optimized course recommendations, ultimately providing a comprehensive platform for academic guidance. The project envisions enhancing academic success and administrative efficiency through intuitive and data-driven advising.

## User Preferences
I prefer:
- Simple, direct language in explanations.
- Iterative development with clear communication at each stage.
- To be asked before any major changes are implemented.
- The agent to prioritize functional completeness over minor optimizations.
- Do not make changes to files outside of the core application logic (e.g., `get_refresh_token.py`, `.streamlit/config.toml`).
- Do not modify the deployment configuration unless explicitly requested.

## System Architecture

### UI/UX Decisions
The dashboard features a modern, accessible design adhering to WCAG AA standards, including keyboard navigation and mobile responsiveness. It uses a 5-section navigation system (Home, Setup, Workspace, Insights Hub, Settings) with a persistent header. Functionality is gated by a mandatory advising period selection. The interface includes a simple student selection dropdown, a stepwise accordion-style data upload with inline validation, and a unified notification system. Visual styling is consistent, and deprecated Streamlit API usage has been updated.

### Technical Implementations
Built with Streamlit in Python 3.11, the application uses Pandas for data manipulation. It integrates with the Google Drive API for cloud storage and synchronization, and uses standard Python SMTP for Outlook/Office 365 email functionality with HTML templates. Key features include multi-major data tracking, automated course eligibility checks (including a Requisite Bypass feature), and persistent advising sessions. Performance optimizations include extensive session-state caching for advising data and period history.

### Feature Specifications
- **Multi-Major Support**: Manages data for PBHL, SPTH-New, SPTH-Old.
- **Course Eligibility**: Automated checks with support for prerequisites, corequisites, concurrent requirements, and student standing. Includes a "Requisite Bypass" feature.
- **Student Views**: Provides a "Student Eligibility View" and a "Full Student View" with degree plan, QAA sheet, and schedule conflict insights.
- **Course Offering Planner**: Recommends courses based on student needs, bottlenecks, and eligibility, using a weighted priority scoring system.
- **Advising Sessions**: Records and persists advisor recommendations and notes, with Google Drive synchronization and a bulk restore feature.
- **Email Integration**: Sends formatted advising sheets via Outlook/Office 365.
- **Data Upload**: Validated, stepwise interface for `courses_table.xlsx`, `progress_report.xlsx`, and email rosters.
- **Advising Periods**: Tracks advising cycles per major, with archiving and new period creation.
- **Degree Plan View**: Displays curriculum grid with color-coded student progress.
- **Course Exclusions**: Allows advisors to exclude intensive courses for selected students.

### System Design Choices
- **File Organization**: Google Drive uses a major-specific folder hierarchy (`{ROOT}/{MAJOR}/`) with sessions in `{ROOT}/{MAJOR}/sessions/`.
- **Period Tracking**: Advising periods are tracked per major, with metadata in `current_period.json` and historical data in `periods_history.json`.
- **Data Storage**: Advising sessions are saved locally and asynchronously synced to Google Drive.
- **Security**: Sensitive credentials are managed via Replit Secrets.
- **Module Structure**: Eligibility logic is isolated in `eligibility_utils.py`, and Google Drive functions use lazy loading to prevent import-time side effects.

## External Dependencies

- **Google Drive API**: For cloud backup, data synchronization, and file organization.
- **Outlook/Office 365 SMTP**: For sending advising emails.
- **Streamlit**: Primary web framework.
- **Pandas**: For data manipulation, especially with Excel files.
- **openpyxl**: For reading and writing Excel files.
- **Pillow**: For image handling.