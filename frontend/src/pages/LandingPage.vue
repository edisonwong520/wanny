<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import AppHeader from "@/components/AppHeader.vue";

const { t } = useI18n();

const capabilityCards = computed(() => [
  {
    kicker: "01",
    title: t("landing.capabilityA.title"),
    body: t("landing.capabilityA.body"),
  },
  {
    kicker: "02",
    title: t("landing.capabilityB.title"),
    body: t("landing.capabilityB.body"),
  },
  {
    kicker: "03",
    title: t("landing.capabilityC.title"),
    body: t("landing.capabilityC.body"),
  },
]);

const blueprintCards = computed(() => [
  {
    title: t("landing.blueprintA.title"),
    body: t("landing.blueprintA.body"),
  },
  {
    title: t("landing.blueprintB.title"),
    body: t("landing.blueprintB.body"),
  },
  {
    title: t("landing.blueprintC.title"),
    body: t("landing.blueprintC.body"),
  },
]);
</script>

<template>
  <div class="ambient-shell min-h-screen bg-canvas px-4 pb-14 pt-4 sm:px-6 lg:px-10">
    <AppHeader />

    <main class="mx-auto flex max-w-7xl flex-col gap-10">
      <section class="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div class="glass-panel overflow-hidden rounded-[34px] p-6 sm:p-8 lg:p-10">
          <div class="mb-4 inline-flex rounded-full border border-brand/10 bg-glow px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-brand">
            {{ t("landing.eyebrow") }}
          </div>

          <div class="space-y-6">
            <h1 class="max-w-4xl font-display text-4xl font-bold leading-tight text-ink sm:text-5xl lg:text-6xl">
              {{ t("landing.titleLead") }}
              <span class="bg-gradient-to-r from-brand via-brand to-[#4FD387] bg-clip-text text-transparent">
                {{ t("landing.titleAccent") }}
              </span>
            </h1>

            <p class="max-w-2xl text-base leading-8 text-[#4a4a4a] sm:text-lg">
              {{ t("landing.summary") }}
            </p>

            <div class="flex flex-wrap gap-3">
              <span class="rounded-full border border-black/[0.05] bg-white px-4 py-2 text-sm text-ink">
                {{ t("landing.chips.safety") }}
              </span>
              <span class="rounded-full border border-black/[0.05] bg-white px-4 py-2 text-sm text-ink">
                {{ t("landing.chips.memory") }}
              </span>
              <span class="rounded-full border border-black/[0.05] bg-white px-4 py-2 text-sm text-ink">
                {{ t("landing.chips.shell") }}
              </span>
            </div>

            <div class="flex flex-col gap-3 sm:flex-row">
              <RouterLink
                class="inline-flex h-12 items-center justify-center rounded-full border border-brand bg-brand px-6 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:shadow-[0_16px_32px_rgba(7,193,96,0.18)]"
                to="/console"
              >
                {{ t("landing.primary") }}
              </RouterLink>

              <a
                class="inline-flex h-12 items-center justify-center rounded-full border border-black/[0.06] bg-white px-6 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:bg-[#fcfcfc]"
                href="#blueprint"
              >
                {{ t("landing.secondary") }}
              </a>
            </div>
          </div>
        </div>

        <aside class="glass-panel soft-grid rounded-[34px] p-6 sm:p-8">
          <div class="mb-6 flex items-center justify-between">
            <div>
              <p class="text-xs uppercase tracking-[0.28em] text-muted">
                {{ t("landing.preview.title") }}
              </p>
              <h2 class="mt-2 text-2xl font-semibold text-ink">Jarvis Runtime</h2>
            </div>
            <div class="rounded-full border border-brand/10 bg-glow px-3 py-1 text-xs font-medium text-brand">
              ACTIVE
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-3">
            <div class="rounded-3xl border border-black/[0.05] bg-white p-4">
              <p class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("landing.statA.label") }}</p>
              <p class="mt-3 text-lg font-semibold text-ink">{{ t("landing.statA.value") }}</p>
            </div>
            <div class="rounded-3xl border border-black/[0.05] bg-white p-4">
              <p class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("landing.statB.label") }}</p>
              <p class="mt-3 text-lg font-semibold text-ink">{{ t("landing.statB.value") }}</p>
            </div>
            <div class="rounded-3xl border border-black/[0.05] bg-white p-4">
              <p class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("landing.statC.label") }}</p>
              <p class="mt-3 text-lg font-semibold text-ink">{{ t("landing.statC.value") }}</p>
            </div>
          </div>

          <div class="mt-6 rounded-[28px] border border-brand/10 bg-glow/70 p-5">
            <p class="text-sm text-[#4a4a4a]">{{ t("landing.preview.status") }}</p>
            <div class="mt-5 space-y-3 rounded-2xl border border-brand/10 bg-white/85 p-4 font-mono text-sm text-brand">
              <div>{{ t("landing.preview.line1") }}</div>
              <div>{{ t("landing.preview.line2") }}</div>
              <div>{{ t("landing.preview.line3") }}</div>
            </div>
          </div>
        </aside>
      </section>

      <section class="grid gap-4 lg:grid-cols-3">
        <article
          v-for="card in capabilityCards"
          :key="card.kicker"
          class="glass-panel rounded-[30px] p-6"
        >
          <div class="text-xs uppercase tracking-[0.28em] text-brand/70">{{ card.kicker }}</div>
          <h3 class="mt-4 text-2xl font-semibold text-ink">{{ card.title }}</h3>
          <p class="mt-3 text-sm leading-7 text-[#4a4a4a]">{{ card.body }}</p>
        </article>
      </section>

      <section id="blueprint" class="glass-panel rounded-[34px] p-6 sm:p-8">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.28em] text-muted">Console Blueprint</p>
            <h2 class="mt-3 text-3xl font-semibold text-ink">{{ t("landing.blueprintTitle") }}</h2>
          </div>
          <p class="max-w-2xl text-sm leading-7 text-[#4a4a4a]">
            {{ t("landing.footer") }}
          </p>
        </div>

        <div class="mt-8 grid gap-4 lg:grid-cols-3">
          <article
            v-for="card in blueprintCards"
            :key="card.title"
            class="rounded-[28px] border border-black/[0.05] bg-white p-6"
          >
            <h3 class="text-xl font-semibold text-ink">{{ card.title }}</h3>
            <p class="mt-3 text-sm leading-7 text-[#4a4a4a]">{{ card.body }}</p>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>
