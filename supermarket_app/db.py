"""Connections are short-lived; each business operation owns one transaction."""
import os
import psycopg
from psycopg.rows import dict_row


def connect():
    # libpq PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD also work.
    return psycopg.connect(os.environ.get('DATABASE_URL', ''), row_factory=dict_row,
                           connect_timeout=5, options='-c statement_timeout=15000 -c lock_timeout=10000')


def query(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).fetchall()
