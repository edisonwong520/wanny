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
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        identifier: identifier.value,
        password: password.value,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "登录失败");
    }

    // 更新全局状态并跳转
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
  <div class="ambient-shell min-h-screen bg-canvas px-4 pb-14 pt-4 sm:px-6 lg:px-10">
    <AppHeader />

    <main class="mx-auto mt-10 max-w-lg">
      <div class="glass-panel relative overflow-hidden rounded-[34px] p-8 sm:p-10">
        <div class="relative z-10 space-y-8">
          <div class="text-center">
            <h1 class="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              欢迎回来
            </h1>
            <p class="mt-3 text-sm text-muted">
              请登录以访问您的 Wanny 控制台
            </p>
          </div>

          <form @submit.prevent="handleLogin" class="space-y-6">
            <div class="space-y-2">
              <label for="identifier" class="ml-1 text-xs font-semibold uppercase tracking-widest text-muted">
                昵称或邮箱
              </label>
              <input
                id="identifier"
                v-model="identifier"
                type="text"
                placeholder="请输入您的昵称或注册邮箱"
                required
                class="w-full rounded-2xl border border-black/[0.05] bg-white/50 px-5 py-4 text-ink outline-none transition-all focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
            </div>

            <div class="space-y-2">
              <div class="flex items-center justify-between px-1">
                <label for="password" class="text-xs font-semibold uppercase tracking-widest text-muted">
                  账户密码
                </label>
              </div>
              <input
                id="password"
                v-model="password"
                type="password"
                placeholder="请输入您的密码"
                required
                class="w-full rounded-2xl border border-black/[0.05] bg-white/50 px-5 py-4 text-ink outline-none transition-all focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
            </div>

            <div v-if="errorMessage" class="rounded-2xl bg-red-50 p-4 text-sm text-red-500 border border-red-100">
              ⚠️ {{ errorMessage }}
            </div>

            <button
              type="submit"
              :disabled="isLoading"
              class="group relative flex w-full items-center justify-center overflow-hidden rounded-full bg-brand py-4 font-semibold text-white transition-all hover:shadow-[0_12px_24px_rgba(7,193,96,0.2)]"
            >
              <span v-if="isLoading" class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
              {{ isLoading ? '登录中...' : '立即登录' }}
            </button>
          </form>

          <footer class="text-center">
            <p class="text-sm text-muted">
              还没有账号？
              <router-link to="/register" class="font-semibold text-brand hover:underline">
                立即注册
              </router-link>
            </p>
          </footer>
        </div>
      </div>
    </main>
  </div>
</template>
