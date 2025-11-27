"""
Script to create the PostgreSQL database for the procurement platform.
"""

import psycopg
from psycopg import sql

# Database connection parameters
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = ""
DB_NAME = "procurment"


def create_database():
    """Create the database if it doesn't exist."""
    try:
        # Connect to the default 'postgres' database
        conn_string = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname=postgres"

        print(f"Connecting to PostgreSQL server at {DB_HOST}:{DB_PORT}...")
        with psycopg.connect(conn_string, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Check if database exists
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
                exists = cur.fetchone()

                if exists:
                    print(f"✓ Database '{DB_NAME}' already exists.")
                else:
                    # Create the database
                    print(f"Creating database '{DB_NAME}'...")
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME))
                    )
                    print(f"✓ Database '{DB_NAME}' created successfully!")

        # Test connection to the new database
        print(f"\nTesting connection to '{DB_NAME}'...")
        test_conn_string = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(test_conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"✓ Successfully connected to '{DB_NAME}'")
                print(f"  PostgreSQL version: {version.split(',')[0]}")

        return True

    except psycopg.OperationalError as e:
        print(f"✗ Connection error: {e}")
        print("\nPlease check:")
        print("  1. PostgreSQL is running")
        print("  2. Connection parameters are correct")
        print("  3. User has permission to create databases")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("PostgreSQL Database Setup")
    print("=" * 60)
    print()

    success = create_database()

    print()
    print("=" * 60)
    if success:
        print("✓ Database setup completed successfully!")
        print("\nNext steps:")
        print("  1. Run migrations: alembic upgrade head")
        print("  2. Start the application: python startup.py")
    else:
        print("✗ Database setup failed. Please check the errors above.")
    print("=" * 60)
