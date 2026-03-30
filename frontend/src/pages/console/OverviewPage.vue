<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import { createConsoleMockData } from "@/data/console";

const { t } = useI18n();

const consoleData = computed(() => createConsoleMockData(t));

const metricCards = computed(() => {
  const missions = consoleData.value.missions;
  const approvedCount = missions.filter((mission) => mission.status === "approved").length;
  const failedCount = missions.filter((mission) => mission.status === "failed").length;
  const pendingCount = missions.filter((mission) => mission.status === "pending").length;

  return [
    {
      label: t("overview.metrics.components"),
      value: t("overview.values.components"),
      note: t("overview.notes.components"),
    },
    {
      label: t("overview.metrics.tasks"),
      value: String(approvedCount),
      note: t("overview.notes.tasks", { pending: pendingCount, failed: failedCount }),
    },
    {
      label: t("overview.metrics.suggestions"),
      value: String(consoleData.value.proactiveCount),
      note: t("overview.notes.suggestions"),
    },
    {
      label: t("overview.metrics.anomalies"),
      value: String(consoleData.value.anomalyCount),
      note: t("overview.notes.anomalies"),
    },
    {
      label: t("overview.metrics.devices"),
      value: String(consoleData.value.devices.length),
      note: t("overview.notes.devices", { rooms: consoleData.value.rooms.length }),
    },
  ];
});

const recentEvents = computed(() => consoleData.value.recentEvents);
</script>

<template>
  <div class="space-y-5">
    <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <article
        v-for="item in metricCards"
        :key="item.label"
        class="rounded-[26px] border border-black/[0.05] bg-white p-5"
      >
        <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ item.label }}</div>
        <div class="mt-4 text-3xl font-semibold text-ink">{{ item.value }}</div>
        <div class="mt-2 text-sm leading-6 text-muted">{{ item.note }}</div>
      </article>
    </section>

    <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-2xl font-semibold text-ink">{{ t("overview.events.title") }}</h2>
        <RouterLink class="text-sm font-medium text-brand transition hover:text-[#059651]" to="/console/manage">
          {{ t("overview.events.link") }}
        </RouterLink>
      </div>

      <div class="mt-5 space-y-3">
        <RouterLink
          v-for="event in recentEvents"
          :key="event.id"
          :to="event.route"
          class="block rounded-[24px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#4a4a4a] transition hover:border-brand/10 hover:bg-glow"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="font-medium text-ink">{{ event.title }}</div>
              <div class="mt-2 text-sm leading-7 text-[#4a4a4a]">{{ event.body }}</div>
            </div>
            <div class="rounded-full border border-brand/10 bg-glow px-3 py-1 text-xs font-semibold text-brand">
              {{ event.time }}
            </div>
          </div>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
