<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  createCareDataSource,
  createCareRule,
  deleteCareDataSource,
  deleteCareRule,
  fetchCareDataSources,
  fetchCareRules,
  type CareDataSourceRecord,
  type CareRuleRecord,
  updateCareDataSource,
  updateCareRule,
} from "@/lib/care";

const { t } = useI18n();

type FieldMode = "control" | "device" | "offline_hours";

type BuilderPresetMeta = {
  labelKey: string;
  descriptionKey: string;
  operator: string;
  threshold: string;
  unit: string;
  deviceCategory: string;
  template: string;
};

const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const actionMessage = ref("");
const rules = ref<CareRuleRecord[]>([]);
const dataSources = ref<CareDataSourceRecord[]>([]);
const editingRuleId = ref<number | null>(null);
const editingWeatherSourceId = ref<number | null>(null);

const form = ref({
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
});

const weatherSourceForm = ref({
  sourceType: "weather_api",
  name: "Open-Meteo",
  latitude: "",
  longitude: "",
  timezone: "Asia/Shanghai",
  fetchFrequency: "30m",
  haEntityId: "weather.home",
});

const controlPresetMeta: Record<string, BuilderPresetMeta> = {
  filter_life_percent: {
    labelKey: "care.rules.presets.filterLife",
    descriptionKey: "care.rules.builder.descriptions.filterLife",
    operator: "<",
    threshold: "20",
    unit: "%",
    deviceCategory: "water_purifier",
    template: "{device_name} 滤芯寿命偏低，建议尽快更换。",
  },
  water_level: {
    labelKey: "care.rules.presets.waterLevel",
    descriptionKey: "care.rules.builder.descriptions.waterLevel",
    operator: "<",
    threshold: "30",
    unit: "%",
    deviceCategory: "pet_waterer",
    template: "{device_name} 水位偏低，建议尽快加水。",
  },
  target_temperature: {
    labelKey: "care.rules.presets.targetTemperature",
    descriptionKey: "care.rules.builder.descriptions.targetTemperature",
    operator: "<",
    threshold: "20",
    unit: "°C",
    deviceCategory: "climate",
    template: "{device_name} 当前目标温度偏低，建议关注环境变化。",
  },
  current_temperature: {
    labelKey: "care.rules.presets.currentTemperature",
    descriptionKey: "care.rules.builder.descriptions.currentTemperature",
    operator: ">",
    threshold: "28",
    unit: "°C",
    deviceCategory: "climate",
    template: "{device_name} 当前温度偏高，建议检查制冷效果。",
  },
  battery_level: {
    labelKey: "care.rules.presets.batteryLevel",
    descriptionKey: "care.rules.builder.descriptions.batteryLevel",
    operator: "<",
    threshold: "20",
    unit: "%",
    deviceCategory: "",
    template: "{device_name} 电量偏低，建议尽快充电或更换电池。",
  },
  doorlockstatusvehicle: {
    labelKey: "care.rules.presets.vehicleLock",
    descriptionKey: "care.rules.builder.descriptions.vehicleLock",
    operator: "!=",
    threshold: "2",
    unit: "",
    deviceCategory: "vehicle",
    template: "{device_name} 当前未处于已锁车状态，建议检查。",
  },
};

const devicePresetMeta: Record<string, BuilderPresetMeta> = {
  status: {
    labelKey: "care.rules.presets.deviceStatus",
    descriptionKey: "care.rules.builder.descriptions.deviceStatus",
    operator: "!=",
    threshold: "online",
    unit: "",
    deviceCategory: "",
    template: "{device_name} 当前状态异常，建议排查连接情况。",
  },
  telemetry: {
    labelKey: "care.rules.presets.telemetry",
    descriptionKey: "care.rules.builder.descriptions.telemetry",
    operator: "contains",
    threshold: "离线",
    unit: "",
    deviceCategory: "",
    template: "{device_name} 遥测摘要命中了关注关键词，建议检查。",
  },
  room_name: {
    labelKey: "care.rules.presets.roomName",
    descriptionKey: "care.rules.builder.descriptions.roomName",
    operator: "contains",
    threshold: "客厅",
    unit: "",
    deviceCategory: "",
    template: "{device_name} 位于重点房间，建议优先检查。",
  },
};

