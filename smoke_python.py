"""Released Python client against a private loopback registry; aggregate output only."""
import importlib.metadata,json,sys
from pathlib import Path
import datapond,datapond.registry as registry,duckdb
from common import require
registry.REGISTRY_URL=sys.argv[1]
registry.CACHE_DIR=Path(sys.argv[2]);registry.CACHE_FILE=registry.CACHE_DIR/'registry.json'
pilot=sys.argv[3]=='true'
require(datapond.list()==['uscis'],'Unexpected local catalog')
con=datapond.connect('uscis',quiet=True)
try:
    con.execute("SET memory_limit='128MiB'");con.execute('SET threads=1');con.execute("SET max_temp_directory_size='0B'")
    counts={'daca_applications':2048 if pilot else 4526373,'tps_applications':2048 if pilot else 6680172}
    for table,expected in counts.items():require(con.execute('SELECT count(*) FROM '+table).fetchone()[0]==expected,'Wrong client row count')
    require(con.execute('SELECT count(*) FROM _metadata').fetchone()[0]==2,'Missing table metadata')
    require(con.execute('SELECT count(*) FROM _columns').fetchone()[0]==63,'Missing field metadata')
    require(con.execute('SELECT count(*) FROM _provenance WHERE is_pilot=?',[pilot]).fetchone()[0]==2,'Wrong build scope')
    definitions=json.loads((Path(__file__).resolve().parent/'field-definitions.json').read_text())
    for column,description,hint in con.execute('SELECT column_name,description,join_hint FROM _columns').fetchall():
        require(description==definitions[column]['description'] and hint==definitions[column].get('join_hint'),'Field metadata differs: '+column)
    example=con.execute('SELECT data_source, count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source').fetchall()
    print(json.dumps({'passed':True,'is_pilot':pilot,'client':'Python datapond','version':importlib.metadata.version('datapond'),'duckdb':duckdb.__version__,'counts':counts,'example':example}))
finally:con.close()
