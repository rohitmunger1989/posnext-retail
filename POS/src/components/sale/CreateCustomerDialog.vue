<template>
	<Dialog
		v-model="show"
		:options="{
			title: isEditMode ? __('Edit Customer') : __('Create New Customer'),
			size: 'md',
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-6">
				<!-- Customer Name (Required) -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("Customer Name") }} <span class="text-red-500">*</span>
					</label>
					<Input
						v-model="customerData.customer_name"
						type="text"
						:placeholder="__('Enter customer name')"
						required
					/>
				</div>

				<!-- Mobile Number with Country Code Selector -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("Mobile Number") }} <span class="text-red-500">*</span>
					</label>
					<div class="flex gap-2">
						<!-- Country Code Dropdown -->
						<div class="relative" ref="dropdownRef">
							<button
								type="button"
								@click="showCountryDropdown = !showCountryDropdown"
								class="flex items-center gap-1 w-24 ps-2 pe-1 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white hover:bg-gray-50"
							>
								<img
									:src="`https://flagcdn.com/h24/${currentCountryCode}.png`"
									:alt="currentCountryCode"
									class="w-6 h-auto rounded-sm"
									@error="handleFlagError"
								/>
								<span class="flex-1 text-start">{{
									selectedCountryCode || "+20"
								}}</span>
								<svg
									class="w-4 h-4 text-gray-400"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M19 9l-7 7-7-7"
									/>
								</svg>
							</button>

							<!-- Country Search Dropdown -->
							<div
								v-if="showCountryDropdown"
								class="absolute start-0 z-50 mt-1 w-80 max-h-80 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden"
							>
								<div class="sticky top-0 bg-white border-b border-gray-200 p-2">
									<input
										ref="countrySearchRef"
										v-model="countrySearchQuery"
										type="text"
										:placeholder="__('Search country or code...')"
										class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
										@keydown.escape="showCountryDropdown = false"
									/>
								</div>
								<div class="overflow-y-auto max-h-64">
									<button
										v-for="country in filteredCountries"
										:key="country.code"
										type="button"
										@click="selectCountry(country)"
										class="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors text-start"
										:class="{
											'bg-blue-50': selectedCountryCode === country.isd,
										}"
									>
										<img
											:src="`https://flagcdn.com/h24/${country.code.toLowerCase()}.png`"
											:alt="country.name"
											class="w-6 h-auto rounded-sm shadow-sm"
											@error="(e) => (e.target.style.display = 'none')"
										/>
										<span class="flex-1 text-sm font-medium text-gray-700">{{
											country.name
										}}</span>
										<span class="text-sm text-gray-500">{{
											country.isd
										}}</span>
									</button>
									<div
										v-if="filteredCountries.length === 0"
										class="px-4 py-8 text-center text-sm text-gray-500"
									>
										{{ __("No countries found") }}
									</div>
								</div>
							</div>
						</div>

						<!-- Phone Number Input -->
						<input
							v-model="phoneNumber"
							type="tel"
							:placeholder="__('Enter phone number')"
							class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-start"
							@input="updateMobileNumber"
							required
						/>
					</div>
				</div>

				<!-- Email -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("Email") }}
					</label>
					<Input
						v-model="customerData.email_id"
						type="email"
						:placeholder="__('Enter email address')"
					/>
				</div>

				<!-- Customer Group -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("Customer Group") }}
					</label>
					<select
						v-model="customerData.customer_group"
						class="w-full px-8 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
					>
						<option value="">{{ __("Select Customer Group") }}</option>
						<option v-for="group in customerGroups" :key="group" :value="group">
							{{ group }}
						</option>
					</select>
				</div>

				<!-- Territory -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("Territory") }}
					</label>
					<select
						v-model="customerData.territory"
						class="w-full px-8 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
					>
						<option value="">{{ __("Select Territory") }}</option>
						<option
							v-for="territory in territories"
							:key="territory"
							:value="territory"
						>
							{{ territory }}
						</option>
					</select>
				</div>

				<!-- Governorate -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("Governorate") }}
					</label>
					<select
						v-model="customerData.custom_governorate"
						class="w-full px-8 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
					>
						<option value="">{{ __("Select Governorate") }}</option>
						<option v-for="gov in governorates" :key="gov" :value="gov">
							{{ gov }}
						</option>
					</select>
				</div>

				<!-- District (filtered by selected Governorate) -->
				<div>
					<label class="block text-start text-sm font-medium text-gray-700 mb-2">
						{{ __("District") }}
					</label>
					<select
						v-model="customerData.custom_district"
						:disabled="!customerData.custom_governorate"
						class="w-full px-8 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
					>
						<option value="">
							{{
								customerData.custom_governorate
									? __("Select District")
									: __("Select a governorate first")
							}}
						</option>
						<option
							v-for="district in districts"
							:key="district.name"
							:value="district.name"
						>
							{{ district.district }}
						</option>
					</select>
				</div>
			</div>
		</template>

		<template #actions>
			<div class="flex flex-col gap-2">
				<!-- Permission Warning -->
				<div
					v-if="!hasPermission"
					class="px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg"
				>
					<div class="flex items-start gap-2">
						<svg
							class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5"
							fill="currentColor"
							viewBox="0 0 20 20"
						>
							<path
								fill-rule="evenodd"
								d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
								clip-rule="evenodd"
							/>
						</svg>
						<div class="flex-1">
							<p class="text-sm font-medium text-amber-900">
								{{ __("Permission Required") }}
							</p>
							<p class="text-xs text-amber-700 mt-0.5">
								{{
									__(
										"You don't have permission to create customers. Contact your administrator."
									)
								}}
							</p>
						</div>
					</div>
				</div>

				<div class="flex gap-2">
					<Button
						variant="solid"
						@click="handleCreate"
						:loading="
							createCustomerResource.loading ||
							updateCustomerResource.loading ||
							checkingPermission
						"
						:disabled="!customerData.customer_name || !phoneNumber || !hasPermission"
					>
						{{ isEditMode ? __("Save Changes") : __("Create Customer") }}
					</Button>
					<Button variant="subtle" @click="show = false">
						{{ __("Cancel") }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { call } from "@/utils/apiWrapper";
/**
 * CreateCustomerDialog - Quick customer creation from POS
 *
 * Features:
 * - Country code selector with flag icons and search
 * - Auto-sets territory based on selected country
 * - Permission checking before allowing creation
 * - Lazy loads countries data when dialog opens (not on app startup)
 */

import { usePOSPermissions } from "@/composables/usePermissions";
import { useToast } from "@/composables/useToast";
import { useCountriesStore } from "@/stores/countries";
import { db } from "@/utils/offline/db";
import { offlineState } from "@/utils/offline/offlineState";
import { saveOfflineCustomer } from "@/utils/offline/customerQueue";
import { logger } from "@/utils/logger";
import { Button, Dialog, Input, createResource } from "frappe-ui";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const log = logger.create("CreateCustomerDialog");

// =============================================================================
// Composables & Stores
// =============================================================================

const countriesStore = useCountriesStore();
const { canCreateCustomer } = usePOSPermissions();
const { showSuccess, showError } = useToast();

// =============================================================================
// Props & Emits
// =============================================================================

const props = defineProps({
	modelValue: Boolean,
	posProfile: String,
	initialName: String,
	customer: Object, // Customer object for edit mode
});

const emit = defineEmits(["update:modelValue", "customer-created", "customer-updated"]);

// =============================================================================
// State
// =============================================================================

const hasPermission = ref(true);
const checkingPermission = ref(false);
const selectedCountryCode = ref("");
const phoneNumber = ref("");
const showCountryDropdown = ref(false);
const countrySearchQuery = ref("");
const dropdownRef = ref(null);
const countrySearchRef = ref(null);

const customerGroups = ref([]);
const territories = ref([]);
const governorates = ref([]);
const districts = ref([]);

const customerData = ref({
	customer_name: "",
	mobile_no: "",
	email_id: "",
	customer_group: "",
	territory: "",
	custom_governorate: "",
	custom_district: "",
});

// =============================================================================
// Computed
// =============================================================================

const show = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
});

