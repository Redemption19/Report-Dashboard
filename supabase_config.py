import streamlit as st
from supabase import create_client
import uuid
from datetime import datetime
import json
import os
import pandas as pd

# Constants (matching your existing structure)
REPORTS_DIR = "officer_reports"
ADDITIONAL_FOLDERS = ["Templates", "Summaries", "Archives", "Attachments", "Tasks"]

def init_supabase():
    """Initialize Supabase client"""
    try:
        supabase_url = st.secrets["supabase_url"]
        supabase_key = st.secrets["supabase_key"]
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Error initializing Supabase: {str(e)}")
        return None

def save_report_to_supabase(officer_name, report_data):
    """Save report to Supabase"""
    try:
        # Generate unique ID if not present
        if 'id' not in report_data:
            report_data['id'] = str(uuid.uuid4())
        
        # Format the date properly
        report_date = report_data['date']
        if hasattr(report_date, 'strftime'):
            formatted_date = report_date.strftime("%Y-%m-%d")
            report_data['date'] = formatted_date
        elif isinstance(report_date, str):
            formatted_date = report_date.split()[0]
        
        # Initialize Supabase client
        supabase = init_supabase()
        if not supabase:
            return False
            
        # Prepare report data for Supabase
        supabase_data = {
            'id': report_data['id'],
            'officer_name': officer_name,
            'date': formatted_date,
            'type': report_data['type'],
            'status': report_data.get('status', 'Pending Review'),
            'company_name': report_data.get('company_name'),
            'companies_assigned': report_data.get('companies_assigned'),
            'total_companies': report_data.get('total_companies'),
            'total_years': report_data.get('total_years'),
            'tasks': report_data.get('tasks'),
            'challenges': report_data.get('challenges'),
            'solutions': report_data.get('solutions'),
            'frequency': report_data.get('frequency'),
            'review_date': report_data.get('review_date'),
            'reviewer_notes': report_data.get('reviewer_notes'),
            'comments': json.dumps(report_data.get('comments', [])),
            'report_data': json.dumps(report_data)  # Store complete report data
        }
        
        # Save to Supabase
        response = supabase.table('reports').upsert(supabase_data).execute()
        return True if response else False
        
    except Exception as e:
        st.error(f"Error saving report to Supabase: {str(e)}")
        return False

def load_reports_from_supabase(officer_name=None):
    """Load reports from Supabase maintaining folder structure"""
    try:
        supabase = init_supabase()
        if not supabase:
            return []
            
        query = supabase.table('reports')
        
        if officer_name:
            query = query.eq('officer_name', officer_name)
        
        response = query.execute()
        
        # Convert Supabase data back to original format
        reports = []
        for record in response.data:
            try:
                # Parse the stored JSON data
                report_data = json.loads(record['report_data'])
                reports.append(report_data)
            except:
                # Fallback to raw record if JSON parsing fails
                reports.append(record)
        
        return reports
        
    except Exception as e:
        st.error(f"Error loading reports from Supabase: {str(e)}")
        return []

def get_officer_names_from_supabase():
    """Get unique officer names from Supabase"""
    try:
        supabase = init_supabase()
        if not supabase:
            return []
            
        response = supabase.table('reports').select('officer_name').execute()
        officers = list(set(r['officer_name'] for r in response.data if r['officer_name']))
        return sorted(officers)
        
    except Exception as e:
        st.error(f"Error loading officer names from Supabase: {str(e)}")
        return []

