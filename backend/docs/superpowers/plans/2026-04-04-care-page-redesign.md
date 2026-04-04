# 关怀页面重设计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将关怀中心和规则管理合并为三栏布局页面，天气、建议、规则同屏展示。

**Architecture:** 创建三个面板组件（WeatherPanel、SuggestionsPanel、RulesPanel）和两个弹窗组件（DataSourceDialog、RuleEditorDialog），重构 CareCenterPage 为三栏布局，删除 CareRulesPage。

**Tech Stack:** Vue 3 Composition API, TypeScript, Vue I18n, Tailwind CSS

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `frontend/src/components/console/care/WeatherPanel.vue` | 天气面板：显示天气、指数、数据源入口 |
| `frontend/src/components/console/care/SuggestionsPanel.vue` | 建议面板：筛选器、建议列表、巡检按钮 |
| `frontend/src/components/console/care/RulesPanel.vue` | 规则面板：系统规则、自定义规则、新建入口 |
| `frontend/src/components/console/care/DataSourceDialog.vue` | 数据源配置弹窗 |
| `frontend/src/components/console/care/RuleEditorDialog.vue` | 规则编辑弹窗 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/pages/console/CareCenterPage.vue` | 重构为三栏布局 |
| `frontend/src/router/index.ts` | 移除 /care/rules 路由，重定向到 /console/care |
| `frontend/src/i18n/zh-CN/console.ts` | 更新文案 |
| `frontend/src/i18n/en/console.ts` | 更新文案 |

### 删除文件

| 文件 | 说明 |
|------|------|
| `frontend/src/pages/console/CareRulesPage.vue` | 合并到 CareCenterPage |

---

## Task 1: 创建 WeatherPanel 组件

**Files:**
- Create: `frontend/src/components/console/care/WeatherPanel.vue`

- [ ] **Step 1: 创建 WeatherPanel.vue 基础结构**

```vue
<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import type { WeatherSnapshot } from "@/lib/care";
import { formatDateTime } from "@/lib/utils";

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
          <div class="text-[42px] font-semibold text-[#1F2A22]">{{ weatherTemperature }}</div>
          <div>
            <div class="text-sm text-[#344054]">{{ weather.condition || "--" }}</div>
            <div class="text-xs text-[#667085]">
              {{ weather.provider || "--" }}
            </div>
          </div>
        </div>
      </div>
      <div v-else class="rounded-2xl border border-dashed border-[#D0D5DD] px-4 py-5 text-sm text-[#98A2B3] mb-3">
        {{ weatherSourceId ? $t("care.weather.empty") : $t("care.weather.noSource") }}
      </div>

      <!-- Weather Indices -->
      <div v-if="weather" class="grid grid-cols-2 gap-2">
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.humidity") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ weather.raw?.humidity ?? "--" }}%</div>
        </div>
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.feelsLike") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ weather.raw?.feels_like ?? "--" }}°C</div>
        </div>
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.wind") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ weather.raw?.wind_dir ?? "--" }}</div>
        </div>
        <div class="rounded-xl bg-[#F9FAFB] p-3">
          <div class="text-[10px] text-[#98A2B3] uppercase">{{ $t("care.weather.indices.pressure") }}</div>
          <div class="mt-1 text-base font-semibold text-[#1F2A22]">{{ weather.raw?.pressure ?? "--" }}hPa</div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 添加国际化文案到 zh-CN/console.ts**

在 `care.weather` 对象中添加：

```typescript
dataSource: "数据源",
indices: {
  humidity: "湿度",
  feelsLike: "体感",
  wind: "风向",
  pressure: "气压",
},
```

- [ ] **Step 3: 验证组件可导入**

在 CareCenterPage.vue 中临时添加导入验证无语法错误：

```typescript
import WeatherPanel from "@/components/console/care/WeatherPanel.vue";
```

---

## Task 2: 创建 DataSourceDialog 组件

**Files:**
- Create: `frontend/src/components/console/care/DataSourceDialog.vue`

- [ ] **Step 1: 创建 DataSourceDialog.vue**

