"""English staff interface for inventory, purchasing and goods receiving."""
import logging
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st

from auth import require_login, sign_out
from db import query
from product_search import matches_product
from workspace_header import supermarket_border, workspace_header
from service import (BusinessError, create_order, submit_order, order_details,
                     create_receipt, confirm_receipt)

st.set_page_config(page_title='Supermarket Operations', page_icon='🛒', layout='wide')
# Load the shared visual theme without changing business logic or widget keys.
styles = Path(__file__).with_name('styles.css').read_text()
st.markdown(f'<style>{styles}</style>', unsafe_allow_html=True)

# No business page or database query is reachable before successful sign-in.
require_login()

COLUMN_LABELS = {
    'product_id': 'Product ID', 'product_name': 'Product', 'unit': 'Selling unit',
    'unit_size': 'Pack size', 'quantity_on_hand': 'Stock on hand',
    'reorder_level': 'Reorder level', 'low_stock': 'Low stock',
    'purchase_order_line_id': 'Order line ID', 'purchase_order_id': 'Order ID',
    'ordered_quantity': 'Ordered', 'unit_purchase_price': 'Unit price',
    'received': 'Received', 'remaining': 'Remaining to receive',
    'remaining_before_receipt': 'Remaining before receipt',
    'remaining_after_receipt': 'Remaining after confirmation',
    'supply_price': 'Supplier unit price', 'mini_order_quantity': 'Minimum order',
    'receipt_id': 'Receipt ID', 'receipt_line_id': 'Receipt line ID',
    'quantity_received': 'This delivery', 'receipt_date': 'Receipt date',
    'received_by': 'Received by', 'status': 'Status', 'movement_id': 'Movement ID',
    'store_name': 'Store', 'quantity_change': 'Quantity change',
    'movement_type': 'Movement type', 'movement_date': 'Movement date',
    'after_confirmation': 'Stock after confirmation', 'line_total': 'Line total',
    'supplier_name': 'Supplier', 'order_date': 'Order date',
}
STATUS = {'Draft': 'Draft', 'Submitted': 'Submitted',
          'PartiallyReceived': 'Partially received', 'Completed': 'Completed',
          'Confirmed': 'Confirmed'}


def navigate(**values):
    """Apply navigation on the next run, before the target widgets are created."""
    st.session_state['_navigation'] = values
    st.rerun()


def action(fn, *args, message, destination=None, reset_prefix=None):
    """Keep invalid input intact; clear completed forms and show the saved record."""
    try:
        result = fn(*args)
    except BusinessError as exc:
        st.error(str(exc))
    except psycopg.Error:
        logging.exception('Database operation failed')
        st.error('Could not save your changes. Nothing was saved. Refresh and try again, or contact the administrator.')
    else:
        st.session_state['notice'] = message(result)
        if reset_prefix:
            for key in list(st.session_state):
                if key.startswith(reset_prefix):
                    del st.session_state[key]
        if destination:
            st.session_state['_navigation'] = destination(result)
        st.rerun()


def table(rows, columns=None):
    if not rows:
        st.info('No records match these filters. Try a different search or filter.')
        return
    frame = pd.DataFrame(rows)
    if columns:
        frame = frame[[c for c in columns if c in frame.columns]]
    for col in ('status', 'order_status'):
        if col in frame:
            frame[col] = frame[col].map(lambda x: STATUS.get(x, x))
    st.dataframe(frame, hide_index=True, width='stretch', column_config=COLUMN_LABELS)


def selector(label, rows, field, key, formatter):
    ids = [r[field] for r in rows]
    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]
    return st.selectbox(label, ids, key=key, format_func=formatter)


def store_picker(stores, label, key, include_all=False):
    options = ([{'store_id': 0, 'store_name': 'All stores'}] if include_all else []) + stores
    names = {r['store_id']: r['store_name'] for r in options}
    return selector(label, options, 'store_id', key, names.get)


