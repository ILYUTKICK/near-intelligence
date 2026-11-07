"""Research command surface for the offline model pipeline.

The estimator itself is offline research code under
``research/models/fit.py`` (NI-052); this package owns only the
``python -m near_api.research`` dispatch. It contains no estimation
logic: it loads the research module by path (import only) and forwards
the command arguments, so there is exactly one estimator implementation
and one version source. Persistence/publication of fit runs belongs to
NI-054.
"""
