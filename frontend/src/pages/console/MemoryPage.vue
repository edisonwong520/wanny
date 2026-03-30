<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const memoryCards = computed(() => [
  t("memory.items.a"),
  t("memory.items.b"),
  t("memory.items.c"),
]);
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-[30px] border border-black/[0.05] bg-white p-6">
      <div class="text-xs uppercase tracking-[0.26em] text-brand">{{ t("memory.eyebrow") }}</div>
      <h1 class="mt-3 text-3xl font-bold text-ink">{{ t("memory.title") }}</h1>
      <p class="mt-4 max-w-3xl text-base leading-8 text-[#4a4a4a]">{{ t("memory.summary") }}</p>
    </section>

    <section class="grid gap-4 lg:grid-cols-3">
      <article
        v-for="item in memoryCards"
        :key="item"
        class="rounded-[28px] border border-black/[0.05] bg-white p-5 text-sm leading-7 text-[#4a4a4a]"
      >
        {{ item }}
      </article>
    </section>
  </div>
</template>