def choose_order(rows, key):
    labels = {r['purchase_order_id']: f"PO{r['purchase_order_id']:03d} · {r['store_name']} · {r['supplier_name']}" for r in rows}
    return selector('Purchase order', rows, 'purchase_order_id', key, labels.get)


def inventory_page(stores):
    workspace_header('Inventory', 'Find products that need replenishment, then create a purchase order.', 'inventory')
    left, right = st.columns([1, 2])
    with left:
        store_id = store_picker(stores, 'Store', 'inventory_store')
    with right:
        search = st.text_input('Search products', placeholder='Product ID (exact) or product name', key='inventory_search',
                               help='Enter 1 to find only product 1. Text searches product names, ignoring case. Press Enter to search.')
    rows = query('''SELECT p.product_id,p.product_name,COALESCE(p.unit,'Selling unit') AS unit,
        p.unit_size,p.category,i.quantity_on_hand,i.reorder_level,
        (i.quantity_on_hand<i.reorder_level) AS low_stock
        FROM inventory i JOIN product p USING(product_id)
        WHERE i.store_id=%s ORDER BY low_stock DESC,p.product_name''', (store_id,))
    low_count = sum(r['low_stock'] for r in rows)
    c1, c2 = st.columns(2)
    c1.metric('Products at this store', len(rows))
    c2.metric('Need replenishment', low_count)
    low_only = st.toggle('Show low-stock products only', key='low_only')
    filtered = [r for r in rows if (not low_only or r['low_stock']) and
                matches_product(r, search)]
    st.caption(f'{len(filtered)} products shown · Low-stock products appear first.')
    st.caption('All quantities count selling units (individual packs or items). Pack size describes the product; no unit conversion is applied.')
    table(filtered, ['product_id','product_name','unit_size','quantity_on_hand','reorder_level','low_stock'])
    if st.button('Create a purchase order', key='replenish', type='primary'):
        navigate(page='Purchase Orders', po_mode='Create order', new_po_store=store_id)


def review_orders(orders, stores):
    c1, c2 = st.columns(2)
    with c1:
        status_filter = st.selectbox('Order status', ['All statuses'] + list(STATUS)[:4],
                                    format_func=lambda x: STATUS.get(x, x), key='po_filter')
    with c2:
        store_id = store_picker(stores, 'Store', 'po_store_filter', include_all=True)
    filtered = [r for r in orders if (status_filter=='All statuses' or r['order_status']==status_filter)
                and (not store_id or r['store_id']==store_id)]
    if not filtered:
        st.info('No purchase orders match these filters. Change the filters or choose Create order.')
        return
    # Stable ordering keeps the selected order visible after its status changes.
    filtered.sort(key=lambda r: -r['purchase_order_id'])
    order_id = choose_order(filtered, 'po_view')
    selected = next(r for r in filtered if r['purchase_order_id']==order_id)
    details = order_details(order_id)
    st.subheader(f'PO{order_id:03d} · {STATUS[selected["order_status"]]}')
    st.caption(f"{selected['store_name']} · {selected['supplier_name']} · Ordered {selected['order_date']}")
    total = sum(r['ordered_quantity']*r['unit_purchase_price'] for r in details)
    ordered = sum(r['ordered_quantity'] for r in details)
    received = sum(r['received'] for r in details)
    c1, c2, c3 = st.columns(3)
    c1.metric('Order total', f'${total:,.2f}')
    c2.metric('Product lines', len(details))
    c3.metric('Lines fully received', sum(r['remaining']==0 for r in details))
    if selected['order_status'] != 'Draft' and ordered:
        st.progress(min(received/ordered, 1.0), text=f'{received} of {ordered} selling units received across all lines')
    table(details, ['product_name','unit_size','unit','ordered_quantity','received','remaining','unit_purchase_price'])
    if selected['order_status']=='Draft':
        st.info('Ready to order? Submitting makes this order available for receiving. Stock will not change.')
        if st.button('Submit Purchase Order', key='submit_po', type='primary'):
            action(submit_order, order_id, message=lambda _:f'PO{order_id:03d} submitted. You can now record a delivery.')
    elif selected['order_status'] in ('Submitted','PartiallyReceived'):
        if st.button('Record a delivery for this order', key='receive_order', type='primary'):
            navigate(page='Goods Receiving', receiving_mode='Record delivery', receipt_order=order_id)
    else:
        st.success('All order lines have been received.')


