<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  type DeviceAnomalyRecord,
  type DeviceAutomationRuleRecord,
  type DeviceDashboardSnapshot,
  type DeviceRoomRecord,
  type DeviceSnapshotRecord,
  fetchDeviceDashboard,
} from "@/lib/devices";
import { cn } from "@/lib/utils";

const { t } = useI18n();

const dashboard = ref<DeviceDashboardSnapshot | null>(null);
const activeRoomId = ref("all");
const loading = ref(true);
const errorMessage = ref("");
let pollTimer: number | null = null;

const roomTabs = computed(() => {
  const rooms = dashboard.value?.rooms ?? [];
  const totalDevices = dashboard.value?.devices.length ?? 0;

  return [
    {
      id: "all",
      label: t("devices.filters.all"),
      count: totalDevices,
      anomalyCount: dashboard.value?.anomalies.length ?? 0,
    },
    ...rooms.map((room) => ({
      id: room.id,
      label: room.name,
      count: room.device_count,
      anomalyCount: room.anomaly_count,
    })),
  ];
});

const activeRoom = computed<DeviceRoomRecord | null>(() => {
  if (!dashboard.value || activeRoomId.value === "all") {
    return null;
  }
  return dashboard.value.rooms.find((room) => room.id === activeRoomId.value) ?? null;
});

const visibleDevices = computed<DeviceSnapshotRecord[]>(() => {
  const devices = dashboard.value?.devices ?? [];
  if (activeRoomId.value === "all") {
    return devices;
  }
  return devices.filter((device) => device.room_id === activeRoomId.value);
});

const visibleAnomalies = computed<DeviceAnomalyRecord[]>(() => {
  const anomalies = dashboard.value?.anomalies ?? [];
  if (activeRoomId.value === "all") {
    return anomalies;
  }
  return anomalies.filter((anomaly) => anomaly.room_id === activeRoomId.value);
});

const visibleRules = computed<DeviceAutomationRuleRecord[]>(() => {
  const rules = dashboard.value?.rules ?? [];
  if (activeRoomId.value === "all") {
    return rules;
  }
  return rules.filter((rule) => rule.room_id === activeRoomId.value);
});

const syncNotice = computed(() => {
  if (!dashboard.value) {
    return "";
  }
  if (dashboard.value.pending_refresh && !dashboard.value.has_snapshot) {
    return t("devices.sync.initializing");
  }
  if (dashboard.value.pending_refresh) {
    return t("devices.sync.pending");
  }
  if (!dashboard.value.has_snapshot) {
    return t("devices.sync.empty");
  }
  return "";
});

const emptyStateMessage = computed(() => {
  if (!dashboard.value?.has_snapshot) {
    return dashboard.value?.pending_refresh
      ? t("devices.sync.initializing")
      : t("devices.sync.empty");
  }
  return "";
});

