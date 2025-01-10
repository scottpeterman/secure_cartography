import sys
import os
import traceback

import yaml
import time
from datetime import datetime
from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QListWidget,
    QMessageBox, QGroupBox, QGridLayout, QLineEdit, QFileDialog
)
from PyQt6.QtCore import QProcess, QTimer, Qt
from admin.job_editor import SchemaBasedJobDialog

class Job:
    """Represents a job loaded from YAML configuration."""

    def __init__(self, name: str, script: str, args: List[str],
                 schedule: str = "manual", log_file: Optional[str] = None):
        self.name = name
        self.script = script
        self.args = args
        self.schedule = schedule
        self.log_file = log_file
        self.process = None
        self.status = "idle"  # idle, running, completed, failed
        self.last_run = None
        self.next_run = None

    @classmethod
    def from_yaml_data(cls, data: Dict) -> 'Job':
        """Create a Job instance from YAML data."""
        return cls(
            name=data['name'],
            script=data['script'],
            args=data.get('args', []),
            schedule=data.get('schedule', 'manual'),
            log_file=data.get('log_file')
        )

    def to_dict(self) -> Dict:
        """Convert job to dictionary format for YAML storage."""
        return {
            'name': self.name,
            'script': self.script,
            'args': self.args,
            'schedule': self.schedule,
            'log_file': self.log_file
        }



def main():
    app = QApplication(sys.argv)

    # Parse command line arguments
    jobs_file = "jobs.yaml"
    if len(sys.argv) > 1:
        jobs_file = sys.argv[1]

    scheduler = SchedulerWidget(jobs_file)
    scheduler.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
class Job:
    """Represents a job loaded from YAML configuration."""

    def __init__(self, name: str, script: str, args: List[str],
                 schedule: str = "manual", log_file: Optional[str] = None):
        self.name = name
        self.script = script
        self.args = args
        self.schedule = schedule
        self.log_file = log_file
        self.process = None
        self.status = "idle"  # idle, running, completed, failed
        self.last_run = None
        self.next_run = None

    @classmethod
    def from_yaml_data(cls, data: Dict) -> 'Job':
        """Create a Job instance from YAML data."""
        return cls(
            name=data['name'],
            script=data['script'],
            args=data.get('args', []),
            schedule=data.get('schedule', 'manual'),
            log_file=data.get('log_file')
        )


