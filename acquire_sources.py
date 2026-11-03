"""Preflight by default; --download explicitly acquires the two immutable files."""
from pathlib import Path
import argparse,json,os,re,shutil,tempfile,urllib.request
from common import read_lock,verify_source,require,sha256
ROOT=Path(__file__).resolve().parent
RESERVE=2*1024**3
WORK_CAP=8*1024**3

def fetch(table,reserve=RESERVE):
    path=Path(table['resolved_path']);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():verify_source(table);return
    require(re.fullmatch(r'https://media\.githubusercontent\.com/media/deportationdata/uscis/[a-f0-9]{40}/data/(daca|tps)-latest\.parquet',table['url']) is not None,'Unpinned/unexpected source URL')
    require('/'+table['commit']+'/' in table['url'],'Source URL/commit mismatch')
    require(shutil.disk_usage(path.parent).free>=reserve+table['bytes'],'Insufficient acquisition reserve')
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.part',dir=path.parent);part=Path(name)
    total=0;digest=__import__('hashlib').sha256()
    with os.fdopen(fd,'wb') as output:
        with urllib.request.urlopen(table['url'],timeout=60) as response:
            require(response.status==200,'Source did not return HTTP200')
            while True:
                chunk=response.read(min(1024**2,table['bytes']-total+1))
                if not chunk:break
                total+=len(chunk);require(total<=table['bytes'],'Source exceeds pinned length')
                require(shutil.disk_usage(path.parent).free>=reserve+len(chunk),'Source transfer crossed physical reserve')
                output.write(chunk);digest.update(chunk)
    require(total==table['bytes'] and digest.hexdigest()==table['sha256'],'Source full length/hash mismatch')
    require(shutil.disk_usage(path.parent).free>=reserve,'Source transfer crossed final reserve')
    os.link(part,path)  # no overwrite even when another process creates the path late
    part.unlink()      # only this function's completed temporary link

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lock',type=Path,default=ROOT/'source-lock.json');parser.add_argument('--download',action='store_true');args=parser.parse_args()
    lock=read_lock(args.lock);missing=[]
    for table in lock['tables']:
        if table['resolved_path'].exists():verify_source(table)
        else:missing.append(table)
    free=shutil.disk_usage(args.lock.resolve().parent).free
    needed=sum(t['bytes'] for t in missing)+WORK_CAP+RESERVE
    print(json.dumps({'missing_bytes':sum(t['bytes'] for t in missing),'physical_free_bytes':free,'full_cloud_budget_bytes':needed,'download_requested':args.download}),flush=True)
    if not args.download:return
    require(not lock['is_pilot'],'Pilot sources are supplied locally; no network acquisition')
    require(free>=needed,'Cloud build/acquisition capacity preflight failed')
    for table in missing:fetch(table)
    for table in lock['tables']:verify_source(table)
    print(json.dumps({'complete_source_hashes_verified':True,'source_bytes':sum(t['bytes'] for t in lock['tables'])}))

if __name__=='__main__':main()
