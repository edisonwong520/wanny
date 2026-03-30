<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  createConsoleMockData,
  type DeviceRecord,
  type DeviceStatus,
  type MissionRisk,
  type PolicyDecision,
} from "@/data/console";
import { cn } from "@/lib/utils";

const { t, locale } = useI18n();

const activeRoomId = ref("all");
const selectedDeviceId = ref("");

const consoleData = computed(() => createConsoleMockData(t));
const activeModeId = computed(() => consoleData.value.activeModeId);

function resetView() {
  activeRoomId.value = "all";
  selectedDeviceId.value = consoleData.value.devices[0]?.id ?? "";
}

watch(
  () => locale.value,
  () => {
    resetView();
  },
  { immediate: true },
);

const summaryCards = computed(() => [
  {
    label: t("devices.metrics.online"),
    value: consoleData.value.devices.filter((device) => device.status === "online").length,
  },
  {
    label: t("devices.metrics.attention"),
    value: consoleData.value.devices.filter((device) => device.status !== "online").length,
  },
  {
    label: t("devices.metrics.anomalies"),
    value: consoleData.value.deviceAlerts.length,
  },
  {
    label: t("devices.metrics.rooms"),
    value: consoleData.value.rooms.length,
  },
]);

const roomFilters = computed(() => [
  {
    id: "all",
    label: t("devices.filters.all"),
    count: consoleData.value.devices.length,
  },
  ...consoleData.value.rooms.map((room) => ({
    id: room.id,
    label: room.name,
    count: room.deviceCount,
  })),
]);

const filteredDevices = computed(() => {
  if (activeRoomId.value === "all") {
    return consoleData.value.devices;
  }
  return consoleData.value.devices.filter((device) => device.roomId === activeRoomId.value);
});

watch(
  filteredDevices,
  (items) => {
    if (!items.some((device) => device.id === selectedDeviceId.value)) {
      selectedDeviceId.value = items[0]?.id ?? "";
    }
  },
  { immediate: true },
);

const selectedDevice = computed(
  () =>
    filteredDevices.value.find((device) => device.id === selectedDeviceId.value) ??
    filteredDevices.value[0] ??
    null,
);

const visiblePolicies = computed(() =>
  consoleData.value.policies.filter(
    (policy) =>
      policy.modeId === activeModeId.value &&
      (activeRoomId.value === "all" || policy.roomId === activeRoomId.value),
  ),
);

const visibleAlerts = computed(() =>
  consoleData.value.deviceAlerts.filter(
    (alert) => activeRoomId.value === "all" || alert.roomId === activeRoomId.value,
  ),
);

function selectRoom(id: string) {
  activeRoomId.value = id;
}

function selectDevice(id: string) {
  selectedDeviceId.value = id;
}

function deviceStatusLabel(status: DeviceStatus) {
  return t(`devices.status.${status}`);
}

function deviceStatusClasses(status: DeviceStatus) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    status === "online" && "border-brand/10 bg-glow text-brand",
    status === "attention" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    status === "offline" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

function policyDecisionLabel(decision: PolicyDecision) {
  return t(`devices.decisions.${decision}`);
}

function policyDecisionClasses(decision: PolicyDecision) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    decision === "always" && "border-brand/10 bg-glow text-brand",
    decision === "ask" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    decision === "never" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

function severityLabel(severity: MissionRisk) {
  return t(`devices.severity.${severity}`);
}

function severityClasses(severity: MissionRisk) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    severity === "low" && "border-brand/10 bg-glow text-brand",
    severity === "medium" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    severity === "high" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

function deviceCardClasses(device: DeviceRecord) {
  return cn(
    "rounded-[28px] border p-5 text-left transition",
    selectedDeviceId.value === device.id
      ? "border-brand/18 bg-glow/65 shadow-[0_16px_36px_rgba(7,193,96,0.08)]"
      : "border-black/[0.05] bg-white hover:border-brand/10 hover:bg-[#fcfffd]",
  );
}
</script>

