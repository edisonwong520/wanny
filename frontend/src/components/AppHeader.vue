<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const route = useRoute();
const { locale, t } = useI18n();

const navItems = computed(() => [
  { to: "/console", label: t("nav.console") },
  { to: "/landing", label: t("nav.landing") },
]);

function toggleLocale() {
  locale.value = locale.value === "zh-CN" ? "en" : "zh-CN";
  document.documentElement.lang = locale.value;
}
</script>

<template>
  <header class="sticky top-4 z-30 mx-auto mb-8 max-w-7xl">
    <div class="glass-panel flex flex-col gap-4 rounded-[28px] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <RouterLink class="flex items-center gap-3" to="/console">
        <div class="flex h-11 w-11 items-center justify-center rounded-2xl border border-brand/15 bg-brand/10 text-xs font-bold tracking-[0.3em] text-brand">
          WA
        </div>
        <div>
          <div class="font-display text-lg font-bold text-ink">Wanny</div>
          <div class="text-xs uppercase tracking-[0.28em] text-muted">
            {{ t("brand.subtitle") }}
          </div>
        </div>
      </RouterLink>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <nav class="flex items-center gap-2 rounded-full border border-black/[0.05] bg-white/75 p-1">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            :class="
              cn(
                'rounded-full px-4 py-2 text-sm transition',
                route.path === item.to
                  ? 'bg-glow text-brand'
                  : 'text-muted hover:text-ink',
              )
            "
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <Button size="sm" variant="ghost" @click="toggleLocale">
          {{ locale === "zh-CN" ? "EN" : "中文" }}
        </Button>
      </div>
    </div>
  </header>
</template>
