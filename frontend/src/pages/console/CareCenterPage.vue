<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import CareSuggestionCard from "@/components/console/care/CareSuggestionCard.vue";
import ConfirmActionDialog from "@/components/console/care/ConfirmActionDialog.vue";
import {
  type CareConfirmDetail,
  type CareSuggestionRecord,
  executeCareSuggestion,
  fetchCurrentWeather,
  fetchCareConfirmDetail,
  fetchCareSuggestions,
  refreshCurrentWeather,
  runCareInspection,
  sendCareSuggestionFeedback,
  type WeatherSnapshot,
} from "@/lib/care";
import { formatDateTime } from "@/lib/utils";

const { t } = useI18n();
const CARE_FILTER_STORAGE_KEY = "wanny-care-center-filters";

const loading = ref(false);
const weatherLoading = ref(false);
const processingId = ref<number | null>(null);
const suggestions = ref<CareSuggestionRecord[]>([]);
const weather = ref<WeatherSnapshot | null>(null);
const weatherSourceId = ref<number | null>(null);
const activeFilter = ref<"all" | "pending" | "approved" | "executed" | "failed">("pending");
const activePriority = ref<"all" | "high" | "medium" | "low">("all");
const activeSuggestionType = ref<"all" | "inspection" | "care">("all");
const errorMessage = ref("");
const actionMessage = ref("");
const selectedSuggestionId = ref<number | null>(null);
const rejectDialogOpen = ref(false);
const confirmDialogOpen = ref(false);
const pendingConfirmAction = ref<"approve" | "execute">("approve");
const rejectReason = ref("");
const confirmDetail = ref<CareConfirmDetail | null>(null);

const visibleCountLabel = computed(() =>
  t("care.labels.filteredCount", {
    count: filteredSuggestions.value.length,
  }),
);

const filters = computed(() => [
  { id: "all", label: t("care.filters.all") },
  { id: "pending", label: t("care.filters.pending") },
  { id: "approved", label: t("care.filters.approved") },
  { id: "executed", label: t("care.filters.executed") },
  { id: "failed", label: t("care.filters.failed") },
]);

const priorityFilters = computed(() => [
  { id: "all", label: t("care.filters.allPriorities") },
  { id: "high", label: t("care.filters.high") },
  { id: "medium", label: t("care.filters.medium") },
  { id: "low", label: t("care.filters.low") },
]);

const suggestionTypeFilters = computed(() => [
  { id: "all", label: t("care.filters.allTypes") },
  { id: "inspection", label: t("care.filters.inspection") },
  { id: "care", label: t("care.filters.care") },
]);

const filteredSuggestions = computed(() => suggestions.value);

const selectedSuggestion = computed(
  () => filteredSuggestions.value.find((item) => item.id === selectedSuggestionId.value) ?? filteredSuggestions.value[0] ?? null,
);

const selectedAggregationMarkers = computed(() => {
  return (selectedSuggestion.value?.aggregationSources ?? []).slice(0, 6);
});

const selectedPushAuditBadges = computed(() => {
  const audit = selectedSuggestion.value?.pushAudit;
  if (!audit) return [];
  const badges = [t(`care.push.levels.${audit.level}`)];
  if (audit.consoleOnly) {
    badges.push(t("care.push.consoleOnly"));
  }
  if (audit.suppressReason) {
    badges.push(t(`care.push.reasons.${audit.suppressReason}`));
  }
  return badges;
});

const pushOverview = computed(() => {
  const overview = {
    total: suggestions.value.length,
    high: 0,
    medium: 0,
    low: 0,
    consoleOnly: 0,
    ignoredCooldown: 0,
    repeatGap: 0,
  };

  for (const item of suggestions.value) {
    const audit = item.pushAudit;
    if (!audit) continue;
    overview[audit.level] += 1;
    if (audit.consoleOnly) overview.consoleOnly += 1;
    if (audit.suppressReason === "ignored_cooldown") overview.ignoredCooldown += 1;
    if (audit.suppressReason === "repeat_gap") overview.repeatGap += 1;
  }

  return overview;
});

