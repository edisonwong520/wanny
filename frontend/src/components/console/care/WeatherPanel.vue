<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { WeatherSnapshot } from "@/lib/care";

const props = defineProps<{
  weather: WeatherSnapshot | null;
  weatherSourceId: number | null;
  weatherLoading: boolean;
}>();

const emit = defineEmits<{
  refreshWeather: [];
  openDataSourceDialog: [];
}>();

const { t } = useI18n();

const weatherTemperature = computed(() => {
  const value = props.weather?.temperature;
  return typeof value === "number" ? `${value.toFixed(1)}°C` : "--";
});

const weatherDelta = computed(() => {
  const current = props.weather?.temperature;
  const previous = props.weather?.previous_temperature;
  if (typeof current !== "number" || typeof previous !== "number") return "";
  const diff = current - previous;
  if (Math.abs(diff) < 0.1) return "0.0°C";
  return `${diff > 0 ? "+" : ""}${diff.toFixed(1)}°C`;
});

function getWeatherIndex(key: string): string {
  const raw = props.weather?.raw;
  if (typeof raw !== "object" || raw === null) return "--";
  const value = (raw as Record<string, unknown>)[key];
  if (value === null || value === undefined) return "--";
  return String(value);
}
</script>

<template>
  <div class="rounded-[20px] border border-[#E4E7EC] bg-white overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-4 border-b border-[#E4E7EC]">
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-[#1F2A22]">{{ $t("care.weather.title") }}</div>
        <div class="flex gap-2">
          <button
            class="rounded-full border border-[#E4E7EC] bg-white px-3 py-1.5 text-xs text-[#344054] transition-all hover:border-[#07C160]/30 hover:text-[#07C160] disabled:opacity-50"
            :disabled="weatherLoading"
            @click="emit('openDataSourceDialog')"
          >
            {{ $t("care.weather.dataSource") }}
          </button>
          <button
            class="rounded-full border border-[#CFE5D6] bg-white px-3 py-1.5 text-xs text-[#344054] transition-all hover:border-[#07C160]/30 hover:text-[#07C160] disabled:opacity-50"
            :disabled="weatherLoading || !weatherSourceId"
            @click="emit('refreshWeather')"
          >
            {{ $t("care.weather.refresh") }}
          </button>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="p-4">
      <!-- Current Weather -->
      <div v-if="weatherLoading" class="rounded-2xl bg-[#F9FAFB] px-4 py-5 text-sm text-[#98A2B3]">
        {{ $t("common.loading") }}
      </div>
      <div v-else-if="weather" class="rounded-2xl bg-gradient-to-br from-[#E8F8EC] to-[#F2FBF5] p-4 mb-3">
        <div class="flex items-center gap-4">
          <div class="text-[36px] font-semibold text-[#1F2A22] leading-none">{{ weatherTemperature }}</div>
          <div>
            <div class="text-sm text-[#344054]">{{ weather.condition || "--" }}</div>
            <div class="text-xs text-[#667085]">
              {{ weather.provider || "--" }}
            </div>
          </div>
        </div>
        <div v-if="weatherDelta" class="mt-2 text-xs text-[#667085]">
          {{ $t("care.weather.delta") }}: {{ weatherDelta }}
        </div>
      </div>
      <div v-else class="rounded-2xl border border-dashed border-[#D0D5DD] px-4 py-5 text-sm text-[#98A2B3] mb-3">
        {{ weatherSourceId ? $t("care.weather.empty") : $t("care.weather.noSource") }}
      </div>

      <!-- Weather Indices -->
      <div v-if="weather" class="grid grid-cols-2 gap-2">
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.humidity") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ getWeatherIndex("humidity") }}%</div>
        </div>
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.feelsLike") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ getWeatherIndex("feelsLike") }}°C</div>
        </div>
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.wind") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ getWeatherIndex("windDir") || getWeatherIndex("wind_dir") }}</div>
        </div>
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.pressure") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ getWeatherIndex("pressure") }}hPa</div>
        </div>
      </div>
    </div>
  </div>
</template>