def new_order(stores):
    st.subheader('Create a purchase order')
    st.caption('1. Choose a store and supplier   →   2. Select products   →   3. Review and save')
    store_id = store_picker(stores, 'Receiving store', 'new_po_store')
    suppliers = query("SELECT * FROM supplier WHERE supplier_status='Active' ORDER BY supplier_name")
    if not suppliers:
        st.info('No active suppliers are available. Ask an administrator to set up a supplier.')
        return
    names = {r['supplier_id']:r['supplier_name'] for r in suppliers}
    supplier_id = selector('Supplier', suppliers, 'supplier_id', 'new_po_supplier', names.get)
    supply = query('''SELECT sp.product_id,p.product_name,COALESCE(p.unit,'Selling unit') AS unit,
        p.unit_size,sp.supply_price,sp.mini_order_quantity FROM supplierproduct sp JOIN product p USING(product_id)
        WHERE sp.supplier_id=%s AND sp.supply_status='Active' AND p.product_status='Active'
        ORDER BY p.product_name''', (supplier_id,))
    available = [r for r in supply if r['supply_price'] is not None and r['mini_order_quantity'] is not None]
    if not available:
        st.info('This supplier has no products with a configured price and minimum order quantity.')
        return
    lookup = {r['product_id']:r for r in available}
    prefix = f'cart_{store_id}_{supplier_id}_'
    # Keep the order independent of search results and the dropdown's fuzzy filter.
    selected_ids = [pid for pid in st.session_state.get(prefix+'products', []) if pid in lookup]
    st.session_state[prefix+'products'] = selected_ids
    search = st.text_input('Search products', placeholder='Product ID (exact) or product name', key=prefix+'search',
                           help='Enter 1 to find only product 1. Text searches product names, ignoring case. Press Enter to search.')
    matches = [pid for pid, row in lookup.items() if matches_product(row, search)]
    st.caption('Enter a number for an exact product ID, or part of a product name. Press Enter to search. Only this supplier’s available products are shown.')
    if matches:
        product_id = st.selectbox('Matching products', matches, key=prefix+'match',
            format_func=lambda x:f"ID {x} · {lookup[x]['product_name']} · {lookup[x]['unit_size'] or 'Pack size not specified'} · ${lookup[x]['supply_price']:.2f}")
        if st.button('Add product to order', key=prefix+'add', disabled=product_id in selected_ids):
            st.session_state[prefix+'products'] = selected_ids + [product_id]
            st.rerun()
        if product_id in selected_ids:
            st.caption('This product is already in your order. Adjust its quantity below.')
    else:
        st.info('No matching products are available from this supplier. Try another ID or name.')
    st.caption(f'{len(selected_ids)} products in this order. Changing the search keeps your selected products and quantities.')
    quantities = st.session_state.setdefault(prefix+'quantities', {})
    lines, total = [], Decimal('0')
    for product_id in selected_ids:
        row = lookup[product_id]
        with st.container(border=True):
            st.markdown(f"**{row['product_name']}**")
            st.caption(f"Product ID {product_id} · {row['unit_size'] or 'Pack size not specified'} · {row['unit']} · ${row['supply_price']:.2f} per unit · Minimum {row['mini_order_quantity']}")
            qty = st.number_input(f"Order quantity · {row['product_name']}", min_value=int(row['mini_order_quantity']),
                                  value=max(int(row['mini_order_quantity']), quantities.get(product_id, int(row['mini_order_quantity']))),
                                  step=1, key=prefix+str(product_id))
            quantities[product_id] = qty
            subtotal = qty*row['supply_price']
            st.caption(f'Line total: ${subtotal:,.2f}')
            if st.button('Remove product', key=prefix+'remove_'+str(product_id)):
                st.session_state[prefix+'products'] = [pid for pid in selected_ids if pid != product_id]
                st.session_state.pop(prefix+str(product_id), None)
                quantities.pop(product_id, None)
                st.rerun()
            total += subtotal
            lines.append({'product_id':product_id,'ordered_quantity':qty})
    st.metric('Draft total', f'${total:,.2f}')
    st.caption('Saving creates a draft for review. Stock is unchanged. Current supplier prices are checked again when saved.')
    if st.button('Save Draft Purchase Order', key='save_po', type='primary', disabled=not lines):
        action(create_order, store_id, supplier_id, lines,
               message=lambda oid:f'PO{oid:03d} created. Review the order below, then submit it when ready.',
               destination=lambda oid:dict(po_mode='Review orders',po_filter='All statuses',po_store_filter=0,po_view=oid),
               reset_prefix=prefix)


