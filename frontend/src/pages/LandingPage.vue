<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import AppHeader from "@/components/AppHeader.vue";
import { isAuthenticated } from "@/lib/auth";

const { t, tm } = useI18n();

const primaryAction = computed(() => (isAuthenticated.value ? "/console" : "/register"));
const primaryLabel = computed(() => (isAuthenticated.value ? t("landing.primary") : t("landing.secondary")));

const features = computed(() => {
  const brief = tm("landing.briefFeatures") as any;
  return [
    { icon: "wechat", title: brief.wechat.title, desc: brief.wechat.desc },
    { icon: "device", title: brief.device.title, desc: brief.device.desc },
    { icon: "memory", title: brief.memory.title, desc: brief.memory.desc },
  ];
});

const platformFeature = computed(() => tm("landing.platformFeature") as {
  eyebrow: string;
  slogan: string;
  description: string;
  platforms: Array<{ name: string; tag: string }>;
});

// 从 i18n 获取翻译后的列表
const localizedPrompts = computed(() => tm("landing.prompts") as string[]);
const displayPrompts = computed(() => [...localizedPrompts.value, localizedPrompts.value[0]]);

const isTransitionsEnabled = ref(true);
const currentPromptIndex = ref(0);

onMounted(() => {
  setInterval(() => {
    isTransitionsEnabled.value = true;
    currentPromptIndex.value++;

    if (currentPromptIndex.value === displayPrompts.value.length - 1) {
      setTimeout(() => {
        isTransitionsEnabled.value = false;
        currentPromptIndex.value = 0;
      }, 700);
    }
  }, 2000);
});
</script>

<template>
  <div class="min-h-screen bg-white">
    <AppHeader />

    <main class="mx-auto max-w-4xl px-4 py-16 text-center">
      <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#E8F8EC] text-[#07C160] text-sm mb-6">
        <svg class="w-4 h-4 animate-breath" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
        </svg>
        {{ $t("landing.butler") }}
      </div>

      <h1 class="text-5xl font-semibold text-[#333333] mb-4 tracking-tight">
        {{ $t("landing.titleLead") }}
      </h1>

      <div class="flex items-center justify-center gap-2 text-lg text-[#888888] mb-12">
        <span>{{ $t("landing.questions") }}</span>
        <div class="h-7 overflow-hidden relative w-64">
          <div
            class="absolute w-full left-0"
            :class="{ 'transition-all duration-700 ease-in-out': isTransitionsEnabled }"
            :style="{ transform: `translateY(-${currentPromptIndex * 28}px)` }"
          >
            <div
              v-for="(prompt, index) in displayPrompts"
              :key="index"
              class="h-7 leading-7 text-[#07C160] font-medium text-left truncate"
            >
              {{ prompt }}
            </div>
          </div>
          <div class="absolute inset-0 pointer-events-none bg-gradient-to-b from-white via-transparent to-white opacity-60"></div>
        </div>
      </div>

      <div class="flex justify-center gap-3 mb-16">
        <RouterLink
          :to="primaryAction"
          class="rounded-full bg-[#07C160] px-6 py-3 text-white text-sm font-medium transition-all duration-200 hover:bg-[#06AD56] hover:shadow-lg hover:-translate-y-0.5"
        >
          {{ primaryLabel }}
        </RouterLink>
      </div>

      <div class="grid md:grid-cols-3 gap-4 text-left">
        <div
          v-for="feature in features"
          :key="feature.title"
          class="p-5 rounded-2xl bg-[#F7F7F7] transition-all duration-200 hover:bg-[#E8F8EC]/30 hover:-translate-y-1 hover:shadow-md"
        >
          <div class="font-medium text-[#333333] mb-1">{{ feature.title }}</div>
          <div class="text-sm text-[#888888]">{{ feature.desc }}</div>
        </div>
      </div>

      <section class="mt-20 text-left">
        <div class="rounded-[32px] border border-[#E4EFE7] bg-[linear-gradient(180deg,#FCFFFD_0%,#F5FBF7_100%)] px-6 py-8 shadow-[0_20px_60px_rgba(7,193,96,0.06)] md:px-8 md:py-10">
          <h2 class="text-center text-3xl font-semibold tracking-tight text-[#1F2A22] md:text-4xl">
            {{ platformFeature.slogan }}
          </h2>

          <div class="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div
              v-for="platform in platformFeature.platforms"
              :key="platform.name"
              class="rounded-3xl border border-[#DDEEE2] bg-white px-4 py-4 text-center transition-all duration-200 hover:-translate-y-1 hover:border-[#07C160]/30 hover:shadow-[0_14px_30px_rgba(7,193,96,0.12)]"
            >
              <div class="flex aspect-[4/3] items-center justify-center rounded-2xl border border-dashed border-[#C9DDCF] bg-[#F8FCF9] text-xs font-medium uppercase tracking-[0.24em] text-[#A0B1A6]">
                {{ platform.tag }}
              </div>
              <div class="mt-3 text-sm font-medium text-[#223126] md:text-base">
                {{ platform.name }}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer class="border-t border-[#EDEDED] py-4 text-center text-sm text-[#888888]">
      Wanny - {{ $t("landing.butler") }}
    </footer>
  </div>
</template>

<style scoped>
.animate-breath {
  animation: breath 3s infinite ease-in-out;
  filter: drop-shadow(0 0 4px rgba(7, 193, 96, 0.4));
}

@keyframes breath {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
    filter: drop-shadow(0 0 2px rgba(7, 193, 96, 0.2));
  }
  50% {
    transform: scale(1.15);
    opacity: 0.7;
    filter: drop-shadow(0 0 8px rgba(7, 193, 96, 0.6));
  }
}
</style>
