#!/usr/bin/env python3
"""
GA Monitor — lightweight status dashboard
Usage: python3 server.py [port]
Default port: 10000
"""
import json, os, subprocess, re, glob, time, threading, functools
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.environ.get('GA_BACKUP_DIR', "/home/moclaw/backups/ocip")
TEMP_DIR = os.environ.get('GA_TEMP_DIR', os.path.join(ROOT, "temp"))
HANDOFFS_FILE = os.environ.get('GA_HANDOFFS_FILE', os.path.join(ROOT, "memory", "handoffs", "handoffs.jsonl"))
PLAN_FILE = os.environ.get('GA_PLAN_FILE', os.path.join(ROOT, "plan_ocip_os_upgrade", "plan.md"))
TASKS_FILE = os.environ.get('GA_TASKS_FILE', os.path.join(ROOT, "ga_monitor", "task_status.json"))
CACHE_TTL = int(os.environ.get('GA_CACHE_TTL', '5'))

# ---- Cache decorator ----
cache_store = {}
cache_lock = threading.Lock()
def cached(ttl=CACHE_TTL):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            with cache_lock:
                hit = cache_store.get(key)
                if hit and time.time() - hit['ts'] < ttl:
                    return hit['data']
            result = fn(*args, **kwargs)
            with cache_lock:
                cache_store[key] = {'data': result, 'ts': time.time()}
            return result
        return wrapper
    return deco

