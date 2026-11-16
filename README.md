# USCIS DACA and TPS applications in DuckDB

Application records for Deferred Action for Childhood Arrivals (DACA) and Temporary Protected Status (TPS), released by USCIS and processed by the Deportation Data Project. The snapshot contains 4,526,373 DACA and 6,680,172 TPS application records, with observations through February 2026. Use it to study recorded applications and administrative outcomes. Applicants can appear repeatedly; approvals do not identify unique people or current beneficiaries, and source duplicate flags and reconstruction limits require explicit treatment.

## Start querying

Count DACA application records by source system. These are applications, not unique applicants or current beneficiaries; duplicate recommendations remain in the data.

`data_source` identifies the USCIS case-management source system: C3 (also called CLAIMS3) or ELIS. `application_rows` is the number of records in each system. This query returns 1,326,378 C3 rows and 3,199,995 ELIS rows in the DACA table.

Choose R or Python. Install datapond once: use `install.packages("datapond")` in R, or run `python -m pip install datapond` in a terminal.

### R

```r
library(datapond)
con <- dp_connect("uscis")
tryCatch({
  DBI::dbExecute(con, "SET threads=1")
  DBI::dbExecute(con, "SET memory_limit='128MiB'")
  DBI::dbExecute(con, "SET max_temp_directory_size='0B'")
  print(DBI::dbGetQuery(con, "SELECT data_source,count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source"))
}, finally = dp_disconnect(con))
```

### Python

```python
import datapond
con = datapond.connect('uscis')
try:
    con.execute("SET threads=1")
    con.execute("SET memory_limit='128MiB'")
    con.execute("SET max_temp_directory_size='0B'")
    print(con.execute("""SELECT data_source,count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source""").fetchall())
finally:
    con.close()
```

Queries run on your computer and read the byte ranges they need. A small result can still require a large scan. These examples limit DuckDB to one thread and a 128 MiB buffer pool with disk spill disabled; that is not a limit on the entire R or Python process. Larger analyses may need more memory or a local download with enough disk space.

<a id="coverage-fields-and-sources"></a>
<a id="additional-dataset-notes"></a>

## Tables, fields and joins

The two tables contain **11,206,545 application records**. The `uscis` identifier is available in the live Datapond catalog; direct download and local queries are also available.