const isEditMode = computed(() => !!props.customer?.name);

const currentCountryCode = computed(() => {
	const country = countriesStore.countries.find((c) => c.isd === selectedCountryCode.value);
	return country?.code.toLowerCase() || "eg";
});

const filteredCountries = computed(() => {
	if (!countrySearchQuery.value) return countriesStore.countries;

	const query = countrySearchQuery.value.toLowerCase();
	return countriesStore.countries.filter(
		(c) =>
			c.name.toLowerCase().includes(query) ||
			c.isd.includes(query) ||
			c.code.toLowerCase().includes(query)
	);
});

// =============================================================================
// Country & Territory Methods
// =============================================================================

const handleFlagError = (e) => (e.target.style.display = "none");

const selectCountry = (country) => {
	selectedCountryCode.value = country.isd;
	showCountryDropdown.value = false;
	countrySearchQuery.value = "";
	updateMobileNumber();
};

const updateMobileNumber = () => {
	customerData.value.mobile_no = phoneNumber.value
		? `${selectedCountryCode.value}-${phoneNumber.value}`
		: "";
};

const handleClickOutside = (event) => {
	if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
		showCountryDropdown.value = false;
		countrySearchQuery.value = "";
	}
};

const setCountryFromName = (countryName) => {
	if (!countryName) {
		selectedCountryCode.value = "+20";
		return;
	}

	const isd = countriesStore.countryNameToISDMap[countryName];
	if (isd) {
		selectedCountryCode.value = isd;
		log.info(`Set country code to ${isd} for ${countryName}`);
	} else {
		log.warn(`Country "${countryName}" not found`);
		selectedCountryCode.value = "+20";
	}
};

