import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
import calendar
from io import BytesIO

# Constants
TASK_DIR = "tasks"
TASK_PRIORITIES = ["High", "Medium", "Low"]
TASK_STATUSES = ["Pending", "In Progress", "Completed", "Overdue"]
TASK_CATEGORIES = ["Work", "Personal", "Urgent", "Meeting", "Project", "Other"]
REPORTS_DIR = "officer_reports"
ADDITIONAL_FOLDERS = ["Templates", "Summaries", "Archives", "Attachments", "Tasks"]

# Ensure necessary directories exist
os.makedirs(TASK_DIR, exist_ok=True)

def get_officer_names():
    """Get list of officer names from the reports directory"""
    try:
        officer_folders = [
            d for d in os.listdir(REPORTS_DIR) 
            if os.path.isdir(os.path.join(REPORTS_DIR, d))
            and d not in ADDITIONAL_FOLDERS
        ]
        return sorted(officer_folders)
    except Exception as e:
        st.error(f"Error loading officer names: {str(e)}")
        return []

def save_task(task_data):
    """Save task to JSON file"""
    task_id = task_data.get('task_id', datetime.now().strftime('%Y%m%d_%H%M%S'))
    filepath = os.path.join(TASK_DIR, f"task_{task_id}.json")
    with open(filepath, 'w') as f:
        json.dump(task_data, f, indent=4)
    return task_id

def load_tasks():
    """Load all tasks from JSON files"""
    tasks = []
    for filename in os.listdir(TASK_DIR):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(TASK_DIR, filename), 'r') as f:
                    task = json.load(f)
                    tasks.append(task)
            except Exception as e:
                st.error(f"Error loading task {filename}: {str(e)}")
    return tasks

def create_task_dashboard():
    """Create the main task management dashboard"""
    st.title("Task Management Dashboard")
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Task Overview", "Task List", "Team Collaboration", 
         "Calendar View", "Analytics & Reports"]
    )
    
    if page == "Task Overview":
        show_task_overview()
    elif page == "Task List":
        show_task_list()
    elif page == "Team Collaboration":
        show_team_collaboration()
    elif page == "Calendar View":
        show_calendar_view()
    elif page == "Analytics & Reports":
        show_analytics_reports()

