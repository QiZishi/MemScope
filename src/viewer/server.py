"""
MemOS Local Viewer - Web UI for memory management.

Built-in HTTP server serving a single-page dashboard with 7 views:
1. Dashboard - stats overview
2. Memories - list/search all chunks
3. Tasks - task management
4. Skills - skill library
5. Timeline - chronological view
6. Tool Logs - tool call history
7. Shared - shared memories
"""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MemOS Local Viewer</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.header{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:20px;font-weight:600;color:#58a6ff}
.nav{display:flex;gap:8px;flex-wrap:wrap}
.nav button{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;transition:all .2s}
.nav button:hover{background:#30363d}
.nav button.active{background:#1f6feb;border-color:#1f6feb;color:#fff}
.container{max-width:1400px;margin:0 auto;padding:24px}
.page{display:none}.page.active{display:block}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px}
.stat-card h3{font-size:13px;color:#8b949e;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}
.stat-card .value{font-size:32px;font-weight:600;color:#58a6ff}
.search-bar{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;gap:12px}
.search-bar input{flex:1;background:transparent;border:none;color:#c9d1d9;font-size:14px;outline:none}
.search-bar button{background:#238636;border:none;color:#fff;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px}
.item-list{display:flex;flex-direction:column;gap:8px}
.item-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;cursor:pointer;transition:border-color .2s}
.item-card:hover{border-color:#58a6ff}
.item-card .meta{display:flex;gap:8px;margin-bottom:8px;font-size:12px;color:#8b949e;flex-wrap:wrap}
.item-card .meta span{background:#21262d;padding:2px 8px;border-radius:4px}
.item-card .content{font-size:14px;line-height:1.5;word-break:break-word;white-space:pre-wrap}
.item-card .content.trunc{max-height:80px;overflow:hidden;position:relative}
.item-card .content.trunc::after{content:'';position:absolute;bottom:0;left:0;right:0;height:30px;background:linear-gradient(transparent,#161b22)}
.timeline{position:relative;padding-left:24px}
.timeline::before{content:'';position:absolute;left:8px;top:0;bottom:0;width:2px;background:#30363d}
.timeline-item{position:relative;margin-bottom:16px}
.timeline-item::before{content:'';position:absolute;left:-20px;top:4px;width:8px;height:8px;background:#58a6ff;border-radius:50%}
.timeline-item .time{font-size:12px;color:#8b949e;margin-bottom:4px}
.loading{text-align:center;padding:48px;color:#8b949e}
.status-active{color:#3fb950}.status-done{color:#58a6ff}.status-failed{color:#f85149}
.btn-sm{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px}
.btn-sm:hover{background:#30363d}
.pagination{display:flex;gap:8px;justify-content:center;margin-top:16px}
</style>
</head>
<body>
<div class="header">
  <h1>MemOS Local Viewer</h1>
  <nav class="nav" id="nav"></nav>
</div>
<div class="container" id="content"></div>
<script>
const API = '';
const pages = [
  {id:'dashboard',label:'Dashboard'},
  {id:'memories',label:'Memories'},
  {id:'tasks',label:'Tasks'},
  {id:'skills',label:'Skills'},
  {id:'timeline',label:'Timeline'},
  {id:'logs',label:'Tool Logs'},
  {id:'shared',label:'Shared'}
];

let currentPage = 'dashboard';
let memoryOffset = 0;

// Build nav
const nav = document.getElementById('nav');
pages.forEach(p => {
  const btn = document.createElement('button');
  btn.textContent = p.label;
  btn.dataset.page = p.id;
  btn.onclick = () => showPage(p.id);
  nav.appendChild(btn);
});

function showPage(id) {
  currentPage = id;
  nav.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.page === id));
  const c = document.getElementById('content');
  switch(id) {
    case 'dashboard': loadDashboard(c); break;
    case 'memories': loadMemories(c); break;
    case 'tasks': loadTasks(c); break;
    case 'skills': loadSkills(c); break;
    case 'timeline': loadTimeline(c); break;
    case 'logs': loadLogs(c); break;
    case 'shared': loadShared(c); break;
  }
}

async function fetchJSON(path) {
  const r = await fetch(API + path);
  return r.json();
}

function esc(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtTime(ts) {
  if (!ts) return '-';
  const d = new Date(ts < 1e12 ? ts * 1000 : ts);
  return d.toLocaleString();
}

function truncate(s, len) {
  if (!s) return '';
  if (s.length <= len) return esc(s);
  return esc(s.substring(0, len)) + '...';
}

async function loadDashboard(el) {
  el.innerHTML = '<div class="loading">Loading stats...</div>';
  try {
    const d = await fetchJSON('/api/stats');
    el.innerHTML = `
      <div class="stats-grid">
        <div class="stat-card"><h3>Total Memories</h3><div class="value">${d.total_chunks||0}</div></div>
        <div class="stat-card"><h3>Total Tasks</h3><div class="value">${d.total_tasks||0}</div></div>
        <div class="stat-card"><h3>Total Skills</h3><div class="value">${d.total_skills||0}</div></div>
        <div class="stat-card"><h3>Shared Memories</h3><div class="value">${d.shared_chunks||0}</div></div>
        <div class="stat-card"><h3>Sessions</h3><div class="value">${d.total_sessions||0}</div></div>
        <div class="stat-card"><h3>Tool Calls</h3><div class="value">${d.total_tool_logs||0}</div></div>
      </div>
      <h2 style="margin-bottom:16px;color:#58a6ff">Recent Activity</h2>
      <div class="timeline" id="dash-timeline"><div class="loading">Loading...</div></div>`;
    const items = await fetchJSON('/api/timeline?limit=10');
    const tl = document.getElementById('dash-timeline');
    if (!items.length) { tl.innerHTML = '<p style="color:#8b949e">No recent activity</p>'; return; }
    tl.innerHTML = items.map(i => `
      <div class="timeline-item">
        <div class="time">${fmtTime(i.createdAt)}</div>
        <div class="item-card">
          <div class="meta"><span>${esc(i.role)}</span><span>${esc(i.sessionKey||'')}</span></div>
          <div class="content">${truncate(i.content, 200)}</div>
        </div>
      </div>`).join('');
  } catch(e) { el.innerHTML = '<div class="error">Failed to load: '+esc(e.message)+'</div>'; }
}

async function loadMemories(el, offset=0, query='') {
  memoryOffset = offset;
  el.innerHTML = `<div class="search-bar">
    <input type="text" id="mem-search" placeholder="Search memories..." value="${esc(query)}"
      onkeypress="if(event.key==='Enter')loadMemories(document.getElementById('content'),0,document.getElementById('mem-search').value)">
    <button onclick="loadMemories(document.getElementById('content'),0,document.getElementById('mem-search').value)">Search</button>
  </div><div class="item-list" id="mem-list"><div class="loading">Loading...</div></div>`;
  const listEl = document.getElementById('mem-list');
  try {
    const items = await fetchJSON(`/api/memories?limit=50&offset=${offset}` + (query ? `&q=${encodeURIComponent(query)}` : ''));
    if (!items.length) { listEl.innerHTML = '<p style="color:#8b949e;padding:16px">No memories found</p>'; return; }
    listEl.innerHTML = items.map(i => `
      <div class="item-card" onclick="this.classList.toggle('expanded')">
        <div class="meta">
          <span>${esc(i.role)}</span>
          <span>${fmtTime(i.createdAt)}</span>
          <span>${esc(i.visibility||'private')}</span>
          ${i.sessionKey ? '<span>'+esc(i.sessionKey)+'</span>' : ''}
        </div>
        <div class="content trunc">${esc(i.content||'')}</div>
      </div>`).join('');
    listEl.innerHTML += `<div class="pagination">
      ${offset>0?'<button class="btn-sm" onclick="loadMemories(document.getElementById(\'content\'),'+(offset-50)+',\''+esc(query.replace(/'/g,"\\\\'"))+'\')">Prev</button>':''}
      ${items.length===50?'<button class="btn-sm" onclick="loadMemories(document.getElementById(\'content\'),'+(offset+50)+',\''+esc(query.replace(/'/g,"\\\\'"))+'\')">Next</button>':''}
    </div>`;
  } catch(e) { listEl.innerHTML = '<div class="error">Failed: '+esc(e.message)+'</div>'; }
}

async function loadTasks(el) {
  el.innerHTML = '<div class="loading">Loading tasks...</div>';
  try {
    const items = await fetchJSON('/api/tasks?limit=100');
    if (!items.length) { el.innerHTML = '<p style="color:#8b949e;padding:16px">No tasks found</p>'; return; }
    el.innerHTML = '<div class="item-list">' + items.map(i => `
      <div class="item-card" onclick="this.classList.toggle('expanded')">
        <div class="meta">
          <span class="status-${i.status}">${esc(i.status)}</span>
          <span>${fmtTime(i.startedAt)}</span>
          <span>${esc(i.id)}</span>
        </div>
        <div class="content">${esc(i.title||'Untitled')}${i.summary ? '\n\n'+i.summary : ''}</div>
      </div>`).join('') + '</div>';
  } catch(e) { el.innerHTML = '<div class="error">Failed: '+esc(e.message)+'</div>'; }
}

async function loadSkills(el) {
  el.innerHTML = '<div class="loading">Loading skills...</div>';
  try {
    const items = await fetchJSON('/api/skills?limit=100');
    if (!items.length) { el.innerHTML = '<p style="color:#8b949e;padding:16px">No skills found</p>'; return; }
    el.innerHTML = '<div class="item-list">' + items.map(i => `
      <div class="item-card" onclick="this.classList.toggle('expanded')">
        <div class="meta">
          <span class="status-${i.status}">${esc(i.status)}</span>
          <span>v${esc(i.version||'1')}</span>
          <span>${esc(i.owner||'local')}</span>
          <span>${fmtTime(i.updatedAt)}</span>
        </div>
        <div class="content">${esc(i.name||'Unnamed')}${i.content ? '\n\n'+i.content : ''}</div>
      </div>`).join('') + '</div>';
  } catch(e) { el.innerHTML = '<div class="error">Failed: '+esc(e.message)+'</div>'; }
}

async function loadTimeline(el) {
  el.innerHTML = '<div class="loading">Loading timeline...</div>';
  try {
    const items = await fetchJSON('/api/timeline?limit=50');
    if (!items.length) { el.innerHTML = '<p style="color:#8b949e;padding:16px">No timeline data</p>'; return; }
    el.innerHTML = '<div class="timeline">' + items.map(i => `
      <div class="timeline-item">
        <div class="time">${fmtTime(i.createdAt)} &middot; ${esc(i.role)}</div>
        <div class="item-card" onclick="this.classList.toggle('expanded')">
          <div class="meta">
            <span>${esc(i.sessionKey||'-')}</span>
            <span>${esc(i.visibility||'private')}</span>
          </div>
          <div class="content">${esc(i.content||'')}</div>
        </div>
      </div>`).join('') + '</div>';
  } catch(e) { el.innerHTML = '<div class="error">Failed: '+esc(e.message)+'</div>'; }
}

async function loadLogs(el) {
  el.innerHTML = '<div class="loading">Loading tool logs...</div>';
  try {
    const items = await fetchJSON('/api/logs?limit=100');
    if (!items.length) { el.innerHTML = '<p style="color:#8b949e;padding:16px">No tool logs</p>'; return; }
    el.innerHTML = '<div class="item-list">' + items.map(i => `
      <div class="item-card" onclick="this.classList.toggle('expanded')">
        <div class="meta">
          <span>${esc(i.tool)}</span>
          <span>${fmtTime(i.ts)}</span>
          <span>${esc(i.owner||'local')}</span>
        </div>
        <div class="content">Args: ${esc(i.args||'-')}\nResult: ${esc(i.result||'-')}</div>
      </div>`).join('') + '</div>';
  } catch(e) { el.innerHTML = '<div class="error">Failed: '+esc(e.message)+'</div>'; }
}

async function loadShared(el) {
  el.innerHTML = '<div class="loading">Loading shared memories...</div>';
  try {
    const items = await fetchJSON('/api/shared?limit=50');
    if (!items.length) { el.innerHTML = '<p style="color:#8b949e;padding:16px">No shared memories</p>'; return; }
    el.innerHTML = '<div class="item-list">' + items.map(i => `
      <div class="item-card" onclick="this.classList.toggle('expanded')">
        <div class="meta">
          <span>Owner: ${esc(i.owner||'-')}</span>
          <span>${fmtTime(i.createdAt)}</span>
          ${i.sharedWith ? '<span>To: '+esc(i.sharedWith)+'</span>' : '<span>To: all</span>'}
        </div>
        <div class="content">${esc(i.content||'')}</div>
      </div>`).join('') + '</div>';
  } catch(e) { el.innerHTML = '<div class="error">Failed: '+esc(e.message)+'</div>'; }
}

// Init
showPage('dashboard');
</script>
</body>
</html>"""


class ViewerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the viewer."""

    def __init__(self, store: Any, *args, **kwargs):
        self._store = store
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_html(INDEX_HTML)
        elif path == "/api/stats":
            self._json_response(self._store.get_stats())
        elif path == "/api/memories":
            limit = int(params.get("limit", [50])[0])
            offset = int(params.get("offset", [0])[0])
            query = params.get("q", [None])[0]
            if query:
                results = self._store.search_chunks(query, max_results=limit)
            else:
                results = self._store.get_all_chunks(limit=limit, offset=offset)
            self._json_response(results)
        elif path == "/api/tasks":
            limit = int(params.get("limit", [100])[0])
            offset = int(params.get("offset", [0])[0])
            self._json_response(self._store.get_all_tasks(limit=limit, offset=offset))
        elif path == "/api/skills":
            limit = int(params.get("limit", [100])[0])
            offset = int(params.get("offset", [0])[0])
            self._json_response(self._store.get_all_skills(limit=limit, offset=offset))
        elif path == "/api/timeline":
            limit = int(params.get("limit", [50])[0])
            self._json_response(self._store.get_recent_chunks(limit=limit))
        elif path == "/api/logs":
            limit = int(params.get("limit", [100])[0])
            self._json_response(self._store.get_tool_logs_all(limit=limit))
        elif path == "/api/shared":
            limit = int(params.get("limit", [50])[0])
            self._json_response(self._store.get_all_shared_chunks(limit=limit))
        else:
            self.send_error(404, "Not Found")

    def _serve_html(self, html: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _json_response(self, data: Any):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))


class ViewerServer:
    """Built-in web server for the MemOS Local viewer dashboard."""

    def __init__(self, store: Any, host: str = "127.0.0.1", port: int = 18799):
        self._store = store
        self._host = host
        self._port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _make_handler(self, store: Any):
        """Create a handler class bound to the store."""
        class BoundHandler(ViewerHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(store, *args, **kwargs)
        return BoundHandler

    def start(self) -> str:
        """Start the viewer server in a background thread. Returns the URL."""
        if self._server is not None:
            return f"http://{self._host}:{self._port}"

        handler_cls = self._make_handler(self._store)
        self._server = HTTPServer((self._host, self._port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        url = f"http://{self._host}:{self._port}"
        logger.info(f"memos-local: viewer started at {url}")
        return url

    def stop(self):
        """Stop the viewer server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("memos-local: viewer stopped")

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"
