<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const items = computed(() => [
  t("guard.items.a"),
  t("guard.items.b"),
  t("guard.items.c"),
]);
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-[#333333]">{{ t("guard.title") }}</h1>
    <p class="text-sm text-[#888888]">{{ t("guard.summary") }}</p>

    <div class="space-y-2">
      <div
        v-for="item in items"
        :key="item"
        class="p-4 rounded-2xl bg-[#F7F7F7] text-sm text-[#333333] transition-all duration-200 hover:bg-[#E8F8EC]/30"
      >
        {{ item }}
      </div>
    </div>
  </div>
</template>