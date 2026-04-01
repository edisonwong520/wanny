<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  type DeviceControlRecord,
  type DeviceDashboardSnapshot,
  type DeviceSnapshotRecord,
  executeDeviceControl,
  fetchDeviceDashboard,
  refreshDeviceDashboard,
} from "@/lib/devices";
import { formatDateTime } from "@/lib/utils";

const { t } = useI18n();

const dashboard = ref<DeviceDashboardSnapshot | null>(null);
const activeRoomId = ref("all");
const selectedDeviceId = ref("");
const loading = ref(true);
const syncing = ref(false);
const errorMessage = ref("");
const executingControlId = ref("");
const draftValues = ref<Record<string, unknown>>({});
const collapsedGroups = ref<Record<string, boolean>>({});
const actionFeedback = ref<{ type: "success" | "error" | "info"; message: string } | null>(null);
let pollTimer: number | null = null;

const rooms = computed(() => {
  const r = dashboard.value?.rooms ?? [];
  const total = dashboard.value?.devices.length ?? 0;
  return [
    { id: "all", name: t("devices.filters.all"), count: total },
    ...r.map((room) => ({ id: room.id, name: room.name, count: room.device_count })),
  ];
});

const visibleDevices = computed<DeviceSnapshotRecord[]>(() => {
  const devices = dashboard.value?.devices ?? [];
  if (activeRoomId.value === "all") return devices;
  return devices.filter((device) => device.room_id === activeRoomId.value);
});

