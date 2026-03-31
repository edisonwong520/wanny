<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { setAuth } from "@/lib/auth";
import AppHeader from "@/components/AppHeader.vue";

const { t } = useI18n();
const router = useRouter();

const email = ref("");
const name = ref("");
const password = ref("");
const isLoading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const handleRegister = async () => {
  if (!email.value || !name.value || !password.value) {
    errorMessage.value = "请填写所有必填字段";
    return;
  }

  if (password.value.length < 6) {
    errorMessage.value = "密码长度至少需要 6 个字符";
    return;
  }

  isLoading.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    const response = await fetch(`${apiBaseUrl}/api/accounts/register/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: email.value,
        name: name.value,
        password: password.value,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "注册失败");
    }

    // 注册成功自动登录
    setAuth(data.data);
    
    successMessage.value = "注册成功！正在为您开启控制台...";
    setTimeout(() => {
      router.push("/console");
    }, 1500);
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
        <!-- Decoration -->
        <div class="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-brand/5 blur-3xl"></div>
        
        <div class="relative z-10 space-y-8">
          <div class="text-center">
            <h1 class="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              加入 <span class="text-brand">Wanny</span>
            </h1>
            <p class="mt-3 text-sm text-muted">
              开始您的私人 AI 管家之旅
            </p>
          </div>

          <form @submit.prevent="handleRegister" class="space-y-6">
            <div class="space-y-2">
              <label for="name" class="ml-1 text-xs font-semibold uppercase tracking-widest text-muted">
                您的昵称
              </label>
              <input
                id="name"
                v-model="name"
                type="text"
                placeholder="作为 AI 对您的日常称呼"
                required
                class="w-full rounded-2xl border border-black/[0.05] bg-white/50 px-5 py-4 text-ink outline-none transition-all focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
            </div>

            <div class="space-y-2">
              <label for="email" class="ml-1 text-xs font-semibold uppercase tracking-widest text-muted">
                邮箱地址
              </label>
              <input
                id="email"
                v-model="email"
                type="email"
                placeholder="用于后续登录凭证"
                required
                class="w-full rounded-2xl border border-black/[0.05] bg-white/50 px-5 py-4 text-ink outline-none transition-all focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
            </div>

            <div class="space-y-2">
              <label for="password" class="ml-1 text-xs font-semibold uppercase tracking-widest text-muted">
                账户密码
              </label>
              <input
                id="password"
                v-model="password"
                type="password"
                placeholder="至少 6 位字符"
                required
                class="w-full rounded-2xl border border-black/[0.05] bg-white/50 px-5 py-4 text-ink outline-none transition-all focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
            </div>

            <div v-if="errorMessage" class="rounded-2xl bg-red-50 p-4 text-sm text-red-500 border border-red-100 flex items-center gap-2">
              <span class="text-lg">⚠️</span> {{ errorMessage }}
            </div>

            <div v-if="successMessage" class="rounded-2xl bg-green-50 p-4 text-sm text-green-600 border border-green-100 flex items-center gap-2">
              <span class="text-lg">✅</span> {{ successMessage }}
            </div>

            <button
              type="submit"
              :disabled="isLoading"
              class="group relative flex w-full items-center justify-center overflow-hidden rounded-full bg-brand py-4 font-semibold text-white transition-all hover:shadow-[0_12px_24px_rgba(7,193,96,0.2)] disabled:opacity-70"
            >
              <span v-if="isLoading" class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
              {{ isLoading ? '处理中...' : '立即注册' }}
            </button>
          </form>

          <div class="pt-4 text-center">
            <p class="text-xs text-muted">
              注册即表示您同意我们的服务条款
            </p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.bg-canvas {
  background-color: transparent;
}
</style>
