<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";

import type { CareRuleRecord } from "@/lib/care";

const props = defineProps<{
  open: boolean;
  saving: boolean;
  rule?: CareRuleRecord | null;
}>();

const emit = defineEmits<{
  close: [];
  save: [payload: Partial<CareRuleRecord>];
}>();

const { t } = useI18n();

type FieldMode = "control" | "device" | "offline_hours";

const form = ref({
  name: "",
  description: "",
  deviceCategory: "",
  fieldMode: "control" as FieldMode,
  fieldPreset: "filter_life_percent",
  devicePath: "status",
  operator: "<",
  threshold: "20",
  suggestionTemplate: "{device_name} 需要关注",
  priority: "5",
  cooldownHours: "24",
});

const controlFieldOptions = computed(() => [
  { value: "filter_life_percent", label: t("care.rules.presets.filterLife") },
  { value: "water_level", label: t("care.rules.presets.waterLevel") },
  { value: "target_temperature", label: t("care.rules.presets.targetTemperature") },
  { value: "current_temperature", label: t("care.rules.presets.currentTemperature") },
  { value: "battery_level", label: t("care.rules.presets.batteryLevel") },
]);

const deviceFieldOptions = computed(() => [
  { value: "status", label: t("care.rules.presets.deviceStatus") },
  { value: "telemetry", label: t("care.rules.presets.telemetry") },
]);

const operatorOptions = computed(() => [
  { value: "<", label: t("care.rules.operators.lt") },
  { value: "<=", label: t("care.rules.operators.lte") },
  { value: ">", label: t("care.rules.operators.gt") },
  { value: ">=", label: t("care.rules.operators.gte") },
  { value: "==", label: t("care.rules.operators.eq") },
  { value: "!=", label: t("care.rules.operators.neq") },
  { value: "contains", label: t("care.rules.operators.contains") },
]);

const conditionFieldPreview = computed(() => {
  if (form.value.fieldMode === "offline_hours") return "device_offline_hours";
  if (form.value.fieldMode === "device") return `device.${form.value.devicePath}`;
  return `control.${form.value.fieldPreset}`;
});

function resetForm() {
  form.value = {
    name: "",
    description: "",
    deviceCategory: "",
    fieldMode: "control",
    fieldPreset: "filter_life_percent",
    devicePath: "status",
    operator: "<",
    threshold: "20",
    suggestionTemplate: "{device_name} 需要关注",
    priority: "5",
    cooldownHours: "24",
  };
}

function applyRuleToForm(rule: CareRuleRecord) {
  const conditionSpec = rule.conditionSpec || {};
  const field = String(conditionSpec.field || "control.filter_life_percent");

  form.value = {
    name: rule.name,
    description: rule.description,
    deviceCategory: rule.deviceCategory,
    fieldMode: field === "device_offline_hours" ? "offline_hours" : field.startsWith("device.") ? "device" : "control",
    fieldPreset: field.startsWith("control.") ? field.replace(/^control\./, "") : "filter_life_percent",
    devicePath: field.startsWith("device.") ? field.replace(/^device\./, "") : "status",
    operator: String(conditionSpec.operator || "<"),
    threshold: conditionSpec.threshold == null ? "" : String(conditionSpec.threshold),
    suggestionTemplate: rule.suggestionTemplate,
    priority: String(rule.priority),
    cooldownHours: String(rule.cooldownHours),
  };
}

function handleSubmit() {
  const thresholdValue =
    form.value.operator === "contains"
      ? form.value.threshold
      : Number.isNaN(Number(form.value.threshold))
        ? form.value.threshold
        : Number(form.value.threshold);

  emit("save", {
    ruleType: "custom",
    deviceCategory: form.value.deviceCategory,
    name: form.value.name,
    description: form.value.description,
    checkFrequency: "hourly",
    conditionSpec: {
      field: conditionFieldPreview.value,
      operator: form.value.operator,
      threshold: thresholdValue,
    },
    suggestionTemplate: form.value.suggestionTemplate,
    priority: Number(form.value.priority),
    cooldownHours: Number(form.value.cooldownHours),
    isActive: true,
  });
}

watch(
  () => props.rule,
  (rule) => {
    if (rule) {
      applyRuleToForm(rule);
    } else {
      resetForm();
    }
  },
  { immediate: true }
);

