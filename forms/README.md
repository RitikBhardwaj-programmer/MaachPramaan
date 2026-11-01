> **WARNING: the Assamese text is machine-drafted.** A native Assamese speaker must check every label, hint and message before any field use. Wrong wording in a survey form changes the data. Keep the English label next to the Assamese one while the check runs.

# D-32 field forms (XLSForm)

Five offline XLSForms for KoboToolbox and ODK Collect. They follow `docs/design.md` sections 2 (definitions), 7 (measurement), 9 (dropout reasons), 10 (plausibility: flag, never overwrite) and 13 (audit).

The `.xlsx` files are generated from code. Do not edit them by hand. Edit `tools/build_forms.py` and rebuild.

| Form | `form_id` | Who | Design reference |
|---|---|---|---|
| `d32_listing.xlsx` | `d32_listing` | Enumerator, start of year | 7.1 Listing schedule; 2 (area, type) |
| `d32_harvest_diary.xlsx` | `d32_harvest_diary` | Farmer or helper, one submission per harvest event | 7.2 Harvest event record; 2 (harvest event) |
| `d32_verification.xlsx` | `d32_verification` | Enumerator at a phase-2 harvest | 7.1, 7.3 Verification; 10 Diary vs verified |
| `d32_recall.xlsx` | `d32_recall` | Enumerator, after the year ends | 7.1, 7.4 Recall and not-on-list interview; 3.4; 9 (dropout reason) |
| `d32_monthly_check.xlsx` | `d32_monthly_check` | Enumerator, monthly | 7.1 Monthly check (finds missed events) |

All forms have `form_title`, `form_id`, `version` (date string, now `2026-11-01`) and `default_language` English. Labels, hints and messages are in English and Assamese.

## Design choices you should know

- **Soft warnings are notes, not blocks.** ODK has no soft constraint. A warning is a `note` that appears when the value looks wrong (area above 20 ha, one harvest above 2000 kg, diary vs verified above 50%, missing diary events, odd phone or event code). The user can always continue. This follows design section 10.
- **Hard constraints only where the value is impossible:** area or quantity not above 0, negative counts, dates in the future, a harvest date before the reference year start, a percent outside 0 to 100, and disposal parts that do not add up to the total (tolerance 1 kg).
- **Reference year start** is one parameter: `--ref-year-start` (default `2026-04-01`, assumption A1 in the design). Set the real pilot year before you build the final forms. Used by the harvest date and monthly check constraints.
- **Harvest diary idempotency.** `event_id = once(uuid())` is made once on the phone. Kobo itself de-duplicates on its own `_uuid` / `meta/instanceID`, not on `event_id`. The estimator must also drop duplicate `event_id` rows.
- **Diary shortcut.** "All sold" and "All used at home" need no kg fields. Only "Divided in parts" opens five kg fields. The `kg_*` columns are filled for every row.
- **Consent (listing).** If consent is "no", the rest of the form is hidden and the refusal is still submitted. This keeps refusals countable.

## Rebuild and check

From the project root (Windows):

```
forms\.venv\Scripts\python.exe forms\tools\build_forms.py [--ref-year-start 2026-04-01] [--version 2026-11-01]
forms\.venv\Scripts\python.exe forms\tools\validate_forms.py
forms\.venv\Scripts\python.exe forms\tools\list_columns.py
```

`validate_forms.py` converts each form with pyxform and runs ODK Validate. It does not use `xls2xform` for validation because pyxform 4.5.0 starts Java with an empty environment on Windows, and Java crashes (exit code 0xC0000409). The script runs the same bundled jar with the normal environment. The setup is `py -3 -m venv forms/.venv` plus `pip install pyxform openpyxl`.

## Export columns the estimator reads

Full list with types: `export_schema.md`. The main ones:

- **Harvest diary:** `event_id`, `unit_id`, `harvest_date`, `quantity_kg`, `g_recorder/source`, and the disposal parts `kg_sold`, `kg_home`, `kg_gift`, `kg_labour`, `kg_other`. Also `species_group`, `harvest_type`, `price_per_kg`, `g_recorder/recorder`, `device_time`.
- **Verification:** `event_id`, `unit_id`, `verified_kg`, `farmer_stated_kg`, `rel_diff`.
- **Recall:** `unit_key`, `on_list`, `total_harvest_kg`, `n_harvests`, `share_self_consumed_pct`, `diary_completed`, `dropout_reason`.
- **Monthly check:** `unit_id`, `month`, `any_harvest`, `g_harvest/n_happened`, `g_harvest/n_in_diary`.
- **Listing:** `unit_id`, `consent`, `g_listing/area_ha`, `g_listing/type`, `g_listing/phase2_flag`.

## Upload to KoboToolbox

1. Sign in to KoboToolbox (or your server). Choose **New project**, then **Upload an XLSForm**.
2. Select the `.xlsx` file. Kobo reads the `settings` sheet for title, `form_id` and version.
3. Open the project, fix any warning Kobo shows, then **Deploy**.
4. On each phone, install KoboCollect (or ODK Collect), point it at the server, and download the blank form once while online. After that the form works offline.
5. Submissions sync when the phone has network. Export as CSV from **Data > Downloads**. Keep the **group names in headers** option on, with the `/` separator, to get the column names in `export_schema.md`. With it off you get the bare names.

For ODK Collect with ODK Central, upload the same `.xlsx` as a form definition.

## Known limitations

- Assamese is machine-drafted and unchecked (see the warning at the top).
- Not run on a real phone, Kobo server or ODK Collect. The five forms pass pyxform conversion and ODK Validate only.
- `unit_id` is typed (checked only for non-empty, no spaces). There is no frame-based lookup, because no frame file exists yet. When the frame exists, a CSV lookup with `pulldata()` can fill district, block, village, type and the phase-2 flag.
- `phase2_flag` is entered by the enumerator, not preloaded.
- `calculate` fields are exported as text. The estimator must cast them (`device_time`, `rel_diff`, `kg_*`).
- Species group in the diary has one extra choice, `mixed`, for a harvest with several groups in one event. Design 7.2 has one species group per event.
- Crate method: net weight = crate count x (full crate weight - empty crate weight). The brief said "count x kg per crate - tare". I read this as tare per crate. Confirm.
- The verification form compares the *farmer-stated* quantity with the verified one on the phone. The diary quantity is not available offline. The exact diary vs verified check (design 10) joins on `event_id` in the estimator.
- The diary shows the event code as a note so the enumerator can type it into the verification form. There is no QR code on the diary form.
- The 12-month calibration warning and the dropout reason list are my drafts; the design does not define them.
- No consent question in the recall form for a not-on-list unit. Add one if the ethics process needs it.