def sync_local_to_supabase():
    """Sync all local reports to Supabase"""
    try:
        # Get all officer folders
        officer_folders = [
            d for d in os.listdir(REPORTS_DIR) 
            if os.path.isdir(os.path.join(REPORTS_DIR, d))
            and d not in ADDITIONAL_FOLDERS
        ]
        
        for officer_name in officer_folders:
            officer_dir = os.path.join(REPORTS_DIR, officer_name)
            for filename in os.listdir(officer_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(officer_dir, filename)
                    with open(filepath, 'r') as f:
                        report_data = json.load(f)
                        save_report_to_supabase(officer_name, report_data)
        
        return True
    except Exception as e:
        st.error(f"Error syncing to Supabase: {str(e)}")
        return False

def check_supabase_data():
    """Check data stored in Supabase"""
    # Initialize session state if needed
    if 'supabase_check' not in st.session_state:
        st.session_state.supabase_check = False

    try:
        # Create a container for the data display
        with st.container():
            st.subheader("📊 Supabase Data Check")
            
            supabase = init_supabase()
            if not supabase:
                st.error("Could not connect to Supabase")
                return None
                
            # Get all reports
            response = supabase.table('reports').select('*').execute()
            
            if response.data:
                st.success(f"✅ Found {len(response.data)} reports in Supabase")
                
                # Convert to DataFrame
                df = pd.DataFrame(response.data)
                
                # Format dates
                if 'created_at' in df.columns:
                    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
                if 'last_edited' in df.columns:
                    df['last_edited'] = pd.to_datetime(df['last_edited']).dt.strftime('%Y-%m-%d %H:%M:%S')
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                
                # Show data in an expander
                with st.expander("View Reports Data", expanded=True):
                    st.dataframe(
                        df[['officer_name', 'date', 'type', 'status', 'created_at']],
                        use_container_width=True
                    )
                
                return response.data
            else:
                st.warning("No data found in Supabase")
                return None
                
    except Exception as e:
        st.error(f"Error checking Supabase data: {str(e)}")
        return None

def auto_backup_to_supabase():
    """Automatically backup all local reports to Supabase"""
    try:
        st.info("🔄 Starting automatic backup...")
        
        # Get all officer folders
        officer_folders = [
            d for d in os.listdir(REPORTS_DIR) 
            if os.path.isdir(os.path.join(REPORTS_DIR, d))
            and d not in ADDITIONAL_FOLDERS
        ]
        
        total_reports = 0
        success_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, officer_name in enumerate(officer_folders):
            officer_dir = os.path.join(REPORTS_DIR, officer_name)
            
            # Get all JSON files in officer directory
            report_files = [f for f in os.listdir(officer_dir) if f.endswith('.json')]
            total_reports += len(report_files)
            
            for report_file in report_files:
                filepath = os.path.join(officer_dir, report_file)
                try:
                    # Load report data
                    with open(filepath, 'r') as f:
                        report_data = json.load(f)
                    
                    # Save to Supabase
                    if save_report_to_supabase(officer_name, report_data):
                        success_count += 1
                    
                    # Update progress
                    progress = (i + 1) / len(officer_folders)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing: {officer_name} - {report_file}")
                    
                except Exception as e:
                    st.error(f"Error backing up {report_file}: {str(e)}")
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count == total_reports:
            st.success(f"✅ Successfully backed up {success_count} reports to Supabase")
        else:
            st.warning(f"⚠️ Backed up {success_count} out of {total_reports} reports")
        
        return True
    
    except Exception as e:
        st.error(f"❌ Error during backup: {str(e)}")
        return False

def restore_from_supabase():
    """Restore reports from Supabase to local storage"""
    try:
        st.info("🔄 Starting restoration from Supabase...")
        
        # Get all reports from Supabase
        supabase = init_supabase()
        if not supabase:
            return False
        
        response = supabase.table('reports').select('*').execute()
        if not response.data:
            st.warning("No data found in Supabase to restore")
            return False
        
        total_reports = len(response.data)
        success_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, report in enumerate(response.data):
            try:
                # Extract report data
                report_data = json.loads(report['report_data'])
                officer_name = report['officer_name']
                
                # Create officer directory if it doesn't exist
                officer_dir = os.path.join(REPORTS_DIR, officer_name)
                os.makedirs(officer_dir, exist_ok=True)
                
                # Create filename
                report_date = report['date']
                report_type = report_data['type'].replace(' ', '_')
                filename = f"{report_date}_{report_type}.json"
                filepath = os.path.join(officer_dir, filename)
                
                # Save locally
                with open(filepath, 'w') as f:
                    json.dump(report_data, f, indent=4)
                
                success_count += 1
                
                # Update progress
                progress = (i + 1) / total_reports
                progress_bar.progress(progress)
                status_text.text(f"Restoring: {officer_name} - {filename}")
                
            except Exception as e:
                st.error(f"Error restoring report: {str(e)}")
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count == total_reports:
            st.success(f"✅ Successfully restored {success_count} reports from Supabase")
        else:
            st.warning(f"⚠️ Restored {success_count} out of {total_reports} reports")
        
        return True
    
    except Exception as e:
        st.error(f"❌ Error during restoration: {str(e)}")
        return False

def schedule_auto_backup():
    """Schedule automatic backup to run daily"""
    try:
        if 'last_backup' not in st.session_state:
            st.session_state.last_backup = None
        
        # Check if backup is needed
        now = datetime.now()
        if (st.session_state.last_backup is None or 
            (now - st.session_state.last_backup).days >= 1):
            
            if auto_backup_to_supabase():
                st.session_state.last_backup = now
                st.success("✅ Scheduled backup completed successfully")
            else:
                st.error("❌ Scheduled backup failed")
    
    except Exception as e:
        st.error(f"❌ Error in scheduled backup: {str(e)}")

def save_task_to_supabase(task_data):
    """Save task to Supabase"""
    try:
        # Initialize Supabase client
        supabase = init_supabase()
        if not supabase:
            return False
            
        # Prepare task data for Supabase
        supabase_data = {
            'task_id': task_data['task_id'],
            'title': task_data['title'],
            'description': task_data['description'],
            'status': task_data['status'],
            'priority': task_data['priority'],
            'category': task_data['category'],
            'assigned_to': task_data['assigned_to'],
            'due_date': task_data['due_date'],
            'created_date': task_data['created_date'],
            'comments': json.dumps(task_data.get('comments', [])),
            'task_data': json.dumps(task_data)  # Store complete task data
        }
        
        # Save to Supabase
        response = supabase.table('tasks').upsert(supabase_data).execute()
        return True if response else False
        
    except Exception as e:
        st.error(f"Error saving task to Supabase: {str(e)}")
        return False

def load_tasks_from_supabase():
    """Load all tasks from Supabase"""
    try:
        supabase = init_supabase()
        if not supabase:
            return []
            
        response = supabase.table('tasks').select('*').execute()
        
        tasks = []
        for record in response.data:
            try:
                # Parse the stored JSON data
                task_data = json.loads(record['task_data'])
                tasks.append(task_data)
            except:
                # Fallback to raw record if JSON parsing fails
                tasks.append(record)
        
        return tasks
        
    except Exception as e:
        st.error(f"Error loading tasks from Supabase: {str(e)}")
        return []

def delete_task_from_supabase(task_id):
    """Delete task from Supabase"""
    try:
        supabase = init_supabase()
        if not supabase:
            return False
            
        response = supabase.table('tasks').delete().eq('task_id', task_id).execute()
        return True if response else False
        
    except Exception as e:
        st.error(f"Error deleting task from Supabase: {str(e)}")
        return False 