"""NESFIC D-32 survey engine. Everything produced by the simulation is SIMULATED."""
import os

# one BLAS thread per process: keeps results independent of the machine's thread count
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
