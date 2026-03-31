<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  type DeviceDashboardSnapshot,
  type DeviceSnapshotRecord,
  fetchDeviceDashboard,
} from "@/lib/devices";
import { formatDateTime } from "@/lib/utils";

const { t } = useI18n();

const dashboard = ref<DeviceDashboardSnapshot | null>(null);
const activeRoomId = ref("all");
const loading = ref(true);
const errorMessage = ref("");
let pollTimer: number | null = null;

const rooms = computed(() => {
  const r = dashboard.value?.rooms ?? [];
  const total = dashboard.value?.devices.length ?? 0;
  return [
    { id: "all", name: "全部", count: total },
    ...r.map((room) => ({ id: room.id, name: room.name, count: room.device_count })),
  ];
});

const visibleDevices = computed<DeviceSnapshotRecord[]>(() => {
  const devices = dashboard.value?.devices ?? [];
  if (activeRoomId.value === "all") return devices;
  return devices.filter((d) => d.room_id === activeRoomId.value);
});

const visibleOfflineDevices = computed(() => {
  return visibleDevices.value.filter((d) => d.status === "offline");
});

function selectRoom(id: string) {
  activeRoomId.value = id;
}

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

function statusStyle(status: DeviceSnapshotRecord["status"]) {
  if (status === "online") return { bg: "#E8F8EC", text: "#07C160" };
  if (status === "attention") return { bg: "#FFF7E6", text: "#E8A223" };
  return { bg: "#FFE8E8", text: "#E84343" };
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

onMounted(() => void loadDashboard());
onBeforeUnmount(() => stopPolling());
</script>

<template>
  <div class="space-y-4">
    <div v-if="errorMessage" class="px-4 py-3 rounded-2xl bg-[#FFE8E8] text-sm text-[#E84343]">
      {{ errorMessage }}
    </div>

    <div v-if="loading" class="py-8 text-center text-sm text-[#888888]">
      加载中...
    </div>

    <div v-else-if="dashboard">
      <div class="flex gap-2 mb-4">
        <button
          v-for="room in rooms"
          :key="room.id"
          class="px-4 py-2 rounded-full text-sm transition-all duration-200"
          :class="activeRoomId === room.id
            ? 'bg-[#07C160] text-white shadow-sm'
            : 'bg-[#F7F7F7] text-[#888888] hover:bg-[#EDEDED]'"
          @click="selectRoom(room.id)"
        >
          {{ room.name }} ({{ room.count }})
        </button>
      </div>

      <!-- 设备网格 -->
      <div class="grid gap-3 md:grid-cols-2">
        <div
          v-for="device in visibleDevices"
          :key="device.id"
          class="p-4 rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/20 hover:shadow-sm"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-medium text-[#333333]">{{ device.name }}</span>
            <span
              class="px-2.5 py-1 rounded-full text-xs font-medium"
              :style="{ background: statusStyle(device.status).bg, color: statusStyle(device.status).text }"
            >
              {{ t(`devices.status.${device.status}`) }}
            </span>
          </div>
          <div class="mt-2 text-sm text-[#333333]">状态: {{ device.telemetry }}</div>
        </div>
      </div>

      <div v-if="visibleDevices.length === 0" class="py-8 text-center text-sm text-[#888888]">
        暂无设备
      </div>
    </div>
  </div>
</template>
