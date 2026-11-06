"""Owner-scoped repositories for private data (NI-019).

Each repository module exposes functions whose first parameter is a
transaction ``Connection`` obtained from
:func:`near_api.db.security.principal_transaction`; ownership always comes
from the verified ``Principal`` that opened it. HTTP routes (owning tasks)
map :class:`near_api.db.security.ResourceNotFound` to one generic 404.
"""