/** Auto-set territory based on selected country (exact or fuzzy match) */
const updateTerritoryFromCountry = () => {
	if (!territories.value.length) return;

	const country = countriesStore.countries.find((c) => c.isd === selectedCountryCode.value);
	if (!country) return;

	// Try exact match first
	if (territories.value.includes(country.name)) {
		customerData.value.territory = country.name;
		log.info(`Territory set to: ${country.name}`);
		return;
	}

	// Try fuzzy match
	const fuzzyMatch = territories.value.find(
		(t) =>
			t.toLowerCase().includes(country.name.toLowerCase()) ||
			country.name.toLowerCase().includes(t.toLowerCase())
	);

	if (fuzzyMatch) {
		customerData.value.territory = fuzzyMatch;
		log.info(`Territory set to fuzzy match: ${fuzzyMatch}`);
	}
};

// =============================================================================
// API Resources
// =============================================================================

const createCustomerResource = createResource({
	url: "pos_next.api.customers.create_customer",
	makeParams: () => ({
		customer_name: customerData.value.customer_name,
		mobile_no: customerData.value.mobile_no || "",
		email_id: customerData.value.email_id || "",
		customer_group: customerData.value.customer_group || "",
		territory: customerData.value.territory || "",
		custom_governorate: customerData.value.custom_governorate || "",
		custom_district: customerData.value.custom_district || "",
		pos_profile: props.posProfile,
	}),
	onSuccess: (data) => {
		showSuccess(__("Customer {0} created successfully", [data.customer_name]));
		emit("customer-created", data);
		show.value = false;
	},
	onError: (error) => {
		log.error("Error creating customer", error);
		showError(error.message || __("Failed to create customer"));
	},
});

const updateCustomerResource = createResource({
	url: "frappe.client.set_value",
	makeParams: () => ({
		doctype: "Customer",
		name: props.customer?.name,
		fieldname: {
			customer_name: customerData.value.customer_name,
			customer_group: customerData.value.customer_group || "",
			territory: customerData.value.territory || "",
			mobile_no: customerData.value.mobile_no || "",
			email_id: customerData.value.email_id || "",
			custom_governorate: customerData.value.custom_governorate || "",
			custom_district: customerData.value.custom_district || "",
		},
	}),
	onSuccess: (data) => {
		showSuccess(__("Customer {0} updated successfully", [data.customer_name]));
		emit("customer-updated", data);
		show.value = false;
	},
	onError: (error) => {
		log.error("Error updating customer", error);
		showError(error.message || __("Failed to update customer"));
	},
});

