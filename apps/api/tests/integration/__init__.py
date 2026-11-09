"""NI-061 business/data integration regression suite (independent oracles).

These tests recompute the expected financial and research values from the
synthetic canonical inputs with an implementation that is deliberately
DIFFERENT from ``near_api.metrics`` (plain-integer yoctoNEAR arithmetic and
straight-line matching in :mod:`integration.oracles`) and compare the result
EXACTLY (Decimal equality on the delivered decimal strings) against what the
pipeline delivers across every boundary:

raw saved-extract rows -> NI-029 computation/emission -> NI-028 staging and
publication (real PostgreSQL) -> NI-032 delivery APIs -> NI-041/NI-043 frozen
document revision contexts -> NI-036 projections -> NI-049 evidence graph.

Every account, receipt id, amount and hash in the fixtures is synthetic and
visibly labeled (``synthetic`` in names and fixture notes). No test touches
the research archives, the stopped collectors, any provider, or the network.
"""