function priorityClass(priority: number) {
  if (priority >= 7) return "bg-[#FFE8E8] text-[#D92D20]";
  if (priority >= 4) return "bg-[#FFF7E6] text-[#E8A223]";
  return "bg-[#E8F8EC] text-[#07C160]";
}

function loadSavedFilters() {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(CARE_FILTER_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as {
      status?: "all" | "pending" | "approved" | "executed" | "failed";
      priority?: "all" | "high" | "medium" | "low";
      suggestionType?: "all" | "inspection" | "care";
      suggestionId?: number | null;
    };
    if (parsed.status) activeFilter.value = parsed.status;
    if (parsed.priority) activePriority.value = parsed.priority;
    if (parsed.suggestionType) activeSuggestionType.value = parsed.suggestionType;
    if (typeof parsed.suggestionId === "number") selectedSuggestionId.value = parsed.suggestionId;
  } catch {
    // Ignore broken localStorage payloads.
  }
}

function persistFilters() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    CARE_FILTER_STORAGE_KEY,
    JSON.stringify({
      status: activeFilter.value,
      priority: activePriority.value,
      suggestionType: activeSuggestionType.value,
      suggestionId: selectedSuggestionId.value,
    }),
  );
}

function selectStatusFilter(filterId: "all" | "pending" | "approved" | "executed" | "failed") {
  activeFilter.value = filterId;
  persistFilters();
  void loadSuggestions();
}

function selectPriorityFilter(filterId: "all" | "high" | "medium" | "low") {
  activePriority.value = filterId;
  persistFilters();
  void loadSuggestions();
}

function selectSuggestionTypeFilter(filterId: "all" | "inspection" | "care") {
  activeSuggestionType.value = filterId;
  persistFilters();
  void loadSuggestions();
}

const weatherTemperature = computed(() => {
  const value = weather.value?.temperature;
  return typeof value === "number" ? `${value.toFixed(1)}°C` : "--";
});

const weatherDelta = computed(() => {
  const current = weather.value?.temperature;
  const previous = weather.value?.previous_temperature;
  if (typeof current !== "number" || typeof previous !== "number") return "";
  const diff = current - previous;
  if (Math.abs(diff) < 0.1) return "0.0°C";
  return `${diff > 0 ? "+" : ""}${diff.toFixed(1)}°C`;
});

async function loadWeather() {
  weatherLoading.value = true;
  try {
    const response = await fetchCurrentWeather();
    weather.value = response.weather && Object.keys(response.weather).length > 0 ? response.weather : null;
    weatherSourceId.value = response.sourceId;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.loadWeather");
  } finally {
    weatherLoading.value = false;
  }
}

async function loadSuggestions() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await fetchCareSuggestions({
      status: activeFilter.value === "all" ? undefined : activeFilter.value,
      suggestionType: activeSuggestionType.value === "all" ? undefined : activeSuggestionType.value,
      priority: activePriority.value === "all" ? undefined : activePriority.value,
    });
    suggestions.value = response.suggestions;
    if (!selectedSuggestionId.value && response.suggestions.length > 0) {
      selectedSuggestionId.value = response.suggestions[0].id;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.load");
  } finally {
    loading.value = false;
  }
}

function clearFilters() {
  activeFilter.value = "pending";
  activePriority.value = "all";
  activeSuggestionType.value = "all";
  persistFilters();
  void loadSuggestions();
}

async function selectSuggestion(id: number) {
  selectedSuggestionId.value = id;
  confirmDetail.value = null;
  try {
    const response = await fetchCareConfirmDetail(id);
    confirmDetail.value = response.confirmDetail;
  } catch {
    confirmDetail.value = null;
  }
}

async function submitFeedback(action: "approve" | "reject" | "ignore", reason = "") {
  if (!selectedSuggestion.value || processingId.value) return;
  processingId.value = selectedSuggestion.value.id;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const response = await sendCareSuggestionFeedback(selectedSuggestion.value.id, action, reason);
    actionMessage.value = t(`care.feedback.${response.status}`);
    await loadSuggestions();
    if (selectedSuggestionId.value) {
      await selectSuggestion(selectedSuggestionId.value);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    processingId.value = null;
  }
}

