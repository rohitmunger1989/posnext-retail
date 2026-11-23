/** Same canonical comparison as the POS server; local eight-digit imports are Kuwait numbers. */
export function normalizeCustomerMobile(value) {
    let digits = String(value || '').replace(/[^0-9]/g, '');
    if (digits.startsWith('00')) digits = digits.slice(2);
    if (digits.length === 8) digits = '965' + digits;
    return digits;
}
