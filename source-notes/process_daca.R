library(tidyverse)
library(tidylog)
library(writexl)

source("code/country_codes.R")
source("code/functions/repair_double_encoded_utf8.R")
source("code/functions/write_xlsx_by_fy.R")
source("code/functions/is_not_blank_or_redacted.R")

daca_df <-
  arrow::open_dataset("data/staging/i821d") |>
  collect() |>
  select(-form_id, -label) |>
  # remove columns that are fully blank (all NA) or fully redacted
  select(where(is_not_blank_or_redacted)) |>
  # add indicator for fully-redacted rows
  mutate(row_redacted = if_all(!c(file_original, row_original), is.na)) |>
  # C3 records store country of birth as a 5-letter code, ELIS records store
  # the full name, so map the codes and keep the names as they are.
  left_join(uscis_country_codes, by = join_by(ben_country_of_birth == code)) |>
  mutate(
    # a C3 value that the code table cannot resolve is not a country code so blank
    ben_country_of_birth = case_when(
      data_source == "ELIS" ~ repair_double_encoded_utf8(ben_country_of_birth),
      !is.na(country) ~ country,
      .default = NA_character_
    ),
    # recode gender and form type given differences across C3 and ELIS
    ben_gender = replace_values(
      ben_gender,
      "F" ~ "Female",
      "M" ~ "Male",
      "U" ~ "Unknown"
    )
  ) |>
  select(-country) |>
  # standardize unique identifier field
  rename(unique_identifier = unique_alien_id) |>
  mutate(
    unique_identifier_nona = coalesce(
      unique_identifier,
      paste0("noid_", row_number())
    )
  ) |>
  arrange(unique_identifier_nona, rec_date, file_original, row_original) |>
  mutate(
    duplicate_identifier = cumsum(coalesce(rec_date != lag(rec_date), TRUE)),
    .by = unique_identifier_nona
  ) |>
  mutate(
    duplicate_last = row_number() == n(),
    duplicate_likely = if_else(
      is.na(unique_identifier) | is.na(rec_date),
      NA,
      n() > 1L
    ),
    .by = c(unique_identifier_nona, duplicate_identifier)
  ) |>
  select(-unique_identifier_nona) |>
  mutate(
    duplicate_drop_row = coalesce(duplicate_likely, FALSE) &
      !duplicate_last
  ) |>
  relocate(file_original, row_original, .after = last_col())

# drop fully-redacted rows
nrow_pre <- nrow(daca_df)

redacted_rows <- sum(daca_df$row_redacted)

daca_df <- daca_df |>
  filter(row_redacted == FALSE) |>
  select(-row_redacted)

nrow_post <- nrow(daca_df)

stopifnot((nrow_pre - nrow_post) == redacted_rows)

# separate ELIS records and records missing unique identifier from C3 records
# create `form_type_filled_in` values for C3 records to match ELIS format
# re-concatenate data subsets and check that no rows were dropped or added
nrow_pre <- nrow(daca_df)

dat_elis_noid <- daca_df |>
  filter(data_source == "ELIS" | is.na(unique_identifier)) |>
  mutate(form_type_filled_in = form_type)

dat_c3 <- daca_df |>
  filter(data_source == "C3", !is.na(unique_identifier)) |>
  arrange(unique_identifier, decision_date) |>
  group_by(unique_identifier) |>
  mutate(
    is_approval = decision == "Approved",
    n_approvals = cumsum(is_approval),
    likely_initial = n_approvals <= 1,
  ) |>
  ungroup() |>
  mutate(
    form_type_filled_in = case_when(
      likely_initial == TRUE ~ "DACA - Initial",
      likely_initial == FALSE ~ "DACA - Renewal",
      TRUE ~ NA
    )
  ) |>
  select(-c(is_approval, n_approvals, likely_initial))

daca_df <- rbind(dat_elis_noid, dat_c3)

nrow_post <- nrow(daca_df)

stopifnot(nrow_post == nrow_pre)

rm(dat_elis_noid, dat_c3)

arrow::write_parquet(
  daca_df,
  "data/daca-latest.parquet",
  compression = "zstd"
)
haven::write_dta(daca_df, "data/daca-latest.dta")
haven::write_sav(daca_df, "data/daca-latest.sav")
write_xlsx_by_fy(daca_df, "data/daca-latest.xlsx", label = "DACA")
