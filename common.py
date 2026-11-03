"""Small explicit integrity and storage guards shared by acquisition/import."""
from pathlib import Path
import hashlib,json,re,shutil

def require(condition,message):
    if not condition:raise ValueError(message)

def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):digest.update(chunk)
    return digest.hexdigest()

def safe_path(root,relative):
    target=(Path(root)/relative).resolve()
    require(target.is_relative_to(Path(root).resolve()),'Source path escapes its workspace')
    return target

def read_lock(path):
    path=Path(path).resolve();lock=json.loads(path.read_text())
    require(isinstance(lock.get('is_pilot'),bool),'Lock must explicitly identify pilot/full scope')
    require({t['table'] for t in lock['tables']}=={'daca_applications','tps_applications'},'Expected exactly DACA and TPS')
    require(len(lock['tables'])==2,'Duplicate source table')
    for table in lock['tables']:
        require(bool(re.fullmatch('[a-f0-9]{64}',table['sha256'])),'Invalid SHA256 pin')
        require(0<table['bytes']<=128*1024**2,'Source exceeds bounded acquisition size')
        require(table['rows']>0,'Empty source is not a complete dataset')
        require(len({c[0] for c in table['schema']})==len(table['schema']),'Duplicate source columns')
        table['resolved_path']=safe_path(path.parent,table['local_path'])
    return lock

def verify_source(table):
    path=Path(table['resolved_path'])
    require(path.stat().st_size==table['bytes'],f'Wrong source length: {path.name}')
    require(sha256(path)==table['sha256'],f'Wrong source SHA256: {path.name}')

def refuse_output(output):
    output=Path(output)
    for path in (output,Path(str(output)+'.wal'),output.with_suffix('.manifest.json')):
        if path.exists() or path.is_symlink():raise FileExistsError(path)

def check_budget(work,parent,cap,reserve):
    used=sum(p.stat().st_size for p in Path(work).rglob('*') if p.is_file())
    free=shutil.disk_usage(parent).free
    require(used<=cap and free>=reserve,f'Storage guard: working={used}, cap={cap}, free={free}, reserve={reserve}')
    return {'work_bytes':used,'free_bytes':free}