```vue
<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";

import type { CareDataSourceRecord } from "@/lib/care";

const props = defineProps<{
  open: boolean;
  sources: CareDataSourceRecord[];
  saving: boolean;
}>();

const emit = defineEmits<{
  close: [];
  save: [payload: Partial<CareDataSourceRecord>];
  delete: [id: number];
  toggle: [id: number, active: boolean];
}>();

const { t } = useI18n();

const form = ref({
  sourceType: "weather_api" as "weather_api" | "ha_entity",
  provider: "qweather",
  name: "",
  location: "",
  latitude: "",
  longitude: "",
  timezone: "Asia/Shanghai",
  fetchFrequency: "30m",
  haEntityId: "weather.home",
});

const editingId = ref<number | null>(null);

const weatherSources = computed(() =>
  props.sources.filter((s) => ["weather_api", "ha_entity"].includes(s.sourceType))
);

function resetForm() {
  editingId.value = null;
  form.value = {
    sourceType: "weather_api",
    provider: "qweather",
    name: "",
    location: "",
    latitude: "",
    longitude: "",
    timezone: "Asia/Shanghai",
    fetchFrequency: "30m",
    haEntityId: "weather.home",
  };
}

function switchProvider(provider: "qweather" | "open_meteo") {
  form.value.provider = provider;
  if (!editingId.value || !form.value.name.trim()) {
    form.value.name = provider === "qweather" ? t("care.weather.types.qweather") : "Open-Meteo";
  }
}

function editSource(source: CareDataSourceRecord) {
  const config = source.config || {};
  editingId.value = source.id;
  form.value = {
    sourceType: source.sourceType as "weather_api" | "ha_entity",
    provider: String(config.provider || "qweather"),
    name: source.name,
    location: String(config.location || ""),
    latitude: config.latitude == null ? "" : String(config.latitude),
    longitude: config.longitude == null ? "" : String(config.longitude),
    timezone: String(config.timezone || "Asia/Shanghai"),
    fetchFrequency: source.fetchFrequency,
    haEntityId: String(config.ha_entity_id || config.entity_id || "weather.home"),
  };
}

function handleSubmit() {
  const payload: Partial<CareDataSourceRecord> = {
    sourceType: form.value.sourceType,
    name: form.value.name,
    fetchFrequency: form.value.fetchFrequency,
    isActive: true,
    config:
      form.value.sourceType === "ha_entity"
        ? { ha_entity_id: form.value.haEntityId }
        : form.value.provider === "qweather"
          ? {
              provider: "qweather",
              location: form.value.location.trim() || undefined,
              latitude: form.value.latitude.trim() ? Number(form.value.latitude) : undefined,
              longitude: form.value.longitude.trim() ? Number(form.value.longitude) : undefined,
              timezone: form.value.timezone,
            }
          : {
              provider: "open_meteo",
              latitude: Number(form.value.latitude),
              longitude: Number(form.value.longitude),
              timezone: form.value.timezone,
            },
  };
  emit("save", payload);
}

watch(
  () => props.open,
  (val) => {
    if (!val) resetForm();
  }
);
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4">
    <div class="w-full max-w-lg rounded-[20px] bg-white shadow-[0_24px_80px_rgba(16,24,40,0.2)]">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-[#E4E7EC]">
        <div class="flex items-center justify-between">
          <div class="text-sm font-semibold text-[#1F2A22]">{{ $t("care.weather.sourceTitle") }}</div>
          <button
            class="flex h-7 w-7 items-center justify-center rounded-full bg-[#F2F4F7] text-[#667085] hover:bg-[#E4E7EC]"
            @click="emit('close')"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="p-5 max-h-[60vh] overflow-y-auto">
        <!-- Existing Sources -->
        <div v-if="weatherSources.length > 0" class="mb-4">
          <div class="text-[10px] text-[#98A2B3] uppercase mb-2">{{ $t("care.weather.existingSources") }}</div>
          <div class="space-y-2">
            <div
              v-for="source in weatherSources"
              :key="source.id"
              class="rounded-xl border border-[#E4E7EC] bg-[#F9FAFB] p-3"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-xs font-semibold text-[#1F2A22]">{{ source.name }}</div>
                  <div class="text-[10px] text-[#667085] mt-0.5">
                    {{
                      source.sourceType === "ha_entity"
                        ? $t("care.weather.types.haEntity")
                        : source.config?.provider === "qweather"
                          ? $t("care.weather.types.qweather")
                          : "Open-Meteo"
                    }}
                  </div>
                </div>
                <div class="flex gap-1">
                  <button
                    class="rounded-full px-2 py-1 text-[10px]"
                    :class="source.isActive ? 'bg-[#E8F8EC] text-[#07C160]' : 'bg-[#F2F4F7] text-[#667085]'"
                    @click="emit('toggle', source.id, !source.isActive)"
                  >
                    {{ source.isActive ? $t("care.rules.actions.enabled") : $t("care.rules.actions.disabled") }}
                  </button>
                  <button
                    class="rounded-full bg-white px-2 py-1 text-[10px] text-[#344054] border border-[#E4E7EC]"
                    @click="editSource(source)"
                  >
                    {{ $t("care.rules.actions.edit") }}
                  </button>
                  <button
                    class="rounded-full bg-[#FFF1F3] px-2 py-1 text-[10px] text-[#D92D20]"
                    @click="emit('delete', source.id)"
                  >
                    {{ $t("care.rules.actions.delete") }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Form -->
        <div class="text-[10px] text-[#98A2B3] uppercase mb-2">
          {{ editingId ? $t("care.weather.editTitle") : $t("care.weather.addSource") }}
        </div>
        <div class="space-y-3">
          <!-- Source Type -->
          <div class="flex gap-2">
            <button
              class="flex-1 rounded-full px-3 py-2 text-xs transition-all"
              :class="form.sourceType === 'weather_api' ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085]'"
              @click="form.sourceType = 'weather_api'"
            >
              {{ $t("care.weather.apiSource") }}
            </button>
            <button
              class="flex-1 rounded-full px-3 py-2 text-xs transition-all"
              :class="form.sourceType === 'ha_entity' ? 'bg-[#07C160] text-white' : 'bg-[#F2F4F7] text-[#667085]'"
              @click="form.sourceType = 'ha_entity'"
            >
              {{ $t("care.weather.types.haEntity") }}
            </button>
          </div>

          <!-- Provider Selection (for weather_api) -->
          <div v-if="form.sourceType === 'weather_api'" class="flex gap-2">
            <button
              class="flex-1 rounded-full px-3 py-2 text-xs transition-all"
              :class="form.provider === 'qweather' ? 'bg-[#07C160] text-white' : 'bg-white border border-[#E4E7EC] text-[#667085]'"
              @click="switchProvider('qweather')"
            >
              {{ $t("care.weather.types.qweather") }}
            </button>
            <button
              class="flex-1 rounded-full px-3 py-2 text-xs transition-all"
              :class="form.provider === 'open_meteo' ? 'bg-[#07C160] text-white' : 'bg-white border border-[#E4E7EC] text-[#667085]'"
              @click="switchProvider('open_meteo')"
            >
              {{ $t("care.weather.types.openMeteo") }}
            </button>
          </div>

          <!-- Name -->
          <input
            v-model="form.name"
            :placeholder="$t('care.weather.form.name')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />

          <!-- HA Entity ID -->
          <template v-if="form.sourceType === 'ha_entity'">
            <input
              v-model="form.haEntityId"
              placeholder="weather.home"
              class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
            />
          </template>

          <!-- Weather API Fields -->
          <template v-else>
            <input
              v-if="form.provider === 'qweather'"
              v-model="form.location"
              :placeholder="$t('care.weather.form.location')"
              class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
            />
            <div class="grid grid-cols-2 gap-2">
              <input
                v-model="form.latitude"
                :placeholder="$t('care.weather.form.latitude')"
                class="rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              />
              <input
                v-model="form.longitude"
                :placeholder="$t('care.weather.form.longitude')"
                class="rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
              />
            </div>
          </template>

          <!-- Fetch Frequency -->
          <input
            v-model="form.fetchFrequency"
            :placeholder="$t('care.weather.form.fetchFrequency')"
            class="w-full rounded-xl border border-[#E4E7EC] px-4 py-2.5 text-sm outline-none focus:border-[#07C160]"
          />
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-[#E4E7EC] flex justify-end gap-2">
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
          {{ editingId ? $t("care.weather.actions.saveSource") : $t("care.weather.actions.addSource") }}
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 添加国际化文案**

在 `care.weather` 中添加：

```typescript
addSource: "添加数据源",
existingSources: "已配置数据源",
apiSource: "天气 API",
```

---

## Task 3: 创建 SuggestionsPanel 组件

**Files:**
- Create: `frontend/src/components/console/care/SuggestionsPanel.vue`

- [ ] **Step 1: 创建 SuggestionsPanel.vue**

```vue
<script setup lang="ts">
import { computed, ref, watch } from "vue";
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
  { id: "all", label: t("care.filters.allPriorities") },
  { id: "high", label: t("care.filters.high") },
  { id: "medium", label: t("care.filters.medium") },
  { id: "low", label: t("care.filters.low") },
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

