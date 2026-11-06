"""JWT verification and application-principal bootstrap (NI-018).

The API authenticates independently of gateway trust: bearer JWTs are verified
against the configured provider JWKS with exact issuer/audience claims, and the
database identity is derived only from the verified subject. See
docs/AUTHENTICATION_SECURITY.md.
"""