class SchedulerWidget(QWidget):
    def __init__(self, jobs_file: str = "jobs.yaml"):
        super().__init__()
        self.jobs_file = jobs_file
        self.jobs: List[Job] = []
        self.current_job = None

        # Setup UI
        self.setup_ui()

        # Load jobs from YAML
        self.load_jobs()

        # Setup scheduler timer
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_jobs)
        self.scheduler_timer.start(60000)  # Check every minute

    def setup_ui(self):
        """Initialize the user interface."""
        from PyQt6.QtWidgets import QSplitter
        from PyQt6.QtCore import Qt

        # Main layout
        main_layout = QVBoxLayout(self)

        # Create splitter for upper section
        upper_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Job List
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for cleaner look

        # Add job list section
        left_layout.addWidget(QLabel("Jobs"))
        self.job_list = QListWidget()
        self.job_list.currentRowChanged.connect(self.on_job_selected)
        self.job_list.itemDoubleClicked.connect(self.edit_job)
        left_layout.addWidget(self.job_list)

        # Job file management buttons
        button_layout = QHBoxLayout()

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload_jobs)
        button_layout.addWidget(reload_btn)

        load_btn = QPushButton("Load Jobs")
        load_btn.clicked.connect(self.load_different_jobs)
        button_layout.addWidget(load_btn)

        save_as_btn = QPushButton("Save As")
        save_as_btn.clicked.connect(self.save_jobs_as)
        button_layout.addWidget(save_as_btn)

        left_layout.addLayout(button_layout)

        left_panel.setLayout(left_layout)
        upper_splitter.addWidget(left_panel)
        left_panel.setMaximumWidth(200)

        # Right panel - Job Details
        right_panel = QWidget()
        right_panel.setMaximumWidth(600)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for cleaner look

        # Job details group
        details_group = QGroupBox("Job Details")
        details_group.setMaximumWidth(400)
        details_grid = QGridLayout()

        # Add readonly detail fields
        self.script_label = QLabel("")
        self.args_label = QLineEdit("")
        self.args_label.setReadOnly(False)
        self.args_label.setMaximumWidth(300)
        self.args_label.setFrame(False)
        self.schedule_label = QLabel("")
        self.status_label = QLabel("")
        self.last_run_label = QLabel("")

        details_grid.addWidget(QLabel("Script:"), 0, 0)
        details_grid.addWidget(self.script_label, 0, 1)
        details_grid.addWidget(QLabel("Arguments:"), 1, 0)
        details_grid.addWidget(self.args_label, 1, 1)
        details_grid.addWidget(QLabel("Schedule:"), 2, 0)
        details_grid.addWidget(self.schedule_label, 2, 1)
        details_grid.addWidget(QLabel("Status:"), 3, 0)
        details_grid.addWidget(self.status_label, 3, 1)
        details_grid.addWidget(QLabel("Last Run:"), 4, 0)
        details_grid.addWidget(self.last_run_label, 4, 1)

        details_group.setLayout(details_grid)
        right_layout.addWidget(details_group)

        # Control buttons
        control_button_layout = QHBoxLayout()

        # Create equal-width buttons
        min_button_width = 120

        self.run_btn = QPushButton("Run")
        self.run_btn.setMinimumWidth(min_button_width)
        self.run_btn.clicked.connect(self.run_selected_job)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumWidth(min_button_width)
        self.stop_btn.clicked.connect(self.stop_selected_job)

        self.upload_btn = QPushButton("Upload Data")
        self.upload_btn.setMinimumWidth(min_button_width)
        self.upload_btn.clicked.connect(self.run_upload_data)

        # Add buttons to layout with equal spacing
        control_button_layout.addWidget(self.run_btn)
        control_button_layout.addWidget(self.stop_btn)
        control_button_layout.addWidget(self.upload_btn)

        # Add stretches to ensure proper spacing
        control_button_layout.addStretch()

        right_layout.addLayout(control_button_layout)
        right_layout.addStretch()  # Add stretch to keep controls at top

        right_panel.setLayout(right_layout)
        upper_splitter.addWidget(right_panel)

        # Set initial sizes for the splitter (40% left, 60% right)
        upper_splitter.setSizes([200, 300])

        # Add splitter to main layout
        main_layout.addWidget(upper_splitter)

        # Output section at the bottom
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setMinimumHeight(300)
        self.output_display.setMaximumWidth(800)
        main_layout.addWidget(self.output_display)
    def run_upload_data(self) -> None:
        """Run the upload wrapper to process all data files."""
        if not self.jobs_file:
            self.output_display.append("No jobs file loaded. Please load a jobs file first.")
            return

        if any(job.status == "running" for job in self.jobs):
            QMessageBox.warning(self, "Error", "Cannot upload while jobs are running")
            return

        # Create and configure process
        self.upload_process = QProcess()
        self.upload_process.readyReadStandardOutput.connect(
            lambda: self.handle_output(self.upload_process)
        )
        self.upload_process.readyReadStandardError.connect(
            lambda: self.handle_error(self.upload_process)
        )
        self.upload_process.finished.connect(self.handle_upload_finished)

        try:
            # Clear previous output
            self.output_display.clear()

            # Build command using module notation
            cmd = [sys.executable, "-m", "surveyor.upload_wrapper",
                   "--jobs-file", self.jobs_file, "-v"]

            self.output_display.append(f"Starting upload process with command: {' '.join(cmd)}")

            # Disable buttons during upload
            self.upload_btn.setEnabled(False)
            self.run_btn.setEnabled(False)

            # Start the process
            self.upload_process.start(cmd[0], cmd[1:])

        except Exception as e:
            self.output_display.append(f"Error starting upload process: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error starting upload process: {str(e)}")
            self.upload_btn.setEnabled(True)
            self.run_btn.setEnabled(True)

    def handle_upload_finished(self, exit_code: int, exit_status: int) -> None:
        """Handle completion of the upload process."""
        if exit_code == 0:
            self.output_display.append("Upload process completed successfully")
        else:
            self.output_display.append(f"Upload process failed with exit code {exit_code}")

        # Re-enable buttons
        self.upload_btn.setEnabled(True)
        self.run_btn.setEnabled(True)

    def load_different_jobs(self):
        """Open file dialog to load a different jobs file."""
        jobs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jobs')
        os.makedirs(jobs_dir, exist_ok=True)

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Jobs File",
            jobs_dir,
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )

        if filename:
            self.jobs_file = filename
            self.load_jobs()
            self.output_display.append(f"Loaded jobs from: {filename}")

    def save_jobs_as(self):
        """Save current jobs to a new file."""
        jobs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jobs')
        os.makedirs(jobs_dir, exist_ok=True)

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Jobs As",
            jobs_dir,
            "YAML Files (*.yaml);;All Files (*)"
        )

        if filename:
            old_jobs_file = self.jobs_file
            self.jobs_file = filename
            self.save_jobs()
            self.jobs_file = old_jobs_file  # Restore original jobs file
            self.output_display.append(f"Saved jobs to: {filename}")
    def edit_job(self, item):
        """Handle double-click on job list item."""
        job_index = self.job_list.row(item)
        if job_index >= 0 and job_index < len(self.jobs):
            job = self.jobs[job_index]

            try:
                # Get base script name without path
                script_basename = os.path.basename(job.script)
                schema_name = f"{os.path.splitext(script_basename)[0]}_schema.json"

                # Get project root directory (where main_ui.py is)
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                # Construct path to schema file in admin directory
                schema_name = 'admin/' + schema_name
                schema_path = os.path.join(project_root, schema_name)

                self.output_display.append(f"Loading schema from: {schema_path}")

                if not os.path.exists(schema_path):
                    raise FileNotFoundError(f"Schema file not found: {schema_path}")

                # Create job data dictionary
                job_data = {
                    'name': job.name,
                    'script': job.script,
                    'args': job.args,
                    'schedule': job.schedule,
                    'log_file': job.log_file
                }

                dialog = SchemaBasedJobDialog(
                    job_data=job_data,
                    schema_file=schema_path,
                    parent=self
                )

                if dialog.exec():
                    updated_data = dialog.get_job_data()

                    # Create a new Job instance with the updated data
                    updated_job = Job(
                        name=updated_data['name'],
                        script=updated_data['script'],
                        args=updated_data['args'],
                        schedule=updated_data['schedule'],
                        log_file=updated_data['log_file']
                    )

                    # Replace the old job with the new one
                    self.jobs[job_index] = updated_job

                    # Save and reload
                    self.save_jobs()
                    self.reload_jobs()

            except Exception as e:
                traceback.print_exc()
                error_msg = f"Error loading job editor: {str(e)}\nSchema path: {schema_path}"
                self.output_display.append(error_msg)
                QMessageBox.critical(self, "Error", error_msg)

    def job_to_dict(self, job) -> dict:
        """Convert a Job object to a dictionary for YAML storage."""
        return {
            'name': job.name,
            'script': job.script,
            'args': job.args,
            'schedule': job.schedule,
            'log_file': job.log_file
        }

    def save_jobs(self) -> None:
        """Save jobs to YAML file."""
        try:
            data = {'jobs': [self.job_to_dict(job) for job in self.jobs]}
            os.makedirs(os.path.dirname(os.path.abspath(self.jobs_file)), exist_ok=True)
            with open(self.jobs_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
        except Exception as e:
            self.output_display.append(f"Error saving jobs: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error saving jobs: {str(e)}")

    def load_jobs(self) -> None:
        """Load jobs from YAML file."""
        try:
            if not os.path.exists(self.jobs_file):
                self.output_display.append(f"Jobs file not found: {self.jobs_file}")
                return

            with open(self.jobs_file, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'jobs' not in data:
                self.output_display.append("No jobs found in YAML file")
                return

            self.jobs = []
            self.job_list.clear()

            for job_data in data['jobs']:
                job = Job.from_yaml_data(job_data)
                self.jobs.append(job)
                self.job_list.addItem(job.name)

            self.output_display.append(f"Loaded {len(self.jobs)} jobs from {self.jobs_file}")

        except Exception as e:
            self.output_display.append(f"Error loading jobs: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error loading jobs: {str(e)}")

    def reload_jobs(self) -> None:
        """Reload jobs from YAML file."""
        # Stop any running jobs
        for job in self.jobs:
            if job.status == "running" and job.process:
                job.process.terminate()
                if not job.process.waitForFinished(5000):
                    job.process.kill()

        self.load_jobs()

    # Change this section in run_selected_job method:
    def run_selected_job(self) -> None:
        """Run the currently selected job."""
        if not self.current_job:
            return

        if self.current_job.status == "running":
            QMessageBox.warning(self, "Error", "Job is already running")
            return

        # Create and configure process
        self.current_job.process = QProcess()
        self.current_job.process.readyReadStandardOutput.connect(
            lambda: self.handle_output(self.current_job.process)
        )
        self.current_job.process.readyReadStandardError.connect(
            lambda: self.handle_error(self.current_job.process)
        )
        self.current_job.process.finished.connect(
            lambda: self.handle_finished(self.current_job)
        )

        try:
            # Ensure log directory exists if log file is specified
            if self.current_job.log_file:
                os.makedirs(os.path.dirname(self.current_job.log_file), exist_ok=True)
            self.output_display.setText("")
            # Start process using module notation
            cmd = [sys.executable, "-m",
                   f"surveyor.{os.path.splitext(self.current_job.script)[0]}"] + self.current_job.args
            self.output_display.append(f"Running command: {' '.join(cmd)}")

            self.current_job.process.start(cmd[0], cmd[1:])
            self.current_job.status = "running"
            self.current_job.last_run = datetime.now()
            self.update_job_display()

            self.output_display.append(f"Started job: {self.current_job.name}")

        except Exception as e:
            self.output_display.append(f"Error starting job: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error starting job: {str(e)}")
            self.current_job.status = "failed"
            self.update_job_display()


    def stop_selected_job(self) -> None:
        """Stop the currently selected job."""
        if not self.current_job or not self.current_job.process:
            return

        try:
            self.current_job.process.terminate()
            if not self.current_job.process.waitForFinished(5000):
                self.current_job.process.kill()

            self.output_display.append(f"Stopped job: {self.current_job.name}")

        except Exception as e:
            self.output_display.append(f"Error stopping job: {str(e)}")

    def handle_output(self, process: QProcess) -> None:
        """Handle process standard output."""
        data = process.readAllStandardOutput()
        text = bytes(data).decode('utf-8')
        self.output_display.append(text)

        # Write to log file if specified
        if self.current_job and self.current_job.log_file:
            try:
                with open(self.current_job.log_file, 'a') as f:
                    f.write(text + '\n')
            except Exception as e:
                self.output_display.append(f"Error writing to log: {str(e)}")

    def handle_error(self, process: QProcess) -> None:
        """Handle process standard error."""
        data = process.readAllStandardError()
        text = bytes(data).decode('utf-8')
        self.output_display.append(f"Log: {text}")

        # Write to log file if specified
        if self.current_job and self.current_job.log_file:
            try:
                with open(self.current_job.log_file, 'a') as f:
                    f.write(f"Error: {text}\n")
            except Exception as e:
                self.output_display.append(f"Error writing to log: {str(e)}")

    def handle_finished(self, job: Job) -> None:
        """Handle process completion."""
        exit_code = job.process.exitCode()
        job.status = "completed" if exit_code == 0 else "failed"
        job.process = None
        self.update_job_display()

        status_msg = f"Job {job.name} finished with status: {job.status}"
        self.output_display.append(status_msg)

        # Write completion status to log
        if job.log_file:
            try:
                with open(job.log_file, 'a') as f:
                    f.write(f"\n{status_msg}\n")
            except Exception as e:
                self.output_display.append(f"Error writing to log: {str(e)}")

    def check_scheduled_jobs(self) -> None:
        """Check and run scheduled jobs."""
        current_time = datetime.now()

        for job in self.jobs:
            if not job.schedule or job.schedule == "manual" or job.status == "running":
                continue

            try:
                from croniter import croniter

                # Extract cron expression from schedule field
                cron_expr = job.schedule.replace("cron:", "").strip()

                if croniter.match(cron_expr, current_time):
                    self.current_job = job
                    self.run_selected_job()

            except Exception as e:
                self.output_display.append(f"Error checking schedule for {job.name}: {str(e)}")

    def update_job_display(self) -> None:
        """Update job details display."""
        if not self.current_job:
            self.script_label.setText("")
            self.args_label.setText("")
            self.schedule_label.setText("")
            self.status_label.setText("")
            self.last_run_label.setText("")
            return

        self.script_label.setText(self.current_job.script)
        self.args_label.setText(" ".join(self.current_job.args))
        self.schedule_label.setText(self.current_job.schedule)
        self.status_label.setText(self.current_job.status)
        self.last_run_label.setText(
            self.current_job.last_run.strftime("%Y-%m-%d %H:%M:%S")
            if self.current_job.last_run else "Never"
        )

    def on_job_selected(self, index: int) -> None:
        """Handle job selection in list."""
        if index < 0 or index >= len(self.jobs):
            self.current_job = None
        else:
            self.current_job = self.jobs[index]

        self.update_job_display()

    def closeEvent(self, event) -> None:
        """Handle application close."""
        # Stop all running jobs
        for job in self.jobs:
            if job.status == "running" and job.process:
                job.process.terminate()
                job.process.waitForFinished(1000)

        # Stop upload process if running
        if hasattr(self, 'upload_process') and self.upload_process:
            self.upload_process.terminate()
            self.upload_process.waitForFinished(1000)

        event.accept()


def main():
    app = QApplication(sys.argv)

    # Parse command line arguments
    jobs_file = "jobs.yaml"
    if len(sys.argv) > 1:
        jobs_file = sys.argv[1]

    scheduler = SchedulerWidget(jobs_file)
    scheduler.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()