<template>
  <div class="space-y-5">
    <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="item in summaryCards"
        :key="item.label"
        class="rounded-[26px] border border-black/[0.05] bg-white p-5"
      >
        <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ item.label }}</div>
        <div class="mt-4 text-3xl font-semibold text-ink">{{ item.value }}</div>
      </article>
    </section>

    <section class="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <div class="space-y-4">
        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="flex flex-wrap gap-3">
            <button
              v-for="room in roomFilters"
              :key="room.id"
              :class="
                cn(
                  'rounded-full border px-4 py-2 text-sm font-semibold transition',
                  activeRoomId === room.id
                    ? 'border-2 border-[#07C160] bg-[#F1FFF7] text-[#067A3C] shadow-[0_10px_24px_rgba(7,193,96,0.10)]'
                    : 'border border-black/[0.06] bg-white text-muted hover:border-[#8ED9B0] hover:text-ink',
                )
              "
              type="button"
              @click="selectRoom(room.id)"
            >
              {{ room.label }}
              <span class="ml-2 text-xs opacity-70">{{ room.count }}</span>
            </button>
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("devices.sections.devices") }}</div>

          <div class="mt-4 grid gap-4 sm:grid-cols-2">
            <button
              v-for="device in filteredDevices"
              :key="device.id"
              :class="deviceCardClasses(device)"
              type="button"
              @click="selectDevice(device.id)"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <h2 class="text-lg font-semibold text-ink">{{ device.name }}</h2>
                  <p class="mt-2 text-sm text-muted">{{ device.roomName }} / {{ device.category }}</p>
                </div>
                <span :class="deviceStatusClasses(device.status)">{{ deviceStatusLabel(device.status) }}</span>
              </div>

              <div class="mt-4 text-sm leading-7 text-[#4a4a4a]">{{ device.note }}</div>
              <div class="mt-4 rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-3 text-sm font-medium text-ink">
                {{ device.telemetry }}
              </div>
            </button>
          </div>

          <div
            v-if="filteredDevices.length === 0"
            class="mt-4 rounded-[24px] border border-dashed border-black/[0.08] bg-white/70 px-5 py-8 text-sm text-muted"
          >
            {{ t("devices.empty.devices") }}
          </div>
        </section>

        <section v-if="selectedDevice" class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="flex flex-wrap items-center gap-2">
            <span :class="deviceStatusClasses(selectedDevice.status)">
              {{ deviceStatusLabel(selectedDevice.status) }}
            </span>
          </div>

          <h2 class="mt-4 text-2xl font-semibold text-ink">{{ selectedDevice.name }}</h2>
          <p class="mt-3 text-sm leading-7 text-[#4a4a4a]">{{ selectedDevice.note }}</p>

          <div class="mt-5 grid gap-3 sm:grid-cols-2">
            <div class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4">
              <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("devices.detail.room") }}</div>
              <div class="mt-3 text-sm font-medium text-ink">{{ selectedDevice.roomName }}</div>
            </div>
            <div class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4">
              <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("devices.detail.category") }}</div>
              <div class="mt-3 text-sm font-medium text-ink">{{ selectedDevice.category }}</div>
            </div>
            <div class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4">
              <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("devices.detail.lastSeen") }}</div>
              <div class="mt-3 text-sm font-medium text-ink">{{ selectedDevice.lastSeen }}</div>
            </div>
            <div class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4">
              <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("devices.detail.telemetry") }}</div>
              <div class="mt-3 text-sm font-medium text-ink">{{ selectedDevice.telemetry }}</div>
            </div>
          </div>

          <section class="mt-5 rounded-[24px] border border-black/[0.05] bg-[#fcfcfc] p-4">
            <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("devices.detail.note") }}</div>
            <div class="mt-3 text-sm leading-7 text-[#4a4a4a]">{{ selectedDevice.note }}</div>
          </section>

          <section class="mt-5">
            <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("devices.detail.capabilities") }}</div>
            <div class="mt-3 flex flex-wrap gap-3">
              <div
                v-for="capability in selectedDevice.capabilities"
                :key="capability"
                class="rounded-full border border-black/[0.05] bg-[#fcfcfc] px-4 py-2 text-sm text-ink"
              >
                {{ capability }}
              </div>
            </div>
          </section>
        </section>
      </div>

      <aside class="space-y-4">
        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("devices.sections.policies") }}</div>
          <div class="mt-4 space-y-3">
            <div
              v-for="policy in visiblePolicies"
              :key="policy.id"
              class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <div class="font-medium text-ink">{{ policy.target }}</div>
                  <div class="mt-2 text-sm leading-7 text-[#4a4a4a]">{{ policy.condition }}</div>
                </div>
                <span :class="policyDecisionClasses(policy.decision)">
                  {{ policyDecisionLabel(policy.decision) }}
                </span>
              </div>
              <div class="mt-3 text-sm leading-7 text-muted">{{ policy.rationale }}</div>
            </div>
          </div>

          <div
            v-if="visiblePolicies.length === 0"
            class="mt-4 rounded-[22px] border border-dashed border-black/[0.08] bg-white/70 px-4 py-6 text-sm text-muted"
          >
            {{ t("devices.empty.policies") }}
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("devices.sections.anomalies") }}</div>
          <div class="mt-4 space-y-3">
            <div
              v-for="alert in visibleAlerts"
              :key="alert.id"
              class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <div class="font-medium text-ink">{{ alert.title }}</div>
                  <div class="mt-2 text-sm leading-7 text-[#4a4a4a]">{{ alert.body }}</div>
                </div>
                <span :class="severityClasses(alert.severity)">{{ severityLabel(alert.severity) }}</span>
              </div>

              <div class="mt-3 text-xs uppercase tracking-[0.22em] text-muted">
                {{ t("devices.anomaly.recommendation") }}
              </div>
              <div class="mt-2 text-sm leading-7 text-[#4a4a4a]">{{ alert.recommendation }}</div>
            </div>
          </div>

          <div
            v-if="visibleAlerts.length === 0"
            class="mt-4 rounded-[22px] border border-dashed border-black/[0.08] bg-white/70 px-4 py-6 text-sm text-muted"
          >
            {{ t("devices.empty.anomalies") }}
          </div>
        </section>
      </aside>
    </section>
  </div>
</template>
