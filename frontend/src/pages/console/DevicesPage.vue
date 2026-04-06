<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
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
  reorderDeviceList,
} from "@/lib/devices";
import { formatDateTime } from "@/lib/utils";

const { t } = useI18n();

const DEVICE_PANEL_STATE_STORAGE_KEY = "wanny.devices.panelState";
const DEVICE_PLATFORM_FILTER_STORAGE_KEY = "wanny.devices.platformFilters";

// Dashboard state
const dashboard = ref<DeviceDashboardSnapshot | null>(null);
const loading = ref(true);
const syncing = ref(false);
const errorMessage = ref("");

// Device list state
const devices = ref<DeviceListItem[]>([]);
const devicesLoading = ref(false);
const savingOrder = ref(false);
const pagination = ref({ page: 1, page_size: 10, total: 0, total_pages: 0 });
const searchQuery = ref("");
const activePlatforms = ref<string[]>([]);
const platformSelectOpen = ref(false);
const draggedDeviceId = ref("");
const dragOverDeviceId = ref("");
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

function readLocalStorageJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeLocalStorageJson(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage write failures so the page remains interactive.
  }
}

function restoreUiPreferences() {
  const storedCollapsedGroups = readLocalStorageJson<Record<string, boolean>>(DEVICE_PANEL_STATE_STORAGE_KEY, {});
  const storedPlatforms = readLocalStorageJson<string[]>(DEVICE_PLATFORM_FILTER_STORAGE_KEY, []);

  collapsedGroups.value = Object.fromEntries(
    Object.entries(storedCollapsedGroups).filter(
      (entry): entry is [string, boolean] => typeof entry[0] === "string" && typeof entry[1] === "boolean",
    ),
  );
  activePlatforms.value = storedPlatforms.filter((item): item is string => typeof item === "string");
}

function persistCollapsedGroups() {
  writeLocalStorageJson(DEVICE_PANEL_STATE_STORAGE_KEY, collapsedGroups.value);
}

function persistActivePlatforms() {
  writeLocalStorageJson(DEVICE_PLATFORM_FILTER_STORAGE_KEY, activePlatforms.value);
}

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

function getPlatformMeta(platformId: string) {
  const classes: Record<string, string> = {
    home_assistant: "bg-[#FFF2E8] text-[#C96B2C] border-[#F3C9A8]",
    mijia: "bg-[#EAF3FF] text-[#2F6FDB] border-[#BDD4FF]",
    midea_cloud: "bg-[#EAFBF7] text-[#138A6B] border-[#B7E7DA]",
    mbapi2020: "bg-[#F5F0FF] text-[#6941C6] border-[#D9CCFF]",
    hisense_ha: "bg-[#EEF8FF] text-[#0F6CBD] border-[#B9D8F4]",
    unknown: "bg-[#F2F4F7] text-[#667085] border-[#D0D5DD]",
  };

  return {
    id: platformId,
    label: t(`devices.platforms.${platformId}`),
    className: classes[platformId] ?? classes.unknown,
  };
}

const platformOptions = computed(() => {
  const knownPlatforms = new Map([
    ["home_assistant", getPlatformMeta("home_assistant")],
    ["mijia", getPlatformMeta("mijia")],
    ["midea_cloud", getPlatformMeta("midea_cloud")],
    ["mbapi2020", getPlatformMeta("mbapi2020")],
    ["hisense_ha", getPlatformMeta("hisense_ha")],
  ]);

  (dashboard.value?.devices ?? []).forEach((device) => {
    const platform = inferDevicePlatform(device.id);
    if (!knownPlatforms.has(platform.id)) {
      knownPlatforms.set(platform.id, platform);
    }
  });

  return Array.from(knownPlatforms.values());
});