const offlineHoursPresetMeta: BuilderPresetMeta = {
  labelKey: "care.rules.presets.offlineHours",
  descriptionKey: "care.rules.builder.descriptions.offlineHours",
  operator: ">=",
  threshold: "24",
  unit: "h",
  deviceCategory: "",
  template: "{device_name} 已离线较长时间，建议检查设备状态。",
};

const editableRules = computed(() => rules.value.filter((item) => !item.isSystemDefault));
const systemRules = computed(() => rules.value.filter((item) => item.isSystemDefault));
const weatherSources = computed(() => dataSources.value.filter((item) => ["weather_api", "ha_entity"].includes(item.sourceType)));
const conditionFieldPreview = computed(() => {
  if (form.value.fieldMode === "offline_hours") return "device_offline_hours";
  if (form.value.fieldMode === "device") return `device.${form.value.devicePath}`;
  return `control.${form.value.fieldPreset}`;
});
const operatorOptions = computed(() => [
  { value: "<", label: t("care.rules.operators.lt") },
  { value: "<=", label: t("care.rules.operators.lte") },
  { value: ">", label: t("care.rules.operators.gt") },
  { value: ">=", label: t("care.rules.operators.gte") },
  { value: "==", label: t("care.rules.operators.eq") },
  { value: "!=", label: t("care.rules.operators.neq") },
  { value: "contains", label: t("care.rules.operators.contains") },
]);
const controlFieldOptions = computed(() => [
  { value: "filter_life_percent", label: t("care.rules.presets.filterLife") },
  { value: "water_level", label: t("care.rules.presets.waterLevel") },
  { value: "target_temperature", label: t("care.rules.presets.targetTemperature") },
  { value: "current_temperature", label: t("care.rules.presets.currentTemperature") },
  { value: "battery_level", label: t("care.rules.presets.batteryLevel") },
  { value: "doorlockstatusvehicle", label: t("care.rules.presets.vehicleLock") },
]);
const deviceFieldOptions = computed(() => [
  { value: "status", label: t("care.rules.presets.deviceStatus") },
  { value: "telemetry", label: t("care.rules.presets.telemetry") },
  { value: "room_name", label: t("care.rules.presets.roomName") },
]);
const templatePresetOptions = computed(() => [
  {
    id: "attention",
    label: t("care.rules.templates.attention"),
    value: "{device_name} 当前状态需要关注，建议尽快检查。",
  },
  {
    id: "maintenance",
    label: t("care.rules.templates.maintenance"),
    value: "{device_name} 建议安排一次维护检查。",
  },
  {
    id: "safety",
    label: t("care.rules.templates.safety"),
    value: "{device_name} 可能存在安全隐患，建议立即确认。",
  },
  {
    id: "energy",
    label: t("care.rules.templates.energy"),
    value: "{device_name} 当前运行状态可能影响能耗，建议优化。",
  },
  {
    id: "comfort",
    label: t("care.rules.templates.comfort"),
    value: "{device_name} 当前状态可能影响舒适度，建议调整。",
  },
]);
const activeBuilderMeta = computed<BuilderPresetMeta>(() => {
  if (form.value.fieldMode === "offline_hours") return offlineHoursPresetMeta;
  if (form.value.fieldMode === "device") return devicePresetMeta[form.value.devicePath] ?? devicePresetMeta.status;
  return controlPresetMeta[form.value.fieldPreset] ?? controlPresetMeta.filter_life_percent;
});
const thresholdPlaceholder = computed(() =>
  activeBuilderMeta.value.unit
    ? `${t("care.rules.form.threshold")} (${activeBuilderMeta.value.unit})`
    : t("care.rules.form.threshold"),
);
const thresholdInputMode = computed(() => (form.value.operator === "contains" ? "text" : "decimal"));

function applyBuilderPreset(mode: FieldMode, value?: string) {
  form.value.fieldMode = mode;
  if (mode === "control" && value) {
    form.value.fieldPreset = value;
  } else if (mode === "device" && value) {
    form.value.devicePath = value;
  }

  const meta =
    mode === "offline_hours"
      ? offlineHoursPresetMeta
      : mode === "device"
        ? devicePresetMeta[form.value.devicePath] ?? devicePresetMeta.status
        : controlPresetMeta[form.value.fieldPreset] ?? controlPresetMeta.filter_life_percent;

  form.value.operator = meta.operator;
  form.value.threshold = meta.threshold;
  if (!editingRuleId.value || !form.value.deviceCategory.trim()) {
    form.value.deviceCategory = meta.deviceCategory;
  }
  if (!editingRuleId.value || !form.value.suggestionTemplate.trim()) {
    form.value.suggestionTemplate = meta.template;
  }
}

