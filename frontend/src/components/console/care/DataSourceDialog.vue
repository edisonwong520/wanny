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
  sourceType: "weather_api" as "weather_api" | "ha_entity",
  provider: "qweather",
  name: "",
  location: "",
  latitude: "",
  longitude: "",
  timezone: "Asia/Shanghai",
  fetchFrequency: "30m",
  haEntityId: "weather.home",
});

const editingId = ref<number | null>(null);

const weatherSources = computed(() =>
  props.sources.filter((s) => ["weather_api", "ha_entity"].includes(s.sourceType))
);

function resetForm() {
  editingId.value = null;
  form.value = {
    sourceType: "weather_api",
    provider: "qweather",
    name: "",
    location: "",
    latitude: "",
    longitude: "",
    timezone: "Asia/Shanghai",
    fetchFrequency: "30m",
    haEntityId: "weather.home",
  };
}

function switchProvider(provider: "qweather" | "open_meteo") {
  form.value.provider = provider;
  if (!editingId.value || !form.value.name.trim()) {
    form.value.name = provider === "qweather" ? t("care.weather.types.qweather") : "Open-Meteo";
  }
}

function editSource(source: CareDataSourceRecord) {
  const config = source.config || {};
  editingId.value = source.id;
  form.value = {
    sourceType: source.sourceType as "weather_api" | "ha_entity",
    provider: String(config.provider || "qweather"),
    name: source.name,
    location: String(config.location || ""),
    latitude: config.latitude == null ? "" : String(config.latitude),
    longitude: config.longitude == null ? "" : String(config.longitude),
    timezone: String(config.timezone || "Asia/Shanghai"),
    fetchFrequency: source.fetchFrequency,
    haEntityId: String(config.ha_entity_id || config.entity_id || "weather.home"),
  };
}

function handleSubmit() {
  const payload: Partial<CareDataSourceRecord> = {
    sourceType: form.value.sourceType,
    name: form.value.name,
    fetchFrequency: form.value.fetchFrequency,
    isActive: true,
    config:
      form.value.sourceType === "ha_entity"
        ? { ha_entity_id: form.value.haEntityId }
        : form.value.provider === "qweather"
          ? {
              provider: "qweather",
              location: form.value.location.trim() || undefined,
              latitude: form.value.latitude.trim() ? Number(form.value.latitude) : undefined,
              longitude: form.value.longitude.trim() ? Number(form.value.longitude) : undefined,
              timezone: form.value.timezone,
            }
          : {
              provider: "open_meteo",
              latitude: Number(form.value.latitude),
              longitude: Number(form.value.longitude),
              timezone: form.value.timezone,
            },
  };
  emit("save", payload);
}

watch(
  () => props.open,
  (val) => {
    if (!val) resetForm();
  }
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
                  <div class="text-[10px] text-[#667085] mt-0.5">
                    {{
                      source.sourceType === "ha_entity"
                        ? $t("care.weather.types.haEntity")
                        : source.config?.provider === "qweather"
                          ? $t("care.weather.types.qweather")
                          : "Open-Meteo"
                    }}
                  </div>
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
          <!-- Source Type -->
          <div class="flex gap-2">
            <button
              class="flex-1 rounded-full px-3 py-2 text-xs transition-all"
              :class="form.sourceType === 'weather_api' ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085]'"
              @click="form.sourceType = 'weather_api'"
            >
              {{ $t("care.weather.apiSource") }}
            </button>
            <button
              class="flex-1 rounded-full px-3 py-2 text-xs transition-all"
              :class="form.sourceType === 'ha_entity' ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085]'"
              @click="form.sourceType = 'ha_entity'"
            >
              {{ $t("care.weather.types.haEntity") }}
            </button>
          </div>

          <!-- Provider Selection (for weather_api) -->
          <div v-if="form.sourceType === 'weather_api'" class="flex gap-2 pl-2">
            <button
              class="flex-1 rounded-full px-3 py-1.5 text-[11px] transition-all"
              :class="form.provider === 'qweather' ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085]'"
              @click="switchProvider('qweather')"
            >
              {{ $t("care.weather.types.qweather") }}
            </button>
            <button
              class="flex-1 rounded-full px-3 py-1.5 text-[11px] transition-all"
              :class="form.provider === 'open_meteo' ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085]'"
              @click="switchProvider('open_meteo')"
            >
              {{ $t("care.weather.types.openMeteo") }}
            </button>
          </div>

          <!-- Name -->
          <input
            v-model="form.name"
            :placeholder="$t('care.weather.form.name')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />

          <!-- HA Entity ID -->
          <template v-if="form.sourceType === 'ha_entity'">
            <input
              v-model="form.haEntityId"
              placeholder="weather.home"
              class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
            />
          </template>

          <!-- Weather API Fields -->
          <template v-else>
            <input
              v-if="form.provider === 'qweather'"
              v-model="form.location"
              :placeholder="$t('care.weather.form.location')"
              class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
            />
            <div class="grid grid-cols-2 gap-2">
              <input
                v-model="form.latitude"
                :placeholder="$t('care.weather.form.latitude')"
                class="rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              />
              <input
                v-model="form.longitude"
                :placeholder="$t('care.weather.form.longitude')"
                class="rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              />
            </div>
          </template>

          <!-- Fetch Frequency -->
          <input
            v-model="form.fetchFrequency"
            :placeholder="$t('care.weather.form.fetchFrequency')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
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