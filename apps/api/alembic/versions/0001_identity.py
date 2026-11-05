"""NI-003: identity only; role bootstrap precedes this reversible migration."""

from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION app.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog
        AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;
        CREATE FUNCTION app.is_valid_timezone(zone text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog
        AS $$ SELECT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = zone)
                     AND zone NOT LIKE 'posix/%' AND zone NOT LIKE 'right/%' $$;
        REVOKE ALL ON FUNCTION app.current_user_id(), app.is_valid_timezone(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION app.current_user_id(), app.is_valid_timezone(text)
            TO near_app, near_operator;

        CREATE TABLE app.users (
            id uuid CONSTRAINT pk_users PRIMARY KEY,
            auth_provider varchar(16) NOT NULL DEFAULT 'supabase',
            created_at timestamptz NOT NULL DEFAULT now(),
            disabled_at timestamptz,
            CONSTRAINT ck_users_auth_provider CHECK (auth_provider = 'supabase')
        );
        CREATE TABLE app.user_profiles (
            user_id uuid CONSTRAINT pk_user_profiles PRIMARY KEY,
            display_name varchar(80) NOT NULL DEFAULT '',
            display_timezone varchar(64) NOT NULL DEFAULT 'UTC',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_user_profiles_user_id FOREIGN KEY (user_id) REFERENCES app.users(id)
                ON DELETE CASCADE,
            CONSTRAINT ck_user_profiles_timezone CHECK (app.is_valid_timezone(display_timezone))
        );
        CREATE FUNCTION app.touch_profile_updated_at() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$;
        REVOKE ALL ON FUNCTION app.touch_profile_updated_at() FROM PUBLIC;
        CREATE TRIGGER profile_updated_at BEFORE UPDATE ON app.user_profiles
            FOR EACH ROW EXECUTE FUNCTION app.touch_profile_updated_at();

        ALTER TABLE app.users ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.users FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.user_profiles ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.user_profiles FORCE ROW LEVEL SECURITY;
        CREATE POLICY users_self_read ON app.users FOR SELECT TO near_app
            USING (id = app.current_user_id());
        CREATE POLICY users_self_bootstrap ON app.users FOR INSERT TO near_app
            WITH CHECK (id = app.current_user_id() AND disabled_at IS NULL);
        CREATE POLICY users_operator ON app.users TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY profile_self ON app.user_profiles TO near_app
            USING (user_id = app.current_user_id() AND EXISTS (
                SELECT 1 FROM app.users u WHERE u.id = user_id AND u.disabled_at IS NULL))
            WITH CHECK (user_id = app.current_user_id() AND EXISTS (
                SELECT 1 FROM app.users u WHERE u.id = user_id AND u.disabled_at IS NULL));
        CREATE POLICY profile_operator ON app.user_profiles TO near_operator
            USING (true) WITH CHECK (true);

        GRANT SELECT ON app.users TO near_app, near_operator;
        GRANT INSERT(id) ON app.users TO near_app, near_operator;
        GRANT UPDATE(disabled_at) ON app.users TO near_operator;
        GRANT DELETE ON app.users TO near_operator;
        GRANT SELECT, DELETE ON app.user_profiles TO near_app, near_operator;
        GRANT INSERT(user_id, display_name, display_timezone), UPDATE(display_name, display_timezone)
            ON app.user_profiles TO near_app, near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.user_profiles;
        DROP TABLE app.users;
        DROP FUNCTION app.touch_profile_updated_at();
        DROP FUNCTION app.is_valid_timezone(text);
        DROP FUNCTION app.current_user_id();
    """)