function applyCurrentBuilderDefaults() {
  if (form.value.fieldMode === "control") {
    applyBuilderPreset("control", form.value.fieldPreset);
    return;
  }
  if (form.value.fieldMode === "device") {
    applyBuilderPreset("device", form.value.devicePath);
    return;
  }
  applyBuilderPreset("offline_hours");
}

function applyTemplatePreset(template: string) {
  form.value.suggestionTemplate = template;
}

function resetWeatherSourceForm() {
  editingWeatherSourceId.value = null;
  weatherSourceForm.value = {
    sourceType: "weather_api",
    name: "Open-Meteo",
    latitude: "",
    longitude: "",
    timezone: "Asia/Shanghai",
    fetchFrequency: "30m",
    haEntityId: "weather.home",
  };
}

function applyWeatherSourceToForm(source: CareDataSourceRecord) {
  const config = source.config || {};
  editingWeatherSourceId.value = source.id;
  weatherSourceForm.value = {
    sourceType: source.sourceType,
    name: source.name,
    latitude: config.latitude == null ? "" : String(config.latitude),
    longitude: config.longitude == null ? "" : String(config.longitude),
    timezone: String(config.timezone || "Asia/Shanghai"),
    fetchFrequency: source.fetchFrequency,
    haEntityId: String(config.ha_entity_id || config.entity_id || "weather.home"),
  };
}

function resetRuleForm() {
  editingRuleId.value = null;
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
  applyBuilderPreset("control", "filter_life_percent");
}

function applyRuleToForm(rule: CareRuleRecord) {
  const conditionSpec = rule.conditionSpec || {};
  const field = String(conditionSpec.field || "control.filter_life_percent");
  const operator = String(conditionSpec.operator || "<");
  const threshold = conditionSpec.threshold;

  editingRuleId.value = rule.id;
  form.value = {
    name: rule.name,
    description: rule.description,
    deviceCategory: rule.deviceCategory,
    fieldMode: field === "device_offline_hours" ? "offline_hours" : field.startsWith("device.") ? "device" : "control",
    fieldPreset: field.startsWith("control.") ? field.replace(/^control\./, "") : "filter_life_percent",
    devicePath: field.startsWith("device.") ? field.replace(/^device\./, "") : "status",
    operator,
    threshold: threshold == null ? "" : String(threshold),
    suggestionTemplate: rule.suggestionTemplate,
    priority: String(rule.priority),
    cooldownHours: String(rule.cooldownHours),
  };
}

async function loadRules() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await fetchCareRules();
    rules.value = response.rules;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.loadRules");
  } finally {
    loading.value = false;
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

async function handleCreateRule() {
  saving.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const thresholdValue =
      form.value.operator === "contains"
        ? form.value.threshold
        : Number.isNaN(Number(form.value.threshold))
          ? form.value.threshold
          : Number(form.value.threshold);
    const payload = {
      ruleType: "custom" as const,
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
    };
    if (editingRuleId.value) {
      await updateCareRule(editingRuleId.value, payload);
      actionMessage.value = t("care.feedback.ruleUpdated");
    } else {
      await createCareRule(payload);
      actionMessage.value = t("care.feedback.ruleCreated");
    }
    resetRuleForm();
    await loadRules();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    saving.value = false;
  }
}

