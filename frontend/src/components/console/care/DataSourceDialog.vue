<script setup lang="ts">
import { ref, watch, computed, nextTick } from "vue";
import { useI18n } from "vue-i18n";

import type { CareDataSourceRecord } from "@/lib/care";
import { reverseGeocode } from "@/lib/care";

const props = defineProps<{
  open: boolean;
  sources: CareDataSourceRecord[];
  saving: boolean;
}>();

const emit = defineEmits<{
  close: [];
  save: [payload: Partial<CareDataSourceRecord>];
  delete: [id: number];
  toggle: [id: number, active: boolean];
}>();

const { t } = useI18n();

const form = ref({
  location: "",
  apiKey: "",
  apiHost: "",
  longitude: "",
  latitude: "",
  timezone: "Asia/Shanghai",
  fetchFrequency: "30m",
});

const editingId = ref<number | null>(null);
const loadingLocation = ref(false);
const apiHostInput = ref<HTMLInputElement | null>(null);

const weatherSources = computed(() =>
  props.sources.filter((s) => s.sourceType === "weather_api")
);

function formatResolvedLocation(result: { name?: string; adm1?: string; adm2?: string; country?: string; locationId?: string }) {
  const parts = [result.country, result.adm1, result.adm2, result.name]
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  const uniqueParts = parts.filter((part, index) => parts.indexOf(part) === index);
  return uniqueParts.join(" / ");
}

function normalizedSubmitLocation() {
  const value = form.value.location.trim();
  if (!value) return undefined;
  return /^\d+$/.test(value) ? value : undefined;
}

function normalizedDisplayLocation(config: Record<string, unknown>) {
  const locationLabel = String(config.location_label || "").trim();
  if (locationLabel) {
    return locationLabel;
  }
  const rawLocation = String(config.location || "").trim();
  if (rawLocation && !/^\d+$/.test(rawLocation)) {
    return rawLocation;
  }
  const parts = [config.country, config.adm1, config.adm2, config.name]
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  const uniqueParts = parts.filter((part, index) => parts.indexOf(part) === index);
  if (uniqueParts.length > 0) {
    return uniqueParts.join(" / ");
  }
  return rawLocation;
}

function resetForm() {
  editingId.value = null;
  form.value = {
    location: "",
    apiKey: "",
    apiHost: "",
    longitude: "",
    latitude: "",
    timezone: "Asia/Shanghai",
    fetchFrequency: "30m",
  };
}

async function focusForm() {
  await nextTick();
  apiHostInput.value?.focus();
}

async function requestBrowserLocation() {
  if (!form.value.apiKey.trim() || !form.value.apiHost.trim()) {
    alert(t("care.weather.errors.missingApiConfig"));
    return;
  }
  if (!navigator.geolocation) {
    alert(t("care.weather.errors.geolocationNotSupported"));
    return;
  }
  loadingLocation.value = true;
  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const lon = position.coords.longitude;
      const lat = position.coords.latitude;
      form.value.longitude = lon.toFixed(4);
      form.value.latitude = lat.toFixed(4);

      // Try to get location name via reverse geocoding
      try {
        const result = await reverseGeocode(lon, lat, form.value.apiKey.trim(), form.value.apiHost.trim());
        const resolvedLocation = formatResolvedLocation(result);
        if (resolvedLocation) {
          form.value.location = resolvedLocation;
        } else if (result.locationId) {
          form.value.location = result.locationId;
        }
      } catch {
        // Ignore geocoding errors, user can fill location manually
      }

      loadingLocation.value = false;
    },
    (error) => {
      loadingLocation.value = false;
      let message = t("care.weather.errors.geolocationFailed");
      if (error.code === error.PERMISSION_DENIED) {
        message = t("care.weather.errors.geolocationDenied");
      }
      alert(message);
    },
    { enableHighAccuracy: false, timeout: 10000 }
  );
}

