<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="cashier-success-overlay"
			role="dialog"
			aria-modal="true"
			aria-labelledby="cashier-success-title"
		>
			<div class="cashier-success-window">
				<div class="cashier-success-content">
					<div class="success-check" aria-hidden="true">✓</div>

					<h1 id="cashier-success-title">{{ __("Thank You") }}</h1>
					<p class="success-subtitle">{{ __("Payment completed successfully") }}</p>

					<div v-if="invoiceName" class="invoice-number">{{ invoiceName }}</div>

					<section class="payment-card">
						<div class="card-title">{{ __("Payment") }}</div>

						<div v-if="normalizedMethods.length" class="payment-methods">
							<div
								v-for="(method, index) in normalizedMethods"
								:key="`${method.mode_of_payment}-${index}`"
								class="payment-method-row"
							>
								<span>{{ method.mode_of_payment || __("Payment") }}</span>
								<strong>{{ formatCurrency(method.amount) }}</strong>
							</div>
						</div>

						<div class="payment-tiles" :class="{ 'single-tile': changeAmount <= 0 }">
							<div class="payment-tile paid">
								<span>{{ __("Paid") }}</span>
								<strong>{{ formatCurrency(paidAmount) }}</strong>
							</div>

							<div v-if="changeAmount > 0" class="payment-tile change">
								<span>{{ __("Change Due") }}</span>
								<strong>{{ formatCurrency(changeAmount) }}</strong>
							</div>
						</div>
					</section>

					<button ref="newSaleButton" type="button" class="new-sale-button" @click="handleNewSale">
						{{ __("New Sale") }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { formatCurrency as formatCurrencyUtil } from "@/utils/currency";

const props = defineProps({
	modelValue: {
		type: Boolean,
		default: false,
	},
	invoiceName: {
		type: String,
		default: "",
	},
	paidAmount: {
		type: Number,
		default: 0,
	},
	changeAmount: {
		type: Number,
		default: 0,
	},
	paymentMethods: {
		type: Array,
		default: () => [],
	},
	currency: {
		type: String,
		default: "KWD",
	},
});

const emit = defineEmits(["update:modelValue", "new-sale"]);
const newSaleButton = ref(null);

const normalizedMethods = computed(() =>
	(props.paymentMethods || [])
		.filter((row) => Math.abs(Number(row?.amount || 0)) > 0.000001)
		.map((row) => ({
			mode_of_payment: row?.mode_of_payment || row?.method || row?.type || __("Payment"),
			amount: Number(row?.amount || 0),
		}))
);

function formatCurrency(amount) {
	return formatCurrencyUtil(Number(amount || 0), props.currency);
}

function handleNewSale() {
	emit("new-sale");
	emit("update:modelValue", false);
}

watch(
	() => props.modelValue,
	async (isOpen) => {
		if (!isOpen) return;
		await nextTick();
		newSaleButton.value?.focus?.();
	}
);
</script>

<style scoped>
.cashier-success-overlay {
	position: fixed;
	inset: 0;
	z-index: 1000;
	display: flex;
	align-items: stretch;
	justify-content: stretch;
	background: rgba(0, 0, 0, 0.28);
	padding: clamp(6px, 1.2vw, 18px);
}

.cashier-success-window {
	width: 100%;
	height: 100%;
	min-width: 0;
	min-height: 0;
	overflow: auto;
	border-radius: clamp(12px, 1.4vw, 22px);
	background: #f7f7f5;
	box-shadow: 0 24px 70px rgba(0, 0, 0, 0.2);
	display: flex;
	align-items: center;
	justify-content: center;
	padding:
		clamp(18px, 4vh, 56px)
		clamp(14px, 4vw, 72px);
}

.cashier-success-content {
	width: min(100%, 720px);
	display: flex;
	flex-direction: column;
	align-items: stretch;
}

.success-check {
	width: clamp(58px, 8vh, 86px);
	height: clamp(58px, 8vh, 86px);
	margin: 0 auto;
	border-radius: 999px;
	background: #fff;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: clamp(34px, 5vh, 54px);
	line-height: 1;
	font-weight: 500;
	color: #111;
}

h1 {
	margin: clamp(18px, 3vh, 34px) 0 0;
	text-align: center;
	font-size: clamp(42px, 7vw, 76px);
	line-height: 1;
	font-weight: 500;
	letter-spacing: -0.045em;
	color: #080808;
}

.success-subtitle {
	margin: clamp(12px, 2.2vh, 22px) 0 0;
	text-align: center;
	font-size: clamp(18px, 2.4vw, 29px);
	color: #666;
}

.invoice-number {
	margin: clamp(18px, 2.6vh, 30px) auto 0;
	padding: 8px 16px;
	font-size: clamp(15px, 1.8vw, 20px);
	font-weight: 700;
	color: #444;
	text-align: center;
}

.payment-card {
	margin-top: clamp(18px, 3vh, 30px);
	border: 1px solid #d7d7d7;
	border-radius: 18px;
	background: #fff;
	padding: clamp(16px, 2.5vw, 24px);
	box-shadow: 0 16px 34px rgba(0, 0, 0, 0.08);
}

.card-title {
	margin-bottom: 12px;
	font-size: 13px;
	font-weight: 800;
	letter-spacing: 0.16em;
	text-transform: uppercase;
	color: #898989;
}

.payment-methods {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.payment-method-row {
	min-height: 46px;
	border-radius: 12px;
	background: #f7f7f8;
	padding: 10px 14px;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 20px;
	font-size: clamp(15px, 1.7vw, 19px);
	color: #5e5e5e;
}

.payment-method-row strong {
	color: #111;
	font-weight: 800;
}

.payment-tiles {
	margin-top: 12px;
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 12px;
}

.payment-tiles.single-tile {
	grid-template-columns: 1fr;
}

.payment-tile {
	min-height: clamp(92px, 14vh, 118px);
	border: 1px solid;
	border-radius: 16px;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 14px;
	text-align: center;
}

.payment-tile span {
	font-size: 12px;
	font-weight: 800;
	letter-spacing: 0.05em;
	text-transform: uppercase;
}

.payment-tile strong {
	margin-top: 6px;
	font-size: clamp(26px, 3.4vw, 38px);
	line-height: 1;
	font-weight: 800;
}

.payment-tile.paid {
	border-color: #bfdcff;
	background: #eaf4ff;
	color: #1671d9;
}

.payment-tile.change {
	border-color: #bcebc8;
	background: #ecfbf0;
	color: #15803d;
}

.new-sale-button {
	width: min(100%, 420px);
	min-height: 54px;
	margin: clamp(18px, 3vh, 30px) auto 0;
	border: 0;
	border-radius: 14px;
	background: #0b78d0;
	color: #fff;
	font-size: clamp(16px, 1.7vw, 19px);
	font-weight: 800;
	cursor: pointer;
	box-shadow: 0 10px 24px rgba(11, 120, 208, 0.2);
}

.new-sale-button:hover {
	background: #086cbf;
}

.new-sale-button:focus-visible {
	outline: 3px solid rgba(11, 120, 208, 0.28);
	outline-offset: 3px;
}

@media (max-width: 640px), (max-height: 620px) {
	.cashier-success-window {
		align-items: flex-start;
		padding: 16px 12px;
	}

	.payment-tiles {
		grid-template-columns: 1fr;
	}

	h1 {
		font-size: clamp(36px, 12vw, 56px);
	}
}
</style>