function selectRoom(roomId: string) {
  activeRoomId.value = roomId;
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function schedulePolling(delay = 3000) {
  stopPolling();
  pollTimer = window.setTimeout(() => {
    void loadDashboard({ silent: true });
  }, delay);
}

function deviceStatusLabel(status: DeviceSnapshotRecord["status"]) {
  return t(`devices.status.${status}`);
}

function deviceStatusClasses(status: DeviceSnapshotRecord["status"]) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    status === "online" && "border-brand/10 bg-glow text-brand",
    status === "attention" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    status === "offline" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

function anomalySeverityLabel(severity: DeviceAnomalyRecord["severity"]) {
  return t(`devices.severity.${severity}`);
}

function anomalySeverityClasses(severity: DeviceAnomalyRecord["severity"]) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    severity === "low" && "border-brand/10 bg-glow text-brand",
    severity === "medium" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    severity === "high" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

function ruleDecisionLabel(decision: DeviceAutomationRuleRecord["decision"]) {
  return t(`devices.decisions.${decision}`);
}

function ruleDecisionClasses(decision: DeviceAutomationRuleRecord["decision"]) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    decision === "always" && "border-brand/10 bg-glow text-brand",
    decision === "ask" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    decision === "never" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

async function loadDashboard(options: { silent?: boolean } = {}) {
  if (!options.silent) {
    loading.value = true;
  }
  errorMessage.value = "";

  try {
    const response = await fetchDeviceDashboard();
    dashboard.value = response.snapshot;
    if (
      activeRoomId.value !== "all" &&
      !response.snapshot.rooms.some((room) => room.id === activeRoomId.value)
    ) {
      activeRoomId.value = "all";
    }
    if (response.snapshot.pending_refresh) {
      schedulePolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    stopPolling();
    errorMessage.value = error instanceof Error ? error.message : t("devices.errors.load");
  } finally {
    if (!options.silent) {
      loading.value = false;
    }
  }
}

onMounted(() => {
  void loadDashboard();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<template>
  <div class="space-y-5">
    <section
      v-if="errorMessage"
      class="rounded-[24px] border border-[#F0C8C8] bg-[#FFF4F4] px-4 py-4 text-sm leading-7 text-[#A44545]"
    >
      {{ errorMessage }}
    </section>

    <section
      v-if="loading"
      class="rounded-[28px] border border-black/[0.05] bg-white p-8 text-sm text-muted"
    >
      {{ t("devices.loading") }}
    </section>

    <template v-else-if="dashboard">
      <section
        v-if="syncNotice"
        class="rounded-[24px] border border-[#D4EFD8] bg-[#F6FFF8] px-4 py-4 text-sm leading-7 text-[#2E7D4F]"
      >
        {{ syncNotice }}
      </section>

      <section
        v-if="dashboard.last_error"
        class="rounded-[24px] border border-[#F0C8C8] bg-[#FFF4F4] px-4 py-4 text-sm leading-7 text-[#A44545]"
      >
        {{ t("devices.sync.error") }} {{ dashboard.last_error }}
      </section>

      <section class="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="grid gap-5 lg:grid-cols-[180px_minmax(0,1fr)]">
            <div class="space-y-2">
              <button
                v-for="room in roomTabs"
                :key="room.id"
                :class="
                  cn(
                    'w-full rounded-[22px] border px-4 py-4 text-left transition',
                    activeRoomId === room.id
                      ? 'border-[#07C160] bg-[#F1FFF7]'
                      : 'border-black/[0.06] bg-[#fcfcfc] hover:border-brand/20 hover:bg-white',
                  )
                "
                type="button"
                @click="selectRoom(room.id)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="text-sm font-semibold text-ink">{{ room.label }}</div>
                    <div class="mt-1 text-xs text-muted">
                      {{ room.count }} {{ t("devices.meta.devices") }}
                    </div>
                  </div>
                  <span
                    v-if="room.anomalyCount"
                    class="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-[#FFF1F1] px-2 text-xs font-semibold text-[#B64B4B]"
                  >
                    {{ room.anomalyCount }}
                  </span>
                </div>
              </button>
            </div>

            <div class="space-y-4">
              <div class="rounded-[24px] border border-black/[0.05] bg-[#fcfcfc] px-5 py-4">
                <div class="text-xs uppercase tracking-[0.22em] text-muted">
                  {{ t("devices.sections.rooms") }}
                </div>
                <div class="mt-3 text-2xl font-semibold text-ink">
                  {{ activeRoom?.name ?? t("devices.filters.all") }}
                </div>
                <div v-if="activeRoom?.climate" class="mt-2 text-sm font-medium text-[#6C665B]">
                  {{ activeRoom.climate }}
                </div>
                <p class="mt-3 text-sm leading-7 text-[#4a4a4a]">
                  {{ activeRoom?.summary ?? t("devices.allRoomsSummary") }}
                </p>
              </div>

              <div class="grid gap-4 md:grid-cols-2">
                <article
                  v-for="device in visibleDevices"
                  :key="device.id"
                  class="rounded-[24px] border border-black/[0.05] bg-[#fcfcfc] p-5"
                >
                  <div class="flex items-start justify-between gap-4">
                    <div>
                      <div class="text-lg font-semibold text-ink">{{ device.name }}</div>
                      <div class="mt-2 text-sm text-muted">{{ device.category }}</div>
                    </div>
                    <span :class="deviceStatusClasses(device.status)">
                      {{ deviceStatusLabel(device.status) }}
                    </span>
                  </div>

                  <div class="mt-4 rounded-[20px] border border-black/[0.05] bg-white px-4 py-3 text-sm font-medium text-ink">
                    {{ device.telemetry }}
                  </div>

                  <p class="mt-4 text-sm leading-7 text-[#4a4a4a]">{{ device.note }}</p>
                </article>
              </div>

              <div
                v-if="visibleDevices.length === 0"
                class="rounded-[24px] border border-dashed border-black/[0.08] px-5 py-8 text-sm text-muted"
              >
                {{ emptyStateMessage || t("devices.empty.devices") }}
              </div>
            </div>
          </div>
        </section>

        <aside class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">
            {{ t("devices.sections.anomalies") }}
          </div>

          <div class="mt-4 space-y-3">
            <article
              v-for="anomaly in visibleAnomalies"
              :key="anomaly.id"
              class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <div class="font-medium text-ink">{{ anomaly.title }}</div>
                  <div class="mt-2 text-sm leading-7 text-[#4a4a4a]">{{ anomaly.body }}</div>
                </div>
                <span :class="anomalySeverityClasses(anomaly.severity)">
                  {{ anomalySeverityLabel(anomaly.severity) }}
                </span>
              </div>

              <div class="mt-3 text-xs uppercase tracking-[0.22em] text-muted">
                {{ t("devices.anomaly.recommendation") }}
              </div>
              <div class="mt-2 text-sm leading-7 text-[#4a4a4a]">
                {{ anomaly.recommendation }}
              </div>
            </article>
          </div>

          <div
            v-if="visibleAnomalies.length === 0"
            class="mt-4 rounded-[22px] border border-dashed border-black/[0.08] px-4 py-6 text-sm text-muted"
          >
            {{ emptyStateMessage || t("devices.empty.anomalies") }}
          </div>
        </aside>
      </section>

      <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
        <div class="text-xs uppercase tracking-[0.24em] text-muted">
          {{ t("devices.sections.policies") }}
        </div>

        <div class="mt-4 grid gap-4 lg:grid-cols-2">
          <article
            v-for="rule in visibleRules"
            :key="rule.id"
            class="rounded-[24px] border border-black/[0.05] bg-[#fcfcfc] p-5"
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="rounded-full border border-black/[0.06] bg-white px-3 py-1 text-xs font-semibold text-ink">
                {{ rule.mode_label }}
              </span>
              <span :class="ruleDecisionClasses(rule.decision)">
                {{ ruleDecisionLabel(rule.decision) }}
              </span>
            </div>

            <div class="mt-4 text-lg font-semibold text-ink">{{ rule.target }}</div>
            <div class="mt-3 text-sm leading-7 text-[#4a4a4a]">{{ rule.condition }}</div>
            <div class="mt-4 rounded-[20px] border border-black/[0.05] bg-white px-4 py-4 text-sm leading-7 text-muted">
              {{ rule.rationale }}
            </div>
          </article>
        </div>

        <div
          v-if="visibleRules.length === 0"
          class="mt-4 rounded-[22px] border border-dashed border-black/[0.08] px-4 py-6 text-sm text-muted"
        >
          {{ emptyStateMessage || t("devices.empty.policies") }}
        </div>
      </section>
    </template>
  </div>
</template>
