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

  return [
    {
      label: t("overview.metrics.components"),
      value: t("overview.values.components"),
    },
    {
      label: t("overview.metrics.tasks"),
      value: t("overview.values.tasks", { approved: approvedCount }),
    },
    {
      label: t("overview.metrics.suggestions"),
      value: String(consoleData.value.proactiveCount),
    },
    {
      label: t("overview.metrics.anomalies"),
      value: String(consoleData.value.anomalyCount),
    },
    {
      label: t("overview.metrics.devices"),
      value: String(consoleData.value.devices.length),
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
      </article>
    </section>

    <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-2xl font-semibold text-ink">{{ t("overview.events.title") }}</h2>
        <RouterLink
          class="inline-flex h-10 items-center justify-center rounded-full border border-[#9AD5B1] bg-[#F1FFF7] px-4 text-sm font-semibold text-[#067A3C] transition hover:-translate-y-0.5 hover:border-[#07C160] hover:bg-[#E9FAF0]"
          to="/console/manage"
        >
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