async function handleExecute() {
  if (!selectedSuggestion.value || processingId.value) return;
  processingId.value = selectedSuggestion.value.id;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const response = await executeCareSuggestion(selectedSuggestion.value.id);
    actionMessage.value = response.result?.message || t("care.feedback.executed");
    await loadSuggestions();
    if (selectedSuggestionId.value) {
      await selectSuggestion(selectedSuggestionId.value);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    processingId.value = null;
  }
}

async function handleIgnore() {
  await submitFeedback("ignore");
}

function openRejectDialog() {
  rejectReason.value = "";
  rejectDialogOpen.value = true;
}

function closeRejectDialog() {
  rejectDialogOpen.value = false;
  rejectReason.value = "";
}

async function confirmReject() {
  await submitFeedback("reject", rejectReason.value.trim());
  closeRejectDialog();
}

async function openConfirmDialog(action: "approve" | "execute") {
  pendingConfirmAction.value = action;
  if (selectedSuggestion.value) {
    await selectSuggestion(selectedSuggestion.value.id);
  }
  confirmDialogOpen.value = true;
}

function closeConfirmDialog() {
  confirmDialogOpen.value = false;
}

async function confirmAction() {
  if (pendingConfirmAction.value === "approve") {
    await submitFeedback("approve");
  } else {
    await handleExecute();
  }
  closeConfirmDialog();
}

async function handleRunInspection() {
  if (loading.value) return;
  loading.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const response = await runCareInspection();
    actionMessage.value = t("care.feedback.scanCreated", { count: response.created.length });
    await loadSuggestions();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    loading.value = false;
  }
}

async function handleRefreshWeather() {
  weatherLoading.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const response = await refreshCurrentWeather();
    weather.value = response.weather && Object.keys(response.weather).length > 0 ? response.weather : null;
    weatherSourceId.value = response.sourceId;
    actionMessage.value = response.suggestionId
      ? t("care.feedback.weatherTriggered")
      : t("care.feedback.weatherRefreshed");
    await loadSuggestions();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    weatherLoading.value = false;
  }
}

onMounted(async () => {
  loadSavedFilters();
  await Promise.all([loadSuggestions(), loadWeather()]);
  if (selectedSuggestionId.value) {
    await selectSuggestion(selectedSuggestionId.value);
  }
});

