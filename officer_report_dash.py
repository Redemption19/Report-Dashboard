import streamlit as st
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import shutil
from io import BytesIO, StringIO
import plotly.graph_objects as go
import time


# Add these imports at the top of your file
from task_management_dash import (
    create_task_dashboard,
    save_task,
    load_tasks,
    TASK_PRIORITIES,
    TASK_STATUSES,
    TASK_CATEGORIES
)

ALLOWED_ATTACHMENT_TYPES = ['png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xlsx', 'csv']

# Configuration and Constants
REPORTS_DIR = "officer_reports"
REPORT_TYPES = ["Daily", "Weekly"]
ADDITIONAL_FOLDERS = ["Templates", "Summaries", "Archives", "Attachments"]

# Add new constants
TEMPLATE_EXTENSIONS = ['.json', '.txt', '.md']
ALLOWED_ATTACHMENT_TYPES = ['png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xlsx', 'csv']
AUTO_ARCHIVE_DAYS = 30  # Reports older than this will be auto-archived

# Add to your existing constants
TASK_DIR = os.path.join(REPORTS_DIR, "Tasks")
TASK_PRIORITIES = ["High", "Medium", "Low"]
TASK_STATUSES = ["Pending", "In Progress", "Completed", "Overdue"]
TASK_CATEGORIES = ["Work", "Personal", "Urgent", "Meeting", "Project", "Other"]

