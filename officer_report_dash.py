import uuid
import streamlit as st
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import shutil
from io import BytesIO, StringIO
import plotly.graph_objects as go
import time
import plotly.express as px
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from wordcloud import WordCloud
from reportlab.lib.units import inch


# Add these imports at the top of your file
from task_management_dash import (
    create_task_dashboard,
    save_task,
    load_tasks,
    TASK_PRIORITIES,
    TASK_STATUSES,
    TASK_CATEGORIES
)

# Constants
REPORTS_DIR = "officer_reports"
TASK_DIR = "tasks"  # Make sure this matches where your tasks are actually saved

# Report Related Constants
REPORT_TYPES = ["Daily", "Weekly"]
REPORT_STATUSES = ['Pending Review', 'Approved', 'Reviewed', 'Needs Attention']

# Task Related Constants
TASK_PRIORITIES = ["High", "Medium", "Low"]
TASK_STATUSES = ["Pending", "In Progress", "Completed", "Overdue"]
TASK_CATEGORIES = ["Work", "Personal", "Urgent", "Meeting", "Project", "Other"]

# File and Folder Management
ADDITIONAL_FOLDERS = ["Templates", "Summaries", "Archives", "Attachments", "Tasks"]
TEMPLATE_EXTENSIONS = ['.json', '.txt', '.md']
ALLOWED_ATTACHMENT_TYPES = ['png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xlsx', 'csv']
AUTO_ARCHIVE_DAYS = 30  # Reports older than this will be auto-archived

# Create necessary directories
os.makedirs(TASK_DIR, exist_ok=True)

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
    """Save report to JSON file with status"""
    # Add default status if not present
    if 'status' not in report_data:
        report_data['status'] = 'Pending Review'
    if 'comments' not in report_data:
        report_data['comments'] = []
        
    # Create main officer directory if it doesn't exist
    officer_dir = os.path.join(REPORTS_DIR, officer_name)
    if not os.path.exists(officer_dir):
        os.makedirs(officer_dir)
    
    # Format the date properly for both filename and JSON
    report_date = report_data['date']
    if hasattr(report_date, 'strftime'):  # Handle datetime or Timestamp objects
        formatted_date = report_date.strftime("%Y-%m-%d")
        report_data['date'] = formatted_date  # Update the date in report_data
    elif isinstance(report_date, str):
        formatted_date = report_date.split()[0]  # Take just the date part
    
    # Create filename with properly formatted date and type
    report_type = report_data['type'].replace(' ', '_')
    filename = f"{formatted_date}_{report_type}.json"
    filepath = os.path.join(officer_dir, filename)
    
    # Convert any Timestamp objects in the report data to strings
    report_data = json.loads(
        json.dumps(report_data, default=lambda x: x.strftime("%Y-%m-%d") if hasattr(x, 'strftime') else str(x))
    )
    
    # Save the report
    with open(filepath, 'w') as f:
        json.dump(report_data, f, indent=4)
    return filepath

def review_reports():
    """Review pending reports and update their status"""
    st.subheader("Review Reports")
    
    # Load reports
    reports_data = load_reports()
    pending_reports = [r for r in reports_data if r.get('status') == 'Pending Review']
    
    if not pending_reports:
        st.info("No reports pending review")
        return
    
    # Display pending reports in an expandable format
    for report in pending_reports:
        with st.expander(f"📄 {report.get('title', 'Untitled Report')} - {report.get('officer_name', 'Unknown Officer')}"):
            # Report Details
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Officer:**", report.get('officer_name', 'Unknown'))
                st.write("**Date:**", report.get('date', 'No date'))
                st.write("**Type:**", report.get('type', 'No type'))
            with col2:
                st.write("**Status:**", report.get('status', 'Unknown'))
                st.write("**Priority:**", report.get('priority', 'No priority'))
            
            # Report Content
            st.write("**Content:**")
            st.write(report.get('content', 'No content available'))
            
            # Attachments if any
            if 'attachments' in report and report['attachments']:
                st.write("**Attachments:**")
                for attachment in report['attachments']:
                    st.write(f"- {attachment}")
            
            # Review Actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Approve", key=f"approve_{report.get('id', '')}"):
                    # Update report status
                    report['status'] = 'Approved'
                    report['review_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    report['reviewer_notes'] = st.session_state.get(f"notes_{report.get('id', '')}", '')
                    # Use the existing save_report function with correct parameters
                    save_report(report.get('officer_name', 'Unknown'), report)
                    st.success("Report approved!")
                    st.rerun()
            
            with col2:
                if st.button("⚠️ Needs Attention", key=f"attention_{report.get('id', '')}"):
                    # Update report status
                    report['status'] = 'Needs Attention'
                    report['review_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    report['reviewer_notes'] = st.session_state.get(f"notes_{report.get('id', '')}", '')
                    # Use the existing save_report function with correct parameters
                    save_report(report.get('officer_name', 'Unknown'), report)
                    st.warning("Report marked as needing attention!")
                    st.rerun()
            
            # Reviewer Notes
            st.text_area(
                "Review Notes",
                key=f"notes_{report.get('id', '')}",
                placeholder="Add your review notes here..."
            )
def load_reports(officer_folder=None):
    """Load all reports from all officer folders or a specific officer folder"""
    reports_data = []
    try:
        # If specific officer folder is provided
        if officer_folder:
            officer_path = os.path.join(REPORTS_DIR, officer_folder)
            if os.path.isdir(officer_path) and officer_folder not in ADDITIONAL_FOLDERS:
                report_files = [f for f in os.listdir(officer_path) 
                              if f.endswith('.json') and f != 'template.json']
                
                for report_file in report_files:
                    try:
                        with open(os.path.join(officer_path, report_file), 'r') as f:
                            report_data = json.load(f)
                            if 'officer_name' not in report_data:
                                report_data['officer_name'] = officer_folder
                            reports_data.append(report_data)
                    except Exception as e:
                        st.error(f"Error loading report {report_file} for {officer_folder}: {str(e)}")
                        continue
        else:
            # Get all officer folders
            for officer_folder in os.listdir(REPORTS_DIR):
                officer_path = os.path.join(REPORTS_DIR, officer_folder)
                
                # Skip if not a directory or is in ADDITIONAL_FOLDERS
                if not os.path.isdir(officer_path) or officer_folder in ADDITIONAL_FOLDERS:
                    continue
                    
                # Get all report files for this officer
                report_files = [f for f in os.listdir(officer_path) 
                              if f.endswith('.json') and f != 'template.json']
                
                for report_file in report_files:
                    try:
                        with open(os.path.join(officer_path, report_file), 'r') as f:
                            report_data = json.load(f)
                            # Ensure officer name is included
                            if 'officer_name' not in report_data:
                                report_data['officer_name'] = officer_folder
                            reports_data.append(report_data)
                    except Exception as e:
                        st.error(f"Error loading report {report_file} for {officer_folder}: {str(e)}")
                        continue
    
    except Exception as e:
        st.error(f"Error accessing reports directory: {str(e)}")
    
    return reports_data

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
    
    # Report Type and Frequency selection
    report_type = st.selectbox("Report Type", REPORT_TYPES)
    frequency = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])  # Add frequency selection for all report types
    
    officer_name = st.text_input("Officer Name")
    company_name = st.text_input("Company Name")
    
    # Additional fields based on report type
    if report_type == "Schedule Upload Report":
        total_files = st.number_input("Total Schedule Files", min_value=0)
        total_years = st.number_input("Total Years", min_value=0)
    elif report_type == "Global Deposit Assigning":
        companies_assigned = st.text_area("Companies Assigned (one per line)")
        total_companies = st.number_input("Total Companies", min_value=0)
    
    tasks = st.text_area("Tasks Completed")
    challenges = st.text_area("Challenges Encountered")
    solutions = st.text_area("Proposed Solutions")
    
    if st.button("Submit Report"):
        if officer_name and tasks:
            report_data = {
                "type": report_type,
                "frequency": frequency,  # Make sure frequency is included in report_data
                "officer_name": officer_name,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "company_name": company_name,
                "tasks": tasks,
                "challenges": challenges,
                "solutions": solutions
            }
            
            # Add type-specific fields
            if report_type == "Schedule Upload Report":
                report_data.update({
                    "total_schedule_files": total_files,
                    "total_years": total_years
                })
            elif report_type == "Global Deposit Assigning":
                report_data.update({
                    "companies_assigned": companies_assigned,
                    "total_companies": total_companies
                })
            
            try:
                save_report(officer_name, report_data)
                st.success("Report saved successfully!")
            except Exception as e:
                st.error(f"Error saving report: {str(e)}")
        else:
            st.warning("Please fill in all required fields.")