const sellingSettingsResource = createResource({
	url: "frappe.client.get_value",
	makeParams: () => ({
		doctype: "Selling Settings",
		fieldname: ["customer_group", "territory"],
	}),
	auto: false,
	onError: (err) => log.error("Error loading Selling Settings", err),
});

function pickDefault(settingsValue, list, fallbackFn = null) {
	if (settingsValue && list.includes(settingsValue)) return settingsValue;
	if (fallbackFn) return fallbackFn(list) || list[0] || "";
	return list[0] || "";
}

/** Load previously cached customer-form options. */
const restoreCustomerFormOptions = async () => {
    const entries = [
        ["Customer Group", customerGroups],
        ["Territory", territories],
        ["Governorate", governorates],
    ];

    for (const [doctype, target] of entries) {
        try {
            const cached = await db.settings.get(`customer_form_options_v1:${doctype}`);
            if (Array.isArray(cached?.value)) {
                target.value = cached.value;
            }
        } catch (error) {
            log.warn(`Failed to restore cached ${doctype}`, error);
        }
    }
};

/** Helper to create list fetch resources */
const createListResource = (doctype, onSuccess) =>
    createResource({
        url: "frappe.client.get_list",
        makeParams: () => ({
            doctype,
            fields: ["name"],
            filters: doctype === "Customer Group" ? { is_group: 0 } : {},
            limit_page_length: 500,
        }),
        auto: false,
        onSuccess: (data) => {
            if (!Array.isArray(data)) return;
            const names = data.map((d) => d.name).filter(Boolean);
            onSuccess(names);
            db.settings.put({
                key: `customer_form_options_v1:${doctype}`,
                value: names,
            }).catch((error) => log.warn(`Failed to cache ${doctype}`, error));
        },
        onError: (err) => log.warn(`Error loading ${doctype}`, err),
    });

const customerGroupsResource = createListResource("Customer Group", (names) => {
	customerGroups.value = names;
	if (!customerData.value.customer_group && names.length > 0) {
		const settingsDefault = sellingSettingsResource.data?.customer_group;
		customerData.value.customer_group = pickDefault(settingsDefault, names);
	}
});

const territoriesResource = createListResource("Territory", (names) => {
	territories.value = names;
	if (!customerData.value.territory && names.length > 0) {
		const settingsDefault = sellingSettingsResource.data?.territory;
		customerData.value.territory = pickDefault(settingsDefault, names, (list) =>
			list.find((n) => n === "All Territories")
		);
	}
});

const governoratesResource = createListResource("Governorate", (names) => {
	governorates.value = names;
});

const customerLocationResource = createResource({
	url: "frappe.client.get_value",
	makeParams: () => ({
		doctype: "Customer",
		filters: { name: props.customer?.name },
		fieldname: ["custom_governorate", "custom_district"],
	}),
	auto: false,
	onSuccess: (data) => {
		customerData.value.custom_governorate = data?.custom_governorate || "";
		customerData.value.custom_district = data?.custom_district || "";
	},
	onError: (err) => log.error("Error loading customer location", err),
});

const districtsResource = createResource({
    url: "frappe.client.get_list",
    makeParams: () => ({
        doctype: "District",
        fields: ["name", "district"],
        filters: { governorate: customerData.value.custom_governorate },
        limit_page_length: 0,
        order_by: "district asc",
    }),
    auto: false,
    onSuccess: (data) => {
        if (!Array.isArray(data)) return;

        districts.value = data;

        const governorate = customerData.value.custom_governorate;
        if (governorate) {
            db.settings.put({
                key: `customer_districts_v1:${governorate}`,
                value: data,
            }).catch((error) => log.warn("Failed to cache districts", error));
        }

        if (
            customerData.value.custom_district &&
            !data.some((d) => d.name === customerData.value.custom_district)
        ) {
            customerData.value.custom_district = "";
        }
    },
    onError: (err) => log.warn("Error loading Districts", err),
});

