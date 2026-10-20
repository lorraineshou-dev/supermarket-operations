"""All writes use transactions. Every receipt writer locks its parent PO first.
This serializes receipts for the same order, including completion-state calculation.
Inventory increments are atomic; product rows are visited in a consistent order.
Draft quantities do not reserve stock or count towards confirmed received quantities.
"""
from db import connect, query


class BusinessError(ValueError):
    pass


def _order(conn, order_id):
    row = conn.execute('SELECT * FROM purchaseorder WHERE purchase_order_id=%s FOR UPDATE', (order_id,)).fetchone()
    if not row:
        raise BusinessError('Purchase order not found.')
    return row


def _lines(conn, order_id):
    return conn.execute('SELECT * FROM purchaseorderline WHERE purchase_order_id=%s ORDER BY product_id FOR UPDATE', (order_id,)).fetchall()


def _validate_supply(conn, supplier_id, lines):
    supplier = conn.execute('SELECT * FROM supplier WHERE supplier_id=%s FOR SHARE', (supplier_id,)).fetchone()
    if not supplier or supplier['supplier_status'] != 'Active':
        raise BusinessError('The supplier does not exist or is inactive.')
    if not lines:
        raise BusinessError('A purchase order must contain at least one line.')
    products = [x['product_id'] for x in lines]
    if len(set(products)) != len(products):
        raise BusinessError('A product cannot appear more than once in a purchase order.')
    for line in sorted(lines, key=lambda x: x['product_id']):
        supply = conn.execute('''SELECT sp.*, p.product_status FROM supplierproduct sp
            JOIN product p USING(product_id) WHERE supplier_id=%s AND product_id=%s FOR SHARE OF sp,p''',
            (supplier_id, line['product_id'])).fetchone()
        if not supply or supply['supply_status'] != 'Active' or supply['product_status'] != 'Active':
            raise BusinessError('The product is not available from this supplier or is inactive.')
        qty = line['ordered_quantity']
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise BusinessError('Order quantities must be positive integers.')
        if supply['mini_order_quantity'] is None or qty < supply['mini_order_quantity']:
            raise BusinessError('The order quantity is below the minimum, or the minimum order quantity has not been configured.')
        price = line.get('unit_purchase_price', supply['supply_price'])
        if price is None or price < 0:
            raise BusinessError('The purchase price is missing or negative.')
        line['unit_purchase_price'] = price


def create_order(store_id, supplier_id, lines):
    lines = [dict(x) for x in lines]
    with connect() as conn:
        if not conn.execute('SELECT 1 FROM store WHERE store_id=%s', (store_id,)).fetchone():
            raise BusinessError('Store not found.')
        # Capture current supplier quote, never accept client-controlled pricing.
        for line in lines:
            line.pop('unit_purchase_price', None)
        _validate_supply(conn, supplier_id, lines)
        order_id = conn.execute('''INSERT INTO purchaseorder (supplier_id,store_id,order_date)
            VALUES (%s,%s,CURRENT_DATE) RETURNING purchase_order_id''', (supplier_id,store_id)).fetchone()['purchase_order_id']
        for x in lines:
            conn.execute('''INSERT INTO purchaseorderline (purchase_order_id,product_id,ordered_quantity,unit_purchase_price)
                VALUES (%s,%s,%s,%s)''', (order_id,x['product_id'],x['ordered_quantity'],x['unit_purchase_price']))
        return order_id


def submit_order(order_id):
    with connect() as conn:
        order = _order(conn, order_id)
        if order['order_status'] != 'Draft':
            raise BusinessError('This purchase order has already been submitted or received and cannot be submitted again.')
        _validate_supply(conn, order['supplier_id'], _lines(conn, order_id))
        conn.execute("UPDATE purchaseorder SET order_status='Submitted' WHERE purchase_order_id=%s", (order_id,))


def order_details(order_id):
    return query('''SELECT pol.purchase_order_line_id,pol.product_id,p.product_name,
        COALESCE(p.unit,'Selling unit') AS unit,p.unit_size,pol.ordered_quantity,pol.unit_purchase_price,
        COALESCE(r.received,0)::integer AS received,
        (pol.ordered_quantity-COALESCE(r.received,0))::integer AS remaining
        FROM purchaseorderline pol JOIN product p USING(product_id)
        LEFT JOIN (SELECT gl.purchase_order_line_id,SUM(gl.quantity_received) AS received
            FROM goodsreceiptline gl JOIN goodsreceipt gr USING(receipt_id)
            WHERE gr.status='Confirmed' GROUP BY gl.purchase_order_line_id) r USING(purchase_order_line_id)
        WHERE pol.purchase_order_id=%s ORDER BY pol.product_id''', (order_id,))