def view_reports():
    """View reports with enhanced tabbed interface and export options"""
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
            ["All Types", "Schedule Upload Report", "Global Deposit Assigning", "Other Report"]
        )
    
    with col3:
        sort_order = st.selectbox(
            "Sort By",
            ["Newest First", "Oldest First"]
        )

    # Load reports
    if selected_officer != "All Officers":
        all_reports = load_reports(selected_officer)
    else:
        all_reports = load_reports()

    if all_reports:
        # Filter by report type if selected
        if report_type != "All Types":
            filtered_reports = [r for r in all_reports if r.get('type') == report_type]
        else:
            filtered_reports = all_reports

        # Report Statistics Section
        st.subheader("Report Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Reports", len(filtered_reports))
        
        with col2:
            unique_officers = len(set(r.get('officer_name') for r in filtered_reports))
            st.metric("Total Officers", unique_officers)
        
        with col3:
            unique_companies = len(set(r.get('company_name') for r in filtered_reports))
            st.metric("Total Companies", unique_companies)
        
        with col4:
            report_types_count = len(set(r.get('type') for r in filtered_reports))
            st.metric("Report Types", report_types_count)

        # Report Analysis Section
        st.subheader("Report Analysis")
        
        # Create tabs for different analyses
        analysis_tab1, analysis_tab2 = st.tabs(["Time Analysis", "Distribution Analysis"])
        
        with analysis_tab1:
            # Convert dates for analysis
            dates = [datetime.strptime(r.get('date'), '%Y-%m-%d') for r in filtered_reports]
            df_dates = pd.DataFrame({'date': dates})
            df_dates['count'] = 1
            df_dates = df_dates.set_index('date')
            df_dates = df_dates.resample('D').sum().fillna(0)
            
            # Create time series plot
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_dates.index,
                y=df_dates['count'],
                mode='lines+markers',
                name='Reports'
            ))
            fig.update_layout(
                title='Reports Over Time',
                xaxis_title='Date',
                yaxis_title='Number of Reports',
                hovermode='x'
            )
            st.plotly_chart(fig, use_container_width=True)

        with analysis_tab2:
            col1, col2 = st.columns(2)
            
            with col1:
                # Report types distribution
                type_counts = pd.Series([r.get('type') for r in filtered_reports]).value_counts()
                fig_types = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    title='Distribution of Report Types'
                )
                st.plotly_chart(fig_types, use_container_width=True)
            
            with col2:
                # Officer distribution
                officer_counts = pd.Series([r.get('officer_name') for r in filtered_reports]).value_counts()
                fig_officers = px.bar(
                    x=officer_counts.index,
                    y=officer_counts.values,
                    title='Reports by Officer',
                    labels={'x': 'Officer', 'y': 'Number of Reports'}
                )
                fig_officers.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_officers, use_container_width=True)

        # Create tabs for different report types
        tab1, tab2, tab3 = st.tabs(["Schedule Upload Reports", "Global Deposit Reports", "Other Reports"])

        # Separate reports by type
        schedule_reports = [r for r in filtered_reports if r.get('type') == 'Schedule Upload Report']
        global_reports = [r for r in filtered_reports if r.get('type') == 'Global Deposit Assigning']
        other_reports = [r for r in filtered_reports if r.get('type') not in ['Schedule Upload Report', 'Global Deposit Assigning']]

        # Schedule Upload Reports Tab
        with tab1:
            if schedule_reports:
                st.write(f"Found {len(schedule_reports)} Schedule Upload Reports")
                
                # Create DataFrame
                df = pd.DataFrame([{
                    'Date': r.get('date', 'N/A'),
                    'Officer': r.get('officer_name', 'N/A'),
                    'Frequency': r.get('frequency', 'N/A'),
                    'Company': r.get('company_name', 'N/A'),
                    'Files': r.get('total_schedule_files', 0),
                    'Years': r.get('total_years', 0),
                    'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                    'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                    'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
                } for r in schedule_reports])

                # Sort DataFrame
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date', ascending=(sort_order == "Oldest First"))

                # Export buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df.to_excel(writer, sheet_name='Schedule Reports', index=False)
                        workbook = writer.book
                        worksheet = writer.sheets['Schedule Reports']
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#0066cc',
                            'font_color': 'white'
                        })
                        for col_num, value in enumerate(df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=buffer.getvalue(),
                        file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.ms-excel",
                        use_container_width=True
                    )

                with col2:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📄 Download CSV",
                        data=csv,
                        file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                with col3:
                    pdf_buffer = BytesIO()
                    doc = SimpleDocTemplate(
                        pdf_buffer,
                        pagesize=landscape(letter)
                    )
                    elements = []
                    data = [df.columns.values.tolist()] + df.values.tolist()
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 14),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    elements.append(table)
                    doc.build(elements)
                    
                    st.download_button(
                        label="📑 Download PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                # Display dataframe
                st.dataframe(
                    df,
                    column_config={
                        "Date": st.column_config.DateColumn(
                            "Date",
                            format="YYYY-MM-DD",
                            width="medium"
                        ),
                        "Officer": st.column_config.TextColumn(
                            "Officer",
                            width="medium"
                        ),
                        "Frequency": st.column_config.TextColumn(
                            "Frequency",
                            width="small"
                        ),
                        "Company For Schedule Upload": st.column_config.TextColumn(
                            "Company For Schedule Upload",
                            width="medium"
                        ),
                        "Files": st.column_config.NumberColumn(
                            "Files",
                            help="Total schedule files processed",
                            width="small"
                        ),
                        "Years": st.column_config.NumberColumn(
                            "Years",
                            help="Total years processed",
                            width="small"
                        ),
                        "Tasks": st.column_config.TextColumn(
                            "Tasks",
                            width="large"
                        ),
                        "Challenges": st.column_config.TextColumn(
                            "Challenges",
                            width="large"
                        ),
                        "Solutions": st.column_config.TextColumn(
                            "Solutions",
                            width="large"
                        )
                    },
                    hide_index=True,
                    use_container_width=True  # Only one instance of use_container_width
                )
            else:
                st.info("No Schedule Upload Reports found")

        # Global Deposit Reports Tab
        with tab2:
            if global_reports:
                st.write(f"Found {len(global_reports)} Global Deposit Reports")
                
                # Create DataFrame
                df = pd.DataFrame([{
                    'Date': r.get('date', 'N/A'),
                    'Officer': r.get('officer_name', 'N/A'),
                    'Frequency': r.get('frequency', 'N/A'),
                    'Companies': r.get('companies_assigned', '').strip().replace('\n', ', '),
                    'Total': r.get('total_companies', 0),
                    'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                    'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                    'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
                } for r in global_reports])

                # Sort DataFrame
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date', ascending=(sort_order == "Oldest First"))

                # Export buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df.to_excel(writer, sheet_name='Global Reports', index=False)
                        workbook = writer.book
                        worksheet = writer.sheets['Global Reports']
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#0066cc',
                            'font_color': 'white'
                        })
                        for col_num, value in enumerate(df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=buffer.getvalue(),
                        file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.ms-excel",
                        use_container_width=True
                    )

                with col2:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📄 Download CSV",
                        data=csv,
                        file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                with col3:
                    pdf_buffer = BytesIO()
                    doc = SimpleDocTemplate(
                        pdf_buffer,
                        pagesize=landscape(letter)
                    )
                    elements = []
                    data = [df.columns.values.tolist()] + df.values.tolist()
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 14),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    elements.append(table)
                    doc.build(elements)
                    
                    st.download_button(
                        label="📑 Download PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                # Display dataframe
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "Date": st.column_config.DateColumn(
                            "Date",
                            format="YYYY-MM-DD",
                            width="medium"
                        ),
                        "Officer": st.column_config.TextColumn(
                            "Officer",
                            width="medium"
                        ),
                        "Frequency": st.column_config.TextColumn(
                            "Frequency",
                            width="small"
                        ),
                        "Companies": st.column_config.TextColumn(
                            "Companies Assigned For Global Deposit",
                            width="large"
                        ),
                        "Total Companies Assigned For Global Deposit": st.column_config.NumberColumn(
                            "Total Companies Assigned For Global Deposit",
                            help="Total number of companies assigned for global deposit",
                            width="small"
                        ),
                        "Tasks": st.column_config.TextColumn(
                            "Tasks",
                            width="large"
                        ),
                        "Challenges": st.column_config.TextColumn(
                            "Challenges",
                            width="large"
                        ),
                        "Solutions": st.column_config.TextColumn(
                            "Solutions",
                            width="large"
                        )
                    },
                    hide_index=True
                )
            else:
                st.info("No Global Deposit Reports found")

        # Other Reports Tab
        with tab3:
            if other_reports:
                df = pd.DataFrame([{
                    'Date': r.get('date', 'N/A'),
                    'Officer': r.get('officer_name', 'Unknown'),
                    'Frequency': r.get('frequency', 'Daily'),
                    'Company': r.get('company_name', 'N/A'),
                    'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                    'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                    'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
                } for r in other_reports])

                # Sort DataFrame
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date', ascending=(sort_order == "Oldest First"))

                # Display dataframe first
                st.dataframe(
                    data=df,
                    column_config={
                        "Date": st.column_config.DateColumn(
                            "Date",
                            format="YYYY-MM-DD",
                            width="medium"
                        ),
                        "Officer": st.column_config.TextColumn(
                            "Officer",
                            width="medium"
                        ),
                        "Frequency": st.column_config.TextColumn(
                            "Frequency",
                            width="small"
                        ),
                        "Company": st.column_config.TextColumn(
                            "Company",
                            width="medium"
                        ),
                        "Tasks": st.column_config.TextColumn(
                            "Tasks",
                            width="large"
                        ),
                        "Challenges": st.column_config.TextColumn(
                            "Challenges",
                            width="large"
                        ),
                        "Solutions": st.column_config.TextColumn(
                            "Solutions",
                            width="large"
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )

                # Export buttons in columns
                st.write("Export Options:")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df.to_excel(writer, sheet_name='Other Reports', index=False)
                        workbook = writer.book
                        worksheet = writer.sheets['Other Reports']
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#0066cc',
                            'font_color': 'white'
                        })
                        for col_num, value in enumerate(df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=buffer.getvalue(),
                        file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.ms-excel"
                    )

                with col2:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📄 Download CSV",
                        data=csv,
                        file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )

                with col3:
                    pdf_buffer = BytesIO()
                    doc = SimpleDocTemplate(
                        pdf_buffer,
                        pagesize=landscape(letter)
                    )
                    elements = []
                    data = [df.columns.values.tolist()] + df.values.tolist()
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 14),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    elements.append(table)
                    doc.build(elements)
                    
                    st.download_button(
                        label="📑 Download PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
            else:
                st.info("No Other Reports found")
    else:
        st.info("No reports found.")

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

# Edit Reports
def edit_report():
    """Allow officers to edit their submitted reports"""
    st.header("Edit Reports")
    
    # Get list of existing officer folders
    officer_folders = [
        d for d in os.listdir(REPORTS_DIR) 
        if os.path.isdir(os.path.join(REPORTS_DIR, d))
        and d not in ADDITIONAL_FOLDERS
    ]
    
    # Officer selection
    officer_name = st.selectbox(
        "Select Officer",
        ["Select Officer..."] + sorted(officer_folders)
    )
    
    if officer_name and officer_name != "Select Officer...":
        # Load officer's reports
        reports = load_reports(officer_name)
        if not reports:
            st.info("No reports found for this officer.")
            return
        
        # Sort reports by date (most recent first)
        reports.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Display reports in expandable format
        for index, report in enumerate(reports):
            report_id = f"{report.get('date', 'unknown')}_{index}"  # Create unique identifier
            
            with st.expander(f"📄 {report.get('date', 'No date')} - {report.get('type', 'Unknown Type')}"):
                # Show current status
                st.write(f"**Status:** {report.get('status', 'Unknown')}")
                
                # Only allow editing if status is 'Needs Attention' or 'Pending Review'
                if report.get('status') in ['Needs Attention', 'Pending Review']:
                    # Report type and frequency
                    report_type = report.get('type')
                    
                    # Dynamic fields based on report type
                    col1, col2, col3 = st.columns([3, 2, 3])
                    
                    if report_type == "Schedule Upload Report":
                        with col1:
                            company_name = st.text_input(
                                "Company Name",
                                value=report.get('company_name', ''),
                                key=f"edit_company_{report_id}"
                            )
                        with col2:
                            total_files = st.number_input(
                                "Total Schedule Files",
                                value=int(report.get('total_schedule_files', 0)),
                                key=f"edit_files_{report_id}"
                            )
                        with col3:
                            total_years = st.number_input(
                                "Total Years",
                                value=int(report.get('total_years', 0)),
                                key=f"edit_years_{report_id}"
                            )
                    
                    elif report_type == "Global Deposit Assigning":
                        with col1:
                            companies_assigned = st.text_area(
                                "List Companies Assigned For Global Deposit",
                                value=report.get('companies_assigned', ''),
                                height=150,
                                key=f"edit_companies_{report_id}"
                            )
                        with col2:
                            total_companies = st.number_input(
                                "Total Companies",
                                value=int(report.get('total_companies', 0)),
                                key=f"edit_total_{report_id}"
                            )
                    
                    else:  # Other Report
                        with col1:
                            other_company = st.text_input(
                                "Company Name or Please Specify",
                                value=report.get('company_name', ''),
                                key=f"edit_other_{report_id}"
                            )
                    
                    # Common fields for all report types
                    tasks = st.text_area(
                        "Tasks Completed",
                        value=report.get('tasks', ''),
                        key=f"edit_tasks_{report_id}"
                    )
                    challenges = st.text_area(
                        "Challenges Encountered",
                        value=report.get('challenges', ''),
                        key=f"edit_challenges_{report_id}"
                    )
                    solutions = st.text_area(
                        "Proposed Solutions",
                        value=report.get('solutions', ''),
                        key=f"edit_solutions_{report_id}"
                    )
                    
                    # Save changes button
                    if st.button("Save Changes", key=f"edit_save_{report_id}"):
                        try:
                            # Update report data based on type
                            if report_type == "Schedule Upload Report":
                                report.update({
                                    'company_name': company_name,
                                    'total_schedule_files': total_files,
                                    'total_years': total_years
                                })
                            elif report_type == "Global Deposit Assigning":
                                report.update({
                                    'companies_assigned': companies_assigned,
                                    'total_companies': total_companies
                                })
                            else:  # Other Report
                                report.update({
                                    'company_name': other_company
                                })
                            
                            # Update common fields
                            report.update({
                                'tasks': tasks,
                                'challenges': challenges,
                                'solutions': solutions,
                                'last_edited': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            
                            # Save updated report
                            save_report(officer_name, report)
                            st.success("Report updated successfully! 📝")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error updating report: {str(e)}")
                
                else:
                    # Display read-only view for approved reports
                    st.info("This report has been approved and cannot be edited.")
                    st.write("**Content:**")
                    st.write(report.get('tasks', 'No tasks specified'))
                    if report.get('reviewer_notes'):
                        st.write("**Reviewer Notes:**", report.get('reviewer_notes'))

# def load_reports():
#     """Load all reports from all officer folders"""
#     reports_data = []
#     try:
#         # Get all officer folders
#         for officer_folder in os.listdir(REPORTS_DIR):
#             officer_path = os.path.join(REPORTS_DIR, officer_folder)
            
#             # Skip if not a directory or is in ADDITIONAL_FOLDERS
#             if not os.path.isdir(officer_path) or officer_folder in ADDITIONAL_FOLDERS:
#                 continue
                
#             # Get all report files for this officer
#             report_files = [f for f in os.listdir(officer_path) 
#                           if f.endswith('.json') and f != 'template.json']
            
#             for report_file in report_files:
#                 try:
#                     with open(os.path.join(officer_path, report_file), 'r') as f:
#                         report_data = json.load(f)
#                         # Ensure officer name is included
#                         if 'officer_name' not in report_data:
#                             report_data['officer_name'] = officer_folder
#                         reports_data.append(report_data)
#                 except Exception as e:
#                     st.error(f"Error loading report {report_file} for {officer_folder}: {str(e)}")
#                     continue
    
#     except Exception as e:
#         st.error(f"Error accessing reports directory: {str(e)}")
    
#     return reports_data

def load_tasks():
    """Load all tasks from the tasks directory"""
    tasks = []
    try:
        if os.path.exists(TASK_DIR):
            for task_file in os.listdir(TASK_DIR):
                if task_file.endswith('.json'):
                    with open(os.path.join(TASK_DIR, task_file), 'r') as f:
                        task = json.load(f)
                        tasks.append(task)
    except Exception as e:
        st.error(f"Error loading tasks: {str(e)}")
    return tasks

def get_team_productivity():
    """Get combined productivity data from reports and tasks"""
    reports_data = load_reports()
    tasks_data = load_tasks()
    
    productivity_data = {}
    
    # Process Reports Data
    for report in reports_data:
        officer = report.get('officer_name', 'Unknown')
        if officer not in productivity_data:
            productivity_data[officer] = {
                'total_reports': 0,
                'reports_completed': 0,
                'reports_pending': 0,
                'reports_in_progress': 0,
                'tasks_completed': 0,
                'tasks_pending': 0,
                'tasks_in_progress': 0,
                'tasks_overdue': 0
            }
        
        productivity_data[officer]['total_reports'] += 1
        status = report.get('status', 'Pending Review')
        
        if status == 'Approved':
            productivity_data[officer]['reports_completed'] += 1
        elif status == 'Pending Review':
            productivity_data[officer]['reports_pending'] += 1
        elif status == 'Needs Attention':
            productivity_data[officer]['reports_in_progress'] += 1

    # Process Tasks Data
    for task in tasks_data:
        assigned_to = task.get('assigned_to', 'Unknown')
        if assigned_to not in productivity_data:
            productivity_data[assigned_to] = {
                'total_reports': 0,
                'reports_completed': 0,
                'reports_pending': 0,
                'reports_in_progress': 0,
                'tasks_completed': 0,
                'tasks_pending': 0,
                'tasks_in_progress': 0,
                'tasks_overdue': 0
            }
        
        status = task.get('status', 'Pending')
        if status == 'Completed':
            productivity_data[assigned_to]['tasks_completed'] += 1
        elif status == 'Pending':
            productivity_data[assigned_to]['tasks_pending'] += 1
        elif status == 'In Progress':
            productivity_data[assigned_to]['tasks_in_progress'] += 1
        elif status == 'Overdue':
            productivity_data[assigned_to]['tasks_overdue'] += 1
            
    return productivity_data

def display_team_productivity():
    """Display team productivity metrics"""
    st.subheader("Team Productivity Overview")
    
    productivity_data = get_team_productivity()
    
    if not productivity_data:
        st.info("No productivity data available")
        return
        
    # Convert to DataFrame for display
    df = pd.DataFrame.from_dict(productivity_data, orient='index')
    
    # Display metrics table
    st.dataframe(
        df,
        column_config={
            "total_reports": st.column_config.NumberColumn("Total Reports"),
            "reports_completed": st.column_config.NumberColumn("Reports Completed"),
            "reports_pending": st.column_config.NumberColumn("Reports Pending"),
            "reports_in_progress": st.column_config.NumberColumn("Reports In Progress"),
            "tasks_completed": st.column_config.NumberColumn("Tasks Completed"),
            "tasks_pending": st.column_config.NumberColumn("Tasks Pending"),
            "tasks_in_progress": st.column_config.NumberColumn("Tasks In Progress"),
            "tasks_overdue": st.column_config.NumberColumn("Tasks Overdue")
        },
        use_container_width=True
    )
    
    # Create visualization
    fig = go.Figure()
    
    for officer in productivity_data.keys():
        fig.add_trace(go.Bar(
            name=officer,
            x=['Reports Completed', 'Reports Pending', 'Reports In Progress', 
               'Tasks Completed', 'Tasks Pending', 'Tasks In Progress', 'Tasks Overdue'],
            y=[
                productivity_data[officer]['reports_completed'],
                productivity_data[officer]['reports_pending'],
                productivity_data[officer]['reports_in_progress'],
                productivity_data[officer]['tasks_completed'],
                productivity_data[officer]['tasks_pending'],
                productivity_data[officer]['tasks_in_progress'],
                productivity_data[officer]['tasks_overdue']
            ]
        ))
    
    fig.update_layout(
        title="Team Productivity Breakdown",
        barmode='group',
        xaxis_title="Status",
        yaxis_title="Count"
    )
    
    st.plotly_chart(fig, use_container_width=True)

def get_report_insights():
    """Generate insights from reports data"""
    reports_data = load_reports()
    insights = {
        'total_reports': len(reports_data),
        'by_status': {},
        'by_officer': {},
        'recent_activity': [],
        'common_challenges': {}
    }
    
    for report in reports_data:
        # Status counts
        status = report.get('status', 'Unknown')
        insights['by_status'][status] = insights['by_status'].get(status, 0) + 1
        
        # Officer activity
        officer = report.get('officer_name', 'Unknown')
        if officer not in insights['by_officer']:
            insights['by_officer'][officer] = {
                'total': 0,
                'completed': 0,
                'pending': 0
            }
        insights['by_officer'][officer]['total'] += 1
        
        # Recent activity
        insights['recent_activity'].append({
            'date': report.get('date'),
            'officer': officer,
            'type': report.get('type'),
            'status': status
        })
        
        # Common challenges
        if 'challenges' in report:
            for challenge in report['challenges']:
                insights['common_challenges'][challenge] = insights['common_challenges'].get(challenge, 0) + 1
    
    # Sort recent activity by date
    insights['recent_activity'].sort(key=lambda x: x['date'], reverse=True)
    insights['recent_activity'] = insights['recent_activity'][:10]
    
    return insights

def show_summaries():
    """Enhanced Report Summaries Dashboard with all requested features"""
    st.title("Report Summaries Dashboard")

    # Sidebar Filters
    st.sidebar.header("Filters & Search")
    
    # Date Range Filter
    date_filter = st.sidebar.selectbox(
        "Date Range",
        ["All Time", "Today", "This Week", "This Month", "Custom"]
    )
    
    if date_filter == "Custom":
        start_date = st.sidebar.date_input("Start Date")
        end_date = st.sidebar.date_input("End Date")
    
    # Officer Filter
    reports_data = load_reports()
    officers = list(set(r.get('officer_name') for r in reports_data))
    selected_officer = st.sidebar.selectbox("Filter by Officer", ["All"] + officers)
    
    # Status Filter
    status_filter = st.sidebar.selectbox(
        "Filter by Status",
        ["All", "Completed", "In Progress", "Pending Review"]
    )
    
    # Company Search
    company_search = st.sidebar.text_input("Search by Company Name")
    
    # Keyword Search
    keyword_search = st.sidebar.text_input("Search by Keywords")

    # Create 6 tabs instead of 7 to match your UI
    overview_tab, breakdown_tab, insights_tab, recent_tab, alerts_tab, review_tab = st.tabs([
        "Overview",
        "Reports Breakdown", 
        "Visual Insights",
        "Recent Reports",
        "Alerts",
        "Review Reports"
    ])

    # 1. Overview Tab
    with overview_tab:
        st.subheader("High-Level Summary")
        
        # Summary Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            daily_reports = len([r for r in reports_data if r.get('frequency') == 'Daily'])
            st.metric("Daily Reports", daily_reports)
        with col2:
            weekly_reports = len([r for r in reports_data if r.get('frequency') == 'Weekly'])
            st.metric("Weekly Reports", weekly_reports)
        with col3:
            monthly_reports = len([r for r in reports_data if r.get('frequency') == 'Monthly'])
            st.metric("Monthly Reports", monthly_reports)
        with col4:
            pending_reports = len([r for r in reports_data if r.get('status') == 'Pending Review'])
            st.metric("Pending Review", pending_reports)

        # Team Productivity Overview
        st.subheader("Team Productivity Overview")
        
        # Get combined productivity data
        productivity_data = get_team_productivity()
        
        if productivity_data:
            # Convert to DataFrame for display
            df = pd.DataFrame.from_dict(productivity_data, orient='index')
            
            # Display metrics table
            st.dataframe(
                df,
                column_config={
                    "total_reports": st.column_config.NumberColumn("Total Reports"),
                    "reports_completed": st.column_config.NumberColumn("Reports Completed"),
                    "reports_pending": st.column_config.NumberColumn("Reports Pending"),
                    "reports_in_progress": st.column_config.NumberColumn("Reports In Progress"),
                    "tasks_completed": st.column_config.NumberColumn("Tasks Completed"),
                    "tasks_pending": st.column_config.NumberColumn("Tasks Pending"),
                    "tasks_in_progress": st.column_config.NumberColumn("Tasks In Progress"),
                    "tasks_overdue": st.column_config.NumberColumn("Tasks Overdue")
                },
                use_container_width=True
            )
            
            # Create visualization
            fig = go.Figure()
            
            for officer in productivity_data.keys():
                fig.add_trace(go.Bar(
                    name=officer,
                    x=['Reports Completed', 'Reports Pending', 'Reports In Progress', 
                       'Tasks Completed', 'Tasks Pending', 'Tasks In Progress', 'Tasks Overdue'],
                    y=[
                        productivity_data[officer]['reports_completed'],
                        productivity_data[officer]['reports_pending'],
                        productivity_data[officer]['reports_in_progress'],
                        productivity_data[officer]['tasks_completed'],
                        productivity_data[officer]['tasks_pending'],
                        productivity_data[officer]['tasks_in_progress'],
                        productivity_data[officer]['tasks_overdue']
                    ]
                ))
            
            fig.update_layout(
                title="Team Productivity Breakdown",
                barmode='group',
                xaxis_title="Status",
                yaxis_title="Count"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No productivity data available")

    # 2. Reports Breakdown Tab
    with breakdown_tab:
        st.subheader("Reports Analysis")
        
        # Reports by Company
        company_data = {}
        for report in reports_data:
            company = report.get('company_name', 'Unknown')
            if company not in company_data:
                company_data[company] = 1
            else:
                company_data[company] += 1
        
        # Create and display company chart
        fig_companies = go.Figure(data=[
            go.Bar(
                x=list(company_data.keys()),
                y=list(company_data.values())
            )
        ])
        fig_companies.update_layout(title="Reports by Company")
        st.plotly_chart(fig_companies, use_container_width=True)

        # Common Challenges Analysis
        st.subheader("Common Challenges")
        challenges = [r.get('challenges', '') for r in reports_data if r.get('challenges')]
        if challenges:
            # Create word cloud of challenges
            wordcloud = WordCloud(width=800, height=400, background_color='white').generate(' '.join(challenges))
            st.image(wordcloud.to_array())

    # 3. Visual Insights Tab
    with insights_tab:
        st.subheader("Visual Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Reports per Officer Bar Chart
            officer_counts = {}
            for report in reports_data:
                officer = report.get('officer_name', 'Unknown')
                officer_counts[officer] = officer_counts.get(officer, 0) + 1
            
            fig_officers = go.Figure(data=[
                go.Bar(
                    x=list(officer_counts.keys()),
                    y=list(officer_counts.values())
                )
            ])
            fig_officers.update_layout(title="Reports per Officer")
            st.plotly_chart(fig_officers, use_container_width=True)
        
        with col2:
            # Status Distribution Pie Chart
            status_counts = {}
            for report in reports_data:
                status = report.get('status', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            fig_status = go.Figure(data=[
                go.Pie(
                    labels=list(status_counts.keys()),
                    values=list(status_counts.values())
                )
            ])
            fig_status.update_layout(title="Reports by Status")
            st.plotly_chart(fig_status, use_container_width=True)

    # 4. Recent Reports Tab
    with recent_tab:
        st.subheader("Latest Reports")
        
        recent_reports = sorted(
            reports_data,
            key=lambda x: datetime.strptime(x.get('date', '1900-01-01'), '%Y-%m-%d'),
            reverse=True
        )[:10]
        
        for report in recent_reports:
            with st.expander(f"{report.get('date')} - {report.get('officer_name')} - {report.get('type')}"):
                st.write(f"**Company:** {report.get('company_name', 'N/A')}")
                st.write(f"**Status:** {report.get('status', 'N/A')}")
                st.write(f"**Tasks:** {report.get('tasks', 'N/A')}")
                if report.get('challenges'):
                    st.write(f"**Challenges:** {report.get('challenges')}")
                if report.get('solutions'):
                    st.write(f"**Solutions:** {report.get('solutions')}")

       # 5. Alerts Tab
    with alerts_tab:
        st.subheader("Notifications & Alerts")
        
        # Get current date
        today = datetime.now()
        
        # Create columns for different alert types
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Reports needing attention
            attention_reports = [r for r in reports_data if r.get('status') == 'Needs Attention']
            with st.container(border=True):
                st.markdown("### ⚠️ Needs Attention")
                if attention_reports:
                    for report in attention_reports[:3]:  # Show top 3
                        st.warning(
                            f"**{report.get('officer_name', 'Unknown Officer')}** - {report.get('date', 'No date')}\n\n"
                            f"Type: {report.get('type', 'Unknown Type')}"
                        )
                    if len(attention_reports) > 3:
                        st.info(f"+ {len(attention_reports) - 3} more reports need attention")
                else:
                    st.success("No reports need attention")
        
        with col2:
            # Check for pending reviews
            pending = [r for r in reports_data if r.get('status') == 'Pending Review']
            with st.container(border=True):
                st.markdown("### 🕒 Pending Review")
                if pending:
                    st.warning(f"{len(pending)} reports pending review")
                    for report in pending[:3]:  # Show top 3
                        st.info(
                            f"**{report.get('officer_name', 'Unknown Officer')}** - {report.get('date', 'No date')}\n\n"
                            f"Type: {report.get('type', 'Unknown Type')}"
                        )
                    if len(pending) > 3:
                        st.info(f"+ {len(pending) - 3} more reports pending review")
                else:
                    st.success("No pending reviews")
        
        with col3:
            # Check for inactive officers
            with st.container(border=True):
                st.markdown("### 👤 Inactive Officers")
                inactive_found = False
                for officer in officers:
                    last_report = max([
                        datetime.strptime(r.get('date', '1900-01-01'), '%Y-%m-%d')
                        for r in reports_data
                        if r.get('officer_name') == officer
                    ], default=None)
                    
                    if last_report and (today - last_report).days > 7:
                        inactive_found = True
                        st.warning(f"⚠️ {officer} hasn't submitted a report in {(today - last_report).days} days")
                
                if not inactive_found:
                    st.success("All officers are active")

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
    
    # Add custom CSS for Summary Cards
    st.markdown("""
        <style>
        .stat-card {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
        .stat-card h3 {
            color: #ffffff;
            margin-bottom: 10px;
        }
        .stat-card p {
            color: #dddddd;
        }
        </style>
    """, unsafe_allow_html=True)

    # Summary Cards
    col1, col2, col3 = st.columns(3)
    with col1:
        top_officer = df['officer_name'].value_counts().index[0]
        top_reports = df['officer_name'].value_counts().iloc[0]
        st.markdown(f"""
            <div class="stat-card">
                <h3>🏆 Top Performer</h3>
                <p>{top_officer}<br>{top_reports} reports</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        current_month_name = datetime.now().strftime('%B')
        monthly_reports = len(df[df['date'].dt.month == datetime.now().month])
        st.markdown(f"""
            <div class="stat-card">
                <h3>📊 {current_month_name} Overview</h3>
                <p>{monthly_reports} reports submitted</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        total_companies = len(df['company_name'].unique())
        st.markdown(f"""
            <div class="stat-card">
                <h3>🏢 Company Coverage</h3>
                <p>{total_companies} companies monitored</p>
            </div>
        """, unsafe_allow_html=True)

    # Interactive KPI Cards with Trends
    st.subheader("Key Performance Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_month = len(df[df['date'].dt.month == datetime.now().month])
        last_month = len(df[df['date'].dt.month == (datetime.now().month - 1)])
        delta = current_month - last_month
        st.metric(
            "Reports This Month", 
            current_month,
            delta=delta,
            delta_color="normal"
        )
    
    with col2:
        current_officers = len(df[df['date'].dt.month == datetime.now().month]['officer_name'].unique())
        last_officers = len(df[df['date'].dt.month == (datetime.now().month - 1)]['officer_name'].unique())
        delta_officers = current_officers - last_officers
        st.metric(
            "Active Officers",
            current_officers,
            delta=delta_officers,
            delta_color="normal"
        )
    
    with col3:
        current_companies = len(df[df['date'].dt.month == datetime.now().month]['company_name'].unique())
        last_companies = len(df[df['date'].dt.month == (datetime.now().month - 1)]['company_name'].unique())
        delta_companies = current_companies - last_companies
        st.metric(
            "Companies Covered",
            current_companies,
            delta=delta_companies,
            delta_color="normal"
        )
    
    with col4:
        avg_reports = round(df.groupby('officer_name').size().mean(), 1)
        st.metric(
            "Avg Reports/Officer",
            avg_reports,
            delta=None
        )

    # Two columns for charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie Chart: Report Types Distribution
        st.subheader("Report Types Distribution")
        report_types = df['type'].value_counts()
        fig_pie = go.Figure(data=[go.Pie(
            labels=report_types.index,
            values=report_types.values,
            hole=0.4,
            marker_colors=['#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e74c3c']
        )])
        fig_pie.update_layout(
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Bar Chart: Top Companies
        st.subheader("Top Companies by Report Count")
        top_companies = df['company_name'].value_counts().head(10)
        fig_companies = go.Figure(data=[go.Bar(
            x=top_companies.index,
            y=top_companies.values,
            marker_color='#3498db'
        )])
        fig_companies.update_layout(
            height=400,
            xaxis_tickangle=45,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        st.plotly_chart(fig_companies, use_container_width=True)

    # Progress Gauges
    st.subheader("Monthly Progress Tracking")
    col1, col2 = st.columns(2)
    
    with col1:
        # Monthly target progress
        target_reports = 100  # Adjust this target as needed
        progress = min((current_month / target_reports) * 100, 100)
        
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=progress,
            title={'text': "Monthly Reports Progress"},
            delta={'reference': 100},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "rgba(50, 168, 212, 0.8)"},
                'steps': [
                    {'range': [0, 50], 'color': "rgba(255, 255, 255, 0.1)"},
                    {'range': [50, 75], 'color': "rgba(255, 255, 255, 0.2)"},
                    {'range': [75, 100], 'color': "rgba(255, 255, 255, 0.3)"}
                ]
            }
        ))
        fig_gauge.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=300
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col2:
        # Company coverage progress
        target_companies = 50  # Adjust this target as needed
        company_progress = min((current_companies / target_companies) * 100, 100)
        
        fig_company_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=company_progress,
            title={'text': "Company Coverage Progress"},
            delta={'reference': 100},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "rgba(46, 204, 113, 0.8)"},
                'steps': [
                    {'range': [0, 50], 'color': "rgba(255, 255, 255, 0.1)"},
                    {'range': [50, 75], 'color': "rgba(255, 255, 255, 0.2)"},
                    {'range': [75, 100], 'color': "rgba(255, 255, 255, 0.3)"}
                ]
            }
        ))
        fig_company_gauge.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=300
        )
        st.plotly_chart(fig_company_gauge, use_container_width=True)

    # Activity Heatmap
    st.subheader("Report Activity Patterns")
    
    # Create heatmap data
    df['dow'] = df['date'].dt.dayofweek
    df['hour'] = df['date'].dt.hour
    activity_data = df.groupby(['dow', 'hour']).size().unstack(fill_value=0)
    
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=activity_data.values,
        x=[f"{i}:00" for i in range(24)],
        y=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        colorscale='Viridis'
    ))
    
    fig_heatmap.update_layout(
        title="Report Submission Patterns by Day and Hour",
        xaxis_title="Hour of Day",
        yaxis_title="Day of Week",
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white')
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

        # Animated Time Series
    st.subheader("Report Trends Over Time")
    
    # Create a fresh copy of the data for trends
    trends_df = df.copy()
    
    # Extract year and month
    trends_df['year'] = trends_df['date'].dt.year
    trends_df['month'] = trends_df['date'].dt.month
    
    # Group by year and month
    monthly_counts = trends_df.groupby(['year', 'month']).size().reset_index(name='total_reports')
    
    # Create a simple line chart without animation
    fig_trends = go.Figure()
    
    for year in monthly_counts['year'].unique():
        year_data = monthly_counts[monthly_counts['year'] == year]
        
        fig_trends.add_trace(go.Scatter(
            x=year_data['month'],
            y=year_data['total_reports'],
            name=str(year),
            mode='lines+markers'
        ))
    
    fig_trends.update_layout(
        title='Monthly Report Submissions by Year',
        xaxis=dict(
            title='Month',
            tickmode='array',
            ticktext=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            tickvals=list(range(1, 13))
        ),
        yaxis=dict(title='Number of Reports'),
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=True,
        legend=dict(
            title='Year',
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_trends, use_container_width=True)

        # Officer Report Distribution
    st.subheader("Reports Distribution by Officer")
    
    # Calculate officer report counts
    officer_reports = df['officer_name'].value_counts()
    
    # Create pie chart for officer distribution with your custom colors
    fig_officer_dist = go.Figure(data=[go.Pie(
        labels=officer_reports.index,
        values=officer_reports.values,
        hole=0.4,  # Makes it a donut chart
        textinfo='label+percent+value',  # Shows officer name, percentage, and number of reports
        textposition='outside',
        marker=dict(
            colors=['#D52DB7', '#6050DC', '#FF2E7E', '#FF6B45', '#FFAB05'],  # Your specified colors
            line=dict(color='rgba(255, 255, 255, 0.5)', width=2)
        ),
        pull=[0.1 if i == 0 else 0 for i in range(len(officer_reports))]  # Pulls out the highest value slice
    )])
    
    # Update layout
    fig_officer_dist.update_layout(
        title={
            'text': f"Total Reports by Officer ({len(officer_reports)} Officers)",
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        height=500,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', size=12),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        ),
        annotations=[
            dict(
                text=f'Total Reports: {sum(officer_reports.values)}',
                x=0.5,
                y=0.5,
                font=dict(size=14),
                showarrow=False
            )
        ]
    )
    
    # Display the chart
    st.plotly_chart(fig_officer_dist, use_container_width=True)
    
    # Add a detailed breakdown in an expander
    with st.expander("📊 Detailed Officer Report Breakdown"):
        # Create a DataFrame for the breakdown
        officer_breakdown = pd.DataFrame({
            'Officer': officer_reports.index,
            'Total Reports': officer_reports.values,
            'Percentage': (officer_reports.values / sum(officer_reports.values) * 100).round(2)
        })
        
        # Display the breakdown as a styled table
        st.dataframe(
            officer_breakdown,
            column_config={
                "Officer": st.column_config.TextColumn(
                    "Officer Name",
                    width="medium"
                ),
                "Total Reports": st.column_config.NumberColumn(
                    "Total Reports",
                    format="%d",
                    width="small"
                ),
                "Percentage": st.column_config.NumberColumn(
                    "% of Total",
                    format="%.2f%%",
                    width="small"
                )
            },
            hide_index=True,
            use_container_width=True
        )
    
        # After your charts and before the DataTable, add this section:
    
    # Report Review Section
        # Report Review Section in your dashboard
    st.subheader("📋 Recent Reports for Review")
    
    # Create tabs for different report statuses
    review_tab1, review_tab2, review_tab3 = st.tabs(["Pending Review", "Approved", "Needs Attention"])
    
    with review_tab1:
        pending_reports = [r for r in df.to_dict('records') if r.get('status') == 'Pending Review']
        if pending_reports:
            for index, report in enumerate(pending_reports[:5]):  # Show last 5 pending reports
                report_id = f"{report.get('date', 'unknown')}_{index}"  # Create unique identifier
                
                with st.expander(f"📄 {report.get('officer_name', 'Unknown Officer')} - {report.get('date', 'No date')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Officer:**", report.get('officer_name', 'Unknown'))
                        st.write("**Date:**", report.get('date', 'No date'))
                        st.write("**Type:**", report.get('type', 'No type'))
                    with col2:
                        st.write("**Status:**", report.get('status', 'Unknown'))
                        st.write("**Company:**", report.get('company_name', 'No company'))
                    
                    # Report Content
                    st.write("**Tasks:**")
                    st.write(report.get('tasks', 'No tasks available'))
                    
                    # Review Actions
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✅ Approve", key=f"dashboard_approve_{report_id}"):
                            try:
                                report['status'] = 'Approved'
                                report['review_date'] = datetime.now().strftime("%Y-%m-%d")
                                report['reviewer_notes'] = st.session_state.get(f"dashboard_notes_{report_id}", '')
                                save_report(report['officer_name'], report)
                                st.success("Report approved successfully! ✅")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error approving report: {str(e)}")
                    
                    with col2:
                        if st.button("⚠️ Needs Attention", key=f"dashboard_attention_{report_id}"):
                            try:
                                report['status'] = 'Needs Attention'
                                report['review_date'] = datetime.now().strftime("%Y-%m-%d")
                                report['reviewer_notes'] = st.session_state.get(f"dashboard_notes_{report_id}", '')
                                save_report(report['officer_name'], report)
                                st.warning("Report marked as needing attention! ⚠️")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating report status: {str(e)}")
                    
                    # Reviewer Notes
                    st.text_area(
                        "Review Notes",
                        key=f"dashboard_notes_{report_id}",
                        placeholder="Add your review notes here..."
                    )
        else:
            st.info("No reports pending review")

    with review_tab2:
        approved_reports = [r for r in df.to_dict('records') if r.get('status') == 'Approved']
        if approved_reports:
            for index, report in enumerate(approved_reports[:5]):
                report_id = f"{report.get('date', 'unknown')}_{index}"
                with st.expander(f"✅ {report.get('officer_name', 'Unknown Officer')} - {report.get('date', 'No date')}"):
                    st.write("**Officer:**", report.get('officer_name', 'Unknown'))
                    st.write("**Date:**", report.get('date', 'No date'))
                    st.write("**Review Date:**", report.get('review_date', 'Not specified'))
                    st.write("**Type:**", report.get('type', 'No type'))
                    st.write("**Review Notes:**", report.get('reviewer_notes', 'No notes provided'))
        else:
            st.info("No approved reports")

    with review_tab3:
        attention_reports = [r for r in df.to_dict('records') if r.get('status') == 'Needs Attention']
        if attention_reports:
            for index, report in enumerate(attention_reports[:5]):
                report_id = f"{report.get('date', 'unknown')}_{index}"
                with st.expander(f"⚠️ {report.get('officer_name', 'Unknown Officer')} - {report.get('date', 'No date')}"):
                    st.write("**Officer:**", report.get('officer_name', 'Unknown'))
                    st.write("**Date:**", report.get('date', 'No date'))
                    st.write("**Type:**", report.get('type', 'No type'))
                    st.write("**Review Notes:**", report.get('reviewer_notes', 'No notes provided'))
                    
                    if st.button("✅ Mark as Approved", key=f"dashboard_approve_attention_{report_id}"):
                        try:
                            report['status'] = 'Approved'
                            report['review_date'] = datetime.now().strftime("%Y-%m-%d")
                            save_report(report['officer_name'], report)
                            st.success("Report approved!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error approving report: {str(e)}")
        else:
            st.info("No reports needing attention")

    # Continue with your existing DataTable and export options...

        # After your review tabs section in the dashboard, add:
    
    # Data Table Section
    st.subheader("Report Data Table")
    
        # Create DataFrame for the table
    df_data = []
    for report in all_reports:
        # Get companies assigned string for Global Deposit reports
        companies_assigned = report.get('companies_assigned', '')
        if isinstance(companies_assigned, str):
            companies_assigned = companies_assigned.strip().replace('\n', ', ')
        
        # Handle company name based on report type
        if report.get('type') == "Global Deposit Assigning":
            company_name = "Global Deposit"  # Set a default value for Global Deposit reports
        else:
            company_name = report.get('company_name', 'N/A')
        
        row = {
            'Date': report.get('Date', 'N/A'),
            'Officer': report.get('Officer Name', 'Unknown'),
            'Type': report.get('Report Type', 'N/A'),
            'Status': report.get('Status', 'Pending Review'),  # Set default status if not present
            'Frequency': report.get('Frequency', 'N/A'),
            'Company': company_name,
            'Total Years': report.get('Total Years Uploaded', 'N/A'),
            'Companies Assigned': companies_assigned,
            'Total Companies': report.get('Total Companies Assigned', 'N/A'),
            'Tasks': report.get('tasks', 'N/A')[:100] + '...' if len(report.get('tasks', 'N/A')) > 100 else report.get('tasks', 'N/A'),
            'Challenges': report.get('challenges', 'N/A')[:100] + '...' if len(report.get('challenges', 'N/A')) > 100 else report.get('challenges', 'N/A'),
            'Solutions': report.get('solutions', 'N/A')[:100] + '...' if len(report.get('solutions', 'N/A')) > 100 else report.get('solutions', 'N/A'),
        }
        df_data.append(row)
    
    # Export buttons
    st.write("Export Options:")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Excel export
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Reports', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Reports']
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#0066cc',
                'font_color': 'white'
            })
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
        
        st.download_button(
            label="📥 Download Excel",
            data=buffer.getvalue(),
            file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )

    with col2:
        # CSV export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download CSV",
            data=csv,
            file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col3:
        # PDF export
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
            from reportlab.lib.units import inch
            
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=landscape(letter),
                rightMargin=30,
                leftMargin=30,
                topMargin=30,
                bottomMargin=30
            )
            elements = []
            
            # Prepare data for PDF table - convert all values to strings
            pdf_data = []
            # Add headers
            pdf_data.append([str(col) for col in df.columns])
            # Add rows with string conversion
            for _, row in df.iterrows():
                pdf_row = []
                for value in row:
                    # Convert any non-string values to strings
                    if value is None:
                        pdf_row.append('')
                    elif isinstance(value, (int, float)):
                        pdf_row.append(str(value))
                    else:
                        # Limit text length to prevent overflow
                        text = str(value)
                        if len(text) > 100:
                            text = text[:97] + '...'
                        pdf_row.append(text)
                pdf_data.append(pdf_row)
            
            # Create table with wrapped text
            table = Table(pdf_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('WORDWRAP', (0, 0), (-1, -1), True),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
            doc.build(elements)
            
            st.download_button(
                label="📑 Download PDF",
                data=pdf_buffer.getvalue(),
                file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Error generating PDF: {str(e)}")

    # Add a small space between buttons and table
    st.write("")
    
    # Display the data table with enhanced column configuration
    st.dataframe(
        df,
        column_config={
            "Date": st.column_config.DateColumn("Date"),
            "Officer": st.column_config.TextColumn("Officer"),
            "Type": st.column_config.TextColumn(
                "Report Type",
                help="Schedule Upload Report or Global Deposit Assigning"
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                help="Current status of the report"
            ),
            "Frequency": st.column_config.TextColumn(
                "Frequency",
                help="Daily, Weekly, or Monthly"
            ),
            "Company": st.column_config.TextColumn(
                "Company",
                width="medium"
            ),
            "Total Years": st.column_config.NumberColumn(
                "Total Years",
                width="small"
            ),
            "Companies Assigned": st.column_config.TextColumn(
                "Companies Assigned",
                width="large"
            ),
            "Total Companies": st.column_config.NumberColumn(
                "Total Companies",
                width="small"
            ),
            "Tasks": st.column_config.TextColumn(
                "Tasks",
                width="large"
            ),
            "Challenges": st.column_config.TextColumn(
                "Challenges",
                width="large"
            ),
            "Solutions": st.column_config.TextColumn(
                "Solutions",
                width="large"
            )
        },
        hide_index=True,
        use_container_width=True
    )

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
            ["All Types", "Schedule Upload Report", "Global Deposit Assigning", "Other Report"],
            label_visibility="collapsed"
        )
    with search_col3:
        report_type_filter = st.selectbox(
            "Report Type",
            ["All", "Daily", "Weekly", "Monthly"],
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

    # Load all reports
    all_reports = []
    try:
        # Get list of officer folders
        officer_folders = [
            d for d in os.listdir(REPORTS_DIR)
            if os.path.isdir(os.path.join(REPORTS_DIR, d))
            and d not in ADDITIONAL_FOLDERS
        ]
        
        # Load reports from all officers
        for officer in officer_folders:
            officer_reports = load_reports(officer)
            all_reports.extend(officer_reports)
            
    except Exception as e:
        st.error(f"Error loading reports: {str(e)}")
        return

    # Filter reports based on search criteria
    filtered_reports = []
    for report in all_reports:
        try:
            # Date filter
            report_date = datetime.strptime(report.get('date', ''), '%Y-%m-%d').date()
            if start_date <= report_date <= end_date:
                # Type filter
                if search_type == "All Types" or report.get('type') == search_type:
                    # Frequency filter
                    if report_type_filter == "All" or report.get('frequency') == report_type_filter:
                        # Search query filter
                        if search_query:
                            search_query = search_query.lower()
                            searchable_text = ' '.join([
                                str(report.get('officer_name', '')),
                                str(report.get('company_name', '')),
                                str(report.get('tasks', '')),
                                str(report.get('challenges', '')),
                                str(report.get('solutions', '')),
                                str(report.get('companies_assigned', ''))
                            ]).lower()
                            
                            if search_query in searchable_text:
                                filtered_reports.append(report)
                        else:
                            filtered_reports.append(report)
                            
        except (ValueError, KeyError) as e:
            st.warning(f"Error processing report: {str(e)}")
            continue

    # Display results using the show_found_reports function
    if filtered_reports:
        st.success(f"Found {len(filtered_reports)} matching reports")
        show_found_reports(filtered_reports)
    else:
        st.info("No reports found matching your criteria")

def submit_report():
    """Submit a new report"""
    # Initialize session state variable if it doesn't exist
    if 'report_submitted' not in st.session_state:
        st.session_state.report_submitted = False

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
        report_category = st.selectbox(
            "Report Type", 
            ["Schedule Upload Report", "Global Deposit Assigning", "Other Report"]
        )
    
    with col3:
        if report_category != "Other Report":
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
    col1, col2, col3 = st.columns([3, 2, 3])
    
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
    elif report_category == "Global Deposit Assigning":
        with col1:
            companies_assigned = st.text_area(
                "List Companies Assigned For Global Deposit",
                height=150,
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
                "Total Number of Companies Assigned For Global Deposit", 
                min_value=0, 
                value=0, 
                step=1
            )
        with col3:
            st.markdown("""
                <div style='padding: 10px; color: #00FF00;'>
                <i>Please list each company on a new line. The total should match the number of companies assigned for global deposit.</i>
                </div>
            """, unsafe_allow_html=True)
    else:  # Other Report
        with col1:
            other_company = st.text_input("Company Name or Please Specify")
        with col3:
            st.markdown("""
                <div style='padding: 10px; color: #00FF00;'>
                <i>Please specify the company name or any other relevant information.</i>
                </div>
            """, unsafe_allow_html=True)
    
    tasks = st.text_area("Tasks Completed")
    challenges = st.text_area("Challenges Encountered")
    solutions = st.text_area("Proposed Solutions")
    
    # File upload with proper handling
    st.subheader("Attachments")
    try:
        uploaded_files = st.file_uploader(
            "Upload attachments", 
            accept_multiple_files=True,
            type=ALLOWED_ATTACHMENT_TYPES
        )
    except Exception as e:
        st.error(f"Error uploading files: {str(e)}")
        uploaded_files = None

    # Submit Report button and handling
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
                
                # Create report data with status tracking
                report_data = {
                    "id": str(uuid.uuid4()),  # Unique identifier
                    "type": report_category,
                    "date": selected_date.strftime("%Y-%m-%d"),
                    "officer_name": officer_name,
                    "tasks": tasks,
                    "challenges": challenges,
                    "solutions": solutions,
                    "attachments": attachment_paths,
                    # New status tracking fields
                    "status": "Pending Review",
                    "submission_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "review_date": None,
                    "reviewer_notes": None,
                    "priority": "Normal"  # Default priority
                }
                
                # Add type-specific fields
                if report_category == "Schedule Upload Report":
                    report_data.update({
                        "frequency": report_frequency,
                        "company_name": company_name,
                        "total_schedule_files": total_files,
                        "total_years": total_years
                    })
                elif report_category == "Global Deposit Assigning":
                    report_data.update({
                        "frequency": report_frequency,
                        "companies_assigned": companies_assigned,
                        "total_companies": total_companies
                    })
                else:  # Other Report
                    report_data.update({
                        "company_name": other_company
                    })
                
                # Save the report
                save_report(officer_name, report_data)
                st.session_state.report_submitted = True
                
                # Enhanced success message with submission details
                st.success("Report submitted successfully!")
                with st.expander("View Submission Details"):
                    st.write("**Report Status:** Pending Review")
                    st.write(f"**Submission Date:** {report_data['submission_date']}")
                    st.write(f"**Report ID:** {report_data['id']}")
                    st.write(f"**Officer:** {officer_name}")
                    st.write(f"**Type:** {report_category}")
                    if report_category != "Other Report":
                        st.write(f"**Frequency:** {report_frequency}")
                    st.info("Your report will be reviewed by a manager soon.")
                
                # Wait a moment before rerunning
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error submitting report: {str(e)}")
        else:
            st.warning("Please fill in all required fields.")
    
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
        st.metric("Total Companies Assigned For Global Deposit", total_companies)
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
            # Fix company/companies display logic
            if report.get('type') == 'Global Deposit Assigning':
                # Get companies_assigned field and clean it up
                companies = report.get('companies_assigned', '').strip()
                # Convert multiline companies to a single company name for display
                company_list = [c.strip() for c in companies.split('\n') if c.strip()]
                # Use the first company as the main display, or N/A if empty
                company_display = company_list[0] if company_list else 'N/A'
            else:
                company_display = report.get('company_name', 'N/A')

            row = {
                'Date': report.get('date', 'N/A'),
                'Officer': report.get('officer_name', 'N/A'),
                'Report Type': report.get('type', 'N/A'),
                'Frequency': report.get('frequency', 'N/A'),
                'Company For Schedule Upload': company_display,  # Changed from 'Company/Companies'
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
                "Company For Schedule Upload": st.column_config.TextColumn(  # Changed from 'Company/Companies'
                    "Company For Schedule Upload",
                    width="medium",
                    help="Company name"
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
        search_type = st.selectbox("Report Type", ["All Types", "Schedule Upload Report", "Global Deposit Assigning", "Other Report"])
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
                    if search_type != "All Types":
                        if search_type == "Other Report":
                            if report.get('type') in ["Schedule Upload Report", "Global Deposit Assigning"]:
                                continue
                        elif report.get('type') != search_type:
                            continue
                        
                    # Frequency filter
                    if search_frequency != "All" and report.get('frequency') != search_frequency:
                        continue
                    
                    # Date range filter
                    try:
                        report_date = datetime.strptime(report.get('date', ''), '%Y-%m-%d').date()
                        if start_date and report_date < start_date:
                            continue
                        if end_date and report_date > end_date:
                            continue
                    except ValueError:
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
    """Display found reports in separate tables based on report type"""
    if not found_reports:
        st.info("No reports found.")
        return

    # Create tabs for different report types
    tab1, tab2, tab3 = st.tabs(["Schedule Upload Reports", "Global Deposit Reports", "Other Reports"])

    # Filter reports by type
    schedule_reports = [r for r in found_reports if r.get('type') == 'Schedule Upload Report']
    global_reports = [r for r in found_reports if r.get('type') == 'Global Deposit Assigning']
    other_reports = [r for r in found_reports if r.get('type') not in ['Schedule Upload Report', 'Global Deposit Assigning']]

    # Schedule Upload Reports Tab
    with tab1:
        if schedule_reports:
            st.write(f"Found {len(schedule_reports)} Schedule Upload Reports")
            
            # Create DataFrame
            df = pd.DataFrame([{
                'Date': r.get('date', 'N/A'),
                'Officer': r.get('officer_name', 'N/A'),
                'Frequency': r.get('frequency', 'N/A'),
                'Company For Schedule Upload': r.get('company_name', 'N/A'),
                'Files': r.get('total_schedule_files', 0),
                'Years': r.get('total_years', 0),
                'Tasks': r.get('tasks', 'N/A'),
                'Challenges': r.get('challenges', 'N/A'),
                'Solutions': r.get('solutions', 'N/A')
            } for r in schedule_reports])

            # Export buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                # Excel export
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Schedule Reports', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Schedule Reports']
                    
                    # Add some formatting
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                
                st.download_button(
                    label="📥 Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )

            with col2:
                # CSV export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col3:
                # PDF export
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(letter)
                )
                elements = []
                
                # Convert DataFrame to list of lists for PDF table
                data = [df.columns.values.tolist()] + df.values.tolist()
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                doc.build(elements)
                
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # Display dataframe
            st.dataframe(
                df,
                column_config={
                    "Date": st.column_config.DateColumn(
                        "Date",
                        format="YYYY-MM-DD",
                        width="medium"
                    ),
                    "Officer": st.column_config.TextColumn(
                        "Officer",
                        width="medium"
                    ),
                    "Frequency": st.column_config.TextColumn(
                        "Frequency",
                        width="small"
                    ),
                    "Company For Schedule Upload": st.column_config.TextColumn(
                        "Company For Schedule Upload",
                        width="medium"
                    ),
                    "Files": st.column_config.NumberColumn(
                        "Files",
                        help="Total schedule files processed",
                        width="small"
                    ),
                    "Years": st.column_config.NumberColumn(
                        "Years",
                        help="Total years processed",
                        width="small"
                    ),
                    "Tasks": st.column_config.TextColumn(
                        "Tasks",
                        width="large"
                    ),
                    "Challenges": st.column_config.TextColumn(
                        "Challenges",
                        width="large"
                    ),
                    "Solutions": st.column_config.TextColumn(
                        "Solutions",
                        width="large"
                    )
                },
                hide_index=True,
                use_container_width=True  # Only one instance of use_container_width
            )
        else:
            st.info("No Schedule Upload Reports found")

    # Global Deposit Reports Tab
    with tab2:
        if global_reports:
            st.write(f"Found {len(global_reports)} Global Deposit Reports")
            
            # Create DataFrame
            df = pd.DataFrame([{
                'Date': r.get('date', 'N/A'),
                'Officer': r.get('officer_name', 'N/A'),
                'Frequency': r.get('frequency', 'N/A'),
                'Companies': r.get('companies_assigned', '').strip().replace('\n', ', '),
                'Total': r.get('total_companies', 0),
                'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
            } for r in global_reports])

            # Sort DataFrame
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date', ascending=(sort_order == "Oldest First"))

            # Export buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Global Reports', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Global Reports']
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                
                st.download_button(
                    label="📥 Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )

            with col2:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col3:
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(letter)
                )
                elements = []
                data = [df.columns.values.tolist()] + df.values.tolist()
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                doc.build(elements)
                
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # Display dataframe
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No Global Deposit Reports found")

    # Other Reports Tab
    with tab3:
        if other_reports:
            df = pd.DataFrame([{
                'Date': r.get('date', 'N/A'),
                'Officer': r.get('officer_name', 'Unknown'),
                'Frequency': r.get('frequency', 'Daily'),
                'Company': r.get('company_name', 'N/A'),
                'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
            } for r in other_reports])

            # Sort DataFrame
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date', ascending=(sort_order == "Oldest First"))

            # Display dataframe first
            st.dataframe(
                data=df,
                column_config={
                    "Date": st.column_config.DateColumn(
                        "Date",
                        format="YYYY-MM-DD",
                        width="medium"
                    ),
                    "Officer": st.column_config.TextColumn(
                        "Officer",
                        width="medium"
                    ),
                    "Frequency": st.column_config.TextColumn(
                        "Frequency",
                        width="small"
                    ),
                    "Company": st.column_config.TextColumn(
                        "Company",
                        width="medium"
                    ),
                    "Tasks": st.column_config.TextColumn(
                        "Tasks",
                        width="large"
                    ),
                    "Challenges": st.column_config.TextColumn(
                        "Challenges",
                        width="large"
                    ),
                    "Solutions": st.column_config.TextColumn(
                        "Solutions",
                        width="large"
                    )
                },
                hide_index=True,
                use_container_width=True
            )

            # Export buttons in columns
            st.write("Export Options:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Other Reports', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Other Reports']
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=buffer.getvalue(),
                        file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.ms-excel"
                    )

                with col2:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📄 Download CSV",
                        data=csv,
                        file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )

                with col3:
                    pdf_buffer = BytesIO()
                    doc = SimpleDocTemplate(
                        pdf_buffer,
                        pagesize=landscape(letter)
                    )
                    elements = []
                    data = [df.columns.values.tolist()] + df.values.tolist()
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 14),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    elements.append(table)
                    doc.build(elements)
                    
                    st.download_button(
                        label="📑 Download PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.info("No Other Reports found")

def load_officer_reports(officer_name):
    """Load all reports for a specific officer"""
    reports = []
    officer_dir = os.path.join(REPORTS_DIR, officer_name)
    
    # Check if officer directory exists
    if not os.path.exists(officer_dir):
        return reports
    
    # Load reports from main officer directory
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
    
    # Check for reports in the reports subfolder
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
    
    return reports

def show_dashboard():
    """Display the main dashboard with enhanced analytics"""
    st.header("Report Data Table")
    
    # Load all reports
    reports_data = load_reports()
    
    # Filter reports by type
    schedule_reports = [r for r in reports_data if r.get('type') == 'Schedule Upload Report']
    global_reports = [r for r in reports_data if r.get('type') == 'Global Deposit Assigning']
    other_reports = [r for r in reports_data if r.get('type') == 'Other']
    
    # Sort order selection
    sort_order = st.selectbox("Sort Order", ["Newest First", "Oldest First"])

    # Create combined DataFrame for all reports
    df = pd.DataFrame([{
        'Date': r.get('date', 'N/A'),
        'Officer': r.get('officer_name', 'Unknown'),
        'Report Type': r.get('type', 'N/A'),
        'Company': r.get('company_name', 'N/A'),
        'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
        'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
        'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
    } for r in reports_data])

    # Sort DataFrame
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date', ascending=(sort_order == "Oldest First"))

    # Export Options
    st.write("Export Options:")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Reports', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Reports']
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#0066cc',
                'font_color': 'white'
            })
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
        
        st.download_button(
            label="📊 Download Excel",
            data=buffer.getvalue(),
            file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )

    with col2:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download CSV",
            data=csv,
            file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col3:
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=landscape(letter)
        )
        elements = []
        data = [df.columns.values.tolist()] + df.values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        doc.build(elements)
        
        st.download_button(
            label="📑 Download PDF",
            data=pdf_buffer.getvalue(),
            file_name=f"reports_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # Display combined dataframe
    st.dataframe(
        data=df,
        column_config={
            "Date": st.column_config.DateColumn(
                "Date",
                format="YYYY-MM-DD",
                width="medium"
            ),
            "Officer": st.column_config.TextColumn(
                "Officer",
                width="medium"
            ),
            "Report Type": st.column_config.TextColumn(
                "Report Type",
                width="medium"
            ),
            "Company": st.column_config.TextColumn(
                "Company",
                width="medium"
            ),
            "Tasks": st.column_config.TextColumn(
                "Tasks",
                width="large"
            ),
            "Challenges": st.column_config.TextColumn(
                "Challenges",
                width="large"
            ),
            "Solutions": st.column_config.TextColumn(
                "Solutions",
                width="large"
            )
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Create tabs for different report types
    tab1, tab2, tab3 = st.tabs(["Schedule Upload Reports", "Global Deposit Reports", "Other Reports"])
    
    # Schedule Upload Reports Tab
    with tab1:
        if schedule_reports:
            df_schedule = pd.DataFrame([{
                'Date': r.get('date', 'N/A'),
                'Officer': r.get('officer_name', 'Unknown'),
                'Company': r.get('company_name', 'N/A'),
                'Total Years': r.get('total_years', 'N/A'),
                'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
            } for r in schedule_reports])

            # Sort DataFrame
            df_schedule['Date'] = pd.to_datetime(df_schedule['Date'])
            df_schedule = df_schedule.sort_values('Date', ascending=(sort_order == "Oldest First"))

            # Export buttons
            st.write("Export Options:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_schedule.to_excel(writer, sheet_name='Schedule Reports', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Schedule Reports']
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df_schedule.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                
                st.download_button(
                    label="📥 Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )

            with col2:
                csv = df_schedule.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col3:
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(letter)
                )
                elements = []
                data = [df_schedule.columns.values.tolist()] + df_schedule.values.tolist()
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                doc.build(elements)
                
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=f"schedule_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info("No Schedule Upload Reports found")

    # Global Deposit Reports Tab
    with tab2:
        if global_reports:
            df_global = pd.DataFrame([{
                'Date': r.get('date', 'N/A'),
                'Officer': r.get('officer_name', 'Unknown'),
                'Companies Assigned': r.get('companies_assigned', 'N/A'),
                'Total Companies': r.get('total_companies', 'N/A'),
                'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
            } for r in global_reports])

            # Sort DataFrame
            df_global['Date'] = pd.to_datetime(df_global['Date'])
            df_global = df_global.sort_values('Date', ascending=(sort_order == "Oldest First"))

            # Export buttons
            st.write("Export Options:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_global.to_excel(writer, sheet_name='Global Reports', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Global Reports']
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df_global.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                
                st.download_button(
                    label="📥 Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )

            with col2:
                csv = df_global.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col3:
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(letter)
                )
                elements = []
                data = [df_global.columns.values.tolist()] + df_global.values.tolist()
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                doc.build(elements)
                
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=f"global_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info("No Global Deposit Reports found")

    # Other Reports Tab
    with tab3:
        if other_reports:
            df_other = pd.DataFrame([{
                'Date': r.get('date', 'N/A'),
                'Officer': r.get('officer_name', 'Unknown'),
                'Type': r.get('type', 'N/A'),
                'Tasks': r.get('tasks', 'N/A')[:100] + '...' if len(r.get('tasks', 'N/A')) > 100 else r.get('tasks', 'N/A'),
                'Challenges': r.get('challenges', 'N/A')[:100] + '...' if len(r.get('challenges', 'N/A')) > 100 else r.get('challenges', 'N/A'),
                'Solutions': r.get('solutions', 'N/A')[:100] + '...' if len(r.get('solutions', 'N/A')) > 100 else r.get('solutions', 'N/A')
            } for r in other_reports])

            # Sort DataFrame
            df_other['Date'] = pd.to_datetime(df_other['Date'])
            df_other = df_other.sort_values('Date', ascending=(sort_order == "Oldest First"))

            # Export buttons
            st.write("Export Options:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_other.to_excel(writer, sheet_name='Other Reports', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Other Reports']
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#0066cc',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df_other.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                
                st.download_button(
                    label="📥 Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )

            with col2:
                csv = df_other.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col3:
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=landscape(letter)
                )
                elements = []
                data = [df_other.columns.values.tolist()] + df_other.values.tolist()
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                doc.build(elements)
                
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=f"other_reports_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info("No Other Reports found")

#END OF SHOW DASHBOARD

def generate_report_summaries():
    """Enhanced Report Summaries Dashboard with comprehensive analytics and management features"""
    st.header("📊 Report Summaries & Analytics Dashboard")

    # Date Range Selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From Date",
            value=datetime.now().date() - timedelta(days=30),
            max_value=datetime.now().date()
        )
    with col2:
        end_date = st.date_input(
            "To Date",
            value=datetime.now().date(),
            max_value=datetime.now().date()
        )

    # Load and filter reports with error handling
    try:
        all_reports = load_reports()
        st.write(f"Total reports loaded: {len(all_reports)}")  # Debug info
        
        if not all_reports:
            st.warning("No reports found in the system.")
            return

        # Filter reports within date range
        filtered_reports = []
        for report in all_reports:
            try:
                report_date = datetime.strptime(report.get('date', ''), '%Y-%m-%d').date()
                if start_date <= report_date <= end_date:
                    filtered_reports.append(report)
            except (ValueError, TypeError) as e:
                st.error(f"Error processing report date: {e}")
                continue

        st.write(f"Filtered reports: {len(filtered_reports)}")  # Debug info

        if not filtered_reports:
            st.warning("No reports found for the selected date range.")
            return

        # Convert to DataFrame for analysis
        df = pd.DataFrame(filtered_reports)
        df['date'] = pd.to_datetime(df['date'])

        # 1. Key Metrics Dashboard
        st.subheader("📈 Key Performance Metrics")
        metric_cols = st.columns(4)
        
        with metric_cols[0]:
            total_reports = len(filtered_reports)
            st.metric("Total Reports", total_reports)
        
        with metric_cols[1]:
            unique_officers = len(df['officer_name'].unique())
            st.metric("Total Officers", unique_officers)
        
        with metric_cols[2]:
            unique_companies = len(df['company_name'].unique())
            st.metric("Total Companies", unique_companies)
        
        with metric_cols[3]:
            pending_reviews = len(df[df['status'].isin(['Pending Review', 'Needs Attention'])])
            st.metric("Pending Reviews", pending_reviews)

        # 2. Report Distribution
        st.subheader("📊 Report Distribution")
        dist_col1, dist_col2 = st.columns(2)

        with dist_col1:
            # Reports by Type
            type_counts = df['type'].value_counts()
            fig_types = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title='Distribution by Report Type'
            )
            st.plotly_chart(fig_types, use_container_width=True)

        with dist_col2:
            # Reports by Status
            status_counts = df['status'].value_counts()
            fig_status = px.bar(
                x=status_counts.index,
                y=status_counts.values,
                title='Reports by Status',
                labels={'x': 'Status', 'y': 'Count'}
            )
            st.plotly_chart(fig_status, use_container_width=True)

        # 3. Timeline Analysis
        st.subheader("📅 Timeline Analysis")
        timeline_tabs = st.tabs(["Daily", "Weekly", "Monthly"])

        with timeline_tabs[0]:
            daily_counts = df.groupby(df['date'].dt.date).size()
            fig_daily = px.line(
                x=daily_counts.index,
                y=daily_counts.values,
                title='Daily Report Submissions',
                labels={'x': 'Date', 'y': 'Number of Reports'}
            )
            st.plotly_chart(fig_daily, use_container_width=True)

        with timeline_tabs[1]:
            weekly_counts = df.groupby(pd.Grouper(key='date', freq='W')).size()
            fig_weekly = px.bar(
                x=weekly_counts.index,
                y=weekly_counts.values,
                title='Weekly Report Submissions',
                labels={'x': 'Week', 'y': 'Number of Reports'}
            )
            st.plotly_chart(fig_weekly, use_container_width=True)

        with timeline_tabs[2]:
            monthly_counts = df.groupby(pd.Grouper(key='date', freq='M')).size()
            fig_monthly = px.bar(
                x=monthly_counts.index,
                y=monthly_counts.values,
                title='Monthly Report Submissions',
                labels={'x': 'Month', 'y': 'Number of Reports'}
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

        # 4. Officer Performance
        st.subheader("👥 Officer Performance")
        officer_tabs = st.tabs(["Report Volume", "Status Distribution"])

        with officer_tabs[0]:
            officer_counts = df['officer_name'].value_counts()
            fig_officers = px.bar(
                x=officer_counts.index,
                y=officer_counts.values,
                title='Reports by Officer',
                labels={'x': 'Officer', 'y': 'Number of Reports'}
            )
            st.plotly_chart(fig_officers, use_container_width=True)

        with officer_tabs[1]:
            officer_status = pd.crosstab(df['officer_name'], df['status'])
            fig_officer_status = px.bar(
                officer_status,
                title='Report Status by Officer',
                barmode='stack'
            )
            st.plotly_chart(fig_officer_status, use_container_width=True)

        # 5. Report Management
        st.subheader("📋 Report Management")
        if len(filtered_reports) > 0:
            selected_report = st.selectbox(
                "Select Report to Manage",
                options=[(f"{r.get('date')} - {r.get('officer_name')} - {r.get('type')}") for r in filtered_reports],
                format_func=lambda x: x
            )

            if selected_report:
                report_idx = [(f"{r.get('date')} - {r.get('officer_name')} - {r.get('type')}") for r in filtered_reports].index(selected_report)
                report = filtered_reports[report_idx]

                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Current Status:**", report.get('status', 'Pending'))
                    new_status = st.selectbox(
                        "Update Status",
                        options=REPORT_STATUSES,
                        index=REPORT_STATUSES.index(report.get('status', 'Pending Review'))
                    )

                with col2:
                    st.write("**Comments**")
                    new_comment = st.text_area("Add Comment")
                    if st.button("Add Comment"):
                        st.success("Comment added successfully!")

        # 6. Export Options
        st.subheader("📤 Export Options")
        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            if st.button("📊 Export Summary (Excel)"):
                st.success("Excel summary generated!")

        with export_col2:
            if st.button("📄 Export Summary (PDF)"):
                st.success("PDF summary generated!")

        with export_col3:
            if st.button("📈 Export Charts"):
                st.success("Charts exported!")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.write("Please try again or contact support if the problem persists.")

def main():
    """Main dashboard with navigation"""
    st.set_page_config(page_title="Officer Report Dashboard", layout="wide")
    
    # Initialize session state for report submission if not exists
    if 'report_submitted' not in st.session_state:
        st.session_state.report_submitted = False
    
    # Sidebar navigation with corrected mapping
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select a page",
        ["Dashboard", "Submit Report", "Edit Reports", "View Reports", "Report Summaries", 
         "Task Management", "Manage Folders"]
    )
    
    # Handle page navigation with correct function mapping
    if page == "Dashboard":
        create_dashboard()  # Main Dashboard Analytics
    elif page == "Submit Report":
        submit_report()
    elif page == "View Reports":
        view_reports()
    elif page == "Report Summaries":
        show_summaries()  # Report Summaries Dashboard
    elif page == "Task Management":
        create_task_dashboard()
    elif page == "Manage Folders":
        manage_folders()

if __name__ == "__main__":
    st.set_page_config(page_title="Officer Report Dashboard", layout="wide")
    
    # Initialize session state for report submission if not exists
    if 'report_submitted' not in st.session_state:
        st.session_state.report_submitted = False
    
    # Sidebar navigation
        st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select a page",
        ["Dashboard", "Submit Report", "View Reports", "Report Summaries", 
         "Task Management", "Manage Folders", "Edit Reports"]  # Added at the end
    )
    
    # Handle page navigation
    if page == "Dashboard":
        try:
            create_dashboard()  # Main Dashboard Analytics
        except Exception as e:
            st.error(f"Error loading Dashboard: {str(e)}")
    elif page == "Submit Report":
        try:
            submit_report()
        except Exception as e:
            st.error(f"Error loading Submit Report: {str(e)}")
    elif page == "View Reports":
        try:
            view_reports()
        except Exception as e:
            st.error(f"Error loading View Reports: {str(e)}")
    elif page == "Report Summaries":
        try:
            show_summaries()  # Report Summaries Dashboard
        except Exception as e:
            st.error(f"Error loading Report Summaries: {str(e)}")
    elif page == "Task Management":
        try:
            create_task_dashboard()
        except Exception as e:
            st.error(f"Error loading Task Management: {str(e)}")
    elif page == "Manage Folders":
        try:
            manage_folders()
        except Exception as e:
            st.error(f"Error loading Manage Folders: {str(e)}")
    elif page == "Edit Reports":  # Add this new section at the end
        try:
            edit_report()
        except Exception as e:
            st.error(f"Error loading Edit Reports: {str(e)}")

# # Add these constants at the top of your file with other constants
# TASK_DIR = "tasks"
# TASK_STATUSES = ["Pending", "In Progress", "Completed", "Overdue"]
# REPORT_STATUSES = ['Pending Review', 'Approved', 'Needs Attention']

# def load_tasks():
#     """Load all tasks from the tasks directory"""
#     tasks = []
#     try:
#         if os.path.exists(TASK_DIR):
#             for task_file in os.listdir(TASK_DIR):
#                 if task_file.endswith('.json'):
#                     with open(os.path.join(TASK_DIR, task_file), 'r') as f:
#                         task = json.load(f)
#                         tasks.append(task)
#     except Exception as e:
#         st.error(f"Error loading tasks: {str(e)}")
#     return tasks