watch(
  () => props.open,
  (open) => {
    if (!open) resetForm();
  }
);
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4">
    <div class="w-full max-w-lg rounded-[20px] bg-white shadow-[0_24px_80px_rgba(16,24,40,0.2)] max-h-[90vh] flex flex-col">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-[#E4E7EC] shrink-0">
        <div class="flex items-center justify-between">
          <div class="text-sm font-semibold text-[#1F2A22]">
            {{ rule ? $t("care.rules.editTitle") : $t("care.rules.createTitle") }}
          </div>
          <button
            class="flex h-7 w-7 items-center justify-center rounded-full bg-[#F2F4F7] text-[#667085] hover:bg-[#E4E7EC]"
            @click="emit('close')"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="p-5 overflow-y-auto flex-1">
        <div class="space-y-3">
          <input
            v-model="form.name"
            :placeholder="$t('care.rules.form.name')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
          <input
            v-model="form.deviceCategory"
            :placeholder="$t('care.rules.form.deviceCategory')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
          <textarea
            v-model="form.description"
            :placeholder="$t('care.rules.form.description')"
            class="min-h-[80px] w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />

          <!-- Condition Builder -->
          <div class="rounded-xl border border-[#E4E7EC] bg-[#F9FAFB] p-3">
            <div class="text-[10px] text-[#98A2B3] uppercase mb-2">{{ $t("care.rules.builder.title") }}</div>
            <div class="space-y-2">
              <!-- Field Mode -->
              <div class="flex gap-2">
                <button
                  class="flex-1 rounded-full px-3 py-1.5 text-xs transition-all"
                  :class="form.fieldMode === 'control' ? 'bg-[#07C160] text-white' : 'bg-white border border-[#E4E7EC] text-[#667085]'"
                  @click="form.fieldMode = 'control'"
                >
                  {{ $t("care.rules.builder.control") }}
                </button>
                <button
                  class="flex-1 rounded-full px-3 py-1.5 text-xs transition-all"
                  :class="form.fieldMode === 'device' ? 'bg-[#07C160] text-white' : 'bg-white border border-[#E4E7EC] text-[#667085]'"
                  @click="form.fieldMode = 'device'"
                >
                  {{ $t("care.rules.builder.device") }}
                </button>
                <button
                  class="flex-1 rounded-full px-3 py-1.5 text-xs transition-all"
                  :class="form.fieldMode === 'offline_hours' ? 'bg-[#07C160] text-white' : 'bg-white border border-[#E4E7EC] text-[#667085]'"
                  @click="form.fieldMode = 'offline_hours'"
                >
                  {{ $t("care.rules.builder.offlineHours") }}
                </button>
              </div>

              <!-- Field Select -->
              <select
                v-if="form.fieldMode === 'control'"
                v-model="form.fieldPreset"
                class="w-full rounded-xl border border-[#E4E7EC] bg-white px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              >
                <option v-for="opt in controlFieldOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
              <select
                v-else-if="form.fieldMode === 'device'"
                v-model="form.devicePath"
                class="w-full rounded-xl border border-[#E4E7EC] bg-white px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              >
                <option v-for="opt in deviceFieldOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <!-- Operator & Threshold -->
              <div class="grid grid-cols-3 gap-2">
                <select
                  v-model="form.operator"
                  class="rounded-xl border border-[#E4E7EC] bg-white px-3 py-2 text-sm outline-none focus:border-[#07C160]"
                >
                  <option v-for="opt in operatorOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
                <input
                  v-model="form.threshold"
                  :placeholder="$t('care.rules.form.threshold')"
                  class="rounded-xl border border-[#E4E7EC] px-3 py-2 text-sm outline-none focus:border-[#07C160]"
                />
                <input
                  v-model="form.priority"
                  :placeholder="$t('care.rules.form.priority')"
                  class="rounded-xl border border-[#E4E7EC] px-3 py-2 text-sm outline-none focus:border-[#07C160]"
                />
              </div>

              <!-- Preview -->
              <div class="rounded-lg bg-white px-3 py-2 text-xs text-[#667085]">
                {{ $t("care.rules.builder.preview") }}: <span class="font-medium text-[#1F2A22]">{{ conditionFieldPreview }}</span>
              </div>
            </div>
          </div>

          <input
            v-model="form.cooldownHours"
            :placeholder="$t('care.rules.form.cooldownHours')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
          <input
            v-model="form.suggestionTemplate"
            :placeholder="$t('care.rules.form.template')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-[#E4E7EC] shrink-0 flex justify-end gap-2">
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
          {{ rule ? $t("care.rules.actions.save") : $t("care.rules.actions.create") }}
        </button>
      </div>
    </div>
  </div>
</template>