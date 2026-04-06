<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
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
const now = ref(new Date());
let clockTimer: number | null = null;

const weatherTemperature = computed(() => {
  const value = props.weather?.temperature;
  return typeof value === "number" ? `${value.toFixed(1)}°C` : "--";
});

const feelsLikeLabel = computed(() => {
  const value = props.weather?.feels_like;
  return typeof value === "number" ? `${value.toFixed(1)}°C` : "--";
});

const airQuality = computed(() => props.weather?.air_quality ?? null);
const forecastItems = computed(() => props.weather?.forecast ?? []);
const hourlyForecastItems = computed(() => props.weather?.hourly_forecast ?? []);
const indexItems = computed(() => props.weather?.indices ?? []);
const warningItems = computed(() => props.weather?.warnings ?? []);
const airQualityTone = computed(() => {
  const category = String(airQuality.value?.category || "").toLowerCase();
  if (["excellent", "good", "优", "良"].some((token) => category.includes(token))) {
    return {
      card: "bg-[#ECFDF3] border-[#ABEFC6]",
      badge: "bg-[#D1FADF] text-[#067647]",
      title: "text-[#067647]",
      text: "text-[#344054]",
    };
  }
  if (["moderate", "fair", "一般", "轻度"].some((token) => category.includes(token))) {
    return {
      card: "bg-[#FFFAEB] border-[#F7CE8E]",
      badge: "bg-[#FEF0C7] text-[#B54708]",
      title: "text-[#B54708]",
      text: "text-[#7A2E0E]",
    };
  }
  if (["poor", "unhealthy", "bad", "中度", "重度", "严重"].some((token) => category.includes(token))) {
    return {
      card: "bg-[#FEF3F2] border-[#FECACA]",
      badge: "bg-[#FEE4E2] text-[#B42318]",
      title: "text-[#B42318]",
      text: "text-[#7A271A]",
    };
  }
  return {
    card: "bg-[#F9FAFB] border-[#E4E7EC]",
    badge: "bg-[#F2F4F7] text-[#344054]",
    title: "text-[#1F2A22]",
    text: "text-[#667085]",
  };
});

const airQualityBadgeLabel = computed(() => {
  if (!airQuality.value) return "";
  const parts = [airQuality.value.aqi, airQuality.value.category].filter(Boolean);
  return parts.map((part) => String(part)).join(" ");
});

function formatForecastTemperature(min?: number | null, max?: number | null) {
  const minLabel = typeof min === "number" ? `${min.toFixed(0)}°` : "--";
  const maxLabel = typeof max === "number" ? `${max.toFixed(0)}°` : "--";
  return `${minLabel} / ${maxLabel}`;
}

const currentTimeLabel = computed(() => {
  const year = now.value.getFullYear();
  const month = `${now.value.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.value.getDate()}`.padStart(2, "0");
  const hours = `${now.value.getHours()}`.padStart(2, "0");
  const minutes = `${now.value.getMinutes()}`.padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
});

function weatherEmoji(text?: string) {
  const value = String(text || "");
  if (value.includes("雾") || value.includes("霾") || value.includes("烟")) return "🌫️";
  if (value.includes("雷")) return "⛈️";
  if (value.includes("雪")) return "❄️";
  if (value.includes("雨")) return "🌧️";
  if (value.includes("云") || value.includes("阴")) return "☁️";
  if (value.includes("风")) return "🌬️";
  if (value.includes("晴")) return "☀️";
  return "🌤️";
}

function formatHourlyTime(value?: string) {
  const raw = String(value || "").trim();
  if (!raw) return "--:--";
  const match = raw.match(/T(\d{2}:\d{2})/);
  return match?.[1] ?? raw.slice(-5);
}

onMounted(() => {
  clockTimer = window.setInterval(() => {
    now.value = new Date();
  }, 1000);
});

onBeforeUnmount(() => {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer);
  }
});
</script>

