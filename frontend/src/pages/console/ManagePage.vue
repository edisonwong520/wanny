<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import { createConsoleMockData } from "@/data/console";

const { t } = useI18n();

const consoleData = computed(() => createConsoleMockData(t));

const pendingRiskCount = computed(
  () =>
    consoleData.value.missions.filter(
      (mission) => mission.status === "pending" && mission.risk !== "low",
    ).length,
);

const manageMetrics = computed(() => [
  {
    label: t("manage.metrics.preferences"),
    value: "12",
  },
  {
    label: t("manage.metrics.suggestions"),
    value: String(consoleData.value.proactiveCount),
  },
  {
    label: t("manage.metrics.risky"),
    value: String(pendingRiskCount.value),
  },
  {
    label: t("manage.metrics.blocks"),
    value: "1",
  },
]);

const memoryItems = computed(() => [
  t("manage.memory.items.a"),
  t("manage.memory.items.b"),
  t("manage.memory.items.c"),
]);

const safetyItems = computed(() => [
  t("manage.safety.items.a"),
  t("manage.safety.items.b"),
  t("manage.safety.items.c"),
]);

const relatedEvents = computed(() => consoleData.value.recentEvents.slice(2));
</script>

<template>
  <div class="space-y-5">
    <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="item in manageMetrics"
        :key="item.label"
        class="rounded-[26px] border border-black/[0.05] bg-white p-5"
      >
        <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ item.label }}</div>
        <div class="mt-4 text-3xl font-semibold text-ink">{{ item.value }}</div>
      </article>
    </section>

    <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
      <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
        <h2 class="text-2xl font-semibold text-ink">{{ t("manage.memory.title") }}</h2>

        <div class="mt-5 space-y-3">
          <div
            v-for="item in memoryItems"
            :key="item"
            class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#4a4a4a]"
          >
            {{ item }}
          </div>
        </div>
      </section>

      <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
        <h2 class="text-2xl font-semibold text-ink">{{ t("manage.safety.title") }}</h2>

        <div class="mt-5 space-y-3">
          <div
            v-for="item in safetyItems"
            :key="item"
            class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#4a4a4a]"
          >
            {{ item }}
          </div>
        </div>
      </section>
    </section>

    <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
      <h2 class="text-2xl font-semibold text-ink">{{ t("manage.events.title") }}</h2>

      <div class="mt-5 space-y-3">
        <div
          v-for="event in relatedEvents"
          :key="event.id"
          class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4"
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
        </div>
      </div>
    </section>
  </div>
</template>