def init_folders():
    """Initialize necessary folders if they don't exist"""
    # Create main reports directory
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    
    # Create additional organizational folders
    folders_to_create = ADDITIONAL_FOLDERS + ["Tasks"]
    for folder in folders_to_create:
        folder_path = os.path.join(REPORTS_DIR, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            
    # Create a README file explaining the folder structure
    readme_path = os.path.join(REPORTS_DIR, "README.txt")
    if not os.path.exists(readme_path):
        with open(readme_path, 'w') as f:
            f.write("""Folder Structure:
- Templates: Store report templates
- Summaries: Store generated report summaries
- Archives: Store archived or old reports
- Attachments: Store any supplementary files
- [Officer Names]: Individual officer report folders are created automatically
""")

def save_report(officer_name, report_data):
    """Save report to JSON file in officer's folder"""
    # Create main officer directory if it doesn't exist
    officer_dir = os.path.join(REPORTS_DIR, officer_name)
    if not os.path.exists(officer_dir):
        os.makedirs(officer_dir)
    
    # Create filename with date and type
    filename = f"{report_data['date']}_{report_data['type']}.json"
    filepath = os.path.join(officer_dir, filename)
    
    # Save the report
    with open(filepath, 'w') as f:
        json.dump(report_data, f, indent=4)
    return filepath

def load_reports(officer_name=None):
    """Load all reports or reports for a specific officer"""
    reports = []
    
    if officer_name:
        # Check the direct officer directory
        officer_dir = os.path.join(REPORTS_DIR, officer_name)
        if os.path.exists(officer_dir):
            # Look for reports in the main directory
            for filename in os.listdir(officer_dir):
                if filename.endswith('.json'):
                    try:
                        filepath = os.path.join(officer_dir, filename)
                        with open(filepath, 'r') as f:
                            report_data = json.load(f)
                            # Ensure officer_name is in the report data
                            report_data['officer_name'] = officer_name
                            reports.append(report_data)
                    except Exception as e:
                        st.warning(f"Error reading report {filename}: {str(e)}")
                        continue
            
            # Also check the reports subfolder if it exists
            reports_subdir = os.path.join(officer_dir, 'reports')
            if os.path.exists(reports_subdir):
                for filename in os.listdir(reports_subdir):
                    if filename.endswith('.json'):
                        try:
                            filepath = os.path.join(reports_subdir, filename)
                            with open(filepath, 'r') as f:
                                report_data = json.load(f)
                                # Ensure officer_name is in the report data
                                report_data['officer_name'] = officer_name
                                reports.append(report_data)
                        except Exception as e:
                            st.warning(f"Error reading report {filename}: {str(e)}")
                            continue
    else:
        # Load reports for all officers
        for officer_folder in os.listdir(REPORTS_DIR):
            if officer_folder not in ADDITIONAL_FOLDERS and os.path.isdir(os.path.join(REPORTS_DIR, officer_folder)):
                reports.extend(load_reports(officer_folder))
    
    return reports

def load_template(template_name):
    """Load a report template from the Templates folder"""
    template_path = os.path.join(REPORTS_DIR, "Templates", template_name)
    try:
        with open(template_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading template: {str(e)}")
        return None

def save_template(template_name, template_data):
    """Save a new template to the Templates folder"""
    template_path = os.path.join(REPORTS_DIR, "Templates", template_name)
    try:
        with open(template_path, 'w') as f:
            json.dump(template_data, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error saving template: {str(e)}")
        return False

def generate_summary(start_date=None, end_date=None, officer_name=None):
    """Generate a summary report for the specified period"""
    # Load all reports using load_reports function
    if officer_name and officer_name != "All Officers":
        reports = load_reports(officer_name)
    else:
        reports = load_reports()
    
    if not reports:
        return None
    
    df = pd.DataFrame(reports)
    df['date'] = pd.to_datetime(df['date'])
    
    if start_date:
        df = df[df['date'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['date'] <= pd.to_datetime(end_date)]
    
    # Convert recent reports to serializable format
    recent_reports = df.sort_values('date', ascending=False).head(5)
    recent_reports_list = []
    for _, report in recent_reports.iterrows():
        report_dict = report.to_dict()
        # Convert timestamp to string
        report_dict['date'] = report_dict['date'].strftime('%Y-%m-%d')
        recent_reports_list.append(report_dict)
    
    summary = {
        'period': f"{start_date} to {end_date}" if start_date and end_date else "All time",
        'total_reports': len(df),
        'officers': df['officer_name'].nunique(),
        'companies': df['company_name'].nunique(),
        'report_types': df['type'].value_counts().to_dict(),
        'officer_activity': df['officer_name'].value_counts().to_dict(),
        'company_distribution': df['company_name'].value_counts().to_dict(),
        'recent_reports': recent_reports_list
    }
    
    return summary

def auto_archive_old_reports():
    """Automatically archive reports older than AUTO_ARCHIVE_DAYS"""
    today = datetime.now()
    archive_before = today - timedelta(days=AUTO_ARCHIVE_DAYS)
    
    for officer in os.listdir(REPORTS_DIR):
        if officer not in ADDITIONAL_FOLDERS and os.path.isdir(os.path.join(REPORTS_DIR, officer)):
            officer_dir = os.path.join(REPORTS_DIR, officer)
            for report_file in os.listdir(officer_dir):
                if report_file.endswith('.json'):
                    report_path = os.path.join(officer_dir, report_file)
                    try:
                        with open(report_path, 'r') as f:
                            report_data = json.load(f)
                        report_date = datetime.strptime(report_data['date'], '%Y-%m-%d')
                        
                        if report_date < archive_before:
                            # Create archive structure
                            year_month = report_date.strftime('%Y_%m')
                            archive_dir = os.path.join(REPORTS_DIR, "Archives", year_month, officer)
                            os.makedirs(archive_dir, exist_ok=True)
                            
                            # Move file to archive
                            shutil.move(report_path, os.path.join(archive_dir, report_file))
                    except Exception as e:
                        st.error(f"Error archiving {report_file}: {str(e)}")

def report_form():
    """Enhanced report form with template selection and file attachments"""
    st.header("Submit New Report")
    
    # Template selection
    template_files = [f for f in os.listdir(os.path.join(REPORTS_DIR, "Templates")) 
                     if any(f.endswith(ext) for ext in TEMPLATE_EXTENSIONS)]
    
    use_template = st.checkbox("Use a template")
    if use_template and template_files:
        selected_template = st.selectbox("Select Template", template_files)
        template_data = load_template(selected_template)
        if template_data:
            # Pre-fill form with template data
            report_type = st.selectbox("Report Type", REPORT_TYPES, 
                                     index=REPORT_TYPES.index(template_data.get('type', REPORT_TYPES[0])))
            officer_name = st.text_input("Officer Name", value=template_data.get('officer_name', ''))
            company_name = st.text_input("Company Name", value=template_data.get('company_name', ''))
            tasks = st.text_area("Tasks Completed", value=template_data.get('tasks', ''))
            challenges = st.text_area("Challenges Encountered", value=template_data.get('challenges', ''))
            solutions = st.text_area("Proposed Solutions", value=template_data.get('solutions', ''))
    else:
        # Regular form
        report_type = st.selectbox("Report Type", REPORT_TYPES)
        officer_name = st.text_input("Officer Name")
        company_name = st.text_input("Company Name")
        tasks = st.text_area("Tasks Completed")
        challenges = st.text_area("Challenges Encountered")
        solutions = st.text_area("Proposed Solutions")
    
    # File attachments
    st.subheader("Attachments")
    try:
        uploaded_files = st.file_uploader("Upload attachments", 
                                        accept_multiple_files=True,
                                        type=ALLOWED_ATTACHMENT_TYPES)
    except Exception as e:
        st.error(f"Error uploading files: {str(e)}")
    
    if st.button("Submit Report"):
        if officer_name and tasks:
            # Save attachments
            attachment_paths = []
            if uploaded_files:
                for file in uploaded_files:
                    attachment_dir = os.path.join(REPORTS_DIR, "Attachments", 
                                                officer_name, datetime.now().strftime('%Y_%m_%d'))
                    os.makedirs(attachment_dir, exist_ok=True)
                    file_path = os.path.join(attachment_dir, file.name)
                    with open(file_path, 'wb') as f:
                        f.write(file.getbuffer())
                    attachment_paths.append(file_path)
            
            report_data = {
                "type": report_type,
                "officer_name": officer_name,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "company_name": company_name,
                "total_schedule_files": 0,  # Updated field
                "total_years": 0,          # New field
                "tasks": tasks,
                "challenges": challenges,
                "solutions": solutions,
                "attachments": attachment_paths
            }
            
            try:
                save_report(officer_name, report_data)
                st.success("Report and attachments saved successfully!")
                
                # Save as template option
                if st.checkbox("Save this as a template?"):
                    template_name = st.text_input("Template name (with .json extension):")
                    if template_name and template_name.endswith('.json'):
                        if save_template(template_name, report_data):
                            st.success("Template saved successfully!")
                
                # Auto-archive old reports
                auto_archive_old_reports()
                
                # Create related tasks
                if st.checkbox("Create related tasks?"):
                    st.subheader("Create Related Tasks")
                    task_title = st.text_input("Task Title")
                    task_priority = st.selectbox("Priority", TASK_PRIORITIES)
                    task_category = st.selectbox("Category", TASK_CATEGORIES)
                    due_date = st.date_input("Due Date")
                    
                    if st.button("Add Task"):
                        task_data = {
                            "title": task_title,
                            "priority": task_priority,
                            "category": task_category,
                            "status": "Pending",
                            "due_date": due_date.strftime("%Y-%m-%d"),
                            "assigned_to": officer_name,
                            "linked_report": report_data.get("report_id"),
                            "created_date": datetime.now().strftime("%Y-%m-%d")
                        }
                        save_task(task_data)
                        st.success("Task created and linked to report!")
            except Exception as e:
                st.error(f"Error saving report: {str(e)}")
        else:
            st.warning("Please fill in all required fields.")

def view_reports():
    """View reports with charts and proper folder filtering"""
    st.header("View Reports")
    
    # Define system folders to exclude
    SYSTEM_FOLDERS = {'Summaries', 'Archive', 'Attachments', 'Templates', '__pycache__'}
    
    # Get filtered list of officer folders
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d)) 
        and d not in SYSTEM_FOLDERS
        and not d.startswith('.')
        and not d.startswith('__')
    ]
    
    # Filter controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_officer = st.selectbox(
            "Select Officer",
            ["All Officers"] + sorted(officer_folders)
        )
    
    with col2:
        report_type = st.selectbox(
            "Report Type",
            ["All Types"] + REPORT_TYPES
        )
    
    with col3:
        sort_order = st.selectbox(
            "Sort By",
            ["Newest First", "Oldest First"]
        )

    # Load reports using the load_reports function
    if selected_officer != "All Officers":
        all_reports = load_reports(selected_officer)
    else:
        all_reports = load_reports()  # This will load all reports

    # Filter by report type if selected
    if report_type != "All Types":
        all_reports = [r for r in all_reports if r.get('type') == report_type]

    if all_reports:
        # Convert to DataFrame
        df = pd.DataFrame(all_reports)
        
        # Convert date strings to datetime for sorting
        df['date'] = pd.to_datetime(df['date'])
        
        # Sort based on user selection
        df = df.sort_values('date', ascending=(sort_order == "Oldest First"))
        
        # Statistics Section
        st.subheader("Report Statistics")
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        
        with stat_col1:
            st.metric("Total Reports", len(df))
        with stat_col2:
            unique_companies = len(df['company_name'].unique())
            st.metric("Companies", unique_companies)
        with stat_col3:
            unique_officers = len(df['officer_name'].unique())
            st.metric("Officers", unique_officers)
        with stat_col4:
            report_types = len(df['type'].unique())
            st.metric("Report Types", report_types)

        # Charts Section
        st.subheader("Report Analysis")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            # Bar Chart: Report Types Distribution
            type_counts = df['type'].value_counts()
            bar_fig = go.Figure(data=[go.Bar(
                x=type_counts.index,
                y=type_counts.values,
                marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
            )])
            
            bar_fig.update_layout(
                title="Report Types Distribution",
                xaxis_title="Report Type",
                yaxis_title="Number of Reports",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=400
            )
            
            st.plotly_chart(bar_fig, use_container_width=True)

        with chart_col2:
            # Pie Chart: Report Types Distribution
            pie_fig = go.Figure(data=[go.Pie(
                labels=type_counts.index,
                values=type_counts.values,
                hole=.3,
                marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
            )])
            
            total_reports = len(df)
            pie_fig.update_layout(
                title="Report Types - Distribution",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                annotations=[dict(text=f'Total: {total_reports}', font=dict(size=16, color='white'), 
                                showarrow=False, x=0.5, y=0.5)],
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=400
            )
            
            st.plotly_chart(pie_fig, use_container_width=True)

        # Data Table Section
        st.subheader("Detailed Reports")
        
        # Prepare DataFrame for display
        display_df = pd.DataFrame([{
            'Date': report.get('date'),
            'Officer': report.get('officer_name', 'N/A'),
            'Type': report.get('type', 'N/A'),
            'Company': report.get('company_name', 'N/A'),
            'Tasks': str(report.get('tasks', 'N/A'))[:100] + '...' if len(str(report.get('tasks', 'N/A'))) > 100 else str(report.get('tasks', 'N/A')),
            'Challenges': str(report.get('challenges', 'N/A'))[:100] + '...' if len(str(report.get('challenges', 'N/A'))) > 100 else str(report.get('challenges', 'N/A')),
            'Solutions': str(report.get('solutions', 'N/A'))[:100] + '...' if len(str(report.get('solutions', 'N/A'))) > 100 else str(report.get('solutions', 'N/A'))
        } for report in all_reports])
        
        # Convert date to datetime for sorting
        display_df['Date'] = pd.to_datetime(display_df['Date'])
        
        # Sort based on user selection
        display_df = display_df.sort_values('Date', ascending=(sort_order == "Oldest First"))
        
        # Convert date back to string format for display
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        
        # Display the DataFrame with improved formatting
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                "Date": st.column_config.TextColumn(
                    "Date",
                    width="medium",
                ),
                "Officer": st.column_config.TextColumn(
                    "Officer",
                    width="medium",
                ),
                "Type": st.column_config.TextColumn(
                    "Type",
                    width="small",
                ),
                "Company": st.column_config.TextColumn(
                    "Company",
                    width="medium",
                ),
                "Tasks": st.column_config.TextColumn(
                    "Tasks",
                    width="large",
                ),
                "Challenges": st.column_config.TextColumn(
                    "Challenges",
                    width="large",
                ),
                "Solutions": st.column_config.TextColumn(
                    "Solutions",
                    width="large",
                )
            },
            hide_index=True
        )

    else:
        st.info("No reports found for the selected criteria.")

