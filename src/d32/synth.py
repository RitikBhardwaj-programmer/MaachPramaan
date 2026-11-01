"""Synthetic district (design.md 15.1). All values are SIMULATED."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .config import Config


def _ln_mu(mean: float, sigma: float) -> float:
    return np.log(mean) - sigma**2 / 2


def _expit(x):
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class District:
    units: pd.DataFrame   # listed units first (on_list=True), then not-on-list
    n_listed: int
    cell_water_rich: np.ndarray   # bool per cell (imagery-based stratum)
    cell_ids: np.ndarray          # str ids of cells
    calib_group: np.ndarray       # group label per unit for the rho calibration
    cfg: Config

    @property
    def listed(self) -> pd.DataFrame:
        return self.units.iloc[: self.n_listed]

    @property
    def truth_total(self) -> float:
        """True district production incl. not-on-list units (tonnes, simulated)."""
        return float(self.units["y"].sum())

    @property
    def truth_list(self) -> float:
        return float(self.listed["y"].sum())

    @property
    def truth_nol(self) -> float:
        return float(self.units["y"].iloc[self.n_listed:].sum())


def make_district(cfg: Config) -> District:
    rng = np.random.default_rng(np.random.SeedSequence(cfg.pop_seed))
    NL, NN = cfg.n_listed, cfg.n_not_on_list
    n = NL + NN

    # type and area ----------------------------------------------------------
    tank = np.zeros(n, dtype=bool)
    tank[:NL] = rng.random(NL) < cfg.tank_share
    area = np.empty(n)
    pond_mean = (cfg.mean_area_ha - cfg.tank_share * cfg.tank_mean_area_ha) / (1 - cfg.tank_share)
    # listed ponds then listed tanks then not-on-list ponds
    ip = np.where(~tank[:NL])[0]
    it = np.where(tank[:NL])[0]
    area[ip] = rng.lognormal(_ln_mu(pond_mean, cfg.pond_area_sigma), cfg.pond_area_sigma, ip.size)
    area[it] = rng.lognormal(_ln_mu(cfg.tank_mean_area_ha, cfg.tank_area_sigma), cfg.tank_area_sigma, it.size)
    area[NL:] = rng.lognormal(_ln_mu(cfg.nol_mean_area_ha, cfg.nol_area_sigma), cfg.nol_area_sigma, NN)

    # intensity proxy (listed only; not-on-list units have no scheme records)
    la = np.log(area[:NL] / cfg.mean_area_ha)
    f = lambda a0: _expit(a0 + cfg.assisted_area_slope * la).mean() - cfg.assisted_share
    a0 = brentq(f, -20, 20)
    assisted = np.zeros(n, dtype=bool)
    assisted[:NL] = rng.random(NL) < _expit(a0 + cfg.assisted_area_slope * la)

    block = rng.integers(0, cfg.n_blocks, n)
    dist = rng.gamma(cfg.dist_gamma_shape, cfg.dist_gamma_scale, n)

    # true production ----------------------------------------------------------
    base = np.where(tank, np.where(assisted, cfg.prod_tank_assisted, cfg.prod_tank_plain),
                    np.where(assisted, cfg.prod_pond_assisted, cfg.prod_pond_plain))
    z_prod = rng.standard_normal(n)
    s = cfg.prod_noise_sigma
    prod = base * np.exp(s * z_prod - s**2 / 2)
    if cfg.sigma_b != 0.0:      # design.md 21.4: block effect, own SeedSequence child so no other draw moves
        u_b = np.random.default_rng(np.random.SeedSequence(cfg.pop_seed).spawn(3)[2]).standard_normal(cfg.n_blocks)
        prod = prod * (1 + cfg.sigma_b * u_b[block])
    y = area * prod                                  # tonnes
    n_events = rng.integers(1, cfg.max_events + 1, n)

    # grid cells ------------------------------------------------------------
    w = rng.lognormal(0, cfg.cell_clustering_sigma, cfg.n_cells)
    cell = rng.choice(cfg.n_cells, size=n, p=w / w.sum())
    cell_area = np.bincount(cell, weights=area, minlength=cfg.n_cells)
    proxy = cell_area * np.exp(cfg.imagery_noise_sigma * rng.standard_normal(cfg.n_cells))
    cut = np.quantile(proxy, 1 - cfg.water_rich_share)
    water_rich = proxy >= cut

    ids = np.array([f"D1-{i:06d}" for i in range(n)])
    ids[NL:] = [f"D1-NOL{i:05d}" for i in range(NN)]
    units = pd.DataFrame({
        "unit_id": ids,
        "on_list": np.arange(n) < NL,
        "type": np.where(tank, "tank", "pond"),
        "area": area,
        "assisted": assisted.astype(int),
        "block": block,
        "dist_km": dist,
        "cell": cell,
        "z_prod": z_prod,
        "prod": prod,
        "y": y,
        "n_events": n_events,
    })
    # calibration groups for rho: (type, assisted, area tercile) ; separate group for not-on-list
    grp = np.empty(n, dtype=object)
    lst = units.iloc[:NL]
    terc = lst.groupby(["type", "assisted"])["area"].rank(pct=True)
    tbin = np.minimum((terc.values * 3).astype(int), 2)
    grp[:NL] = [f"{t}-{a}-{b}" for t, a, b in zip(lst["type"], lst["assisted"], tbin)]
    grp[NL:] = "nol"
    return District(units, NL, water_rich, np.array([f"C{i:04d}" for i in range(cfg.n_cells)]), grp, cfg)


def eta_cv(y: np.ndarray, groups: np.ndarray, rho: float) -> float:
    """CV of a mean-1 multiplicative noise so that pooled within-group corr(y, y*eta) = rho.

    Derivation: with E[eta]=1 independent of y, Cov(y, y*eta) = Var(y) and
    Var(y*eta) = Var(y) + cv^2 * E[y^2]  (group by group), hence
    cv^2 = (1/rho^2 - 1) * sum_g N_g Var_g / sum_g N_g E_g[y^2].
    """
    df = pd.DataFrame({"y": y, "g": groups})
    g = df.groupby("g")["y"]
    N = g.size().values
    var = g.var(ddof=0).values
    m2 = g.apply(lambda s: float((s**2).mean())).values
    return float(np.sqrt((1 / rho**2 - 1) * (N * var).sum() / (N * m2).sum()))


def lognormal_noise(z: np.ndarray, cv: float) -> np.ndarray:
    s2 = np.log1p(cv**2)
    return np.exp(np.sqrt(s2) * z - s2 / 2)


def response_probability(dist: District, cfg: Config) -> np.ndarray:
    """Per-listed-unit probability of completing the diary year; mean = cfg.mean_response."""
    u = dist.listed
    rng = np.random.default_rng(np.random.SeedSequence(cfg.pop_seed).spawn(2)[1])
    block_eff = rng.normal(0, cfg.resp_block_sd, cfg.n_blocks)
    lin = (cfg.resp_b_logarea * np.log(u["area"].values / cfg.mean_area_ha)
           + cfg.resp_b_assisted * u["assisted"].values
           + cfg.resp_b_tank * (u["type"].values == "tank")
           + cfg.resp_b_dist * u["dist_km"].values
           + block_eff[u["block"].values]
           + cfg.dropout_gamma * u["z_prod"].values)
    a = brentq(lambda a: _expit(a + lin).mean() - cfg.mean_response, -30, 30)
    return _expit(a + lin)
