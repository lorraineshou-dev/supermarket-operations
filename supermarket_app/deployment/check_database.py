"""Read-only database connectivity and table-count checks before deployment.

Set DATABASE_URL in the environment; credentials are never printed.
This script does not create tables, restore a backup, or change business data.
"""
import json
import os
import sys

import psycopg
from psycopg import sql


TABLES = ('store', 'supplier', 'product', 'supplierproduct', 'inventory',
          'purchaseorder', 'purchaseorderline', 'goodsreceipt',
          'goodsreceiptline', 'stockmovement')


def main():
    url = os.environ.get('DATABASE_URL')
    if not url:
        print('DATABASE_URL is required.', file=sys.stderr)
        return 1
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            conn.execute("SET LOCAL statement_timeout = '15s'")
            counts = {}
            for table in TABLES:
                counts[table] = conn.execute(sql.SQL('SELECT count(*) FROM public.{}').format(
                    sql.Identifier(table))).fetchone()[0]
            print(json.dumps({'connection': 'ok', 'table_counts': counts}, indent=2))
        return 0
    except psycopg.Error as exc:
        # Avoid leaking connection strings through database error messages.
        print(f'Database check failed ({type(exc).__name__}). Check connectivity, credentials and schema.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
