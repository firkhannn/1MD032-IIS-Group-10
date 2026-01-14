import os
import sys
import time
import signal
import subprocess
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

PROCS = {"emotion": None, "bot": None}


# ---------------- Utilities ----------------
def pyexe():
    return sys.executable  # uses current venv python


def is_running(name: str) -> bool:
    p = PROCS.get(name)
    return p is not None and p.poll() is None


def start_process(name: str, script: str):
    if is_running(name):
        return {"ok": True, "message": f"{name} already running", "pid": PROCS[name].pid}

    if not os.path.exists(script):
        return {"ok": False, "message": f"Missing file: {script}"}

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    p = subprocess.Popen(
        [pyexe(), script],
        stdout=subprocess.DEVNULL,   # keep simple; no log spam
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags,
    )
    PROCS[name] = p
    return {"ok": True, "message": f"Started {name}", "pid": p.pid}


def stop_process(name: str):
    p = PROCS.get(name)
    if p is None:
        return {"ok": True, "message": f"{name} not running"}

    if p.poll() is not None:
        PROCS[name] = None
        return {"ok": True, "message": f"{name} already stopped"}

    try:
        if os.name == "nt":
            # best effort graceful
            p.send_signal(signal.CTRL_BREAK_EVENT)
            time.sleep(0.8)
        else:
            p.terminate()
            time.sleep(0.8)

        if p.poll() is None:
            p.kill()

        PROCS[name] = None
        return {"ok": True, "message": f"Stopped {name}"}
    except Exception as e:
        return {"ok": False, "message": f"Stop failed: {e}"}


