import { db } from "@/utils/offline/db";
import { call } from "@/utils/apiWrapper";
import { isOffline } from "@/utils/offline/offlineState";

export const CUSTOMER_BENEFIT_FIELDS = {
  loyalty: "custom_pos_disable_loyalty",
  wallet: "custom_pos_disable_wallet",
  credit: "custom_pos_disable_credit",
};

export function customerFeatureDisabled(customer, feature) {
  const field = CUSTOMER_BENEFIT_FIELDS[feature];
  if (!field) throw new Error("Unknown customer benefit");
  if (!customer || typeof customer !== "object" || customer[field] == null) return true;
  return [true, 1, "1"].includes(customer[field]);
}
export const customerLoyaltyDisabled = customer => customerFeatureDisabled(customer, "loyalty");
export const customerWalletDisabled = customer => customerFeatureDisabled(customer, "wallet");
export const customerCreditDisabled = customer => customerFeatureDisabled(customer, "credit");

export async function resolveCustomerBenefitPolicy(customer) {
  const id = typeof customer === "string" ? customer : customer?.name;
  if (!id) return customer;
  const base = typeof customer === "object" ? customer : {name:id, customer_name:id};
  let resolved = await db.customers.get(id);
  if (!isOffline() && !id.startsWith("pos_customer_")) {
    try {
      const response = await call("pos_next.api.customers.get_customer_details", {customer:id});
      const latest = response?.message || response;
      if (latest?.name === id && Object.values(CUSTOMER_BENEFIT_FIELDS).every(f => latest[f] != null)) {
        resolved = {...resolved, ...latest};
        await db.customers.put(resolved);
      }
    } catch (_) { /* Keep cached policy; the server checks the live settings. */ }
  }
  return {...base, ...resolved};
}

export function validateCustomerBenefitPayment(customer, payments, total, creditSale = false) {
  if (customerWalletDisabled(customer) && payments.some(row => Number(row.amount || 0) !== 0 && row.is_wallet_payment)) {
    throw new Error("Customer wallet is disabled for this customer.");
  }
  if (!customerCreditDisabled(customer)) return;
  if (creditSale || payments.some(row => Number(row.amount || 0) !== 0 &&
      (row.is_customer_credit || row.mode_of_payment === "POSNext Customer Credit"))) {
    throw new Error("Customer credit is disabled for this customer.");
  }
  const paid = payments.reduce((sum,row) => sum + Number(row.amount || 0),0);
  if (Math.round((Number(total) - paid) * 1000) > 0) {
    throw new Error("Customer credit is disabled. This POS sale must be fully paid.");
  }
}
