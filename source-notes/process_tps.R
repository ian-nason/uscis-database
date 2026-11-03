library(tidyverse)
library(tidylog)
library(writexl)

source("code/country_codes.R")
source("code/functions/repair_double_encoded_utf8.R")
source("code/functions/write_xlsx_by_fy.R")
source("code/functions/is_not_blank_or_redacted.R")

tps_df <-
  arrow::open_dataset("data/staging/i821") |>
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
      .default = "Unlisted Entry (Any foreign country not listed)"
    ),
    # recode gender and form type given differences across C3 and ELIS
    ben_gender = replace_values(
      ben_gender,
      "F" ~ "Female",
      "M" ~ "Male",
      "U" ~ "Unknown"
    ),
    form_type = replace_values(
      form_type,
      "This is my annual registration/re-registration application" ~ "TPS - Re-registration",
      "This is my first application" ~ "TPS - Initial"
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
  arrange(
    unique_identifier_nona,
    rec_date,
    decision_date,
    file_original,
    row_original
  ) |>
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
  relocate(row_redacted, file_original, row_original, .after = last_col())

# drop fully-redacted rows
nrow_pre <- nrow(tps_df)

redacted_rows <- sum(tps_df$row_redacted)

tps_df <- tps_df |>
  filter(row_redacted == FALSE) |>
  select(-row_redacted)

nrow_post <- nrow(tps_df)

stopifnot((nrow_pre - nrow_post) == redacted_rows)

arrow::write_parquet(tps_df, "data/tps-latest.parquet", compression = "zstd")

haven::write_dta(tps_df, "data/tps-latest.dta")
haven::write_sav(tps_df, "data/tps-latest.sav")
write_xlsx_by_fy(tps_df, "data/tps-latest.xlsx", label = "TPS")