function editSource(source: CareDataSourceRecord) {
  const config = source.config || {};
  editingId.value = source.id;
  form.value = {
    location: normalizedDisplayLocation(config),
    apiKey: String(config.api_key || ""),
    apiHost: String(config.endpoint || "").replace(/^https?:\/\//, ""),
    longitude: config.longitude == null ? "" : String(config.longitude),
    latitude: config.latitude == null ? "" : String(config.latitude),
    timezone: String(config.timezone || "Asia/Shanghai"),
    fetchFrequency: source.fetchFrequency,
  };
}

function handleSubmit() {
  const payload: Partial<CareDataSourceRecord> = {
    id: editingId.value ?? undefined,
    sourceType: "weather_api",
    name: editingId.value ? undefined : t("care.weather.types.qweather"),
    fetchFrequency: form.value.fetchFrequency,
    isActive: true,
    config: {
      provider: "qweather",
      api_key: form.value.apiKey.trim(),
      endpoint: form.value.apiHost.trim(),
      location: normalizedSubmitLocation(),
      location_label: form.value.location.trim() || undefined,
      longitude: form.value.longitude.trim() ? Number(form.value.longitude) : undefined,
      latitude: form.value.latitude.trim() ? Number(form.value.latitude) : undefined,
      timezone: form.value.timezone,
    },
  };
  emit("save", payload);
}

function clearField(field: "apiHost" | "apiKey" | "location" | "longitude" | "latitude") {
  form.value[field] = "";
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      resetForm();
      void focusForm();
    }
  },
  { immediate: true }
);
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4">
    <div class="w-full max-w-lg rounded-[20px] bg-white shadow-[0_24px_80px_rgba(16,24,40,0.2)]">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-[#E4E7EC]">
        <div class="flex items-center justify-between">
          <div class="text-sm font-semibold text-[#1F2A22]">{{ $t("care.weather.sourceTitle") }}</div>
          <button
            class="flex h-7 w-7 items-center justify-center rounded-full bg-[#F2F4F7] text-[#667085] hover:bg-[#E4E7EC]"
            @click="emit('close')"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="p-5 max-h-[60vh] overflow-y-auto">
        <div class="mb-4 rounded-2xl border border-[#E4E7EC] bg-[#F9FAFB] px-4 py-3 text-xs leading-6 text-[#667085]">
          <div class="font-semibold text-[#344054]">{{ $t("care.weather.tutorial.title") }}</div>
          <div class="mt-2">{{ $t("care.weather.tutorial.step1") }}</div>
          <div>{{ $t("care.weather.tutorial.step2") }}</div>
          <div>{{ $t("care.weather.tutorial.step3") }}</div>
          <div>{{ $t("care.weather.tutorial.step4") }}</div>
        </div>

        <!-- Existing Sources -->
        <div v-if="weatherSources.length > 0" class="mb-4">
          <div class="text-[10px] text-[#98A2B3] uppercase mb-2">{{ $t("care.weather.existingSources") }}</div>
          <div class="space-y-2">
            <div
              v-for="source in weatherSources"
              :key="source.id"
              class="rounded-xl border border-[#E4E7EC] bg-[#F9FAFB] p-3"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-xs font-semibold text-[#1F2A22]">{{ source.name }}</div>
                  <div class="text-[10px] text-[#667085] mt-0.5">{{ $t("care.weather.types.qweather") }}</div>
                </div>
                <div class="flex gap-1">
                  <button
                    class="rounded-full px-2 py-1 text-[10px]"
                    :class="source.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'"
                    @click="emit('toggle', source.id, !source.isActive)"
                  >
                    {{ source.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                  </button>
                  <button
                    class="rounded-full bg-white px-2 py-1 text-[10px] text-[#344054] border border-[#E4E7EC]"
                    @click="editSource(source)"
                  >
                    {{ $t("care.rules.actions.edit") }}
                  </button>
                  <button
                    class="rounded-full bg-[#FFF1F3] px-2 py-1 text-[10px] text-[#D92D20]"
                    @click="emit('delete', source.id)"
                  >
                    {{ $t("care.rules.actions.delete") }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="mb-4 rounded-2xl border border-dashed border-[#D0D5DD] bg-[#F9FAFB] px-4 py-4">
          <div class="text-sm font-medium text-[#344054]">{{ $t("care.weather.emptySources.title") }}</div>
          <div class="mt-1 text-xs leading-6 text-[#667085]">{{ $t("care.weather.emptySources.description") }}</div>
          <button
            type="button"
            class="mt-3 rounded-full border border-[#CFE5D6] bg-white px-4 py-2 text-xs font-medium text-[#07C160] transition-all hover:border-[#07C160] hover:bg-[#F2FBF5]"
            @click="focusForm"
          >
            {{ $t("care.weather.actions.add") }}
          </button>
        </div>

        <!-- Form -->
        <div class="space-y-3">
          <div class="relative">
            <input
              ref="apiHostInput"
              v-model="form.apiHost"
              :placeholder="$t('care.weather.form.apiHost')"
              class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 pr-10 text-sm outline-none focus:border-[#07C160]"
            />
            <button
              v-if="form.apiHost"
              type="button"
              class="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full bg-[#F2F4F7] text-xs text-[#667085] hover:bg-[#E4E7EC]"
              @click="clearField('apiHost')"
            >
              ×
            </button>
          </div>
          <div class="relative">
            <input
              v-model="form.apiKey"
              :placeholder="$t('care.weather.form.apiKey')"
              class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 pr-10 text-sm outline-none focus:border-[#07C160]"
            />
            <button
              v-if="form.apiKey"
              type="button"
              class="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full bg-[#F2F4F7] text-xs text-[#667085] hover:bg-[#E4E7EC]"
              @click="clearField('apiKey')"
            >
              ×
            </button>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="shrink-0 inline-flex h-[40px] items-center justify-center rounded-xl border border-[#E4E7EC] bg-[#F2F4F7] px-4 text-sm text-[#344054] hover:bg-[#E4E7EC] disabled:opacity-50"
              :disabled="loadingLocation"
              @click="requestBrowserLocation"
            >
              {{ loadingLocation ? $t("care.weather.form.locating") : $t("care.weather.form.autoLocation") }}
            </button>
            <div class="relative min-w-0 flex-1">
              <input
                v-model="form.location"
                :placeholder="$t('care.weather.form.location')"
                class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 pr-10 text-sm outline-none focus:border-[#07C160]"
              />
              <button
                v-if="form.location"
                type="button"
                class="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full bg-[#F2F4F7] text-xs text-[#667085] hover:bg-[#E4E7EC]"
                @click="clearField('location')"
              >
                ×
              </button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="relative">
              <input
                v-model="form.longitude"
                :placeholder="$t('care.weather.form.longitude')"
                class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 pr-10 text-sm outline-none focus:border-[#07C160]"
              />
              <button
                v-if="form.longitude"
                type="button"
                class="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full bg-[#F2F4F7] text-xs text-[#667085] hover:bg-[#E4E7EC]"
                @click="clearField('longitude')"
              >
                ×
              </button>
            </div>
            <div class="relative">
              <input
                v-model="form.latitude"
                :placeholder="$t('care.weather.form.latitude')"
                class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 pr-10 text-sm outline-none focus:border-[#07C160]"
              />
              <button
                v-if="form.latitude"
                type="button"
                class="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full bg-[#F2F4F7] text-xs text-[#667085] hover:bg-[#E4E7EC]"
                @click="clearField('latitude')"
              >
                ×
              </button>
            </div>
          </div>

          <!-- Fetch Frequency -->
          <select
            v-model="form.fetchFrequency"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160] bg-white"
          >
            <option value="10m">{{ $t("care.weather.fetchFrequency.10m") }}</option>
            <option value="30m">{{ $t("care.weather.fetchFrequency.30m") }}</option>
            <option value="1h">{{ $t("care.weather.fetchFrequency.1h") }}</option>
            <option value="3h">{{ $t("care.weather.fetchFrequency.3h") }}</option>
            <option value="6h">{{ $t("care.weather.fetchFrequency.6h") }}</option>
          </select>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-[#E4E7EC] flex justify-end gap-2">
        <button
          class="rounded-full bg-[#F2F4F7] px-4 py-2 text-sm text-[#344054]"
          @click="emit('close')"
        >
          {{ $t("care.actions.cancel") }}
        </button>
        <button
          class="rounded-full bg-[#07C160] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          :disabled="saving"
          @click="handleSubmit"
        >
          {{ editingId ? $t("care.weather.actions.saveSource") : $t("care.weather.actions.add") }}
        </button>
      </div>
    </div>
  </div>
</template>
