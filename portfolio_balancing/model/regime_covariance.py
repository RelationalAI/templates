"""Regime covariance: the covariance of each stock pair under the base regime (the observed covariance) and
under the crisis regime (the observed covariance shrunk toward the product of the stocks' volatilities)."""

from relationalai.semantics import Float

# Declares Stock.volatility, which the crisis covariance reads.
from . import correlation_clusters  # noqa: F401
from .schema import Regime, Stock, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

CRISIS_ALPHA = 0.7  # shrinkage weight for base correlation in crisis regime (Stage 4)

# --------------------------------------------------
# Stage 3: regime covariance
# --------------------------------------------------

# Regime-conditioned covariance is derived in PyRel from the base covariance
# and the derived volatilities:
#   base:   Sigma(i, j)
#   crisis: alpha * Sigma(i, j) + (1 - alpha) * vol_i * vol_j
# The crisis formula is equivalent to correlation shrinkage toward all-ones
# (rho_crisis = alpha * rho + (1 - alpha) * J) re-expressed in covariance
# units. PSD is preserved because the construction is a convex combination of
# PSD matrices.
# Base regime: covariance unchanged.
PairedStockBase = Stock.ref()
base_cov_ref = Float.ref()
base_regime_ref = Regime.ref()
model.where(
    Stock.covar(PairedStockBase, base_cov_ref),
    base_regime_ref.regime_name == "base",
).define(Stock.regime_covar(PairedStockBase, base_regime_ref, base_cov_ref))

# Crisis regime: convex combination of base covariance and vol_i * vol_j.
PairedStockCrisis = Stock.ref()
crisis_cov_ref = Float.ref()
crisis_regime_ref = Regime.ref()
model.where(
    Stock.covar(PairedStockCrisis, crisis_cov_ref),
    crisis_regime_ref.regime_name == "crisis",
).define(
    Stock.regime_covar(
        PairedStockCrisis,
        crisis_regime_ref,
        CRISIS_ALPHA * crisis_cov_ref
        + (1 - CRISIS_ALPHA) * Stock.volatility * PairedStockCrisis.volatility,
    )
)

