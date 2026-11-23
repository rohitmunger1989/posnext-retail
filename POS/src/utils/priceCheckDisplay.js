// Public product/price fields only: never broadcast customer or payment data.
export function priceCheckSnapshot(data) {
  if (!data?.item) return null;
  const price=row=>row ? {price_list:row.price_list,currency:row.currency,uom:row.uom,rate:row.rate ?? null} : null;
  return {item:{item_code:data.item.item_code,item_name:data.item.item_name,brand:data.item.brand || '',image:data.item.image || '',barcode:data.item.barcode || '',uom:data.item.uom,
    attributes:(data.item.attributes || []).map(row=>({attribute:row.attribute,value:row.value}))},
    selling:price(data.selling),comparison:price(data.comparison),
    store:data.store ? {profile:data.store.profile,warehouse:data.store.warehouse,label:data.store.label} : null,
    stock:data.stock ? {available_qty:data.stock.available_qty ?? null,uom:data.stock.uom,tracked:!!data.stock.tracked} : null,
    offer:data.offer ? {savings:data.offer.savings,discount_percentage:data.offer.discount_percentage,currency:data.offer.currency} : null};
}
