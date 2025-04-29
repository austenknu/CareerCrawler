import logging
import os
from flask import Flask, render_template, request, redirect, url_for, abort

from .config_loader import get_config
from .database import get_dashboard_jobs, update_job_status

log = logging.getLogger(__name__)

# Determine the correct template folder path relative to the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')

app = Flask(__name__, template_folder=template_dir)

# Basic security measure - generate a secret key
# In a real app, use environment variables or a config file
app.config['SECRET_KEY'] = os.urandom(24)

# --- Routes ---

@app.route('/')
def index():
    current_view = request.args.get('view', 'active') # Default to active
    filter_applied = (current_view == 'applied')
    filter_ignored = (current_view == 'ignored')

    jobs = get_dashboard_jobs(filter_applied=filter_applied, filter_ignored=filter_ignored)

    title_map = {
        'active': "Active Jobs",
        'applied': "Applied Jobs",
        'ignored': "Ignored Jobs"
    }
    page_title = title_map.get(current_view, "Active Jobs")

    return render_template('index.html',
                           jobs=jobs,
                           title=page_title,
                           current_view=current_view)

@app.route('/job/<int:job_id>/apply', methods=['POST'])
def mark_applied(job_id):
    current_view = request.form.get('current_view', 'active')
    success = update_job_status(job_id=job_id, applied=True)
    if not success:
        log.error(f"Failed to mark job {job_id} as applied.")
        # Add flash message or error handling here later
    return redirect(url_for('index', view=current_view))

@app.route('/job/<int:job_id>/unapply', methods=['POST'])
def mark_unapplied(job_id):
    current_view = request.form.get('current_view', 'active')
    success = update_job_status(job_id=job_id, applied=False)
    if not success:
        log.error(f"Failed to mark job {job_id} as un-applied.")
    return redirect(url_for('index', view=current_view))


@app.route('/job/<int:job_id>/ignore', methods=['POST'])
def mark_ignored(job_id):
    current_view = request.form.get('current_view', 'active')
    success = update_job_status(job_id=job_id, ignored=True)
    if not success:
        log.error(f"Failed to mark job {job_id} as ignored.")
    return redirect(url_for('index', view=current_view))

@app.route('/job/<int:job_id>/unignore', methods=['POST'])
def mark_unignored(job_id):
    current_view = request.form.get('current_view', 'active')
    success = update_job_status(job_id=job_id, ignored=False)
    if not success:
        log.error(f"Failed to mark job {job_id} as un-ignored.")
    return redirect(url_for('index', view=current_view))


# --- App Runner ---

def run_dashboard():
    config = get_config()
    if not config:
        log.error("Configuration not loaded. Cannot start dashboard.")
        return

    dash_config = config.get('dashboard', {})
    host = dash_config.get('host', '127.0.0.1')
    port = int(dash_config.get('port', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true' # Allow override via env var

    log.info(f"Starting Flask dashboard on http://{host}:{port} (Debug: {debug_mode})")
    try:
        app.run(host=host, port=port, debug=debug_mode)
    except Exception as e:
        log.error(f"Failed to run Flask app: {e}", exc_info=True) 