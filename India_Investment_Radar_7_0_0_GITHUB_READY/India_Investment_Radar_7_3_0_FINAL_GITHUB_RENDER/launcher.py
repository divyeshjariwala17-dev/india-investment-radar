from pathlib import Path
import json, os, socket, subprocess, sys, time, urllib.request, webbrowser

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RUNTIME = DATA / ".runtime.json"
PORT_START = 8507
PORT_END = 8599


def _hidden_flags():
    return 0x08000000 if os.name == "nt" else 0


def process_alive(pid: int) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=3,
                creationflags=_hidden_flags(),
            )
            return str(pid) in (r.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def health_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/_stcore/health", timeout=0.6) as r:
            return r.status == 200
    except Exception:
        return False


def port_free(port: int) -> bool:
    s = socket.socket()
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def find_free_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        if port_free(port):
            return port
    raise RuntimeError(f"No free local port found between {PORT_START} and {PORT_END}.")


def load_runtime():
    try:
        return json.loads(RUNTIME.read_text(encoding="utf-8")) if RUNTIME.exists() else {}
    except Exception:
        return {}


def save_runtime(pid: int, port: int):
    DATA.mkdir(parents=True, exist_ok=True)
    RUNTIME.write_text(json.dumps({"pid": int(pid), "port": int(port)}, indent=2), encoding="utf-8")


def show_error(message: str):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "India Investment Radar", 0x10)
            return
        except Exception:
            pass
    print(message)


runtime = load_runtime()
pid = runtime.get("pid")
port = runtime.get("port")
if pid and port and process_alive(pid) and health_ok(port):
    webbrowser.open(f"http://127.0.0.1:{port}")
    raise SystemExit(0)

try:
    port = find_free_port()
except Exception as exc:
    show_error(str(exc))
    raise SystemExit(1)

py = BASE / ".venv" / "Scripts" / "pythonw.exe" if os.name == "nt" else BASE / ".venv" / "bin" / "python"
app = BASE / "app.py"
if not py.exists() or not app.exists():
    show_error("India Investment Radar setup is incomplete. Run INSTALL_OR_UPDATE_PC.bat again.")
    raise SystemExit(1)

try:
    proc = subprocess.Popen(
        [
            str(py), "-m", "streamlit", "run", str(app),
            "--server.port", str(port),
            "--server.address", "127.0.0.1",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--runner.magicEnabled", "false",
        ],
        cwd=str(BASE),
        creationflags=_hidden_flags(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
except Exception as exc:
    show_error(f"Could not start India Investment Radar.\n\n{exc}")
    raise SystemExit(1)

save_runtime(proc.pid, port)
for _ in range(100):
    if health_ok(port):
        webbrowser.open(f"http://127.0.0.1:{port}")
        raise SystemExit(0)
    if proc.poll() is not None:
        break
    time.sleep(0.35)

show_error("India Investment Radar did not start successfully. Run the installer again or check System diagnostics.")
raise SystemExit(1)
