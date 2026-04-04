<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";

import CareSuggestionCard from "./CareSuggestionCard.vue";
import type { CareSuggestionRecord } from "@/lib/care";

const props = defineProps<{
  suggestions: CareSuggestionRecord[];
  loading: boolean;
  selectedId: number | null;
}>();

const emit = defineEmits<{
  select: [id: number];
  runInspection: [];
  filterChange: [filters: { status?: string; priority?: string }];
}>();

const { t } = useI18n();

const STORAGE_KEY = "wanny-care-center-filters";
const activeFilter = ref<"all" | "pending" | "approved" | "executed" | "failed">("pending");
const activePriority = ref<"all" | "high" | "medium" | "low">("all");

const pendingCount = computed(() =>
  props.suggestions.filter((s) => s.status === "pending").length
);

const filters = computed(() => [
  { id: "all", label: t("care.filters.all") },
  { id: "pending", label: t("care.filters.pending") },
  { id: "approved", label: t("care.filters.approved") },
  { id: "executed", label: t("care.filters.executed") },
  { id: "failed", label: t("care.filters.failed") },
]);

const priorityFilters = computed(() => [
  { id: "all", label: t("care.filters.all") },
  { id: "high", label: t("care.priority.high") },
  { id: "medium", label: t("care.priority.medium") },
  { id: "low", label: t("care.priority.low") },
]);

function loadSavedFilters() {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed.status) activeFilter.value = parsed.status;
    if (parsed.priority) activePriority.value = parsed.priority;
  } catch {
    // Ignore
  }
}

function persistFilters() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ status: activeFilter.value, priority: activePriority.value })
  );
}

function selectStatusFilter(id: typeof activeFilter.value) {
  activeFilter.value = id;
  persistFilters();
  emit("filterChange", {
    status: id === "all" ? undefined : id,
    priority: activePriority.value === "all" ? undefined : activePriority.value,
  });
}

function selectPriorityFilter(id: typeof activePriority.value) {
  activePriority.value = id;
  persistFilters();
  emit("filterChange", {
    status: activeFilter.value === "all" ? undefined : activeFilter.value,
    priority: id === "all" ? undefined : id,
  });
}

onMounted(() => {
  loadSavedFilters();
});
</script>

<template>
  <div class="rounded-[20px] border border-[#E4E7EC] bg-white overflow-hidden h-full flex flex-col">
    <!-- Header -->
    <div class="px-4 py-4 border-b border-[#E4E7EC] shrink-0">
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-[#1F2A22]">{{ $t("care.suggestions.title") }}</div>
        <div class="flex items-center gap-2">
          <div class="rounded-full bg-[#F2F4F7] px-3 py-1 text-xs text-[#344054]">
            {{ $t("care.suggestions.pendingCount", { count: pendingCount }) }}
          </div>
          <button
            class="rounded-full bg-[#07C160] px-3 py-1.5 text-xs font-medium text-white transition-all hover:bg-[#06AD56] disabled:opacity-50"
            :disabled="loading"
            @click="emit('runInspection')"
          >
            {{ $t("care.actions.scanNow") }}
          </button>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="px-4 py-3 border-b border-[#E4E7EC] shrink-0">
      <div class="flex flex-wrap gap-2 mb-2">
        <button
          v-for="filter in filters"
          :key="filter.id"
          class="rounded-full px-3 py-1 text-xs transition-all"
          :class="activeFilter === filter.id ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085] hover:bg-[#EDF7F0]'"
          @click="selectStatusFilter(filter.id as typeof activeFilter)"
        >
          {{ filter.label }}
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="filter in priorityFilters"
          :key="filter.id"
          class="rounded-full px-3 py-1 text-xs transition-all"
          :class="activePriority === filter.id ? 'bg-[#1F2A22] text-white' : 'bg-[#F2F4F7] text-[#667085] hover:bg-[#EDF7F0]'"
          @click="selectPriorityFilter(filter.id as typeof activePriority)"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>

    <!-- List -->
    <div class="flex-1 overflow-y-auto p-3">
      <div v-if="loading" class="py-10 text-center text-sm text-[#98A2B3]">
        {{ $t("common.loading") }}
      </div>
      <div v-else-if="suggestions.length === 0" class="rounded-2xl border border-dashed border-[#D0D5DD] px-4 py-10 text-center text-sm text-[#98A2B3]">
        {{ $t("care.empty") }}
      </div>
      <div v-else class="space-y-2">
        <CareSuggestionCard
          v-for="item in suggestions"
          :key="item.id"
          :item="item"
          :selected="selectedId === item.id"
          @select="emit('select', $event)"
        />
      </div>
    </div>
  </div>
</template>