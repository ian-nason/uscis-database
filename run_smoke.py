"""Local HTTP range test; serves only the candidate and a temporary registry."""
import argparse,http.server,json,os,re,subprocess,sys,threading,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--python',default=sys.executable,help='Python with the released datapond client installed')
parser.add_argument('--rscript',default='Rscript')
parser.add_argument('--r-library',default='',help='Optional existing R library containing datapond')
parser.add_argument('--db',type=Path,required=True)
parser.add_argument('--pilot',action='store_true')
args=parser.parse_args()
OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
DB=args.db
COUNTS={'requests':0,'bytes_sent':0,'ranges':0}
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_HEAD(self):self.serve(False)
 def do_GET(self):self.serve(True)
 def serve(self,body):
  COUNTS['requests']+=1
  if self.path=='/registry.json':
   data=json.dumps({'databases':[{'id':'uscis','name':'USCIS applications local review','size_gb':DB.stat().st_size/1024**3,'attach_url':f'http://127.0.0.1:{self.server.server_port}/uscis.duckdb'}]}).encode()
   self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
   if body:self.wfile.write(data)
   return
  if self.path!='/uscis.duckdb':self.send_error(404);return
  size=DB.stat().st_size;start=0;end=size-1
  requested=self.headers.get('Range')
  if requested:
   match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
   if not match:self.send_error(416);return
   start=int(match[1]);end=min(int(match[2]) if match[2] else end,end)
   if start>end:self.send_error(416);return
   COUNTS['ranges']+=1
  self.send_response(206 if requested else 200)
  self.send_header('Content-Type','application/octet-stream');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1));self.send_header('ETag','"uscis-local-reviewed"')
  if requested:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.end_headers()
  if body:
   with DB.open('rb') as f:
    f.seek(start);remaining=end-start+1
    while remaining:
     data=f.read(min(65536,remaining));self.wfile.write(data);remaining-=len(data);COUNTS['bytes_sent']+=len(data)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base=f'http://127.0.0.1:{server.server_port}/registry.json'
run_id=uuid.uuid4().hex
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
commands={
 'python':[args.python,str(ROOT/'smoke_python.py'),base,str(OUT/'python-cache'/run_id),str(args.pilot).lower()],
 'r':[args.rscript,str(ROOT/'smoke_r.R'),base,str(OUT/'r-cache'/run_id),args.r_library,str(args.pilot).lower()],
}
results={}
try:
 for key,command in commands.items():
  start=time.monotonic()
  p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180)
  results[key]={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'elapsed_seconds':round(time.monotonic()-start,3)}
  (OUT/(key+'-smoke.log')).write_text(p.stdout+'\n'+p.stderr)
  print(key,json.dumps(results[key]),flush=True)
finally:server.shutdown();server.server_close()
results['http']=COUNTS
results['scope']={'is_pilot':args.pilot,'database':str(DB.resolve()),'sha256':__import__('common').sha256(DB)}
results['commands']=commands
(OUT/'consumer-smoke.json').write_text(json.dumps(results,indent=2))
raise SystemExit(0 if len(results)==5 and all(results[k]['exit_code']==0 for k in commands) else 1)
