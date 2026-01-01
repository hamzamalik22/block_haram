from flask import Flask, render_template_string, request, redirect, url_for, flash, Response, stream_with_context, session
import os
import subprocess
import sys
import time
import re
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev_secret_key")

# --- 🔐 SECURITY CONFIGURATION ---
ADMIN_USERNAME = "user1"
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "admin")

# --- FILE CONFIG ---
BLOCK_DIR = "data/blocklists"
LOG_DIR = "logs"
QUERY_LOG = f"{LOG_DIR}/query.log"
JUDGE_LOG = f"{LOG_DIR}/judge.log"
DEPLOY_LOG = f"{LOG_DIR}/deploy.log"

AI_FILE = f"{BLOCK_DIR}/ai_blocks.txt"
WHITELIST_FILE = f"{BLOCK_DIR}/whitelist.txt"
BLACKLIST_FILE = f"{BLOCK_DIR}/blacklist.txt"
FINAL_FILE = f"{BLOCK_DIR}/final_blocklist.txt"

# --- LOGIN TEMPLATE ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login - NoHaram DNS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #1a1a1a; display: flex; align-items: center; justify-content: center; height: 100vh; color: #fff; }
        .login-card { background: #2d2d2d; padding: 2rem; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 100%; max-width: 400px; }
        .form-control { background: #3d3d3d; border: 1px solid #4d4d4d; color: #fff; }
        .form-control:focus { background: #4d4d4d; color: #fff; border-color: #0d6efd; box-shadow: none; }
        .btn-primary { width: 100%; font-weight: bold; margin-top: 1rem; }
    </style>
</head>
<body>
    <div class="login-card">
        <h3 class="text-center mb-4">🛡️ Supervisor Access</h3>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} py-2">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="post">
            <div class="mb-3">
                <label>Username</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            <div class="mb-3">
                <label>Password</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary">Login</button>
        </form>
    </div>
</body>
</html>
"""

# --- DASHBOARD TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>NoHaram DNS Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css">
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', system-ui, sans-serif; }
        .navbar { background: linear-gradient(135deg, #2c3e50 0%, #000000 100%); padding: 1rem; }
        .card { border: none; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 24px; }
        .stat-card { border-left: 5px solid transparent; transition: transform 0.2s; }
        .stat-card:hover { transform: translateY(-3px); }
        .stat-number { font-size: 2.2rem; font-weight: 800; line-height: 1; margin-bottom: 0.5rem; }
        .log-box { background: #111; color: #0f0; font-family: monospace; padding: 15px; border-radius: 8px; height: 400px; overflow-y: auto; font-size: 0.85rem; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top mb-4">
        <div class="container-fluid px-4">
            <a class="navbar-brand fw-bold" href="/"><i class="fas fa-shield-alt me-2"></i>NoHaram DNS</a>
            <div class="d-flex align-items-center gap-2">
                <a href="/run_judge_view" class="btn btn-warning fw-bold text-dark"><i class="fas fa-gavel me-2"></i>Run Judge</a>
                <form action="/deploy" method="post" class="d-inline">
                    <button type="submit" class="btn btn-danger fw-bold" onclick="return confirm('Apply changes?')"><i class="fas fa-sync-alt me-2"></i>Deploy</button>
                </form>
                <a href="/logout" class="btn btn-outline-light ms-2"><i class="fas fa-sign-out-alt"></i></a>
            </div>
        </div>
    </nav>

    <div class="container-fluid px-4">
        <div class="row g-4 mb-4">
            <div class="col-md-3">
                <div class="card stat-card h-100 p-3" style="border-left-color: #0d6efd;">
                    <div class="d-flex justify-content-between">
                        <div><div class="stat-number text-primary">{{ unique_users }}</div><small class="text-muted fw-bold">ACTIVE USERS</small></div>
                        <i class="fas fa-users fa-2x text-primary opacity-50"></i>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card h-100 p-3" style="border-left-color: #dc3545;">
                    <div class="d-flex justify-content-between">
                        <div><div class="stat-number text-danger">{{ bl_count }}</div><small class="text-muted fw-bold">MANUAL BLOCKS</small></div>
                        <i class="fas fa-ban fa-2x text-danger opacity-50"></i>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card h-100 p-3" style="border-left-color: #198754;">
                    <div class="d-flex justify-content-between">
                        <div><div class="stat-number text-success">{{ wl_count }}</div><small class="text-muted fw-bold">SAFE SITES</small></div>
                        <i class="fas fa-check-circle fa-2x text-success opacity-50"></i>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card h-100 p-3" style="border-left-color: #ffc107;">
                    <div class="d-flex justify-content-between">
                        <div><div class="stat-number text-warning">{{ ai_count }}</div><small class="text-muted fw-bold">AI SUSPECTS</small></div>
                        <i class="fas fa-robot fa-2x text-warning opacity-50"></i>
                    </div>
                </div>
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show shadow-sm">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card bg-light border-0 mb-4">
            <div class="card-body p-4">
                <h5 class="card-title mb-3"><i class="fas fa-search me-2"></i>Check Master Database</h5>
                <form action="/check_domain" method="post" class="row g-2">
                    <div class="col-md-9"><input type="text" name="check_domain" class="form-control" placeholder="Enter domain (e.g. tiktok.com)..." required></div>
                    <div class="col-md-3"><button type="submit" class="btn btn-dark w-100">Check Status</button></div>
                </form>
                {% if search_result %}
                    <div class="alert alert-{{ search_color }} mt-3 mb-0 fw-bold"><i class="fas fa-{{ search_icon }} me-2"></i> {{ search_result }}</div>
                {% endif %}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <ul class="nav nav-pills card-header-pills">
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'ai' %}active{% endif %}" href="/?tab=ai">Suspects</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'blacklist' %}active{% endif %}" href="/?tab=blacklist">Blacklist</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'whitelist' %}active{% endif %}" href="/?tab=whitelist">Whitelist</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'logs' %}active{% endif %}" href="/?tab=logs">Logs</a></li>
                </ul>
            </div>
            <div class="card-body">
                
                {% if active_tab == 'ai' %}
                    <form method="POST" action="/bulk_action">
                        <input type="hidden" name="source" value="ai">
                        <div class="d-flex justify-content-end mb-2 gap-2">
                            <button name="action" value="block" class="btn btn-outline-danger btn-sm">Block Selected</button>
                            <button name="action" value="whitelist" class="btn btn-outline-success btn-sm">Whitelist Selected</button>
                            <button name="action" value="delete" class="btn btn-outline-secondary btn-sm">Ignore</button>
                        </div>
                        <table class="table table-hover datatable"><thead><tr><th width="30"><input type="checkbox" class="selectAll"></th><th>Domain</th><th class="text-end">Actions</th></tr></thead><tbody>{% for domain in ai_domains %}<tr><td><input type="checkbox" name="domains" value="{{ domain }}"></td><td>{{ domain }}</td><td class="text-end"><a href="/move_to_blacklist/{{ domain }}" class="btn btn-sm btn-light text-danger"><i class="fas fa-ban"></i></a> <a href="/move_to_whitelist/{{ domain }}" class="btn btn-sm btn-light text-success"><i class="fas fa-check"></i></a></td></tr>{% endfor %}</tbody></table>
                    </form>

                {% elif active_tab == 'blacklist' %}
                    <form action="/add_blacklist" method="post" class="mb-3 input-group w-50">
                        <input type="text" name="domain" class="form-control" placeholder="Block domain manually...">
                        <button class="btn btn-danger">Block</button>
                    </form>
                    
                    <form method="POST" action="/bulk_action">
                        <input type="hidden" name="source" value="blacklist">
                        <div class="d-flex justify-content-end mb-2 gap-2">
                            <button name="action" value="whitelist" class="btn btn-outline-success btn-sm">Move to Whitelist</button>
                            <button name="action" value="delete" class="btn btn-outline-secondary btn-sm">Delete Selected</button>
                        </div>
                        <table class="table table-hover datatable">
                            <thead><tr><th width="30"><input type="checkbox" class="selectAll"></th><th>Blocked Domain</th><th class="text-end">Action</th></tr></thead>
                            <tbody>
                                {% for domain in bl_domains %}
                                <tr>
                                    <td><input type="checkbox" name="domains" value="{{ domain }}"></td>
                                    <td class="text-danger fw-bold">{{ domain }}</td>
                                    <td class="text-end"><a href="/remove_blacklist/{{ domain }}" class="btn btn-sm btn-light"><i class="fas fa-trash"></i></a></td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </form>

                {% elif active_tab == 'whitelist' %}
                     <form method="POST" action="/bulk_action">
                        <input type="hidden" name="source" value="whitelist">
                        <div class="d-flex justify-content-end mb-2 gap-2">
                            <button name="action" value="block" class="btn btn-outline-danger btn-sm">Move to Blacklist</button>
                            <button name="action" value="delete" class="btn btn-outline-secondary btn-sm">Delete Selected</button>
                        </div>
                        <table class="table table-hover datatable">
                            <thead><tr><th width="30"><input type="checkbox" class="selectAll"></th><th>Safe Domain</th><th class="text-end">Action</th></tr></thead>
                            <tbody>
                                {% for domain in wl_domains %}
                                <tr>
                                    <td><input type="checkbox" name="domains" value="{{ domain }}"></td>
                                    <td class="text-success fw-bold">{{ domain }}</td>
                                    <td class="text-end"><a href="/remove_whitelist/{{ domain }}" class="btn btn-sm btn-light"><i class="fas fa-trash"></i></a></td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </form>

                {% elif active_tab == 'logs' %}
                    <div class="row"><div class="col-md-6"><h6>Judge Logs</h6><div class="log-box">{{ judge_logs }}</div></div><div class="col-md-6"><h6>Deploy Logs</h6><div class="log-box">{{ deploy_logs }}</div></div></div>
                {% endif %}
            </div>
        </div>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script><script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script><script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
    <script>
        $(document).ready(function(){
            $('.datatable').DataTable({"pageLength":10,"lengthMenu":[10,25,50]});
            $('.selectAll').on('click',function(){$('input[type="checkbox"]',$(this).closest('table').find('tbody tr')).prop('checked',this.checked);});
        });
    </script>
</body></html>
"""
LOG_TEMPLATE = """<!DOCTYPE html><html><head><title>Live</title><style>body{background:#000;color:#0f0;font-family:monospace;padding:20px}.line{border-bottom:1px solid #222;padding:2px}</style></head><body><h3>Running Judge...</h3><div id="log"></div><script>const log=document.getElementById('log');const es=new EventSource("/stream_judge");es.onmessage=function(e){if(e.data.includes("DONE_SIGNAL")){window.location.href='/';return;}const div=document.createElement('div');div.className='line';div.innerText=e.data;log.appendChild(div);window.scrollTo(0,document.body.scrollHeight);};</script></body></html>"""

# --- HELPERS ---
def get_lines(filepath):
    if not os.path.exists(filepath): return []
    with open(filepath, "r") as f: return sorted(list(set([l.strip() for l in f if l.strip()])))

def save_lines(filepath, lines):
    with open(filepath, "w") as f: f.write("\n".join(lines) + "\n")

def count_unique_users():
    if not os.path.exists(QUERY_LOG): return 0
    unique_ips = set()
    try:
        cmd = f"tail -n 5000 {QUERY_LOG}"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        ips = re.findall(r'\[INFO\]\s+([0-9a-fA-F:.]+):\d+\s+-', output)
        for ip in ips:
            if ip not in ['127.0.0.1', '::1']: unique_ips.add(ip)
    except: return 0
    return len(unique_ips)

def read_log_tail(filepath, n=100):
    if not os.path.exists(filepath): return "No logs."
    try: return subprocess.check_output(['tail', '-n', str(n), filepath]).decode('utf-8')
    except: return "Error."

# --- LOGIN DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USERNAME and pw == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials!", "danger")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    tab = request.args.get('tab', 'ai')
    return render_template_string(HTML_TEMPLATE, active_tab=tab,
                                  ai_domains=get_lines(AI_FILE), ai_count=len(get_lines(AI_FILE)),
                                  bl_domains=get_lines(BLACKLIST_FILE), bl_count=len(get_lines(BLACKLIST_FILE)),
                                  wl_domains=get_lines(WHITELIST_FILE), wl_count=len(get_lines(WHITELIST_FILE)),
                                  judge_logs=(read_log_tail(JUDGE_LOG) if tab=='logs' else ""),
                                  deploy_logs=(read_log_tail(DEPLOY_LOG) if tab=='logs' else ""),
                                  unique_users=count_unique_users())

@app.route('/check_domain', methods=['POST'])
@login_required
def check_domain():
    domain = request.form.get('check_domain').strip().lower()
    res, color, icon = f"{domain} is ALLOWED", "secondary", "globe"
    if domain in get_lines(WHITELIST_FILE): res, color, icon = f"{domain} is SAFE (Whitelisted)", "success", "check-circle"
    elif domain in get_lines(BLACKLIST_FILE): res, color, icon = f"{domain} is BLOCKED (Manual)", "danger", "ban"
    else:
        try: subprocess.check_call(['grep', '-q', f"0.0.0.0 {domain}$", FINAL_FILE]); res, color, icon = f"{domain} is BLOCKED (Database)", "danger", "ban"
        except: pass
    return render_template_string(HTML_TEMPLATE, active_tab='ai', search_result=res, search_color=color, search_icon=icon,
                                  unique_users=count_unique_users(),
                                  ai_domains=get_lines(AI_FILE), ai_count=len(get_lines(AI_FILE)),
                                  bl_domains=get_lines(BLACKLIST_FILE), bl_count=len(get_lines(BLACKLIST_FILE)),
                                  wl_domains=get_lines(WHITELIST_FILE), wl_count=len(get_lines(WHITELIST_FILE)))

@app.route('/run_judge_view')
@login_required
def run_judge_view(): return render_template_string(LOG_TEMPLATE)

@app.route('/stream_judge')
@login_required
def stream_judge():
    def generate():
        p = subprocess.Popen([sys.executable, '-u', "src/ai_worker/judge.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for l in iter(p.stdout.readline, b''): yield f"data: {l.decode('utf-8').strip()}\n\n"
        p.stdout.close()
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/bulk_action', methods=['POST'])
@login_required
def bulk_action():
    action = request.form.get('action')
    source = request.form.get('source')
    domains = request.form.getlist('domains')
    
    if not domains: return redirect(url_for('index', tab=source))

    # Determine Source File
    source_file = AI_FILE if source=='ai' else (BLACKLIST_FILE if source=='blacklist' else WHITELIST_FILE)
    lines = get_lines(source_file)
    
    # 1. DELETE ACTION
    if action == 'delete':
        for d in domains: 
            if d in lines: lines.remove(d)
        save_lines(source_file, lines)
        flash(f"Deleted {len(domains)} domains from {source}.", "secondary")

    # 2. BLOCK ACTION
    elif action == 'block':
        bl_lines = get_lines(BLACKLIST_FILE)
        for d in domains:
            if d in lines: lines.remove(d)
            if d not in bl_lines: bl_lines.append(d)
        save_lines(source_file, lines)
        save_lines(BLACKLIST_FILE, bl_lines)
        flash(f"Blocked {len(domains)} domains.", "danger")

    # 3. WHITELIST ACTION
    elif action == 'whitelist':
        wl_lines = get_lines(WHITELIST_FILE)
        for d in domains:
            if d in lines: lines.remove(d)
            if d not in wl_lines: wl_lines.append(d)
        save_lines(source_file, lines)
        save_lines(WHITELIST_FILE, wl_lines)
        flash(f"Whitelisted {len(domains)} domains.", "success")

    return redirect(url_for('index', tab=source))

@app.route('/move_to_blacklist/<d>')
@login_required
def move_to_blacklist(d): l=get_lines(AI_FILE); (l.remove(d) if d in l else None); save_lines(AI_FILE, l); bl=get_lines(BLACKLIST_FILE); (bl.append(d) if d not in bl else None); save_lines(BLACKLIST_FILE, bl); return redirect(url_for('index', tab='ai'))

@app.route('/move_to_whitelist/<d>')
@login_required
def move_to_whitelist(d): l=get_lines(AI_FILE); (l.remove(d) if d in l else None); save_lines(AI_FILE, l); wl=get_lines(WHITELIST_FILE); (wl.append(d) if d not in wl else None); save_lines(WHITELIST_FILE, wl); return redirect(url_for('index', tab='ai'))

@app.route('/add_blacklist', methods=['POST'])
@login_required
def add_blacklist(): d=request.form.get('domain').strip(); l=get_lines(BLACKLIST_FILE); (l.append(d) if d and d not in l else None); save_lines(BLACKLIST_FILE, l); return redirect(url_for('index', tab='blacklist'))

@app.route('/remove_blacklist/<d>')
@login_required
def remove_blacklist(d): l=get_lines(BLACKLIST_FILE); (l.remove(d) if d in l else None); save_lines(BLACKLIST_FILE, l); return redirect(url_for('index', tab='blacklist'))

@app.route('/remove_whitelist/<d>')
@login_required
def remove_whitelist(d): l=get_lines(WHITELIST_FILE); (l.remove(d) if d in l else None); save_lines(WHITELIST_FILE, l); return redirect(url_for('index', tab='whitelist'))

@app.route('/deploy', methods=['POST'])
@login_required
def deploy(): subprocess.Popen(["bash", "src/auto_deploy.sh"]); flash("System updating... Check Logs.", "info"); return redirect(url_for('index'))

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, threaded=True)
