"""Research command surface and descriptive delivery.

The estimator itself is offline research code under
``research/models/fit.py`` (NI-052); this package owns the
``python -m near_api.research`` dispatch. It contains no estimation
logic: it loads the research module by path (import only) and forwards
the command arguments, so there is exactly one estimator implementation
and one version source. Persistence/publication of fit runs belongs to
NI-054. NI-083 adds descriptive approved-dataset delivery and a separate
bounded offline history preparation module; HTTP never reads local archives.
"""