<template>
  <div class="rounded-[20px] border border-[#E4E7EC] bg-white overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-4 border-b border-[#E4E7EC]">
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-[#1F2A22]">{{ $t("care.weather.title") }}</div>
        <div class="flex gap-2">
          <button
            class="rounded-full border border-[#CFE5D6] bg-white px-3 py-1.5 text-xs text-[#344054] transition-all hover:border-[#07C160]/30 hover:text-[#07C160] disabled:opacity-50"
            :disabled="weatherLoading || !weatherSourceId"
            @click="emit('refreshWeather')"
          >
            {{ $t("care.weather.refresh") }}
          </button>
          <button
            class="rounded-full border border-[#E4E7EC] bg-white px-3 py-1.5 text-xs text-[#344054] transition-all hover:border-[#07C160]/30 hover:text-[#07C160] disabled:opacity-50"
            :disabled="weatherLoading"
            @click="emit('openDataSourceDialog')"
          >
            {{ $t("care.weather.dataSource") }}
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
            <div class="flex flex-wrap items-center gap-2">
              <div class="text-sm text-[#344054]">{{ `${weatherEmoji(weather.condition)} ${weather.condition || "--"}` }}</div>
              <div
                v-if="airQualityBadgeLabel"
                class="rounded-full px-2 py-1 text-[10px] font-medium"
                :class="airQualityTone.badge"
              >
                AQI {{ airQualityBadgeLabel }}
              </div>
            </div>
            <div class="mt-1 text-xs text-[#667085]">
              {{ $t("care.weather.indices.feelsLike") }}: {{ feelsLikeLabel }}
            </div>
            <div class="text-xs text-[#667085]">{{ currentTimeLabel }}</div>
          </div>
        </div>
      </div>
      <div v-else class="rounded-2xl border border-dashed border-[#D0D5DD] px-4 py-5 text-sm text-[#98A2B3] mb-3">
        {{ weatherSourceId ? $t("care.weather.empty") : $t("care.weather.noSource") }}
      </div>

      <div v-if="hourlyForecastItems.length > 0" class="mt-3">
        <div class="mb-2 text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.sections.recent") }}</div>
        <div class="weather-hourly-strip flex gap-2 overflow-x-auto pb-2">
          <div
            v-for="item in hourlyForecastItems"
            :key="`${item.time}-${item.text}`"
            class="min-w-[76px] rounded-xl border border-[#E9EEF1] bg-[#FBFDFC] px-3 py-3 text-center"
          >
            <div class="text-[11px] font-medium text-[#667085]">{{ formatHourlyTime(item.time) }}</div>
            <div class="mt-2 text-lg leading-none">{{ weatherEmoji(item.text) }}</div>
            <div class="mt-2 text-sm font-semibold text-[#1F2A22]">
              {{ typeof item.temp === "number" ? `${item.temp.toFixed(0)}°` : "--" }}
            </div>
            <div class="mt-1 text-[11px] text-[#667085] truncate">{{ item.text || "--" }}</div>
            <div
              v-if="item.pop"
              class="mt-2 inline-flex rounded-full bg-[#EEF4FF] px-2 py-1 text-[10px] font-medium text-[#3559B2]"
            >
              {{ item.pop }}%
            </div>
          </div>
        </div>
      </div>

      <div v-if="forecastItems.length > 0" class="mt-3">
        <div class="mb-2 text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.sections.forecast") }}</div>
        <div class="grid gap-2 sm:grid-cols-3">
          <div v-for="item in forecastItems" :key="item.date" class="rounded-xl border border-[#E9EEF1] bg-[#FBFDFC] p-3">
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs font-medium text-[#344054]">{{ item.date || "--" }}</div>
              <div class="text-lg leading-none">{{ weatherEmoji(item.textDay) }}</div>
            </div>
            <div class="mt-1 text-sm font-semibold text-[#1F2A22]">{{ item.textDay || "--" }}</div>
            <div class="mt-2 text-xs text-[#667085]">{{ formatForecastTemperature(item.tempMin, item.tempMax) }}</div>
            <div v-if="item.uvIndex" class="mt-1 text-xs text-[#667085]">{{ $t("care.weather.forecast.uv") }}: {{ item.uvIndex }}</div>
          </div>
        </div>
      </div>

      <div v-if="indexItems.length > 0" class="mt-3">
        <div class="mb-2 text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.sections.indices") }}</div>
        <div class="grid gap-2">
          <div
            v-for="item in indexItems"
            :key="`${item.name}-${item.category}`"
            class="flex items-center justify-between gap-3 rounded-xl border border-[#E9EEF1] bg-[#FBFDFC] px-3 py-3"
          >
            <div class="min-w-0 text-sm font-medium text-[#223126] truncate">
              {{ item.name || "--" }}
            </div>
            <span class="inline-flex shrink-0 rounded-full bg-[#E8F8EC] px-2.5 py-1 text-[10px] font-medium text-[#138A6B]">
              {{ item.category || "--" }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="warningItems.length > 0" class="mt-3">
        <div class="mb-2 text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.sections.warning") }}</div>
        <div class="space-y-2">
          <div v-for="item in warningItems" :key="`${item.title}-${item.severity}`" class="rounded-xl border border-[#FECACA] bg-[#FFF5F5] p-3">
            <div class="flex items-center justify-between gap-2">
              <div class="text-sm font-semibold text-[#B42318]">{{ item.title || "--" }}</div>
              <div v-if="item.severity" class="rounded-full bg-white/80 px-2 py-1 text-[10px] font-medium text-[#B42318]">{{ item.severity }}</div>
            </div>
            <div v-if="item.typeName" class="mt-1 text-xs text-[#B54708]">{{ item.typeName }}</div>
            <div v-if="item.text" class="mt-2 text-xs leading-5 text-[#7A271A]">{{ item.text }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.weather-hourly-strip {
  scrollbar-width: none;
}

.weather-hourly-strip::-webkit-scrollbar {
  height: 0;
}

.weather-hourly-strip:hover {
  scrollbar-width: thin;
}

.weather-hourly-strip:hover::-webkit-scrollbar {
  height: 8px;
}

.weather-hourly-strip:hover::-webkit-scrollbar-track {
  background: #eef2ef;
  border-radius: 999px;
}

.weather-hourly-strip:hover::-webkit-scrollbar-thumb {
  background: #c7d4cc;
  border-radius: 999px;
}
</style>
