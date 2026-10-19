"""Create dashboard account/session tables without rewriting financial records.

Only new auth table permissions are protected. Production also performs a
read-only audit of existing Supabase table privacy and stops on ambiguity.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.database_setup_service import prepare_database

if __name__ == "__main__":
    prepare_database()
    print("Account/session tables ready; existing financial records and permissions preserved.")
