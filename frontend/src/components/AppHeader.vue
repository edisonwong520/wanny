<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

import { clearAuth, currentUser, isAuthenticated } from "@/lib/auth";

const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const githubUrl = "https://github.com/edisonwong520/wanny?tab=readme-ov-file#readme";

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
        <img
          alt="Wanny logo"
          class="h-8 w-8 rounded-lg object-cover shadow-sm"
          src="/brand-icon.svg"
        />
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
        <a
          :href="githubUrl"
          class="inline-flex items-center gap-2 rounded-full border border-[#EDEDED] bg-white px-4 py-1.5 text-sm text-[#888888] transition-all duration-200 hover:bg-[#F7F7F7] hover:text-[#333333]"
          rel="noreferrer"
          target="_blank"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.42-4.04-1.42-.55-1.38-1.33-1.75-1.33-1.75-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.25 1.84 1.25 1.07 1.84 2.81 1.31 3.49 1 .11-.78.42-1.31.76-1.61-2.67-.31-5.47-1.35-5.47-5.98 0-1.32.47-2.39 1.24-3.24-.12-.31-.54-1.57.12-3.27 0 0 1.01-.33 3.3 1.24a11.4 11.4 0 0 1 6 0c2.29-1.57 3.29-1.24 3.29-1.24.66 1.7.24 2.96.12 3.27.77.85 1.24 1.92 1.24 3.24 0 4.64-2.8 5.67-5.48 5.97.43.37.82 1.1.82 2.22v3.29c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z"/>
          </svg>
          {{ $t("nav.github") }}
        </a>
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
        <a
          :href="githubUrl"
          class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm text-[#888888]"
          rel="noreferrer"
          target="_blank"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.42-4.04-1.42-.55-1.38-1.33-1.75-1.33-1.75-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.25 1.84 1.25 1.07 1.84 2.81 1.31 3.49 1 .11-.78.42-1.31.76-1.61-2.67-.31-5.47-1.35-5.47-5.98 0-1.32.47-2.39 1.24-3.24-.12-.31-.54-1.57.12-3.27 0 0 1.01-.33 3.3 1.24a11.4 11.4 0 0 1 6 0c2.29-1.57 3.29-1.24 3.29-1.24.66 1.7.24 2.96.12 3.27.77.85 1.24 1.92 1.24 3.24 0 4.64-2.8 5.67-5.48 5.97.43.37.82 1.1.82 2.22v3.29c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z"/>
          </svg>
          {{ $t("nav.github") }}
        </a>
      </nav>
    </div>
  </header>
</template>
