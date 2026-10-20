# Deployment plan

Status: public GitHub repository created and current database migrated to Neon. All ten table contents and identity sequence states match the migration source. Application hosting setup is in progress.

## Recommended route

Use the user-selected public GitHub repository and Streamlit Community Cloud with a reachable PostgreSQL database. The entrypoint is `supermarket_app/app.py`. Select Python 3.11. Dependencies are pinned in `supermarket_app/requirements.txt`.

The existing local startup script defaults to `127.0.0.1:55432/supermarket_dev`. That address is local to the computer running the application; it does not provide remote database access. Confirm the database strategy before deployment.

In Community Cloud Advanced settings, configure a root-level secret:

```toml
DATABASE_URL = "postgresql://USERNAME:PASSWORD@DATABASE_HOST:5432/DATABASE_NAME?sslmode=require"
```

Use the database provider's actual connection URL and TLS settings. Never commit a real connection string. Community Cloud makes root-level secrets available as environment variables, matching the existing `db.py` configuration.

For a container host, build the root Dockerfile and configure DATABASE_URL in the host's secret settings. The process uses the platform's PORT variable, defaulting to 8501. Do not run `init_dev.py` or restore backups during application startup.

## Repository contents

Upload application Python files (excluding `init_dev.py`), `styles.css`, `assets/login_market.svg`, dependency files, `.streamlit/config.toml`, the cloud startup script and deployment files. The `deployment_bundle/` directory, when prepared, contains only these deployment files.

Do not upload coursework documents, database backups, `.venv`, secrets, screenshots, or test logs. Tests requiring the source backup should remain local unless a separate private test-fixture strategy is chosen.

## Database strategy

1. Existing hosted database: configure its reachable connection URL; verify its schema and data before starting the app.
2. Migrate current local data: export a fresh snapshot of the running database, including recent manual test changes. Restore once into an empty hosted PostgreSQL database. Do not use the old assignment backup as a substitute for current data. Compare source and destination data, constraints, identity sequences and critical receipt records before switching the app.
3. Keep the same database on this computer: requires an explicitly configured private network path and an always-on computer. Do not expose the local trust-authenticated PostgreSQL port to the internet.

A migrated copy does not synchronize with the local database. Decide which database is authoritative before allowing writes.

## Verification

With DATABASE_URL set securely, run:

```sh
python supermarket_app/deployment/check_database.py
```

This read-only check verifies connectivity and counts the ten required tables. Matching counts alone do not prove all data is identical; compare migration exports and critical records as well.

After deployment, verify login, all four pages, exact product-ID search, and inventory/receipt values against the selected source. Use an explicitly designated test order for any live write tests. Check partial receipts and duplicate-confirm prevention in an isolated test database first.

The deployment copy reads APP_USERNAME, APP_PASSWORD_SALT (hex), and APP_PASSWORD_HASH (PBKDF2-HMAC-SHA256, 600000 iterations, hex) from platform secrets. It refuses access if those values are missing. The local prototype remains unchanged. Never commit the authentication secret values.

## Completion requirements

- A GitHub repository destination and authenticated access.
- A selected application host and access to its deployment dashboard.
- A decision on the database strategy and securely configured credentials.
- A successful remote build, a working URL, and verification from the deployed app.

Local syntax checks or a successful local database connection do not establish remote deployment success.
