"""D-32 dashboard: shows the SIMULATED output of the D-32 survey engine.

Reads CSV and JSON files from results/ by path. Does not import src/d32.
"""
import html
import io
import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

RESULTS = Path(__file__).resolve().parent.parent / "results"

RUNS = {
    "v0.2": {
        "label": "v0.2 confirmatory",
        "about": "Confirmatory run of design v0.2. Nothing was tuned on its seeds.",
        "dir": RESULTS / "v0.2",
    },
    "v0.3": {
        "label": "v0.3 post-confirmation",
        "about": "Follow-up check of design v0.3 with a new calibration rule. Not confirmatory.",
        "dir": RESULTS / "v0.3",
    },
}

SCENARIOS = {
    "S1": "Base case",
    "S2": "Noisier diary (rho 0.7)",
    "S3": "Diary bias, assisted -5%, not assisted -20%",
    "S4": "Dropout more likely in low-production years",
    "S5": "Only 75% of phase-2 harvests verified",
}

PAPER, INK, WATER, SILT, GAMOSA, MUTED = "#F6F7F4", "#15232B", "#1D6A73", "#B9770E", "#A8201A", "#7A8C99"

FLAG_RULES = [
    "Yield outlier: modified z-score on log(production / area) within stratum, flagged when |M| is above 3.5 (pond-year).",
    "Event size: one event far above the stratum median event size per hectare (event).",
    "Seed consistency: production above what the stocked seed could produce (pond-year).",
    "Duplicate: same unit, same day, same quantity within 5% (event).",
    "Diary against verified: phase-2 units where the diary differs from the verified value by more than 50% (event).",
]

