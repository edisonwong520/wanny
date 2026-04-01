<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

import { clearAuth, currentUser, isAuthenticated } from "@/lib/auth";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();

const isConsoleRoute = computed(() => route.path.startsWith("/console"));

function toggleLocale() {
  locale.value = locale.value === "zh-CN" ? "en" : "zh-CN";
  document.documentElement.lang = locale.value;
}

function handleLogout() {
  clearAuth();
  router.push("/landing");
}
</script>

<template>
  <header class="sticky top-0 z-40 bg-white border-b border-[#EDEDED]">
    <div class="mx-auto max-w-6xl flex items-center justify-between px-4 py-3">
      <RouterLink class="flex items-center gap-2" to="/landing">
        <div class="w-8 h-8 rounded-lg bg-[#07C160] flex items-center justify-center">
          <svg class="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.1c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
          </svg>
        </div>
        <span class="font-semibold text-[#333333]">Wanny</span>
      </RouterLink>

      <nav class="hidden md:flex items-center gap-1">
        <RouterLink
          to="/landing"
          class="px-4 py-2 rounded-full text-sm transition-all duration-200"
          :class="route.path === '/landing'
            ? 'bg-[#E8F8EC] text-[#07C160]'
            : 'text-[#888888] hover:bg-[#F7F7F7] hover:text-[#333333]'"
        >
          {{ $t("nav.landing") }}
        </RouterLink>
        <RouterLink
          to="/console"
          class="px-4 py-2 rounded-full text-sm transition-all duration-200"
          :class="isConsoleRoute
            ? 'bg-[#E8F8EC] text-[#07C160]'
            : 'text-[#888888] hover:bg-[#F7F7F7] hover:text-[#333333]'"
        >
          {{ $t("nav.console") }}
        </RouterLink>
      </nav>

      <div class="flex items-center gap-3">
        <span v-if="isAuthenticated && currentUser" class="text-sm text-[#888888] truncate max-w-[80px]">
          {{ currentUser.name }}
        </span>
        <button
          class="text-sm text-[#888888] hover:text-[#07C160] transition-colors w-12 text-center"
          type="button"
          @click="toggleLocale"
        >
          {{ locale === "zh-CN" ? "EN" : "中文" }}
        </button>

        <button
          v-if="isAuthenticated"
          class="rounded-full border border-[#EDEDED] bg-white px-4 py-1.5 text-sm text-[#888888] transition-all duration-200 hover:border-[#EDEDED] hover:bg-[#F7F7F7] hover:text-[#333333]"
          type="button"
          @click="handleLogout"
        >
          {{ $t("auth.logout") }}
        </button>
        <RouterLink
          v-else
          class="rounded-full bg-[#07C160] px-4 py-1.5 text-sm text-white transition-all duration-200 hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5"
          to="/login"
        >
          {{ $t("auth.loginRegister") }}
        </RouterLink>
      </div>
    </div>

    <div class="md:hidden border-t border-[#EDEDED] px-4 py-2">
      <nav class="flex gap-2">
        <RouterLink
          to="/landing"
          class="px-3 py-1.5 rounded-full text-sm"
          :class="route.path === '/landing' ? 'bg-[#E8F8EC] text-[#07C160]' : 'text-[#888888]'"
        >
          {{ $t("nav.landing") }}
        </RouterLink>
        <RouterLink
          to="/console"
          class="px-3 py-1.5 rounded-full text-sm"
          :class="isConsoleRoute ? 'bg-[#E8F8EC] text-[#07C160]' : 'text-[#888888]'"
        >
          {{ $t("nav.console") }}
        </RouterLink>
      </nav>
    </div>
  </header>
</template>