const loadDistrictOptions = async (governorate) => {
    if (!governorate) {
        districts.value = [];
        return;
    }

    // Restore previously cached districts first.
    try {
        const cached = await db.settings.get(
            `customer_districts_v1:${governorate}`
        );
        districts.value = Array.isArray(cached?.value) ? cached.value : [];
    } catch (error) {
        log.warn("Failed to restore districts", error);
        districts.value = [];
    }

    // Refresh only when ERPNext is reachable.
    if (!offlineState.isOffline && navigator.onLine) {
        try {
            await districtsResource.reload();
        } catch (error) {
            log.warn("Using cached districts", error);
        }
    }
};

const posProfileResource = createResource({
    url: "frappe.client.get_value",
    makeParams: () => ({
        doctype: "POS Profile",
        filters: { name: props.posProfile },
        fieldname: ["country"],
    }),
    auto: false,
    onSuccess: (data) => {
        if (!data?.country) return;
        setCountryFromName(data.country);
        if (props.posProfile && selectedCountryCode.value) {
            db.settings.put({
                key: `customer_pos_country_v1:${props.posProfile}`,
                value: selectedCountryCode.value,
            }).catch((err) => log.warn("Failed to cache POS country", err));
        }
    },
    onError: (err) => {
        log.warn("Could not load POS Profile country", err);
    },
});

// =============================================================================
// // Dialog Lifecycle
// =============================================================================

/**
 * Smart-prefill the create customer form from the text entered in POS search.
 *
 * Examples:
 * - "Ahmed" -> customer name
 * - "65156265" -> mobile number (keep POS Profile/default country code)
 * - "Ahmed 65156265" -> name + mobile
 * - "+971501234567 Ahmed" / "00971501234567 Ahmed" -> country code + mobile + name
 */
const applyInitialSearchPrefill = (rawValue) => {
	if (isEditMode.value) return;

	const query = String(rawValue || "").trim();
	if (!query) return;

	let working = query;
	let detectedPhone = "";
	let detectedCountryISD = "";

	// Match an explicitly international number anywhere in the search text.
	// Keep separators so values like +965 6515 6265 and 00971-50-123-4567 work.
	const internationalMatches = [
		...working.matchAll(/(?:\+|00)\s*\d(?:[\d\s().-]*\d)?/g),
	];

	for (const match of internationalMatches) {
		const token = match[0];
		let digits = token.replace(/\D/g, "");
		if (token.trim().startsWith("00")) digits = digits.slice(2);

		// Prefer the longest known ISD prefix so overlapping codes are deterministic.
		const country = [...countriesStore.countries]
			.map((entry) => ({
				...entry,
				isdDigits: String(entry.isd || "").replace(/\D/g, ""),
			}))
			.filter((entry) => entry.isdDigits && digits.startsWith(entry.isdDigits))
			.sort((a, b) => b.isdDigits.length - a.isdDigits.length)[0];

		// Kuwait fallback when the offline country cache is unavailable.
		const resolvedCountry = country || (
		    digits.startsWith("965") ? { isd: "+965", isdDigits: "965" } : null
		);
		if (!resolvedCountry) continue;
		const localDigits = digits.slice(resolvedCountry.isdDigits.length);
		if (localDigits.length < 6 || localDigits.length > 15) continue;

		detectedCountryISD = resolvedCountry.isd;
		detectedPhone = localDigits;
		working = `${working.slice(0, match.index)} ${working.slice(
			(match.index || 0) + token.length
		)}`;
		break;
	}

	// If there was no explicit international prefix, detect a local phone-like value.
	// Require at least 7 digits so short numeric text is not accidentally treated as a phone.
	if (!detectedPhone) {
		const localMatches = [...working.matchAll(/\d(?:[\d\s().-]*\d)?/g)];
		for (const match of localMatches) {
			const token = match[0];
			const digits = token.replace(/\D/g, "");
			if (digits.length < 7 || digits.length > 15) continue;

			detectedPhone = digits;
			working = `${working.slice(0, match.index)} ${working.slice(
				(match.index || 0) + token.length
			)}`;
			break;
		}
	}

	const detectedName = working
		.replace(/^[\s,;|/\-]+|[\s,;|/\-]+$/g, "")
		.replace(/\s{2,}/g, " ")
		.trim();

	customerData.value.customer_name = detectedName;

	if (detectedCountryISD) {
		selectedCountryCode.value = detectedCountryISD;
	}
	if (detectedPhone) {
		phoneNumber.value = detectedPhone;
		updateMobileNumber();
	}
};

