import json
import streamlit as st
import json
import pandas as pd
import datetime
import io
import os
from collections import defaultdict
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Google Calendar API scope
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def authenticate_google():
    import json
    creds = None
    token_path = 'token.json'
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = json.loads(st.secrets["GOOGLE_CLIENT_SECRET"])
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
    return creds

def upload_tasks_to_calendar(tasks):
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)
    calendar_id = 'primary'

    for task in tasks:
        try:
            start_time = datetime.datetime.strptime(task['start'], '%H:%M')
            end_time = datetime.datetime.strptime(task['end'], '%H:%M')
            task_date = task.get('date', datetime.date.today())
            if isinstance(task_date, str):
                task_date = datetime.datetime.strptime(task_date, "%Y-%m-%d").date()
        except Exception:
            st.error(f"Time or Date format error in task: {task['task']}")
            continue

        start = datetime.datetime.combine(task_date, start_time.time())
        end = datetime.datetime.combine(task_date, end_time.time())

        event = {
            'summary': f"{task['task']} (Priority: {task['priority']}, Category: {task['category']})",
            'start': {'dateTime': start.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'UTC'},
            'description': f"Duration: {task['duration']:.2f} hours\nCategory: {task['category']}\nPriority: {task['priority']}"
        }
        service.events().insert(calendarId=calendar_id, body=event).execute()
    st.success("✅ Tasks uploaded to Google Calendar successfully!")

def schedule_tasks(task_list, work_start, work_end, break_duration_minutes, break_frequency):
    sorted_tasks = sorted(task_list, key=lambda x: x['priority'])
    scheduled = []
    current_time = datetime.datetime.combine(datetime.date.today(), work_start)
    work_end_dt = datetime.datetime.combine(datetime.date.today(), work_end)
    break_td = datetime.timedelta(minutes=break_duration_minutes)

    for i, task in enumerate(sorted_tasks):
        duration_td = datetime.timedelta(hours=task['duration'])
        end_time = current_time + duration_td

        if end_time > work_end_dt:
            st.warning(f"Task '{task['name']}' cannot fit in the working time.")
            break

        scheduled.append({
            'task': task['name'],
            'start': current_time.strftime('%H:%M'),
            'end': end_time.strftime('%H:%M'),
            'duration': task['duration'],
            'priority': task['priority'],
            'category': task['category'],
            'date': task.get('date', datetime.date.today())
        })
        current_time = end_time

        if break_duration_minutes > 0 and break_frequency > 0 and (i + 1) % break_frequency == 0 and i < len(sorted_tasks) - 1:
            break_end = current_time + break_td
            if break_end > work_end_dt:
                break
            scheduled.append({
                'task': 'Break',
                'start': current_time.strftime('%H:%M'),
                'end': break_end.strftime('%H:%M'),
                'duration': break_duration_minutes / 60,
                'priority': None,
                'category': 'Break',
                'date': datetime.date.today()
            })
            current_time = break_end
    return scheduled

CATEGORY_COLORS = {
    'Work': '#FFD700',
    'Study': '#90EE90',
    'Exercise': '#ADD8E6',
    'Break': '#D3D3D3',
    'Other': '#FFB6C1'
}