watch(selectedSuggestion, async (next, previous) => {
  if (!next) {
    confirmDetail.value = null;
    if (selectedSuggestionId.value !== null) {
      selectedSuggestionId.value = null;
      persistFilters();
    }
    return;
  }
  if (next.id !== selectedSuggestionId.value) {
    selectedSuggestionId.value = next.id;
    persistFilters();
  }
  if (!confirmDetail.value || previous?.id !== next.id) {
    await selectSuggestion(next.id);
  }
});
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-[28px] border border-[#DDEEE2] bg-[linear-gradient(180deg,#FCFFFD_0%,#F2FBF5_100%)] p-5 shadow-[0_18px_40px_rgba(7,193,96,0.06)]">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div class="text-xs font-semibold uppercase tracking-[0.2em] text-[#07C160]/70">{{ $t("care.eyebrow") }}</div>
          <h1 class="mt-2 text-3xl font-semibold tracking-tight text-[#1F2A22]">{{ $t("care.title") }}</h1>
          <p class="mt-2 max-w-2xl text-sm leading-7 text-[#667085]">{{ $t("care.description") }}</p>
        </div>
        <div class="flex gap-2">
          <RouterLink
            to="/console/care/rules"
            class="inline-flex h-[38px] items-center rounded-full border border-[#D0E6D7] bg-white px-4 text-sm text-[#344054] transition-all hover:-translate-y-0.5 hover:border-[#07C160]/30 hover:text-[#07C160]"
          >
            {{ $t("care.actions.manageRules") }}
          </RouterLink>
          <button
            class="inline-flex h-[38px] items-center rounded-full bg-[#07C160] px-4 text-sm font-medium text-white transition-all hover:-translate-y-0.5 hover:bg-[#06AD56] disabled:opacity-50"
            :disabled="loading"
            @click="handleRunInspection"
          >
            {{ $t("care.actions.scanNow") }}
          </button>
        </div>
      </div>
    </section>

    <div v-if="errorMessage" class="rounded-2xl bg-[#FFE8E8] px-4 py-3 text-sm text-[#E84343]">
      {{ errorMessage }}
    </div>
    <div v-if="actionMessage" class="rounded-2xl bg-[#E8F8EC] px-4 py-3 text-sm text-[#07C160]">
      {{ actionMessage }}
    </div>

    <div class="grid gap-5 lg:grid-cols-12">
      <section class="lg:col-span-5">
        <div class="mb-5 rounded-3xl border border-[#DDEEE2] bg-[linear-gradient(180deg,#FCFFFD_0%,#F4FBF6_100%)] p-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#07C160]/70">{{ $t("care.weather.eyebrow") }}</div>
              <div class="mt-2 text-lg font-semibold text-[#1F2A22]">{{ $t("care.weather.title") }}</div>
              <div class="mt-1 text-xs text-[#667085]">
                {{
                  weather?.fetched_at
                    ? `${$t("care.weather.snapshot")} · ${formatDateTime(weather.fetched_at)}`
                    : $t("care.weather.noSource")
                }}
              </div>
            </div>
            <button
              class="inline-flex h-[34px] items-center rounded-full border border-[#CFE5D6] bg-white px-3 text-xs font-medium text-[#344054] transition-all hover:-translate-y-0.5 hover:border-[#07C160]/30 hover:text-[#07C160] disabled:opacity-50"
              :disabled="weatherLoading || !weatherSourceId"
              @click="handleRefreshWeather"
            >
              {{ $t("care.weather.refresh") }}
            </button>
          </div>

          <div v-if="weatherLoading" class="mt-4 rounded-2xl bg-white/80 px-4 py-5 text-sm text-[#98A2B3]">
            {{ $t("common.loading") }}
          </div>
          <div v-else-if="weather" class="mt-4 grid gap-3 md:grid-cols-2">
            <div class="rounded-2xl border border-white/80 bg-white/90 p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.weather.snapshot") }}</div>
              <div class="mt-2 text-3xl font-semibold text-[#1F2A22]">{{ weatherTemperature }}</div>
              <div class="mt-1 text-sm text-[#667085]">{{ weather.condition || "--" }}</div>
            </div>
            <div class="rounded-2xl border border-white/80 bg-white/90 p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.weather.delta") }}</div>
              <div class="mt-2 text-2xl font-semibold text-[#1F2A22]">{{ weatherDelta || "--" }}</div>
              <div class="mt-1 text-sm text-[#667085]">{{ weather.provider || "--" }}</div>
            </div>
          </div>
          <div v-else class="mt-4 rounded-2xl border border-dashed border-[#D0D5DD] px-4 py-5 text-sm text-[#98A2B3]">
            {{ weatherSourceId ? $t("care.weather.empty") : $t("care.weather.noSource") }}
          </div>
        </div>

        <div class="mb-5 rounded-3xl border border-[#E4E7EC] bg-white p-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.push.overviewTitle") }}</div>
              <div class="mt-1 text-sm text-[#667085]">{{ $t("care.push.overviewDescription") }}</div>
            </div>
            <div class="rounded-full bg-[#F2F4F7] px-3 py-1 text-xs font-medium text-[#344054]">
              {{ $t("care.push.total", { count: pushOverview.total }) }}
            </div>
          </div>
          <div class="mt-4 grid gap-3 sm:grid-cols-3">
            <div class="rounded-2xl bg-[#FFF4F3] p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.push.levels.high") }}</div>
              <div class="mt-2 text-2xl font-semibold text-[#D92D20]">{{ pushOverview.high }}</div>
            </div>
            <div class="rounded-2xl bg-[#FFF8EB] p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.push.levels.medium") }}</div>
              <div class="mt-2 text-2xl font-semibold text-[#E8A223]">{{ pushOverview.medium }}</div>
            </div>
            <div class="rounded-2xl bg-[#F2F4F7] p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.push.levels.low") }}</div>
              <div class="mt-2 text-2xl font-semibold text-[#475467]">{{ pushOverview.low }}</div>
            </div>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-3">
            <div class="rounded-2xl border border-[#E4E7EC] bg-[#FCFCFD] p-4">
              <div class="text-xs text-[#98A2B3]">{{ $t("care.push.consoleOnly") }}</div>
              <div class="mt-2 text-lg font-semibold text-[#101828]">{{ pushOverview.consoleOnly }}</div>
            </div>
            <div class="rounded-2xl border border-[#E4E7EC] bg-[#FCFCFD] p-4">
              <div class="text-xs text-[#98A2B3]">{{ $t("care.push.reasons.ignored_cooldown") }}</div>
              <div class="mt-2 text-lg font-semibold text-[#101828]">{{ pushOverview.ignoredCooldown }}</div>
            </div>
            <div class="rounded-2xl border border-[#E4E7EC] bg-[#FCFCFD] p-4">
              <div class="text-xs text-[#98A2B3]">{{ $t("care.push.reasons.repeat_gap") }}</div>
              <div class="mt-2 text-lg font-semibold text-[#101828]">{{ pushOverview.repeatGap }}</div>
            </div>
          </div>
        </div>

        <div class="rounded-3xl border border-[#E4E7EC] bg-white p-4">
          <div class="mb-3 flex items-center justify-between gap-3">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.filters.status") }}</div>
              <div class="mt-1 text-xs text-[#667085]">{{ visibleCountLabel }}</div>
            </div>
            <button
              class="rounded-full border border-[#D0D5DD] bg-white px-3 py-1.5 text-xs text-[#475467] transition-all hover:border-[#07C160]/30 hover:text-[#07C160]"
              @click="clearFilters"
            >
              {{ $t("care.filters.reset") }}
            </button>
          </div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button
              v-for="filter in filters"
              :key="filter.id"
              class="rounded-full px-3 py-1.5 text-xs transition-all"
              :class="activeFilter === filter.id ? 'bg-[#07C160] text-white' : 'bg-[#F7F7F7] text-[#667085] hover:bg-[#EDF7F0]'"
              @click="selectStatusFilter(filter.id as 'all' | 'pending' | 'approved' | 'executed' | 'failed')"
            >
              {{ filter.label }}
            </button>
          </div>
          <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.filters.priority") }}</div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button
              v-for="filter in priorityFilters"
              :key="filter.id"
              class="rounded-full px-3 py-1.5 text-xs transition-all"
              :class="activePriority === filter.id ? 'bg-[#1F2A22] text-white' : 'bg-[#F7F7F7] text-[#667085] hover:bg-[#EDF7F0]'"
              @click="selectPriorityFilter(filter.id as 'all' | 'high' | 'medium' | 'low')"
            >
              {{ filter.label }}
            </button>
          </div>
          <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.filters.type") }}</div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button
              v-for="filter in suggestionTypeFilters"
              :key="filter.id"
              class="rounded-full px-3 py-1.5 text-xs transition-all"
              :class="activeSuggestionType === filter.id ? 'bg-[#138A6B] text-white' : 'bg-[#F7F7F7] text-[#667085] hover:bg-[#EDF7F0]'"
              @click="selectSuggestionTypeFilter(filter.id as 'all' | 'inspection' | 'care')"
            >
              {{ filter.label }}
            </button>
          </div>

          <div v-if="loading" class="py-10 text-center text-sm text-[#98A2B3]">
            {{ $t("common.loading") }}
          </div>
          <div v-else-if="filteredSuggestions.length === 0" class="rounded-2xl border border-dashed border-[#D0D5DD] px-4 py-10 text-center text-sm text-[#98A2B3]">
            {{ $t("care.empty") }}
          </div>
          <div v-else class="space-y-3">
            <CareSuggestionCard
              v-for="item in filteredSuggestions"
              :key="item.id"
              :item="item"
              :selected="selectedSuggestion?.id === item.id"
              @select="selectSuggestion"
            />
          </div>
        </div>
      </section>

      <section class="lg:col-span-7">
        <div class="rounded-3xl border border-[#E4E7EC] bg-white p-5 min-h-[460px]">
          <template v-if="selectedSuggestion">
            <div class="flex items-start justify-between gap-4">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#07C160]/70">{{ $t("care.labels.detail") }}</div>
                <h2 class="mt-2 text-2xl font-semibold text-[#1F2A22]">{{ selectedSuggestion.title }}</h2>
                <p class="mt-2 text-sm leading-7 text-[#667085]">{{ selectedSuggestion.body }}</p>
              </div>
              <span class="rounded-full px-3 py-1 text-xs font-semibold capitalize" :class="priorityClass(selectedSuggestion.priority)">
                {{ selectedSuggestion.status }}
              </span>
            </div>

            <div class="mt-5 grid gap-3 md:grid-cols-2">
              <div class="rounded-2xl border border-[#E9EEF1] bg-[#FBFDFC] p-4">
                <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.labels.device") }}</div>
                <div class="mt-2 text-sm font-medium text-[#223126]">{{ selectedSuggestion.device?.name || $t("care.labels.noDevice") }}</div>
                <div class="mt-1 text-xs text-[#667085]">{{ selectedSuggestion.device?.category || "-" }}</div>
                <div v-if="selectedSuggestion.aggregatedCount > 1" class="mt-2 text-[11px] text-[#138A6B]">
                  {{ $t("care.labels.aggregated", { count: selectedSuggestion.aggregatedCount }) }}
                </div>
              </div>
              <div class="rounded-2xl border border-[#E9EEF1] bg-[#FBFDFC] p-4">
                <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.labels.control") }}</div>
                <div class="mt-2 text-sm font-medium text-[#223126]">{{ selectedSuggestion.control?.label || "-" }}</div>
                <div class="mt-1 text-xs text-[#667085]">{{ selectedSuggestion.control?.key || "-" }}</div>
              </div>
            </div>

            <div
              v-if="selectedSuggestion.aggregatedCount > 1"
              class="mt-5 rounded-3xl border border-[#E6F3EA] bg-[#FAFDFB] p-4"
            >
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.labels.aggregationTitle") }}</div>
              <div class="mt-2 text-sm text-[#344054]">
                {{ $t("care.labels.aggregationSummary", { count: selectedSuggestion.aggregatedCount }) }}
              </div>
              <div v-if="selectedAggregationMarkers.length > 0" class="mt-3 flex flex-wrap gap-2">
                <div
                  v-for="source in selectedAggregationMarkers"
                  :key="`${source.kind}:${source.id ?? source.label}`"
                  class="inline-flex items-center gap-1 rounded-full bg-[#EEF7F1] px-2.5 py-1 text-[11px] font-medium text-[#138A6B]"
                >
                  <span>{{ source.label }}</span>
                  <span v-if="source.detail" class="text-[#0F6B52]/70">· {{ source.detail }}</span>
                </div>
              </div>
            </div>

            <div class="mt-5 rounded-3xl border border-[#E4E7EC] bg-[#FCFCFD] p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.push.title") }}</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.push.level") }}</div>
                  <div class="mt-1 flex flex-wrap gap-2">
                    <span
                      v-for="badge in selectedPushAuditBadges"
                      :key="badge"
                      class="inline-flex rounded-full bg-[#F2F4F7] px-2.5 py-1 text-[11px] font-medium text-[#344054]"
                    >
                      {{ badge }}
                    </span>
                  </div>
                </div>
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.push.count") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ selectedSuggestion.pushAudit.pushCount }}</div>
                </div>
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.push.lastPushedAt") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ formatDateTime(selectedSuggestion.pushAudit.lastPushedAt) }}</div>
                </div>
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.push.repeatEligibleAt") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ formatDateTime(selectedSuggestion.pushAudit.repeatEligibleAt) }}</div>
                </div>
                <div v-if="selectedSuggestion.pushAudit.ignoredUntil">
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.push.ignoredUntil") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ formatDateTime(selectedSuggestion.pushAudit.ignoredUntil) }}</div>
                </div>
              </div>
            </div>

            <div v-if="confirmDetail" class="mt-5 rounded-3xl border border-[#DDEEE2] bg-[linear-gradient(180deg,#FCFFFD_0%,#F6FBF8_100%)] p-4">
              <div class="text-xs uppercase tracking-[0.16em] text-[#07C160]/70">{{ $t("care.labels.confirm") }}</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.labels.targetDevice") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ confirmDetail.deviceName || confirmDetail.deviceId || "-" }}</div>
                </div>
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.labels.targetControl") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ confirmDetail.controlLabel || confirmDetail.controlId || "-" }}</div>
                </div>
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.labels.action") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ confirmDetail.action || "-" }}</div>
                </div>
                <div>
                  <div class="text-xs text-[#98A2B3]">{{ $t("care.labels.value") }}</div>
                  <div class="mt-1 text-sm text-[#223126]">{{ JSON.stringify(confirmDetail.value ?? null) }}</div>
                </div>
              </div>
            </div>

            <div class="mt-6 flex flex-wrap gap-2">
              <button
                v-if="selectedSuggestion.canApprove"
                class="rounded-full bg-[#07C160] px-4 py-2 text-sm font-medium text-white transition-all hover:-translate-y-0.5 hover:bg-[#06AD56] disabled:opacity-50"
                :disabled="processingId === selectedSuggestion.id"
                @click="openConfirmDialog('approve')"
              >
                {{ $t("care.actions.approve") }}
              </button>
              <button
                v-if="selectedSuggestion.canReject"
                class="rounded-full border border-[#E4E7EC] bg-white px-4 py-2 text-sm text-[#344054] transition-all hover:-translate-y-0.5 hover:border-[#F04438]/20 hover:text-[#F04438] disabled:opacity-50"
                :disabled="processingId === selectedSuggestion.id"
                @click="openRejectDialog"
              >
                {{ $t("care.actions.reject") }}
              </button>
              <button
                v-if="selectedSuggestion.canIgnore"
                class="rounded-full border border-[#E4E7EC] bg-[#F8FAFC] px-4 py-2 text-sm text-[#667085] transition-all hover:-translate-y-0.5 hover:bg-[#EEF2F6] disabled:opacity-50"
                :disabled="processingId === selectedSuggestion.id"
                @click="handleIgnore"
              >
                {{ $t("care.actions.ignore") }}
              </button>
              <button
                v-if="selectedSuggestion.canExecute"
                class="rounded-full border border-[#B7E7DA] bg-[#E8F8EC] px-4 py-2 text-sm font-medium text-[#138A6B] transition-all hover:-translate-y-0.5 disabled:opacity-50"
                :disabled="processingId === selectedSuggestion.id"
                @click="openConfirmDialog('execute')"
              >
                {{ $t("care.actions.execute") }}
              </button>
            </div>
          </template>

          <div v-else class="flex min-h-[400px] items-center justify-center text-sm text-[#98A2B3]">
            {{ $t("care.empty") }}
          </div>
        </div>
      </section>
    </div>

    <ConfirmActionDialog
      :open="confirmDialogOpen"
      :suggestion="selectedSuggestion"
      :confirm-detail="confirmDetail"
      :action="pendingConfirmAction"
      :processing="processingId === selectedSuggestion?.id"
      @close="closeConfirmDialog"
      @confirm="confirmAction"
    />

    <div v-if="rejectDialogOpen && selectedSuggestion" class="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4">
      <div class="w-full max-w-lg rounded-[28px] bg-white p-6 shadow-[0_24px_80px_rgba(16,24,40,0.2)]">
        <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#F04438]/70">{{ $t("care.dialog.rejectEyebrow") }}</div>
        <h3 class="mt-2 text-2xl font-semibold text-[#101828]">{{ $t("care.dialog.rejectTitle") }}</h3>
        <p class="mt-2 text-sm leading-7 text-[#667085]">{{ selectedSuggestion.title }}</p>
        <textarea
          v-model="rejectReason"
          :placeholder="$t('care.dialog.rejectPlaceholder')"
          class="mt-4 min-h-[120px] w-full rounded-3xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#F04438]"
        />
        <div class="mt-6 flex justify-end gap-2">
          <button class="rounded-full border border-[#E4E7EC] bg-white px-4 py-2 text-sm text-[#344054]" @click="closeRejectDialog">
            {{ $t("care.actions.cancel") }}
          </button>
          <button
            class="rounded-full bg-[#F04438] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            :disabled="processingId === selectedSuggestion.id"
            @click="confirmReject"
          >
            {{ $t("care.actions.confirmReject") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
