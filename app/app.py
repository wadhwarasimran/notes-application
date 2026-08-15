"""
notes-api v0.6.0 — L12 rollout target (only __version__ differs from 0.5.0).

What changed from v0.4.0 (the student's Act B diff):
  * GET /version — echoes the build version (APP_VERSION env overrides), so a
    rolling update is observable (L12).
  * GET /work?n=N — does a FIXED amount of CPU work (N million iterations) and
    reports wall-clock ms. Fixed work (not a wall-clock deadline) is what makes
    CPU throttling visible: under a tight cpu limit the SAME work takes longer
    (L13 throttling, L14 HPA load source).
  * GET /mem?mb=M&hold=S — allocates M MiB of real memory and holds it, so an
    over-limit allocation can be OOMKilled on purpose (L13).
All v0.4.0 endpoints (/ /notes /healthz /ready /admin/break) are unchanged.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)

__version__ = "0.6.0"

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")
API_KEY = os.environ.get("API_KEY", "")
GREETING = os.environ.get("GREETING")

_data_env = os.environ.get("DATA_DIR")
PERSIST = _data_env is not None
DATA_DIR = Path(_data_env) if PERSIST else None
NOTES_FILE = (DATA_DIR / "notes.json") if PERSIST else None

STATE_DIR = DATA_DIR if PERSIST else Path(tempfile.gettempdir())
STATE_DIR.mkdir(parents=True, exist_ok=True)
READY_FILE = STATE_DIR / "ready"
HEALTH_FILE = STATE_DIR / "healthy"
READY_FILE.touch()
HEALTH_FILE.touch()

print(f"[boot] notes-api startings — version={__version__} LOG_LEVEL={LOG_LEVEL} PERSIST={PERSIST}")

_mem: list[dict] = []


def _load() -> list[dict]:
    if not PERSIST:
        return _mem
    return json.loads(NOTES_FILE.read_text()) if NOTES_FILE.exists() else []


def _save(notes: list[dict]) -> None:
    global _mem
    if not PERSIST:
        _mem = notes
    else:
        NOTES_FILE.write_text(json.dumps(notes))


@app.get("/healthz")
def healthz():
    return ("ok\n", 200) if HEALTH_FILE.exists() else ("broken\n", 500)


@app.get("/ready")
def ready():
    return ("ready\n", 200) if READY_FILE.exists() else ("not ready\n", 503)


@app.get("/version")
def version():
    return (os.environ.get("APP_VERSION", __version__) + "\n", 200)


@app.get("/work")
def work():
    """Fixed CPU work → wall-clock ms. Under a tight cpu limit the SAME work
    takes proportionally longer. ?n = millions of iterations (default 5)."""
    n_million = int(request.args.get("n", "5"))
    iters = n_million * 1_000_000
    start = time.perf_counter()
    x = 0
    for i in range(iters):
        x = (x + i * i) % 1_000_003
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return (f"work n={n_million}M elapsed_ms={elapsed_ms:.0f}\n", 200)


@app.get("/mem")
def mem():
    """Allocate ~mb MiB of real memory and hold it. Over the container limit →
    kernel OOMKills (exit 137). ?mb (default 50), ?hold seconds (default 15) akshdgsbd."""
    mb = int(request.args.get("mb", "50"))
    hold = int(request.args.get("hold", "15"))
    blob = bytearray(mb * 1024 * 1024)   # zero-fills → real RSS, not lazy
    time.sleep(hold)
    return (f"allocated_mib={mb} held_s={hold} len={len(blob)}\n", 200)


@app.get("/notes")
def list_notes():
    return jsonify(_load())


@app.post("/notes")
def add_note():
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "missing or wrong X-API-Keys"}), 401
    text = (request.get_json(silent=True) or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    notes = _load()
    note = {"id": len(notes) + 1, "text": text}
    notes.append(note)
    _save(notes)
    return jsonify(note), 201


@app.post("/admin/break")
def admin_break():
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "auth required"}), 401
    HEALTH_FILE.unlink(missing_ok=True)
    return "healthz will now fail until the container restarts\n", 200


@app.get("/")
def root():
    if GREETING:
        return f"{GREETING} — try GET /notes\n"
    return "notes-api — try GET /notes or POST /notes with, this is to test {\"text\":\"...\"}\n"



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