loadSavedFilters();
</script>

<template>
  <div class="rounded-[20px] border border-[#E4E7EC] bg-white overflow-hidden h-full flex flex-col">
    <!-- Header -->
    <div class="px-4 py-4 border-b border-[#E4E7EC]">
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
    <div class="px-4 py-3 border-b border-[#E4E7EC]">
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
```

- [ ] **Step 2: 添加国际化文案**

在 `care` 中添加：

```typescript
suggestions: {
  title: "当前建议",
  pendingCount: "{count} 条待处理",
},
```

---

## Task 4: 创建 RulesPanel 组件

**Files:**
- Create: `frontend/src/components/console/care/RulesPanel.vue`

- [ ] **Step 1: 创建 RulesPanel.vue**

```vue
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
    <div class="px-4 py-4 border-b border-[#E4E7EC]">
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
                <div>
                  <div class="text-xs font-semibold text-[#1F2A22]">{{ rule.name }}</div>
                  <div class="text-[10px] text-[#667085] mt-0.5">{{ rule.description || rule.suggestionTemplate }}</div>
                </div>
                <button
                  class="rounded-full px-2 py-1 text-[10px]"
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
                <div>
                  <div class="text-xs font-semibold text-[#1F2A22]">{{ rule.name }}</div>
                  <div class="text-[10px] text-[#667085] mt-0.5">{{ rule.description || rule.suggestionTemplate }}</div>
                  <div class="text-[10px] text-[#98A2B3] mt-1">{{ rule.deviceCategory || "-" }} · {{ rule.checkFrequency }}</div>
                </div>
                <div class="flex gap-1">
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
```

---

## Task 5: 创建 RuleEditorDialog 组件

**Files:**
- Create: `frontend/src/components/console/care/RuleEditorDialog.vue`

- [ ] **Step 1: 创建 RuleEditorDialog.vue**

从现有 CareRulesPage.vue 提取规则编辑表单逻辑，创建独立弹窗组件。

```vue
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
```

---

## Task 6: 重构 CareCenterPage 为三栏布局

**Files:**
- Modify: `frontend/src/pages/console/CareCenterPage.vue`

- [ ] **Step 1: 重写 CareCenterPage.vue 为三栏布局**

将现有代码重构为三栏布局，引入新组件：

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
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
import { formatDateTime } from "@/lib/utils";

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
    await createCareDataSource(payload);
    actionMessage.value = t("care.feedback.weatherSourceCreated");
    await loadDataSources();
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

    <!-- Confirm Action Dialog (existing) -->
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
```

