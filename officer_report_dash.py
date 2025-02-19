import streamlit as st
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import shutil
from io import BytesIO
import plotly.graph_objects as go

# Configuration and Constants
REPORTS_DIR = "officer_reports"
REPORT_TYPES = ["Daily", "Weekly"]
ADDITIONAL_FOLDERS = ["Templates", "Summaries", "Archives", "Attachments"]

# Add new constants
TEMPLATE_EXTENSIONS = ['.json', '.txt', '.md']
ALLOWED_ATTACHMENT_TYPES = ['png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xlsx', 'csv']
AUTO_ARCHIVE_DAYS = 30  # Reports older than this will be auto-archived

def init_folders():
    """Initialize necessary folders if they don't exist"""
    # Create main reports directory
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    
    # Create additional organizational folders
    for folder in ADDITIONAL_FOLDERS:
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
    """Save report to JSON file in officer's reports folder"""
    officer_dir = os.path.join(REPORTS_DIR, officer_name)
    reports_dir = os.path.join(officer_dir, 'reports')  # Save in reports subfolder
    
    # Create directories if they don't exist
    if not os.path.exists(officer_dir):
        os.makedirs(officer_dir)
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    filename = f"{report_data['date']}_{report_data['type']}.json"
    filepath = os.path.join(reports_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(report_data, f, indent=4)
    return filepath

def load_reports(officer_name=None):
    """Load all reports or reports for a specific officer"""
    reports = []
    if officer_name:
        officer_dir = os.path.join(REPORTS_DIR, officer_name)
        reports_dir = os.path.join(officer_dir, 'reports')  # Look in reports subfolder
        if os.path.exists(reports_dir):
            for filename in os.listdir(reports_dir):
                if filename.endswith('.json'):  # Only process JSON files
                    try:
                        with open(os.path.join(reports_dir, filename), 'r') as f:
                            reports.append(json.load(f))
                    except Exception as e:
                        st.warning(f"Error reading report {filename}: {str(e)}")
                        continue
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
    reports = []
    for officer in os.listdir(REPORTS_DIR):
        if officer not in ADDITIONAL_FOLDERS and os.path.isdir(os.path.join(REPORTS_DIR, officer)):
            if officer_name and officer != officer_name:
                continue
            officer_reports = load_reports(officer)
            reports.extend(officer_reports)
    
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
        'recent_reports': recent_reports_list  # Use the converted list
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
    uploaded_files = st.file_uploader("Upload attachments", 
                                    accept_multiple_files=True,
                                    type=ALLOWED_ATTACHMENT_TYPES)
    
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
            ["All Types", "Daily", "Weekly", "Monthly", "Special"]
        )
    
    with col3:
        sort_order = st.selectbox(
            "Sort By",
            ["Newest First", "Oldest First"]
        )

    # Collect reports
    report_list = []
    officers_to_check = [selected_officer] if selected_officer != "All Officers" else officer_folders
    
    for officer in officers_to_check:
        if officer != "All Officers":
            officer_path = os.path.join(REPORTS_DIR, officer)
            if os.path.isdir(officer_path):
                for report_file in os.listdir(officer_path):
                    if report_file.endswith('.json'):
                        try:
                            with open(os.path.join(officer_path, report_file), 'r') as f:
                                report_data = json.load(f)
                                report_data['file_name'] = report_file
                                report_data['officer_name'] = officer
                                report_list.append(report_data)
                        except Exception as e:
                            st.warning(f"Error reading report {report_file}: {str(e)}")
                            continue

    # Filter by report type if selected
    if report_type != "All Types":
        report_list = [r for r in report_list if r.get('type') == report_type]

    # Sort reports
    report_list.sort(
        key=lambda x: datetime.strptime(x.get('date', '1900-01-01'), '%Y-%m-%d'),
        reverse=(sort_order == "Newest First")
    )

    if report_list:
        # Statistics Section
        st.subheader("Report Statistics")
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        
        with stat_col1:
            st.metric("Total Reports", len(report_list))
        with stat_col2:
            unique_companies = len(set(r.get('company_name', '') for r in report_list))
            st.metric("Companies", unique_companies)
        with stat_col3:
            unique_officers = len(set(r.get('officer_name', '') for r in report_list))
            st.metric("Officers", unique_officers)
        with stat_col4:
            report_types = len(set(r.get('type', '') for r in report_list))
            st.metric("Report Types", report_types)

        # Charts Section
        st.subheader("Report Analysis")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            # Bar Chart
            type_counts = {
                'Daily': 0, 'Weekly': 0, 'Monthly': 0, 'Special': 0
            }
            for report in report_list:
                report_type = report.get('type', 'Daily')
                if report_type in type_counts:
                    type_counts[report_type] += 1

            bar_fig = go.Figure(data=[go.Bar(
                x=list(type_counts.keys()),
                y=list(type_counts.values()),
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
            # Pie Chart
            pie_fig = go.Figure(data=[go.Pie(
                labels=list(type_counts.keys()),
                values=list(type_counts.values()),
                hole=.3,
                marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
            )])
            
            total_reports = sum(type_counts.values())
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

        # Data Table
        st.subheader("Detailed Reports")
        df = pd.DataFrame([{
            'Date': report.get('date', 'N/A'),
            'Officer': report.get('officer_name', 'N/A'),
            'Type': report.get('type', 'Daily'),
            'Company': report.get('company_name', 'N/A'),
            'Tasks': str(report.get('tasks', 'N/A'))[:100] + '...' if len(str(report.get('tasks', 'N/A'))) > 100 else str(report.get('tasks', 'N/A'))
        } for report in report_list])
        
        st.dataframe(df, use_container_width=True)

    else:
        st.info("No reports found for the selected criteria.")

def manage_folders():
    """Create and manage folders with enhanced visual interface"""
    st.header("Manage Folders")
    
    # Custom CSS for better spacing only
    st.markdown("""
        <style>
            /* Container spacing */
            .block-container {
                padding: 2rem 1rem !important;
            }
            
            /* Table spacing */
            .stDataFrame {
                width: 100% !important;
            }
            
            /* File list spacing */
            [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] > div {
                margin-bottom: 1.5rem;
            }
            
            /* Button spacing */
            .stButton > button {
                margin: 0.5rem 0;
                width: 100%;
            }
            
            /* Selectbox spacing */
            .stSelectbox {
                margin: 1rem 0;
            }
            
            /* Section spacing */
            .section-spacing {
                margin: 2rem 0;
                padding: 1rem;
            }
            
            /* Grid layout spacing */
            .row-widget {
                margin: 1rem 0;
            }
            
            /* Column spacing */
            [data-testid="column"] {
                padding: 0 0.5rem;
            }
            
            /* Header spacing */
            h1, h2, h3, h4, h5 {
                margin: 1.5rem 0 1rem 0;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Display existing folders
    st.subheader("Existing Folders")
    all_folders = [d for d in os.listdir(REPORTS_DIR) 
                  if os.path.isdir(os.path.join(REPORTS_DIR, d))]
    
    if all_folders:
        # Create tabs for different views
        tab1, tab2 = st.tabs(["📂 Folder View", "📊 Folder Statistics"])
        
        with tab1:
            # Enhanced folder selection with metrics
            selected_folder = st.selectbox("Select folder to view/manage:", all_folders)
            
            if selected_folder:
                folder_path = os.path.join(REPORTS_DIR, selected_folder)
                
                # Folder actions in a container
                with st.container():
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("✏️ Rename Folder", use_container_width=True):
                            st.session_state.show_rename = True
                            
                    with col2:
                        if st.button("🗑️ Delete Folder", use_container_width=True):
                            if st.session_state.get('confirm_delete', False):
                                try:
                                    import shutil
                                    shutil.rmtree(folder_path)
                                    st.success(f"Folder '{selected_folder}' deleted successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting folder: {str(e)}")
                            else:
                                st.session_state.confirm_delete = True
                                st.warning(f"Are you sure you want to delete '{selected_folder}'? Click delete again to confirm.")
                    
                    with col3:
                        # Add folder info button
                        if st.button("ℹ️ Folder Info", use_container_width=True):
                            st.session_state.show_info = True
                
                # Rename folder interface
                if st.session_state.get('show_rename', False):
                    with st.expander("Rename Folder", expanded=True):
                        new_name = st.text_input("Enter new folder name:", selected_folder)
                        if st.button("✅ Confirm Rename"):
                            if new_name and new_name != selected_folder:
                                try:
                                    new_path = os.path.join(REPORTS_DIR, new_name)
                                    if os.path.exists(new_path):
                                        st.warning(f"Folder '{new_name}' already exists!")
                                    else:
                                        os.rename(folder_path, new_path)
                                        st.success(f"Folder renamed to '{new_name}' successfully!")
                                        st.session_state.show_rename = False
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error renaming folder: {str(e)}")
                
                # Folder info display
                if st.session_state.get('show_info', False):
                    with st.expander("Folder Information", expanded=True):
                        contents = os.listdir(folder_path)
                        total_size = sum(os.path.getsize(os.path.join(folder_path, f)) 
                                       for f in contents if os.path.isfile(os.path.join(folder_path, f)))
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Items", len(contents))
                        with col2:
                            st.metric("Size", f"{total_size/1024:.1f} KB")
                        with col3:
                            st.metric("Last Modified", 
                                    datetime.fromtimestamp(os.path.getmtime(folder_path))
                                    .strftime("%Y-%m-%d"))
                
                # Display folder contents with enhanced visuals
                st.markdown("### 📂 Folder Contents")
                contents = os.listdir(folder_path)
                
                # Separate files and folders
                subfolders = [item for item in contents if os.path.isdir(os.path.join(folder_path, item))]
                files = [item for item in contents if os.path.isfile(os.path.join(folder_path, item))]
                
                # Display subfolders in a grid
                if subfolders:
                    st.markdown("#### 📁 Subfolders")
                    cols = st.columns(3)
                    for idx, subfolder in enumerate(subfolders):
                        with cols[idx % 3]:
                            with st.container():
                                st.markdown(f"**{subfolder}**")
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("🗑️", key=f"del_{subfolder}", help="Delete subfolder"):
                                        try:
                                            import shutil
                                            shutil.rmtree(os.path.join(folder_path, subfolder))
                                            st.success(f"Subfolder '{subfolder}' deleted!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error deleting subfolder: {str(e)}")
                                with col2:
                                    if st.button("📊", key=f"info_{subfolder}", help="Subfolder info"):
                                        subfolder_path = os.path.join(folder_path, subfolder)
                                        subfolder_contents = os.listdir(subfolder_path)
                                        st.info(f"Items: {len(subfolder_contents)}")
                
                # Display files in a table with actions
                if files:
                    st.markdown("#### 📄 Files")
                    file_data = []
                    for file in files:
                        file_path = os.path.join(folder_path, file)
                        file_size = os.path.getsize(file_path)
                        file_date = datetime.fromtimestamp(os.path.getmtime(file_path))
                        file_data.append({
                            "Name": file,
                            "Size": f"{file_size/1024:.1f} KB",
                            "Modified": file_date.strftime("%Y-%m-%d %H:%M"),
                            "Actions": file
                        })
                    
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
                    selected_file = st.selectbox("Select file for actions:", files)
                    if selected_file:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("👁️ View", use_container_width=True):
                                file_path = os.path.join(folder_path, selected_file)
                                try:
                                    with open(file_path, 'r') as f:
                                        content = json.load(f)
                                    
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
                                                min-width: 250px;  /* Minimum width for each item */
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
                                            
                                            /* Container adjustments for the grid */
                                            [data-testid="stHorizontalBlock"] {
                                                gap: 1.5rem !important;
                                                padding: 0 1rem !important;
                                            }
                                        </style>
                                    """, unsafe_allow_html=True)
                                    
                                    # Report Header Grid with expanded width
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
                                    
                                    # Add CSS for company section
                                    st.markdown("""
                                        <style>
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
                                    
                                    # Update the Company section with new styling
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
                                    
                                    # Add these CSS rules for Challenges and Solutions grid
                                    st.markdown("""
                                        <style>
                                            /* Challenges and Solutions grid */
                                            .challenge-solution-grid {
                                                display: grid;
                                                grid-template-columns: repeat(2, minmax(350px, 1fr));
                                                gap: 1.5rem;
                                                margin: 1.5rem 0;
                                                width: 100%;
                                            }
                                            
                                            .challenge-solution-item {
                                                background-color: #2d2d2d;
                                                padding: 1.5rem;
                                                border-radius: 8px;
                                                border: 1px solid #3d3d3d;
                                                min-width: 350px;
                                            }
                                            
                                            .challenge-solution-item h4 {
                                                color: #9e9e9e;
                                                margin-bottom: 1rem;
                                                font-size: 1rem;
                                                text-transform: uppercase;
                                                letter-spacing: 0.05em;
                                                display: flex;
                                                align-items: center;
                                                gap: 0.5rem;
                                            }
                                            
                                            .challenge-solution-content {
                                                background-color: #363636;
                                                padding: 1.25rem;
                                                border-radius: 6px;
                                                color: #ffffff;
                                                font-size: 1rem;
                                                line-height: 1.5;
                                                min-height: 100px;
                                            }
                                        </style>
                                    """, unsafe_allow_html=True)
                                    
                                    # Update the Challenges and Solutions section
                                    st.markdown("""
                                        <div class="challenge-solution-grid">
                                            <div class="challenge-solution-item">
                                                <h4>⚠️ Challenges</h4>
                                                <div class="challenge-solution-content">
                                                    {}
                                                </div>
                                            </div>
                                            <div class="challenge-solution-item">
                                                <h4>💡 Solutions</h4>
                                                <div class="challenge-solution-content">
                                                    {}
                                                </div>
                                            </div>
                                        </div>
                                    """.format(
                                        content.get('challenges', 'No challenges recorded'),
                                        content.get('solutions', 'No solutions recorded')
                                    ), unsafe_allow_html=True)
                                    
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
                                    
                                    # Download Button
                                    st.markdown("<div style='margin-top: 2rem;'>", unsafe_allow_html=True)
                                    st.download_button(
                                        label="📥 Download Report",
                                        data=json.dumps(content, indent=4),
                                        file_name=selected_file,
                                        mime="application/json",
                                        use_container_width=True
                                    )
                                    st.markdown("</div>", unsafe_allow_html=True)
                                    
                                except json.JSONDecodeError:
                                    with open(file_path, 'r') as f:
                                        content = f.read()
                                    st.markdown('<div class="content-box">', unsafe_allow_html=True)
                                    st.markdown("##### FILE CONTENT")
                                    st.text_area("", value=content, height=300, disabled=True)
                                    st.markdown('</div>', unsafe_allow_html=True)
                                except Exception as e:
                                    st.error(f"Error reading file: {str(e)}")
                        with col2:
                            if st.button("🗑️ Delete", use_container_width=True):
                                try:
                                    os.remove(os.path.join(folder_path, selected_file))
                                    st.success(f"File '{selected_file}' deleted!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting file: {str(e)}")
                        with col3:
                            if st.button("📥 Download", use_container_width=True):
                                file_path = os.path.join(folder_path, selected_file)
                                with open(file_path, 'rb') as f:
                                    st.download_button(
                                        label="Confirm Download",
                                        data=f.read(),
                                        file_name=selected_file,
                                        mime="application/octet-stream"
                                    )
                
                if not contents:
                    st.info("This folder is empty")
                
                # Create subfolder interface
                with st.expander("Create New Subfolder"):
                    subfolder_name = st.text_input(f"Enter subfolder name for '{selected_folder}':")
                    if st.button("📁 Create Subfolder"):
                        if subfolder_name:
                            try:
                                subfolder_path = os.path.join(folder_path, subfolder_name)
                                if os.path.exists(subfolder_path):
                                    st.warning(f"Subfolder '{subfolder_name}' already exists!")
                                else:
                                    os.makedirs(subfolder_path)
                                    st.success(f"Subfolder '{subfolder_name}' created successfully!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error creating subfolder: {str(e)}")
                        else:
                            st.warning("Please enter a subfolder name.")
        
        with tab2:
            # Folder statistics and visualizations
            st.subheader("Folder Statistics")
            folder_sizes = {}
            folder_items = {}
            
            for folder in all_folders:
                folder_path = os.path.join(REPORTS_DIR, folder)
                contents = os.listdir(folder_path)
                size = sum(os.path.getsize(os.path.join(folder_path, f)) 
                          for f in contents if os.path.isfile(os.path.join(folder_path, f)))
                folder_sizes[folder] = size/1024  # Convert to KB
                folder_items[folder] = len(contents)
            
            # Display folder size distribution
            fig_sizes = {
                'data': [{
                    'type': 'pie',
                    'labels': list(folder_sizes.keys()),
                    'values': list(folder_sizes.values()),
                    'hole': 0.4,
                }],
                'layout': {
                    'title': 'Folder Size Distribution (KB)',
                    'height': 400
                }
            }
            st.plotly_chart(fig_sizes, use_container_width=True)
            
            # Display items per folder
            fig_items = {
                'data': [{
                    'type': 'bar',
                    'x': list(folder_items.keys()),
                    'y': list(folder_items.values()),
                    'marker': {'color': 'lightblue'},
                }],
                'layout': {
                    'title': 'Items per Folder',
                    'height': 400,
                    'xaxis': {'tickangle': 45}
                }
            }
            st.plotly_chart(fig_items, use_container_width=True)
    
    else:
        st.info("No folders created yet.")
    
    # Create new main folder interface
    with st.expander("Create New Main Folder"):
        st.write("### Create New Main Folder")
        new_folder = st.text_input("Enter folder name:")
        if st.button("📁 Create Folder"):
            if new_folder:
                try:
                    folder_path = os.path.join(REPORTS_DIR, new_folder)
                    if os.path.exists(folder_path):
                        st.warning(f"Folder '{new_folder}' already exists!")
                    else:
                        os.makedirs(folder_path)
                        st.success(f"Folder '{new_folder}' created successfully!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error creating folder: {str(e)}")
            else:
                st.warning("Please enter a folder name.")

def show_summaries():
    """Show summaries with proper folder filtering"""
    st.header("Report Summaries")
    
    # Define system folders to exclude
    SYSTEM_FOLDERS = {'Summaries', 'Archive', 'Attachments', 'Templates', '__pycache__'}
    
    # Filter controls with cleaned officer list
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # Get only officer folders (excluding system folders)
        officer_folders = [
            d for d in os.listdir(REPORTS_DIR) 
            if os.path.isdir(os.path.join(REPORTS_DIR, d)) 
            and d not in SYSTEM_FOLDERS
            and not d.startswith('.')  # Exclude hidden folders
            and not d.startswith('__')  # Exclude python special folders
        ]
        
        selected_officer = st.selectbox(
            "Select Officer",
            ["All Officers"] + sorted(officer_folders)
        )
    
    with col2:
        report_type = st.selectbox(
            "Report Type",
            ["All Types", "Daily", "Weekly", "Monthly", "Special"]
        )
    
    with col3:
        time_range = st.selectbox(
            "Time Range",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"]
        )
    
    # Date calculation based on time range
    end_date = datetime.now().date()
    if time_range == "Last 7 Days":
        start_date = end_date - timedelta(days=7)
    elif time_range == "Last 30 Days":
        start_date = end_date - timedelta(days=30)
    elif time_range == "Last 90 Days":
        start_date = end_date - timedelta(days=90)
    else:
        start_date = datetime.min.date()
    
    # Collect reports with proper folder filtering
    all_reports = []
    officers_to_check = [selected_officer] if selected_officer != "All Officers" else officer_folders
    
    for officer in officers_to_check:
        officer_path = os.path.join(REPORTS_DIR, officer)
        if os.path.isdir(officer_path) and officer not in SYSTEM_FOLDERS:
            for report_file in os.listdir(officer_path):
                if report_file.endswith('.json'):
                    try:
                        with open(os.path.join(officer_path, report_file), 'r') as f:
                            report_data = json.load(f)
                            
                            # Handle date from report or filename
                            if 'date' not in report_data:
                                date_str = report_file.split('_')[0]
                                try:
                                    report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                    report_data['date'] = date_str
                                except ValueError:
                                    file_path = os.path.join(officer_path, report_file)
                                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                    report_data['date'] = mod_time.strftime('%Y-%m-%d')
                            
                            report_data['officer_name'] = officer
                            
                            # Apply filters
                            report_date = datetime.strptime(report_data['date'], '%Y-%m-%d').date()
                            if start_date <= report_date <= end_date:
                                if report_type == "All Types" or report_data.get('type', 'Daily') == report_type:
                                    all_reports.append(report_data)
                                    
                    except Exception as e:
                        st.warning(f"Error reading report {report_file}: {str(e)}")
                        continue
    
    if all_reports:
        # Summary Statistics
        st.subheader("Summary Statistics")
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        
        with stat_col1:
            st.metric("Total Reports", len(all_reports))
        with stat_col2:
            companies = len(set(report.get('company_name', '') for report in all_reports))
            st.metric("Companies Covered", companies)
        with stat_col3:
            officers = len(set(report.get('officer_name', '') for report in all_reports))
            st.metric("Active Officers", officers)
        with stat_col4:
            avg_tasks = sum(len(str(report.get('tasks', '')).split('\n')) for report in all_reports) / len(all_reports)
            st.metric("Avg Tasks per Report", f"{avg_tasks:.1f}")
        
        # Report Type Distribution with both Bar and Pie charts
        st.subheader("Report Distribution")
        
        # Calculate type counts
        type_counts = {
            'Daily': 0,
            'Weekly': 0,
            'Monthly': 0,
            'Special': 0
        }
        for report in all_reports:
            report_type = report.get('type', 'Daily')
            if report_type in type_counts:
                type_counts[report_type] += 1
        
        # Create two columns for charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Bar Chart
            bar_fig = go.Figure(data=[go.Bar(
                x=list(type_counts.keys()),
                y=list(type_counts.values()),
                marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
            )])
            
            bar_fig.update_layout(
                title="Report Types - Bar Chart",
                xaxis_title="Report Type",
                yaxis_title="Number of Reports",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                margin=dict(t=30, l=0, r=0, b=0),
                height=400
            )
            
            st.plotly_chart(bar_fig, use_container_width=True)
        
        with chart_col2:
            # Pie Chart
            pie_fig = go.Figure(data=[go.Pie(
                labels=list(type_counts.keys()),
                values=list(type_counts.values()),
                hole=.3,
                marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']),
            )])
            
            total_reports = sum(type_counts.values())
            pie_fig.update_layout(
                title="Report Types - Distribution",
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                annotations=[dict(
                    text=f'Total: {total_reports}',
                    font=dict(size=16, color='white'),
                    showarrow=False,
                    x=0.5,
                    y=0.5
                )],
                margin=dict(t=30, l=0, r=0, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=400
            )
            
            st.plotly_chart(pie_fig, use_container_width=True)
        
        # Data Table Section
        st.subheader("Detailed Report Data")
        
        # Create DataFrame with all report data
        df_data = []
        for report in all_reports:
            df_data.append({
                'Date': report.get('date', 'N/A'),
                'Officer': report.get('officer_name', 'N/A'),
                'Type': report.get('type', 'Daily'),
                'Company': report.get('company_name', 'N/A'),
                'Tasks': str(report.get('tasks', 'N/A')),
                'Challenges': str(report.get('challenges', 'N/A')),
                'Solutions': str(report.get('solutions', 'N/A'))
            })
        
        df = pd.DataFrame(df_data)
        
        # Display table with truncated text for viewing
        display_df = df.copy()
        for col in ['Tasks', 'Challenges', 'Solutions']:
            display_df[col] = display_df[col].apply(
                lambda x: str(x)[:100] + '...' if len(str(x)) > 100 else str(x)
            )
        
        # Add table styling
        st.markdown("""
            <style>
                .dataframe {
                    width: 100% !important;
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                .dataframe th {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    padding: 12px 8px !important;
                    border-bottom: 1px solid #3d3d3d !important;
                }
                .dataframe td {
                    padding: 10px 8px !important;
                    border-bottom: 1px solid #2d2d2d !important;
                }
                .dataframe tr:hover {
                    background-color: #2d2d2d;
                }
                
                /* Download button styling */
                .stDownloadButton {
                    margin: 1rem 0;
                }
                .stDownloadButton button {
                    width: 100%;
                    padding: 0.5rem !important;
                }
            </style>
        """, unsafe_allow_html=True)
        
        # Display the table
        st.dataframe(display_df, use_container_width=True)
        
        # Download buttons section after the table
        if not df.empty:
            st.markdown("### Download Options")
            col1, col2 = st.columns(2)
            
            # Function to convert dataframe to excel
            def convert_df_to_excel():
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Reports', index=False)
                    # Auto-adjust columns' width
                    worksheet = writer.sheets['Reports']
                    for idx, col in enumerate(df.columns):
                        series = df[col]
                        max_len = max(
                            series.astype(str).map(len).max(),
                            len(str(series.name))
                        ) + 1
                        worksheet.set_column(idx, idx, max_len)
                return output.getvalue()
            
            # Generate Excel file
            excel_file = convert_df_to_excel()
            
            # Generate CSV file
            csv_file = df.to_csv(index=False).encode('utf-8')
            
            # Download buttons
            with col1:
                st.download_button(
                    label="📥 Download Excel",
                    data=excel_file,
                    file_name=f"officer_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )
            
            with col2:
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_file,
                    file_name=f"officer_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        if not all_reports:
            st.info("No reports found for the selected criteria.")
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
            ["All Types", "Daily", "Weekly", "Monthly", "Special"],
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

    # Get all reports with error handling
    all_reports = []
    for officer_folder in [d for d in os.listdir(REPORTS_DIR) if os.path.isdir(os.path.join(REPORTS_DIR, d))]:
        officer_path = os.path.join(REPORTS_DIR, officer_folder)
        for report_file in os.listdir(officer_path):
            if report_file.endswith('.json'):
                try:
                    with open(os.path.join(officer_path, report_file), 'r') as f:
                        report_data = json.load(f)
                        
                        # Extract date from filename if not in report data
                        if 'date' not in report_data:
                            # Assuming filename format: YYYY-MM-DD_type.json
                            date_str = report_file.split('_')[0]
                            try:
                                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                report_data['date'] = date_str
                            except ValueError:
                                # If filename doesn't contain valid date, use file modification time
                                file_path = os.path.join(officer_path, report_file)
                                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                report_data['date'] = mod_time.strftime('%Y-%m-%d')
                        
                        report_data['officer_folder'] = officer_folder
                        report_data['file_name'] = report_file
                        
                        # Convert date string to datetime for comparison
                        try:
                            report_date = datetime.strptime(report_data['date'], '%Y-%m-%d').date()
                            if start_date <= report_date <= end_date:
                                all_reports.append(report_data)
                        except ValueError:
                            # If date parsing fails, include the report anyway
                            all_reports.append(report_data)
                            
                except Exception as e:
                    st.warning(f"Error reading report {report_file}: {str(e)}")
                    continue

    # Filter reports based on search and type
    filtered_reports = []
    for report in all_reports:
        include_report = True
        
        # Report type filter
        if report_type_filter != "All Types":
            report_type = report.get('type', '')
            if isinstance(report_type, str) and report_type != report_type_filter:
                include_report = False
        
        # Search filter
        if search_query:
            search_query = search_query.lower()
            if search_type == "All":
                if not any(search_query in str(value).lower() 
                          for value in [report.get('officer_name', ''),
                                      report.get('company_name', ''),
                                      report.get('tasks', ''),
                                      report.get('type', '')]):
                    include_report = False
            elif search_type == "Officer":
                if search_query not in str(report.get('officer_name', '')).lower():
                    include_report = False
            elif search_type == "Company":
                if search_query not in str(report.get('company_name', '')).lower():
                    include_report = False
            elif search_type == "Report Type":
                if search_query not in str(report.get('type', '')).lower():
                    include_report = False
            elif search_type == "Content":
                if search_query not in str(report.get('tasks', '')).lower():
                    include_report = False
        
        if include_report:
            filtered_reports.append(report)

    # Display results in the existing table format
    if filtered_reports:
        df_data = []
        for report in filtered_reports:
            df_data.append({
                'Date': report.get('date', 'N/A'),
                'Type': report.get('type', 'N/A'),
                'Officer': report.get('officer_name', 'N/A'),
                'Company': report.get('company_name', 'N/A'),
                'Tasks': report.get('tasks', 'N/A')[:100] + '...' if len(str(report.get('tasks', 'N/A'))) > 100 else report.get('tasks', 'N/A')
            })
        
        df = pd.DataFrame(df_data)
        
        # Keep your existing table styling
        st.markdown(f"Found {len(filtered_reports)} reports")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No reports found matching your search criteria.")

def submit_report():
    """Submit report with proper officer management"""
    st.header("Submit Report")
    
    # Define system folders to exclude
    SYSTEM_FOLDERS = {'Summaries', 'Archive', 'Attachments', 'Templates', '__pycache__'}
    
    # Get existing officers
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d)) 
        and d not in SYSTEM_FOLDERS
        and not d.startswith('.')
        and not d.startswith('__')
    ]
    
    # Date and Officer Selection
    col1, col2 = st.columns(2)
    
    with col1:
        selected_date = st.date_input(
            "Select Report Date",
            value=datetime.now().date(),
            min_value=datetime.now().date() - timedelta(days=30),
            max_value=datetime.now().date(),
            help="Select the date for which you're submitting the report"
        )
    
    with col2:
        day_types = {
            "Daily": "Regular daily report",
            "Weekly": "Weekly summary report",
            "Monthly": "Monthly overview report",
            "Special": "Special assignment report"
        }
        
        selected_day_type = st.selectbox(
            "Select Report Type",
            options=list(day_types.keys()),
            help="Choose the type of report you're submitting"
        )
        st.caption(day_types[selected_day_type])
    
    # Officer and Company Selection
    col3, col4 = st.columns(2)
    
    with col3:
        officer_name = st.selectbox(
            "Select Officer",
            options=["Select Officer..."] + sorted(officer_folders) + ["+ Add New Officer"],
            index=0,
            help="Choose your name from the list or add a new officer"
        )
        
        # Show text input if "Add New Officer" is selected
        new_officer_added = False
        if officer_name == "+ Add New Officer":
            new_officer = st.text_input("Enter New Officer Name")
            if new_officer:
                # Create necessary folders for new officer
                try:
                    # Create main officer folder
                    officer_path = os.path.join(REPORTS_DIR, new_officer)
                    if not os.path.exists(officer_path):
                        os.makedirs(officer_path)
                        
                    # Create standard subfolders
                    for subfolder in ['reports', 'attachments']:
                        subfolder_path = os.path.join(officer_path, subfolder)
                        if not os.path.exists(subfolder_path):
                            os.makedirs(subfolder_path)
                    
                    officer_name = new_officer
                    new_officer_added = True
                    st.success(f"New officer '{new_officer}' added successfully!")
                except Exception as e:
                    st.error(f"Error creating officer folders: {str(e)}")
        elif officer_name == "Select Officer...":
            officer_name = ""
    
    with col4:
        company_name = st.text_input("Company Name")
    
    # Rest of the form
    tasks = st.text_area("Tasks Completed", height=150)
    
    col5, col6 = st.columns(2)
    with col5:
        challenges = st.text_area("Challenges Faced", height=150)
    with col6:
        solutions = st.text_area("Solutions Implemented", height=150)
    
    uploaded_files = st.file_uploader("Attach Files", accept_multiple_files=True)
    
    if st.button("Submit Report", use_container_width=True):
        if officer_name and company_name and tasks:
            try:
                # Create report data
                report_data = {
                    "type": selected_day_type,
                    "date": selected_date.strftime("%Y-%m-%d"),
                    "officer_name": officer_name,
                    "company_name": company_name,
                    "tasks": tasks,
                    "challenges": challenges,
                    "solutions": solutions,
                    "attachments": [file.name for file in uploaded_files] if uploaded_files else []
                }
                
                # Use reports subfolder for new structure
                reports_folder = os.path.join(REPORTS_DIR, officer_name, 'reports')
                if not os.path.exists(reports_folder):
                    os.makedirs(reports_folder)
                
                # Save report
                file_name = f"{selected_date.strftime('%Y-%m-%d')}_{selected_day_type}.json"
                file_path = os.path.join(reports_folder, file_name)
                
                if os.path.exists(file_path):
                    if st.warning(f"A report already exists for {selected_date}. Do you want to overwrite it?"):
                        if st.button("Yes, Overwrite"):
                            with open(file_path, 'w') as f:
                                json.dump(report_data, f, indent=4)
                            st.success("Report updated successfully!")
                else:
                    with open(file_path, 'w') as f:
                        json.dump(report_data, f, indent=4)
                    st.success("Report submitted successfully!")
                
                # Handle attachments
                if uploaded_files:
                    attachments_folder = os.path.join(REPORTS_DIR, officer_name, 'attachments')
                    if not os.path.exists(attachments_folder):
                        os.makedirs(attachments_folder)
                    
                    for file in uploaded_files:
                        file_path = os.path.join(attachments_folder, file.name)
                        with open(file_path, 'wb') as f:
                            f.write(file.getbuffer())
                
            except Exception as e:
                st.error(f"Error submitting report: {str(e)}")
        else:
            st.warning("Please fill in all required fields (Officer Name, Company Name, and Tasks)")

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
        report_type = report.get('type', 'Daily')  # Default to Daily if type not specified
        if report_type in report_types:
            report_types[report_type] += 1
    
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

def main():
    """Updated main application"""
    st.title("Officer Report Dashboard")
    
    # Initialize folders
    init_folders()
    
    # Sidebar navigation
    page = st.sidebar.radio("Navigation", 
                          ["Dashboard", "Submit Report", "View Reports", 
                           "Manage Folders", "Summaries"])
    
    if page == "Dashboard":
        create_dashboard()
    elif page == "Submit Report":
        submit_report()
    elif page == "View Reports":
        view_reports()
    elif page == "Summaries":
        show_summaries()
    else:
        manage_folders()

if __name__ == "__main__":
    main()
