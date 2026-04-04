<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import WeatherPanel from "@/components/console/care/WeatherPanel.vue";
import SuggestionsPanel from "@/components/console/care/SuggestionsPanel.vue";
import RulesPanel from "@/components/console/care/RulesPanel.vue";
import DataSourceDialog from "@/components/console/care/DataSourceDialog.vue";
import RuleEditorDialog from "@/components/console/care/RuleEditorDialog.vue";
import ConfirmActionDialog from "@/components/console/care/ConfirmActionDialog.vue";
import {
  type CareConfirmDetail,
  type CareDataSourceRecord,
  type CareRuleRecord,
  type CareSuggestionRecord,
  type WeatherSnapshot,
  createCareDataSource,
  createCareRule,
  deleteCareDataSource,
  deleteCareRule,
  executeCareSuggestion,
  fetchCareConfirmDetail,
  fetchCareDataSources,
  fetchCareRules,
  fetchCareSuggestions,
  fetchCurrentWeather,
  refreshCurrentWeather,
  runCareInspection,
  sendCareSuggestionFeedback,
  updateCareDataSource,
  updateCareRule,
} from "@/lib/care";

const { t } = useI18n();

// State
const loading = ref(false);
const weatherLoading = ref(false);
const saving = ref(false);
const processingId = ref<number | null>(null);
const errorMessage = ref("");
const actionMessage = ref("");

// Data
const suggestions = ref<CareSuggestionRecord[]>([]);
const rules = ref<CareRuleRecord[]>([]);
const dataSources = ref<CareDataSourceRecord[]>([]);
const weather = ref<WeatherSnapshot | null>(null);
const weatherSourceId = ref<number | null>(null);
const selectedSuggestionId = ref<number | null>(null);
const confirmDetail = ref<CareConfirmDetail | null>(null);

// Dialog state
const dataSourceDialogOpen = ref(false);
const ruleEditorDialogOpen = ref(false);
const editingRule = ref<CareRuleRecord | null>(null);
const confirmDialogOpen = ref(false);
const pendingConfirmAction = ref<"approve" | "execute">("approve");
const rejectDialogOpen = ref(false);
const rejectReason = ref("");
let weatherRefreshTimer: number | null = null;

// Computed
const selectedSuggestion = computed(
  () => suggestions.value.find((item) => item.id === selectedSuggestionId.value) ?? null
);

// Filters
const activeFilters = ref<{ status?: string; priority?: string }>({ status: "pending" });

// Methods
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
    const response = await fetchCareSuggestions(activeFilters.value);
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

async function loadRules() {
  try {
    const response = await fetchCareRules();
    rules.value = response.rules;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.loadRules");
  }
}

async function loadDataSources() {
  try {
    const response = await fetchCareDataSources();
    dataSources.value = response.dataSources;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.loadWeather");
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
    actionMessage.value = response.suggestionId ? t("care.feedback.weatherTriggered") : t("care.feedback.weatherRefreshed");
    await loadSuggestions();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    weatherLoading.value = false;
  }
}

function clearWeatherRefreshTimer() {
  if (weatherRefreshTimer !== null) {
    window.clearTimeout(weatherRefreshTimer);
    weatherRefreshTimer = null;
  }
}