def wait_for_emotion_api(timeout=8.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get("http://127.0.0.1:5000/emotion", timeout=0.4)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def status_payload():
    return {
        "emotion_running": is_running("emotion"),
        "bot_running": is_running("bot"),
        "emotion_pid": (PROCS["emotion"].pid if is_running("emotion") else None),
        "bot_pid": (PROCS["bot"].pid if is_running("bot") else None),
        "emotion_api_reachable": wait_for_emotion_api(timeout=0.1),
    }


# ---------------- Web UI ----------------
PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>EmoConnect Controller</title>
  <style>
    body{
      margin:0;
      font-family: Arial, sans-serif;
      background:#f4f5f7;
      display:flex;
      justify-content:center;
      align-items:center;
      min-height:100vh;
    }
    .wrap{
      width:min(920px, 94vw);
      background:#f2f2f2;
      border-radius:24px;
      padding:48px 24px 28px;
      box-shadow:0 10px 30px rgba(0,0,0,0.10);
      text-align:center;
    }
    .brand{
      display:flex;
      flex-direction:column;
      align-items:center;
      gap:16px;
      margin-bottom:34px;
    }
    .logo{
      width:150px;
      height:150px;
      border-radius:28px;
      background:white;
      display:flex;
      align-items:center;
      justify-content:center;
      box-shadow:0 8px 20px rgba(0,0,0,0.10);
      overflow:hidden;
    }
    .logo img{
      width:100%;
      height:100%;
      object-fit:cover;
    }
    .title{
      font-size:56px;
      font-weight:800;
      letter-spacing:0.5px;
      color:#111;
      margin:0;
      line-height:1;
    }

    .buttons{
      display:flex;
      justify-content:center;
      gap:36px;
      flex-wrap:wrap;
      margin:26px 0 26px;
    }

    .btn{
      width:370px;
      max-width:90vw;
      height:120px;
      border:none;
      border-radius:999px;
      font-size:44px;
      font-weight:800;
      cursor:pointer;
      display:flex;
      align-items:center;
      justify-content:center;
      gap:18px;
      box-shadow:0 10px 0 rgba(0,0,0,0.12);
      transition:transform 0.05s ease;
    }
    .btn:active{
      transform:translateY(2px);
      box-shadow:0 8px 0 rgba(0,0,0,0.12);
    }
    .btn-start{ background:#86e06b; color:#111; }
    .btn-stop{  background:#b94545; color:#111; }

    .icon{
      width:64px;
      height:64px;
      border-radius:999px;
      background:#111;
      display:flex;
      align-items:center;
      justify-content:center;
    }
    .icon svg{
      width:32px;
      height:32px;
      fill:#fff;
    }

    .status{
      margin-top:18px;
      background:#fff;
      border-radius:18px;
      padding:14px 16px;
      text-align:left;
      border:1px solid #e5e5e5;
      max-width:720px;
      margin-left:auto;
      margin-right:auto;
    }
    pre{
      margin:8px 0 0;
      white-space:pre-wrap;
      word-break:break-word;
      font-size:14px;
      line-height:1.35;
    }
    .hint{
      margin-top:10px;
      font-weight:700;
    }
    .ok{ color:#117a37; }
    .bad{ color:#b00020; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="logo">
        <img src="/static/logo.jpg" alt="EmoConnect logo">
      </div>
      <h1 class="title">EmoConnect</h1>
    </div>

    <div class="buttons">
      <button class="btn btn-start" onclick="startSystem()">
        <span class="icon" aria-hidden="true">
          <!-- Play icon -->
          <svg viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z"></path>
          </svg>
        </span>
        Start
      </button>

      <button class="btn btn-stop" onclick="stopSystem()">
        <span class="icon" aria-hidden="true">
          <!-- Stop icon -->
          <svg viewBox="0 0 24 24">
            <path d="M7 7h10v10H7z"></path>
          </svg>
        </span>
        Stop
      </button>
    </div>

    <div class="status">
      <div><b>Status</b></div>
      <pre id="statusBox">Loading...</pre>
      <div id="hint" class="hint"></div>
    </div>
  </div>

<script>
async function startSystem(){
  const r = await fetch('/start', {method:'POST'});
  const j = await r.json();
  await refreshStatus();
  alert(JSON.stringify(j, null, 2));
}

async function stopSystem(){
  const r = await fetch('/stop', {method:'POST'});
  const j = await r.json();
  await refreshStatus();
  alert(JSON.stringify(j, null, 2));
}

async function refreshStatus(){
  const r = await fetch('/status');
  const j = await r.json();
  document.getElementById('statusBox').textContent = JSON.stringify(j, null, 2);

  const hint = document.getElementById('hint');
  if(!j.emotion_api_reachable){
    hint.className = "hint bad";
    hint.textContent = "Emotion API not reachable. Make sure the webcam window is allowed and port 5000 is free.";
  } else if(!j.bot_running){
    hint.className = "hint bad";
    hint.textContent = "Bot not running. Ensure Furhat Studio is open and Remote API is available.";
  } else {
    hint.className = "hint ok";
    hint.textContent = "All good. Talk to Furhat now.";
  }
}

// auto-refresh every 1.5s so you don't need a refresh button
setInterval(refreshStatus, 1500);
refreshStatus();
</script>
</body>
</html>
"""


@app.get("/")
def home():
    return render_template_string(PAGE)


# ---------------- API ----------------
@app.get("/status")
def status():
    return jsonify(status_payload())


@app.post("/start")
def start():
    # Start webcam first
    res_emotion = start_process("emotion", "emotion_webcam.py")

    # Wait until emotion API is actually up (better than fixed sleep)
    ok = wait_for_emotion_api(timeout=30.0)


    # Start bot after webcam is ready
    res_bot = start_process("bot", "main_integrated.py") if ok else {
        "ok": False,
        "message": "Emotion API did not come up. Bot not started."
    }

    return jsonify({
        "emotion": res_emotion,
        "emotion_api_ready": ok,
        "bot": res_bot
    })


@app.post("/stop")
def stop():
    # Stop bot first, then webcam
    res_bot = stop_process("bot")
    res_emotion = stop_process("emotion")
    return jsonify({"bot": res_bot, "emotion": res_emotion})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
