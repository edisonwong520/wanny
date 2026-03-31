<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { setAuth } from "@/lib/auth";
import AppHeader from "@/components/AppHeader.vue";

const router = useRouter();

const identifier = ref("");
const password = ref("");
const isLoading = ref(false);
const errorMessage = ref("");

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const handleLogin = async () => {
  if (!identifier.value || !password.value) {
    errorMessage.value = "请填写完整登录信息";
    return;
  }

  isLoading.value = true;
  errorMessage.value = "";

  try {
    const response = await fetch(`${apiBaseUrl}/api/accounts/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identifier: identifier.value,
        password: password.value,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "登录失败");
    }

    setAuth(data.data);
    router.push("/console");
  } catch (err: any) {
    errorMessage.value = err.message || "系统繁忙，请稍后再试";
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <div class="min-h-screen bg-[#F7F7F7]">
    <AppHeader />

    <main class="mx-auto max-w-sm px-4 py-12">
      <div class="bg-white rounded-2xl p-6 shadow-sm">
        <h1 class="text-xl font-semibold text-[#333333] mb-1">登录</h1>
        <p class="text-sm text-[#888888] mb-6">
          登录以访问控制台
        </p>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <input
              v-model="identifier"
              type="text"
              placeholder="昵称或邮箱"
              required
              class="w-full rounded-xl border border-[#EDEDED] px-4 py-3 text-sm outline-none transition-all duration-200 focus:border-[#07C160] focus:ring-2 focus:ring-[#07C160]/20"
            />
          </div>

          <div>
            <input
              v-model="password"
              type="password"
              placeholder="密码"
              required
              class="w-full rounded-xl border border-[#EDEDED] px-4 py-3 text-sm outline-none transition-all duration-200 focus:border-[#07C160] focus:ring-2 focus:ring-[#07C160]/20"
            />
          </div>

          <div v-if="errorMessage" class="px-4 py-3 rounded-xl bg-[#FFE8E8] text-sm text-[#E84343]">
            {{ errorMessage }}
          </div>

          <button
            type="submit"
            :disabled="isLoading"
            class="w-full rounded-full bg-[#07C160] py-3 text-sm font-medium text-white transition-all duration-200 hover:bg-[#06AD56] hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            <span v-if="isLoading" class="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></span>
            {{ isLoading ? '登录中...' : '登录' }}
          </button>
        </form>

        <div class="mt-5 text-sm text-center text-[#888888]">
          还没有账号？
          <router-link to="/register" class="text-[#07C160] hover:underline">
            注册
          </router-link>
        </div>
      </div>
    </main>
  </div>
</template>