def _validate_receipt(conn, order_id, lines, po_lines):
    if not lines:
        raise BusinessError('A receipt must contain at least one line with a positive quantity.')
    ids = [x['purchase_order_line_id'] for x in lines]
    if len(set(ids)) != len(ids):
        raise BusinessError('A purchase order line cannot appear more than once in a receipt.')
    known = {x['purchase_order_line_id']:x for x in po_lines}
    for x in lines:
        if x['purchase_order_line_id'] not in known:
            raise BusinessError('A receipt line does not belong to this purchase order.')
        qty = x['quantity_received']
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise BusinessError('Received quantities must be positive integers.')
        received = conn.execute('''SELECT COALESCE(SUM(gl.quantity_received),0) AS qty
            FROM goodsreceiptline gl JOIN goodsreceipt gr USING(receipt_id)
            WHERE gl.purchase_order_line_id=%s AND gr.status='Confirmed' ''', (x['purchase_order_line_id'],)).fetchone()['qty']
        if received + qty > known[x['purchase_order_line_id']]['ordered_quantity']:
            raise BusinessError('This delivery exceeds the outstanding quantity. Refresh and try again.')


def create_receipt(order_id, received_by, lines):
    with connect() as conn:
        order = _order(conn, order_id)
        if order['order_status'] not in ('Submitted','PartiallyReceived'):
            raise BusinessError('Receipts can only be created for submitted orders that are not fully received.')
        _validate_receipt(conn, order_id, lines, _lines(conn, order_id))
        receipt_id = conn.execute('''INSERT INTO goodsreceipt (purchase_order_id,receipt_date,received_by)
            VALUES (%s,CURRENT_DATE,%s) RETURNING receipt_id''', (order_id,received_by.strip() or None)).fetchone()['receipt_id']
        for x in lines:
            conn.execute('''INSERT INTO goodsreceiptline (receipt_id,purchase_order_line_id,quantity_received)
                VALUES (%s,%s,%s)''', (receipt_id,x['purchase_order_line_id'],x['quantity_received']))
        return receipt_id


def confirm_receipt(receipt_id):
    with connect() as conn:
        ref = conn.execute('SELECT purchase_order_id FROM goodsreceipt WHERE receipt_id=%s', (receipt_id,)).fetchone()
        if not ref:
            raise BusinessError('Goods receipt not found.')
        order = _order(conn, ref['purchase_order_id'])
        receipt = conn.execute('SELECT * FROM goodsreceipt WHERE receipt_id=%s FOR UPDATE', (receipt_id,)).fetchone()
        if not receipt or receipt['purchase_order_id'] != order['purchase_order_id']:
            raise BusinessError('The receipt has changed. Please refresh.')
        if receipt['status'] != 'Draft':
            raise BusinessError('This receipt has already been confirmed. Stock cannot be added again.')
        if order['order_status'] not in ('Submitted','PartiallyReceived'):
            raise BusinessError('The purchase order has not been submitted or is already fully received.')
        po_lines = _lines(conn, order['purchase_order_id'])
        lines = conn.execute('SELECT * FROM goodsreceiptline WHERE receipt_id=%s ORDER BY receipt_line_id FOR UPDATE', (receipt_id,)).fetchall()
        _validate_receipt(conn, order['purchase_order_id'], lines, po_lines)
        products = {x['purchase_order_line_id']:x['product_id'] for x in po_lines}
        for x in sorted(lines, key=lambda x:products[x['purchase_order_line_id']]):
            product_id = products[x['purchase_order_line_id']]
            conn.execute('''INSERT INTO stockmovement (store_id,product_id,receipt_line_id,quantity_change,movement_type)
                VALUES (%s,%s,%s,%s,'Receipt')''', (order['store_id'],product_id,x['receipt_line_id'],x['quantity_received']))
            # Initial dataset covers all products/stores. Missing inventory requires explicit setup.
            updated = conn.execute('''UPDATE inventory SET quantity_on_hand=quantity_on_hand+%s
                WHERE store_id=%s AND product_id=%s RETURNING quantity_on_hand''',
                (x['quantity_received'],order['store_id'],product_id)).fetchone()
            if not updated:
                raise BusinessError('No inventory record exists for this store and product. Create it before receiving. This operation was rolled back.')
        conn.execute("UPDATE goodsreceipt SET status='Confirmed' WHERE receipt_id=%s", (receipt_id,))
        remaining = conn.execute('''SELECT COUNT(*) AS n FROM purchaseorderline pol
            WHERE purchase_order_id=%s AND ordered_quantity > (
                SELECT COALESCE(SUM(gl.quantity_received),0) FROM goodsreceiptline gl
                JOIN goodsreceipt gr USING(receipt_id)
                WHERE gl.purchase_order_line_id=pol.purchase_order_line_id AND gr.status='Confirmed')''',
            (order['purchase_order_id'],)).fetchone()['n']
        status = 'PartiallyReceived' if remaining else 'Completed'
        conn.execute('UPDATE purchaseorder SET order_status=%s WHERE purchase_order_id=%s', (status,order['purchase_order_id']))
        return status
