"""Every parameter of the simulation in one place.

Tags: [DOC] = fixed by docs/design.md; [SOURCED] = from a cited figure;
[ASSUMPTION] = my placeholder, chosen before any result was seen and never
tuned afterwards. All output built on this config is SIMULATED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json


@dataclass(frozen=True)
class Config:
    # ---- master seeds -----------------------------------------------------
    pop_seed: int = 20261102          # [DOC] 15.4 confirmatory run (v0.1 used 20261101)
    master_seed: int = 4417           # [DOC] 15.4 confirmatory run (v0.1 used 2026)

    # ---- synthetic district (design.md 15.1) -------------------------------
    n_listed: int = 20000             # [DOC]
    n_not_on_list: int = 1600         # [DOC] 8% undercoverage
    mean_area_ha: float = 0.17        # [SOURCED] 96,968.86 ha / 560,019 (NEDFI 2023-24)
    pond_area_sigma: float = 1.0      # [ASSUMPTION] log-sd of pond area (long right tail)
    tank_share: float = 0.02          # [DOC] placeholder
    tank_mean_area_ha: float = 1.0    # [ASSUMPTION] tanks larger on average
    tank_area_sigma: float = 0.8      # [ASSUMPTION]
    nol_mean_area_ha: float = 0.09    # [ASSUMPTION] not-on-list skewed to small ponds
    nol_area_sigma: float = 0.8       # [ASSUMPTION]
    assisted_share: float = 0.30      # [ASSUMPTION] share of listed units in scheme/seed records
    assisted_area_slope: float = 0.6  # [ASSUMPTION] bigger units more likely assisted (logit per log-ha)
    n_blocks: int = 10                # [ASSUMPTION]
    dist_gamma_shape: float = 2.0     # [ASSUMPTION] distance to block office (km) ~ Gamma(shape, scale)
    dist_gamma_scale: float = 4.0     # [ASSUMPTION]
    n_cells: int = 1500               # [ASSUMPTION] 1 km2 grid cells in the district
    cell_clustering_sigma: float = 1.0  # [ASSUMPTION] log-sd of cell attractiveness for water bodies
    imagery_noise_sigma: float = 0.5  # [ASSUMPTION] log-sd error of the NDWI water proxy
    water_rich_share: float = 0.30    # [ASSUMPTION] share of cells in the "water-rich" stratum

    # true productivity t/ha by (type, assisted)   [ASSUMPTION] placeholders
    prod_pond_plain: float = 3.0
    prod_pond_assisted: float = 5.5
    prod_tank_plain: float = 3.5
    prod_tank_assisted: float = 6.0
    prod_noise_sigma: float = 0.5     # [ASSUMPTION] log-sd of unit-level noise (mean-1 lognormal)

    # ---- measurement errors (design.md 15.1) ------------------------------
    beta_diary_assisted: float = -0.10      # [DOC]
    beta_diary_plain: float = -0.10         # [DOC]
    rho_diary: float = 0.9                  # [DOC] within-stratum corr(diary, truth)
    beta_recall: float = -0.25              # [DOC]
    rho_recall: float = 0.6                 # [ASSUMPTION] "noisier than the diary"
    verify_prob: float = 1.0                # [ASSUMPTION] share of phase-2 harvest events verified (A7 holds)
    max_events: int = 6                     # [DOC] 1-6 events per unit-year

    # ---- dropout (design.md 15.1, S4) -------------------------------------
    mean_response: float = 0.85             # [DOC]
    resp_b_logarea: float = 0.3             # [ASSUMPTION]
    resp_b_assisted: float = 0.4            # [ASSUMPTION]
    resp_b_tank: float = 0.3                # [ASSUMPTION]
    resp_b_dist: float = -0.05              # [ASSUMPTION] per km
    resp_block_sd: float = 0.4              # [ASSUMPTION]
    dropout_gamma: float = 0.0              # [ASSUMPTION] S4: response rises with the unit's yield shock

    # ---- design (sections 4-6, 9) ------------------------------------------
    n_per_district: int = 200               # [DOC]
    n_size_classes: int = 3                 # [DOC]
    hist_bins: int = 1000                   # [ASSUMPTION] "fine histogram" for the sqrt-f rule
    n_min_stratum: int = 5                  # [DOC]
    min_frame_stratum: int = 20             # [DOC]
    take_all_cap_frac: float = 0.10         # [DOC] 4.4 / A4: take-all capped at floor(0.1 n), counted inside n
    take_all_min_area_ha: float = 2.0       # [DOC] 4.4 v0.2: take-all candidates are units >= 2 ha
    # planning productivity t/ha (A5), assumed equal to the true placeholders
    plan_prod_pond_plain: float = 3.0
    plan_prod_pond_assisted: float = 5.5
    plan_prod_tank_plain: float = 3.5
    plan_prod_tank_assisted: float = 6.0
    phase2_rate: float = 0.30               # [DOC] nu
    phase2_min: int = 2                     # [DOC] variance needs >= 2 verified per stratum
    n_np_classes: int = 5                   # [DOC]
    phi_cap: float = 2.0                    # [DOC]
    logit_ridge: float = 1e-6               # [ASSUMPTION] numerical safety only (4 parameters, ~200 rows)
    cal_g_lo: float = 0.3                   # [DOC] 9 step 5: calibration factor bounds
    cal_g_hi: float = 3.0                   # [DOC]
    cal_max_iter: int = 20                  # [DOC]
    cal_min_resp: int = 8                   # [DOC] v0.3 (was 4): fewer respondents -> calibrate to N_h only
    cal_fallback: bool = True               # [DOC] v0.3: a stratum that still misses N_h/A_h redoes N_h only
                                            # v0.2 rule on the same samples: cal_min_resp=4, cal_fallback=False
    cells_water_rich: int = 20              # [ASSUMPTION] "about 30 cells" split 20 / 10
    cells_other: int = 10                   # [ASSUMPTION]

    # ---- estimators / variance --------------------------------------------
    e0_norm_productivity: float = 4.89      # [SOURCED] 4.74 lakh t / 96,968.86 ha (one of 3 published totals)
    ci_level: float = 0.95                  # [DOC]
    n_boot: int = 500                       # [DOC]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @property
    def planning_productivity(self) -> dict:
        return {
            ("pond", 0): self.plan_prod_pond_plain,
            ("pond", 1): self.plan_prod_pond_assisted,
            ("tank", 0): self.plan_prod_tank_plain,
            ("tank", 1): self.plan_prod_tank_assisted,
        }


BASE = Config()

# Scenario overrides (design.md 15.3). S6 (3 years, rotation) is NOT implemented.
SCENARIOS: dict[str, dict] = {
    "S1": {},
    "S2": {"rho_diary": 0.7},
    "S3": {"beta_diary_assisted": -0.05, "beta_diary_plain": -0.20},
    "S4": {"dropout_gamma": 0.8},
    "S5": {"verify_prob": 0.75},
}


def scenario_config(name: str, base: Config = BASE) -> Config:
    return replace(base, **SCENARIOS[name])
