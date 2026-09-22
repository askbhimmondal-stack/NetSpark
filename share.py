#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Share - Zero Install File & Text Sharing
AnyDesk-style Clean UI
Designed by Bhim Mondal
"""

import http.server
import socketserver
import socket
import os
import re
import json
import html
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

PORT = 8000
UPLOAD_DIR = Path("shared_files")
NOTEPAD_FILE = Path("shared_notepad.txt")
MAX_FILE_SIZE = 300 * 1024 * 1024

UPLOAD_DIR.mkdir(exist_ok=True)
if not NOTEPAD_FILE.exists():
    NOTEPAD_FILE.write_text("", encoding="utf-8")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_files():
    files = []
    try:
        for f in UPLOAD_DIR.iterdir():
            if f.is_file() and not f.name.startswith("."):
                st = f.stat()
                files.append({
                    "name": f.name,
                    "size": format_size(st.st_size),
                    "time": datetime.fromtimestamp(st.st_mtime).strftime("%d %b, %I:%M %p"),
                    "mtime": st.st_mtime
                })
        files.sort(key=lambda x: x["mtime"], reverse=True)
    except Exception:
        pass
    return files


def safe_filename(name):
    name = os.path.basename(name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(". ")
    if not name:
        name = "file_" + str(uuid.uuid4())[:8]
    return name[:180]


def parse_multipart(data: bytes, content_type: str):
    files = []
    if "boundary=" not in content_type:
        return files
    boundary = content_type.split("boundary=")[-1].strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    boundary = boundary.encode("utf-8")
    delimiter = b"--" + boundary
    parts = data.split(delimiter)
    for part in parts:
        if not part or part in (b"--", b"--\r\n", b"\r\n"):
            continue
        if part.startswith(b"--"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if b"\r\n\r\n" not in part:
            continue
        header_bytes, body = part.split(b"\r\n\r\n", 1)
        if body.endswith(b"\r\n"):
            body = body[:-2]
        headers = header_bytes.decode("utf-8", errors="ignore")
        filename_match = re.search(r'filename="([^"]*)"', headers, re.IGNORECASE)
        if not filename_match:
            filename_match = re.search(r"filename=([^;\r\n]+)", headers, re.IGNORECASE)
        if not filename_match:
            continue
        filename = filename_match.group(1).strip()
        if not filename:
            continue
        files.append((filename, body))
    return files


HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Local Share</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;500;600;700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    background: #f5f5f7;
    color: #1a1a1a;
    min-height: 100vh;
  }

  /* Top bar */
  .topbar {
    background: #fff;
    border-bottom: 1px solid #e5e5e5;
    padding: 0 28px;
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .topbar-left {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 600;
    font-size: 1.05rem;
  }
  .topbar-left span { color: #ef4444; }
  .topbar-right {
    font-size: 0.82rem;
    color: #888;
  }

  .app {
    max-width: 960px;
    margin: 0 auto;
    padding: 36px 24px 50px;
  }

  /* Hero Address */
  .hero {
    text-align: center;
    margin-bottom: 36px;
  }
  .hero-label {
    font-size: 0.95rem;
    color: #666;
    margin-bottom: 10px;
  }
  .hero-address {
    font-size: 2.4rem;
    font-weight: 700;
    color: #ef4444;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .hero-sub {
    font-size: 0.88rem;
    color: #999;
  }

  /* Feature cards row */
  .cards-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 32px;
  }
  .info-card {
    border-radius: 10px;
    padding: 18px 16px;
    color: #fff;
    min-height: 110px;
  }
  .info-card h3 {
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .info-card p {
    font-size: 0.8rem;
    opacity: 0.9;
    line-height: 1.4;
  }
  .c-pink { background: #e879a0; }
  .c-blue { background: #4a7fb5; }
  .c-orange { background: #e8a838; }
  .c-purple { background: #9b7bb8; }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 0;
    border-bottom: 2px solid #e5e5e5;
    margin-bottom: 24px;
  }
  .tab {
    padding: 12px 22px;
    border: none;
    background: transparent;
    font-size: 0.95rem;
    font-weight: 500;
    color: #888;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: color 0.15s;
  }
  .tab.active {
    color: #ef4444;
    border-bottom-color: #ef4444;
  }

  .section { display: none; }
  .section.active { display: block; }

  /* Upload area */
  .upload-box {
    background: #fff;
    border: 2px dashed #d0d0d0;
    border-radius: 12px;
    padding: 42px 20px;
    text-align: center;
    cursor: pointer;
    margin-bottom: 24px;
    transition: border-color 0.2s, background 0.2s;
  }
  .upload-box:hover, .upload-box.dragover {
    border-color: #ef4444;
    background: #fff5f5;
  }
  .upload-box .icon {
    font-size: 2.2rem;
    margin-bottom: 10px;
  }
  .upload-box p {
    font-size: 1rem;
    font-weight: 500;
    color: #333;
  }
  .upload-box .hint {
    font-size: 0.82rem;
    color: #999;
    margin-top: 4px;
  }
  #fileInput { display: none; }

  .progress {
    display: none;
    height: 4px;
    background: #eee;
    border-radius: 4px;
    margin-top: 16px;
    overflow: hidden;
  }
  .progress .fill {
    height: 100%;
    background: #ef4444;
    width: 0%;
    transition: width 0.3s;
  }

  /* File list */
  .file-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .file-item {
    background: #fff;
    border-radius: 10px;
    padding: 14px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.15s;
  }
  .file-item:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }
  .file-icon {
    width: 44px;
    height: 44px;
    background: #f0f0f0;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  .file-info { flex: 1; min-width: 0; }
  .file-name {
    font-weight: 600;
    font-size: 0.95rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .file-meta {
    font-size: 0.8rem;
    color: #999;
    margin-top: 2px;
  }
  .file-actions {
    display: flex;
    gap: 8px;
  }
  .btn {
    padding: 8px 14px;
    border-radius: 8px;
    border: none;
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .btn-dl {
    background: #e8f5e9;
    color: #2e7d32;
  }
  .btn-del {
    background: #fce4ec;
    color: #c62828;
  }
  .btn-clear {
    background: #fce4ec;
    color: #c62828;
    padding: 10px 20px;
    margin-top: 16px;
  }

  .empty {
    text-align: center;
    padding: 50px 20px;
    color: #999;
    background: #fff;
    border-radius: 12px;
  }
  .empty .icon { font-size: 2.5rem; margin-bottom: 10px; opacity: 0.5; }

  /* Notepad */
  .notepad-box {
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .notepad-box textarea {
    width: 100%;
    height: 340px;
    border: none;
    padding: 20px;
    font-size: 0.95rem;
    font-family: inherit;
    resize: vertical;
    outline: none;
    line-height: 1.6;
    color: #1a1a1a;
  }
  .notepad-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 18px;
    border-top: 1px solid #eee;
    background: #fafafa;
  }
  .save-status { font-size: 0.85rem; color: #2e7d32; }
  .save-btn {
    background: #ef4444;
    color: #fff;
    border: none;
    padding: 10px 24px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.9rem;
    cursor: pointer;
  }
  .note-hint {
    text-align: center;
    font-size: 0.82rem;
    color: #999;
    margin-top: 12px;
  }

  footer {
    text-align: center;
    margin-top: 48px;
    font-size: 0.8rem;
    color: #aaa;
    line-height: 1.7;
  }

  @media (max-width: 700px) {
    .cards-row { grid-template-columns: 1fr 1fr; }
    .hero-address { font-size: 1.8rem; }
    .app { padding: 24px 16px 40px; }
  }
  @media (max-width: 480px) {
    .cards-row { grid-template-columns: 1fr; }
    .file-item { flex-wrap: wrap; }
    .file-actions { width: 100%; margin-top: 8px; }
  }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <span>●</span> Local Share
  </div>
  <div class="topbar-right">Designed by Bhim Mondal</div>
</div>

<div class="app">

  <div class="hero">
    <div class="hero-label">Your Local Address</div>
    <div class="hero-address">__IP__</div>
    <div class="hero-sub">Port __PORT__ &nbsp;•&nbsp; Same WiFi pe devices se open karo</div>
  </div>

  <div class="cards-row">
    <div class="info-card c-pink">
      <h3>Files</h3>
      <p id="fileCountText">0 files shared</p>
    </div>
    <div class="info-card c-blue">
      <h3>Status</h3>
      <p>Server is online and ready</p>
    </div>
    <div class="info-card c-orange">
      <h3>Network</h3>
      <p>Local WiFi only • No internet needed</p>
    </div>
    <div class="info-card c-purple">
      <h3>Privacy</h3>
      <p>All data stays on your PC</p>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('files')">Files</button>
    <button class="tab" onclick="switchTab('notepad')">Shared Text</button>
  </div>

  <div id="filesSection" class="section active">
    <div class="upload-box" id="uploadZone">
      <div class="icon">📤</div>
      <p>Click or drop files here</p>
      <p class="hint">Any file type • Max 300 MB</p>
      <div class="progress" id="progress"><div class="fill" id="progressFill"></div></div>
    </div>
    <input type="file" id="fileInput" multiple>

    <div class="file-list" id="fileList">
      __FILES__
    </div>

    <div style="text-align:center;__CLEAR_STYLE__">
      <form method="POST" action="/clear" onsubmit="return confirm('Delete all files?')">
        <button type="submit" class="btn btn-clear">Clear All Files</button>
      </form>
    </div>
  </div>

  <div id="notepadSection" class="section">
    <div class="notepad-box">
      <textarea id="notepad" placeholder="Type something here... everyone on the network can see it">__NOTEPAD__</textarea>
      <div class="notepad-footer">
        <span class="save-status" id="saveStatus"></span>
        <button class="save-btn" onclick="saveNotepad()">Save</button>
      </div>
    </div>
    <p class="note-hint">After saving, other devices should refresh the page</p>
  </div>

  <footer>
    Local Share • Data stays on your PC<br>
    Designed by Bhim Mondal
  </footer>
</div>

<script>
const IP = "__IP__";
const PORT = "__PORT__";
const FILE_COUNT = __FILE_COUNT__;

document.getElementById('fileCountText').textContent = FILE_COUNT + ' file' + (FILE_COUNT !== 1 ? 's' : '') + ' shared';

function switchTab(t) {
  document.querySelectorAll('.tab').forEach(e => e.classList.remove('active'));
  document.querySelectorAll('.section').forEach(e => e.classList.remove('active'));
  if (t === 'files') {
    document.querySelectorAll('.tab')[0].classList.add('active');
    document.getElementById('filesSection').classList.add('active');
  } else {
    document.querySelectorAll('.tab')[1].classList.add('active');
    document.getElementById('notepadSection').classList.add('active');
  }
}

const zone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
zone.addEventListener('click', () => fileInput.click());

['dragenter','dragover','dragleave','drop'].forEach(ev => {
  zone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); });
});
['dragenter','dragover'].forEach(ev => zone.addEventListener(ev, () => zone.classList.add('dragover')));
['dragleave','drop'].forEach(ev => zone.addEventListener(ev, () => zone.classList.remove('dragover')));
zone.addEventListener('drop', e => {
  if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', function() {
  if (this.files.length) uploadFiles(this.files);
});

function uploadFiles(files) {
  const fd = new FormData();
  for (let i = 0; i < files.length; i++) fd.append('file', files[i]);
  const prog = document.getElementById('progress');
  const fill = document.getElementById('progressFill');
  prog.style.display = 'block';
  fill.style.width = '0%';
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload');
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) fill.style.width = Math.round(e.loaded / e.total * 100) + '%';
  };
  xhr.onload = () => {
    fill.style.width = '100%';
    setTimeout(() => { prog.style.display = 'none'; fill.style.width = '0%'; }, 500);
    try {
      const res = JSON.parse(xhr.responseText);
      if (res.ok) location.reload();
      else alert(res.error || 'Upload failed');
    } catch(e) { location.reload(); }
  };
  xhr.onerror = () => alert('Upload failed');
  xhr.send(fd);
  fileInput.value = '';
}

function deleteFile(name) {
  if (!confirm('Delete this file?')) return;
  fetch('/delete?name=' + encodeURIComponent(name), { method: 'POST' })
    .then(() => location.reload())
    .catch(() => location.reload());
}

function saveNotepad() {
  const text = document.getElementById('notepad').value;
  fetch('/notepad', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      const s = document.getElementById('saveStatus');
      s.textContent = 'Saved ✓';
      setTimeout(() => s.textContent = '', 2000);
    }
  });
}
</script>
</body>
</html>
'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                self.serve_page()
            elif path.startswith("/download/"):
                name = urllib.parse.unquote(path[len("/download/"):])
                name = os.path.basename(name)
                fp = UPLOAD_DIR / name
                if fp.is_file():
                    self.serve_download(fp)
                else:
                    self.send_error(404, "File not found")
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[ERROR] GET: {e}")
            self.send_error(500)

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/upload":
                self.handle_upload()
            elif path == "/delete":
                self.handle_delete(parsed)
            elif path == "/clear":
                self.handle_clear()
            elif path == "/notepad":
                self.handle_notepad()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[ERROR] POST: {e}")
            try:
                self.send_json({"ok": False, "error": str(e)}, 500)
            except Exception:
                pass

    def serve_page(self):
        files = get_files()
        files_html = ""
        if files:
            for f in files:
                safe_name = html.escape(f["name"])
                quoted = urllib.parse.quote(f["name"])
                files_html += f'''
        <div class="file-item">
          <div class="file-icon">📄</div>
          <div class="file-info">
            <div class="file-name">{safe_name}</div>
            <div class="file-meta">{f["size"]} • {f["time"]}</div>
          </div>
          <div class="file-actions">
            <a class="btn btn-dl" href="/download/{quoted}">Download</a>
            <button class="btn btn-del" onclick="deleteFile('{safe_name}')">Delete</button>
          </div>
        </div>'''
        else:
            files_html = '''
        <div class="empty">
          <div class="icon">📂</div>
          <div>No files yet. Upload something!</div>
        </div>'''

        notepad = ""
        try:
            notepad = NOTEPAD_FILE.read_text(encoding="utf-8")
        except Exception:
            pass

        clear_style = "display:none;" if not files else ""

        page = (HTML
                .replace("__IP__", get_local_ip())
                .replace("__PORT__", str(PORT))
                .replace("__FILES__", files_html)
                .replace("__NOTEPAD__", html.escape(notepad))
                .replace("__CLEAR_STYLE__", clear_style)
                .replace("__FILE_COUNT__", str(len(files))))

        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def serve_download(self, filepath: Path):
        try:
            size = filepath.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filepath.name}"')
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception as e:
            print(f"[ERROR] download: {e}")
            self.send_error(500)

    def handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_FILE_SIZE:
            self.send_json({"ok": False, "error": "File too large (max 300 MB)"}, 400)
            return
        if length == 0:
            self.send_json({"ok": False, "error": "Empty request"}, 400)
            return
        body = self.rfile.read(length)
        if "multipart/form-data" not in content_type:
            self.send_json({"ok": False, "error": "Need multipart form"}, 400)
            return
        try:
            files = parse_multipart(body, content_type)
        except Exception as e:
            self.send_json({"ok": False, "error": f"Parse error: {e}"}, 400)
            return
        if not files:
            self.send_json({"ok": False, "error": "No file found"}, 400)
            return
        saved = []
        for original_name, file_bytes in files:
            if len(file_bytes) > MAX_FILE_SIZE:
                continue
            name = safe_filename(original_name)
            dest = UPLOAD_DIR / name
            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                i = 1
                while dest.exists():
                    dest = UPLOAD_DIR / f"{stem}_{i}{suffix}"
                    i += 1
            try:
                dest.write_bytes(file_bytes)
                saved.append(dest.name)
                print(f"[OK] Uploaded: {dest.name} ({format_size(len(file_bytes))})")
            except Exception as e:
                print(f"[ERROR] save: {e}")
        if saved:
            self.send_json({"ok": True, "files": saved})
        else:
            self.send_json({"ok": False, "error": "Could not save"}, 500)

    def handle_delete(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        name = qs.get("name", [""])[0]
        name = os.path.basename(name)
        fp = UPLOAD_DIR / name
        if fp.is_file():
            try:
                fp.unlink()
                print(f"[OK] Deleted: {name}")
            except Exception as e:
                print(f"[ERROR] delete: {e}")
        self.send_json({"ok": True})

    def handle_clear(self):
        count = 0
        for f in list(UPLOAD_DIR.iterdir()):
            if f.is_file():
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        print(f"[OK] Cleared {count} files")
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def handle_notepad(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            text = data.get("text", "")
            NOTEPAD_FILE.write_text(text, encoding="utf-8")
            self.send_json({"ok": True})
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)}, 400)


class ReusableServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ip = get_local_ip()
    print()
    print("=" * 54)
    print("          Local Share  •  Zero Install")
    print("          Designed by Bhim Mondal")
    print("=" * 54)
    print()
    print(f"  Is PC pe open karo      :  http://127.0.0.1:{PORT}")
    print(f"  Doosre devices se open  :  http://{ip}:{PORT}")
    print()
    print("  • Same WiFi pe raho")
    print("  • Windows Firewall → Allow Access")
    print("  • Band karne ke liye  Ctrl + C")
    print("=" * 54)
    print()
    try:
        with ReusableServer(("0.0.0.0", PORT), Handler) as httpd:
            print(f"[READY] Server running on port {PORT}...\n")
            httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e) or "already in use" in str(e).lower():
            print(f"[ERROR] Port {PORT} busy hai.")
        else:
            print(f"[ERROR] {e}")
    except KeyboardInterrupt:
        print("\n[BYE] Server band ho gaya.")


if __name__ == "__main__":
    main()