const loadDialogData = async () => {
    await restoreCustomerFormOptions();
    await countriesStore.loadCountries();

    const online = !offlineState.isOffline && navigator.onLine;

    if (online) {
        try {
            await sellingSettingsResource.reload();
            await Promise.all([
                territoriesResource.reload(),
                customerGroupsResource.reload(),
                governoratesResource.reload(),
            ]);
        } catch (error) {
            log.warn("Using cached customer form options", error);
        }
    }

    if (!isEditMode.value) {
        const settings = sellingSettingsResource.data || {};
        customerData.value.customer_group = pickDefault(
            settings.customer_group,
            customerGroups.value
        );
        customerData.value.territory = pickDefault(
            settings.territory,
            territories.value,
            (list) => list.find((name) => name === "All Territories")
        );
    }

    if (online && isEditMode.value && props.customer?.name) {
        await customerLocationResource.reload();
    }

    if (customerData.value.custom_governorate) {
        await loadDistrictOptions(customerData.value.custom_governorate);
    }

    await checkPermissions();

    selectedCountryCode.value = "";

    if (props.posProfile) {
        try {
            const cached = await db.settings.get(
                `customer_pos_country_v1:${props.posProfile}`
            );
            if (cached?.value) selectedCountryCode.value = cached.value;
        } catch (error) {
            log.warn("Could not restore cached POS country", error);
        }

        if (online) {
            try {
                await posProfileResource.reload();
            } catch (error) {
                log.warn("Using cached POS country", error);
            }
        }
    }

    // Preserve Smart Prefill for name, local and international numbers.
    if (!isEditMode.value && props.initialName) {
        applyInitialSearchPrefill(props.initialName);
    }
};

const getPermissionUser = () => {
    const cookie = document.cookie
        .split("; ")
        .find((entry) => entry.startsWith("user_id="));

    if (!cookie) return null;

    try {
        const user = decodeURIComponent(cookie.slice("user_id=".length));
        return user && user !== "Guest" ? user : null;
    } catch {
        return null;
    }
};

const customerPermissionKey = (user) =>
    `customer_create_permission_v1:${user}`;

const restoreOfflineCustomerPermission = async () => {
    hasPermission.value = false;

    const user = getPermissionUser();
    if (!user) return;

    try {
        const record = await db.settings.get(customerPermissionKey(user));
        const permission = record?.value;

        const valid =
            permission?.user === user &&
            permission?.allowed === true &&
            Number.isFinite(permission?.timestamp) &&
            Date.now() - permission.timestamp >= 0 &&
            Date.now() - permission.timestamp < 24 * 60 * 60 * 1000;

        hasPermission.value = Boolean(valid);
    } catch (error) {
        log.warn("Could not restore offline customer permission", error);
    }
};

const checkPermissions = async () => {
    checkingPermission.value = true;
    hasPermission.value = false;

    try {
        const user = getPermissionUser();
        if (!user) return;

        if (offlineState.isOffline || !navigator.onLine) {
            await restoreOfflineCustomerPermission();
            return;
        }

        // Check directly with ERPNext; distinguish denial from network errors.
        const response = await call("frappe.client.has_permission", {
            doctype: "Customer",
            docname: "",
            perm_type: "create",
        });

        const permission = response?.message ?? response;
        if (permission?.has_permission === undefined) {
            throw new Error("Invalid Customer permission response");
        }

        const allowed =
            permission.has_permission === true ||
            permission.has_permission === 1;

        hasPermission.value = allowed;

        await db.settings.put({
            key: customerPermissionKey(user),
            value: {
                user,
                allowed: Boolean(allowed),
                timestamp: Date.now(),
            },
        });
    } catch (error) {
        log.error("Permission check failed", error);
        hasPermission.value = false;
    } finally {
        checkingPermission.value = false;
    }
};

