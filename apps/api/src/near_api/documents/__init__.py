"""Canonical document schema, revision service and projections (NI-036).

The complete editor JSON is canonical (EDITOR_SPECIFICATION.md): every save
validates one authoritative :mod:`near_api.documents.schema` document, writes
an immutable ``document_versions`` revision together with the validated
``document_blocks``/``insights``/``hypotheses``/``evidence_links`` projections
(:mod:`near_api.documents.projections`) in ONE transaction
(:mod:`near_api.documents.service`), and moves the document's current-version
pointer with compare-and-set semantics. Insight/hypothesis/evidence REST
mutations (NI-046+) are convenience editors of this same JSON, never a second
mutable source.
"""
