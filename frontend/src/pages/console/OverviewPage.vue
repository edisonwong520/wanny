<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import { createConsoleMockData } from "@/data/console";

const { t } = useI18n();

const consoleData = computed(() => createConsoleMockData(t));

const metrics = computed(() => {
  const missions = consoleData.value.missions;
  const approvedCount = missions.filter((mission) => mission.status === "approved").length;

  return [
    { label: "在线设备", value: consoleData.value.devices.length, color: "#07C160", bg: "#E8F8EC" },
    { label: "待处理任务", value: missions.filter((m) => m.status === "pending").length, color: "#E8A223", bg: "#FFF7E6" },
    { label: "异常设备", value: consoleData.value.anomalyCount, color: "#E84343", bg: "#FFE8E8" },
    { label: "主动建议", value: consoleData.value.proactiveCount, color: "#07C160", bg: "#E8F8EC" },
  ];
});

const events = computed(() => consoleData.value.recentEvents.slice(0, 4));
</script>

<template>
  <div class="space-y-5">
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
        <h2 class="text-sm font-medium text-[#333333]">最近动态</h2>
        <RouterLink
          to="/console/manage"
          class="text-xs text-[#07C160] hover:underline"
        >
          查看全部
        </RouterLink>
      </div>

      <div class="space-y-2">
        <RouterLink
          v-for="event in events"
          :key="event.id"
          :to="event.route"
          class="flex items-center justify-between p-4 rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30 hover:shadow-sm"
        >
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-[#333333] truncate">{{ event.title }}</div>
            <div class="text-xs text-[#888888] truncate mt-1">{{ event.body }}</div>
          </div>
          <span class="text-xs text-[#888888] ml-3 flex-shrink-0">{{ event.time }}</span>
        </RouterLink>
      </div>
    </section>
  </div>
</template>