See the [data dictionary](https://huggingface.co/datasets/Nason/uscis-database/resolve/db5d5bfed09d433c09f13a3b8bfbef8f5f4c9481/DICTIONARY.md) for column definitions.

| Table | Application records | Original source fields |
| --- | ---: | ---: |
| `daca_applications` | 4,526,373 | 31 |
| `tps_applications` | 6,680,172 | 30 |

Both tables retain applicant identifiers and demographics; form and application-status fields; receipt, decision and notice dates; processing office and source system; duplicate flags; and original-file/row references. DACA adds the reconstructed `form_type_filled_in` field. See [DICTIONARY.md](DICTIONARY.md) for all 63 table-specific stored fields, including the added ordinal in each table, and exact missing counts.

Every original row, field, NULL and duplicate flag is retained. `_source_row` is a one-based ordinal within this exact processed table, not a stable person or application identifier. There is no verified cross-form, cross-release, ICE or EOIR identity link.

## Interpretation

### Repeated applications and duplicate flags

Applicants can have multiple applications and repeated administrative records. Approved application rows do not establish how many people currently hold DACA or TPS.

| Full-source measurement | DACA | TPS |
| --- | ---: | ---: |
| `duplicate_drop_row = true`, retained | 149 | 2,603 |
| Missing applicant identifier | 19,135 | 604 |
| Unknown `duplicate_likely` flag | 19,135 | 612 |
| Missing receipt date | 0 | 8 |
| Decision date before receipt date, retained | 15,853 | 297,594 |

Unknown duplicate flags are not false flags. Publisher duplicate recommendations are preserved, with no automatic deduplication.

The historical manifest key `null_duplicate_flags` counts only NULL `duplicate_drop_row`; its value zero does not contradict the 19,135/612 unknown `duplicate_likely` values in `null_counts`. A false drop flag on these unknown rows comes from coalescing, not verified absence of duplicates.

### Reconstructed form type

DACA `form_type_filled_in` copies `form_type` for ELIS and missing-ID rows; only C3 rows with an ID are reconstructed. Their cumulative approval count, ordered by decision date and including the current row, labels counts at most one Initial and larger counts Renewal (unknown counts stay NULL). Duplicate approvals count; denied/pending renewals after a first approval can be labelled Initial. See the field guide for the exact rule and limits.

### Source-system differences

C3/CLAIMS3 and ELIS are case-management source systems. Source systems differ in status labels, coverage and missingness.

The publisher removes fully redacted rows and entirely blank/redacted columns, repairs ELIS UTF-8, harmonizes gender labels and TPS form-type labels, and adds duplicate flags and DACA reconstruction. This importer preserves that processed output; it does not reconstruct excluded agency records.

### Geography limitations

Country of birth and processing offices do not provide residence geography. TPS maps failed C3 country-code lookups to `Unlisted Entry (Any foreign country not listed)`, so stored NULL counts do not capture all underlying missingness; DACA uses NULL for failed C3 lookups.

### Date limitations

Unusual dates, including early LPR dates, remain uncorrected; assess them before calculating durations or cohort outcomes.

The November 3 UTC build date is not a newer observation period than February 2026. Build/download timestamps, snapshot status, receipt dates and decision dates have different meanings. [FIELD-GUIDE.md](FIELD-GUIDE.md) explains these limits.

<a id="advanced-access-python-and-r-queries"></a>
<a id="snapshot-files-and-datapond-clients"></a>

## Other ways to connect

[Download the database](https://huggingface.co/datasets/Nason/uscis-database/resolve/main/uscis.duckdb), [browse its versioned files](https://huggingface.co/datasets/Nason/uscis-database/tree/main), or inspect the [source repository](https://github.com/ian-nason/uscis-database).

The first-use examples above use the live catalog. The downloaded snapshot also supports local queries.

### Local DuckDB queries

After downloading the audited `uscis.duckdb` snapshot, query it locally:

```python
import duckdb
con = duckdb.connect("uscis.duckdb", read_only=True,
                     config={"threads": "1", "memory_limit": "128 MiB"})
try:
    print(con.sql("SELECT data_source, count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source").fetchall())
finally:
    con.close()
```

```r
library(DBI)
con <- dbConnect(duckdb::duckdb(), dbdir="uscis.duckdb", read_only=TRUE)
tryCatch({
  dbExecute(con, "SET threads=1")
  dbExecute(con, "SET memory_limit='128 MiB'")
  print(dbGetQuery(con, "SELECT data_source, count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source"))
}, finally=dbDisconnect(con, shutdown=TRUE))
```

### Additional catalog connection examples

The first query above is the recommended package start. These retained alternatives run the same question through the live catalog.

```python
import datapond
con = datapond.connect("uscis")
try:
    print(con.sql("SELECT data_source, count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source").fetchall())
finally:
    con.close()
```

```r
library(datapond)
con <- dp_connect("uscis")
tryCatch(print(DBI::dbGetQuery(con, "SELECT data_source, count(*) AS application_rows FROM daca_applications GROUP BY data_source ORDER BY data_source")), finally=dp_disconnect(con))
```

## Sources and maintenance

### Provenance and license

Source: [Deportation Data Project (public records and FOIA)](https://deportationdata.org/data/processed/uscis.html). License: CC0-1.0 data.

The publisher repository is pinned to commit `dfe86ad18fd04ed6ed8281366d8bfb9c56716c1b`. Both complete Parquet files matched their immutable URLs, full SHA256 hashes and combined 208,298,935 bytes before ingestion. [source-lock.json](source-lock.json) records all pins, source schemas and exact NULL baselines; [uscis.manifest.json](uscis.manifest.json) records the full build and measurements. The processed record counts come from actual pinned files, rather than rounded release-announcement totals.

Sources: [publisher catalog](https://deportationdata.org/data/processed/uscis.html), [codebook](https://deportationdata.org/docs/uscis/codebook-processed.html), and [pinned source repository](https://github.com/deportationdata/uscis/tree/dfe86ad18fd04ed6ed8281366d8bfb9c56716c1b). The processed data are distributed under CC0-1.0; the publisher's text is retained in [LICENSE-DATA](LICENSE-DATA). Cite USCIS data processed by the Deportation Data Project, this source commit and the snapshot date. Updates depend on FOIA releases; no fixed monthly cadence is promised.

The full database is 391,131,136 bytes. SHA256: `e0957fb5726b990f694b08c86c0bf8f1d785a5b41d5ad5079ecaac2dfe5a2f9f`. It includes `_metadata`, `_columns` and `_provenance`. The full build and released Python/R client checks have passed.

Verify the full SHA256 recorded above. The catalog PR pins an immutable HF revision; `main` can later refer to a newer snapshot.

### Client checks

Both released Datapond clients passed the same query and full counts via a temporary loopback registry: Python Datapond 0.1.5/DuckDB 1.5.6 and R Datapond 0.1.0/DuckDB 1.5.5. Those smoke scripts use a temporary test registry. The public `uscis` catalog entry is now available, and the first-use examples above connect through that live catalog.

The retained build smoke scripts use an isolated registry with the same full database.

### Reproduce and refresh

Clone the [source repository](https://github.com/ian-nason/uscis-database) for build scripts and offline fixtures. Use Python 3.11+ and the pinned `duckdb==1.5.6` dependency. No Arrow, spatial extension or credentials are required for ingestion.

```sh
python -m pip install -r requirements.txt
python acquire_sources.py
python acquire_sources.py --download
python build_database.py --lock source-lock.json --output output/uscis.duckdb
```

The build uses one thread, 2 GiB DuckDB memory, a 4 GiB spill cap within its private workspace, an 8 GiB work cap and a 2 GiB free-space reserve. Initial acquisition/build preflight requires about 10.2 GiB free. Existing verified sources are reused. Outputs, WALs and manifests are never overwritten; use a new output path. The filesystem must support atomic hard links. Failed work is retained for inspection. The successful work directory retains a hard link to the output. Rebuilds have new `_metadata.built_at` timestamps and need not have the same file SHA256; compare source pins, schemas and all typed row values. The published checksum identifies the distributed artifact. The measured full build took about 99 seconds with sampled peak process RSS about 1.34 GiB; these observations are not guaranteed peak bounds on other machines.

The importer verifies complete source hashes, schemas, row counts, every typed source value and ordinal in bounded batches, exact NULL baselines and the publisher's duplicate-flag relationship. Missing IDs, source-key duplication and date anomalies are reported without silent repair. [VALIDATION.md](VALIDATION.md) distinguishes full execution, independent review and client checks. [CLOUD-HANDOFF.md](CLOUD-HANDOFF.md) documents the bounded workflow and included pilot fixtures.

To refresh, select a new immutable publisher commit, update the complete source pins and expected schema/NULL counts, inspect processing-code changes, and repeat the build, field checks, Python/R queries and independent audits. No automatic refresh or current legal-status inference is supplied.
