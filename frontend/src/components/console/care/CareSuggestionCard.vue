<script setup lang="ts">
import { useI18n } from "vue-i18n";

import type { CareSuggestionRecord } from "@/lib/care";
import { formatDateTime } from "@/lib/utils";

const props = defineProps<{
  item: CareSuggestionRecord;
  selected: boolean;
}>();

defineEmits<{
  select: [id: number];
}>();

const { t } = useI18n();

function priorityClass(priority: number) {
  if (priority >= 7) return "bg-[#FFE8E8] text-[#D92D20]";
  if (priority >= 4) return "bg-[#FFF7E6] text-[#E8A223]";
  return "bg-[#E8F8EC] text-[#07C160]";
}
</script>

<template>
  <button
    class="w-full rounded-3xl border p-4 text-left transition-all duration-200"
    :class="selected ? 'border-[#07C160]/30 bg-[#F3FBF5] shadow-sm' : 'border-[#EDEDED] bg-white hover:border-[#07C160]/20 hover:bg-[#FAFFFB]'"
    @click="$emit('select', item.id)"
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <div class="text-sm font-semibold text-[#223126]">{{ item.title }}</div>
        <div class="mt-1 text-xs leading-5 text-[#667085]">{{ item.body }}</div>
        <div class="mt-2 flex flex-wrap gap-2">
          <span class="inline-flex rounded-full bg-[#F2F4F7] px-2.5 py-1 text-[11px] font-medium text-[#344054]">
            {{ item.suggestionType === "inspection" ? t("care.filters.inspection") : t("care.filters.care") }}
          </span>
          <div v-if="item.aggregatedCount > 1" class="inline-flex rounded-full bg-[#EEF7F1] px-2.5 py-1 text-[11px] font-medium text-[#138A6B]">
            {{ t("care.labels.aggregated", { count: item.aggregatedCount }) }}
          </div>
        </div>
      </div>
      <span class="rounded-full px-2.5 py-1 text-[11px] font-semibold" :class="priorityClass(item.priority)">
        P{{ item.priority.toFixed(1) }}
      </span>
    </div>
    <div class="mt-3 flex items-center justify-between text-[11px] text-[#98A2B3]">
      <span>{{ item.device?.name || t("care.labels.noDevice") }}</span>
      <span>{{ formatDateTime(item.createdAt) }}</span>
    </div>
  </button>
</template>
