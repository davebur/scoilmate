"""Launch only our own temporary server, request preview resources, then stop it."""
from pathlib import Path
import json, os, socket, subprocess, tempfile, time, urllib.request
ROOT=Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
env=dict(os.environ,HOST='127.0.0.1',PORT=str(port),RELOAD='0')
with tempfile.TemporaryFile(mode='w+') as log:
    proc=subprocess.Popen([str(ROOT/'run_local_testing')],cwd='/tmp',env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as r:
                    assert json.load(r)=={'status':'ok','app':'ScoilMate','mode':'preview'}
                break
            except OSError:
                if proc.poll() is not None: raise RuntimeError('Preview exited')
                time.sleep(.1)
        else: raise RuntimeError('Preview did not become ready')
        for path,expected in [('/',b'not ready for student use'),('/practice/english/q/1',b'Check answer'),('/static/branding/favicon.ico',None),('/static/branding/scoilmate-icon-192.png',None)]:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=3) as r:
                body=r.read(); assert r.status==200 and body
                if expected: assert expected in body
                print('PASS GET',path,r.status,len(body),'bytes')
        print('PASS GET /health; launcher works from /tmp; test port',port)
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
        log.seek(0); print(log.read())
assert proc.poll() is not None
print('PASS owned temporary server stopped')
for bad in ({'PORT':'0'},{'PORT':'abc'},{'HOST':'not-a-host'},{'RELOAD':'yes'}):
    result=subprocess.run([str(ROOT/'run_local_testing')],env=dict(env,**bad),capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'Invalid local testing settings' in result.stderr
print('PASS invalid settings rejected')
