"""Frozen document export representation (NI-056).

:mod:`near_api.exports.ir` translates one acknowledged immutable document
revision into the deterministic intermediate representation
(:mod:`near_api.schemas.export`) that the export pipeline renders from:
NI-057 static chart assets and NI-058 Markdown ZIP delivery. The
representation is strictly frozen — it never consults a latest pointer, it
fails closed on any unresolvable pin or unsupported block, and building it
twice for the same revision yields byte-identical canonical serialization.
"""