def purchase_page(orders, stores):
    workspace_header('Purchase orders', 'Prepare replenishment orders and track what has arrived.', 'purchasing')
    mode = st.radio('Workspace', ['Review orders','Create order'], horizontal=True, key='po_mode')
    if mode=='Review orders':
        review_orders(orders, stores)
    else:
        new_order(stores)


def review_receipts(receipts):
    scope = st.radio('Receipt status', ['Awaiting confirmation','All receipts'], horizontal=True, key='receipt_filter')
    filtered = [r for r in receipts if scope=='All receipts' or r['status']=='Draft']
    if not filtered:
        st.info('No receipts awaiting confirmation.' if scope!='All receipts' else 'No receipts yet.')
        if st.button('Record a new delivery', key='new_delivery_empty'):
            navigate(receiving_mode='Record delivery')
        return
    labels = {r['receipt_id']:f"Receipt {r['receipt_id']} · PO{r['purchase_order_id']:03d} · {r['store_name']} · {STATUS[r['status']]}" for r in filtered}
    rid = selector('Goods receipt', filtered, 'receipt_id','receipt_view',labels.get)
    selected = next(r for r in filtered if r['receipt_id']==rid)
    st.subheader(f"Receipt {rid} · {STATUS[selected['status']]}")
    st.caption(f"{selected['store_name']} · {selected['supplier_name']} · {selected['receipt_date']} · Received by {selected['received_by'] or 'Not specified'}")
    rows = query('''SELECT gl.receipt_line_id,pol.purchase_order_line_id,p.product_name,
        COALESCE(p.unit,'Selling unit') AS unit,p.unit_size,gl.quantity_received,i.quantity_on_hand
        FROM goodsreceiptline gl JOIN purchaseorderline pol USING(purchase_order_line_id)
        JOIN product p USING(product_id) JOIN goodsreceipt gr USING(receipt_id)
        JOIN purchaseorder po ON po.purchase_order_id=gr.purchase_order_id
        LEFT JOIN inventory i ON i.store_id=po.store_id AND i.product_id=pol.product_id
        WHERE gl.receipt_id=%s ORDER BY gl.receipt_line_id''', (rid,))
    outstanding = {r['purchase_order_line_id']:r['remaining'] for r in order_details(selected['purchase_order_id'])}
    for row in rows:
        row['remaining_before_receipt'] = outstanding.get(row['purchase_order_line_id'],0)
        row['remaining_after_receipt'] = row['remaining_before_receipt'] - row['quantity_received']
        row['after_confirmation'] = (row['quantity_on_hand']+row['quantity_received']) if row['quantity_on_hand'] is not None else None
    draft = selected['status']=='Draft'
    columns = ['product_name','unit_size','quantity_received','quantity_on_hand']
    if draft:
        columns += ['remaining_before_receipt','remaining_after_receipt','after_confirmation']
    table(rows, columns)
    if draft:
        st.info('Review the quantities above. Confirming adds this delivery to stock and locks the receipt for editing.')
        st.caption('Remaining before receipt excludes this draft. Remaining after confirmation subtracts this delivery. Both remaining quantities and stock are previews, checked again when you confirm.')
        if st.button('Confirm Receipt', key='confirm_receipt', type='primary', disabled=not rows):
            action(confirm_receipt, rid,
                message=lambda status:f'Receipt {rid} confirmed. Stock and movement history updated. PO{selected["purchase_order_id"]:03d}: {STATUS[status]}.',
                destination=lambda _:dict(receipt_filter='All receipts',receipt_view=rid))
    else:
        st.success('This delivery has been added to stock. It cannot be confirmed again.')
        if st.button('View movements for this receipt',key='view_movements', type='primary'):
            navigate(page='History',history_store=selected['store_id'],history_receipt=str(rid))