def main():
    st.title("Ultimate Smart Scheduler with Google Calendar Integration")

    st.sidebar.header("Select Date to Manage Tasks")
    date_option = st.sidebar.radio("Choose Date:", options=["Today", "Tomorrow", "Pick a Date"])
    if date_option == "Today":
        selected_date = datetime.date.today()
    elif date_option == "Tomorrow":
        selected_date = datetime.date.today() + datetime.timedelta(days=1)
    else:
        selected_date = st.sidebar.date_input("Pick a Date", datetime.date.today())
    st.sidebar.markdown("---")

    st.sidebar.header("Scheduler Settings")
    work_start = st.sidebar.time_input("Work Start Time", datetime.time(9, 0))
    work_end = st.sidebar.time_input("Work End Time", datetime.time(18, 0))
    break_duration_minutes = st.sidebar.number_input("Break Duration (minutes)", min_value=0, max_value=60, value=10, step=1)
    break_frequency = st.sidebar.number_input("Insert Break After Every N Tasks", min_value=1, max_value=10, value=3, step=1)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Task Categories")
    categories = st.sidebar.text_area("Add categories (comma separated)", "Work, Study, Exercise, Break, Other").split(",")
    categories = [c.strip() for c in categories if c.strip()]

    st.header(f"Add / Edit Tasks for {selected_date.strftime('%Y-%m-%d')}")
    task_count = st.number_input("Number of tasks to add", min_value=1, step=1)

    tasks = []
    for i in range(task_count):
        with st.expander(f"Task {i + 1} Details", expanded=True):
            task_name = st.text_input(f"Name", key=f"name_{i}")
            task_duration = st.number_input(f"Duration (hours, e.g. 1.5)", min_value=0.01, step=0.01, format="%.2f", key=f"duration_{i}")
            task_priority = st.number_input(f"Priority (1 = highest)", min_value=1, max_value=10, value=5, step=1, key=f"priority_{i}")
            task_category = st.selectbox(f"Category", options=categories, index=0, key=f"category_{i}")
            task_date = selected_date
            if task_name and task_duration:
                tasks.append({
                    'name': task_name,
                    'duration': task_duration,
                    'priority': task_priority,
                    'category': task_category,
                    'date': task_date
                })

    if st.button("Generate Schedule"):
        if not tasks:
            st.error("Add at least one task to schedule.")
        elif work_start >= work_end:
            st.error("Work start time must be before work end time.")
        else:
            schedule = schedule_tasks(tasks, work_start, work_end, break_duration_minutes, break_frequency)
            schedule = [t for t in schedule if t.get('date', datetime.date.today()) == selected_date]
            st.session_state['schedule'] = schedule

    if 'schedule' in st.session_state:
        schedule = st.session_state['schedule']
        df_schedule = pd.DataFrame(schedule)

        def color_row(row):
            color = CATEGORY_COLORS.get(row['category'], '#FFFFFF')
            return ['background-color: ' + color] * len(row)

        st.subheader("Scheduled Tasks")
        st.dataframe(df_schedule.style.apply(color_row, axis=1), use_container_width=True)

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_schedule.to_excel(writer, index=False, sheet_name='Schedule')
            workbook = writer.book
            worksheet = writer.sheets['Schedule']
            for i, row in df_schedule.iterrows():
                color = CATEGORY_COLORS.get(row['category'], '#FFFFFF')
                fmt = workbook.add_format({'bg_color': color})
                worksheet.set_row(i+1, None, fmt)
        excel_data = excel_buffer.getvalue()
        st.download_button("Download Schedule Excel", data=excel_data, file_name="schedule.xlsx", mime="application/vnd.ms-excel")

        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for i, row in df_schedule.iterrows():
                prio = row['priority'] if row['priority'] is not None else 'N/A'
                date_str = row['date'] if not isinstance(row['date'], datetime.date) else row['date'].strftime('%Y-%m-%d')
                line = f"{row['task']} ({row['category']}) - {row['start']} to {row['end']} on {date_str} ({row['duration']:.2f} hrs, Priority: {prio})"
                pdf.cell(200, 10, txt=line, ln=True)
            pdf.output("schedule.pdf")
            with open("schedule.pdf", "rb") as f:
                pdf_data = f.read()
            st.download_button("Download Schedule PDF", data=pdf_data, file_name="schedule.pdf", mime="application/pdf")
        except ImportError:
            st.warning("Install 'fpdf' package for PDF export.")

        if st.button("Upload Tasks to Google Calendar"):
            try:
                upload_tasks_to_calendar(schedule)
            except Exception as e:
                st.error(f"Authentication or upload failed: {e}")

if __name__ == "__main__":
    main()