const selectedDevice = computed<DeviceSnapshotRecord | null>(() => {
  const devices = visibleDevices.value;
  return devices.find((device) => device.id === selectedDeviceId.value) ?? devices[0] ?? null;
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

const metrics = computed(() => {
  const devices = dashboard.value?.devices ?? [];
  return {
    online: devices.filter((item) => item.status === "online").length,
    attention: devices.filter((item) => item.status === "attention").length,
    offline: devices.filter((item) => item.status === "offline").length,
    controls: selectedDevice.value?.controls.length ?? 0,
  };
});

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

function syncSelection() {
  const devices = visibleDevices.value;
  if (devices.length === 0) {
    selectedDeviceId.value = "";
    return;
  }

  if (!devices.some((device) => device.id === selectedDeviceId.value)) {
    selectedDeviceId.value = devices[0].id;
  }
}

function selectRoom(id: string) {
  activeRoomId.value = id;
  syncSelection();
}

function selectDevice(id: string) {
  selectedDeviceId.value = id;
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

function statusTone(status: DeviceSnapshotRecord["status"]) {
  if (status === "online") return "online";
  if (status === "attention") return "attention";
  return "offline";
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

function cloneSnapshot(snapshot: DeviceDashboardSnapshot | null) {
  return snapshot ? (JSON.parse(JSON.stringify(snapshot)) as DeviceDashboardSnapshot) : null;
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

function buildOptimisticTelemetry(device: DeviceSnapshotRecord) {
  const items = device.controls
    .filter((control) => control.kind !== "action")
    .slice(0, 3)
    .map((control) => `${control.label}: ${formatValue(control.value, control.unit)}`);
  return items.join(" | ") || device.telemetry;
}

function rangeInputValue(control: DeviceControlRecord) {
  const draft = Number(readDraftValue(control) ?? 0);
  return Number.isNaN(draft) ? 0 : draft;
}

function applyOptimisticUpdate(
  deviceId: string,
  control: DeviceControlRecord,
  payload: { action?: string; value?: unknown },
) {
  if (!dashboard.value) return;

  const targetDevice = dashboard.value.devices.find((item) => item.id === deviceId);
  if (!targetDevice) return;

  const targetControl = targetDevice.controls.find((item) => item.id === control.id);
  if (!targetControl) return;

  if (targetControl.kind === "toggle") {
    const nextAction = payload.action ?? "toggle";
    if (nextAction === "turn_on" || nextAction === "lock") {
      targetControl.value = "on";
    } else if (nextAction === "turn_off" || nextAction === "unlock") {
      targetControl.value = "off";
    } else {
      targetControl.value = String(targetControl.value).toLowerCase() === "on" ? "off" : "on";
    }
  } else if (payload.value !== undefined) {
    targetControl.value = payload.value;
  }

  targetDevice.telemetry = buildOptimisticTelemetry(targetDevice);
}

async function loadDashboard(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true;
  errorMessage.value = "";
  if (!options.silent) clearFeedback();
  try {
    const response = await fetchDeviceDashboard();
    dashboard.value = response.snapshot;
    syncSelection();
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

async function handleRefresh() {
  syncing.value = true;
  errorMessage.value = "";
  clearFeedback();
  try {
    const response = await refreshDeviceDashboard();
    dashboard.value = response.snapshot;
    syncSelection();
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
  const previousSnapshot = cloneSnapshot(dashboard.value);
  applyOptimisticUpdate(device.id, control, payload);
  try {
    const response = await executeDeviceControl(device.id, control.id, payload);
    dashboard.value = response.snapshot;
    syncSelection();
    showFeedback("success", t("devices.feedback.actionSuccess", { name: control.label }));
  } catch (error) {
    dashboard.value = previousSnapshot;
    syncSelection();
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

watch(visibleDevices, () => syncSelection());

onMounted(() => void loadDashboard());
onBeforeUnmount(() => stopPolling());
</script>

<template>
  <section class="device-studio">
    <div class="device-studio__backdrop"></div>

    <div v-if="errorMessage" class="device-alert">
      {{ errorMessage }}
    </div>

    <div v-if="actionFeedback" class="device-feedback" :class="`device-feedback--${actionFeedback.type}`">
      {{ actionFeedback.message }}
    </div>

    <div v-if="loading" class="device-loading">
      {{ $t("common.loading") }}
    </div>

    <template v-else-if="dashboard">
      <header class="device-hero">
        <div>
          <p class="device-hero__eyebrow">{{ $t("devices.title") }}</p>
          <h1 class="device-hero__title">{{ selectedDevice?.name ?? $t("devices.sections.devices") }}</h1>
          <p class="device-hero__summary">
            {{ selectedDevice?.telemetry ?? $t("devices.allRoomsSummary") }}
          </p>
        </div>
        <button class="device-hero__refresh" :disabled="syncing" @click="handleRefresh">
          {{ syncing ? $t("common.loading") : $t("devices.actions.refresh") }}
        </button>
      </header>

      <div class="device-metrics">
        <article class="metric-card">
          <span>{{ $t("devices.metrics.online") }}</span>
          <strong>{{ metrics.online }}</strong>
        </article>
        <article class="metric-card">
          <span>{{ $t("devices.metrics.attention") }}</span>
          <strong>{{ metrics.attention }}</strong>
        </article>
        <article class="metric-card">
          <span>{{ $t("devices.metrics.offline") }}</span>
          <strong>{{ metrics.offline }}</strong>
        </article>
        <article class="metric-card metric-card--accent">
          <span>{{ $t("devices.metrics.controls") }}</span>
          <strong>{{ metrics.controls }}</strong>
        </article>
      </div>

      <div class="device-filters">
        <button
          v-for="room in rooms"
          :key="room.id"
          class="device-filter"
          :class="{ 'device-filter--active': activeRoomId === room.id }"
          @click="selectRoom(room.id)"
        >
          <span>{{ room.name }}</span>
          <strong>{{ room.count }}</strong>
        </button>
      </div>

      <div class="device-shell">
        <aside class="device-catalog">
          <button
            v-for="device in visibleDevices"
            :key="device.id"
            class="device-card"
            :class="[
              `device-card--${statusTone(device.status)}`,
              { 'device-card--selected': selectedDevice?.id === device.id },
            ]"
            @click="selectDevice(device.id)"
          >
            <div class="device-card__meta">
              <span class="device-card__room">{{ device.room_name || $t("devices.filters.all") }}</span>
              <span class="device-card__status">{{ t(`devices.status.${device.status}`) }}</span>
            </div>
            <h3>{{ device.name }}</h3>
            <p>{{ device.telemetry }}</p>
            <div class="device-card__chips">
              <span>{{ device.category }}</span>
              <span>{{ device.controls.length }} {{ $t("devices.meta.controls") }}</span>
            </div>
          </button>

          <div v-if="visibleDevices.length === 0" class="device-empty">
            {{ $t("devices.empty.devices") }}
          </div>
        </aside>

        <main class="device-panel" v-if="selectedDevice">
          <div class="device-panel__header">
            <div>
              <p class="device-panel__status">
                {{ t(`devices.status.${selectedDevice.status}`) }} · {{ selectedDevice.category }}
              </p>
              <h2>{{ selectedDevice.name }}</h2>
              <p>{{ selectedDevice.note }}</p>
            </div>
            <div class="device-panel__stamp">
              {{ selectedDevice.last_seen ? formatDateTime(selectedDevice.last_seen) : $t("devices.values.empty") }}
            </div>
          </div>

          <div class="device-panel__summary">
            <div>
              <span>{{ $t("devices.detail.telemetry") }}</span>
              <strong>{{ selectedDevice.telemetry }}</strong>
            </div>
            <div>
              <span>{{ $t("devices.detail.capabilities") }}</span>
              <strong>{{ selectedDevice.capabilities.join(" · ") || $t("devices.values.empty") }}</strong>
            </div>
          </div>

          <div v-if="selectedDeviceHighlights.length" class="device-highlight-grid">
            <article v-for="item in selectedDeviceHighlights" :key="item.label" class="device-highlight-card">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>

          <section v-for="group in groupedControls" :key="group.label" class="control-group">
            <button class="control-group__header" type="button" @click="toggleGroup(group.label)">
              <h3>{{ group.label }}</h3>
              <span>
                {{ group.controls.length }} {{ $t("devices.meta.controls") }}
                ·
                {{ isGroupCollapsed(group.label) ? $t("devices.actions.expand") : $t("devices.actions.collapse") }}
              </span>
            </button>

            <div v-if="!isGroupCollapsed(group.label)" class="control-grid">
              <article v-for="control in group.controls" :key="control.id" class="control-card">
                <div class="control-card__top">
                  <div>
                    <p class="control-card__kind">{{ $t(`devices.controlKinds.${control.kind}`) }}</p>
                    <h4>{{ control.label }}</h4>
                  </div>
                  <span class="control-card__value">
                    {{ formatValue(control.value, control.unit) }}
                  </span>
                </div>

                <template v-if="control.kind === 'sensor'">
                  <p class="control-card__hint">{{ $t("devices.hints.readOnly") }}</p>
                </template>

                <template v-else-if="control.kind === 'toggle'">
                  <div class="control-actions">
                    <button
                      v-for="action in controlActions(control)"
                      :key="action.id"
                      class="control-button"
                      :disabled="executingControlId === control.id"
                      @click="runToggle(control, action.id)"
                    >
                      {{ action.label }}
                    </button>
                  </div>
                </template>

                <template v-else-if="control.kind === 'range'">
                  <div class="control-editor">
                    <input
                      type="range"
                      class="control-range"
                      :min="normalizeRangeBounds(control).min"
                      :max="normalizeRangeBounds(control).max"
                      :step="normalizeRangeBounds(control).step"
                      :value="rangeInputValue(control)"
                      @input="handleRangeInput(control.id, $event)"
                    />
                    <div class="control-editor__footer">
                      <span>{{ formatValue(readDraftValue(control), control.unit) }}</span>
                      <button class="control-button control-button--solid" :disabled="executingControlId === control.id" @click="saveValue(control)">
                        {{ $t("devices.actions.apply") }}
                      </button>
                    </div>
                  </div>
                </template>

                <template v-else-if="control.kind === 'enum'">
                  <div class="control-editor">
                    <select
                      class="control-select"
                      :value="String(readDraftValue(control) ?? '')"
                      @change="handleEnumInput(control.id, $event)"
                    >
                      <option v-for="option in control.options" :key="String(option.value)" :value="String(option.value)">
                        {{ displayOptionLabel(option) }}
                      </option>
                    </select>
                    <button class="control-button control-button--solid" :disabled="executingControlId === control.id" @click="saveValue(control)">
                      {{ $t("devices.actions.apply") }}
                    </button>
                  </div>
                </template>

                <template v-else-if="control.kind === 'text'">
                  <div class="control-editor">
                    <input
                      type="text"
                      class="control-input"
                      :value="String(readDraftValue(control) ?? '')"
                      @input="handleTextInput(control.id, $event)"
                    />
                    <button class="control-button control-button--solid" :disabled="executingControlId === control.id" @click="saveValue(control)">
                      {{ $t("devices.actions.apply") }}
                    </button>
                  </div>
                </template>

                <template v-else-if="control.kind === 'action'">
                  <div class="control-actions">
                    <button
                      v-for="action in controlActions(control)"
                      :key="action.id"
                      class="control-button control-button--solid"
                      :disabled="executingControlId === control.id"
                      @click="runAction(control, action.id)"
                    >
                      {{ action.label }}
                    </button>
                  </div>
                </template>
              </article>
            </div>
          </section>
        </main>

        <div v-else class="device-empty device-empty--panel">
          {{ $t("devices.empty.noDevices") }}
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.device-studio {
  position: relative;
  display: grid;
  gap: 20px;
  min-height: calc(100vh - 180px);
}

.device-studio__backdrop {
  position: absolute;
  inset: -24px;
  z-index: 0;
  border-radius: 32px;
  background:
    radial-gradient(circle at top left, rgba(255, 170, 0, 0.22), transparent 28%),
    radial-gradient(circle at top right, rgba(0, 168, 107, 0.14), transparent 26%),
    linear-gradient(135deg, rgba(255, 248, 239, 0.94), rgba(244, 248, 245, 0.96));
  filter: blur(0.5px);
}

.device-alert,
.device-feedback,
.device-loading,
.device-hero,
.device-metrics,
.device-filters,
.device-shell {
  position: relative;
  z-index: 1;
}

.device-alert,
.device-feedback,
.device-loading,
.device-empty {
  padding: 18px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(32, 32, 32, 0.08);
}

.device-feedback--success {
  background: rgba(19, 135, 92, 0.12);
  border-color: rgba(19, 135, 92, 0.18);
  color: #11553f;
}

.device-feedback--error {
  background: rgba(187, 68, 68, 0.12);
  border-color: rgba(187, 68, 68, 0.18);
  color: #842222;
}

.device-feedback--info {
  background: rgba(241, 179, 65, 0.16);
  border-color: rgba(241, 179, 65, 0.22);
  color: #744900;
}

.device-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 24px 28px;
  border-radius: 28px;
  background: rgba(28, 33, 29, 0.9);
  color: #f5f3ea;
  box-shadow: 0 24px 60px rgba(24, 31, 24, 0.16);
}

.device-hero__eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(245, 243, 234, 0.58);
}

.device-hero__title {
  margin: 0;
  font-size: clamp(30px, 4vw, 42px);
  line-height: 1.02;
}

.device-hero__summary {
  max-width: 720px;
  margin: 10px 0 0;
  color: rgba(245, 243, 234, 0.72);
}

.device-hero__refresh,
.control-button {
  border: 0;
  cursor: pointer;
  transition: transform 180ms ease, opacity 180ms ease, background 180ms ease;
}

.device-hero__refresh {
  padding: 12px 18px;
  border-radius: 999px;
  background: #f1b341;
  color: #241a08;
  font-weight: 600;
}

.device-hero__refresh:disabled,
.control-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.device-metrics {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  padding: 18px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(28, 33, 29, 0.08);
  backdrop-filter: blur(14px);
}

.metric-card span {
  display: block;
  color: #6b6e62;
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  font-size: 30px;
  color: #1e231f;
}

.metric-card--accent {
  background: linear-gradient(135deg, rgba(241, 179, 65, 0.18), rgba(12, 139, 101, 0.12));
}

.device-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.device-filter {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(28, 33, 29, 0.08);
  background: rgba(255, 255, 255, 0.78);
  cursor: pointer;
}

.device-filter strong {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(28, 33, 29, 0.08);
  font-size: 12px;
}

.device-filter--active {
  background: #1f3025;
  color: #f5f3ea;
}

.device-shell {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
}

.device-catalog,
.device-panel {
  padding: 18px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(28, 33, 29, 0.08);
  backdrop-filter: blur(18px);
}

.device-catalog {
  display: grid;
  gap: 12px;
  align-content: start;
}

.device-card {
  padding: 16px;
  border-radius: 24px;
  border: 1px solid rgba(28, 33, 29, 0.08);
  background: #fffdfa;
  text-align: left;
  cursor: pointer;
}

.device-card--selected {
  border-color: rgba(241, 179, 65, 0.7);
  box-shadow: 0 14px 28px rgba(241, 179, 65, 0.12);
}

.device-card__meta,
.device-card__chips,
.control-group__header,
.control-card__top,
.control-editor__footer,
.device-panel__summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.device-card__room,
.device-card__status,
.control-card__kind,
.device-panel__status {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6d7264;
}

.device-card h3,
.control-card h4,
.control-group h3,
.device-panel h2 {
  margin: 0;
}

.device-card p,
.device-panel p,
.control-card__hint {
  margin: 8px 0 0;
  color: #5e6257;
}

.device-card__chips {
  margin-top: 12px;
  flex-wrap: wrap;
}

.device-card__chips span,
.device-panel__stamp {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(28, 33, 29, 0.06);
  color: #30352e;
  font-size: 12px;
}

.device-panel {
  display: grid;
  gap: 16px;
}

.device-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.device-panel__summary {
  padding: 16px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(18, 30, 24, 0.94), rgba(33, 57, 41, 0.92));
  color: #f7f3e8;
}

.device-panel__summary span {
  display: block;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(247, 243, 232, 0.58);
}

.device-panel__summary strong {
  display: block;
  margin-top: 6px;
  font-size: 16px;
}

.device-highlight-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.device-highlight-card {
  padding: 14px 16px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 252, 247, 0.96), rgba(250, 244, 231, 0.92));
  border: 1px solid rgba(28, 33, 29, 0.08);
}

.device-highlight-card span {
  display: block;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #787768;
}

.device-highlight-card strong {
  display: block;
  margin-top: 8px;
  font-size: 20px;
  color: #1c221d;
}

.control-group {
  display: grid;
  gap: 12px;
}

.control-group__header {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  align-items: center;
  text-align: left;
}

.control-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.control-card {
  padding: 16px;
  border-radius: 22px;
  background: #fffcf7;
  border: 1px solid rgba(28, 33, 29, 0.08);
  display: grid;
  gap: 14px;
}

.control-card__value {
  color: #1a211d;
  font-weight: 600;
}

.control-actions,
.control-editor {
  display: grid;
  gap: 10px;
}

.control-actions {
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
}

.control-button {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(28, 33, 29, 0.08);
  color: #1d221e;
}

.control-button--solid {
  background: #1f3025;
  color: #f5f3ea;
}

.control-select,
.control-input,
.control-range {
  width: 100%;
}

.control-select,
.control-input {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(28, 33, 29, 0.12);
  background: #ffffff;
}

.control-range {
  accent-color: #0c8b65;
}

.device-empty--panel {
  display: grid;
  place-items: center;
}

@media (max-width: 1100px) {
  .device-metrics,
  .device-highlight-grid,
  .control-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .device-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .device-hero,
  .device-panel__header,
  .device-panel__summary,
  .control-group__header,
  .control-card__top,
  .control-editor__footer {
    grid-template-columns: 1fr;
    display: grid;
  }

  .device-metrics,
  .device-highlight-grid,
  .control-grid {
    grid-template-columns: 1fr;
  }
}
</style>
