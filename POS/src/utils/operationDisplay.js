// Display-only snapshot. Never send PINs, authorization, ledger actions or refunds.
const numeric = value => { const n = Number(value || 0); return Number.isFinite(n) ? n : 0; };
export function buildOperationDisplay(base, snapshot, serializeItem) {
  const v = base.visibility || {};
  const mode = snapshot.mode === 'EXCHANGE' ? 'EXCHANGE' : 'RETURN';
  const rawItems = (snapshot.items || []).filter(row => Math.abs(numeric(row.quantity ?? row.qty)) > 0);
  const items = rawItems.map((row, index) => {
    const quantity = Math.abs(numeric(row.quantity ?? row.qty));
    const item = serializeItem({...row, quantity, qty:quantity, amount:Math.abs(numeric(row.amount ?? numeric(row.rate) * quantity))});
    return {...item, display_key:operationRowKey(row,index),
      item_name:v.item_name === false ? null : item.item_name,
      barcode:v.barcode === false ? null : item.barcode,
      image:v.product_image === false ? null : item.image,
      quantity:v.quantity === false && v.running_qty === false ? null : item.quantity,
      original_price:v.original_price === false ? null : item.original_price,
      discount_amount:v.discount_amount === false ? null : item.discount_amount,
      discount_percentage:v.discount_percentage === false ? null : item.discount_percentage,
      final_price:v.final_price === false ? null : item.final_price,
      line_total:v.final_price === false ? null : item.line_total,
    };
  });
  const subtotal = rawItems.reduce((sum,row) => sum + Math.abs(numeric(row.amount ?? numeric(row.rate) * numeric(row.quantity ?? row.qty))),0);
  const total = Math.abs(numeric(snapshot.total ?? subtotal));
  const focus = Number.isInteger(snapshot.focus_index) ? snapshot.focus_index : items.length-1;
  return {...base, mode, transaction_mode:mode, customer_search_preview:'',
    customer:v.customer_name === false ? null : {name:snapshot.customer_name || snapshot.customer?.customer_name || snapshot.customer?.name || (typeof snapshot.customer === 'string' ? snapshot.customer : '')},
    items, current_item:items[focus] || null, latest_item_index:focus,
    latest_quantity_delta:v.quantity === false ? null : snapshot.focus_delta ?? null,
    operation_change_id:snapshot.change_id ?? 0, payment:null,
    totals:{quantity:v.running_qty === false ? null : rawItems.reduce((sum,row) => sum + Math.abs(numeric(row.quantity ?? row.qty)),0),
      subtotal:v.subtotal === false ? null : subtotal, discount:null, grand_total:v.grand_total === false ? null : total},
    transaction:{type:mode, phase:'PREVIEW', stage:snapshot.stage || 'RETURN_ITEMS',
      reference_invoice:v.invoice_number === false ? null : (snapshot.reference_invoice || ''),
      return_credit:v.grand_total === false || snapshot.return_credit == null ? null : Math.abs(numeric(snapshot.return_credit)),
      estimated_difference:v.grand_total === false || snapshot.return_credit == null ? null : numeric(snapshot.total ?? subtotal)-Math.abs(numeric(snapshot.return_credit))},
  };
}

// Compare quantities by stable row identity, not by list position. A repeated
// scan can change an existing row in the middle of the list.
export function operationRowKey(row, index) {
  return String(row.display_key || `${row.item_code || ''}|${row.uom || ''}|${index}`);
}
export function trackOperationFocus(previous, next) {
  const before = (previous?.items || []).filter(row => Math.abs(numeric(row.quantity ?? row.qty)) > 0);
  const old = new Map(before.map((row,index) => [operationRowKey(row,index), Math.abs(numeric(row.quantity ?? row.qty))]));
  const current = (next?.items || []).filter(row => Math.abs(numeric(row.quantity ?? row.qty)) > 0);
  let index = -1, delta = 0;
  current.forEach((row,i) => {
    const key = operationRowKey(row,i), qty = Math.abs(numeric(row.quantity ?? row.qty));
    const difference = qty - (old.get(key) || 0);
    if (difference !== 0) { index = i; delta = difference; }
    old.delete(key);
  });
  if (index >= 0) return {index, delta, changed:true};
  if (old.size) {
    const previousIndex = Number(previous?.focus_index ?? 0);
    return {index:current.length ? Math.min(Math.max(previousIndex,0),current.length-1) : -1, delta:0, changed:true};
  }
  return {index:current.length ? Math.min(Math.max(Number(previous?.focus_index ?? current.length-1),0),current.length-1) : -1, delta:0, changed:false};
}
