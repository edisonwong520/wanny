<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  type DeviceControlRecord,
  type DeviceDashboardSnapshot,
  type DeviceListItem,
  type DeviceSnapshotRecord,
  executeDeviceControl,
  fetchDeviceDashboard,
  fetchDeviceDetail,
  fetchDeviceList,
  refreshDeviceDashboard,
} from "@/lib/devices";
import { formatDateTime } from "@/lib/utils";

const { t } = useI18n();

// Dashboard state
const dashboard = ref<DeviceDashboardSnapshot | null>(null);
const loading = ref(true);
const syncing = ref(false);
const errorMessage = ref("");

// Device list state
const devices = ref<DeviceListItem[]>([]);
const devicesLoading = ref(false);
const pagination = ref({ page: 1, page_size: 8, total: 0, total_pages: 0 });
const searchQuery = ref("");
const activeRoomId = ref("all");
let searchTimeout: number | null = null;

// Selected device detail
const selectedDeviceId = ref("");
const selectedDevice = ref<DeviceSnapshotRecord | null>(null);
const deviceLoading = ref(false);
const executingControlId = ref("");
const draftValues = ref<Record<string, unknown>>({});
const collapsedGroups = ref<Record<string, boolean>>({});
const actionFeedback = ref<{ type: "success" | "error" | "info"; message: string } | null>(null);

let pollTimer: number | null = null;

// Rooms computed from dashboard
const rooms = computed(() => {
  const r = dashboard.value?.rooms ?? [];
  const total = pagination.value.total;
  return [
    { id: "all", name: t("devices.filters.all"), count: total },
    ...r.map((room) => ({ id: room.id, name: room.name, count: room.device_count })),
  ];
});

// Metrics computed from dashboard
const metrics = computed(() => {
  const devicesList = dashboard.value?.devices ?? [];
  return {
    online: devicesList.filter((item) => item.status === "online").length,
    attention: devicesList.filter((item) => item.status === "attention").length,
    offline: devicesList.filter((item) => item.status === "offline").length,
    controls: selectedDevice.value?.controls.length ?? 0,
  };
});

const groupedControls = computed(() => {
  const device = selectedDevice.value;
  if (!device) return [];

  const groups = new Map<string, DeviceControlRecord[]>();
  device.controls.forEach((control) => {
    const key = control.group_label || t("devices.groups.general");
    groups.set(key, [...(groups.get(key) ?? []), control]);
  });

  return Array.from(groups.entries())
    .map(([label, controls]) => ({
      label,
      controls: [...controls].sort((a, b) => controlPriority(a) - controlPriority(b) || a.label.localeCompare(b.label)),
    }))
    .sort((a, b) => groupPriority(a.label) - groupPriority(b.label) || a.label.localeCompare(b.label));
});

const selectedDeviceHighlights = computed(() => {
  const device = selectedDevice.value;
  if (!device) return [];

  const highlights: Array<{ label: string; value: string }> = [];
  const addHighlight = (label: string, matcher: (control: DeviceControlRecord) => boolean) => {
    const found = device.controls.find(matcher);
    if (found) highlights.push({ label, value: formatValue(found.value, found.unit) });
  };

  const category = device.category;
  if (category.includes("空调")) {
    addHighlight(t("devices.highlights.mode"), (control) => control.key.includes(":hvac_mode"));
    addHighlight(t("devices.highlights.targetTemp"), (control) => control.key.includes(":target_temperature"));
    addHighlight(t("devices.highlights.currentTemp"), (control) => control.key.includes(":current_temperature"));
  } else if (category.includes("冰箱")) {
    addHighlight(t("devices.highlights.refrigerator"), (control) => control.group_label === "冷藏区");
    addHighlight(t("devices.highlights.freezer"), (control) => control.group_label === "冷冻区");
    addHighlight(t("devices.highlights.power"), (control) => control.kind === "toggle");
  } else if (category.includes("清洁")) {
    addHighlight(t("devices.highlights.state"), (control) => control.kind === "action");
    addHighlight(t("devices.highlights.mode"), (control) => control.key.includes(":fan_speed"));
  } else if (category.includes("媒体")) {
    addHighlight(t("devices.highlights.state"), (control) => control.kind === "action");
    addHighlight(t("devices.highlights.volume"), (control) => control.key.includes(":volume_level"));
    addHighlight(t("devices.highlights.source"), (control) => control.key.includes(":source"));
  } else {
    addHighlight(t("devices.highlights.state"), (control) => control.kind === "toggle" || control.kind === "enum");
    addHighlight(t("devices.highlights.primary"), (control) => control.kind === "range");
    addHighlight(t("devices.highlights.secondary"), (control) => control.kind === "sensor");
  }

  return highlights.filter((item, index, array) => array.findIndex((x) => x.label === item.label) === index).slice(0, 3);
});