def show_task_overview():
    """Display task overview with key metrics and charts"""
    st.header("Task Overview")
    
    # Load tasks
    tasks = load_tasks()
    if not tasks:
        st.info("No tasks found. Start by adding some tasks!")
        return
    
    df = pd.DataFrame(tasks)
    
    # Convert date strings to datetime
    df['due_date'] = pd.to_datetime(df['due_date'])
    df['created_date'] = pd.to_datetime(df['created_date'])
    
    # Key Metrics with improved styling
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_tasks = len(df)
        st.metric("📊 Total Tasks", total_tasks)
    
    with col2:
        pending_tasks = len(df[df['status'] == 'Pending'])
        st.metric("⏳ Pending Tasks", pending_tasks, 
                 delta=f"{(pending_tasks/total_tasks*100):.1f}%" if total_tasks > 0 else "0%")
    
    with col3:
        completed_tasks = len(df[df['status'] == 'Completed'])
        st.metric("✅ Completed Tasks", completed_tasks,
                 delta=f"{(completed_tasks/total_tasks*100):.1f}%" if total_tasks > 0 else "0%")
    
    with col4:
        overdue_tasks = len(df[(df['status'] != 'Completed') & 
                              (df['due_date'] < pd.Timestamp.now())])
        st.metric("⚠️ Overdue Tasks", overdue_tasks,
                 delta=f"{(overdue_tasks/total_tasks*100):.1f}%" if total_tasks > 0 else "0%",
                 delta_color="inverse")
    
    # Charts with improved styling
    col1, col2 = st.columns(2)
    
    with col1:
        # Task Status Distribution with custom colors
        status_counts = df['status'].value_counts()
        colors = {'Completed': '#28a745', 'Pending': '#ffc107', 
                 'In Progress': '#17a2b8', 'Overdue': '#dc3545'}
        
        fig_status = go.Figure(data=[go.Pie(
            labels=status_counts.index,
            values=status_counts.values,
            hole=.3,
            marker_colors=[colors.get(status, '#6c757d') for status in status_counts.index]
        )])
        fig_status.update_layout(
            title="Task Status Distribution",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        # Priority Distribution with custom colors
        priority_counts = df['priority'].value_counts()
        fig_priority = go.Figure(data=[go.Bar(
            x=priority_counts.index,
            y=priority_counts.values,
            marker_color=['#dc3545', '#ffc107', '#28a745'],
            text=priority_counts.values,
            textposition='auto',
        )])
        fig_priority.update_layout(
            title="Tasks by Priority",
            xaxis_title="Priority Level",
            yaxis_title="Number of Tasks",
            showlegend=False
        )
        st.plotly_chart(fig_priority, use_container_width=True)
    
    # Upcoming Deadlines with improved styling
    st.subheader("📅 Upcoming Deadlines")
    upcoming_tasks = df[
        (df['status'] != 'Completed') & 
        (df['due_date'] > pd.Timestamp.now()) & 
        (df['due_date'] <= pd.Timestamp.now() + pd.Timedelta(days=7))
    ].sort_values('due_date')
    
    if not upcoming_tasks.empty:
        # Create a more detailed table for upcoming tasks
        upcoming_display = upcoming_tasks[['title', 'due_date', 'priority', 'status', 'assigned_to']].copy()
        upcoming_display['due_date'] = upcoming_display['due_date'].dt.strftime('%Y-%m-%d')
        
        # Add priority indicators
        priority_indicators = {
            'High': '🔴',
            'Medium': '🟡',
            'Low': '🟢'
        }
        upcoming_display['priority'] = upcoming_display['priority'].map(
            lambda x: f"{priority_indicators.get(x, '⚪')} {x}")
        
        st.dataframe(
            upcoming_display,
            column_config={
                "title": st.column_config.TextColumn("Task Title", width="large"),
                "due_date": st.column_config.TextColumn("Due Date", width="medium"),
                "priority": st.column_config.TextColumn("Priority", width="medium"),
                "status": st.column_config.TextColumn("Status", width="medium"),
                "assigned_to": st.column_config.TextColumn("Assigned To", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Add visual indicators for urgent tasks
        urgent_tasks = upcoming_tasks[upcoming_tasks['priority'] == 'High']
        if not urgent_tasks.empty:
            st.warning(f"⚠️ {len(urgent_tasks)} high-priority tasks due soon!")
    else:
        st.info("🎉 No upcoming deadlines in the next 7 days")
    
    # Task Distribution by Assignee with improved styling
    st.subheader("👥 Tasks by Assignee")
    
    # Get task counts by assignee and status
    assignee_status = pd.crosstab(df['assigned_to'], df['status'])
    
    # Create stacked bar chart
    fig_assignee = go.Figure()
    
    status_colors = {
        'Completed': '#28a745',
        'In Progress': '#17a2b8',
        'Pending': '#ffc107',
        'Overdue': '#dc3545'
    }
    
    for status in TASK_STATUSES:
        if status in assignee_status.columns:
            fig_assignee.add_trace(go.Bar(
                name=status,
                x=assignee_status.index,
                y=assignee_status[status],
                marker_color=status_colors.get(status, '#6c757d')
            ))
    
    fig_assignee.update_layout(
        title="Task Distribution by Assignee",
        xaxis_title="Assignee",
        yaxis_title="Number of Tasks",
        barmode='stack',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    st.plotly_chart(fig_assignee, use_container_width=True)
    
    # Task Completion Timeline
    st.subheader("📈 Task Completion Timeline")
    
    # Create timeline of task completion
    df_completed = df[df['status'] == 'Completed'].copy()
    if not df_completed.empty:
        df_completed['completion_date'] = pd.to_datetime(df_completed['modified_date'] 
            if 'modified_date' in df_completed.columns else df_completed['created_date'])
        
        fig_timeline = go.Figure()
        
        # Add completed tasks line
        fig_timeline.add_trace(go.Scatter(
            x=df_completed['completion_date'],
            y=df_completed.groupby('completion_date').size().cumsum(),
            mode='lines+markers',
            name='Completed Tasks',
            line=dict(color='#28a745', width=2),
            marker=dict(size=8)
        ))
        
        fig_timeline.update_layout(
            title="Cumulative Task Completion",
            xaxis_title="Date",
            yaxis_title="Number of Completed Tasks",
            showlegend=True
        )
        
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("No completed tasks to show in timeline")

def show_task_list():
    """Display and manage task list"""
    st.header("Task List")
    
    # Get officer names
    officer_names = get_officer_names()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.multiselect("Status", TASK_STATUSES)
    with col2:
        priority_filter = st.multiselect("Priority", TASK_PRIORITIES)
    with col3:
        category_filter = st.multiselect("Category", TASK_CATEGORIES)
    
    # Add New Task button
    if st.button("➕ Add New Task"):
        st.session_state.show_task_form = True
        st.session_state.editing_task = None
        st.session_state.new_assignee = False
    
    # Task creation/editing form
    if st.session_state.show_task_form:
        with st.form("task_form"):
            st.subheader("Create New Task" if not st.session_state.get('editing_task') else "Edit Task")
            
            # Get existing task data if editing
            editing_task = None
            if st.session_state.get('editing_task'):
                editing_task = next((task for task in load_tasks() 
                                   if task['task_id'] == st.session_state.editing_task), None)
            
            title = st.text_input("Task Title", value=editing_task['title'] if editing_task else "")
            description = st.text_area("Description", value=editing_task['description'] if editing_task else "")
            
            col1, col2 = st.columns(2)
            with col1:
                priority = st.selectbox("Priority", TASK_PRIORITIES, 
                                      index=TASK_PRIORITIES.index(editing_task['priority']) if editing_task else 0)
                category = st.selectbox("Category", TASK_CATEGORIES,
                                      index=TASK_CATEGORIES.index(editing_task['category']) if editing_task else 0)
            with col2:
                status = st.selectbox("Status", TASK_STATUSES,
                                    index=TASK_STATUSES.index(editing_task['status']) if editing_task else 0)
                due_date = st.date_input("Due Date", 
                    value=datetime.strptime(editing_task['due_date'], '%Y-%m-%d').date() if editing_task else datetime.now())
            
            # Officer assignment with option to add new
            assign_options = ["Select Officer...", "+ Add New Assignee"] + officer_names
            if editing_task and editing_task['assigned_to'] in officer_names:
                default_index = officer_names.index(editing_task['assigned_to']) + 2
            else:
                default_index = 0
            
            assigned_to = st.selectbox(
                "Assign To",
                assign_options,
                index=default_index
            )
            
            # Show input field for new assignee if selected
            new_assignee_name = None
            if assigned_to == "+ Add New Assignee":
                new_assignee_name = st.text_input("Enter New Assignee Name")
                if new_assignee_name:
                    # Create new officer directory
                    new_officer_dir = os.path.join(REPORTS_DIR, new_assignee_name)
                    if not os.path.exists(new_officer_dir):
                        os.makedirs(new_officer_dir)
            
            submitted = st.form_submit_button("Update Task" if editing_task else "Create Task")
            if submitted:
                if not title:
                    st.error("Please enter a task title")
                elif assigned_to == "Select Officer..." and not new_assignee_name:
                    st.error("Please select an assignee or create a new one")
                else:
                    final_assignee = new_assignee_name if new_assignee_name else assigned_to
                    task_data = {
                        "task_id": editing_task['task_id'] if editing_task else datetime.now().strftime('%Y%m%d_%H%M%S'),
                        "title": title,
                        "description": description,
                        "priority": priority,
                        "category": category,
                        "status": status,
                        "due_date": due_date.strftime("%Y-%m-%d"),
                        "assigned_to": final_assignee,
                        "created_date": editing_task['created_date'] if editing_task else datetime.now().strftime("%Y-%m-%d"),
                        "comments": editing_task.get('comments', []) if editing_task else []
                    }
                    save_task(task_data)
                    st.success(f"Task {'updated' if editing_task else 'created'} successfully and assigned to {final_assignee}!")
                    st.session_state.show_task_form = False
                    st.session_state.editing_task = None
                    st.rerun()
    
    # Load and display tasks
    tasks = load_tasks()
    if not tasks:
        st.info("No tasks found. Create your first task!")
        return
    
    # Apply filters
    filtered_tasks = tasks
    if status_filter:
        filtered_tasks = [t for t in filtered_tasks if t['status'] in status_filter]
    if priority_filter:
        filtered_tasks = [t for t in filtered_tasks if t['priority'] in priority_filter]
    if category_filter:
        filtered_tasks = [t for t in filtered_tasks if t['category'] in category_filter]
    
    # Display tasks
    for task in filtered_tasks:
        with st.expander(f"{task['title']} ({task['status']})"):
            col1, col2, col3 = st.columns([2,1,1])
            with col1:
                st.write(f"**Description:** {task['description']}")
                st.write(f"**Assigned to:** {task['assigned_to']}")
            with col2:
                st.write(f"**Priority:** {task['priority']}")
                st.write(f"**Category:** {task['category']}")
            with col3:
                st.write(f"**Due Date:** {task['due_date']}")
                st.write(f"**Created:** {task['created_date']}")
            
            # Action buttons
            col1, col2, col3 = st.columns([1,1,2])
            with col1:
                if st.button("🖊️ Edit", key=f"edit_{task['task_id']}"):
                    st.session_state.editing_task = task['task_id']
                    st.session_state.show_task_form = True
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Delete", key=f"delete_{task['task_id']}"):
                    try:
                        os.remove(os.path.join(TASK_DIR, f"task_{task['task_id']}.json"))
                        st.success("Task deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting task: {str(e)}")
            
            # Update status
            new_status = st.selectbox(
                "Update Status",
                TASK_STATUSES,
                index=TASK_STATUSES.index(task['status']),
                key=f"status_{task['task_id']}"
            )
            
            if new_status != task['status']:
                task['status'] = new_status
                save_task(task)
                st.success("Status updated!")
                st.rerun()
            
            # Comments section
            st.write("**Comments:**")
            for comment in task.get('comments', []):
                st.text(f"{comment['date']} - {comment['author']}: {comment['text']}")
            
            # Add comment
            new_comment = st.text_input("Add comment", key=f"comment_{task['task_id']}")
            if st.button("Add Comment", key=f"btn_{task['task_id']}"):
                if new_comment:
                    if 'comments' not in task:
                        task['comments'] = []
                    task['comments'].append({
                        'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'author': "User",  # You can modify this to use actual user name
                        'text': new_comment
                    })
                    save_task(task)
                    st.success("Comment added!")
                    st.rerun()

def show_team_collaboration():
    """Display team collaboration features"""
    st.header("Team Collaboration")
    
    # Load tasks
    tasks = load_tasks()
    if not tasks:
        st.info("No tasks available for team collaboration")
        return
    
    df = pd.DataFrame(tasks)
    
    # Team Overview
    st.subheader("Team Overview")
    team_members = df['assigned_to'].unique()
    
    for member in team_members:
        if member:  # Skip empty assignments
            member_tasks = df[df['assigned_to'] == member]
            with st.expander(f"📊 {member}'s Dashboard"):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Tasks", len(member_tasks))
                with col2:
                    completed = len(member_tasks[member_tasks['status'] == 'Completed'])
                    st.metric("Completed", completed)
                with col3:
                    pending = len(member_tasks[member_tasks['status'] == 'Pending'])
                    st.metric("Pending", pending)
                with col4:
                    completion_rate = (completed / len(member_tasks) * 100) if len(member_tasks) > 0 else 0
                    st.metric("Completion Rate", f"{completion_rate:.1f}%")
                
                # Show member's tasks
                st.write("Recent Tasks:")
                recent_tasks = member_tasks.sort_values('due_date', ascending=False).head()
                st.dataframe(
                    recent_tasks[['title', 'status', 'due_date', 'priority']],
                    use_container_width=True
                )

def show_calendar_view():
    """Display calendar view of tasks with interactive calendar"""
    st.header("Calendar View")
    
    # Calendar type selection
    view_type = st.radio("Select View", ["Monthly", "Weekly", "Daily"], horizontal=True)
    
    # Load tasks
    tasks = load_tasks()
    if not tasks:
        st.info("No tasks scheduled")
        return
    
    df = pd.DataFrame(tasks)
    df['due_date'] = pd.to_datetime(df['due_date'])
    
    if view_type == "Daily":
        selected_date = st.date_input("Select Date", datetime.now())
        daily_tasks = df[df['due_date'].dt.date == selected_date]
        
        # Create a timeline for the day
        st.subheader(f"Schedule for {selected_date.strftime('%B %d, %Y')}")
        
        # Morning, Afternoon, Evening sections
        sections = ["Morning (6 AM - 12 PM)", "Afternoon (12 PM - 5 PM)", "Evening (5 PM - 11 PM)"]
        for section in sections:
            with st.expander(section, expanded=True):
                if not daily_tasks.empty:
                    for _, task in daily_tasks.iterrows():
                        st.markdown(f"""
                        🎯 **{task['title']}** ({task['status']})
                        - Priority: {task['priority']}
                        - Category: {task['category']}
                        - Assigned to: {task['assigned_to']}
                        """)
                else:
                    st.info("No tasks scheduled")
    
    elif view_type == "Weekly":
        selected_date = st.date_input("Select Week (Starting Date)", datetime.now())
        week_start = selected_date - timedelta(days=selected_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        weekly_tasks = df[
            (df['due_date'].dt.date >= week_start) & 
            (df['due_date'].dt.date <= week_end)
        ]
        
        # Create weekly calendar grid
        st.subheader(f"Week of {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}")
        
        # Create 7 columns for each day
        cols = st.columns(7)
        today = datetime.now().date()
        
        for i, day in enumerate(range(7)):
            current_date = week_start + timedelta(days=day)
            day_tasks = weekly_tasks[weekly_tasks['due_date'].dt.date == current_date]
            
            with cols[i]:
                # Highlight current day
                if current_date == today:  # Fixed comparison
                    st.markdown(f"### 📅 {current_date.strftime('%a')}")
                    st.markdown(f"**{current_date.strftime('%d')}**")
                else:
                    st.markdown(f"### {current_date.strftime('%a')}")
                    st.markdown(f"{current_date.strftime('%d')}")
                
                # Display tasks for the day
                if not day_tasks.empty:
                    for _, task in day_tasks.iterrows():
                        priority_color = {
                            "High": "🔴",
                            "Medium": "🟡",
                            "Low": "🟢"
                        }.get(task['priority'], "⚪")
                        
                        st.markdown(f"""
                        {priority_color} **{task['title']}**
                        - {task['status']}
                        """)
    
    else:  # Monthly view
        selected_date = st.date_input("Select Month", datetime.now())
        month_start = selected_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        monthly_tasks = df[
            (df['due_date'].dt.date >= month_start) & 
            (df['due_date'].dt.date <= month_end)
        ]
        
        # Create calendar grid
        st.subheader(f"Calendar - {selected_date.strftime('%B %Y')}")
        
        # Get calendar data
        cal = calendar.monthcalendar(selected_date.year, selected_date.month)
        
        # Create calendar header
        week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        header_cols = st.columns(7)
        for i, day in enumerate(week_days):
            with header_cols[i]:
                st.markdown(f"**{day}**", help="Click to view tasks")
        
        # Create calendar grid
        today = datetime.now().date()
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day != 0:
                        current_date = datetime(selected_date.year, selected_date.month, day).date()
                        day_tasks = monthly_tasks[monthly_tasks['due_date'].dt.date == current_date]
                        
                        # Highlight current day
                        if current_date == today:  # Fixed comparison
                            st.markdown(f"### 📅 {day}")
                        else:
                            st.markdown(f"### {day}")
                        
                        # Show tasks for the day
                        if not day_tasks.empty:
                            with st.expander(f"{len(day_tasks)} tasks"):
                                for _, task in day_tasks.iterrows():
                                    priority_color = {
                                        "High": "🔴",
                                        "Medium": "🟡",
                                        "Low": "🟢"
                                    }.get(task['priority'], "⚪")
                                    
                                    st.markdown(f"""
                                    {priority_color} **{task['title']}**
                                    - Status: {task['status']}
                                    - Category: {task['category']}
                                    """)
    
    # Task Statistics for the selected period
    st.subheader("Task Statistics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_tasks = len(df)
        completed_tasks = len(df[df['status'] == 'Completed'])
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        st.metric("Completion Rate", f"{completion_rate:.1f}%")
    
    with col2:
        overdue_tasks = len(df[
            (df['status'] != 'Completed') & 
            (df['due_date'] < datetime.now())
        ])
        st.metric("Overdue Tasks", overdue_tasks)
    
    with col3:
        upcoming_tasks = len(df[
            (df['status'] != 'Completed') & 
            (df['due_date'] > datetime.now()) & 
            (df['due_date'] <= datetime.now() + timedelta(days=7))
        ])
        st.metric("Upcoming Tasks (7 days)", upcoming_tasks)

def show_analytics_reports():
    """Display analytics and generate reports"""
    st.header("Analytics & Reports")
    
    # Load tasks
    tasks = load_tasks()
    if not tasks:
        st.info("No data available for analysis")
        return
    
    df = pd.DataFrame(tasks)
    df['due_date'] = pd.to_datetime(df['due_date'])
    df['created_date'] = pd.to_datetime(df['created_date'])
    
    # Time period selection
    time_period = st.selectbox(
        "Select Time Period",
        ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"]
    )
    
    # Filter data based on time period
    end_date = datetime.now()
    if time_period == "Last 7 Days":
        start_date = end_date - timedelta(days=7)
    elif time_period == "Last 30 Days":
        start_date = end_date - timedelta(days=30)
    elif time_period == "Last 90 Days":
        start_date = end_date - timedelta(days=90)
    else:
        start_date = df['created_date'].min()
    
    filtered_df = df[
        (df['created_date'] >= start_date) & 
        (df['created_date'] <= end_date)
    ]
    
    # Key Metrics
    st.subheader("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_tasks = len(filtered_df)
        st.metric("Total Tasks", total_tasks)
    
    with col2:
        completed_tasks = len(filtered_df[filtered_df['status'] == 'Completed'])
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        st.metric("Completion Rate", f"{completion_rate:.1f}%")
    
    with col3:
        avg_completion_time = filtered_df[filtered_df['status'] == 'Completed'].apply(
            lambda x: (pd.to_datetime(x['due_date']) - pd.to_datetime(x['created_date'])).days,
            axis=1
        ).mean()
        st.metric("Avg. Completion Time", f"{avg_completion_time:.1f} days")
    
    with col4:
        overdue_tasks = len(filtered_df[
            (filtered_df['status'] != 'Completed') & 
            (filtered_df['due_date'] < datetime.now())
        ])
        st.metric("Overdue Tasks", overdue_tasks)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Task Status Trend
        status_trend = filtered_df.groupby([
            filtered_df['created_date'].dt.strftime('%Y-%m-%d'), 'status'
        ]).size().unstack(fill_value=0)
        
        fig_trend = go.Figure()
        for status in status_trend.columns:
            fig_trend.add_trace(go.Scatter(
                x=status_trend.index,
                y=status_trend[status],
                name=status,
                mode='lines+markers'
            ))
        
        fig_trend.update_layout(
            title="Task Status Trend",
            xaxis_title="Date",
            yaxis_title="Number of Tasks"
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    
    with col2:
        # Priority Distribution
        priority_dist = filtered_df['priority'].value_counts()
        fig_priority = go.Figure(data=[go.Pie(
            labels=priority_dist.index,
            values=priority_dist.values,
            hole=.3
        )])
        fig_priority.update_layout(title="Task Priority Distribution")
        st.plotly_chart(fig_priority, use_container_width=True)
    
    # Export Options
    st.subheader("Export Reports")
    export_format = st.selectbox("Select Format", ["Excel", "CSV", "PDF"])
    
    if st.button("Generate Report"):
        if export_format in ["Excel", "CSV"]:
            # Prepare data for export
            export_df = filtered_df[[
                'title', 'description', 'status', 'priority',
                'category', 'assigned_to', 'created_date', 'due_date'
            ]]
            
            if export_format == "Excel":
                # Create Excel file
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    export_df.to_excel(writer, sheet_name='Tasks', index=False)
                    
                    # Get workbook and worksheet objects
                    workbook = writer.book
                    worksheet = writer.sheets['Tasks']
                    
                    # Add formats
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    
                    # Apply formats
                    for col_num, value in enumerate(export_df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                        worksheet.set_column(col_num, col_num, 15)
                
                st.download_button(
                    label="Download Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"task_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            
            else:  # CSV
                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV Report",
                    data=csv,
                    file_name=f"task_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        else:  # PDF
            st.warning("PDF export functionality coming soon!")

# Initialize session state for task form
if 'show_task_form' not in st.session_state:
    st.session_state.show_task_form = False

# Add to your session state initialization at the top of the file
if 'editing_task' not in st.session_state:
    st.session_state.editing_task = None

# Main app
if __name__ == "__main__":
    st.set_page_config(
        page_title="Task Management Dashboard",
        page_icon="📋",
        layout="wide"
    )
    create_task_dashboard() 