function scheduleNextHourlyWeatherRefresh() {
  clearWeatherRefreshTimer();
  const now = new Date();
  const nextHour = new Date(now);
  nextHour.setMinutes(0, 0, 0);
  nextHour.setHours(nextHour.getHours() + 1);
  const delay = Math.max(nextHour.getTime() - now.getTime(), 1000);
  weatherRefreshTimer = window.setTimeout(async () => {
    if (weatherSourceId.value && !weatherLoading.value) {
      await handleRefreshWeather();
    }
    scheduleNextHourlyWeatherRefresh();
  }, delay);
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

async function handleFilterChange(filters: { status?: string; priority?: string }) {
  activeFilters.value = filters;
  await loadSuggestions();
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

// Data source handlers
async function handleSaveDataSource(payload: Partial<CareDataSourceRecord>) {
  saving.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    if (payload.id) {
      await updateCareDataSource(payload.id, payload);
      actionMessage.value = t("care.feedback.weatherSourceUpdated");
    } else {
      await createCareDataSource(payload);
      actionMessage.value = t("care.feedback.weatherSourceCreated");
    }
    await loadDataSources();
    await handleRefreshWeather();
    dataSourceDialogOpen.value = false;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    saving.value = false;
  }
}

async function handleToggleDataSource(id: number, active: boolean) {
  try {
    await updateCareDataSource(id, { isActive: active });
    await loadDataSources();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

async function handleDeleteDataSource(id: number) {
  try {
    await deleteCareDataSource(id);
    actionMessage.value = t("care.feedback.weatherSourceDeleted");
    await loadDataSources();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

// Rule handlers
function openCreateRuleDialog() {
  editingRule.value = null;
  ruleEditorDialogOpen.value = true;
}

function openEditRuleDialog(rule: CareRuleRecord) {
  editingRule.value = rule;
  ruleEditorDialogOpen.value = true;
}

async function handleSaveRule(payload: Partial<CareRuleRecord>) {
  saving.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    if (editingRule.value) {
      await updateCareRule(editingRule.value.id, payload);
      actionMessage.value = t("care.feedback.ruleUpdated");
    } else {
      await createCareRule(payload);
      actionMessage.value = t("care.feedback.ruleCreated");
    }
    await loadRules();
    ruleEditorDialogOpen.value = false;
    editingRule.value = null;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    saving.value = false;
  }
}

async function handleToggleRule(id: number, active: boolean) {
  try {
    await updateCareRule(id, { isActive: active });
    await loadRules();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

async function handleDeleteRule(id: number) {
  try {
    await deleteCareRule(id);
    actionMessage.value = t("care.feedback.ruleDeleted");
    await loadRules();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

// Confirm dialog
function openConfirmDialog(action: "approve" | "execute") {
  pendingConfirmAction.value = action;
  confirmDialogOpen.value = true;
}

async function confirmAction() {
  if (pendingConfirmAction.value === "approve") {
    await submitFeedback("approve");
  } else {
    await handleExecute();
  }
  confirmDialogOpen.value = false;
}

// Reject dialog
function openRejectDialog() {
  rejectReason.value = "";
  rejectDialogOpen.value = true;
}

async function confirmReject() {
  await submitFeedback("reject", rejectReason.value.trim());
  rejectDialogOpen.value = false;
}

// Lifecycle
onMounted(async () => {
  await Promise.all([loadSuggestions(), loadWeather(), loadRules(), loadDataSources()]);
  if (selectedSuggestionId.value) {
    await selectSuggestion(selectedSuggestionId.value);
  }
  scheduleNextHourlyWeatherRefresh();
});

onBeforeUnmount(() => {
  clearWeatherRefreshTimer();
});

watch(selectedSuggestion, async (next, previous) => {
  if (!next) {
    confirmDetail.value = null;
    return;
  }
  if (!confirmDetail.value || previous?.id !== next.id) {
    await selectSuggestion(next.id);
  }
});

watch(weatherSourceId, () => {
  scheduleNextHourlyWeatherRefresh();
});
</script>

<template>
  <div class="space-y-4">
    <!-- Error/Success Messages -->
    <div v-if="errorMessage" class="rounded-2xl bg-[#FFE8E8] px-4 py-3 text-sm text-[#E84343]">
      {{ errorMessage }}
    </div>
    <div v-if="actionMessage" class="rounded-2xl bg-[#E8F8EC] px-4 py-3 text-sm text-[#07C160]">
      {{ actionMessage }}
    </div>

    <!-- Three Column Layout -->
    <div class="grid gap-4 lg:grid-cols-3">
      <!-- Left: Weather Panel -->
      <WeatherPanel
        :weather="weather"
        :weather-source-id="weatherSourceId"
        :weather-loading="weatherLoading"
        @refresh-weather="handleRefreshWeather"
        @open-data-source-dialog="dataSourceDialogOpen = true"
      />

      <!-- Center: Suggestions Panel -->
      <SuggestionsPanel
        :suggestions="suggestions"
        :loading="loading"
        :selected-id="selectedSuggestionId"
        @select="selectSuggestion"
        @run-inspection="handleRunInspection"
        @filter-change="handleFilterChange"
      />

      <!-- Right: Rules Panel -->
      <RulesPanel
        :rules="rules"
        :loading="loading"
        @create="openCreateRuleDialog"
        @edit="openEditRuleDialog"
        @toggle="handleToggleRule"
        @delete="handleDeleteRule"
      />
    </div>

    <!-- Suggestion Detail Panel (below on larger screens) -->
    <div v-if="selectedSuggestion" class="rounded-[20px] border border-[#E4E7EC] bg-white p-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-[#1F2A22]">{{ selectedSuggestion.title }}</h2>
          <p class="mt-2 text-sm leading-6 text-[#667085]">{{ selectedSuggestion.body }}</p>
        </div>
        <span
          class="rounded-full px-3 py-1 text-xs font-semibold shrink-0"
          :class="{
            'bg-[#FFE8E8] text-[#D92D20]': selectedSuggestion.priority >= 7,
            'bg-[#FFF7E6] text-[#E8A223]': selectedSuggestion.priority >= 4 && selectedSuggestion.priority < 7,
            'bg-[#E8F8EC] text-[#07C160]': selectedSuggestion.priority < 4,
          }"
        >
          {{ selectedSuggestion.status }}
        </span>
      </div>

      <div class="mt-4 grid gap-3 md:grid-cols-2">
        <div class="rounded-xl border border-[#E9EEF1] bg-[#FBFDFC] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.labels.device") }}</div>
          <div class="mt-1 text-sm font-medium text-[#223126]">{{ selectedSuggestion.device?.name || $t("care.labels.noDevice") }}</div>
          <div class="text-xs text-[#667085]">{{ selectedSuggestion.device?.category || "-" }}</div>
        </div>
        <div class="rounded-xl border border-[#E9EEF1] bg-[#FBFDFC] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.labels.control") }}</div>
          <div class="mt-1 text-sm font-medium text-[#223126]">{{ selectedSuggestion.control?.label || "-" }}</div>
          <div class="text-xs text-[#667085]">{{ selectedSuggestion.control?.key || "-" }}</div>
        </div>
      </div>

      <!-- Actions -->
      <div class="mt-4 flex flex-wrap gap-2">
        <button
          v-if="selectedSuggestion.canApprove"
          class="rounded-full bg-[#07C160] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[#06AD56] disabled:opacity-50"
          :disabled="processingId === selectedSuggestion.id"
          @click="openConfirmDialog('approve')"
        >
          {{ $t("care.actions.approve") }}
        </button>
        <button
          v-if="selectedSuggestion.canReject"
          class="rounded-full border border-[#E4E7EC] bg-white px-4 py-2 text-sm text-[#344054] transition-all hover:border-[#F04438]/20 hover:text-[#F04438] disabled:opacity-50"
          :disabled="processingId === selectedSuggestion.id"
          @click="openRejectDialog"
        >
          {{ $t("care.actions.reject") }}
        </button>
        <button
          v-if="selectedSuggestion.canIgnore"
          class="rounded-full border border-[#E4E7EC] bg-[#F8FAFC] px-4 py-2 text-sm text-[#667085] transition-all hover:bg-[#EEF2F6] disabled:opacity-50"
          :disabled="processingId === selectedSuggestion.id"
          @click="submitFeedback('ignore')"
        >
          {{ $t("care.actions.ignore") }}
        </button>
        <button
          v-if="selectedSuggestion.canExecute"
          class="rounded-full border border-[#B7E7DA] bg-[#E8F8EC] px-4 py-2 text-sm font-medium text-[#138A6B] transition-all hover:bg-[#D1FAE5] disabled:opacity-50"
          :disabled="processingId === selectedSuggestion.id"
          @click="openConfirmDialog('execute')"
        >
          {{ $t("care.actions.execute") }}
        </button>
      </div>
    </div>

    <!-- Data Source Dialog -->
    <DataSourceDialog
      :open="dataSourceDialogOpen"
      :sources="dataSources"
      :saving="saving"
      @close="dataSourceDialogOpen = false"
      @save="handleSaveDataSource"
      @toggle="handleToggleDataSource"
      @delete="handleDeleteDataSource"
    />

    <!-- Rule Editor Dialog -->
    <RuleEditorDialog
      :open="ruleEditorDialogOpen"
      :saving="saving"
      :rule="editingRule"
      @close="ruleEditorDialogOpen = false; editingRule = null"
      @save="handleSaveRule"
    />

    <!-- Confirm Action Dialog -->
    <ConfirmActionDialog
      :open="confirmDialogOpen"
      :suggestion="selectedSuggestion"
      :confirm-detail="confirmDetail"
      :action="pendingConfirmAction"
      :processing="processingId === selectedSuggestion?.id"
      @close="confirmDialogOpen = false"
      @confirm="confirmAction"
    />

    <!-- Reject Dialog -->
    <div v-if="rejectDialogOpen && selectedSuggestion" class="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4">
      <div class="w-full max-w-lg rounded-[20px] bg-white p-6 shadow-[0_24px_80px_rgba(16,24,40,0.2)]">
        <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#F04438]/70">{{ $t("care.dialog.rejectEyebrow") }}</div>
        <h3 class="mt-2 text-xl font-semibold text-[#101828]">{{ $t("care.dialog.rejectTitle") }}</h3>
        <p class="mt-2 text-sm leading-7 text-[#667085]">{{ selectedSuggestion.title }}</p>
        <textarea
          v-model="rejectReason"
          :placeholder="$t('care.dialog.rejectPlaceholder')"
          class="mt-4 min-h-[100px] w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#F04438]"
        />
        <div class="mt-6 flex justify-end gap-2">
          <button class="rounded-full border border-[#E4E7EC] bg-white px-4 py-2 text-sm text-[#344054]" @click="rejectDialogOpen = false">
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