const handleCreate = async () => {
    if (!hasPermission.value || !getPermissionUser()) {
        return showError(__("Customer creation permission is required"));
    }

    if (!customerData.value.customer_name?.trim()) {
        return showError(__("Customer Name is required"));
    }

    if (!phoneNumber.value) {
        return showError(__("Mobile Number is required"));
    }

    // Editing existing customers still requires ERPNext.
    if (isEditMode.value) {
        if (offlineState.isOffline || !navigator.onLine) {
            return showError(__("Editing customers requires an internet connection"));
        }

        await updateCustomerResource.submit();
        return;
    }

    // Offline customer creation: persist locally before selecting customer.
    if (offlineState.isOffline || !navigator.onLine) {
        try {
            updateMobileNumber();

            const customer = await saveOfflineCustomer(
                { ...customerData.value },
                props.posProfile
            );

            emit("customer-created", customer);
            showSuccess(__("Customer saved offline. Will sync when online."));
            show.value = false;
        } catch (error) {
            log.error("Could not save offline customer", error);
            showError(error.message || __("Failed to save offline customer"));
        }
        return;
    }

    // Preserve normal online customer creation.
    await createCustomerResource.submit();
};

const resetForm = () => {
	const settings = sellingSettingsResource.data || {};
	Object.assign(customerData.value, {
		customer_name: "",
		mobile_no: "",
		email_id: "",
		customer_group: pickDefault(settings.customer_group, customerGroups.value),
		territory: pickDefault(settings.territory, territories.value, (list) =>
			list.find((n) => n === "All Territories")
		),
		custom_governorate: "",
		custom_district: "",
	});
	districts.value = [];
	selectedCountryCode.value = "";
	phoneNumber.value = "";
};

// =============================================================================
// Watchers
// =============================================================================

watch(
	() => props.initialName,
	(value) => {
		if (show.value && !isEditMode.value && value) {
			applyInitialSearchPrefill(value);
		}
	}
);

// Pre-fill form when customer prop changes (edit mode)
watch(
	() => props.customer,
	(customer) => {
		if (customer?.name) {
			customerData.value.customer_name = customer.customer_name || "";
			customerData.value.email_id = customer.email_id || "";
			customerData.value.customer_group =
				customer.customer_group || customerGroups.value[0] || "";
			customerData.value.territory =
				customer.territory ||
				territories.value.find((n) => n === "All Territories") ||
				territories.value[0] ||
				"";

			customerData.value.custom_governorate = customer.custom_governorate || "";
			customerData.value.custom_district = customer.custom_district || "";
			// Handle mobile_no with country code
			if (customer.mobile_no) {
				customerData.value.mobile_no = customer.mobile_no;
				if (customer.mobile_no.includes("-")) {
					const [code, ...rest] = customer.mobile_no.split("-");
					selectedCountryCode.value = code;
					phoneNumber.value = rest.join("-");
				} else {
					phoneNumber.value = customer.mobile_no;
				}
			}
		}
	},
	{ immediate: true }
);

watch(
	() => customerData.value.mobile_no,
	(value) => {
		if (value?.includes("-")) {
			const [code, ...rest] = value.split("-");
			selectedCountryCode.value = code;
			phoneNumber.value = rest.join("-");
		}
	}
);

watch(selectedCountryCode, async (newVal, oldVal) => {
	if (!oldVal) return;
	await nextTick();
	updateTerritoryFromCountry();
});

watch(
    () => customerData.value.custom_governorate,
    async (governorate) => {
        customerData.value.custom_district = "";

        if (governorate) {
            await loadDistrictOptions(governorate);
        } else {
            districts.value = [];
        }
    }
);

watch(showCountryDropdown, async (isOpen) => {
	if (isOpen) {
		await nextTick();
		countrySearchRef.value?.focus();
	}
});

watch(
	() => props.modelValue,
	async (isOpen) => {
		isOpen ? await loadDialogData() : resetForm();
	}
);

// =============================================================================
// Lifecycle Hooks
// =============================================================================

onMounted(() => {
	document.addEventListener("click", handleClickOutside);
});

onBeforeUnmount(() => {
	document.removeEventListener("click", handleClickOutside);
});
</script>

<style scoped>
.sr-only {
	position: absolute;
	width: 1px;
	height: 1px;
	padding: 0;
	margin: -1px;
	overflow: hidden;
	clip: rect(0, 0, 0, 0);
	white-space: nowrap;
	border-width: 0;
}
</style>
