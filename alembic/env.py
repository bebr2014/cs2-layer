from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.db.models import Base
from app.config import settings

config = context.config

# Подставляем sync URL (psycopg2)
sync_url = "postgresql+psycopg2://postgres:bTzcPhuovaxICNnhvFVatINSHxPgPUqs@shinkansen.proxy.rlwy.net:36960/railway?sslmode=require"
if "?" in sync_url:
    sync_url = sync_url.split("?")[0]
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        run_migrations_online()
    except Exception as e:
        print(f"ALEMBIC ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise
