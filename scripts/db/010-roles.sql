-- Explicit bootstrap for a NEW dedicated database/cluster. Never run as API startup.
-- Password values come from the operator environment, never command-line literals.
\set ON_ERROR_STOP on
\getenv runtime_password DB_RUNTIME_PASSWORD
\getenv migration_password DB_MIGRATION_PASSWORD
\getenv operator_password DB_OPERATOR_PASSWORD
\getenv bootstrap_password DB_BOOTSTRAP_PASSWORD
SELECT length(:'runtime_password') >= 24 AND length(:'migration_password') >= 24
       AND length(:'operator_password') >= 24
       AND length(:'bootstrap_password') >= 24
       AND upper(:'runtime_password') NOT LIKE '%REPLACE%'
       AND upper(:'migration_password') NOT LIKE '%REPLACE%'
       AND upper(:'operator_password') NOT LIKE '%REPLACE%'
       AND upper(:'bootstrap_password') NOT LIKE '%REPLACE%'
       AND :'runtime_password' <> :'migration_password'
       AND :'runtime_password' <> :'operator_password'
       AND :'migration_password' <> :'operator_password'
       AND :'bootstrap_password' <> ALL (ARRAY[:'runtime_password', :'migration_password', :'operator_password'])
       AS passwords_valid \gset
\if :passwords_valid
\else
    \echo 'Four distinct non-placeholder DB passwords of at least 24 characters are required.'
    \quit 3
\endif

-- CREATE ROLE fails on existing names rather than silently altering another deployment.
BEGIN;
CREATE ROLE near_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    NOREPLICATION NOBYPASSRLS PASSWORD :'migration_password';
CREATE ROLE near_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    NOREPLICATION NOBYPASSRLS PASSWORD :'runtime_password';
CREATE ROLE near_operator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    NOREPLICATION NOBYPASSRLS PASSWORD :'operator_password';
-- Optional fifth credential (NI-019): the dedicated limited context for
-- public queries. It receives CONNECT only and no schema privileges here;
-- future public data tables grant it their own read scopes. Deployments
-- that do not set DB_PUBLIC_PASSWORD (for example the DB-only Compose
-- service) bootstrap without the role and behave exactly as before.
\getenv public_password DB_PUBLIC_PASSWORD
\if :{?public_password}
SELECT length(:'public_password') >= 24
       AND upper(:'public_password') NOT LIKE '%REPLACE%'
       AND :'public_password' <> ALL (ARRAY[:'bootstrap_password', :'runtime_password',
                                           :'migration_password', :'operator_password'])
       AS public_password_valid \gset
\if :public_password_valid
\else
    \echo 'DB_PUBLIC_PASSWORD must be a distinct non-placeholder secret of at least 24 characters.'
    \quit 3
\endif
CREATE ROLE near_public LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    NOREPLICATION NOBYPASSRLS PASSWORD :'public_password';
SELECT format('GRANT CONNECT ON DATABASE %I TO near_public', current_database()) \gexec
SELECT format('ALTER ROLE near_public IN DATABASE %I SET search_path = pg_catalog',
              current_database()) \gexec
\else
\echo 'DB_PUBLIC_PASSWORD is not set: skipping the near_public public-query role.'
\endif
SELECT format('ALTER DATABASE %I OWNER TO near_migrator', current_database()) \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO near_app, near_migrator, near_operator',
              current_database()) \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA app AUTHORIZATION near_migrator;
REVOKE ALL ON SCHEMA app FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO near_app, near_operator;
SELECT format('ALTER ROLE near_app IN DATABASE %I SET search_path = pg_catalog, app',
              current_database()) \gexec
SELECT format('ALTER ROLE near_operator IN DATABASE %I SET search_path = pg_catalog, app',
              current_database()) \gexec
COMMIT;
