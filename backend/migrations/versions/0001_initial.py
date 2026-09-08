"""Initial enterprise document schema and native full-text indexes."""
from alembic import op
from app.database import Base, install_search_index
from app import models

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    Base.metadata.create_all(connection)
    install_search_index(connection)


def downgrade():
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        for trigger in ("records_ai", "records_ad", "records_au"):
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {trigger}")
        connection.exec_driver_sql("DROP TABLE IF EXISTS records_fts")
    Base.metadata.drop_all(connection)
