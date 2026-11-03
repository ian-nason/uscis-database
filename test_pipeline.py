"""Offline, bounded integration and integrity regressions using existing pilot rows."""
from pathlib import Path
from unittest import mock
from collections import namedtuple
import hashlib,io,json,os,shutil,subprocess,sys,tempfile,unittest
import duckdb
import acquire_sources as acquire
import build_database as build
from common import check_budget,read_lock
ROOT=Path(__file__).resolve().parent

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.parent=(ROOT/'evidence').resolve();self.parent.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='.uscis-test-',dir=self.parent);self.root=Path(self.tmp.name).resolve()
        self.lock=json.loads((ROOT/'pilot/source-lock.json').read_text())
        for item in self.lock['tables']:shutil.copyfile(ROOT/'pilot'/item['file'],self.root/item['file'])
        self.lock_path=self.root/'source-lock.json';self.save_lock();self.output=self.root/'test.duckdb'
        disk=namedtuple('disk','total used free')
        self.capacity=mock.patch('shutil.disk_usage',return_value=disk(16*1024**3,0,16*1024**3));self.capacity.start()
    def save_lock(self):self.lock_path.write_text(json.dumps(self.lock))
    def tearDown(self):
        self.capacity.stop()
        if self.root.parent!=self.parent or not self.root.name.startswith('.uscis-test-'):raise RuntimeError('Unsafe fixture cleanup')
        self.tmp.cleanup()
    def test_source_rows_flags_and_client_metadata_survive_import(self):
        report=build.build(self.lock_path,self.output,pilot=True)
        self.assertFalse(report['full_source_hashes_verified'])
        con=duckdb.connect(str(self.output),config={'threads':'1'})
        try:
            self.assertEqual(con.sql('SELECT sum(row_count) FROM _metadata').fetchone()[0],4096)
            self.assertEqual(con.sql('SELECT count(*) FROM _columns').fetchone()[0],63)
            definitions=json.loads((ROOT/'field-definitions.json').read_text())
            for column,description,hint in con.sql('SELECT column_name,description,join_hint FROM _columns').fetchall():
                self.assertEqual((description,hint),(definitions[column]['description'],definitions[column].get('join_hint')))
            provenance=con.sql('SELECT source_url,source_sha256,original_full_source_url,expected_full_source_sha256,is_pilot FROM _provenance ORDER BY table_name').fetchall()
            for row,item in zip(provenance,self.lock['tables']):
                self.assertEqual(row,('local-pilot:'+item['file'],item['sha256'],item['original_full_source']['url'],item['original_full_source']['sha256'],True))
            for item in self.lock['tables']:
                table=item['table'];self.assertEqual(report['tables'][table]['rows'],2048)
                self.assertEqual(report['tables'][table]['flagged_drop_rows'],1)
            con.execute("UPDATE daca_applications SET status='intentional regression corruption' WHERE _source_row=1")
            with self.assertRaisesRegex(ValueError,'Field value mismatch'):build.compare_rows(con,'daca_applications',self.root/self.lock['tables'][0]['file'])
        finally:con.close()
    def test_existing_output_or_orphan_wal_is_not_modified(self):
        wal=Path(str(self.output)+'.wal');wal.write_bytes(b'existing WAL')
        with self.assertRaises(FileExistsError):build.build(self.lock_path,self.output,pilot=True)
        self.assertEqual(wal.read_bytes(),b'existing WAL');self.assertFalse(self.output.exists())
    def test_schema_and_footer_null_baselines_fail_closed(self):
        self.lock['tables'][0]['schema'][0][1]='INTEGER';self.save_lock()
        with self.assertRaisesRegex(ValueError,'Pinned schema differs'):build.build(self.lock_path,self.output,pilot=True)
        self.assertFalse(self.output.exists())
        self.lock['tables'][0]['schema'][0][1]='VARCHAR';self.lock['tables'][0]['expected_null_counts']['unique_identifier']=1;self.save_lock()
        with self.assertRaisesRegex(ValueError,'Footer NULL baseline differs'):build.build(self.lock_path,self.output,pilot=True)
        self.assertFalse(self.output.exists())
    def test_pilot_cannot_be_mislabelled_full(self):
        with self.assertRaisesRegex(ValueError,'--pilot'):build.build(self.lock_path,self.output,pilot=False)
        self.assertFalse(self.output.exists())
    def test_missing_field_definitions_fail_before_opening_database(self):
        with mock.patch.object(build,'ROOT',self.root),mock.patch.object(build.duckdb,'connect') as connect:
            with self.assertRaises(FileNotFoundError):build.build(self.lock_path,self.output,pilot=True)
        connect.assert_not_called();self.assertFalse(self.output.exists())
    def test_wrong_hash_rejected_under_optimized_python(self):
        self.lock['tables'][0]['sha256']='0'*64;self.save_lock()
        p=subprocess.run([sys.executable,'-O',str(ROOT/'build_database.py'),'--lock',str(self.lock_path),'--output',str(self.output),'--pilot'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertIn('Wrong source SHA256',p.stderr);self.assertFalse(self.output.exists())
    def test_late_competing_output_is_preserved(self):
        real_link=os.link
        def compete(source,target):
            if Path(target)==self.output:self.output.write_bytes(b'other process output')
            return real_link(source,target)
        with mock.patch.object(build.os,'link',side_effect=compete):
            with self.assertRaises(FileExistsError):build.build(self.lock_path,self.output,pilot=True)
        self.assertEqual(self.output.read_bytes(),b'other process output')
    def test_nested_spill_bytes_count_toward_cap(self):
        spill=self.root/'spill';spill.mkdir();(spill/'data').write_bytes(b'12345')
        with self.assertRaisesRegex(ValueError,'Storage guard'):check_budget(spill,self.root,4,0)
    def test_truncated_download_never_publishes(self):
        table=dict(self.lock['tables'][0]);table['resolved_path']=self.root/'new.parquet';table.update(bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())
        table['url']=table['original_full_source']['url']
        response=io.BytesIO(b'a');response.status=200
        with mock.patch.object(acquire.urllib.request,'urlopen',return_value=response):
            with self.assertRaisesRegex(ValueError,'length/hash'):acquire.fetch(table,reserve=0)
        self.assertFalse(table['resolved_path'].exists())

if __name__=='__main__':unittest.main()
