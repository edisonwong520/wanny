<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";

import type { CareDataSourceRecord } from "@/lib/care";

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
  longitude: "",
  latitude: "",
  timezone: "Asia/Shanghai",
  fetchFrequency: "30m",
});

const editingId = ref<number | null>(null);
const loadingLocation = ref(false);

const weatherSources = computed(() =>
  props.sources.filter((s) => s.sourceType === "weather_api")
);

function resetForm() {
  editingId.value = null;
  form.value = {
    location: "",
    longitude: "",
    latitude: "",
    timezone: "Asia/Shanghai",
    fetchFrequency: "30m",
  };
}

function requestBrowserLocation() {
  if (!navigator.geolocation) {
    alert(t("care.weather.errors.geolocationNotSupported"));
    return;
  }
  loadingLocation.value = true;
  navigator.geolocation.getCurrentPosition(
    (position) => {
      form.value.longitude = position.coords.longitude.toFixed(4);
      form.value.latitude = position.coords.latitude.toFixed(4);
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
    location: String(config.location || ""),
    longitude: config.longitude == null ? "" : String(config.longitude),
    latitude: config.latitude == null ? "" : String(config.latitude),
    timezone: String(config.timezone || "Asia/Shanghai"),
    fetchFrequency: source.fetchFrequency,
  };
}

function handleSubmit() {
  const payload: Partial<CareDataSourceRecord> = {
    sourceType: "weather_api",
    name: editingId.value ? undefined : t("care.weather.types.qweather"),
    fetchFrequency: form.value.fetchFrequency,
    isActive: true,
    config: {
      provider: "qweather",
      location: form.value.location.trim() || undefined,
      longitude: form.value.longitude.trim() ? Number(form.value.longitude) : undefined,
      latitude: form.value.latitude.trim() ? Number(form.value.latitude) : undefined,
      timezone: form.value.timezone,
    },
  };
  emit("save", payload);
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      resetForm();
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

        <!-- Form -->
        <div class="text-[10px] text-[#98A2B3] uppercase mb-2">
          {{ editingId ? $t("care.weather.editTitle") : $t("care.weather.addSource") }}
        </div>
        <div class="space-y-3">
          <input
            v-model="form.location"
            :placeholder="$t('care.weather.form.location')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
          <div class="flex items-center gap-2">
            <div class="flex-1 grid grid-cols-2 gap-2">
              <input
                v-model="form.longitude"
                :placeholder="$t('care.weather.form.longitude')"
                class="rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              />
              <input
                v-model="form.latitude"
                :placeholder="$t('care.weather.form.latitude')"
                class="rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              />
            </div>
            <button
              type="button"
              class="shrink-0 rounded-xl bg-[#F2F4F7] px-3 py-2.5 text-xs text-[#344054] hover:bg-[#E4E7EC] disabled:opacity-50"
              :disabled="loadingLocation"
              @click="requestBrowserLocation"
            >
              {{ loadingLocation ? $t("care.weather.form.locating") : $t("care.weather.form.autoLocation") }}
            </button>
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
          {{ editingId ? $t("care.weather.actions.saveSource") : $t("care.weather.actions.addSource") }}
        </button>
      </div>
    </div>
  </div>
</template>