<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "vue-i18n";

import AppHeader from "@/components/AppHeader.vue";
import { isAuthenticated } from "@/lib/auth";

const { t, tm } = useI18n();
const discordUrl = "https://discord.gg/zpSVespn";

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
  platforms: Array<{ name: string; tag: string; logo: string }>;
});
const marqueePlatforms = computed(() => [
  ...platformFeature.value.platforms,
  ...platformFeature.value.platforms,
]);

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

          <p class="mx-auto mt-4 max-w-2xl text-center text-sm leading-7 text-[#6D7E73] md:text-base">
            {{ platformFeature.description }}
          </p>

          <div class="platform-marquee mt-8 overflow-hidden">
            <div
              class="platform-marquee-track flex w-max gap-4"
            >
              <div
                v-for="(platform, index) in marqueePlatforms"
                :key="`${platform.name}-${index}`"
                class="w-[188px] shrink-0 rounded-3xl border border-[#DDEEE2] bg-white px-4 py-4 text-center transition-all duration-200 hover:-translate-y-1 hover:border-[#07C160]/30 hover:shadow-[0_14px_30px_rgba(7,193,96,0.12)]"
              >
                <div class="flex aspect-[4/3] items-center justify-center rounded-2xl border border-dashed border-[#C9DDCF] bg-[radial-gradient(circle_at_top,#FFFFFF_0%,#F4FBF6_100%)] px-6">
                  <img
                    :src="platform.logo"
                    :alt="platform.name"
                    class="max-h-16 w-auto object-contain"
                    loading="lazy"
                  >
                </div> 
                <div class="mt-1 text-sm font-medium text-[#223126] md:text-base">
                  {{ platform.name }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer class="border-t border-[#EDEDED] py-4 text-center text-sm text-[#888888]">
      <div class="flex flex-col items-center justify-center gap-2 sm:flex-row sm:gap-3">
        <span>Wanny - {{ $t("landing.butler") }}</span>
        <span class="hidden sm:inline text-[#D7D7D7]">|</span>
        <a
          :href="discordUrl"
          class="inline-flex items-center gap-2 text-[#888888] transition-colors duration-200 hover:text-[#5865F2]"
          rel="noreferrer"
          target="_blank"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M20.317 4.369A19.791 19.791 0 0 0 15.885 3c-.191.328-.403.77-.554 1.117a18.27 18.27 0 0 0-5.487 0A11.64 11.64 0 0 0 9.29 3a19.736 19.736 0 0 0-4.438 1.372C2.047 8.578 1.285 12.68 1.666 16.73a19.9 19.9 0 0 0 5.301 2.663c.43-.587.813-1.21 1.142-1.866-.626-.236-1.223-.53-1.788-.876.149-.11.294-.223.434-.34 3.447 1.618 7.18 1.618 10.586 0 .142.117.287.23.434.34-.567.347-1.166.642-1.793.878.328.654.711 1.276 1.142 1.864a19.84 19.84 0 0 0 5.304-2.665c.447-4.701-.764-8.766-3.111-12.361ZM8.02 14.273c-1.03 0-1.877-.936-1.877-2.084 0-1.148.827-2.084 1.877-2.084 1.057 0 1.895.945 1.877 2.084 0 1.148-.828 2.084-1.877 2.084Zm7.94 0c-1.03 0-1.877-.936-1.877-2.084 0-1.148.827-2.084 1.877-2.084 1.057 0 1.895.945 1.877 2.084 0 1.148-.82 2.084-1.877 2.084Z"/>
          </svg>
          {{ $t("nav.discord") }}
        </a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.animate-breath {
  animation: breath 3s infinite ease-in-out;
  filter: drop-shadow(0 0 4px rgba(7, 193, 96, 0.4));
}

.platform-marquee {
  mask-image: linear-gradient(to right, transparent, black 8%, black 92%, transparent);
}

.platform-marquee-track {
  animation: platform-marquee-scroll 22s linear infinite;
}

.platform-marquee:hover .platform-marquee-track {
  animation-play-state: paused;
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

@keyframes platform-marquee-scroll {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(calc(-50% - 0.5rem));
  }
}
</style>
