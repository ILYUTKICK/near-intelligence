"""Owner-scoped workspace aggregation for the authenticated shell (NI-022).

Every query here derives its owner predicate from the verified principal and
pages through `db/security.scoped_page`, so totals and recent lists can never
include another user's rows. Routes in this package are the first private
HTTP surface of the API: identity comes only from `get_principal` (NI-018)
and every response is `Cache-Control: no-store`.
"""