HOSTS = ["amtaa","amtab","amtac","jpkaaa","jpkab","jpkac","jpkba","jpkbb","jpkbc",
         "krkaa","krkab","krkac","krkad","krkca","krkcb","krrea","krreb"]

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GA Monitor</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}
h1{font-size:24px;margin-bottom:16px;color:#38bdf8}
h2{font-size:18px;margin:20px 0 10px;color:#94a3b8;border-bottom:1px solid #334155;padding-bottom:6px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.clock{font-size:14px;color:#64748b;font-family:monospace}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
.card{background:#1e293b;border-radius:8px;padding:12px;border:1px solid #334155}
.card-good{border-color:#22c55e}.card-warn{border-color:#f59e0b}.card-bad{border-color:#ef4444}
.card .name{font-weight:600;font-size:14px;margin-bottom:4px}
.card .meta{font-size:12px;color:#94a3b8;margin-bottom:4px}
.card .status{font-size:13px;margin:4px 0}
.card .status .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot-green{background:#22c55e}.dot-yellow{background:#f59e0b}.dot-red{background:#ef4444}.dot-gray{background:#64748b}
pre{font-size:11px;color:#94a3b8;white-space:pre-wrap;word-break:break-all;max-height:60px;overflow:hidden;margin-top:4px}
.out-preview{max-width:300px;max-height:200px;overflow:auto;text-overflow:unset;white-space:pre-wrap;font-size:11px;margin:0;color:#94a3b8}
.subagent-table{width:100%;border-collapse:collapse;font-size:13px}
.subagent-table th{text-align:left;color:#94a3b8;padding:6px 8px;border-bottom:1px solid #334155;font-weight:500}
.subagent-table td{padding:6px 8px;border-bottom:1px solid #1e293b;vertical-align:top}
.host-grid{display:flex;flex-wrap:wrap;gap:6px}
.host-item{display:inline-flex;align-items:center;gap:4px;background:#1e293b;padding:4px 10px;border-radius:4px;font-size:12px}
.footer{margin-top:30px;text-align:center;font-size:11px;color:#475569}
.refresh-btn{background:#334155;border:1px solid #475569;color:#e2e8f0;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px}
.refresh-btn:hover{background:#475569}
.log-btn{background:#334155;border:1px solid #475569;color:#e2e8f0;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:14px}
.log-btn:hover{background:#475569}
.log-content{font-size:11px;max-height:200px;overflow:auto;background:#1e293b;padding:8px;border-radius:4px;color:#94a3b8;white-space:pre-wrap}
.dimmed{opacity:0.5}
.phase-row{background:#1e293b;border-radius:6px;padding:8px 12px;margin-bottom:8px}
.phase-label{font-size:12px;color:#94a3b8;margin-bottom:4px}
.phase-bar{height:8px;background:#334155;border-radius:4px;overf
...[Truncated]...
h:100%;transition:width 1s}
.phase-progress{background:#eab308;height:100%;transition:width 1s}
.phase-items{display:flex;flex-wrap:wrap;gap:4px}
.phase-item{font-size:10px;background:#334155;padding:2px 6px;border-radius:3px;color:#94a3b8}
/* ===== Tasks Dashboard ===== */
.task-type-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:11px;background:#1e293b;border:1px solid #475569;color:#e2e8f0;margin:2px}
.task-type-label{display:inline-block;padding:0 6px;border-radius:4px;font-size:10px;background:#1e3a5f;color:#60a5fa;vertical-align:middle;margin-left:4px}
.task-progress-bar{height:6px;background:#1e293b;border-radius:4px;overflow:hidden;margin:6px 0}
.task-progress-fill{height:100%;border-radius:4px;transition:width 1s ease}
.task-status-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500}
.task-status-running{background:#0c1929;color:#38bdf8;border:1px solid #38bdf8}
.task-status-completed{background:#052e16;color:#22c55e;border:1px solid #22c55e}
.task-status-failed{background:#3b0a0a;color:#ef4444;border:1px solid #ef4444}
.task-status-stuck{background:#3b2200;color:#f59e0b;border:1px solid #f59e0b}
.task-status-pending{background:#1e293b;color:#94a3b8;border:1px solid #475569}
.task-status-cancelled{background:#1e293b;color:#64748b;border:1px solid #475569}
.task-card{border-left:3px solid #475569}
.task-card.running{border-left-color:#38bdf8}
.task-card.completed{border-left-color:#22c55e}
.task-card.failed{border-left-color:#ef4444}
.task-card.stuck{border-left-color:#f59e0b}
.task-card.pending{border-left-color:#64748b}
.task-group-title{font-size:13px;color:#94a3b8;margin:10px 0 6px;padding:4px 0;border-bottom:1px solid #1e293b}
</style>
</head>
<body>
<div class="header">
<h1>🔍 GA Monitor</h1>
<div>
  <button class="refresh-btn" onclick="toggleAutoRefresh()" id="autorefresh-btn">⏸ Pause</button>
  <span class="clock" id="clock"></span>
</div>
</div>

<div id="tasks-section"><h2>📊 Tasks 任务看板</h2><div id="tasks-loading">Loading...</div></div>
<div id="subagents-section"><h2>🤖 Active Subagents</h2><div id="subagents-loading">Loading...</div></div>
<div id="backup-section"><h2>💾 Docker Backup Status</h2><div id="backup-loading">Loading...</div></div>
<div id="handoff-section"><h2>📋 Active Handoffs</h2><div id="handoff-loading">Loading...</div></div>
<div id="plan-section"><h2>📝 Plan Progress</h2><div id="plan-loading">Loading...</div></div>

<script>
function updateClock(){document.getElementById('clock').textContent=new Date().toLocaleTimeString()}
updateClock();setInterval(updateClock,1000);

async function loadData(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    renderTasks(d.tasks);
    renderSubagents(d.subagents);
    renderBackups(d.backups);
    renderHandoffs(d.handoffs);
    renderPlan(d.plan);
  }catch(e){
    document.querySelectorAll('[id$=-loading]').forEach(el=>el.textContent='Error loading: '+e.message);
  }
}

function escapeHtml(s){if(!s)return '';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

function renderTasks(tasksData){
  const el=document.getElementById('tasks-loading');
  if(!tasksData||!tasksData.tasks||Object.keys(tasksData.tasks).length===0){
    el.innerHTML='<div class="card card-good"><span class="dot dot-gray"></span> No active tasks</div>';
    return;
  }
  const taskArr=Object.values(tasksData.tasks);
  const types=tasksData.types||{};
  const statusOrder=['running','completed','failed','stuck','pending','cancelled'];
  const statusIcons={'running':'🟢','completed':'✅','failed':'🔴','stuck':'🟡','pending':'⏳','cancelled':'🚫'};
  const statusLabels={'running':'Running','completed':'Completed','failed':'Failed','stuck':'Stuck','pending':'Pending','cancelled':'Cancelled'};
  // Group by status
  const groups={};
  taskArr.forEach(t=>{const s=t.status||'pending';if(!groups[s])groups[s]=[];groups[s].push(t)});
  // Sort each group: running by progress desc, others by last_update desc
  Object.keys(groups).forEach(s=>{
    groups[s].sort((a,b)=>{
      if(s==='running')return (b.progress_pct||0)-(a.progress_pct||0);
      return (b.last_update||'').localeCompare(a.last_update||'');
    });
  });
  let html='';
  // Type summary bar
  if(Object.keys(types).length>0){
    html+='<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;align-items:center">';
    html+='<span style="font-size:11px;color:#64748b;margin-right:4px">Types:</span>';
    Object.entries(types).forEach(([type,st])=>{
      html+=`<span class="task-type-badge">${escapeHtml(type)}: ${st.total||0} (🟢${st.running||0} ✅${st.completed||0} 🔴${st.failed||0})</span>`;
    });
    html+='</div>';
  }
  // Status groups in order: running → completed → failed → stuck → pending → cancelled
  statusOrder.forEach(status=>{
    const items=groups[status];
    if(!items||items.length===0)return;
    html+=`<div class="task-group-title">${statusIcons[status]||'❓'} ${statusLabels[status]||status} (${items.length})</div>`;
    html+='<div class="grid">';
    items.forEach(t=>{
      const pct=Math.min(100,Math.max(0,t.progress_pct||0));
      const pColor=status==='running'?'#38bdf8':status==='completed'?'#22c55e':status==='failed'?'#ef4444':status==='stuck'?'#f59e0b':'#64748b';
      html+=`<div class="card task-card ${status}">`;
      html+=`<div class="name">${escapeHtml(t.title||t.id)}`;
      if(t.type)html+=` <span class="task-type-label">${escapeHtml(t.type)}</span>`;
      html+=`</div>`;
      if(t.phase)html+=`<div class="meta">📌 ${escapeHtml(t.phase)}</div>`;
      if(t.host)html+=`<div class="meta">🖥 ${escapeHtml(t.host)}</div>`;
      // Progress bar
      html+=`<div class="task-progress-bar"><div class="task-progress-fill" style="width:${pct}%;background:${pColor}"></div></div>`;
      html+=`<div style="display:flex;justify-content:space-between;align-items:center;margin:2px 0">`;
      html+=`<span class="task-status-badge task-status-${status}">${statusIcons[status]||''} ${escapeHtml(statusLabels[status]||status)}</span>`;
      html+=`<span style="font-size:12px;color:#94a3b8;font-weight:500">${pct}%</span>`;
      html+=`</div>`;
      if(t.message)html+=`<div class="meta" style="color:#e2e8f0;font-size:12px">${escapeHtml(String(t.message).substring(0,120))}</div>`;
      if(t.last_update)html+=`<div class="meta">⏱ ${escapeHtml(t.last_update)}</div>`;
      if(t.handoff_id)html+=`<div class="meta">🔗 <code>${escapeHtml(t.handoff_id)}</code></div>`;
      html+=`</div>`;
    });
    html+='</div>';
  });
  // Last updated timestamp
  if(tasksData.last_updated){
    html+=`<div style="margin-top:6px;font-size:11px;color:#475569">Last updated: ${escapeHtml(tasksData.last_updated)}</div>`;
  }
  el.innerHTML=html;
}

function renderSubagents(agents){
  const el=document.getElementById('subagents-loading');
  if(!agents||agents.length===0){el.innerHTML='<div class="card card-good"><span class="dot dot-gray"></span> No active subagents</div>';return}
  let html='<table class="subagent-table"><tr><th>PID</th><th>Task</th><th>Runtime</th><th>CPU%</th><th>MEM%</th><th>Turn</th><th>Last Output</th><th>Log</th></tr>';
  agents.forEach(a=>{
    if(a.error) return;
    const cls=a.alive?'':'dimmed';
    const cpu=a.cpu||'-';
    const mem=a.mem||'-';
    const logId='log-'+a.pid+'-'+a.task.replace(/[^a-z0-9]/g,'');
    html+=`<tr class="${cls}">
      <td>${a.pid}</td>
      <td>${a.task}</td>
      <td>${a.runtime}</td>
      <td>${cpu}</td>
      <td>${mem}</td>
      <td>T${a.turn}</td>
      <td><pre class="out-preview">${(a.last_output||'-').substring(0,200)}</pre></td>
      <td><button class="log-btn" onclick="toggleLog('${logId}')">📄</button></td>
    </tr>
    <tr id="${logId}" style="display:none"><td colspan="8"><pre class="log-content">${(a.log_tail||'No log').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre></td></tr>`;
  });
  html+='</table>';
  el.innerHTML=html;
}

function renderBackups(bk){
  const el=document.getElementById('backup-loading');
  if(!bk){el.innerHTML='<div class="card">No backup data</div>';return}
  let html='<div class="host-grid">';
  const hosts=['amtaa','amtab','amtac','jpkaaa','jpkab','jpkac','jpkba','jpkbb','jpkbc','krkaa','krkab','krkac','krkad','krkca','krkcb','krrea','krreb'];
  hosts.forEach(h=>{
    const f=bk.files.find(x=>x.host===h);
    const done=f&&f.size!=='?';
    const sz=f?f.size:'-';
    const cls=done?'card-good':'card-warn';
    html+=`<div class="host-item ${cls}"><span class="dot ${done?'dot-green':'dot-yellow'}"></span>${h} <span style="color:#64748b;font-size:10px">${sz}</span></div>`;
  });
  html+=`</div><div style="margin-top:8px;font-size:12px;color:#64748b">Total: ${bk.total_size} | ${bk.files.length}/${hosts.length} files</div>`;
  el.innerHTML=html;
}

function renderHandoffs(hs){
  const el=document.getElementById('handoff-loading');
  if(!hs||hs.length===0){el.innerHTML='<div class="card"><span class="dot dot-gray"></span> No active handoffs</div>';return}
  let html='';
  hs.forEach(h=>{
    const cls=h.status==='active'?'card-warn':h.status==='in_progress'?'card-good':'card';
    html+=`<div class="card ${cls}" style="margin-bottom:6px"><div class="name">${h.session_topic||h.id}</div><div class="meta">${h.status} | ${h.created||''}</div></div>`;
  });
  el.innerHTML=html;
}

function renderPlan(p){
  const el=document.getElementById('plan-loading');
  if(!p){el.innerHTML='<div class="card">No plan data</div>';return}
  let html='';
  // Phase progress bars
  if(p.phases){
    Object.entries(p.phases).forEach(([name, ph])=>{
      if(ph.total===0) return;
      const pctDone = Math.round(ph.done/ph.total*100);
      const pctInProg = Math.round(ph.in_progress/ph.total*100);
      html+=`<div class="phase-row"><div class="phase-label">${name}: ${ph.done}/${ph.total}</div>
        <div class="phase-bar"><div class="phase-done" style="width:${pctDone}%"></div>
        <div class="phase-progress" style="width:${pctInProg}%"></div></div>
        <div class="phase-items">`+ph.items.map(i=>`<span class="phase-item">${i.replace(/</g,'&lt;')}</span>`).join(' ')+`</div></div>`;
    });
  }
  // Checklist items  
  p.items.forEach(item=>{
    const done=item.startsWith('[✓]')||item.startsWith('[x]');
    const cls=done?'card-good':'card-warn';
    html+=`<div class="card ${cls}" style="margin-bottom:4px;padding:4px 8px;font-size:12px"><span class="dot ${done?'dot-green':'dot-yellow'}"></span> ${item}</div>`;
  });
  el.innerHTML=html;
}

let autoRefresh=true;
function toggleAutoRefresh(){
  autoRefresh=!autoRefresh;
  document.getElementById('autorefresh-btn').textContent=autoRefresh?'⏸ Pause':'▶ Resume';
}
function toggleLog(id){
  const el=document.getElementById(id);
  if(el) el.style.display=el.style.display==='none'?'table-row':'none';
}
loadData();
setInterval(()=>{if(autoRefresh) loadData()},15000);
</script>
<div class="footer">GA Monitor — refreshes every 15s</div>
</body>
</html>"""

class GAHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(self._get_status()).encode('utf-8'))
        elif path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(PAGE.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 Not Found')
    
    def _get_status(self):
        return {
            'tasks': self._get_tasks(),
            'subagents': self._get_subagents(),
            'backups': self._get_backups(),
            'handoffs': self._get_handoffs(),
            'plan': self._get_plan(),
        }
    
    @cached(ttl=CACHE_TTL)
    def _get_subagents(self):
        """Find active agentmain.py processes — single ps call"""
        agents = []
        try:
            # Single ps call: pid,etime,cpu,mem,cmd
            result = subprocess.run(
                ['ps', '-eo', 'pid,etime,%cpu,%mem,cmd'],
                capture_output=True, text=True, timeout=10
            )
            header_skipped = False
            for line in result.stdout.splitlines():
                if not header_skipped:
                    header_skipped = True
                    continue
                if 'agentmain.py' not in line:
                    continue
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                pid, runtime, cpu, mem, cmd = parts
                # Read subagent output
                task_dirs = glob.glob(os.path.join(TEMP_DIR, '*'))
                task_name = ''
                last_output = ''
                log_tail = ''
                stderr_tail = ''
                turn = 0
                for td in task_dirs:
                    tn = os.path.basename(td)
                    if tn not in cmd:
                        continue
                    task_name = tn
                    outfile = os.path.join(td, 'output.txt')
                    if not os.path.exists(outfile):
                        break
                    try:
                        with open(outfile, 'r', errors='replace') as f:
                            content = f.read()
                        turn = content.count('Turn ')
                        lines = content.strip().splitlines()
                        last_output = '\n'.join(lines[-3:]) if lines else ''
                        log_tail = '\n'.join(lines[-10:]) if lines else ''
                        stderrfile = os.path.join(td, 'stderr.log')
                        if os.path.exists(stderrfile):
                            with open(stderrfile, 'r', errors='replace') as f:
                                stderr_lines = f.read().strip().splitlines()
                            stderr_tail = '\n'.join(stderr_lines[-5:]) if stderr_lines else ''
                    except:
                        pass
                    break  # matched, stop scanning
                
                agents.append({
                    'pid': pid,
                    'task': task_name,
                    'runtime': runtime,
                    'turn': turn,
                    'cpu': cpu,
                    'mem': mem,
                    'last_output': last_output,
                    'log_tail': log_tail,
                    'stderr_tail': stderr_tail,
                    'alive': True,
                })
        except Exception as e:
            agents.append({'error': str(e)})
        
        if not agents:
            # Orphan task dirs (exited processes)
            for d in sorted(os.listdir(TEMP_DIR)):
                task_dir = os.path.join(TEMP_DIR, d)
                outfile = os.path.join(task_dir, 'output.txt')
                if os.path.isdir(task_dir) and os.path.exists(outfile):
                    try:
                        with open(outfile, 'r', errors='replace') as f:
                            content = f.read()
                        turn = content.count('Turn ')
                        agents.append({
                            'pid': '-',
                            'task': d,
                            'runtime': 'exited',
                            'turn': turn,
                            'last_output': '(process ended)',
                            'alive': False,
                        })
                    except:
                        pass
        return agents
    
    def _get_backups(self):
        """List backup files"""
        files = []
        total_bytes = 0
        try:
            if os.path.exists(BACKUP_DIR):
                for f in sorted(glob.glob(os.path.join(BACKUP_DIR, 'docker_*.tar.gz'))):
                    basename = os.path.basename(f)
                    size = os.path.getsize(f)
                    total_bytes += size
                    mtime = time.strftime('%H:%M:%S', time.localtime(os.path.getmtime(f)))
                    # Extract hostname from filename
                    host = basename.replace('docker_', '').replace('_backup_', '_').split('_')[0]
                    files.append({
                        'host': host,
                        'filename': basename,
                        'size_bytes': size,
                        'size': self._fmt_size(size),
                        'mtime': mtime,
                    })
        except Exception as e:
            return {'error': str(e), 'files': files}
        
        def _sort_key(f):
            try: return HOSTS.index(f['host'])
            except ValueError: return 999
        files.sort(key=_sort_key)
        
        return {
            'files': files,
            'total_size': self._fmt_size(total_bytes),
        }
    
    def _get_handoffs(self):
        """Read active/in_progress handoffs"""
        handoffs = []
        try:
            if os.path.exists(HANDOFFS_FILE):
                with open(HANDOFFS_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                h = json.loads(line)
                                if h.get('status') in ('active', 'in_progress'):
                                    handoffs.append({
                                        'id': h.get('id', '?'),
                                        'session_topic': h.get('session_topic', ''),
                                        'status': h.get('status', ''),
                                        'created': h.get('created', ''),
                                    })
                            except:
                                pass
        except:
            pass
        return handoffs
    
    def _get_plan(self):
        """Parse plan.md checkboxes and phase progress"""
        items = []
        phases = {}  # phase_name -> {total, done, in_progress, items}
        current_phase = 'Other'
        try:
            if os.path.exists(PLAN_FILE):
                with open(PLAN_FILE, 'r', errors='replace') as f:
                    for line in f:
                        line = line.rstrip()
                        # Detect phase headers: ## Phase X
                        m = re.match(r'##\s*(Phase\s+\S+)', line)
                        if m:
                            current_phase = m.group(1)
                            if current_phase not in phases:
                                phases[current_phase] = {'total': 0, 'done': 0, 'in_progress': 0, 'todo': 0, 'items': []}
                        # Detect numbered checklist items: N. [MARKER]
                        m = re.match(r'\s*\d+\.\s*\[([\s✓→])\]\s*\*\*(P\d[^:]+):', line)
                        if m:
                            marker = m.group(1)
                            title = m.group(2).strip()
                            status = 'done' if marker == '✓' else ('in_progress' if marker == '→' else 'todo')
                            items.append(line.strip())
                            if current_phase not in phases:
                                phases[current_phase] = {'total': 0, 'done': 0, 'in_progress': 0, 'todo': 0, 'items': []}
                            phases[current_phase]['total'] += 1
                            phases[current_phase][status] += 1
                            phases[current_phase]['items'].append(f"[{marker}] {title}")
        except Exception as e:
            phases['Error'] = {'total': 0, 'done': 0, 'in_progress': 0, 'todo': 0, 'items': [str(e)]}
        return {'items': items, 'total': len(items), 'phases': phases}
    
    def _get_tasks(self):
        """Read task_status.json"""
        try:
            if os.path.exists(TASKS_FILE):
                with open(TASKS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            return {'error': str(e), 'tasks': {}, 'types': {}}
        return {'tasks': {}, 'types': {}}
    
    def _fmt_size(self, bytes_val):
        for unit in ['B','K','M','G','T']:
            if bytes_val < 1024:
                return f"{bytes_val:.0f}{unit}" if unit=='B' else f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f}T"
    
    def log_message(self, fmt, *args):
        pass  # suppress logs

def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    server = HTTPServer(('0.0.0.0', port), GAHandler)
    print(f"GA Monitor running at http://localhost:{port}")
    print(f"  Subagents: {TEMP_DIR}/*/output.txt")
    print(f"  Backups:   {BACKUP_DIR}")
    print(f"  Handoffs:  {HANDOFFS_FILE}")
    print(f"  Plan:      {PLAN_FILE}")
    print(f"  Tasks:     {TASKS_FILE}")
    server.serve_forever()

if __name__ == '__main__':
    main()
