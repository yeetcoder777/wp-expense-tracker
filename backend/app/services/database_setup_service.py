"""Additive account setup; existing financial table permissions are never changed."""

from sqlalchemy import text

from app.config import settings
from app.db.database import Base, engine
from app.db.models import DashboardLoginChallenge, DashboardSession, DashboardUser

AUTH_TABLES = (DashboardUser.__table__, DashboardLoginChallenge.__table__, DashboardSession.__table__)


def prepare_database() -> None:
    quote = engine.dialect.identifier_preparer.quote
    with engine.begin() as connection:
        # New auth tables and their protection commit together on PostgreSQL.
        Base.metadata.create_all(bind=connection)
        if engine.dialect.name != "postgresql":
            return
        public_roles = ["PUBLIC"]
        database_roles = []
        for role in ("anon", "authenticated"):
            if connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}).scalar():
                public_roles.append(quote(role))
                database_roles.append(role)
        # Only the three newly introduced auth tables are protected here.
        for table in AUTH_TABLES:
            name = quote(table.name)
            connection.execute(text(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY"))
            connection.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {name} FROM {', '.join(public_roles)}"))
        if settings.environment.lower() == "production":
            _check_existing_table_privacy(connection, database_roles)


def _check_existing_table_privacy(connection, roles: list[str]) -> None:
    """Read-only fail-closed audit; an operator must review any existing grants."""
    unsafe = []
    for table in Base.metadata.sorted_tables:
        if table.name in {item.name for item in AUTH_TABLES}:
            continue
        qualified = f"public.{table.name}"
        exposed = any(connection.execute(text(
            "SELECT has_table_privilege(:role, :name, 'SELECT,INSERT,UPDATE,DELETE')"
        ), {"role": role, "name": qualified}).scalar() for role in roles)
        if not exposed:
            continue
        rls = connection.execute(text(
            "SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass(:name)"
        ), {"name": qualified}).scalar()
        policies = connection.execute(text(
            "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = :name"
        ), {"name": table.name}).scalar()
        if not rls or policies:
            unsafe.append(table.name)
    if unsafe:
        raise RuntimeError(
            "Review Supabase Data API access before production. Existing table permissions "
            "were not changed. Tables needing an explicit privacy review: " + ", ".join(unsafe)
        )
