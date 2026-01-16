#!/usr/bin/env python3
"""Check Snowflake account capabilities for Iceberg support."""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        print(f"ERROR: Missing required environment variable: {key}")
        print(f"Add it to your .env file (see .env.example)")
        sys.exit(1)
    return value

def main():
    try:
        import snowflake.connector
    except ImportError:
        print("ERROR: snowflake-connector-python not installed")
        print("Run: ./venv/bin/pip install snowflake-connector-python")
        sys.exit(1)

    account = get_required_env("SNOWFLAKE_ACCOUNT")
    user = get_required_env("SNOWFLAKE_USER")
    password = get_required_env("SNOWFLAKE_PASSWORD")

    print(f"Connecting to Snowflake account: {account}")
    print(f"User: {user}")
    print()

    try:
        conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
        )
        cursor = conn.cursor()

        # Check account edition
        print("=== Account Info ===")
        cursor.execute("SELECT CURRENT_ACCOUNT(), CURRENT_REGION()")
        row = cursor.fetchone()
        print(f"Account: {row[0]}")
        print(f"Region: {row[1]}")

        # Check edition (requires ACCOUNTADMIN or specific privileges)
        try:
            cursor.execute("SHOW ORGANIZATION ACCOUNTS")
            print("Organization accounts available")
        except:
            pass

        # Check if we can see available warehouses
        print("\n=== Available Warehouses ===")
        cursor.execute("SHOW WAREHOUSES")
        warehouses = cursor.fetchall()
        for wh in warehouses[:5]:  # Show first 5
            print(f"  - {wh[0]} (size: {wh[3]}, state: {wh[4]})")
        if len(warehouses) > 5:
            print(f"  ... and {len(warehouses) - 5} more")

        # Check databases
        print("\n=== Available Databases ===")
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        for db in databases[:10]:
            print(f"  - {db[1]}")
        if len(databases) > 10:
            print(f"  ... and {len(databases) - 10} more")

        # Check for Iceberg support by looking at parameters
        print("\n=== Iceberg Table Support ===")
        try:
            # Try to check if Iceberg tables are enabled
            cursor.execute("""
                SELECT SYSTEM$ALLOWLIST()
            """)
            print("External access functions available")
        except Exception as e:
            pass

        # Check for external volume (needed for Iceberg)
        print("\n=== External Volumes (for Iceberg) ===")
        try:
            cursor.execute("SHOW EXTERNAL VOLUMES")
            volumes = cursor.fetchall()
            if volumes:
                for vol in volumes:
                    print(f"  - {vol[1]}")
            else:
                print("  No external volumes configured yet")
                print("  (You can create one to connect to your S3 bucket)")
        except Exception as e:
            print(f"  Cannot list external volumes: {e}")
            print("  (May require specific privileges)")

        # Check current role
        print("\n=== Your Current Role ===")
        cursor.execute("SELECT CURRENT_ROLE()")
        role = cursor.fetchone()[0]
        print(f"Role: {role}")

        # Try to determine edition from available features
        print("\n=== Feature Check ===")

        # Check for data sharing (Enterprise+)
        try:
            cursor.execute("SHOW SHARES")
            print("  ✓ Data Sharing available")
        except:
            print("  ✗ Data Sharing not available")

        # Check for materialized views (Enterprise+)
        try:
            cursor.execute("SHOW MATERIALIZED VIEWS IN ACCOUNT")
            print("  ✓ Materialized Views available")
        except:
            print("  ? Materialized Views (need db context)")

        print("\n=== Recommendation ===")
        print("Iceberg Tables require Enterprise Edition or higher.")
        print("If you have Standard Edition, use Option B (load data into native Snowflake tables).")
        print("If you have Enterprise Edition, you can use Option C (Snowflake reads Iceberg directly).")
        print()
        print("To check your edition, log into Snowflake web UI and look at:")
        print("  Admin -> Account -> Edition")
        print()
        print("Or ask your Snowflake admin for the account edition.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"ERROR connecting to Snowflake: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