def set_delivery_quantities(lines, prefix, fill):
    for line in lines:
        st.session_state[prefix+str(line['purchase_order_line_id'])] = int(line['remaining']) if fill else 0


def record_delivery(orders):
    eligible = [r for r in orders if r['order_status'] in ('Submitted','PartiallyReceived')]
    if not eligible:
        st.info('No orders are available for receiving. Submit a purchase order first.')
        return
    st.subheader('Record a delivery')
    st.caption('Enter what arrived today. You can receive the rest in a later delivery.')
    oid = choose_order(eligible,'receipt_order')
    details = [r for r in order_details(oid) if r['remaining']>0]
    if not details:
        st.info('No items remain to receive. Refresh to load the latest order status.')
        return
    prefix = f'delivery_{oid}_'
    operator = st.text_input('Received by',max_chars=100,key=prefix+'operator',placeholder='Staff name (optional)')
    a,b = st.columns(2)
    a.button('Fill all remaining quantities',key='fill_remaining',on_click=set_delivery_quantities,args=(details,prefix,True))
    b.button('Clear quantities',key='clear_receiving',on_click=set_delivery_quantities,args=(details,prefix,False))
    lines = []
    for row in details:
        line_id = row['purchase_order_line_id']
        key = prefix+str(line_id)
        # Another operator may have received stock since this form was last displayed.
        if key in st.session_state and st.session_state[key]>row['remaining']:
            st.session_state[key] = 0
            st.warning(f"Remaining quantity changed for {row['product_name']}. Please enter the quantity again.")
        with st.container(border=True):
            st.markdown(f"**{row['product_name']}**")
            st.caption(f"{row['unit_size'] or 'Pack size not specified'} · Ordered {row['ordered_quantity']} · Received {row['received']} · Remaining before receipt {row['remaining']}")
            qty = st.number_input(f"Receiving now · {row['product_name']}",min_value=0,max_value=int(row['remaining']),value=0,step=1,key=key)
            if qty:
                lines.append({'purchase_order_line_id':line_id,'quantity_received':qty})
    st.caption(f"This delivery: {len(lines)} product lines · {sum(r['quantity_received'] for r in lines)} selling units")
    st.caption('Saving a draft does not change stock. You will review and confirm it next.')
    if st.button('Save Draft Receipt',key='save_receipt',type='primary',disabled=not lines):
        action(create_receipt,oid,operator,lines,
            message=lambda rid:f'Receipt {rid} saved as a draft. Review the quantities below and confirm when ready.',
            destination=lambda rid:dict(receiving_mode='Review receipts',receipt_filter='Awaiting confirmation',receipt_view=rid),
            reset_prefix=prefix)


def receiving_page(orders, receipts):
    workspace_header('Goods receiving', 'Record deliveries, review quantities and confirm stock updates.', 'receiving')
    st.caption(f"{sum(r['status']=='Draft' for r in receipts)} receipts awaiting confirmation")
    mode = st.radio('Workspace',['Review receipts','Record delivery'],horizontal=True,key='receiving_mode')
    if mode=='Review receipts':
        review_receipts(receipts)
    else:
        record_delivery(orders)


