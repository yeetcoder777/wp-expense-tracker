from app.db.database import Base, engine
from app.db.models import TransactionDB, ConversationState


print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")
