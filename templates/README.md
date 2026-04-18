# Data Upload Templates

This folder contains template files for the Advising Dashboard.

## Files

### 1. courses_table_template.xlsx
Course information for your program.

**Required Columns:**
- `Course Code` - Unique course identifier (e.g., PBHL201)
- `Offered` - When course is offered (Fall, Spring, Summer, Fall/Spring, etc.)

**Recommended Columns:**
- `Title` - Course name
- `Credits` - Credit hours (typically 1-3)
- `Suggested Semester` - Format: "Fall-1", "Spring-2", "Summer-3" (semester-year for Degree Plan view)
- `Type` - Required, Intensive, or Elective
- `Prerequisite` - Course codes separated by commas (must complete before taking this course)
- `Concurrent` - Course codes separated by commas (must register at same time)
- `Corequisite` - Course codes separated by commas (must complete or register at same time)

**Status Codes Used:**
- `c` or `Completed` - Student completed the course
- `r` or `Registered` - Student is currently registered
- `f` or `Failed` - Student failed the course
- (empty) - Student has not taken the course

---

### 2. progress_report_template.xlsx
Student progress tracking with two sheets.

**Sheet 1: Required Courses**
- `ID` - Student ID number
- `NAME` - Student full name
- `Total Credits Completed` - Credits earned so far
- `Remaining Credits` - Credits needed to graduate
- `Standing` - Freshman, Sophomore, Junior, Senior
- Plus one column for each course code with student status (c, r, f, or empty)

**Sheet 2: Intensive Courses** (Optional)
- Same structure as Required Courses
- Used for workshop courses or special requirements
- Data is automatically merged with Required Courses sheet

---

### 3. email_roster_template.csv
Email addresses for students (optional - only needed if using email feature).

**Columns:**
- `Student Name` - Full name
- `Student ID` - Student ID number
- `Email` - Email address

---

## Usage Instructions

1. **Download the templates** from the `templates/` folder
2. **Fill in your data** using the templates as a guide
3. **Keep the column names** exactly as shown
4. **Upload to the dashboard** via the sidebar upload interface

## Tips

- For **Suggested Semester**: Use format "Fall-1", "Spring-2", "Summer-3", etc.
  - The number indicates the year (1, 2, 3, 4...)
  - This enables the Degree Plan view to show semester-by-semester progression

- For **Prerequisites**: List course codes separated by commas
  - Example: "PBHL201, CHEM201" means students must complete both courses

- For **Student Status** in progress report:
  - Use simple codes: c, r, f, or leave blank
  - The system recognizes various formats (c, C, completed, Completed, etc.)

- **Multiple Sheets**: The progress report can have separate sheets for Required and Intensive courses
  - The system automatically merges them
  - If you don't have intensive courses, you can delete that sheet

## Support

If you encounter issues uploading files, check:
1. File format is .xlsx (for Excel) or .csv (for roster)
2. Required columns are present and spelled correctly
3. Data types are appropriate (numbers for IDs, text for names)
