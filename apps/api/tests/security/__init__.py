"""NI-062 adversarial ownership and security audit suites.

The packages here are deliberately separate from the functional suites: they
attack the implemented boundaries (HTTP ownership matrix over every private
endpoint family, direct RLS probes, token/session rejection, untrusted
content, static sink/secret enumeration) instead of re-proving features.

Cluster cases need scripts/run-db-tests.py (they skip elsewhere; a skip is
never integration evidence). All identities, documents, datasets and amounts
are synthetic fixtures; no provider, archive or network is contacted.
"""