def manage_folders():
    """Create and manage folders with enhanced visual interface"""
    st.header("Manage Folders")
    
    # Define system folders to exclude
    SYSTEM_FOLDERS = {'Summaries', 'Archive', 'Attachments', 'Templates', '__pycache__'}
    
    # Get filtered list of officer folders
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d)) 
        and d not in SYSTEM_FOLDERS
        and not d.startswith('.')
        and not d.startswith('__')
    ]
    
    # Initialize session state variables if they don't exist
    if 'show_rename' not in st.session_state:
        st.session_state.show_rename = False
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = False
    if 'show_info' not in st.session_state:
        st.session_state.show_info = False
    if 'show_create' not in st.session_state:
        st.session_state.show_create = False
    
    # Create New Folder button
    if st.button("📁 Create New Folder", use_container_width=True):
        st.session_state.show_create = True
    
    # Handle Create
    if st.session_state.show_create:
        new_folder_name = st.text_input("Enter folder name:")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Create"):
                if new_folder_name:
                    try:
                        new_folder_path = os.path.join(REPORTS_DIR, new_folder_name)
                        if os.path.exists(new_folder_path):
                            st.error("Folder already exists!")
                        else:
                            os.makedirs(new_folder_path)
                            st.success(f"Folder '{new_folder_name}' created successfully!")
                            st.session_state.show_create = False
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error creating folder: {str(e)}")
                else:
                    st.warning("Please enter a folder name")
        with col2:
            if st.button("Cancel Creation"):
                st.session_state.show_create = False
                st.rerun()
    
    # Folder selection
    selected_folder = st.selectbox("Select folder to view/manage:", officer_folders)
    
    if selected_folder:
        folder_path = os.path.join(REPORTS_DIR, selected_folder)
        reports_path = os.path.join(folder_path, 'reports')
        
        # Action buttons in a row
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✏️ Rename Folder", use_container_width=True):
                st.session_state.show_rename = True
        with col2:
            if st.button("🗑️ Delete Folder", use_container_width=True):
                st.session_state.confirm_delete = True
        with col3:
            if st.button("ℹ️ Folder Info", use_container_width=True):
                st.session_state.show_info = True
        
        # Handle Rename
        if st.session_state.show_rename:
            new_name = st.text_input("Enter new folder name:", selected_folder)
            if st.button("Confirm Rename"):
                try:
                    new_path = os.path.join(REPORTS_DIR, new_name)
                    os.rename(folder_path, new_path)
                    st.success(f"Folder renamed to {new_name}")
                    st.session_state.show_rename = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error renaming folder: {str(e)}")
        
        # Handle Delete
        if st.session_state.confirm_delete:
            st.warning(f"Are you sure you want to delete {selected_folder}?")
            if st.button("Yes, Delete"):
                try:
                    shutil.rmtree(folder_path)
                    st.success(f"Folder {selected_folder} deleted")
                    st.session_state.confirm_delete = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting folder: {str(e)}")
            if st.button("Cancel"):
                st.session_state.confirm_delete = False
                st.rerun()
        
        # Handle Info
        if st.session_state.show_info:
            st.subheader("Folder Information")
            num_files = len([f for f in os.listdir(folder_path) if f.endswith('.json')])
            created_date = datetime.fromtimestamp(os.path.getctime(folder_path))
            modified_date = datetime.fromtimestamp(os.path.getmtime(folder_path))
            
            st.write(f"Number of reports: {num_files}")
            st.write(f"Created: {created_date.strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"Last modified: {modified_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if st.button("Close Info"):
                st.session_state.show_info = False
                st.rerun()
        
        # Display folder contents with enhanced visuals
        st.markdown("### 📂 Folder Contents")
        
        # Check both main folder and reports subfolder for JSON files
        contents = []
        if os.path.exists(folder_path):
            contents.extend([f for f in os.listdir(folder_path) if f.endswith('.json')])
        if os.path.exists(reports_path):
            contents.extend([f for f in os.listdir(reports_path) if f.endswith('.json')])
        
        # Display files in a table with actions
        if contents:
            st.markdown("#### 📄 Files")
            file_data = []
            for file in contents:
                try:
                    # Try main folder first, then reports subfolder
                    file_path = os.path.join(folder_path, file)
                    if not os.path.exists(file_path):
                        file_path = os.path.join(reports_path, file)
                    
                    file_size = os.path.getsize(file_path)
                    file_date = datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_data.append({
                        "Name": file,
                        "Size": f"{file_size/1024:.1f} KB",
                        "Modified": file_date.strftime("%Y-%m-%d %H:%M"),
                        "Actions": file
                    })
                except Exception as e:
                    st.error(f"Error processing file {file}: {str(e)}")
                    continue
            
            if file_data:
                df = pd.DataFrame(file_data)
                st.dataframe(
                    df,
                    column_config={
                        "Actions": st.column_config.Column(
                            "Actions",
                            width="medium",
                            help="Available actions for the file"
                        )
                    },
                    hide_index=True
                )
                
                # File actions
                selected_file = st.selectbox("Select file for actions:", contents)
                if selected_file:
                    col1, col2, col3 = st.columns(3)
                    
                    # Determine the correct file path for the selected file
                    selected_file_path = os.path.join(folder_path, selected_file)
                    if not os.path.exists(selected_file_path):
                        selected_file_path = os.path.join(reports_path, selected_file)
                    
                    with col1:
                        if st.button("👁️ View", use_container_width=True):
                            try:
                                with open(selected_file_path, 'r') as f:
                                    content = json.load(f)
                            except Exception as e:
                                st.error(f"Error reading file: {str(e)}")
                                return
                                
                            # Custom CSS focusing on the top grid items
                            st.markdown("""
                                <style>
                                    /* Top grid layout control */
                                    .report-grid {
                                        display: grid;
                                        grid-template-columns: repeat(3, minmax(250px, 1fr));
                                        gap: 1.5rem;
                                        margin: 1.5rem 0;
                                        width: 100%;
                                    }
                                    
                                    .grid-item {
                                        background-color: #2d2d2d;
                                        padding: 1.5rem;
                                        border-radius: 8px;
                                        text-align: center;
                                        border: 1px solid #3d3d3d;
                                        min-width: 250px;
                                    }
                                    
                                    .grid-item h4 {
                                        color: #9e9e9e;
                                        margin-bottom: 0.75rem;
                                        font-size: 0.9rem;
                                        text-transform: uppercase;
                                        letter-spacing: 0.05em;
                                    }
                                    
                                    .grid-item p {
                                        color: #ffffff;
                                        font-size: 1.1rem;
                                        margin: 0;
                                        font-weight: 500;
                                    }
                                    
                                    /* Company section styling */
                                    .company-grid {
                                        display: grid;
                                        grid-template-columns: 1fr;
                                        margin: 1.5rem 0;
                                        width: 100%;
                                    }
                                    
                                    .company-item {
                                        background-color: #2d2d2d;
                                        padding: 1.5rem;
                                        border-radius: 8px;
                                        border: 1px solid #3d3d3d;
                                        min-width: 350px;
                                    }
                                    
                                    .company-item h4 {
                                        color: #9e9e9e;
                                        margin-bottom: 1rem;
                                        font-size: 1rem;
                                        text-transform: uppercase;
                                        letter-spacing: 0.05em;
                                        display: flex;
                                        align-items: center;
                                        gap: 0.5rem;
                                    }
                                    
                                    .company-content {
                                        background-color: #363636;
                                        padding: 1.25rem;
                                        border-radius: 6px;
                                        color: #ffffff;
                                        font-size: 1.1rem;
                                        font-weight: 500;
                                    }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            # Report Header Grid
                            st.markdown("""
                                <div class="report-grid">
                                    <div class="grid-item">
                                        <h4>Report Type</h4>
                                        <p>{}</p>
                                    </div>
                                    <div class="grid-item">
                                        <h4>Date</h4>
                                        <p>{}</p>
                                    </div>
                                    <div class="grid-item">
                                        <h4>Officer</h4>
                                        <p>{}</p>
                                    </div>
                                </div>
                            """.format(
                                content.get('type', 'N/A'),
                                content.get('date', 'N/A'),
                                content.get('officer_name', 'N/A')
                            ), unsafe_allow_html=True)
                            
                            # Company section
                            st.markdown("""
                                <div class="company-grid">
                                    <div class="company-item">
                                        <h4>🏢 Company</h4>
                                        <div class="company-content">
                                            {}
                                        </div>
                                    </div>
                                </div>
                            """.format(content.get('company_name', 'N/A')), unsafe_allow_html=True)
                            
                            # Tasks Section
                            st.markdown('<div class="content-box">', unsafe_allow_html=True)
                            st.markdown("##### TASKS")
                            tasks = content.get('tasks', '').split('\n')
                            for task in tasks:
                                if task.strip():
                                    st.markdown(f"""
                                        <div style='background-color: #363636; padding: 0.75rem; 
                                                  border-radius: 6px; margin: 0.5rem 0;'>
                                            ✓ {task.strip()}
                                        </div>
                                    """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Challenges Section
                            st.markdown('<div class="content-box">', unsafe_allow_html=True)
                            st.markdown("##### CHALLENGES")
                            challenges = content.get('challenges', '').split('\n')
                            for challenge in challenges:
                                if challenge.strip():
                                    st.markdown(f"""
                                        <div style='background-color: #363636; padding: 0.75rem; 
                                                  border-radius: 6px; margin: 0.5rem 0;'>
                                            ⚠️ {challenge.strip()}
                                        </div>
                                    """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Solutions Section
                            st.markdown('<div class="content-box">', unsafe_allow_html=True)
                            st.markdown("##### SOLUTIONS")
                            solutions = content.get('solutions', '').split('\n')
                            for solution in solutions:
                                if solution.strip():
                                    st.markdown(f"""
                                        <div style='background-color: #363636; padding: 0.75rem; 
                                                  border-radius: 6px; margin: 0.5rem 0;'>
                                            💡 {solution.strip()}
                                        </div>
                                    """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Attachments Section
                            if content.get('attachments'):
                                st.markdown('<div class="content-box">', unsafe_allow_html=True)
                                st.markdown("##### ATTACHMENTS")
                                for attachment in content['attachments']:
                                    st.markdown(f"""
                                        <div style='background-color: #363636; padding: 0.75rem; 
                                                  border-radius: 6px; margin: 0.5rem 0;'>
                                            📎 {attachment}
                                        </div>
                                    """, unsafe_allow_html=True)
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Excel download section
                            try:
                                # Create DataFrame for Excel
                                excel_data = {
                                    'Category': [
                                        'Report Type',
                                        'Date',
                                        'Officer Name',
                                        'Company Name',
                                        '\nTasks',
                                        '\nChallenges',
                                        '\nSolutions'
                                    ],
                                    'Details': [
                                        content.get('type', 'N/A'),
                                        content.get('date', 'N/A'),
                                        content.get('officer_name', 'N/A'),
                                        content.get('company_name', 'N/A'),
                                        '\n' + content.get('tasks', 'N/A'),
                                        '\n' + content.get('challenges', 'N/A'),
                                        '\n' + content.get('solutions', 'N/A')
                                    ]
                                }
                                
                                df = pd.DataFrame(excel_data)
                                
                                # Create Excel buffer
                                buffer = BytesIO()
                                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                                    df.to_excel(writer, sheet_name='Report', index=False)
                                    
                                    # Get workbook and worksheet objects
                                    workbook = writer.book
                                    worksheet = writer.sheets['Report']
                                    
                                    # Define formats
                                    header_format = workbook.add_format({
                                        'bold': True,
                                        'font_size': 12,
                                        'bg_color': '#4B5563',
                                        'font_color': 'white',
                                        'border': 1
                                    })
                                    
                                    cell_format = workbook.add_format({
                                        'font_size': 11,
                                        'text_wrap': True,
                                        'valign': 'top',
                                        'border': 1
                                    })
                                    
                                    # Apply formats
                                    worksheet.set_column('A:A', 20)  # Width of Category column
                                    worksheet.set_column('B:B', 60)  # Width of Details column
                                    
                                    # Apply header format
                                    for col_num, value in enumerate(df.columns.values):
                                        worksheet.write(0, col_num, value, header_format)
                                    
                                    # Apply cell format to all data cells
                                    for row in range(1, len(df) + 1):
                                        worksheet.set_row(row, 45)  # Set row height
                                        worksheet.write(row, 0, df.iloc[row-1, 0], cell_format)
                                        worksheet.write(row, 1, df.iloc[row-1, 1], cell_format)
                                
                                st.markdown("<div style='margin-top: 2rem;'>", unsafe_allow_html=True)
                                st.download_button(
                                    label="📥 Download Report as Excel",
                                    data=buffer.getvalue(),
                                    file_name=f"{content.get('date', 'report')}_{content.get('officer_name', 'unknown')}.xlsx",
                                    mime="application/vnd.ms-excel",
                                    use_container_width=True
                                )
                                st.markdown("</div>", unsafe_allow_html=True)
                                
                            except Exception as e:
                                st.error(f"Error preparing Excel download: {str(e)}")
                    
                    with col2:
                        if st.button("🗑️ Delete", use_container_width=True):
                            try:
                                os.remove(selected_file_path)
                                st.success(f"File '{selected_file}' deleted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting file: {str(e)}")
                    
                    with col3:
                        if st.button("📥 Download", use_container_width=True):
                            try:
                                with open(selected_file_path, 'rb') as f:
                                    st.download_button(
                                        label="Confirm Download",
                                        data=f.read(),
                                        file_name=selected_file,
                                        mime="application/octet-stream"
                                    )
                            except Exception as e:
                                st.error(f"Error preparing download: {str(e)}")
        
        if not contents:
            st.info("This folder is empty")

def show_summaries():
    """Show summaries with proper folder filtering"""
    st.header("Report Summaries")
    
    # Define system folders to exclude
    SYSTEM_FOLDERS = {'Summaries', 'Archive', 'Attachments', 'Templates', '__pycache__'}
    
    # Get filtered list of officer folders
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d)) 
        and d not in SYSTEM_FOLDERS
        and not d.startswith('.')
        and not d.startswith('__')
    ]
    
    # Filter controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_officer = st.selectbox(
            "Select Officer",
            ["All Officers"] + sorted(officer_folders)
        )
    
    with col2:
        time_range = st.selectbox(
            "Time Range",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"]
        )
    
    # Calculate date range based on selection
    end_date = datetime.now().date()
    if time_range == "Last 7 Days":
        start_date = end_date - timedelta(days=7)
    elif time_range == "Last 30 Days":
        start_date = end_date - timedelta(days=30)
    elif time_range == "Last 90 Days":
        start_date = end_date - timedelta(days=90)
    else:
        start_date = None
        end_date = None

    # Generate summary
    summary = generate_summary(
        start_date=start_date.strftime('%Y-%m-%d') if start_date else None,
        end_date=end_date.strftime('%Y-%m-%d') if end_date else None,
        officer_name=selected_officer if selected_officer != "All Officers" else None
    )

    if summary:
        # Display summary statistics
        st.subheader("Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Reports", summary['total_reports'])
        with col2:
            st.metric("Active Officers", summary['officers'])
        with col3:
            st.metric("Companies Covered", summary['companies'])
        with col4:
            st.metric("Report Types", len(summary['report_types']))

        # Charts Section
        st.subheader("Report Analysis")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            # Report Types Distribution
            fig_types = go.Figure(data=[go.Pie(
                labels=list(summary['report_types'].keys()),
                values=list(summary['report_types'].values()),
                hole=.3,
                marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
            )])
            
            fig_types.update_layout(
                title="Report Types Distribution",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=400
            )
            
            st.plotly_chart(fig_types, use_container_width=True)

        with chart_col2:
            # Officer Activity
            fig_officers = go.Figure(data=[go.Bar(
                x=list(summary['officer_activity'].keys()),
                y=list(summary['officer_activity'].values()),
                marker_color='#4ECDC4'
            )])
            
            fig_officers.update_layout(
                title="Officer Activity",
                xaxis_title="Officer",
                yaxis_title="Number of Reports",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=400
            )
            
            st.plotly_chart(fig_officers, use_container_width=True)

        # Company Distribution
        st.subheader("Company Distribution")
        fig_companies = go.Figure(data=[go.Bar(
            x=list(summary['company_distribution'].keys()),
            y=list(summary['company_distribution'].values()),
            marker_color='#FF6B6B'
        )])
        
        fig_companies.update_layout(
            xaxis_title="Company",
            yaxis_title="Number of Reports",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=300,
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig_companies, use_container_width=True)

        # Recent reports table
        st.subheader("Recent Reports")
        if summary['recent_reports']:
            recent_df = pd.DataFrame(summary['recent_reports'])
            # Reorder and format columns
            display_cols = ['date', 'officer_name', 'type', 'company_name', 'tasks']
            recent_df = recent_df[display_cols]
            recent_df.columns = ['Date', 'Officer', 'Type', 'Company', 'Tasks']
            
            # Truncate long text in Tasks column
            recent_df['Tasks'] = recent_df['Tasks'].apply(
                lambda x: str(x)[:100] + '...' if len(str(x)) > 100 else str(x)
            )
            st.dataframe(
                recent_df,
                use_container_width=True,
                column_config={
                    "Date": st.column_config.TextColumn(
                        "Date",
                        width="medium",
                    ),
                    "Officer": st.column_config.TextColumn(
                        "Officer",
                        width="medium",
                    ),
                    "Type": st.column_config.TextColumn(
                        "Type",
                        width="small",
                    ),
                    "Company": st.column_config.TextColumn(
                        "Company",
                        width="medium",
                    ),
                    "Tasks": st.column_config.TextColumn(
                        "Tasks",
                        width="large",
                    )
                },
                hide_index=True
            )
        else:
            st.info("No recent reports found.")

    else:
        st.info("No reports found for the selected criteria.")

def create_dashboard():
    """Create interactive dashboard with report analytics"""
    st.header("Dashboard Analytics")
    
    # Load all reports
    all_officers = [d for d in os.listdir(REPORTS_DIR) 
                   if os.path.isdir(os.path.join(REPORTS_DIR, d)) 
                   and d not in ADDITIONAL_FOLDERS]
    
    all_reports = []
    for officer in all_officers:
        all_reports.extend(load_reports(officer))
    
    if not all_reports:
        st.info("No reports available for analysis.")
        return
    
    df = pd.DataFrame(all_reports)
    df['date'] = pd.to_datetime(df['date'])
    
    # Summary Statistics Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Reports", len(df))
    with col2:
        st.metric("Active Officers", len(df['officer_name'].unique()))
    with col3:
        st.metric("Companies Covered", len(df['company_name'].unique()))
    with col4:
        st.metric("Reports This Month", 
                 len(df[df['date'].dt.month == datetime.now().month]))

    # Two columns for charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie Chart: Report Types Distribution
        st.subheader("Report Types Distribution")
        report_types = df['type'].value_counts()
        fig_pie = {
            'data': [{
                'type': 'pie',
                'labels': report_types.index,
                'values': report_types.values,
                'hole': 0.4,  # Makes it a donut chart
            }],
            'layout': {'height': 400}
        }
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Bar Chart: Top Companies
        st.subheader("Top Companies by Report Count")
        top_companies = df['company_name'].value_counts().head(10)
        fig_companies = {
            'data': [{
                'type': 'bar',
                'x': top_companies.index,
                'y': top_companies.values,
                'marker': {'color': 'lightblue'},
            }],
            'layout': {
                'height': 400,
                'xaxis': {'tickangle': 45},
            }
        }
        st.plotly_chart(fig_companies, use_container_width=True)
    
    # Timeline of Reports
    st.subheader("Reports Timeline")
    timeline = df.groupby('date').size().reset_index(name='count')
    fig_timeline = {
        'data': [{
            'type': 'scatter',
            'x': timeline['date'],
            'y': timeline['count'],
            'mode': 'lines+markers',
            'line': {'color': 'blue'},
        }],
        'layout': {'height': 300}
    }
    st.plotly_chart(fig_timeline, use_container_width=True)
    
    # Two columns for more charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie Chart: Officer Workload Distribution
        st.subheader("Officer Workload Distribution")
        officer_load = df['officer_name'].value_counts()
        fig_officer_pie = {
            'data': [{
                'type': 'pie',
                'labels': officer_load.index,
                'values': officer_load.values,
                'hole': 0.3,
            }],
            'layout': {'height': 400}
        }
        st.plotly_chart(fig_officer_pie, use_container_width=True)
    
    with col2:
        # Bar Chart: Reports by Day of Week
        st.subheader("Reports by Day of Week")
        df['day_of_week'] = df['date'].dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts = df['day_of_week'].value_counts().reindex(day_order)
        fig_days = {
            'data': [{
                'type': 'bar',
                'x': day_counts.index,
                'y': day_counts.values,
                'marker': {'color': 'lightgreen'},
            }],
            'layout': {'height': 400}
        }
        st.plotly_chart(fig_days, use_container_width=True)
    
    # Monthly Trends
    st.subheader("Monthly Report Trends")
    monthly_trends = df.groupby(df['date'].dt.strftime('%Y-%m')).size()
    fig_monthly = {
        'data': [{
            'type': 'bar',
            'x': monthly_trends.index,
            'y': monthly_trends.values,
            'marker': {'color': 'purple'},
        }],
        'layout': {
            'height': 300,
            'xaxis': {'tickangle': 45},
        }
    }
    st.plotly_chart(fig_monthly, use_container_width=True)
    
    # Detailed Filters Section
    show_detailed_analysis()

def show_detailed_analysis():
    """Show detailed analysis with updated report fields and error handling"""
    st.subheader("Detailed Analysis")
    
    # Search and filter section
    search_col1, search_col2, search_col3 = st.columns([2, 1, 1])
    with search_col1:
        search_query = st.text_input("🔍 Search reports", "")
    with search_col2:
        search_type = st.selectbox(
            "Search in:",
            ["All", "Officer", "Company", "Content", "Report Type"],
            label_visibility="collapsed"
        )
    with search_col3:
        report_type_filter = st.selectbox(
            "Report Type",
            ["All Types"] + REPORT_TYPES,
            label_visibility="collapsed"
        )

    # Date range filter
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input("From Date", 
            value=datetime.now().date() - timedelta(days=30),
            max_value=datetime.now().date())
    with date_col2:
        end_date = st.date_input("To Date", 
            value=datetime.now().date(),
            max_value=datetime.now().date())

    # Load all reports using the load_reports function
    all_reports = []
    try:
        all_reports = load_reports()  # This will load all reports for all officers
    except Exception as e:
        st.error(f"Error loading reports: {str(e)}")
        return

    # Filter reports based on date range
    filtered_reports = []
    for report in all_reports:
        try:
            report_date = datetime.strptime(report['date'], '%Y-%m-%d').date()
            if start_date <= report_date <= end_date:
                # Apply report type filter
                if report_type_filter == "All Types" or report['type'] == report_type_filter:
                    # Apply search filter
                    if search_query:
                        search_query = search_query.lower()
                        if search_type == "All":
                            if any(search_query in str(value).lower() 
                                  for value in [report.get('officer_name', ''),
                                              report.get('company_name', ''),
                                              report.get('tasks', ''),
                                              report.get('type', '')]):
                                filtered_reports.append(report)
                        elif search_type == "Officer":
                            if search_query in str(report.get('officer_name', '')).lower():
                                filtered_reports.append(report)
                        elif search_type == "Company":
                            if search_query in str(report.get('company_name', '')).lower():
                                filtered_reports.append(report)
                        elif search_type == "Report Type":
                            if search_query in str(report.get('type', '')).lower():
                                filtered_reports.append(report)
                        elif search_type == "Content":
                            if search_query in str(report.get('tasks', '')).lower():
                                filtered_reports.append(report)
                    else:
                        filtered_reports.append(report)
        except (ValueError, KeyError) as e:
            st.warning(f"Error processing report: {str(e)}")
            continue

    # Display results
    if filtered_reports:
        st.markdown(f"Found {len(filtered_reports)} reports")
        
        # Create DataFrame for display
        df_data = []
        for report in filtered_reports:
            tasks_text = str(report.get('tasks', 'N/A'))
            truncated_tasks = tasks_text[:100] + '...' if len(tasks_text) > 100 else tasks_text
            
            df_data.append({
                'Date': report.get('date', 'N/A'),
                'Type': report.get('type', 'N/A'),
                'Officer': report.get('officer_name', 'N/A'),
                'Company': report.get('company_name', 'N/A'),
                'Tasks': truncated_tasks
            })
        
        df = pd.DataFrame(df_data)
        
        # Sort DataFrame by date (newest first)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date', ascending=False)
        
        # Convert date back to string format for display
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # Display the DataFrame
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Date": st.column_config.TextColumn(
                    "Date",
                    width="medium",
                ),
                "Type": st.column_config.TextColumn(
                    "Type",
                    width="small",
                ),
                "Officer": st.column_config.TextColumn(
                    "Officer",
                    width="medium",
                ),
                "Company": st.column_config.TextColumn(
                    "Company",
                    width="medium",
                ),
                "Tasks": st.column_config.TextColumn(
                    "Tasks",
                    width="large",
                ),
            },
            hide_index=True,
        )
    else:
        st.info("No reports found matching your search criteria.")

def submit_report():
    """Submit a new report"""
    st.header("Submit New Report")
    
    # Get list of existing officer folders
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d))
        and d not in ADDITIONAL_FOLDERS
    ]
    
    # Form inputs
    col1, col2, col3 = st.columns([1.5, 1.5, 1])
    with col1:
        selected_date = st.date_input(
            "Report Date",
            value=datetime.now().date(),
            max_value=datetime.now().date()
        )
    
    with col2:
        report_category = st.selectbox("Report Type", ["Schedule Upload Report", "Global Deposit Assigning"])
    
    with col3:
        report_frequency = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])
    
    # Officer selection with option to add new
    officer_name = st.selectbox(
        "Officer Name",
        ["Select Officer..."] + sorted(officer_folders) + ["+ Add New Officer"]
    )
    
    if officer_name == "+ Add New Officer":
        new_officer = st.text_input("Enter New Officer Name")
        if new_officer:
            officer_name = new_officer
            # Create officer directory if it doesn't exist
            officer_dir = os.path.join(REPORTS_DIR, new_officer)
            if not os.path.exists(officer_dir):
                os.makedirs(officer_dir)
                st.success(f"Created new officer folder for {new_officer}")
    
    # Dynamic fields based on report type
    col1, col2, col3 = st.columns([3, 2, 3])  # Adjusted column ratios
    
    if report_category == "Schedule Upload Report":
        with col1:
            company_name = st.text_input("Company Name")
        with col2:
            total_files = st.number_input("Total Schedule Files", min_value=0, value=0, step=1)
        with col3:
            total_years = st.number_input("Total Years", min_value=0, value=0, step=1)
            st.markdown("""
                <div style='padding: 10px; color: #00FF00;'>
                <i>Please specify the total schedule files you have successfully completed for this company and the total number of years for these schedule</i>
                </div>
            """, unsafe_allow_html=True)
    else:  # Global Deposit Assigning
        with col1:
            companies_assigned = st.text_area(
                "List Companies Assigned",
                height=150,  # Same height as Tasks field
                key="companies_text_area",
                placeholder=(
                    "Example:\n"
                    "Company A\n"
                    "Company B\n"
                    "Company C"
                )
            )
        with col2:
            total_companies = st.number_input(
                "Total Number of Companies Assigned", 
                min_value=0, 
                value=0, 
                step=1
            )
        with col3:
            st.markdown("""
                <div style='padding: 10px; color: #00FF00;'>
                <i>Please list each company on a new line. The total should match the number of companies assigned.</i>
                </div>
            """, unsafe_allow_html=True)
    
    tasks = st.text_area("Tasks Completed")
    challenges = st.text_area("Challenges Encountered")
    solutions = st.text_area("Proposed Solutions")
    
    # File upload with proper handling
    uploaded_files = st.file_uploader(
        "Attach Files",
        accept_multiple_files=True,
        type=ALLOWED_ATTACHMENT_TYPES
    )
    
    # Initialize session state for success message if not exists
    if 'report_submitted' not in st.session_state:
        st.session_state.report_submitted = False
    
    if st.button("Submit Report"):
        if officer_name and officer_name not in ["Select Officer...", "+ Add New Officer"] and tasks:
            try:
                # Save attachments if any
                attachment_paths = []
                if uploaded_files:
                    for file in uploaded_files:
                        attachment_dir = os.path.join(REPORTS_DIR, "Attachments", 
                                                    officer_name, selected_date.strftime('%Y_%m_%d'))
                        os.makedirs(attachment_dir, exist_ok=True)
                        file_path = os.path.join(attachment_dir, file.name)
                        with open(file_path, 'wb') as f:
                            f.write(file.getbuffer())
                        attachment_paths.append(file_path)
                
                # Create report data based on report type
                report_data = {
                    "type": report_category,
                    "frequency": report_frequency,
                    "date": selected_date.strftime("%Y-%m-%d"),
                    "officer_name": officer_name,
                    "tasks": tasks,
                    "challenges": challenges,
                    "solutions": solutions,
                    "attachments": attachment_paths
                }
                
                # Add type-specific fields
                if report_category == "Schedule Upload Report":
                    report_data.update({
                        "company_name": company_name,
                        "total_schedule_files": total_files,
                        "total_years": total_years
                    })
                else:
                    report_data.update({
                        "companies_assigned": companies_assigned,
                        "total_companies": total_companies
                    })
                
                # Save the report
                save_report(officer_name, report_data)
                st.session_state.report_submitted = True
                
                # Show success message
                st.success("Report submitted successfully!")
                
                # Wait a moment before rerunning
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error submitting report: {str(e)}")
        else:
            st.warning("Please fill in all required fields (Officer Name and Tasks)")
    
    # Show success message if report was just submitted
    if st.session_state.report_submitted:
        st.success("Report submitted successfully!")
        st.session_state.report_submitted = False

def show_report_type_distribution():
    """Show distribution of report types with all categories"""
    
    # Get all reports
    all_reports = []
    for officer_folder in [d for d in os.listdir(REPORTS_DIR) if os.path.isdir(os.path.join(REPORTS_DIR, d))]:
        officer_path = os.path.join(REPORTS_DIR, officer_folder)
        for report_file in os.listdir(officer_path):
            if report_file.endswith('.json'):
                try:
                    with open(os.path.join(officer_path, report_file), 'r') as f:
                        report_data = json.load(f)
                        all_reports.append(report_data)
                except Exception as e:
                    continue
    
    # Count report types
    report_types = {
        'Daily': 0,
        'Weekly': 0,
        'Monthly': 0,
        'Special': 0
    }
    
    for report in all_reports:
        rpt_type = report.get('type', 'Daily')  # Default to Daily if type not specified
        if rpt_type in report_types:
            report_types[rpt_type] += 1
    
    # Create pie chart
    fig = go.Figure(data=[go.Pie(
        labels=list(report_types.keys()),
        values=list(report_types.values()),
        hole=.3,
        marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']),
    )])
    
    fig.update_layout(
        title="Report Types Distribution",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(t=30, l=0, r=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white')
    )
    
    # Add total count annotation
    total_reports = sum(report_types.values())
    fig.add_annotation(
        text=f'Total: {total_reports}',
        font=dict(size=16, color='white'),
        showarrow=False,
        x=0.5,
        y=0.5
    )
    
    # Display chart
    st.plotly_chart(fig, use_container_width=True)
    
    # Display breakdown
    st.markdown("### Report Type Breakdown")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Daily Reports", report_types['Daily'])
    with col2:
        st.metric("Weekly Reports", report_types['Weekly'])
    with col3:
        st.metric("Monthly Reports", report_types['Monthly'])
    with col4:
        st.metric("Special Reports", report_types['Special'])

def link_task_to_report(task_id, report_id):
    """Link a task to a specific report"""
    task_path = os.path.join(TASK_DIR, f"task_{task_id}.json")
    if os.path.exists(task_path):
        with open(task_path, 'r') as f:
            task_data = json.load(f)
        task_data['linked_report'] = report_id
        with open(task_path, 'w') as f:
            json.dump(task_data, f, indent=4)

def show_analytics_dashboard():
    """Display analytics dashboard with metrics for both report types"""
    st.header("Analytics Dashboard")
    
    # Get all reports
    all_reports = []
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d))
        and d not in ADDITIONAL_FOLDERS
    ]
    
    for officer in officer_folders:
        officer_reports = load_reports(officer)
        all_reports.extend(officer_reports)
    
    # Separate reports by type
    schedule_reports = [r for r in all_reports if r.get('type') == "Schedule Upload Report"]
    global_deposit_reports = [r for r in all_reports if r.get('type') == "Global Deposit Assigning"]
    
    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Reports", len(all_reports))
    with col2:
        st.metric("Schedule Upload Reports", len(schedule_reports))
    with col3:
        st.metric("Global Deposit Reports", len(global_deposit_reports))
    with col4:
        st.metric("Active Officers", len(officer_folders))
    
    # Schedule Upload Metrics
    st.subheader("Schedule Upload Analytics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_files = sum(r.get('total_schedule_files', 0) for r in schedule_reports)
        st.metric("Total Schedule Files Processed", total_files)
    with col2:
        total_years = sum(r.get('total_years', 0) for r in schedule_reports)
        st.metric("Total Years Processed", total_years)
    with col3:
        avg_files = total_files / len(schedule_reports) if schedule_reports else 0
        st.metric("Average Files per Report", f"{avg_files:.1f}")
    
    # Global Deposit Metrics
    st.subheader("Global Deposit Analytics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_companies = sum(r.get('total_companies', 0) for r in global_deposit_reports)
        st.metric("Total Companies Assigned", total_companies)
    with col2:
        avg_companies = total_companies / len(global_deposit_reports) if global_deposit_reports else 0
        st.metric("Average Companies per Report", f"{avg_companies:.1f}")
    with col3:
        unique_companies = set()
        for report in global_deposit_reports:
            companies = report.get('companies_assigned', '').split('\n')
            unique_companies.update(c.strip() for c in companies if c.strip())
        st.metric("Unique Companies", len(unique_companies))
    
    # Frequency Distribution
    st.subheader("Report Frequency Distribution")
    col1, col2 = st.columns(2)
    
    with col1:
        freq_data = {
            "Daily": len([r for r in all_reports if r.get('frequency') == "Daily"]),
            "Weekly": len([r for r in all_reports if r.get('frequency') == "Weekly"]),
            "Monthly": len([r for r in all_reports if r.get('frequency') == "Monthly"])
        }
        
        # Create frequency chart
        fig = go.Figure(data=[
            go.Bar(
                x=list(freq_data.keys()),
                y=list(freq_data.values()),
                marker_color=['#1f77b4', '#ff7f0e', '#2ca02c']
            )
        ])
        fig.update_layout(
            title="Reports by Frequency",
            xaxis_title="Frequency",
            yaxis_title="Number of Reports",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Report type distribution
        type_data = {
            "Schedule Upload": len(schedule_reports),
            "Global Deposit": len(global_deposit_reports)
        }
        
        fig = go.Figure(data=[
            go.Pie(
                labels=list(type_data.keys()),
                values=list(type_data.values()),
                marker_colors=['#1f77b4', '#ff7f0e']
            )
        ])
        fig.update_layout(
            title="Report Type Distribution",
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Time series analysis
    st.subheader("Activity Timeline")
    
    # Prepare timeline data
    timeline_data = {}
    for report in all_reports:
        date = report.get('date')
        if date:
            if date not in timeline_data:
                timeline_data[date] = {'Schedule Upload': 0, 'Global Deposit': 0}
            timeline_data[date][report.get('type')] += 1
    
    dates = sorted(timeline_data.keys())
    schedule_counts = [timeline_data[date]['Schedule Upload Report'] for date in dates]
    global_counts = [timeline_data[date]['Global Deposit Assigning'] for date in dates]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=schedule_counts,
        name='Schedule Upload',
        mode='lines+markers'
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=global_counts,
        name='Global Deposit',
        mode='lines+markers'
    ))
    
    fig.update_layout(
        title="Reports Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Reports",
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

def show_data_table():
    """Display all reports in a data table format with export options"""
    st.header("Data Table")
    
    # Get all reports
    reports_data = []
    for officer_folder in os.listdir(REPORTS_DIR):
        if os.path.isdir(os.path.join(REPORTS_DIR, officer_folder)) and officer_folder not in ADDITIONAL_FOLDERS:
            officer_reports = load_officer_reports(officer_folder)
            reports_data.extend(officer_reports)
    
    if reports_data:
        # Convert reports to DataFrame
        df_data = []
        for report in reports_data:
            row = {
                'Date': report.get('date', 'N/A'),
                'Officer': report.get('officer_name', 'N/A'),
                'Report Type': report.get('type', 'N/A'),
                'Frequency': report.get('frequency', 'N/A'),
                'Company/Companies': (report.get('company_name', '') if report.get('type') == 'Schedule Upload Report' 
                                    else report.get('companies_assigned', '').replace('\n', ', ')) or 'N/A',
                'Tasks': report.get('tasks', 'N/A'),
                'Challenges': report.get('challenges', 'N/A'),
                'Solutions': report.get('solutions', 'N/A')
            }
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # Export buttons at the top
        st.write("Export Options:")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Excel export
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Reports', index=False)
            excel_buffer.seek(0)
            
            st.download_button(
                label="📊 Export to Excel",
                data=excel_buffer.getvalue(),
                file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col2:
            # CSV export
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Export to CSV",
                data=csv,
                file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col3:
            # PDF export
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import letter, landscape
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
                from reportlab.lib.pagesizes import inch
                
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(letter)
                )
                
                # Convert DataFrame to list of lists
                data = [df.columns.tolist()] + df.values.tolist()
                
                # Create table
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                # Build PDF
                elements = []
                elements.append(table)
                doc.build(elements)
                
                pdf_data = pdf_buffer.getvalue()
                st.download_button(
                    label="📑 Export to PDF",
                    data=pdf_data,
                    file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"PDF generation failed: {str(e)}")
        
        # Display table
        st.dataframe(
            df,
            column_config={
                "Date": st.column_config.DateColumn("Date"),
                "Officer": st.column_config.TextColumn("Officer"),
                "Report Type": st.column_config.TextColumn(
                    "Report Type",
                    help="Schedule Upload Report or Global Deposit Assigning"
                ),
                "Frequency": st.column_config.TextColumn(
                    "Frequency",
                    help="Daily, Weekly, or Monthly"
                ),
                "Company/Companies": st.column_config.TextColumn(
                    "Company/Companies",
                    width="large",
                    help="Shows company name for Schedule Upload or list of companies for Global Deposit"
                ),
                "Tasks": st.column_config.TextColumn("Tasks", width="large"),
                "Challenges": st.column_config.TextColumn("Challenges", width="large"),
                "Solutions": st.column_config.TextColumn("Solutions", width="large")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No data available in the table.")

def search_reports():
    """Search reports functionality"""
    st.header("Search Reports")
    
    # Get list of officers
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d))
        and d not in ADDITIONAL_FOLDERS
    ]
    
    # Search filters
    col1, col2, col3 = st.columns(3)
    with col1:
        search_officer = st.selectbox("Select Officer", ["All Officers"] + sorted(officer_folders))
    with col2:
        search_type = st.selectbox("Report Type", ["All Types", "Schedule Upload Report", "Global Deposit Assigning"])
    with col3:
        search_frequency = st.selectbox("Frequency", ["All", "Daily", "Weekly", "Monthly"])
    
    search_term = st.text_input("Search Term (searches in tasks, challenges, and solutions)")
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=None)
    with col2:
        end_date = st.date_input("End Date", value=None)
    
    # Search button
    if st.button("Search Reports"):
        found_reports = []
        
        # Collect all matching reports
        for officer in officer_folders:
            if search_officer == "All Officers" or search_officer == officer:
                officer_reports = load_reports(officer)
                
                # Filter reports based on criteria
                for report in officer_reports:
                    # Type filter
                    if search_type != "All Types" and report.get('type') != search_type:
                        continue
                        
                    # Frequency filter
                    if search_frequency != "All" and report.get('frequency') != search_frequency:
                        continue
                    
                    # Date range filter
                    report_date = datetime.strptime(report.get('date', ''), '%Y-%m-%d').date()
                    if start_date and report_date < start_date:
                        continue
                    if end_date and report_date > end_date:
                        continue
                    
                    # Search term filter
                    if search_term:
                        search_term_lower = search_term.lower()
                        text_to_search = ' '.join([
                            str(report.get('tasks', '')),
                            str(report.get('challenges', '')),
                            str(report.get('solutions', '')),
                            str(report.get('company_name', '')),
                            str(report.get('companies_assigned', ''))
                        ]).lower()
                        
                        if search_term_lower not in text_to_search:
                            continue
                    
                    found_reports.append(report)
        
        # Display results
        if found_reports:
            st.success(f"Found {len(found_reports)} matching reports")
            show_found_reports(found_reports)
        else:
            st.warning("No reports found matching your criteria")

def show_found_reports(found_reports):
    """Display found reports in a table format"""
    if found_reports:
        # Convert reports to DataFrame with additional columns
        df_data = []
        for report in found_reports:
            row = {
                'Date': report.get('date', 'N/A'),
                'Officer': report.get('officer_name', 'N/A'),
                'Report Type': report.get('type', 'N/A'),
                'Frequency': report.get('frequency', 'N/A'),
                'Company/Companies': (report.get('company_name', '') if report.get('type') == 'Schedule Upload Report' 
                                    else report.get('companies_assigned', '').replace('\n', ', ')) or 'N/A',
                'Tasks': report.get('tasks', 'N/A'),
                'Challenges': report.get('challenges', 'N/A'),
                'Solutions': report.get('solutions', 'N/A')
            }
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # Display table with updated columns
        st.dataframe(
            df,
            column_config={
                "Date": st.column_config.DateColumn("Date"),
                "Officer": st.column_config.TextColumn("Officer"),
                "Report Type": st.column_config.TextColumn(
                    "Report Type",
                    help="Schedule Upload Report or Global Deposit Assigning"
                ),
                "Frequency": st.column_config.TextColumn(
                    "Frequency",
                    help="Daily, Weekly, or Monthly"
                ),
                "Company/Companies": st.column_config.TextColumn(
                    "Company/Companies",
                    width="large",
                    help="Shows company name for Schedule Upload or list of companies for Global Deposit"
                ),
                "Tasks": st.column_config.TextColumn("Tasks", width="large"),
                "Challenges": st.column_config.TextColumn("Challenges", width="large"),
                "Solutions": st.column_config.TextColumn("Solutions", width="large")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Export options
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Export to Excel"):
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False)
                excel_buffer.seek(0)
                st.download_button(
                    "Download Excel",
                    data=excel_buffer,
                    file_name=f"found_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            if st.button("Export to CSV"):
                csv_buffer = BytesIO()
                df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                st.download_button(
                    "Download CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"found_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    else:
        st.info("No reports found.")

def main():
    """Main function to run the application"""
    st.set_page_config(page_title="Officer Reports & Task Management", layout="wide")
    
    # Initialize folders
    init_folders()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Add Task Management to the navigation options
    nav_option = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Submit Report", "View Reports", "Report Summaries", 
         "Task Management", "Manage Folders"]
    )
    
    if nav_option == "Dashboard":
        create_dashboard()
    elif nav_option == "Submit Report":
        submit_report()
    elif nav_option == "View Reports":
        view_reports()
    elif nav_option == "Report Summaries":
        show_summaries()
    elif nav_option == "Task Management":
        create_task_dashboard()
    elif nav_option == "Manage Folders":
        manage_folders()

if __name__ == "__main__":
    main()