def history_page(receipts, stores):
    workspace_header('History', 'Trace a delivery from its receipt to the stock movements it created.', 'history')
    a,b = st.columns(2)
    with a:
        store_id = store_picker(stores,'Store','history_store',include_all=True)
    with b:
        receipt_search = st.text_input('Receipt ID',placeholder='Leave blank to show all receipts',key='history_receipt').strip()
    if receipt_search and not receipt_search.isdecimal():
        st.warning('Enter a numeric receipt ID, for example 1.')
        return
    rid = int(receipt_search) if receipt_search else None
    filtered = [r for r in receipts if (not store_id or r['store_id']==store_id) and (rid is None or r['receipt_id']==rid)]
    st.subheader('Goods receipts')
    table(filtered,['receipt_id','purchase_order_id','store_name','supplier_name','receipt_date','received_by','status'])
    movements = query('''SELECT sm.movement_id,s.store_name,p.product_name,gr.receipt_id,sm.receipt_line_id,
        sm.quantity_change,sm.movement_type,sm.movement_date FROM stockmovement sm
        JOIN store s USING(store_id) JOIN product p USING(product_id)
        LEFT JOIN goodsreceiptline gl USING(receipt_line_id) LEFT JOIN goodsreceipt gr USING(receipt_id)
        WHERE (%s=0 OR sm.store_id=%s) AND (%s::integer IS NULL OR gr.receipt_id=%s)
        ORDER BY sm.movement_id DESC''',(store_id,store_id,rid,rid))
    st.subheader('Stock movements')
    table(movements,['movement_id','receipt_id','store_name','product_name','quantity_change','movement_date'])
    if movements:
        csv = pd.DataFrame(movements).rename(columns=COLUMN_LABELS).to_csv(index=False).encode('utf-8-sig')
        st.download_button('Download movements (CSV)',csv,'stock_movements.csv','text/csv',key='export_movements')


# Navigation requests are applied before any widgets consume their session keys.
for key,value in st.session_state.pop('_navigation',{}).items():
    st.session_state[key] = value
supermarket_border('top')
heading, account = st.columns([4, 1])
with heading:
    st.title('Supermarket Operations')
with account:
    st.caption(f"Signed in as {st.session_state['authenticated_user']}")
    st.button('Sign out', key='sign_out', on_click=sign_out)
st.caption('Inventory, purchasing and receiving in one workspace')
page = st.radio('Navigation',['Inventory','Purchase Orders','Goods Receiving','History'],horizontal=True,key='page',label_visibility='collapsed')
# A fixed, non-interactive marker scopes the palette to the selected workspace.
module_theme = {'Inventory': 'inventory', 'Purchase Orders': 'purchasing',
                'Goods Receiving': 'receiving', 'History': 'history'}[page]
st.markdown(f'<span class="module-theme" data-module="{module_theme}" aria-hidden="true"></span>', unsafe_allow_html=True)
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))
if st.button('Refresh data',key='refresh',help='Reload current stock and order statuses. Unsaved input stays in this session.'):
    st.rerun()
try:
    stores = query('SELECT * FROM store ORDER BY store_id')
    orders = query('''SELECT po.*,s.store_name,su.supplier_name FROM purchaseorder po
        JOIN store s USING(store_id) JOIN supplier su USING(supplier_id) ORDER BY purchase_order_id''')
    receipts = query('''SELECT gr.*,po.store_id,s.store_name,su.supplier_name FROM goodsreceipt gr
        JOIN purchaseorder po USING(purchase_order_id) JOIN store s USING(store_id)
        JOIN supplier su USING(supplier_id) ORDER BY receipt_id DESC''')
    if not stores:
        st.info('No stores are configured. Ask an administrator to load the initial data.')
    elif page=='Inventory':
        inventory_page(stores)
    elif page=='Purchase Orders':
        purchase_page(orders,stores)
    elif page=='Goods Receiving':
        receiving_page(orders,receipts)
    else:
        history_page(receipts,stores)
    st.divider()
    st.caption('Quantities use the product selling unit. Pack sizes are descriptive; no unit conversion is applied.')
except psycopg.Error:
    logging.exception('Unable to load database')
    st.error('Unable to load data. Check the database connection, then select Refresh data.')
supermarket_border('bottom')
