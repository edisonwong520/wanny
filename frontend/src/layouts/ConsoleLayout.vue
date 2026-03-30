<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const route = useRoute();
const { locale, t } = useI18n();

const sections = computed(() => [
  { to: "/console", label: t("console.nav.overview") },
  { to: "/console/missions", label: t("console.nav.tasks") },
  { to: "/console/devices", label: t("console.nav.devices") },
  { to: "/console/manage", label: t("console.nav.manage") },
]);

function toggleLocale() {
  locale.value = locale.value === "zh-CN" ? "en" : "zh-CN";
  document.documentElement.lang = locale.value;
}

function isActive(path: string) {
  return route.path === path;
}
</script>

<template>
  <div class="ambient-shell min-h-screen bg-canvas px-4 pb-8 pt-4 sm:px-6 lg:px-8">
    <div class="mx-auto max-w-[1600px] space-y-4">
      <header class="glass-panel rounded-[34px] px-5 py-5 sm:px-6">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <nav class="flex flex-wrap gap-2">
            <RouterLink
              v-for="section in sections"
              :key="section.to"
              :to="section.to"
              :class="
                cn(
                  'inline-flex items-center rounded-full border px-5 py-2.5 text-sm font-semibold transition',
                  isActive(section.to)
                    ? 'border-2 border-[#07C160] bg-[#F1FFF7] text-[#067A3C] shadow-[0_10px_24px_rgba(7,193,96,0.10)]'
                    : 'border border-black/[0.06] bg-white text-muted hover:border-[#8ED9B0] hover:text-ink',
                )
              "
            >
              {{ section.label }}
            </RouterLink>
          </nav>

          <div class="flex flex-wrap items-center gap-3">
            <div class="inline-flex items-center gap-3 rounded-full border border-brand/10 bg-glow px-4 py-2 text-sm font-medium text-brand">
              <span class="text-center">{{ t("console.topbar.mode") }}</span>
              <span class="relative flex h-2.5 w-2.5 items-center justify-center">
                <span class="absolute inline-flex h-full w-full rounded-full bg-[#07C160]/18 shadow-[0_0_0_3px_rgba(7,193,96,0.12)]"></span>
                <span class="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#07C160]"></span>
              </span>
            </div>
            <Button size="sm" variant="ghost" @click="toggleLocale">
              {{ locale === "zh-CN" ? "EN" : "中文" }}
            </Button>
          </div>
        </div>
      </header>

      <main class="glass-panel rounded-[34px] px-5 py-5 sm:px-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
