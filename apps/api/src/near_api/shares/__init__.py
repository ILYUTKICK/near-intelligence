"""Revocable read-only sharing of one frozen revision (NI-060, ADR-021).

:mod:`near_api.shares.projection` narrows the verified NI-056 export IR into
the public allowlist projection (:mod:`near_api.schemas.share`);
:mod:`near_api.shares.service` stores and polices the capability rows of
``app.document_shares`` (high-entropy tokens held as SHA-256 digests only,
frozen canonical projection bytes, owner revoke/expiry denials);
:mod:`near_api.shares.routes` expose the owner-scoped preview/create/list/
revoke routes and the token-gated public projection/chart-view/CSV routes.

The published payload is immutable by construction: every read serves the
bytes stored at create time, re-checking the live share state on every
request; edits, renames and dataset publications can never reach a share.
"""