const platformSelectLabel = computed(() => {
  if (activePlatforms.value.length === 0) return t("devices.filters.all");
  if (activePlatforms.value.length === 1) {
    return platformOptions.value.find((item) => item.id === activePlatforms.value[0])?.label ?? t("devices.filters.all");
  }
  return t("devices.filters.selected", { count: activePlatforms.value.length });
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

function schedulePolling(delay = 10000) {
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
      platforms: activePlatforms.value.length ? activePlatforms.value : undefined,
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
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.detail");
  } finally {
    deviceLoading.value = false;
  }
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

function togglePlatformSelect() {
  platformSelectOpen.value = !platformSelectOpen.value;
}

function togglePlatform(platformId: string) {
  activePlatforms.value = activePlatforms.value.includes(platformId)
    ? activePlatforms.value.filter((item) => item !== platformId)
    : [...activePlatforms.value, platformId];
  persistActivePlatforms();
  pagination.value.page = 1;
  void loadDevices();
}

function clearPlatforms() {
  if (activePlatforms.value.length === 0) return;
  activePlatforms.value = [];
  persistActivePlatforms();
  pagination.value.page = 1;
  void loadDevices();
}

function handleWindowClick(event: MouseEvent) {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.closest("[data-platform-select]")) return;
  platformSelectOpen.value = false;
}

function goToPage(page: number) {
  pagination.value.page = page;
  void loadDevices();
}

function moveDeviceInList(fromId: string, toId: string) {
  const fromIndex = devices.value.findIndex((device) => device.id === fromId);
  const toIndex = devices.value.findIndex((device) => device.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return devices.value;
  const nextDevices = [...devices.value];
  const [moved] = nextDevices.splice(fromIndex, 1);
  nextDevices.splice(toIndex, 0, moved);
  return nextDevices;
}

function handleDeviceDragStart(deviceId: string) {
  draggedDeviceId.value = deviceId;
  dragOverDeviceId.value = deviceId;
}

function handleDeviceDragOver(deviceId: string) {
  if (!draggedDeviceId.value || draggedDeviceId.value === deviceId) return;
  dragOverDeviceId.value = deviceId;
}

function handleDeviceDragEnd() {
  draggedDeviceId.value = "";
  dragOverDeviceId.value = "";
}

async function handleDeviceDrop(targetDeviceId: string) {
  const sourceDeviceId = draggedDeviceId.value;
  handleDeviceDragEnd();
  if (!sourceDeviceId || sourceDeviceId === targetDeviceId || savingOrder.value) return;

  const nextDevices = moveDeviceInList(sourceDeviceId, targetDeviceId);
  if (nextDevices === devices.value) return;

  const previousDevices = [...devices.value];
  devices.value = nextDevices;
  savingOrder.value = true;
  clearFeedback();
  errorMessage.value = "";

  try {
    const response = await reorderDeviceList(nextDevices.map((device) => device.id));
    dashboard.value = response.snapshot;
    showFeedback("success", t("devices.feedback.orderSaved"));
  } catch (error) {
    devices.value = previousDevices;
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.reorder");
    showFeedback("error", t("devices.feedback.orderFailed"));
  } finally {
    savingOrder.value = false;
  }
}

function inferDevicePlatform(deviceId: string) {
  const normalized = String(deviceId || "").toLowerCase();
  if (normalized.startsWith("home_assistant:")) {
    return getPlatformMeta("home_assistant");
  }
  if (normalized.startsWith("mijia:")) {
    return getPlatformMeta("mijia");
  }
  if (normalized.startsWith("midea_cloud:")) {
    return getPlatformMeta("midea_cloud");
  }
  if (normalized.startsWith("mbapi2020:")) {
    return getPlatformMeta("mbapi2020");
  }
  if (normalized.startsWith("hisense_ha:")) {
    return getPlatformMeta("hisense_ha");
  }
  return getPlatformMeta("unknown");
}

function statusLightClass(status: string) {
  if (status === "online") return "bg-[#07C160]";
  if (status === "attention") return "bg-[#E8A223]";
  return "bg-[#E84343]";
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
  const group = groupedControls.value.find((item) => item.label === label);
  if (isTelemetryGroup(label) && (group?.controls.length ?? 0) > 4) {
    return true;
  }
  return [t("devices.groups.system"), t("devices.groups.settings")].includes(label);
}

function toggleGroup(label: string) {
  const device = selectedDevice.value;
  if (!device) return;
  const key = groupKey(device.id, label);
  collapsedGroups.value = {
    ...collapsedGroups.value,
    [key]: !isGroupCollapsed(label),
  };
  persistCollapsedGroups();
}

function isTelemetryGroup(label: string) {
  return [t("devices.groups.telemetry"), t("devices.groups.runtime"), t("devices.highlights.state")].includes(label);
}

function groupPriority(label: string) {
  const priorities: Record<string, number> = {
    [t("devices.groups.wholeMachine")]: 0,
    [t("devices.groups.general")]: 1,
    [t("devices.groups.refrigerator")]: 2,
    [t("devices.groups.freezer")]: 3,
    [t("devices.groups.variableTemperature")]: 4,
    [t("devices.groups.mode")]: 5,
    [t("devices.groups.lighting")]: 6,
    [t("devices.groups.doorBody")]: 7,
    [t("devices.groups.system")]: 90,
    [t("devices.groups.settings")]: 91,
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

function normalizeDisplayUnit(unit = "") {
  const normalized = String(unit || "").trim().toLowerCase();
  if (normalized === "percentage" || normalized === "percent") return "%";
  return unit;
}

function formatValue(value: unknown, unit = "") {
  if (value === null || value === undefined || value === "") return t("devices.values.empty");
  if (typeof value === "object") return JSON.stringify(value);
  const displayUnit = normalizeDisplayUnit(unit);
  if (typeof value === "number") {
    if (displayUnit === "%" && value <= 1) {
      return `${Math.round(value * 100)}%`;
    }
    if (displayUnit === "" && value >= 0 && value <= 1) {
      return `${Math.round(value * 100)}%`;
    }
    if (Number.isInteger(value)) {
      return `${value}${displayUnit}`;
    }
    return `${value.toFixed(2).replace(/\.?0+$/, "")}${displayUnit}`;
  }
  return `${formatEnumLabel(value)}${displayUnit}`;
}

function showFeedback(type: "success" | "error" | "info", message: string) {
  actionFeedback.value = { type, message };
}

function clearFeedback() {
  actionFeedback.value = null;
}

function formatActionLabel(actionId: string, fallbackLabel: string) {
  const actionLabels: Record<string, string> = {
    turn_on: t("devices.actions.turnOn"),
    turn_off: t("devices.actions.turnOff"),
    toggle: t("devices.actions.toggle"),
    unlock: t("devices.actions.unlock"),
    lock: t("devices.actions.lock"),
  };
  return actionLabels[actionId] ?? fallbackLabel;
}

function controlActions(control: DeviceControlRecord) {
  const actions = control.action_params.actions;
  if (Array.isArray(actions) && actions.length > 0) {
    return actions.map((item) => {
      const actionId = String((item as { id?: unknown }).id ?? "");
      const rawLabel = String((item as { label?: unknown }).label ?? t("devices.actions.run"));
      return {
        id: actionId,
        label: formatActionLabel(actionId, rawLabel),
      };
    });
  }

  const service = control.action_params.service;
  return [{ id: String(service ?? "run"), label: formatActionLabel(String(service ?? "run"), t("devices.actions.run")) }];
}

function normalizeToggleState(value: unknown) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (["on", "true", "1", "open", "opened", "unlock", "unlocked"].includes(normalized)) return "on";
  if (["off", "false", "0", "closed", "close", "locked", "lock"].includes(normalized)) return "off";
  return "unknown";
}

function visibleToggleActions(control: DeviceControlRecord) {
  const actions = controlActions(control);
  const state = normalizeToggleState(control.value);

  const filtered = actions.filter((action) => {
    if (state === "on" && ["turn_on", "unlock"].includes(action.id)) return false;
    if (state === "off" && ["turn_off", "lock"].includes(action.id)) return false;
    return true;
  });

  const nonToggleActions = filtered.filter((action) => action.id !== "toggle");
  if (nonToggleActions.length === 1) {
    return nonToggleActions;
  }

  return filtered;
}

function controlValueBadgeClass(control: DeviceControlRecord) {
  if (control.kind === "toggle" && normalizeToggleState(control.value) === "off") {
    return "bg-[#F2F4F7] text-[#98A2B3]";
  }
  return "bg-[#E8F8EC] text-[#07C160]";
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
    dashboard.value = response.snapshot;
    selectedDevice.value = response.snapshot.devices.find((d) => d.id === device.id) ?? device;
    if (response.snapshot.pending_refresh) {
      schedulePolling(1500);
    } else {
      stopPolling();
    }
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
  window.addEventListener("click", handleWindowClick);
  restoreUiPreferences();
  await loadDashboard();
  await loadDevices();
});

onBeforeUnmount(() => {
  window.removeEventListener("click", handleWindowClick);
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
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <div class="flex items-center gap-2 lg:col-span-4">
          <!-- Search -->
          <div class="relative flex-1">
            <input
              v-model="searchQuery"
              type="search"
              :placeholder="$t('common.search')"
              class="h-[34px] w-full rounded-full border border-[#EDEDED] bg-white px-3 pl-4 text-sm focus:outline-none focus:border-[#07C160] transition-colors"
              @input="handleSearchInput"
            />
          </div>
          <div class="flex items-center gap-2 text-sm text-[#667085] ml-4">
            <div class="relative" data-platform-select>
              <button
                @click.stop="togglePlatformSelect"
                class="inline-flex h-[34px] min-w-[160px] items-center justify-between rounded-full border border-[#E4E7EC] bg-white px-3 text-sm text-[#344054] transition-all duration-200 hover:border-[#CBD5E1]"
              >
                <span>{{ platformSelectLabel }}</span>
                <span class="ml-3 text-xs text-[#98A2B3]">{{ platformSelectOpen ? "▲" : "▼" }}</span>
              </button>

              <div
                v-if="platformSelectOpen"
                class="absolute left-0 top-[calc(100%+8px)] z-10 min-w-[220px] rounded-2xl border border-[#E4E7EC] bg-white p-2 shadow-lg"
              >
                <button
                  @click.stop="clearPlatforms"
                  class="mb-1 w-full rounded-xl px-3 py-2 text-left text-sm text-[#98A2B3] transition-colors hover:bg-[#F8FAFC] hover:text-[#344054]"
                >
                  {{ $t("devices.filters.clear") }}
                </button>
                <label
                  v-for="platform in platformOptions"
                  :key="platform.id"
                  class="flex cursor-pointer items-center justify-between rounded-xl px-3 py-2 text-sm text-[#344054] transition-colors hover:bg-[#F8FAFC]"
                >
                  <span>{{ platform.label }}</span>
                  <input
                    :checked="activePlatforms.includes(platform.id)"
                    type="checkbox"
                    class="h-4 w-4 rounded border-[#D0D5DD] text-[#07C160] focus:ring-[#07C160]"
                    @change="togglePlatform(platform.id)"
                  />
                </label>
              </div>
            </div>
          </div>
        </div>
        <!-- Refresh Button -->
        <button
          @click="handleRefresh"
          :disabled="syncing || savingOrder"
          class="inline-flex h-[34px] items-center rounded-full bg-[#07C160] px-4 text-sm font-medium text-white transition-all duration-200 hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50 lg:col-span-8 lg:justify-self-end"
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
              @dragstart="handleDeviceDragStart(device.id)"
              @dragover.prevent="handleDeviceDragOver(device.id)"
              @drop.prevent="handleDeviceDrop(device.id)"
              @dragend="handleDeviceDragEnd"
              draggable="true"
              class="w-full p-4 rounded-2xl border transition-all duration-200"
              :class="selectedDeviceId === device.id
                ? 'bg-[#E8F8EC] border-[#07C160]/30 shadow-sm'
                : dragOverDeviceId === device.id
                  ? 'bg-[#F0FFF4] border-[#07C160]/30 shadow-sm'
                  : 'bg-white border-[#EDEDED] hover:border-[#07C160]/20 hover:bg-[#F7F7F7]'"
            >
              <div class="flex items-center justify-between">
                <div class="flex min-w-0 items-center gap-2">
                  <span class="shrink-0 cursor-grab text-[#98A2B3]" :title="$t('devices.actions.dragSort')">⋮⋮</span>
                  <span class="truncate font-medium text-[#333333]">{{ device.name }}</span>
                  <span
                    class="inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-[0.02em]"
                    :class="inferDevicePlatform(device.id).className"
                  >
                    {{ inferDevicePlatform(device.id).label }}
                  </span>
                </div>
                <span class="ml-3 inline-flex shrink-0 items-center">
                  <span class="h-2.5 w-2.5 rounded-full" :class="statusLightClass(device.status)" />
                </span>
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
            <!-- Controls -->
            <div class="space-y-4">
              <div v-for="group in groupedControls" :key="group.label">
                <button
                  @click="toggleGroup(group.label)"
                  class="flex items-center justify-between w-full py-2 text-sm font-medium text-[#333333] hover:text-[#07C160] transition-colors"
                >
                  <span>{{ group.label }}（{{ group.controls.length }}）</span>
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
                      <span class="min-w-0 pr-3 text-sm text-[#333333]">{{ control.label }}</span>
                      <!-- Toggle switch in header for toggle controls -->
                      <button
                        v-if="control.kind === 'toggle'"
                        @click="runToggle(control, normalizeToggleState(control.value) === 'on' ? 'turn_off' : 'turn_on')"
                        :disabled="executingControlId === control.id"
                        class="relative w-12 h-6 rounded-full transition-all duration-200 disabled:opacity-50 shrink-0"
                        :class="normalizeToggleState(control.value) === 'on' ? 'bg-[#07C160]' : 'bg-[#EDEDED]'"
                      >
                        <span
                          class="absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200"
                          :class="normalizeToggleState(control.value) === 'on' ? 'left-7' : 'left-1'"
                        />
                      </button>
                      <!-- Value badge for non-toggle controls -->
                      <span
                        v-else
                        class="max-w-[9rem] shrink-0 truncate rounded-full px-2 py-0.5 text-xs font-medium md:max-w-[12rem]"
                        :class="controlValueBadgeClass(control)"
                        :title="formatValue(control.value, control.unit)"
                      >
                        {{ formatValue(control.value, control.unit) }}
                      </span>
                    </div>

                    <!-- Range -->
                    <div v-if="control.kind === 'range'" class="space-y-2">
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
