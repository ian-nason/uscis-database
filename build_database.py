"""Source-preserving USCIS importer; requires only DuckDB and Python stdlib."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,os,shutil,tempfile,threading
import duckdb
from common import read_lock,verify_source,require,refuse_output,check_budget,sha256
ROOT=Path(__file__).resolve().parent

def quote(name):return '"'+name.replace('"','""')+'"'

def compare_rows(con,table,source,batch=4096):
    """Exact streaming comparison; fail if either scan violates source order."""
    left=con.cursor();right=con.cursor();seen=0
    try:
        left.execute('SELECT * FROM '+quote(table))
        right.execute('SELECT file_row_number+1 AS _source_row,* EXCLUDE(file_row_number) FROM read_parquet(?,file_row_number=true)',[str(source)])
        while True:
            stored=left.fetchmany(batch);original=right.fetchmany(batch)
            require(len(stored)==len(original),f'Row-stream length differs: {table}')
            if not stored:break
            for offset,(a,b) in enumerate(zip(stored,original),1):
                require(a[0]==b[0]==seen+offset,f'Noncontiguous source ordinals: {table}')
                require(a==b,f'Field value mismatch at {table} source ordinal {seen+offset}')
            seen+=len(stored)
    finally:left.close();right.close()
    return seen

def build(lock_path,output,pilot=False):
    lock=read_lock(lock_path);output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    require(lock['is_pilot']==pilot,'Explicit --pilot must match the source-lock scope')
    refuse_output(output)
    for item in lock['tables']:verify_source(item)
    fields=json.loads((ROOT/'field-definitions.json').read_text())
    for column in {'_source_row'} | {c for item in lock['tables'] for c,_ in item['schema']}:
        require(isinstance(fields.get(column),dict) and isinstance(fields[column].get('description'),str),f'Missing field definition: {column}')
    cap=(64*1024**2 if pilot else 8*1024**3);reserve=(512*1024**2 if pilot else 2*1024**3)
    require(shutil.disk_usage(output.parent).free>=cap+reserve,'Insufficient build workspace reserve')
    work=Path(tempfile.mkdtemp(prefix='.uscis-work-',dir=output.parent));working=work/output.name
    config={'memory_limit':'128MiB' if pilot else '2GiB','threads':'1','max_temp_directory_size':'0B' if pilot else '4GiB','temp_directory':str(work/'spill'),'preserve_insertion_order':'true'}
    con=duckdb.connect(str(working),config=config);stop=threading.Event();errors=[]
    def monitor():
        while not stop.wait(.1):
            try:check_budget(work,output.parent,cap,reserve)
            except Exception as error:errors.append(str(error));con.interrupt();return
    watch=threading.Thread(target=monitor,daemon=True);watch.start()
    report={'built_utc':datetime.now(timezone.utc).isoformat(),'dataset':'uscis-pilot' if pilot else 'uscis','is_pilot':pilot,'full_source_hashes_verified':not pilot,'input_file_hashes_verified':True,'source_lock_sha256':sha256(lock_path),'duckdb':duckdb.__version__,'memory_limit':config['memory_limit'],'threads':1,'spill_limit':config['max_temp_directory_size'],'working_cap_bytes':cap,'physical_reserve_bytes':reserve,'tables':{}}
    try:
        con.execute('CREATE TABLE _metadata(table_name VARCHAR,description VARCHAR,row_count BIGINT,column_count INTEGER,source_url VARCHAR,license VARCHAR,built_at TIMESTAMP)')
        con.execute('CREATE TABLE _columns(table_name VARCHAR,column_name VARCHAR,data_type VARCHAR,source_file VARCHAR,example_value VARCHAR,join_hint VARCHAR,null_pct DOUBLE,description VARCHAR,null_count BIGINT)')
        con.execute('CREATE TABLE _provenance(table_name VARCHAR,source_url VARCHAR,source_commit VARCHAR,source_sha256 VARCHAR,source_bytes BIGINT,is_pilot BOOLEAN,original_full_source_url VARCHAR,expected_full_source_sha256 VARCHAR)')
        for item in lock['tables']:
            table=item['table'];path=item['resolved_path'];qtable=quote(table)
            schema=[[x[0],x[1]] for x in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()]
            require(schema==item['schema'],f'Pinned schema differs: {table}')
            con.execute(f'CREATE TABLE {qtable} AS SELECT file_row_number+1 AS _source_row,* EXCLUDE(file_row_number) FROM read_parquet(?,file_row_number=true)',[str(path)])
            rows=con.execute(f'SELECT count(*) FROM {qtable}').fetchone()[0]
            require(rows==item['rows'],f'Pinned row count differs: {table}')
            checked=compare_rows(con,table,path);require(checked==rows,'Incomplete exact row verification')
            nulls={};columns=[['_source_row','BIGINT']]+schema
            # One aggregate scan for NULL counts; no high-cardinality distinct set needed.
            values=con.execute('SELECT '+','.join(f'count(*) FILTER(WHERE {quote(c)} IS NULL)' for c,_ in columns)+' FROM '+qtable).fetchone()
            nulls=dict(zip((x[0] for x in columns),values))
            for column,expected in item.get('expected_null_counts',{}).items():require(nulls[column]==expected,f'Footer NULL baseline differs: {table}.{column}')
            summary=con.execute(f'''SELECT count(*) FILTER(WHERE duplicate_drop_row),count(*) FILTER(WHERE duplicate_likely),count(*) FILTER(WHERE duplicate_drop_row IS NULL),count(*) FILTER(WHERE unique_identifier IS NULL),count(*) FILTER(WHERE file_original IS NULL OR row_original IS NULL),count(*) FILTER(WHERE decision_date<rec_date),min(rec_date),max(rec_date) FROM {qtable}''').fetchone()
            duplicate_keys=con.execute(f'SELECT count(*) FROM (SELECT file_original,row_original FROM {qtable} GROUP BY 1,2 HAVING count(*)>1)').fetchone()[0]
            flag_errors=con.execute(f'SELECT count(*) FROM {qtable} WHERE duplicate_drop_row IS DISTINCT FROM (coalesce(duplicate_likely,FALSE) AND NOT duplicate_last)').fetchone()[0]
            require(flag_errors==0,f'Publisher duplicate-flag relationship differs: {table}')
            dates={c:list(con.execute(f'SELECT min({quote(c)}),max({quote(c)}) FROM {qtable}').fetchone()) for c,t in schema if t=='DATE'}
            result={'rows':rows,'schema':columns,'exact_rows_compared':checked,'null_counts':nulls,'duplicate_source_key_groups':duplicate_keys,'duplicate_flag_relationship_errors':flag_errors,'flagged_drop_rows':summary[0],'likely_duplicate_rows':summary[1],'null_duplicate_flags':summary[2],'missing_applicant_ids':summary[3],'missing_source_keys':summary[4],'decision_before_receipt_rows':summary[5],'date_ranges':dates}
            report['tables'][table]=result
            scope='Pilot first 2048 source rows; not representative or full dataset. ' if pilot else ''
            description=scope+'Application records; duplicates/flags and missing values preserved. Not unique applicants or active beneficiaries.'
            con.execute('INSERT INTO _metadata VALUES (?,?,?,?,?,?,?)',[table,description,rows,len(columns),lock['source_page'],lock['data_license'],datetime.now(timezone.utc).replace(tzinfo=None)])
            original=item['original_full_source'] if pilot else item
            input_url='local-pilot:'+item['file'] if pilot else item['url']
            con.execute('INSERT INTO _provenance VALUES (?,?,?,?,?,?,?,?)',[table,input_url,item['commit'],item['sha256'],item['bytes'],pilot,original['url'],original['sha256']])
            for column,typ in columns:
                definition=fields[column];hint=definition.get('join_hint')
                con.execute('INSERT INTO _columns VALUES (?,?,?,?,?,?,?,?,?)',[table,column,typ,item['file'],None,hint,100*nulls[column]/rows,definition['description'],nulls[column]])
            if errors:raise RuntimeError(errors)
        con.execute('CHECKPOINT')
    finally:
        stop.set();watch.join(timeout=2);con.close()
    if errors:raise RuntimeError(errors)
    report['final_budget_check']=check_budget(work,output.parent,cap,reserve)
    report['database_bytes']=working.stat().st_size;report['database_sha256']=sha256(working)
    report['audit_status']='Source integrity/schema/equality checks passed; full data semantics and independent release audits still required'
    check_budget(work,output.parent,cap,reserve);refuse_output(output)
    os.link(working,output)
    with output.with_suffix('.manifest.json').open('x') as f:json.dump(report,f,indent=2,default=str)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lock',type=Path,default=ROOT/'source-lock.json');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--pilot',action='store_true');args=parser.parse_args()
    result=build(args.lock,args.output,args.pilot)
    print(json.dumps({k:v for k,v in result.items() if k!='tables'},indent=2))

if __name__=='__main__':main()
