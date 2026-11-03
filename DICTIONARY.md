# USCIS application field dictionary

The full-source row counts and exact NULL counts below were verified against both pinned Parquet footers and the completed 11,206,545-row build. They are not pilot measurements.

Source commit: `dfe86ad18fd04ed6ed8281366d8bfb9c56716c1b`. Source types are preserved; `_source_row` is added. Exact missing counts avoid rounding small nonzero missingness to zero. These are stored processed-source NULL counts; upstream recoding can hide missing original values, especially TPS country of birth.

[Publisher codebook](https://deportationdata.org/docs/uscis/codebook-processed.html) and [source catalog](https://deportationdata.org/data/processed/uscis.html). See FIELD-GUIDE.md for unit, duplicate, time, and linkage limits.

## daca_applications

4,526,373 application records; 31 source fields plus `_source_row`.

| Field | DuckDB type | Source NULL count | Definition |
| --- | --- | ---: | --- |
| `_source_row` | BIGINT | 0 | One-based ordinal in the pinned processed Parquet; added without dropping source rows. Unique only within this table and source commit; not an applicant or application identifier across releases. |
| `unique_identifier` | VARCHAR | 19,135 | Agency-redacted/pseudonymous applicant identifier provided in the source; it may repeat across applications. Not a unique application key. Cross-form, cross-release and EOIR/ICE linkage is not established by this importer. |
| `ben_year_of_birth` | INTEGER | 1,326,379 | Applicant year of birth reported by the source; integer, with source missingness retained. |
| `ben_country_of_birth` | VARCHAR | 52 | Applicant birthplace, not residence. The publisher maps C3 codes to names: failed lookups become NULL in DACA but Unlisted Entry (Any foreign country not listed) in TPS. That TPS category can conflate unresolved/invalid/missing original codes; stored NULL counts do not measure all underlying missingness. ELIS names are retained after publisher UTF-8 repair. |
| `immigration_status` | VARCHAR | 3,685,368 | Original source immigration-status field. Values are retained without inferring current lawful status. |
| `classification` | VARCHAR | 3,520,717 | Original source classification field; interpret with the USCIS source documentation rather than a newly invented category mapping. |
| `form_number` | VARCHAR | 0 | Application form designation: the tables separately cover DACA I-821D and TPS I-821. |
| `form_type` | VARCHAR | 1,291,563 | Source-reported initial/renewal/re-registration form type where available. Legacy-system missingness remains. |
| `latest_trvl_depart_yr` | INTEGER | 4,410,604 | Year of the latest travel departure reported in the source; not a complete travel history. |
| `latest_trvl_return_yr` | INTEGER | 4,409,873 | Year of the latest travel return reported in the source; not a complete travel history. |
| `status` | VARCHAR | 0 | Application/case status recorded in the source snapshot; not necessarily final disposition or current beneficiary status. |
| `status_date` | DATE | 0 | Source date associated with the recorded status; preserved as DATE. |
| `uscis_field_office` | VARCHAR | 3,199,992 | Processing field-office label. It does not identify applicant residence. Do not substitute ICE offices/AORs or infer residence geography from this USCIS processing office. |
| `uscis_service_center` | VARCHAR | 0 | Processing service-center label; not applicant residence geography. |
| `data_source` | VARCHAR | 0 | USCIS case-management source system, such as C3/CLAIMS3 or ELIS. Fields and missingness vary across systems. |
| `lpr_date` | DATE | 4,497,090 | Source lawful-permanent-residence date field, where reported; not a complete longitudinal status history. |
| `ben_gender` | VARCHAR | 3 | Source gender field after publisher harmonization of legacy codes; labels and missingness are retained. |
| `rec_date` | DATE | 0 | Application receipt date reported by USCIS; source duplicate groups use applicant and this date. |
| `decision_date` | DATE | 0 | Application decision date in the source; any date-order anomalies are reported and retained. |
| `decision` | VARCHAR | 0 | Source decision label; no independent recoding of approval/denial or beneficiary status. |
| `latest_notice_type` | VARCHAR | 1,361,660 | Most recent source notice-type label; not a complete notice history. |
| `latest_notice_date` | DATE | 1,361,660 | Date associated with the most recent source notice. |
| `latest_rfe_date` | DATE | 4,212,205 | Most recent request-for-evidence date reported in the source. |
| `latest_noid_date` | DATE | 4,509,780 | Most recent notice-of-intent-to-deny date reported in the source. |
| `g28_flag` | VARCHAR | 0 | Original source G-28 representation flag; retained as text, without inferring complete attorney coverage. |
| `duplicate_identifier` | INTEGER | 0 | Publisher's receipt-date group counter within an applicant grouping; not globally unique. Interpret with applicant identifier/source scope; _source_row identifies a stored row. |
| `duplicate_last` | BOOLEAN | 0 | Last row within the publisher's applicant/receipt-date group. DACA sorts applicant (with a unique placeholder for each missing ID), receipt date, file_original, row_original; TPS additionally sorts decision_date before file_original/row_original. Later DACA reconstruction reorders rows, so physical _source_row does not reconstruct this flag. |
| `duplicate_likely` | BOOLEAN | 19,135 | Publisher's likely-duplicate flag for repeated applicant/receipt-date groups; NULL when applicant ID or receipt date is missing. |
| `duplicate_drop_row` | BOOLEAN | 0 | Publisher recommendation: coalesce(duplicate_likely,FALSE) AND NOT duplicate_last. Every row is retained. On unknown duplicate_likely rows this flag is false because of coalescing, not verified absence of duplication. |
| `file_original` | VARCHAR | 0 | Original agency input-file identifier retained by the publisher. Pair with row_original and table/source commit. This pair is nonmissing and unique in both full pinned tables; no stability across releases is established. |
| `row_original` | INTEGER | 0 | Row number in the original agency input file, distinct from _source_row in the processed Parquet. Pair with file_original and table/source commit; the pair is nonmissing and unique in this snapshot, not a persistent application or person ID. |
| `form_type_filled_in` | VARCHAR | 5 | DACA: copies form_type for ELIS rows and every row with a missing applicant ID. Only C3 rows with a nonmissing ID are reconstructed: within applicant, ordered by decision_date, cumulative approvals including the current row give DACA - Initial when at most one, otherwise DACA - Renewal; an unknown cumulative count gives NULL. Duplicate approvals count, and a denied/pending renewal after the first approval can still be labelled Initial. This is not a uniformly observed or uniformly imputed field. |

## tps_applications

6,680,172 application records; 30 source fields plus `_source_row`.

| Field | DuckDB type | Source NULL count | Definition |
| --- | --- | ---: | --- |
| `_source_row` | BIGINT | 0 | One-based ordinal in the pinned processed Parquet; added without dropping source rows. Unique only within this table and source commit; not an applicant or application identifier across releases. |
| `unique_identifier` | VARCHAR | 604 | Agency-redacted/pseudonymous applicant identifier provided in the source; it may repeat across applications. Not a unique application key. Cross-form, cross-release and EOIR/ICE linkage is not established by this importer. |
| `ben_year_of_birth` | INTEGER | 3,402,411 | Applicant year of birth reported by the source; integer, with source missingness retained. |
| `ben_country_of_birth` | VARCHAR | 2,637 | Applicant birthplace, not residence. The publisher maps C3 codes to names: failed lookups become NULL in DACA but Unlisted Entry (Any foreign country not listed) in TPS. That TPS category can conflate unresolved/invalid/missing original codes; stored NULL counts do not measure all underlying missingness. ELIS names are retained after publisher UTF-8 repair. |
| `immigration_status` | VARCHAR | 1,241,049 | Original source immigration-status field. Values are retained without inferring current lawful status. |
| `classification` | VARCHAR | 6,679,951 | Original source classification field; interpret with the USCIS source documentation rather than a newly invented category mapping. |
| `form_number` | VARCHAR | 0 | Application form designation: the tables separately cover DACA I-821D and TPS I-821. |
| `form_type` | VARCHAR | 5,801 | Source-reported initial/renewal/re-registration form type where available. Legacy-system missingness remains. |
| `latest_trvl_depart_yr` | INTEGER | 6,680,148 | Year of the latest travel departure reported in the source; not a complete travel history. |
| `latest_trvl_return_yr` | INTEGER | 6,680,148 | Year of the latest travel return reported in the source; not a complete travel history. |
| `status` | VARCHAR | 0 | Application/case status recorded in the source snapshot; not necessarily final disposition or current beneficiary status. |
| `status_date` | DATE | 0 | Source date associated with the recorded status; preserved as DATE. |
| `uscis_field_office` | VARCHAR | 3,277,763 | Processing field-office label. It does not identify applicant residence. Do not substitute ICE offices/AORs or infer residence geography from this USCIS processing office. |
| `uscis_service_center` | VARCHAR | 0 | Processing service-center label; not applicant residence geography. |
| `data_source` | VARCHAR | 0 | USCIS case-management source system, such as C3/CLAIMS3 or ELIS. Fields and missingness vary across systems. |
| `lpr_date` | DATE | 6,671,621 | Source lawful-permanent-residence date field, where reported; not a complete longitudinal status history. |
| `ben_gender` | VARCHAR | 3,635 | Source gender field after publisher harmonization of legacy codes; labels and missingness are retained. |
| `rec_date` | DATE | 8 | Application receipt date reported by USCIS; source duplicate groups use applicant and this date. |
| `decision_date` | DATE | 0 | Application decision date in the source; any date-order anomalies are reported and retained. |
| `decision` | VARCHAR | 0 | Source decision label; no independent recoding of approval/denial or beneficiary status. |
| `latest_notice_type` | VARCHAR | 3,582,645 | Most recent source notice-type label; not a complete notice history. |
| `latest_notice_date` | DATE | 3,582,645 | Date associated with the most recent source notice. |
| `latest_rfe_date` | DATE | 6,372,823 | Most recent request-for-evidence date reported in the source. |
| `latest_noid_date` | DATE | 6,520,974 | Most recent notice-of-intent-to-deny date reported in the source. |
| `g28_flag` | VARCHAR | 0 | Original source G-28 representation flag; retained as text, without inferring complete attorney coverage. |
| `duplicate_identifier` | INTEGER | 0 | Publisher's receipt-date group counter within an applicant grouping; not globally unique. Interpret with applicant identifier/source scope; _source_row identifies a stored row. |
| `duplicate_last` | BOOLEAN | 0 | Last row within the publisher's applicant/receipt-date group. DACA sorts applicant (with a unique placeholder for each missing ID), receipt date, file_original, row_original; TPS additionally sorts decision_date before file_original/row_original. Later DACA reconstruction reorders rows, so physical _source_row does not reconstruct this flag. |
| `duplicate_likely` | BOOLEAN | 612 | Publisher's likely-duplicate flag for repeated applicant/receipt-date groups; NULL when applicant ID or receipt date is missing. |
| `duplicate_drop_row` | BOOLEAN | 0 | Publisher recommendation: coalesce(duplicate_likely,FALSE) AND NOT duplicate_last. Every row is retained. On unknown duplicate_likely rows this flag is false because of coalescing, not verified absence of duplication. |
| `file_original` | VARCHAR | 0 | Original agency input-file identifier retained by the publisher. Pair with row_original and table/source commit. This pair is nonmissing and unique in both full pinned tables; no stability across releases is established. |
| `row_original` | INTEGER | 0 | Row number in the original agency input file, distinct from _source_row in the processed Parquet. Pair with file_original and table/source commit; the pair is nonmissing and unique in this snapshot, not a persistent application or person ID. |

## Embedded metadata

`_metadata` records table descriptions and source/licensing. `_columns` records types, definitions, join caveats, and exact NULL counts with percentages. Example values are intentionally unset. `_provenance` records actual input hashes, sizes, source commit and pilot scope. Pilot inputs use `local-pilot:` URLs; `original_full_source_url` and `expected_full_source_sha256` identify the original full file separately, without claiming that its full bytes were verified by the pilot.

`_source_row` is a one-based physical ordinal in this exact processed file, not a stable person or application identifier.
