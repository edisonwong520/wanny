<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

import AppHeader from "@/components/AppHeader.vue";
import { isAuthenticated } from "@/lib/auth";

const primaryAction = computed(() => (isAuthenticated.value ? "/console" : "/register"));
const primaryLabel = computed(() => (isAuthenticated.value ? "进入控制台" : "开始使用"));

const features = [
  { icon: "wechat", title: "微信入口", desc: "消息直达任务流" },
  { icon: "device", title: "设备联动", desc: "房间状态实时同步" },
  { icon: "memory", title: "记忆系统", desc: "主动关怀用户偏好" },
];
</script>

<template>
  <div class="min-h-screen bg-white">
    <AppHeader />

    <main class="mx-auto max-w-4xl px-4 py-16 text-center">
      <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#E8F8EC] text-[#07C160] text-sm mb-6">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
        </svg>
        AI 智能管家
      </div>

      <h1 class="text-4xl font-semibold text-[#333333] mb-4">
        Wanny
      </h1>
      <p class="text-lg text-[#888888] mb-8 max-w-md mx-auto">
        一个智能控制台，连接家庭设备、微信入口、任务审批与长期记忆
      </p>

      <div class="flex justify-center gap-3 mb-12">
        <RouterLink
          :to="primaryAction"
          class="rounded-full bg-[#07C160] px-6 py-3 text-white text-sm font-medium transition-all duration-200 hover:bg-[#06AD56] hover:shadow-lg hover:-translate-y-0.5"
        >
          {{ primaryLabel }}
        </RouterLink>
        <RouterLink
          v-if="!isAuthenticated"
          to="/login"
          class="rounded-full border border-[#EDEDED] px-6 py-3 text-[#333333] text-sm font-medium transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30 hover:-translate-y-0.5"
        >
          登录
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
    </main>

    <footer class="border-t border-[#EDEDED] py-4 text-center text-sm text-[#888888]">
      Wanny - AI 智能家居管理平台
    </footer>
  </div>
</template>