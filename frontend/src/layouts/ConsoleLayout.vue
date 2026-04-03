<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

import AppHeader from "@/components/AppHeader.vue";

const route = useRoute();
const { t } = useI18n();

const tabs = computed(() => [
  { to: "/console/devices", label: t("console.nav.devices") },
  { to: "/console/missions", label: t("console.nav.tasks") },
  { to: "/console/manage", label: t("console.nav.manage") },
]);

function isActive(path: string) {
  return route.path === path;
}
</script>

<template>
  <div class="min-h-screen bg-[#F7F7F7]">
    <AppHeader />

    <div class="mx-auto max-w-6xl px-4 py-4">
      <div class="bg-white rounded-2xl shadow-sm">
        <nav class="flex gap-1 px-3 pt-3">
          <RouterLink
            v-for="tab in tabs"
            :key="tab.to"
            :to="tab.to"
            class="px-4 py-2 rounded-full text-sm transition-all duration-200"
            :class="isActive(tab.to)
              ? 'bg-[#07C160] text-white shadow-sm'
              : 'text-[#888888] hover:bg-[#F7F7F7] hover:text-[#333333]'"
          >
            {{ tab.label }}
          </RouterLink>
        </nav>

        <div class="p-4">
          <RouterView />
        </div>
      </div>
    </div>
  </div>
</template>
