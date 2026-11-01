# D-32 dashboard (simulated data)

A one-page Streamlit app that shows the simulated D-32 output. Every number is simulated (synthetic district, no real Assam data). The app does not import `src/d32`; it reads files in `results/` by path.

## Run

From the repository root (Windows), then run the app from `dashboard/` so Streamlit finds `.streamlit/config.toml`:

```
py -3 -m venv dashboard/.venv
dashboard/.venv/Scripts/python -m pip install -r dashboard/requirements.txt
cd dashboard
.venv/Scripts/python -m streamlit run app.py
```

This venv is separate from the engine `.venv`. Pinned packages: streamlit, pandas, matplotlib (see `requirements.txt`).

The light theme and colours are fixed in `dashboard/.streamlit/config.toml`, so the app must be started from `dashboard/`. Fonts (Source Serif 4, Source Sans 3) load from Google Fonts when online and fall back to Georgia and Segoe UI offline.

## Panels and what they read

Sidebar: run (v0.2 confirmatory or v0.3 post-confirmation), scenario S1-S5, replication number (the `rep` column of the file, default 1).

| Panel | Reads |
|---|---|
| Header, run label | Run choice; fixed text. The SIMULATED badge is always shown. |
| Estimated production | `replications.csv`: `E0..E3_est`, `E1..E3_lo/hi`, `truth`. Second chart: first 100 `E3_lo/E3_hi` intervals of the scenario, coloured by whether they contain `truth`. |
| Quality tiles | `replications.csv`: `n_resp/n_sel`, `n_ver/n_resp`, `undercov_hat`, `deff_factors`, `cal_failed`, and `cal_unmet_after` if the column exists (v0.3). |
| Performance across repetitions | `metrics.csv`: `rel_bias`, `rmse_t`, `coverage` with `coverage_mc_se`, `rse_empirical`, `rse_mean_estimated` for E0-E3. |
| Flag queue | No data. The engine has no event-level flags, so the panel is an honest empty state listing the design section 10 rules. |
| Run record | `config_used.json`: `pop_seed`, `master_seed`, `n_per_district`, `n_boot`, `ci_level`; replication count from `replications.csv`; the three file paths. No hash or commit is shown. |

## Notes

- The reference year and a district filter from the proposal wireframe are not shown: the files hold no year, and the data is one synthetic district.
- Coverage in the first-100 chart title is for those 100 replications only. The table gives the share over all repetitions.
- A missing file or column shows an on-screen message.
