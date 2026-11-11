"""Public research publications (NI-045).

The public side of the editor's duplication story (EDITOR_SPECIFICATION):
operator-seeded immutable ``(slug, version)`` releases whose canonical
content :mod:`near_api.publications.routes` serves publicly and
:mod:`near_api.publications.duplicate` clones into fresh private IDs with
retained attribution, public data/model pins and rebuilt chart contexts.

Public subsequent edits never mutate copies: a duplicate is an independent
private ``app.documents`` row — the publication row itself is immutable
(no UPDATE grant/policy for any role) and only the operator CLI seeds it,
so the API package contains no publication writer.
"""
