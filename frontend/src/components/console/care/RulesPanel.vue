<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { CareRuleRecord } from "@/lib/care";

const props = defineProps<{
  rules: CareRuleRecord[];
  loading: boolean;
}>();

const emit = defineEmits<{
  create: [];
  edit: [rule: CareRuleRecord];
  toggle: [id: number, active: boolean];
  delete: [id: number];
}>();

const { t } = useI18n();

const systemRules = computed(() => props.rules.filter((r) => r.isSystemDefault));
const customRules = computed(() => props.rules.filter((r) => !r.isSystemDefault));
</script>

<template>
  <div class="rounded-[20px] border border-[#E4E7EC] bg-white overflow-hidden h-full flex flex-col">
    <!-- Header -->
    <div class="px-4 py-4 border-b border-[#E4E7EC] shrink-0">
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-[#1F2A22]">{{ $t("care.rules.title") }}</div>
        <button
          class="rounded-full bg-[#07C160] px-3 py-1.5 text-xs font-medium text-white transition-all hover:bg-[#06AD56]"
          @click="emit('create')"
        >
          + {{ $t("care.rules.actions.create") }}
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-3">
      <div v-if="loading" class="py-10 text-center text-sm text-[#98A2B3]">
        {{ $t("common.loading") }}
      </div>
      <template v-else>
        <!-- System Rules -->
        <div class="mb-4">
          <div class="text-[10px] text-[#98A2B3] uppercase mb-2">{{ $t("care.rules.systemTitle") }}</div>
          <div v-if="systemRules.length === 0" class="text-xs text-[#98A2B3]">
            {{ $t("care.rules.empty") }}
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="rule in systemRules"
              :key="rule.id"
              class="rounded-xl bg-[#F9FAFB] p-3"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-semibold text-[#1F2A22] truncate">{{ rule.name }}</div>
                  <div class="text-[10px] text-[#667085] mt-0.5 line-clamp-2">{{ rule.description || rule.suggestionTemplate }}</div>
                </div>
                <button
                  class="rounded-full px-2 py-1 text-[10px] shrink-0"
                  :class="rule.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'"
                  @click="emit('toggle', rule.id, !rule.isActive)"
                >
                  {{ rule.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Custom Rules -->
        <div>
          <div class="text-[10px] text-[#98A2B3] uppercase mb-2">{{ $t("care.rules.customTitle") }}</div>
          <div v-if="customRules.length === 0" class="text-xs text-[#98A2B3]">
            {{ $t("care.rules.empty") }}
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="rule in customRules"
              :key="rule.id"
              class="rounded-xl border border-[#E4E7EC] bg-white p-3"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-semibold text-[#1F2A22] truncate">{{ rule.name }}</div>
                  <div class="text-[10px] text-[#667085] mt-0.5 line-clamp-2">{{ rule.description || rule.suggestionTemplate }}</div>
                  <div class="text-[10px] text-[#98A2B3] mt-1">{{ rule.deviceCategory || "-" }} · {{ rule.checkFrequency }}</div>
                </div>
                <div class="flex gap-1 shrink-0">
                  <button
                    class="rounded-full bg-white px-2 py-1 text-[10px] text-[#344054] border border-[#E4E7EC]"
                    @click="emit('edit', rule)"
                  >
                    {{ $t("care.rules.actions.edit") }}
                  </button>
                  <button
                    class="rounded-full px-2 py-1 text-[10px]"
                    :class="rule.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'"
                    @click="emit('toggle', rule.id, !rule.isActive)"
                  >
                    {{ rule.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                  </button>
                  <button
                    class="rounded-full bg-[#FFF1F3] px-2 py-1 text-[10px] text-[#D92D20]"
                    @click="emit('delete', rule.id)"
                  >
                    {{ $t("care.rules.actions.delete") }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>