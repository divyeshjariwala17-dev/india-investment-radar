from pathlib import Path
import json, os, socket, subprocess, sys, time, urllib.request, webbrowser

BASE=Path(__file__).resolve().parent
DATA=BASE/'data';RUNTIME=DATA/'.runtime.json'
PORT_START=8507;PORT_END=8599

def hidden():return 0x08000000 if os.name=='nt' else 0

def process_alive(pid):
    try:pid=int(pid)
    except Exception:return False
    if pid<=0:return False
    if os.name=='nt':
        try:
            r=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH'],capture_output=True,text=True,timeout=3,creationflags=hidden())
            return str(pid) in (r.stdout or '')
        except Exception:return False
    try:os.kill(pid,0);return True
    except Exception:return False

def health(port,host='127.0.0.1'):
    try:
        with urllib.request.urlopen(f'http://{host}:{int(port)}/_stcore/health',timeout=.8) as r:return r.status==200
    except Exception:return False

def free(port):
    s=socket.socket()
    try:s.bind(('0.0.0.0',int(port)));return True
    except OSError:return False
    finally:s.close()

def find_port():
    for p in range(PORT_START,PORT_END+1):
        if free(p):return p
    raise RuntimeError('No free Radar port found.')

def local_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));ip=s.getsockname()[0];s.close();return ip
    except Exception:
        try:return socket.gethostbyname(socket.gethostname())
        except Exception:return 'YOUR-PC-IP'

def stop_previous():
    try:d=json.loads(RUNTIME.read_text(encoding='utf-8')) if RUNTIME.exists() else {};pid=d.get('pid')
    except Exception:pid=None
    if pid and process_alive(pid):
        try:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(pid),'/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=hidden())
            else:os.kill(int(pid),15)
        except Exception:pass

def msg(text):
    if os.name=='nt':
        try:
            import ctypes;ctypes.windll.user32.MessageBoxW(0,text,'India Investment Radar — Phone Access',0x40);return
        except Exception:pass
    print(text)

stop_previous();time.sleep(.5)
port=find_port();py=BASE/'.venv'/'Scripts'/'pythonw.exe' if os.name=='nt' else BASE/'.venv'/'bin'/'python';app=BASE/'app.py'
if not py.exists() or not app.exists():msg('Setup is incomplete. Re-run RUN_THIS_ONLY_7_0_0_FULL_RELIABILITY_PREMIUM.bat.');raise SystemExit(1)
proc=subprocess.Popen([str(py),'-m','streamlit','run',str(app),'--server.port',str(port),'--server.address','0.0.0.0','--server.headless','true','--browser.gatherUsageStats','false','--runner.magicEnabled','false'],cwd=str(BASE),creationflags=hidden(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
DATA.mkdir(parents=True,exist_ok=True);RUNTIME.write_text(json.dumps({'pid':proc.pid,'port':port,'mode':'LAN'},indent=2),encoding='utf-8')
for _ in range(100):
    if health(port):
        ip=local_ip();webbrowser.open(f'http://127.0.0.1:{port}')
        msg(f'Radar is running for devices on the SAME Wi-Fi/LAN.\n\nOn your phone open:\nhttp://{ip}:{port}\n\nKeep this PC on for this LAN mode. For anywhere access with the PC off, deploy the included WEB_DEPLOY package to an online server.')
        raise SystemExit(0)
    if proc.poll() is not None:break
    time.sleep(.35)
msg('Radar did not start in phone/LAN mode. Re-run the installer or check System Check.');raise SystemExit(1)
