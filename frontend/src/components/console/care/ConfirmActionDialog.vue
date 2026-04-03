<script setup lang="ts">
import { useI18n } from "vue-i18n";

import type { CareConfirmDetail, CareSuggestionRecord } from "@/lib/care";

const props = defineProps<{
  open: boolean;
  suggestion: CareSuggestionRecord | null;
  confirmDetail: CareConfirmDetail | null;
  action: "approve" | "execute";
  processing: boolean;
}>();

defineEmits<{
  close: [];
  confirm: [];
}>();

const { t } = useI18n();
</script>

<template>
  <div v-if="open && suggestion" class="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4">
    <div class="w-full max-w-xl rounded-[28px] bg-white p-6 shadow-[0_24px_80px_rgba(16,24,40,0.2)]">
      <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#07C160]/70">{{ t("care.dialog.confirmEyebrow") }}</div>
      <h3 class="mt-2 text-2xl font-semibold text-[#101828]">{{ suggestion.title }}</h3>
      <p class="mt-2 text-sm leading-7 text-[#667085]">{{ suggestion.body }}</p>
      <div v-if="confirmDetail" class="mt-5 grid gap-3 rounded-3xl border border-[#DDEEE2] bg-[#F7FCF8] p-4 md:grid-cols-2">
        <div>
          <div class="text-xs text-[#98A2B3]">{{ t("care.labels.targetDevice") }}</div>
          <div class="mt-1 text-sm text-[#223126]">{{ confirmDetail.deviceName || confirmDetail.deviceId || "-" }}</div>
        </div>
        <div>
          <div class="text-xs text-[#98A2B3]">{{ t("care.labels.targetControl") }}</div>
          <div class="mt-1 text-sm text-[#223126]">{{ confirmDetail.controlLabel || confirmDetail.controlId || "-" }}</div>
        </div>
        <div>
          <div class="text-xs text-[#98A2B3]">{{ t("care.labels.action") }}</div>
          <div class="mt-1 text-sm text-[#223126]">{{ confirmDetail.action || "-" }}</div>
        </div>
        <div>
          <div class="text-xs text-[#98A2B3]">{{ t("care.labels.value") }}</div>
          <div class="mt-1 text-sm text-[#223126]">{{ JSON.stringify(confirmDetail.value ?? null) }}</div>
        </div>
      </div>
      <div class="mt-6 flex justify-end gap-2">
        <button class="rounded-full border border-[#E4E7EC] bg-white px-4 py-2 text-sm text-[#344054]" @click="$emit('close')">
          {{ t("care.actions.cancel") }}
        </button>
        <button
          class="rounded-full bg-[#07C160] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          :disabled="processing"
          @click="$emit('confirm')"
        >
          {{ action === "approve" ? t("care.actions.confirmApprove") : t("care.actions.confirmExecute") }}
        </button>
      </div>
    </div>
  </div>
</template>
