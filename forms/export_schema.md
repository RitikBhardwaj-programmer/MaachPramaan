# Export schema (CSV columns per form)

Source: `forms/tools/list_columns.py`, read from the built `.xlsx` files. Checked against the pyxform XML, not against a real Kobo export.

**Column names.** Kobo CSV export with "include group names" on gives `group/field` (e.g. `g_listing/area_ha`). With it off you get `area_ha`. Fields outside a group have no prefix. Every export also has Kobo system columns (`_id`, `_uuid`, `_submission_time`, `meta/instanceID`, ...).

**Types.** CSV is all text. The "Cast to" column is what the estimator should parse to. `calculate` fields are exported as text even when numeric. Empty means not asked (skipped by relevance) or not entered.
Dates are `YYYY-MM-DD`. `now()` and `start`/`end` are ISO 8601 with time zone. `select_multiple` is space-separated choice codes. `geopoint` is `lat lon altitude accuracy`, space-separated. `image` is a file name, the file is a Kobo attachment.

Helper columns marked (ignore) hold raw inputs and are not for estimation.

## d32_harvest_diary (one row = one harvest event)

| Column | XLSForm type | Cast to | Values / notes |
|---|---|---|---|
| `event_id` | calculate `once(uuid())` | string (36 chars) | Key. De-duplicate on this |
| `unit_id` | text | string | Frame ID |
| `harvest_date` | date | date | Not in future, not before reference year start |
| `harvest_type` | select_one | string | `partial`, `final` |
| `species_group` | select_one | string | `imc`, `exotic`, `catfish`, `prawn`, `mixed`, `other` |
| `quantity_kg` | decimal | float | > 0 |
| `disposal_mode` | select_one | string | `all_sold`, `all_home`, `split` |
| `g_split/in_kg_sold` ... `in_kg_other` (5) | decimal | (ignore) | Raw inputs, only when `split` |
| `kg_sold`, `kg_home`, `kg_gift`, `kg_labour`, `kg_other` | calculate | float | Always filled. Sum is within 1 kg of `quantity_kg` |
| `price_per_kg` | decimal | float | Optional. Asked only if `kg_sold` > 0 |
| `g_recorder/source` | select_one | string | `diary`, `monthly_check`, `verified`, `recall` (default `diary`) |
| `g_recorder/recorder` | select_one | string | `farmer`, `helper`, `enumerator` (default `farmer`) |
| `g_recorder/gps` | geopoint | string | Optional |
| `device_time` | calculate `now()` | datetime | Phone clock when last computed |

## d32_listing (one row = one listing interview)

| Column | XLSForm type | Cast to | Values / notes |
|---|---|---|---|
| `start`, `end` | start, end | datetime | |
| `today` | today | date | |
| `enumerator_id` | text | string | |
| `unit_id` | text | string | Frame ID |
| `consent` | select_one | string | `yes`, `no`. If `no`, all `g_listing/*` are empty |
| `g_listing/district`, `g_listing/block`, `g_listing/village` | text | string | |
| `g_listing/type` | select_one | string | `pond`, `tank` |
| `g_listing/area_ha` | decimal | float | > 0 |
| `g_listing/gps` | geopoint | string | |
| `g_listing/operator_name`, `g_listing/operator_phone` | text | string | Personal data |
| `g_listing/species_groups` | select_multiple | space list | `imc`, `exotic`, `catfish`, `prawn`, `other` |
| `g_listing/species_other` | text | string | If `other` selected |
| `g_listing/stocking_date` | date | date | Not in future |
| `g_listing/seed_qty` | integer | int | >= 0 |
| `g_listing/feeding_practice` | select_one | string | `none`, `supplementary`, `formulated` |
| `g_listing/phase2_flag` | select_one | string | `yes`, `no`, or empty |

## d32_verification (one row = one verified event)

| Column | XLSForm type | Cast to | Values / notes |
|---|---|---|---|
| `start`, `end`, `today`, `enumerator_id` | as above | | |
| `event_id_scan` | barcode | string | (ignore) optional scan |
| `event_id_typed` | text | string | (ignore) |
| `event_id` | calculate | string | Join key to the diary `event_id` |
| `unit_id` | text | string | |
| `scale_id` | text | string | |
| `scale_calibration_date` | date | date | |
| `method` | select_one | string | `weighed`, `crates` |
| `g_weighed/weighed_kg` | decimal | float | If `weighed` |
| `g_weighed/scale_photo` | image | file name | If `weighed` |
| `g_crates/crate_count` | integer | int | If `crates` |
| `g_crates/kg_per_crate` | decimal | float | Full crate weight, with crate |
| `g_crates/tare_kg` | decimal | float | Empty crate weight |
| `g_crates/crate_net_kg` | calculate | float | count x (full - tare) |
| `verified_kg` | calculate | float | Weighed, or crate net. Use this one |
| `farmer_stated_kg` | decimal | float | > 0 |
| `rel_diff` | calculate | float | abs(stated - verified) / verified. Flag when > 0.5 |
| `rel_diff_pct` | calculate | float | Rounded percent (display) |
| `gps` | geopoint | string | |
| `notes` | text | string | |

## d32_recall (one row = one unit interview)

| Column | XLSForm type | Cast to | Values / notes |
|---|---|---|---|
| `start`, `end`, `today`, `enumerator_id` | as above | | |
| `on_list` | select_one | string | `yes`, `no` |
| `unit_id` | text | string | Only if `on_list` = `yes` |
| `g_notonlist/provisional_id` | calculate | string | `NOL-` + 7 chars; made for every row, use only if `no` |
| `g_notonlist/area_cell_id` | text | string | If `no` |
| `g_notonlist/gps` | geopoint | string | If `no` |
| `g_notonlist/area_ha` | decimal | float | If `no`, > 0 |
| `unit_key` | calculate | string | `unit_id` if on list, else `provisional_id`. Use as the key |
| `total_harvest_kg` | decimal | float | >= 0 |
| `n_harvests` | integer | int | >= 0 |
| `share_self_consumed_pct` | integer | int | 0 to 100 |
| `diary_completed` | select_one | string | `yes`, `no`. Only if on list |
| `dropout_reason` | select_one | string | `no_time`, `difficult`, `phone`, `no_harvest`, `lost_interest`, `sold_unit`, `other` |
| `dropout_reason_other` | text | string | If `other` |
| `notes` | text | string | |

## d32_monthly_check (one row = one unit-month check)

| Column | XLSForm type | Cast to | Values / notes |
|---|---|---|---|
| `start`, `end`, `today`, `enumerator_id` | as above | | |
| `unit_id` | text | string | |
| `month` | date (month-year) | date | First day of the month, `YYYY-MM-01` |
| `visit_mode` | select_one | string | `visit`, `call` |
| `any_harvest` | select_one | string | `yes`, `no` |
| `g_harvest/n_happened` | integer | int | If `yes`, >= 1 |
| `g_harvest/n_in_diary` | integer | int | If `yes`, >= 0 |
| `g_harvest/n_missing` | calculate | int | happened - in diary. > 0 means missed events |
| `notes` | text | string | |
