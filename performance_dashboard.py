import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import json
import os
import uuid

class PerformanceDashboard:
    def __init__(self, reports_dir):
        self.REPORTS_DIR = reports_dir
        self.PERFORMANCE_THRESHOLD = 0.8  # 80% completion rate threshold
        self.WARNING_THRESHOLD = 0.6  # 60% warning threshold
        
    def load_performance_data(self, start_date, end_date):
        """Load and process report data for performance analysis"""
        all_reports = []
        for officer_folder in os.listdir(self.REPORTS_DIR):
            if os.path.isdir(os.path.join(self.REPORTS_DIR, officer_folder)) and officer_folder not in ["Attachments", "Templates", "Summaries", "Archives", "Tasks"]:
                officer_path = os.path.join(self.REPORTS_DIR, officer_folder)
                for report_file in os.listdir(officer_path):
                    if report_file.endswith('.json'):
                        try:
                            with open(os.path.join(officer_path, report_file), 'r') as f:
                                report = json.load(f)
                                # Convert string date to datetime
                                try:
                                    # Convert to pandas Timestamp for consistent comparison
                                    report_date = pd.to_datetime(report['date']).date()
                                    submission_date = pd.to_datetime(report['submission_date'])
                                    
                                    # Add processed dates back to report
                                    report['date'] = report_date
                                    report['submission_date'] = submission_date
                                    
                                    # Compare dates properly
                                    if start_date <= report_date <= end_date:
                                        # Ensure all required fields exist
                                        report.setdefault('is_on_time', True)  # Default to True if not set
                                        report.setdefault('status', 'Pending Review')  # Default status
                                        all_reports.append(report)
                                except (ValueError, KeyError) as e:
                                    st.warning(f"Skipping report with invalid date format: {report_file}")
                                    continue
                        except Exception as e:
                            st.warning(f"Error reading report {report_file}: {str(e)}")
                            continue
        
        if not all_reports:
            return pd.DataFrame()  # Return empty DataFrame if no reports found
        
        df = pd.DataFrame(all_reports)
        
        # Ensure all required columns exist
        required_columns = ['date', 'submission_date', 'officer_name', 'status', 'is_on_time']
        for col in required_columns:
            if col not in df.columns:
                df[col] = None  # Add missing columns with None values
        
        # Convert date columns to datetime
        df['date'] = pd.to_datetime(df['date'])
        df['submission_date'] = pd.to_datetime(df['submission_date'])
        
        return df

    def calculate_completion_rates(self, df):
        """Calculate report completion rates over time"""
        if df.empty:
            return {
                'daily': pd.Series(),
                'weekly': pd.Series(),
                'monthly': pd.Series()
            }
        
        # Ensure date columns are datetime
        df['date'] = pd.to_datetime(df['date'])
        df['submission_date'] = pd.to_datetime(df['submission_date'])
        
        # Calculate on-time submission (as numeric)
        df['is_on_time_num'] = df.apply(
            lambda x: 1 if (
                pd.notnull(x['submission_date']) and 
                pd.notnull(x['date']) and 
                x['submission_date'].date() <= x['date'].date()
            ) else 0,
            axis=1
        )
        
        # Calculate completion rates for different periods
        completion_rates = {
            'daily': df.groupby(df['date'].dt.date)['is_on_time_num'].mean(),
            'weekly': df.groupby(pd.Grouper(key='date', freq='W-MON'))['is_on_time_num'].mean(),
            'monthly': df.groupby(pd.Grouper(key='date', freq='M'))['is_on_time_num'].mean()
        }
        
        # Clean up the results
        for key in completion_rates:
            completion_rates[key] = completion_rates[key].dropna()
            if len(completion_rates[key]) > 0:
                completion_rates[key].index = pd.to_datetime(completion_rates[key].index)
        
        return completion_rates

    def identify_bottlenecks(self, df):
        """Identify bottlenecks in the reporting process"""
        bottlenecks = {
            'late_submissions': len(df[~df['is_on_time']]),
            'incomplete_reports': len(df[df['status'] == 'Needs Attention']),
            'pending_reviews': len(df[df['status'] == 'Pending Review'])
        }
        return bottlenecks

    def analyze_officer_performance(self, df):
        """Analyze individual officer performance with detailed metrics"""
        if df.empty:
            return pd.DataFrame()
        
        # Ensure required columns exist
        required_columns = ['date', 'submission_date', 'officer_name', 'status', 'type']
        for col in required_columns:
            if col not in df.columns:
                df[col] = None
        
        # Convert date columns to datetime
        df['date'] = pd.to_datetime(df['date'])
        df['submission_date'] = pd.to_datetime(df['submission_date'])
        
        # Calculate on-time submission (as numeric)
        df['is_on_time_num'] = df.apply(
            lambda x: 1 if (
                pd.notnull(x['submission_date']) and 
                pd.notnull(x['date']) and 
                x['submission_date'].date() <= x['date'].date()
            ) else 0,
            axis=1
        )
        
        # Calculate same-day submission (as numeric)
        df['same_day_num'] = df.apply(
            lambda x: 1 if (
                pd.notnull(x['submission_date']) and 
                pd.notnull(x['date']) and 
                x['submission_date'].date() == x['date'].date()
            ) else 0,
            axis=1
        )
        
        # Group by officer and calculate metrics
        metrics = {
            'total_reports': df.groupby('officer_name').size(),
            'on_time_rate': df.groupby('officer_name')['is_on_time_num'].mean(),
            'same_day_rate': df.groupby('officer_name')['same_day_num'].mean(),
            'pending_review_rate': df.groupby('officer_name').apply(
                lambda x: (x['status'] == 'Pending Review').mean()
            )
        }
        
        # Create officer stats DataFrame
        officer_stats = pd.DataFrame(metrics)
        
        # Fill NaN values with 0
        officer_stats = officer_stats.fillna(0)
        
        # Calculate performance score
        officer_stats['performance_score'] = (
            (officer_stats['on_time_rate'] * 0.4) +  # 40% weight
            (officer_stats['same_day_rate'] * 0.3) +  # 30% weight
            ((1 - officer_stats['pending_review_rate']) * 0.3)  # 30% weight
        )
        
        # Assign performance ratings
        officer_stats['performance_rating'] = pd.cut(
            officer_stats['performance_score'],
            bins=[-float('inf'), 0.6, 0.8, float('inf')],
            labels=['Low', 'Medium', 'High']
        )
        
        # Calculate recent trends (last 30 days)
        recent_cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
        recent_df = df[df['date'] >= recent_cutoff].copy()
        
        if not recent_df.empty:
            recent_stats = recent_df.groupby('officer_name')['is_on_time_num'].mean()
            # Ensure index alignment
            recent_stats = recent_stats.reindex(officer_stats.index, fill_value=0)
            officer_stats['recent_performance'] = recent_stats
            officer_stats['performance_trend'] = officer_stats['recent_performance'] - officer_stats['on_time_rate']
        
        # Add report type distribution
        officer_stats['type_distribution'] = df.groupby('officer_name')['type'].agg(
            lambda x: dict(x.value_counts())
        )
        
        # Generate insights
        officer_stats['insights'] = officer_stats.apply(self._generate_officer_insights, axis=1)
        
        return officer_stats

    def _generate_officer_insights(self, metrics):
        """Generate insights for an individual officer"""
        insights = []
        
        # Analyze on-time submission rate
        if metrics['on_time_rate'] < 0.6:
            insights.append({
                'type': 'warning',
                'message': 'Low on-time submission rate',
                'recommendation': 'Consider time management training or workload adjustment'
            })
        
        # Analyze same-day submissions
        if metrics['same_day_rate'] < 0.7:
            insights.append({
                'type': 'improvement',
                'message': 'Delayed report submissions',
                'recommendation': 'Encourage submitting reports on the same day as tasks'
            })
        
        # Analyze performance trend
        if 'performance_trend' in metrics:
            if metrics['performance_trend'] < -0.1:
                insights.append({
                    'type': 'danger',
                    'message': 'Declining performance trend',
                    'recommendation': 'Schedule performance review and identify challenges'
                })
            elif metrics['performance_trend'] > 0.1:
                insights.append({
                    'type': 'success',
                    'message': 'Improving performance trend',
                    'recommendation': 'Acknowledge improvement and maintain momentum'
                })
        
        return insights

    def analyze_performance_trends(self, completion_rates):
        """Analyze performance trends and identify areas for improvement"""
        trend_analysis = {
            'daily': {'drops': [], 'improvements': []},
            'weekly': {'drops': [], 'improvements': []},
            'monthly': {'drops': [], 'improvements': []}
        }
        
        for period, rates in completion_rates.items():
            if len(rates) >= 2:
                # Calculate rolling average to smooth out fluctuations
                rolling_avg = rates.rolling(window=3, min_periods=1).mean()
                
                # Identify significant drops (more than 15% decrease)
                for i in range(1, len(rates)):
                    current = rates.iloc[i]
                    previous = rates.iloc[i-1]
                    date = rates.index[i]
                    
                    if current < previous:
                        drop_percent = ((previous - current) / previous) * 100
                        if drop_percent > 15:
                            trend_analysis[period]['drops'].append({
                                'date': date,
                                'drop': drop_percent,
                                'current_rate': current,
                                'previous_rate': previous
                            })
                    elif current > previous:
                        improve_percent = ((current - previous) / previous) * 100
                        if improve_percent > 15:
                            trend_analysis[period]['improvements'].append({
                                'date': date,
                                'improvement': improve_percent,
                                'current_rate': current,
                                'previous_rate': previous
                            })
        
        return trend_analysis

    def generate_performance_alerts(self, completion_rates, officer_stats, trend_analysis):
        """Generate performance alerts and notifications with detailed insights"""
        alerts = []
        
        # Performance trend alerts
        for period, trends in trend_analysis.items():
            # Alert for performance drops
            for drop in trends['drops']:
                alerts.append({
                    'type': 'danger',
                    'message': f"Significant performance drop in {period} completion rate",
                    'metric': f"{drop['current_rate']:.1%} (dropped by {drop['drop']:.1f}%)",
                    'date': drop['date'],
                    'improvement_suggestions': [
                        "Review workload distribution",
                        "Check for process bottlenecks",
                        "Assess resource allocation"
                    ]
                })
        
        # Current performance alerts
        for period, rates in completion_rates.items():
            if len(rates) > 0:
                current = rates.iloc[-1]
                if current < self.WARNING_THRESHOLD:
                    alert_type = 'danger' if current < self.WARNING_THRESHOLD * 0.8 else 'warning'
                    alerts.append({
                        'type': alert_type,
                        'message': f"Low {period} completion rate",
                        'metric': f"{current:.1%}",
                        'improvement_suggestions': [
                            "Schedule additional training sessions",
                            "Review reporting guidelines",
                            "Consider process simplification"
                        ]
                    })

        # Officer performance alerts
        low_performers = officer_stats[officer_stats['performance_rating'] == 'Low']
        for officer in low_performers.index:
            alerts.append({
                'type': 'warning',
                'message': f"Low performance detected for officer: {officer}",
                'metric': f"{low_performers.loc[officer, 'on_time_rate']:.1%} completion rate",
                'improvement_suggestions': [
                    "Schedule one-on-one training",
                    "Review workload allocation",
                    "Identify specific challenges"
                ]
            })

        return alerts

    def render_performance_trends(self, trend_analysis, completion_rates):
        """Render performance trends and analysis"""
        st.subheader("📉 Performance Trend Analysis")
        
        # Display trend insights
        for period in ['monthly', 'weekly', 'daily']:
            with st.expander(f"{period.capitalize()} Performance Analysis"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("🔴 **Performance Drops**")
                    if trend_analysis[period]['drops']:
                        for drop in trend_analysis[period]['drops']:
                            st.error(
                                f"Drop of {drop['drop']:.1f}% on {drop['date'].strftime('%Y-%m-%d')}\n"
                                f"Rate: {drop['previous_rate']:.1%} → {drop['current_rate']:.1%}"
                            )
                    else:
                        st.success("No significant performance drops detected")
                
                with col2:
                    st.write("🟢 **Improvements**")
                    if trend_analysis[period]['improvements']:
                        for improvement in trend_analysis[period]['improvements']:
                            st.success(
                                f"Improvement of {improvement['improvement']:.1f}% on "
                                f"{improvement['date'].strftime('%Y-%m-%d')}\n"
                                f"Rate: {improvement['previous_rate']:.1%} → {improvement['current_rate']:.1%}"
                            )
                    else:
                        st.info("No significant improvements detected")

    def send_notification(self, recipient_email, subject, message, notification_type='email'):
        """Send notifications via email and/or system"""
        
        # Email configuration
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SENDER_EMAIL = "your-email@gmail.com"  # Replace with your email
        SENDER_PASSWORD = "your-app-password"   # Replace with your app password
        
        # HTML email template
        html_template = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 5px;">
                        <h2 style="color: #2c3e50; margin-bottom: 20px;">Officer Report Notification</h2>
                        <div style="background: white; padding: 15px; border-radius: 5px; border-left: 4px solid 
                            {'#28a745' if 'approved' in subject.lower() else 
                             '#dc3545' if 'rejected' in subject.lower() else 
                             '#ffc107' if 'deadline' in subject.lower() else '#17a2b8'};">
                            <h3 style="margin-top: 0;">{subject}</h3>
                            <div style="color: #555;">{message}</div>
                        </div>
                        <div style="margin-top: 20px; font-size: 12px; color: #666;">
                            This is an automated message from the Officer Report Dashboard.
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """

        try:
            # Send email notification
            if notification_type in ['email', 'both']:
                msg = MIMEMultipart('alternative')
                msg['From'] = SENDER_EMAIL
                msg['To'] = recipient_email
                msg['Subject'] = subject

                # Add both plain text and HTML parts
                msg.attach(MIMEText(message, 'plain'))
                msg.attach(MIMEText(html_template, 'html'))

                # Connect to SMTP server and send email
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.send_message(msg)

            # Store system notification in database/session state
            if notification_type in ['system', 'both']:
                if 'notifications' not in st.session_state:
                    st.session_state.notifications = []
                
                notification = {
                    'id': str(uuid.uuid4()),
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'subject': subject,
                    'message': message,
                    'read': False,
                    'type': ('success' if 'approved' in subject.lower() else
                            'error' if 'rejected' in subject.lower() else
                            'warning' if 'deadline' in subject.lower() else 'info')
                }
                st.session_state.notifications.append(notification)

            return True

        except Exception as e:
            st.error(f"Failed to send notification: {str(e)}")
            return False

    def send_approval_notification(self, report_data, reviewer_notes=""):
        """Send approval notification"""
        subject = "Report Approved ✅"
        message = f"""
        Your report has been approved!
        
        Report Details:
        - ID: {report_data['id']}
        - Type: {report_data['type']}
        - Submission Date: {report_data['submission_date']}
        - Review Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
        Reviewer Notes:
        {reviewer_notes if reviewer_notes else "No additional notes provided."}
        """
        
        self.send_notification(
            recipient_email=report_data['officer_email'],  # Assuming email is stored in report data
            subject=subject,
            message=message,
            notification_type='both'
        )

    def send_rejection_notification(self, report_data, rejection_reason=""):
        """Send rejection notification"""
        subject = "Report Requires Revision ⚠️"
        message = f"""
        Your report needs revision.
        
        Report Details:
        - ID: {report_data['id']}
        - Type: {report_data['type']}
        - Submission Date: {report_data['submission_date']}
        - Review Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
        Reason for Revision:
        {rejection_reason if rejection_reason else "No specific reason provided."}
        
        Please review and resubmit your report.
        """
        
        self.send_notification(
            recipient_email=report_data['officer_email'],
            subject=subject,
            message=message,
            notification_type='both'
        )

    def send_deadline_reminder(self, officer_email, report_type, due_date):
        """Send deadline reminder notification"""
        subject = "⏰ Upcoming Report Deadline"
        message = f"""
        This is a reminder about an upcoming report deadline.
        
        Details:
        - Report Type: {report_type}
        - Due Date: {due_date.strftime("%Y-%m-%d")}
        - Time Remaining: {(due_date - datetime.now()).days} days
        
        Please ensure your report is submitted before the deadline.
        """
        
        self.send_notification(
            recipient_email=officer_email,
            subject=subject,
            message=message,
            notification_type='both'
        )

    def render_notifications(self):
        """Render system notifications in the dashboard"""
        if 'notifications' in st.session_state and st.session_state.notifications:
            with st.sidebar.expander("📫 Notifications", expanded=True):
                for notification in reversed(st.session_state.notifications):
                    # Color coding based on notification type
                    color = {
                        'success': '#28a745',
                        'error': '#dc3545',
                        'warning': '#ffc107',
                        'info': '#17a2b8'
                    }.get(notification['type'], '#6c757d')
                    
                    st.markdown(f"""
                        <div style="
                            padding: 10px;
                            margin: 5px 0;
                            border-left: 4px solid {color};
                            background: {'#2D3748' if st.get_option('theme.base') == 'dark' else '#f8f9fa'};
                            border-radius: 4px;">
                            <div style="font-weight: bold; color: {color};">
                                {notification['subject']}
                            </div>
                            <div style="font-size: 0.9em; margin-top: 5px;">
                                {notification['message']}
                            </div>
                            <div style="font-size: 0.8em; color: #666; margin-top: 5px;">
                                {notification['timestamp']}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

    def render_dashboard(self):
        """Render the performance dashboard"""
        st.title("📊 Performance Analytics Dashboard")

        # Date range selection
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now().date() - timedelta(days=30)
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now().date()
            )

        if start_date > end_date:
            st.error("Error: End date must be after start date")
            return

        # Load and process data
        df = self.load_performance_data(start_date, end_date)
        if df.empty:
            st.warning("No data available for the selected date range")
            return

        completion_rates = self.calculate_completion_rates(df)
        bottlenecks = self.identify_bottlenecks(df)
        officer_stats = self.analyze_officer_performance(df)
        trend_analysis = self.analyze_performance_trends(completion_rates)
        alerts = self.generate_performance_alerts(completion_rates, officer_stats, trend_analysis)

        # Display alerts with improvement suggestions
        if alerts:
            st.subheader("⚠️ Performance Alerts")
            for alert in alerts:
                if alert['type'] == 'danger':
                    with st.error(f"🔴 {alert['message']} - {alert['metric']}"):
                        st.write("**Suggested Improvements:**")
                        for suggestion in alert['improvement_suggestions']:
                            st.write(f"• {suggestion}")
                else:
                    with st.warning(f"🟡 {alert['message']} - {alert['metric']}"):
                        st.write("**Suggested Improvements:**")
                        for suggestion in alert['improvement_suggestions']:
                            st.write(f"• {suggestion}")

        # Render performance trends
        self.render_performance_trends(trend_analysis, completion_rates)

        # Performance Metrics
        st.subheader("📈 Key Performance Metrics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            overall_completion = df['is_on_time'].mean()
            st.metric(
                "Overall Completion Rate",
                f"{overall_completion:.1%}",
                delta=f"{(overall_completion - self.PERFORMANCE_THRESHOLD):.1%}"
            )
        
        with col2:
            st.metric("Pending Reviews", bottlenecks['pending_reviews'])
        
        with col3:
            st.metric("Late Submissions", bottlenecks['late_submissions'])

        # Completion Rate Trends
        st.subheader("📊 Completion Rate Trends")
        trend_tabs = st.tabs(["Monthly", "Weekly", "Daily"])
        
        with trend_tabs[0]:
            monthly_fig = px.line(
                x=completion_rates['monthly'].index,
                y=completion_rates['monthly'].values,
                title="Monthly Completion Rates",
                labels={'x': 'Month', 'y': 'Completion Rate'}
            )
            st.plotly_chart(monthly_fig, use_container_width=True)

        with trend_tabs[1]:
            weekly_fig = px.line(
                x=completion_rates['weekly'].index,
                y=completion_rates['weekly'].values,
                title="Weekly Completion Rates",
                labels={'x': 'Week', 'y': 'Completion Rate'}
            )
            st.plotly_chart(weekly_fig, use_container_width=True)

        with trend_tabs[2]:
            daily_fig = px.line(
                x=completion_rates['daily'].index,
                y=completion_rates['daily'].values,
                title="Daily Completion Rates",
                labels={'x': 'Date', 'y': 'Completion Rate'}
            )
            st.plotly_chart(daily_fig, use_container_width=True)

        # Officer Performance
        self.render_officer_performance(officer_stats)

        # Render notifications
        self.render_notifications()

    def render_officer_performance(self, officer_stats):
        """Render officer performance metrics and insights with dropdown sections"""
        if officer_stats.empty:
            st.warning("No performance data available for the selected period.")
            return

        # Get current theme
        is_dark_theme = st.get_option("theme.base") == "dark"
        
        # Color palette with better harmony
        colors = {
            'dark': {
                'background': '#FFD700',
                'card_bg': '#FFD700',
                'card_bg_alt': '#FFD700',
                'text': '#E2E8F0',
                'subtext': '#A0AEC0',
                'border': '#4A5568',
                'accent': '#63B3ED',
                'success': '#68D391',
                'warning': '#F6AD55',
                'danger': '#FC8181',
                'neutral': '#CBD5E0'
            },
            'light': {
                'background': '#272731',
                'card_bg': '#272731',
                'card_bg_alt': '000000',
                'text': '#ffffff',
                'subtext': '#4A5568',
                'border': '#CBD5E0',
                'accent': '#4299E1',
                'success': '#48BB78',
                'warning': '#ED8936',
                'danger': '#E53E3E',
                'neutral': '#718096'
            }
        }

        theme = colors['dark'] if is_dark_theme else colors['light']

        # Custom CSS with dropdown styling
        st.markdown(f"""
            <style>
            .stExpander {{
                background-color: {theme['card_bg']};
                border: 1px solid {theme['border']};
                border-radius: 8px;
                margin-bottom: 10px;
            }}
            .officer-metrics {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                margin-top: 10px;
            }}
            .metric-box {{
                background-color: {theme['card_bg_alt']};
                padding: 15px;
                border-radius: 8px;
                border: 1px solid {theme['border']};
            }}
            .metric-title {{
                color: {theme['subtext']};
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .metric-value {{
                color: {theme['text']};
                font-size: 20px;
                font-weight: bold;
                margin-top: 5px;
            }}
            .performance-indicator {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
                margin-top: 8px;
            }}
            .trend-arrow {{
                margin-left: 5px;
                font-size: 14px;
            }}
            </style>
        """, unsafe_allow_html=True)

        # Individual Performance Section
        st.subheader("👥 Individual Performance")
        
        # Sort officers by performance rating
        performance_order = {'High': 0, 'Medium': 1, 'Low': 2}
        sorted_officers = sorted(
            officer_stats.index,
            key=lambda x: (
                performance_order.get(officer_stats.loc[x, 'performance_rating'], 3),
                -officer_stats.loc[x, 'on_time_rate']
            )
        )

        # Create expandable sections for each officer
        for officer in sorted_officers:
            metrics = officer_stats.loc[officer]
            
            # Determine performance color
            performance_color = {
                'High': theme['success'],
                'Medium': theme['warning'],
                'Low': theme['danger']
            }.get(metrics['performance_rating'], theme['neutral'])
            
            # Create expander with performance indicator
            with st.expander(
                f"📊 {officer} - {metrics['performance_rating']} Performance",
                expanded=metrics['performance_rating'] == 'High'  # Auto-expand high performers
            ):
                # Performance metrics grid
                st.markdown(f"""
                    <div class='officer-metrics'>
                        <div class='metric-box'>
                            <div class='metric-title'>On-time Rate</div>
                            <div class='metric-value'>{metrics['on_time_rate']:.1%}</div>
                            <div class='performance-indicator' 
                                 style='background-color: {performance_color}20; color: {performance_color}'>
                                {metrics['performance_rating']} Performance
                                {'↑' if metrics['on_time_rate'] > 0.8 else '↓'}
                            </div>
                        </div>
                        <div class='metric-box'>
                            <div class='metric-title'>Same-day Rate</div>
                            <div class='metric-value'>{metrics['same_day_rate']:.1%}</div>
                        </div>
                        <div class='metric-box'>
                            <div class='metric-title'>Total Reports</div>
                            <div class='metric-value'>{metrics['total_reports']}</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # Additional performance insights
                if 'type_distribution' in metrics and metrics['type_distribution']:
                    st.markdown("#### Report Distribution")
                    fig = go.Figure(data=[
                        go.Pie(
                            labels=list(metrics['type_distribution'].keys()),
                            values=list(metrics['type_distribution'].values()),
                            hole=.4,
                            marker=dict(colors=[theme['success'], theme['warning'], theme['accent']])
                        )
                    ])
                    fig.update_layout(
                        showlegend=True,
                        margin=dict(l=20, r=20, t=20, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        height=200,
                        font=dict(color=theme['text'])
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Performance recommendations
                if metrics['performance_rating'] != 'High':
                    st.markdown(f"""
                        <div style='background-color: {theme['card_bg_alt']}; 
                                  padding: 15px; border-radius: 8px; margin-top: 10px;'>
                            <div style='color: {theme['text']}; font-weight: bold;'>
                                💡 Improvement Suggestions
                            </div>
                            <ul style='color: {theme['subtext']}; margin-top: 8px;'>
                                <li>Focus on improving submission timeliness</li>
                                <li>Maintain detailed documentation of challenges</li>
                                <li>Regular check-ins with supervisor for guidance</li>
                            </ul>
                        </div>
                    """, unsafe_allow_html=True)