async function toggleRule(rule: CareRuleRecord) {
  try {
    await updateCareRule(rule.id, { isActive: !rule.isActive });
    await loadRules();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

async function handleDeleteRule(rule: CareRuleRecord) {
  try {
    await deleteCareRule(rule.id);
    actionMessage.value = t("care.feedback.ruleDeleted");
    await loadRules();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

async function handleCreateWeatherSource() {
  saving.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const payload = {
      sourceType: weatherSourceForm.value.sourceType as "weather_api" | "ha_entity",
      name: weatherSourceForm.value.name,
      fetchFrequency: weatherSourceForm.value.fetchFrequency,
      isActive: true,
      config:
        weatherSourceForm.value.sourceType === "ha_entity"
          ? {
              ha_entity_id: weatherSourceForm.value.haEntityId,
            }
          : {
              provider: "open_meteo",
              endpoint: "https://api.open-meteo.com/v1/forecast",
              latitude: Number(weatherSourceForm.value.latitude),
              longitude: Number(weatherSourceForm.value.longitude),
              timezone: weatherSourceForm.value.timezone,
            },
    };
    if (editingWeatherSourceId.value) {
      await updateCareDataSource(editingWeatherSourceId.value, payload);
      actionMessage.value = t("care.feedback.weatherSourceUpdated");
    } else {
      await createCareDataSource(payload);
      actionMessage.value = t("care.feedback.weatherSourceCreated");
    }
    resetWeatherSourceForm();
    await loadDataSources();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  } finally {
    saving.value = false;
  }
}

async function toggleWeatherSource(source: CareDataSourceRecord) {
  try {
    await updateCareDataSource(source.id, { isActive: !source.isActive });
    await loadDataSources();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

async function handleDeleteWeatherSource(source: CareDataSourceRecord) {
  try {
    await deleteCareDataSource(source.id);
    actionMessage.value = t("care.feedback.weatherSourceDeleted");
    await loadDataSources();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("care.errors.action");
  }
}

onMounted(async () => {
  await Promise.all([loadRules(), loadDataSources()]);
});
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-[28px] border border-[#E7EAF0] bg-white p-5 shadow-sm">
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#98A2B3]">{{ $t("care.rules.eyebrow") }}</div>
          <h1 class="mt-2 text-3xl font-semibold tracking-tight text-[#101828]">{{ $t("care.rules.title") }}</h1>
          <p class="mt-2 max-w-2xl text-sm leading-7 text-[#667085]">{{ $t("care.rules.description") }}</p>
        </div>
      </div>
    </section>

    <div v-if="errorMessage" class="rounded-2xl bg-[#FFE8E8] px-4 py-3 text-sm text-[#E84343]">{{ errorMessage }}</div>
    <div v-if="actionMessage" class="rounded-2xl bg-[#E8F8EC] px-4 py-3 text-sm text-[#07C160]">{{ actionMessage }}</div>

    <div class="grid gap-5 lg:grid-cols-12">
      <section class="lg:col-span-5 rounded-3xl border border-[#E4E7EC] bg-white p-5">
        <div class="mb-6 rounded-3xl border border-[#DDEEE2] bg-[linear-gradient(180deg,#FCFFFD_0%,#F4FBF6_100%)] p-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.18em] text-[#07C160]/70">{{ $t("care.weather.eyebrow") }}</div>
              <h2 class="mt-2 text-lg font-semibold text-[#101828]">
                {{ editingWeatherSourceId ? $t("care.weather.editTitle") : $t("care.weather.sourceTitle") }}
              </h2>
            </div>
            <button
              v-if="editingWeatherSourceId"
              class="rounded-full border border-[#E4E7EC] bg-white px-3 py-1.5 text-xs text-[#344054]"
              @click="resetWeatherSourceForm"
            >
              {{ $t("care.rules.actions.cancelEdit") }}
            </button>
          </div>
          <div class="mt-1 text-sm text-[#667085]">{{ $t("care.weather.sourceDescription") }}</div>
          <div class="mt-4 space-y-3">
            <div class="grid grid-cols-2 gap-2">
              <button
                class="rounded-full px-3 py-2 text-xs transition-all"
                :class="weatherSourceForm.sourceType === 'weather_api' ? 'bg-[#07C160] text-white' : 'bg-white text-[#667085] hover:bg-[#EDF7F0]'"
                @click="weatherSourceForm.sourceType = 'weather_api'"
              >
                {{ $t("care.weather.types.openMeteo") }}
              </button>
              <button
                class="rounded-full px-3 py-2 text-xs transition-all"
                :class="weatherSourceForm.sourceType === 'ha_entity' ? 'bg-[#07C160] text-white' : 'bg-white text-[#667085] hover:bg-[#EDF7F0]'"
                @click="weatherSourceForm.sourceType = 'ha_entity'"
              >
                {{ $t("care.weather.types.haEntity") }}
              </button>
            </div>
            <input
              v-model="weatherSourceForm.name"
              :placeholder="$t('care.weather.form.name')"
              class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
            />
            <template v-if="weatherSourceForm.sourceType === 'ha_entity'">
              <input
                v-model="weatherSourceForm.haEntityId"
                :placeholder="$t('care.weather.form.haEntityId')"
                class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
              />
              <input
                v-model="weatherSourceForm.fetchFrequency"
                :placeholder="$t('care.weather.form.fetchFrequency')"
                class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
              />
            </template>
            <template v-else>
              <div class="grid grid-cols-2 gap-3">
                <input
                  v-model="weatherSourceForm.latitude"
                  :placeholder="$t('care.weather.form.latitude')"
                  class="rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                />
                <input
                  v-model="weatherSourceForm.longitude"
                  :placeholder="$t('care.weather.form.longitude')"
                  class="rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                />
              </div>
              <div class="grid grid-cols-2 gap-3">
                <input
                  v-model="weatherSourceForm.timezone"
                  :placeholder="$t('care.weather.form.timezone')"
                  class="rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                />
                <input
                  v-model="weatherSourceForm.fetchFrequency"
                  :placeholder="$t('care.weather.form.fetchFrequency')"
                  class="rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                />
              </div>
            </template>
            <button
              class="inline-flex h-[40px] items-center rounded-full bg-[#07C160] px-5 text-sm font-medium text-white transition-all hover:-translate-y-0.5 hover:bg-[#06AD56] disabled:opacity-50"
              :disabled="saving"
              @click="handleCreateWeatherSource"
            >
              {{ editingWeatherSourceId ? $t("care.weather.actions.saveSource") : $t("care.weather.actions.addSource") }}
            </button>
          </div>
        </div>

        <div class="flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold text-[#101828]">
            {{ editingRuleId ? $t("care.rules.editTitle") : $t("care.rules.createTitle") }}
          </h2>
          <button
            v-if="editingRuleId"
            class="rounded-full border border-[#E4E7EC] bg-white px-3 py-1.5 text-xs text-[#344054]"
            @click="resetRuleForm"
          >
            {{ $t("care.rules.actions.cancelEdit") }}
          </button>
        </div>
        <div class="mt-4 space-y-3">
          <input v-model="form.name" :placeholder="$t('care.rules.form.name')" class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]" />
          <input v-model="form.deviceCategory" :placeholder="$t('care.rules.form.deviceCategory')" class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]" />
          <textarea v-model="form.description" :placeholder="$t('care.rules.form.description')" class="min-h-[92px] w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]" />
          <div class="rounded-3xl border border-[#E4E7EC] bg-[#FAFBFC] p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.rules.builder.title") }}</div>
            <div class="mt-3 grid gap-3">
              <div class="grid grid-cols-3 gap-2">
                <button
                  class="rounded-full px-3 py-2 text-xs transition-all"
                  :class="form.fieldMode === 'control' ? 'bg-[#07C160] text-white' : 'bg-white text-[#667085] hover:bg-[#EDF7F0]'"
                  @click="applyBuilderPreset('control', form.fieldPreset)"
                >
                  {{ $t("care.rules.builder.control") }}
                </button>
                <button
                  class="rounded-full px-3 py-2 text-xs transition-all"
                  :class="form.fieldMode === 'device' ? 'bg-[#07C160] text-white' : 'bg-white text-[#667085] hover:bg-[#EDF7F0]'"
                  @click="applyBuilderPreset('device', form.devicePath)"
                >
                  {{ $t("care.rules.builder.device") }}
                </button>
                <button
                  class="rounded-full px-3 py-2 text-xs transition-all"
                  :class="form.fieldMode === 'offline_hours' ? 'bg-[#07C160] text-white' : 'bg-white text-[#667085] hover:bg-[#EDF7F0]'"
                  @click="applyBuilderPreset('offline_hours')"
                >
                  {{ $t("care.rules.builder.offlineHours") }}
                </button>
              </div>
              <select
                v-if="form.fieldMode === 'control'"
                v-model="form.fieldPreset"
                class="w-full rounded-2xl border border-[#E4E7EC] bg-white px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                @change="applyBuilderPreset('control', form.fieldPreset)"
              >
                <option v-for="option in controlFieldOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <select
                v-else-if="form.fieldMode === 'device'"
                v-model="form.devicePath"
                class="w-full rounded-2xl border border-[#E4E7EC] bg-white px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                @change="applyBuilderPreset('device', form.devicePath)"
              >
                <option v-for="option in deviceFieldOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <input
                v-else
                :value="$t('care.rules.presets.offlineHours')"
                disabled
                class="w-full rounded-2xl border border-[#E4E7EC] bg-[#F2F4F7] px-4 py-3 text-sm text-[#667085] outline-none"
              />
              <div class="grid grid-cols-3 gap-3">
                <select v-model="form.operator" class="rounded-2xl border border-[#E4E7EC] bg-white px-4 py-3 text-sm outline-none focus:border-[#07C160]">
                  <option v-for="option in operatorOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
                <input
                  v-model="form.threshold"
                  :inputmode="thresholdInputMode"
                  :placeholder="thresholdPlaceholder"
                  class="rounded-2xl border border-[#E4E7EC] bg-white px-4 py-3 text-sm outline-none focus:border-[#07C160]"
                />
                <input v-model="form.priority" :placeholder="$t('care.rules.form.priority')" class="rounded-2xl border border-[#E4E7EC] bg-white px-4 py-3 text-sm outline-none focus:border-[#07C160]" />
              </div>
              <div class="rounded-2xl border border-[#E4E7EC] bg-white p-4">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.rules.builder.recommendation") }}</div>
                    <div class="mt-1 text-sm font-medium text-[#101828]">{{ t(activeBuilderMeta.labelKey) }}</div>
                    <div class="mt-1 text-xs leading-6 text-[#667085]">{{ t(activeBuilderMeta.descriptionKey) }}</div>
                  </div>
                  <button
                    class="rounded-full border border-[#D0D5DD] bg-white px-3 py-1.5 text-xs text-[#475467] transition-all hover:border-[#07C160]/30 hover:text-[#07C160]"
                    @click="applyCurrentBuilderDefaults"
                  >
                    {{ $t("care.rules.builder.applyDefaults") }}
                  </button>
                </div>
                <div class="mt-3 flex flex-wrap gap-2 text-[11px] text-[#667085]">
                  <span class="rounded-full bg-[#F2F4F7] px-2.5 py-1">{{ $t("care.rules.builder.recommendedOperator") }}: {{ form.operator }}</span>
                  <span class="rounded-full bg-[#F2F4F7] px-2.5 py-1">{{ $t("care.rules.builder.recommendedThreshold") }}: {{ activeBuilderMeta.threshold }}{{ activeBuilderMeta.unit ? ` ${activeBuilderMeta.unit}` : "" }}</span>
                  <span v-if="activeBuilderMeta.deviceCategory" class="rounded-full bg-[#F2F4F7] px-2.5 py-1">{{ $t("care.rules.builder.recommendedCategory") }}: {{ activeBuilderMeta.deviceCategory }}</span>
                </div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 text-xs text-[#667085]">
                {{ $t("care.rules.builder.preview") }}: <span class="font-medium text-[#101828]">{{ conditionFieldPreview }}</span>
              </div>
            </div>
          </div>
          <input v-model="form.cooldownHours" :placeholder="$t('care.rules.form.cooldownHours')" class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]" />
          <input v-model="form.suggestionTemplate" :placeholder="$t('care.rules.form.template')" class="w-full rounded-2xl border border-[#E4E7EC] px-4 py-3 text-sm outline-none focus:border-[#07C160]" />
          <div class="rounded-3xl border border-[#E4E7EC] bg-[#FAFBFC] p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">{{ $t("care.rules.templates.title") }}</div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button
                v-for="preset in templatePresetOptions"
                :key="preset.id"
                class="rounded-full border border-[#D0D5DD] bg-white px-3 py-1.5 text-xs text-[#475467] transition-all hover:border-[#07C160]/30 hover:text-[#07C160]"
                @click="applyTemplatePreset(preset.value)"
              >
                {{ preset.label }}
              </button>
            </div>
          </div>
          <button
            class="inline-flex h-[42px] items-center rounded-full bg-[#07C160] px-5 text-sm font-medium text-white transition-all hover:-translate-y-0.5 hover:bg-[#06AD56] disabled:opacity-50"
            :disabled="saving"
            @click="handleCreateRule"
          >
            {{ editingRuleId ? $t("care.rules.actions.save") : $t("care.rules.actions.create") }}
          </button>
        </div>
      </section>

      <section class="lg:col-span-7 space-y-5">
        <div class="rounded-3xl border border-[#E4E7EC] bg-white p-5">
          <div class="mb-3 text-lg font-semibold text-[#101828]">{{ $t("care.weather.sourceTitle") }}</div>
          <div v-if="weatherSources.length === 0" class="text-sm text-[#98A2B3]">{{ $t("care.weather.noSource") }}</div>
          <div v-else class="space-y-3">
            <div v-for="source in weatherSources" :key="source.id" class="rounded-2xl border border-[#E9EEF1] bg-[#FAFBFC] p-4">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-[#101828]">{{ source.name }}</div>
                  <div class="mt-1 text-xs text-[#667085]">
                    {{
                      source.sourceType === "ha_entity"
                        ? $t("care.weather.types.haEntity")
                        : source.config.provider || $t("care.weather.types.openMeteo")
                    }}
                    · {{ source.fetchFrequency }} · {{ source.lastFetchAt || "-" }}
                  </div>
                  <div class="mt-2 text-[11px] text-[#98A2B3]">
                    {{ $t("care.weather.sourceSnapshot") }}:
                    {{
                      typeof source.lastData.temperature === "number"
                        ? `${Number(source.lastData.temperature).toFixed(1)}°C`
                        : "--"
                    }}
                    ·
                    {{ String(source.lastData.condition || "--") }}
                  </div>
                  <div v-if="source.sourceType === 'ha_entity'" class="mt-2 text-[11px] text-[#98A2B3]">
                    {{ source.config.ha_entity_id || source.config.entity_id || "-" }}
                  </div>
                </div>
                <div class="flex gap-2">
                  <button class="rounded-full bg-white px-3 py-1 text-xs text-[#344054] border border-[#E4E7EC]" @click="applyWeatherSourceToForm(source)">
                    {{ $t("care.rules.actions.edit") }}
                  </button>
                  <button class="rounded-full px-3 py-1 text-xs" :class="source.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'" @click="toggleWeatherSource(source)">
                    {{ source.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                  </button>
                  <button class="rounded-full bg-[#FFF1F3] px-3 py-1 text-xs text-[#D92D20]" @click="handleDeleteWeatherSource(source)">
                    {{ $t("care.rules.actions.delete") }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-3xl border border-[#E4E7EC] bg-white p-5">
          <div class="mb-3 text-lg font-semibold text-[#101828]">{{ $t("care.rules.systemTitle") }}</div>
          <div v-if="loading" class="py-8 text-center text-sm text-[#98A2B3]">{{ $t("common.loading") }}</div>
          <div v-else-if="systemRules.length === 0" class="text-sm text-[#98A2B3]">{{ $t("care.rules.empty") }}</div>
          <div v-else class="space-y-3">
            <div v-for="rule in systemRules" :key="rule.id" class="rounded-2xl border border-[#E9EEF1] bg-[#FAFBFC] p-4">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-[#101828]">{{ rule.name }}</div>
                  <div class="mt-1 text-xs text-[#667085]">{{ rule.description || rule.suggestionTemplate }}</div>
                </div>
                <button class="rounded-full px-3 py-1 text-xs" :class="rule.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'" @click="toggleRule(rule)">
                  {{ rule.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-3xl border border-[#E4E7EC] bg-white p-5">
          <div class="mb-3 text-lg font-semibold text-[#101828]">{{ $t("care.rules.customTitle") }}</div>
          <div v-if="editableRules.length === 0" class="text-sm text-[#98A2B3]">{{ $t("care.rules.empty") }}</div>
          <div v-else class="space-y-3">
            <div v-for="rule in editableRules" :key="rule.id" class="rounded-2xl border border-[#E9EEF1] bg-white p-4">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-[#101828]">{{ rule.name }}</div>
                  <div class="mt-1 text-xs text-[#667085]">{{ rule.description || rule.suggestionTemplate }}</div>
                  <div class="mt-2 text-[11px] text-[#98A2B3]">{{ rule.deviceCategory || "-" }} · {{ rule.checkFrequency }}</div>
                </div>
                <div class="flex gap-2">
                  <button class="rounded-full bg-white px-3 py-1 text-xs text-[#344054] border border-[#E4E7EC]" @click="applyRuleToForm(rule)">
                    {{ $t("care.rules.actions.edit") }}
                  </button>
                  <button class="rounded-full px-3 py-1 text-xs" :class="rule.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'" @click="toggleRule(rule)">
                    {{ rule.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                  </button>
                  <button class="rounded-full bg-[#FFF1F3] px-3 py-1 text-xs text-[#D92D20]" @click="handleDeleteRule(rule)">
                    {{ $t("care.rules.actions.delete") }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
