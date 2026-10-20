# Supermarket Operations

English-language Streamlit application for inventory, purchase orders, partial goods receiving and stock movement history.

## Deploy

Entrypoint: `supermarket_app/app.py`. Python: 3.11.
Install `requirements.txt`. Configure `DATABASE_URL`, `APP_USERNAME`, `APP_PASSWORD_SALT` and `APP_PASSWORD_HASH` using platform secrets.
See [deployment instructions](supermarket_app/deployment/DEPLOYMENT.md).

The repository contains application code only. Database exports and authentication values are not included. Starting the app does not create, reset or restore the database.