---

## Task 7: 更新路由配置

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 移除 CareRulesPage 路由，添加重定向**

```typescript
// 移除这行导入
// import CareRulesPage from "@/pages/console/CareRulesPage.vue";

// 在 children 数组中移除 care/rules 路由，添加重定向
{
  path: "care/rules",
  redirect: "/console/care",
},
```

---

## Task 8: 更新国际化文件

**Files:**
- Modify: `frontend/src/i18n/zh-CN/console.ts`
- Modify: `frontend/src/i18n/en/console.ts`

- [ ] **Step 1: 更新 zh-CN/console.ts**

在 `care` 对象中添加：

```typescript
suggestions: {
  title: "当前建议",
  pendingCount: "{count} 条待处理",
},
weather: {
  // 现有内容...
  dataSource: "数据源",
  addSource: "添加数据源",
  existingSources: "已配置数据源",
  apiSource: "天气 API",
  indices: {
    humidity: "湿度",
    feelsLike: "体感",
    wind: "风向",
    pressure: "气压",
  },
},
```

- [ ] **Step 2: 更新 en/console.ts**

添加对应的英文翻译。

---

## Task 9: 删除 CareRulesPage

**Files:**
- Delete: `frontend/src/pages/console/CareRulesPage.vue`

- [ ] **Step 1: 删除文件**

```bash
rm frontend/src/pages/console/CareRulesPage.vue
```

---

## Task 10: 验证和测试

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: 验证功能**

1. 访问 /console/care，确认三栏布局正常显示
2. 点击"数据源"按钮，确认弹窗正常打开
3. 创建/编辑数据源，确认保存成功
4. 点击"立即巡检"，确认建议列表更新
5. 点击规则面板的"新建"，确认规则弹窗正常
6. 创建/编辑/删除规则，确认操作成功
7. 验证建议筛选功能正常
8. 验证建议详情和执行功能正常

- [ ] **Step 3: 提交代码**

```bash
git add -A
git commit -m "feat(care): redesign care page with three-column layout

- Add WeatherPanel, SuggestionsPanel, RulesPanel components
- Add DataSourceDialog, RuleEditorDialog components
- Refactor CareCenterPage to three-column layout
- Remove CareRulesPage (merged into CareCenterPage)
- Update i18n files with new labels

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```