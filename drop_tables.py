from app.database.database import engine
from app.models.base import Base
import app.companies.model
import app.users.model
import app.auth.model
import app.apps.model

print("Dropping all existing tables to allow Alembic to generate a full initial migration...")
Base.metadata.drop_all(bind=engine)
print("Done.")