plt.rcParams.update({
    "font.family": ["Source Sans 3", "Segoe UI", "DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.edgecolor": INK, "figure.facecolor": PAPER, "axes.facecolor": PAPER,
})

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600&family=Source+Serif+4:wght@400;600&display=swap');
html, body, .stApp, [data-testid="stMarkdownContainer"], [data-testid="stSidebar"] {{
  font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
  font-variant-numeric: tabular-nums;
  color: {INK};
}}
.stApp {{ background: {PAPER}; }}
.block-container {{ max-width: 920px; margin-left: 0; margin-right: auto; padding-top: 1rem; padding-left: 1.25rem; padding-right: 1.25rem; }}
h1, h2, h3, .serif {{ font-family: 'Source Serif 4', Georgia, serif !important; color: {INK}; font-weight: 600; }}
h1 {{ font-size: 2rem !important; line-height: 1.2 !important; padding-top: 1rem; }}
h2 {{ font-size: 1.35rem !important; line-height: 1.25 !important; padding-top: 1rem; }}
.band {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
header[data-testid="stHeader"] {{ background: {GAMOSA}; height: 3.5rem; }}
header[data-testid="stHeader"]::after {{ content: "Simulated data. No real Assam production is shown."; position: absolute;
  left: 3.5rem; right: 1rem; top: 50%; transform: translateY(-50%); color: #fff; font-weight: 600; font-size: 0.95rem; line-height: 1.25; }}
header[data-testid="stHeader"] button, header[data-testid="stHeader"] svg {{ color: #fff !important; fill: #fff; }}
[data-testid="stMainMenuButton"], [data-testid="stAppDeployButton"] {{ display: none; }}
hr.rule {{ border: 0; border-top: 1px solid rgba(21,35,43,0.2); margin: 1.5rem 0; }}
.hero {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 2.6rem; line-height: 1.15; font-weight: 600; margin: 0.25rem 0 0.1rem 0; }}
.hero small {{ font-size: 1.15rem; font-weight: 400; display: block; }}
.muted {{ opacity: 0.8; font-size: 0.95rem; }}
dl.defs {{ display: flex; flex-wrap: wrap; gap: 0.75rem 2rem; margin: 0; padding: 0.9rem 0;
  border-top: 1px solid rgba(21,35,43,0.2); border-bottom: 1px solid rgba(21,35,43,0.2); }}
dl.defs div {{ min-width: 9rem; }}
dl.defs dt {{ font-size: 0.9rem; opacity: 0.8; }}
dl.defs dd {{ margin: 0; font-size: 1.4rem; font-weight: 600; }}
dl.defs dd small {{ font-size: 0.85rem; font-weight: 400; display: block; }}
.tablewrap {{ overflow-x: auto; }}
table.data {{ border-collapse: collapse; width: 100%; font-size: 0.95rem; }}
table.data th, table.data td {{ padding: 0.35rem 0.7rem; border-bottom: 1px solid rgba(21,35,43,0.2); white-space: nowrap; }}
table.data th {{ font-weight: 600; text-align: right; }}
table.data td {{ text-align: right; }}
table.data th:first-child, table.data td:first-child {{ text-align: left; }}
:focus-visible {{ outline: 2px solid {WATER}; outline-offset: 2px; }}
</style>
"""


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def say(text: str):
    st.markdown(f"**{text}**")


def need_columns(df: pd.DataFrame, cols: list, name: str) -> bool:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        say(f"{name} has no column {', '.join(missing)}. This panel needs it. Restore the file from the engine run.")
        return False
    return True


def rule():
    st.markdown('<hr class="rule">', unsafe_allow_html=True)


def show_fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)
    st.image(buf)


def fmt_t(x) -> str:
    return f"{x:,.0f}"


def pct(x) -> str:
    return f"{x * 100:.1f}%"


def pct2(x) -> str:
    return f"{x * 100:+.2f}%"


def defs(items) -> str:
    cells = "".join(
        f"<div><dt>{html.escape(k)}</dt><dd>{html.escape(v)}"
        + (f"<small>{html.escape(sub)}</small>" if sub else "") + "</dd></div>"
        for k, v, sub in items
    )
    return f'<dl class="defs">{cells}</dl>'


def style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", color=INK, alpha=0.12, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:,.0f}")


st.set_page_config(page_title="D-32 production estimate (simulated)", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- header
st.markdown('<div class="band">Simulated data. No real Assam production is shown.</div>', unsafe_allow_html=True)
st.title("Pond and tank production estimate")

with st.sidebar:
    st.header("Choose a run")
    run_key = st.radio("Run", list(RUNS), format_func=lambda k: RUNS[k]["label"])
    scenario = st.selectbox("Scenario", list(SCENARIOS), format_func=lambda k: f"{k}: {SCENARIOS[k]}")

run = RUNS[run_key]
st.markdown(f"**{run['label']}.** {run['about']}")

rep_path = run["dir"] / "replications.csv"
met_path = run["dir"] / "metrics.csv"
cfg_path = run["dir"] / "config_used.json"

reps_all = met = cfg = None
try:
    reps_all = load_csv(str(rep_path))
except FileNotFoundError:
    say(f"Missing file: {rep_path}. Restore it from the engine run.")
try:
    met = load_csv(str(met_path))
except FileNotFoundError:
    say(f"Missing file: {met_path}. Restore it from the engine run.")
try:
    cfg = load_json(str(cfg_path))
except FileNotFoundError:
    say(f"Missing file: {cfg_path}. Restore it from the engine run.")

row = None
reps = None
if reps_all is not None and need_columns(reps_all, ["scenario", "rep", "truth"], "replications.csv"):
    reps = reps_all[reps_all["scenario"] == scenario].sort_values("rep")
    if reps.empty:
        say(f"No rows for scenario {scenario} in {rep_path}.")
        reps = None
    else:
        with st.sidebar:
            rmin, rmax = int(reps["rep"].min()), int(reps["rep"].max())
            default = 1 if rmin <= 1 <= rmax else rmin
            rep_no = st.number_input(f"Replication ({rmin} to {rmax})", rmin, rmax, default, step=1)
        row = reps[reps["rep"] == rep_no].iloc[0]

# ---------------------------------------------------------------- hero
est_cols = [f"{e}_est" for e in ("E0", "E1", "E2", "E3")] + ["E3_lo", "E3_hi"]
if row is not None and need_columns(reps, est_cols, "replications.csv"):
    truth = float(row["truth"])
    st.markdown(
        f'<div class="hero">{fmt_t(row["E3_est"])} t'
        f'<small>95% interval {fmt_t(row["E3_lo"])} to {fmt_t(row["E3_hi"])}</small></div>'
        f'<div class="muted">E3 estimate, scenario {scenario}, replication {int(rep_no)}. '
        f'True total in this synthetic district: {fmt_t(truth)} t.</div>',
        unsafe_allow_html=True,
    )

    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    names = ["E3", "E2", "E1", "E0"]
    for i, e in enumerate(names):
        est = row[f"{e}_est"]
        colour = WATER if e == "E3" else MUTED
        lo, hi = row.get(f"{e}_lo"), row.get(f"{e}_hi")
        if pd.notna(lo) and pd.notna(hi):
            ax.hlines(i, lo, hi, color=colour, linewidth=3)
        ax.plot(est, i, "o", color=colour, markersize=8)
        ax.annotate(fmt_t(est), (est, i), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=10, color=INK)
    ax.axvline(truth, color=INK, linewidth=1.6)
    ax.annotate(f"True total {fmt_t(truth)}", (truth, len(names) - 0.45), textcoords="offset points",
                xytext=(4, 0), fontsize=10, color=INK, va="bottom")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_ylim(-0.6, len(names) - 0.2)
    ax.set_xlabel("Tonnes of fish per year")
    style_axes(ax)
    fig.tight_layout()
    show_fig(fig)
    st.markdown('<div class="muted">E0 is a point estimate with no interval. The vertical line is the true total.</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- quality row
rule()
st.header("Data quality for this replication")
need = ["n_sel", "n_resp", "n_ver", "undercov_hat", "deff_factors", "cal_failed"]
if row is not None and need_columns(reps, need, "replications.csv"):
    items = [
        ("Response rate", pct(row["n_resp"] / row["n_sel"]), f"{int(row['n_resp'])} of {int(row['n_sel'])} selected"),
        ("Verified share", pct(row["n_ver"] / row["n_resp"]), f"{int(row['n_ver'])} of {int(row['n_resp'])} respondents"),
        ("Not-on-list undercoverage", pct(row["undercov_hat"]), "estimated share"),
        ("Kish design effect", f"{row['deff_factors']:.2f}", "factors only"),
    ]
    cal = f"cal_failed {int(row['cal_failed'])}"
    if "cal_unmet_after" in reps.columns:
        cal += f", cal_unmet_after {int(row['cal_unmet_after'])}"
        cal_sub = "0 means none recorded"
    else:
        cal_sub = "cal_unmet_after is not in this run"
    items.append(("Calibration", cal, cal_sub))
    st.markdown(defs(items), unsafe_allow_html=True)

# ---------------------------------------------------------------- coverage chart
rule()
st.header("Do the intervals cover the truth?")
if reps is not None and need_columns(reps, ["E3_lo", "E3_hi"], "replications.csv"):
    first = reps.head(100).reset_index(drop=True)
    truth = float(first["truth"].iloc[0])
    hit = (first["E3_lo"] <= first["truth"]) & (first["truth"] <= first["E3_hi"])
    fig, ax = plt.subplots(figsize=(5.4, 5.2))
    for i, r in first.iterrows():
        if hit[i]:
            ax.hlines(i, r["E3_lo"], r["E3_hi"], color=WATER, linewidth=1.4)
        else:
            ax.hlines(i, r["E3_lo"], r["E3_hi"], color=SILT, linewidth=1.8)
            ax.plot([r["E3_lo"], r["E3_hi"]], [i, i], "o", markerfacecolor=PAPER, markeredgecolor=SILT,
                    markersize=5, markeredgewidth=1.4)
    ax.axvline(truth, color=INK, linewidth=1.4)
    ax.invert_yaxis()
    ax.set_xlabel("Tonnes of fish per year")
    ax.set_ylabel("Replication (first 100)")
    ax.set_title(f"{scenario}: {int(hit.sum())} of {len(first)} intervals contain the truth ({pct(hit.mean())})",
                 fontsize=11, loc="left")
    style_axes(ax)
    fig.tight_layout()
    show_fig(fig)
    st.markdown('<div class="muted">Solid blue-green lines contain the true total. Ochre lines with hollow end markers miss it. '
                'The vertical line is the true total. The share is for these 100 only; the table below covers all repetitions.</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- metrics table
rule()
st.header("Performance across simulated repetitions")
if met is not None:
    mcols = ["scenario", "estimator", "reps", "rel_bias", "rel_bias_mc_se", "rmse_t", "coverage",
             "coverage_mc_se", "rse_empirical", "rse_mean_estimated"]
    if need_columns(met, mcols, "metrics.csv"):
        m = met[(met["scenario"] == scenario) & (met["estimator"].isin(["E0", "E1", "E2", "E3"]))]
        if m.empty:
            say(f"No rows for scenario {scenario} in {met_path}.")
        else:
            na = lambda f: (lambda x: "n/a" if pd.isna(x) else f(x))
            heads = ["Estimator", "Bias", "Bias MC SE", "RMSE (t)", "Coverage", "Coverage MC SE", "RSE empirical", "RSE estimated"]
            body = ""
            for _, r in m.iterrows():
                cells = [r["estimator"], pct2(r["rel_bias"]), f"{r['rel_bias_mc_se'] * 100:.2f}%", fmt_t(r["rmse_t"]),
                         na(pct)(r["coverage"]), na(pct)(r["coverage_mc_se"]), pct(r["rse_empirical"]),
                         na(pct)(r["rse_mean_estimated"])]
                body += "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>"
            head = "".join(f"<th>{h}</th>" for h in heads)
            st.markdown(f'<div class="tablewrap"><table class="data"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
                        unsafe_allow_html=True)
            n_reps = int(m["reps"].iloc[0])
            st.markdown(f'<div class="muted">Bias and coverage are across {n_reps:,} simulated repetitions, not the one replication above. '
                        'Bias is relative to the true total. MC SE is the Monte Carlo standard error. E0 has no interval, so no coverage.</div>',
                        unsafe_allow_html=True)

# ---------------------------------------------------------------- flag queue
rule()
st.header("Flag queue (not connected to simulated events yet)")
st.markdown("The engine does not output event-level flags, so this queue is empty. No flag records are shown and none are made up. "
            "When connected, it will show the plausibility checks of design section 10:")
for r in FLAG_RULES:
    st.markdown(f"- {r}")
st.markdown("A flag sends the record to review. The reviewer records a resolution: confirmed, corrected with evidence, or unresolved. "
            "The original value is kept and the reviewer value is added as a new version. The main estimate uses confirmed and "
            "corrected values. A sensitivity estimate that leaves out unresolved flagged records sits beside it.")

# ---------------------------------------------------------------- run record
rule()
st.header("Run record")
if cfg is not None:
    keys = {"pop_seed": "Population seed", "master_seed": "Master seed", "n_per_district": "Sample size n",
            "n_boot": "Bootstrap replicates", "ci_level": "Interval level"}
    items = [(label, str(cfg[k]), "") for k, label in keys.items() if k in cfg]
    if reps_all is not None and "scenario" in reps_all.columns:
        items.append(("Replications per scenario", f"{int(reps_all.groupby('scenario').size().max()):,}", "counted from replications.csv"))
    st.markdown(defs(items), unsafe_allow_html=True)
    absent = [k for k in keys if k not in cfg]
    if absent:
        say(f"config_used.json has no field {', '.join(absent)}.")
st.code(f"{rep_path}\n{met_path}\n{cfg_path}", language=None)
