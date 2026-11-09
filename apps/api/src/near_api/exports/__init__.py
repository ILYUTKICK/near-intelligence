"""Frozen document export representation and delivery (NI-056/057/058).

:mod:`near_api.exports.ir` translates one acknowledged immutable document
revision into the deterministic intermediate representation
(:mod:`near_api.schemas.export`) that the export pipeline renders from.
NI-057 renders the static chart assets through the pinned Node SSR renderer
(:mod:`near_api.exports.charts`). NI-058 delivers the Markdown ZIP export:
:mod:`near_api.exports.markdown` renders ``research.md`` from the plan,
:mod:`near_api.exports.bundle` assembles ``research.md`` + assets +
``manifest.json`` into the fixed-timestamp ZIP, :mod:`near_api.exports.
service` stores and polices the owner-scoped jobs, :mod:`near_api.exports.
routes` expose create/poll/download, and :mod:`near_api.exports.worker` is
the operator lease/retry/TTL CLI.

The representation is strictly frozen — it never consults a latest pointer,
it fails closed on any unresolvable pin or unsupported block, and building
it twice for the same revision yields byte-identical canonical serialization.
"""