// Methods
function stopPolling() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function schedulePolling(delay = 3000) {
  stopPolling();
  pollTimer = window.setTimeout(() => void loadDashboard({ silent: true }), delay);
}

async function loadDashboard(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true;
  errorMessage.value = "";
  try {
    const response = await fetchDeviceDashboard();
    dashboard.value = response.snapshot;
    if (response.snapshot.pending_refresh) {
      schedulePolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    stopPolling();
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.load");
  } finally {
    if (!options.silent) loading.value = false;
  }
}

async function loadDevices(options: { silent?: boolean } = {}) {
  if (!options.silent) devicesLoading.value = true;
  try {
    const response = await fetchDeviceList({
      page: pagination.value.page,
      page_size: pagination.value.page_size,
      search: searchQuery.value || undefined,
      room_id: activeRoomId.value !== "all" ? activeRoomId.value : undefined,
    });
    devices.value = response.devices;
    pagination.value = response.pagination;

    // Auto-select first device if current selection is not in list
    if (devices.value.length > 0) {
      const isSelectedInList = devices.value.some((d) => d.id === selectedDeviceId.value);
      if (!isSelectedInList) {
        await selectDevice(devices.value[0].id);
      }
    } else {
      selectedDeviceId.value = "";
      selectedDevice.value = null;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.load");
  } finally {
    if (!options.silent) devicesLoading.value = false;
  }
}

async function selectDevice(deviceId: string) {
  if (deviceId === selectedDeviceId.value && selectedDevice.value) return;

  selectedDeviceId.value = deviceId;
  deviceLoading.value = true;
  try {
    const response = await fetchDeviceDetail(deviceId);
    selectedDevice.value = response.device;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "Failed to load device";
  } finally {
    deviceLoading.value = false;
  }
}

function selectRoom(id: string) {
  activeRoomId.value = id;
  pagination.value.page = 1;
  void loadDevices();
}

function handleSearchInput() {
  if (searchTimeout !== null) {
    window.clearTimeout(searchTimeout);
  }
  searchTimeout = window.setTimeout(() => {
    pagination.value.page = 1;
    void loadDevices();
  }, 300);
}

function clearSearch() {
  searchQuery.value = "";
  pagination.value.page = 1;
  void loadDevices();
}

function goToPage(page: number) {
  pagination.value.page = page;
  void loadDevices();
}

function groupKey(deviceId: string, label: string) {
  return `${deviceId}::${label}`;
}

function isGroupCollapsed(label: string) {
  const device = selectedDevice.value;
  if (!device) return false;
  const key = groupKey(device.id, label);
  if (key in collapsedGroups.value) {
    return collapsedGroups.value[key];
  }
  return ["系统", "设置", "System", "Settings"].includes(label);
}

function toggleGroup(label: string) {
  const device = selectedDevice.value;
  if (!device) return;
  const key = groupKey(device.id, label);
  collapsedGroups.value = {
    ...collapsedGroups.value,
    [key]: !isGroupCollapsed(label),
  };
}

function groupPriority(label: string) {
  const priorities: Record<string, number> = {
    整机: 0,
    通用: 1,
    冷藏区: 2,
    冷冻区: 3,
    变温区: 4,
    模式: 5,
    照明: 6,
    门体: 7,
    General: 1,
    System: 90,
    Settings: 91,
    系统: 90,
    设置: 91,
  };
  return priorities[label] ?? 20;
}

function controlPriority(control: DeviceControlRecord) {
  if (control.kind === "toggle") return 0;
  if (control.key.includes(":hvac_mode")) return 1;
  if (control.key.includes(":target_temperature")) return 2;
  if (control.key.includes(":brightness") || control.key.includes(":percentage")) return 3;
  if (control.kind === "enum") return 4;
  if (control.kind === "range") return 5;
  if (control.kind === "action") return 6;
  if (control.kind === "sensor") return 8;
  return 10;
}

function readDraftValue(control: DeviceControlRecord) {
  return draftValues.value[control.id] ?? control.value ?? "";
}

function writeDraftValue(controlId: string, value: unknown) {
  draftValues.value = {
    ...draftValues.value,
    [controlId]: value,
  };
}

function formatValue(value: unknown, unit = "") {
  if (value === null || value === undefined || value === "") return t("devices.values.empty");
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number") {
    if (unit === "%" && value <= 1) {
      return `${Math.round(value * 100)}%`;
    }
    if (unit === "" && value >= 0 && value <= 1) {
      return `${Math.round(value * 100)}%`;
    }
    if (Number.isInteger(value)) {
      return `${value}${unit}`;
    }
    return `${value.toFixed(2).replace(/\.?0+$/, "")}${unit}`;
  }
  return `${formatEnumLabel(value)}${unit}`;
}

function showFeedback(type: "success" | "error" | "info", message: string) {
  actionFeedback.value = { type, message };
}

function clearFeedback() {
  actionFeedback.value = null;
}

function controlActions(control: DeviceControlRecord) {
  const actions = control.action_params.actions;
  if (Array.isArray(actions) && actions.length > 0) {
    return actions.map((item) => ({
      id: String((item as { id?: unknown }).id ?? ""),
      label: String((item as { label?: unknown }).label ?? t("devices.actions.run")),
    }));
  }

  const service = control.action_params.service;
  return [{ id: String(service ?? "run"), label: t("devices.actions.run") }];
}

function formatEnumLabel(value: unknown) {
  const raw = String(value ?? "").trim();
  if (!raw) return t("devices.values.empty");

  const enumLabels: Record<string, string> = {
    on: t("devices.enum.on"),
    off: t("devices.enum.off"),
    cool: t("devices.enum.cool"),
    heat: t("devices.enum.heat"),
    auto: t("devices.enum.auto"),
    dry: t("devices.enum.dry"),
    fan_only: t("devices.enum.fanOnly"),
    heat_cool: t("devices.enum.heatCool"),
    swing: t("devices.enum.swing"),
    vertical: t("devices.enum.vertical"),
    horizontal: t("devices.enum.horizontal"),
    low: t("devices.enum.low"),
    medium: t("devices.enum.medium"),
    high: t("devices.enum.high"),
    sleep: t("devices.enum.sleep"),
    none: t("devices.enum.none"),
    playing: t("devices.enum.playing"),
    paused: t("devices.enum.paused"),
    idle: t("devices.enum.idle"),
    docked: t("devices.enum.docked"),
    cleaning: t("devices.enum.cleaning"),
    returning: t("devices.enum.returning"),
  };

  return enumLabels[raw.toLowerCase()] ?? raw.replace(/_/g, " ");
}

function displayOptionLabel(option: { label: string; value: unknown }) {
  const normalized = String(option.label || "").trim();
  if (normalized && normalized !== String(option.value ?? "")) {
    return normalized;
  }
  return formatEnumLabel(option.value);
}

function normalizeRangeBounds(control: DeviceControlRecord) {
  const min = Number(control.range_spec.min ?? 0);
  const max = Number(control.range_spec.max ?? 100);
  const step = Number(control.range_spec.step ?? 1);

  if (control.unit === "" && max <= 1) {
    return { min, max, step: step || 0.01, scalePercent: true };
  }

  return { min, max, step, scalePercent: false };
}

function handleRangeInput(controlId: string, event: Event) {
  writeDraftValue(controlId, Number((event.target as HTMLInputElement).value));
}

function handleEnumInput(controlId: string, event: Event) {
  writeDraftValue(controlId, (event.target as HTMLSelectElement).value);
}

function handleTextInput(controlId: string, event: Event) {
  writeDraftValue(controlId, (event.target as HTMLInputElement).value);
}

function rangeInputValue(control: DeviceControlRecord) {
  const draft = Number(readDraftValue(control) ?? 0);
  return Number.isNaN(draft) ? 0 : draft;
}

async function handleRefresh() {
  syncing.value = true;
  errorMessage.value = "";
  clearFeedback();
  try {
    const response = await refreshDeviceDashboard();
    dashboard.value = response.snapshot;
    showFeedback("info", t("devices.feedback.refreshQueued"));
    if (response.snapshot.pending_refresh) {
      schedulePolling();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.load");
  } finally {
    syncing.value = false;
  }
}

async function submitControl(control: DeviceControlRecord, payload: { action?: string; value?: unknown }) {
  const device = selectedDevice.value;
  if (!device) return;

  executingControlId.value = control.id;
  errorMessage.value = "";
  clearFeedback();

  try {
    const response = await executeDeviceControl(device.id, control.id, payload);
    selectedDevice.value = response.snapshot.devices.find((d) => d.id === device.id) ?? device;
    showFeedback("success", t("devices.feedback.actionSuccess", { name: control.label }));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.action");
    showFeedback("error", t("devices.feedback.actionFailed", { name: control.label }));
  } finally {
    executingControlId.value = "";
  }
}

async function runToggle(control: DeviceControlRecord, action: string) {
  await submitControl(control, { action });
}

async function runAction(control: DeviceControlRecord, action?: string) {
  await submitControl(control, { action });
}

async function saveValue(control: DeviceControlRecord) {
  await submitControl(control, { value: readDraftValue(control) });
}

onMounted(async () => {
  await loadDashboard();
  await loadDevices();
});

onBeforeUnmount(() => {
  stopPolling();
  if (searchTimeout !== null) {
    window.clearTimeout(searchTimeout);
  }
});
</script>

<template>
  <div class="space-y-5">
    <!-- Alerts -->
    <div v-if="errorMessage" class="p-4 rounded-2xl bg-[#FFE8E8] text-[#E84343] text-sm flex items-center justify-between">
      <span>{{ errorMessage }}</span>
      <button @click="errorMessage = ''" class="opacity-60 hover:opacity-100">✕</button>
    </div>

    <div v-if="actionFeedback"
      class="p-4 rounded-2xl text-sm flex items-center justify-between transition-all duration-300"
      :class="{
        'bg-[#E8F8EC] text-[#07C160]': actionFeedback.type === 'success',
        'bg-[#FFE8E8] text-[#E84343]': actionFeedback.type === 'error',
        'bg-[#FFF7E6] text-[#E8A223]': actionFeedback.type === 'info'
      }"
    >
      <span>{{ actionFeedback.message }}</span>
      <button @click="clearFeedback" class="opacity-60 hover:opacity-100">✕</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-12 text-center text-sm text-[#888888]">
      {{ $t("common.loading") }}
    </div>

    <template v-else-if="dashboard">
      <!-- Metrics -->
      <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="p-4 rounded-2xl bg-[#E8F8EC] transition-all duration-200 hover:-translate-y-1 hover:shadow-md">
          <div class="text-sm text-[#07C160]">{{ $t("devices.metrics.online") }}</div>
          <div class="mt-1 text-2xl font-semibold text-[#07C160]">{{ metrics.online }}</div>
        </div>
        <div class="p-4 rounded-2xl bg-[#FFF7E6] transition-all duration-200 hover:-translate-y-1 hover:shadow-md">
          <div class="text-sm text-[#E8A223]">{{ $t("devices.metrics.attention") }}</div>
          <div class="mt-1 text-2xl font-semibold text-[#E8A223]">{{ metrics.attention }}</div>
        </div>
        <div class="p-4 rounded-2xl bg-[#FFE8E8] transition-all duration-200 hover:-translate-y-1 hover:shadow-md">
          <div class="text-sm text-[#E84343]">{{ $t("devices.metrics.offline") }}</div>
          <div class="mt-1 text-2xl font-semibold text-[#E84343]">{{ metrics.offline }}</div>
        </div>
        <div class="p-4 rounded-2xl bg-[#F7F7F7] transition-all duration-200 hover:-translate-y-1 hover:shadow-md">
          <div class="text-sm text-[#888888]">{{ $t("devices.metrics.controls") }}</div>
          <div class="mt-1 text-2xl font-semibold text-[#333333]">{{ metrics.controls }}</div>
        </div>
      </section>

      <!-- Filters + Refresh -->
      <div class="flex items-center justify-between gap-4">
        <div class="flex items-center gap-2 flex-1">
          <!-- Search -->
          <div class="relative flex-1 max-w-xs">
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="$t('common.search')"
              class="w-full px-3 py-1.5 pl-8 rounded-full border border-[#EDEDED] bg-white text-sm focus:outline-none focus:border-[#07C160] transition-colors"
              :class="searchQuery ? 'pr-8' : ''"
              @input="handleSearchInput"
            />
            <span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#888888] text-sm">🔍</span>
            <button
              v-if="searchQuery"
              @click="clearSearch"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-[#888888] hover:text-[#333333] text-sm"
            >✕</button>
          </div>
          <!-- Room Filters -->
          <div class="flex gap-1.5">
            <button
              v-for="room in rooms"
              :key="room.id"
              @click="selectRoom(room.id)"
              class="px-3 py-1.5 rounded-full text-xs transition-all duration-200"
              :class="activeRoomId === room.id
                ? 'bg-[#07C160] text-white shadow-sm'
                : 'bg-[#F7F7F7] text-[#888888] hover:bg-[#EDEDED]'"
            >
              {{ room.name }} ({{ room.count }})
            </button>
          </div>
        </div>
        <!-- Refresh Button -->
        <button
          @click="handleRefresh"
          :disabled="syncing"
          class="px-4 py-1.5 rounded-full bg-[#07C160] text-white text-sm font-medium transition-all duration-200 hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ syncing ? $t("common.loading") : $t("devices.actions.refresh") }}
        </button>
      </div>

      <!-- Main Layout -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <!-- Device List -->
        <div class="lg:col-span-4 space-y-2">
          <div v-if="devicesLoading" class="py-8 text-center text-sm text-[#888888]">
            {{ $t("common.loading") }}
          </div>

          <div v-else-if="devices.length === 0" class="p-8 text-center rounded-2xl border-2 border-dashed border-[#EDEDED]">
            <div class="text-[#888888] text-sm">{{ $t("devices.empty.devices") }}</div>
          </div>

          <template v-else>
            <button
              v-for="device in devices"
              :key="device.id"
              @click="selectDevice(device.id)"
              class="w-full p-4 rounded-2xl border transition-all duration-200"
              :class="selectedDeviceId === device.id
                ? 'bg-[#E8F8EC] border-[#07C160]/30 shadow-sm'
                : 'bg-white border-[#EDEDED] hover:border-[#07C160]/20 hover:bg-[#F7F7F7]'"
            >
              <div class="flex items-center justify-between">
                <span class="font-medium text-[#333333]">{{ device.name }}</span>
                <span
                  class="px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="{
                    'bg-[#E8F8EC] text-[#07C160]': device.status === 'online',
                    'bg-[#FFF7E6] text-[#E8A223]': device.status === 'attention',
                    'bg-[#FFE8E8] text-[#E84343]': device.status === 'offline'
                  }"
                >
                  {{ t(`devices.status.${device.status}`) }}
                </span>
              </div>
              <div class="mt-1 text-xs text-[#888888] truncate">
                {{ device.telemetry || $t("devices.values.empty") }}
              </div>
            </button>

            <!-- Pagination -->
            <div v-if="pagination.total_pages > 1" class="flex items-center justify-center gap-1 pt-2">
              <button
                :disabled="pagination.page <= 1"
                @click="goToPage(pagination.page - 1)"
                class="w-8 h-8 rounded-full text-xs transition-all"
                :class="pagination.page <= 1 ? 'text-[#EDEDED]' : 'text-[#888888] hover:bg-[#F7F7F7]'"
              >
                ‹
              </button>
              <button
                v-for="p in Math.min(pagination.total_pages, 5)"
                :key="p"
                @click="goToPage(p)"
                class="w-8 h-8 rounded-full text-xs transition-all"
                :class="p === pagination.page
                  ? 'bg-[#07C160] text-white'
                  : 'text-[#888888] hover:bg-[#F7F7F7]'"
              >
                {{ p }}
              </button>
              <span v-if="pagination.total_pages > 5" class="px-1 text-xs text-[#888888]">...</span>
              <button
                :disabled="pagination.page >= pagination.total_pages"
                @click="goToPage(pagination.page + 1)"
                class="w-8 h-8 rounded-full text-xs transition-all"
                :class="pagination.page >= pagination.total_pages ? 'text-[#EDEDED]' : 'text-[#888888] hover:bg-[#F7F7F7]'"
              >
                ›
              </button>
            </div>
          </template>
        </div>

        <!-- Device Panel -->
        <div class="lg:col-span-8 rounded-2xl border border-[#EDEDED] bg-white min-h-[400px]">
          <div v-if="deviceLoading" class="p-12 text-center text-sm text-[#888888]">
            {{ $t("common.loading") }}
          </div>

          <div v-else-if="selectedDevice" class="p-5">
            <!-- Device Info -->
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-base font-semibold text-[#333333]">{{ selectedDevice.name }}</h2>
              <span
                class="px-2 py-0.5 rounded-full text-xs font-medium"
                :class="{
                  'bg-[#E8F8EC] text-[#07C160]': selectedDevice.status === 'online',
                  'bg-[#FFF7E6] text-[#E8A223]': selectedDevice.status === 'attention',
                  'bg-[#FFE8E8] text-[#E84343]': selectedDevice.status === 'offline'
                }"
              >
                {{ t(`devices.status.${selectedDevice.status}`) }}
              </span>
            </div>

            <!-- Highlights -->
            <div v-if="selectedDeviceHighlights.length" class="flex gap-2 mb-5">
              <div
                v-for="item in selectedDeviceHighlights"
                :key="item.label"
                class="px-3 py-2 rounded-xl bg-[#F7F7F7]"
              >
                <div class="text-xs text-[#888888]">{{ item.label }}</div>
                <div class="text-sm font-medium text-[#333333]">{{ item.value }}</div>
              </div>
            </div>

            <!-- Controls -->
            <div class="space-y-4">
              <div v-for="group in groupedControls" :key="group.label">
                <button
                  @click="toggleGroup(group.label)"
                  class="flex items-center justify-between w-full py-2 text-sm font-medium text-[#333333] hover:text-[#07C160] transition-colors"
                >
                  <span>{{ group.label }}</span>
                  <span class="text-xs text-[#888888]">{{ isGroupCollapsed(group.label) ? $t("devices.actions.expand") : $t("devices.actions.collapse") }}</span>
                </button>

                <div v-if="!isGroupCollapsed(group.label)" class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div
                    v-for="control in group.controls"
                    :key="control.id"
                    class="p-3 rounded-xl border border-[#EDEDED] bg-[#F7F7F7]/50"
                    :class="executingControlId === control.id ? 'opacity-60' : ''"
                  >
                    <div class="flex items-center justify-between mb-2">
                      <span class="text-sm text-[#333333]">{{ control.label }}</span>
                      <span class="text-xs font-medium text-[#07C160] bg-[#E8F8EC] px-2 py-0.5 rounded-full">
                        {{ formatValue(control.value, control.unit) }}
                      </span>
                    </div>

                    <!-- Sensor -->
                    <p v-if="control.kind === 'sensor'" class="text-xs text-[#888888]">
                      {{ $t("devices.hints.readOnly") }}
                    </p>

                    <!-- Toggle -->
                    <div v-else-if="control.kind === 'toggle'" class="flex gap-2">
                      <button
                        v-for="action in controlActions(control)"
                        :key="action.id"
                        @click="runToggle(control, action.id)"
                        :disabled="executingControlId === control.id"
                        class="px-3 py-1 rounded-full text-xs transition-all duration-200 border border-[#07C160]/30 text-[#07C160] hover:bg-[#07C160] hover:text-white disabled:opacity-50"
                      >
                        {{ action.label }}
                      </button>
                    </div>

                    <!-- Range -->
                    <div v-else-if="control.kind === 'range'" class="space-y-2">
                      <input
                        type="range"
                        class="w-full h-1 bg-[#EDEDED] rounded-lg appearance-none cursor-pointer accent-[#07C160]"
                        :min="normalizeRangeBounds(control).min"
                        :max="normalizeRangeBounds(control).max"
                        :step="normalizeRangeBounds(control).step"
                        :value="rangeInputValue(control)"
                        @input="handleRangeInput(control.id, $event)"
                      />
                      <div class="flex items-center justify-between">
                        <span class="text-xs text-[#333333]">{{ formatValue(readDraftValue(control), control.unit) }}</span>
                        <button
                          @click="saveValue(control)"
                          :disabled="executingControlId === control.id"
                          class="px-3 py-1 rounded-full bg-[#07C160] text-white text-xs transition-all hover:bg-[#06AD56] disabled:opacity-50"
                        >
                          {{ $t("devices.actions.apply") }}
                        </button>
                      </div>
                    </div>

                    <!-- Enum -->
                    <div v-else-if="control.kind === 'enum'" class="flex gap-2">
                      <select
                        class="flex-1 bg-white border border-[#EDEDED] rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-[#07C160]"
                        :value="String(readDraftValue(control) ?? '')"
                        @change="handleEnumInput(control.id, $event)"
                      >
                        <option v-for="option in control.options" :key="String(option.value)" :value="String(option.value)">
                          {{ displayOptionLabel(option) }}
                        </option>
                      </select>
                      <button
                        @click="saveValue(control)"
                        :disabled="executingControlId === control.id"
                        class="px-3 py-1 rounded-full bg-[#07C160] text-white text-xs transition-all hover:bg-[#06AD56] disabled:opacity-50"
                      >
                        {{ $t("devices.actions.apply") }}
                      </button>
                    </div>

                    <!-- Text -->
                    <div v-else-if="control.kind === 'text'" class="flex gap-2">
                      <input
                        type="text"
                        class="flex-1 bg-white border border-[#EDEDED] rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-[#07C160]"
                        :value="String(readDraftValue(control) ?? '')"
                        @input="handleTextInput(control.id, $event)"
                      />
                      <button
                        @click="saveValue(control)"
                        :disabled="executingControlId === control.id"
                        class="px-3 py-1 rounded-full bg-[#07C160] text-white text-xs transition-all hover:bg-[#06AD56] disabled:opacity-50"
                      >
                        {{ $t("devices.actions.apply") }}
                      </button>
                    </div>

                    <!-- Action -->
                    <div v-else-if="control.kind === 'action'" class="flex gap-2">
                      <button
                        v-for="action in controlActions(control)"
                        :key="action.id"
                        @click="runAction(control, action.id)"
                        :disabled="executingControlId === control.id"
                        class="px-3 py-1 rounded-full bg-[#07C160] text-white text-xs transition-all hover:bg-[#06AD56] disabled:opacity-50"
                      >
                        {{ action.label }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="p-12 text-center">
            <div class="text-3xl mb-2 opacity-40">🏠</div>
            <div class="text-sm text-[#888888]">{{ $t("devices.empty.noDevices") }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>