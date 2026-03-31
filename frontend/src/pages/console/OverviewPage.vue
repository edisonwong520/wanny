<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import { fetchDeviceDashboard, type DeviceDashboardSnapshot } from "@/lib/devices";
import { formatDateTime } from "@/lib/utils";

const snapshot = ref<DeviceDashboardSnapshot | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const { t } = useI18n();

onMounted(async () => {
  try {
    const response = await fetchDeviceDashboard();
    snapshot.value = response.snapshot;
  } catch (e) {
    error.value = e instanceof Error ? e.message : t("common.error");
  } finally {
    loading.value = false;
  }
});

const metrics = computed(() => {
  const onlineLabel = t("overview.metrics.online");
  const offlineLabel = t("overview.metrics.offline");

  if (!snapshot.value) {
    return [
      { label: onlineLabel, value: 0, color: "#07C160", bg: "#E8F8EC" },
      { label: offlineLabel, value: 0, color: "#888888", bg: "#F7F7F7" },
    ];
  }

  const devices = snapshot.value.devices;
  const onlineCount = devices.filter((d) => d.status === "online").length;
  const offlineCount = devices.filter((d) => d.status === "offline").length;

  return [
    { label: onlineLabel, value: onlineCount, color: "#07C160", bg: "#E8F8EC" },
    { label: offlineLabel, value: offlineCount, color: "#888888", bg: "#F7F7F7" },
  ];
});

const recentEvents = computed(() => {
  if (!snapshot.value || !snapshot.value.has_snapshot) {
    return [];
  }

  // 从离线设备生成最近动态事件（如果没有异常可用）
  const offlineDevices = snapshot.value.devices.filter((d) => d.status === "offline");
  const offlineEvents = offlineDevices.slice(0, 4).map((device) => ({
    id: `offline-${device.id}`,
    title: t("overview.events.offline", { name: device.name }),
    body: `${t("common.status")}: ${device.telemetry}`,
    time: formatDateTime(device.last_seen || new Date().toISOString()),
    route: "/console/devices",
  }));

  return offlineEvents;
});

const hasDevices = computed(() => {
  return snapshot.value && snapshot.value.devices.length > 0;
});

const hasAuth = computed(() => {
  return snapshot.value && snapshot.value.source !== "none";
});
</script>

<template>
  <div class="space-y-5">
    <!-- 加载状态 -->
    <div v-if="loading" class="text-center py-10 text-[#888888]">{{ $t("common.loading") }}</div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="text-center py-10 text-[#E84343]">{{ error }}</div>

    <!-- 无授权状态 -->
    <div v-else-if="!hasAuth" class="text-center py-10">
      <div class="text-[#888888] mb-4">{{ $t("overview.empty.auth") }}</div>
      <RouterLink
        to="/console/manage"
        class="inline-block px-4 py-2 bg-[#07C160] text-white rounded-lg hover:bg-[#06AD56] transition-colors"
      >
        {{ $t("overview.actions.authorize") }}
      </RouterLink>
    </div>

    <!-- 正常状态 -->
    <template v-else>
      <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div
          v-for="metric in metrics"
          :key="metric.label"
          class="p-4 rounded-2xl transition-all duration-200 hover:-translate-y-1 hover:shadow-md"
          :style="{ background: metric.bg }"
        >
          <div class="text-sm text-[#888888]">{{ metric.label }}</div>
          <div class="mt-2 text-2xl font-semibold" :style="{ color: metric.color }">
            {{ metric.value }}
          </div>
        </div>
      </section>

      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-medium text-[#333333]">{{ $t("overview.sections.events") }}</h2>
          <RouterLink
            to="/console/devices"
            class="text-xs text-[#07C160] hover:underline"
          >
            {{ $t("overview.sections.viewAll") }}
          </RouterLink>
        </div>

        <!-- 无设备时 -->
        <div v-if="!hasDevices" class="text-center py-8 text-[#888888]">
          {{ $t("overview.empty.sync") }}
        </div>

        <!-- 有设备时 -->
        <div v-else class="space-y-2">
          <RouterLink
            v-for="event in recentEvents"
            :key="event.id"
            :to="event.route"
            class="flex items-center justify-between p-4 rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30 hover:shadow-sm"
          >
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-[#333333] truncate">{{ event.title }}</div>
                </div>
            <span class="text-xs text-[#888888] ml-3 flex-shrink-0">{{ event.time }}</span>
          </RouterLink>

          <!-- 无异常时显示最近设备 -->
          <div v-if="recentEvents.length === 0" class="text-center py-4 text-[#888888]">
            {{ $t("overview.empty.noEvents") }}
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
