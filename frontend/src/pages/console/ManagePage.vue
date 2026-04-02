<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  type AuthorizationSession,
  type ProviderRecord,
  disconnectProvider,
  fetchAuthorizationSession,
  fetchProviders,
  startAuthorization,
} from "@/lib/provider-auth";

const { t, locale } = useI18n();

const providers = ref<ProviderRecord[]>([]);
const sessions = ref<Record<string, AuthorizationSession | null>>({});
const loading = ref(true);
const errorMessage = ref("");
const busyAction = ref("");
const pollingTimers = new Map<string, number>();
const modalPlatform = ref<string | null>(null);
const modalLoading = ref(false);
const homeAssistantBaseUrl = ref("http://127.0.0.1:8123");
const homeAssistantAccessToken = ref("");
// 美的云表单状态
const mideaCloudAccount = ref("");
const mideaCloudPassword = ref("");
const mideaCloudServer = ref<"1" | "2">("2"); // 默认美的美居

// 美的云服务器选项
const mideaServerOptions = computed(() => [
  { value: "1", label: t("manage.auth.servers.msmartHome") },
  { value: "2", label: t("manage.auth.servers.meiju") },
]);

const modalProvider = computed(() =>
  modalPlatform.value
    ? providers.value.find((p) => p.platform === modalPlatform.value) ?? null
    : null
);

const modalSession = computed(() =>
  modalPlatform.value ? sessions.value[modalPlatform.value] ?? null : null
);

const modalQrImageUrl = computed(() => {
  const session = modalSession.value;
  if (!session) return null;
  // 只对米家平台显示二维码图片
  if (modalProvider.value?.platform !== "mijia") return null;
  const url = session.image_url;
  if (!url) return null;
  // 支持 base64 和 HTTP URL
  if (url.startsWith("data:image/") || url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  return null;
});

const isHomeAssistantModal = computed(() => modalProvider.value?.platform === "home_assistant");
const isMideaCloudModal = computed(() => modalProvider.value?.platform === "midea_cloud");

const homeAssistantInstanceName = computed(() => {
  const preview = modalProvider.value?.payload_preview ?? {};
  const value = preview.instance_name;
  return typeof value === "string" ? value : "";
});

const mideaCloudInstanceName = computed(() => {
  const preview = modalProvider.value?.payload_preview ?? {};
  const value = preview.instance_name;
  return typeof value === "string" ? value : "";
});

function stopPolling(platform: string) {
  const timer = pollingTimers.get(platform);
  if (timer) {
    window.clearInterval(timer);
    pollingTimers.delete(platform);
  }
}

function stopAllPolling() {
  pollingTimers.forEach((timer) => window.clearInterval(timer));
  pollingTimers.clear();
}

function updateProvider(provider: ProviderRecord) {
  const next = [...providers.value];
  const idx = next.findIndex((p) => p.platform === provider.platform);
  if (idx >= 0) next[idx] = provider;
  else next.push(provider);
  providers.value = next.sort((a, b) => a.display_name.localeCompare(b.display_name));
}

async function loadProviders() {
  const response = await fetchProviders();
  providers.value = response.providers.sort((a, b) => a.display_name.localeCompare(b.display_name));
}

async function loadSession(platform: string, shouldRefresh = false) {
  const response = await fetchAuthorizationSession(platform);
  sessions.value = { ...sessions.value, [platform]: response.session };
  updateProvider(response.provider);
  if (modalPlatform.value === platform && response.session?.status === "completed") {
    closeModal();
  }
  if (response.session?.is_terminal) {
    stopPolling(platform);
    if (shouldRefresh) await loadProviders();
  }
}

function ensurePolling(platform: string) {
  const session = sessions.value[platform];
  if (!session || session.is_terminal || pollingTimers.has(platform)) return;
  const timer = window.setInterval(async () => {
    try {
      await loadSession(platform, true);
    } catch {
      stopPolling(platform);
    }
  }, 2500);
  pollingTimers.set(platform, timer);
}

async function initialize() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await loadProviders();
    await Promise.all(
      providers.value.map(async (p) => {
        await loadSession(p.platform);
        ensurePolling(p.platform);
      })
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.load");
  } finally {
    loading.value = false;
  }
}

function providerStyle(provider: ProviderRecord) {
  if (provider.status === "connected") return { bg: "#E8F8EC", text: "#07C160" };
  if (provider.status === "disabled") return { bg: "#FFF7E6", text: "#E8A223" };
  return { bg: "#F7F7F7", text: "#888888" };
}

function openModal(platform: string) {
  modalPlatform.value = platform;
  const provider = providers.value.find((p) => p.platform === platform);
  if (platform === "home_assistant") {
    const preview = provider?.payload_preview ?? {};
    homeAssistantBaseUrl.value =
      typeof preview.base_url === "string" && preview.base_url
        ? preview.base_url
        : "http://127.0.0.1:8123";
    homeAssistantAccessToken.value = "";
  }
  if (platform === "midea_cloud") {
    const preview = provider?.payload_preview ?? {};
    mideaCloudAccount.value = typeof preview.account === "string" ? preview.account : "";
    mideaCloudPassword.value = "";
    mideaCloudServer.value = typeof preview.server === "number" ? String(preview.server) : "2";
  }
}

function closeModal() {
  modalPlatform.value = null;
  modalLoading.value = false;
  homeAssistantAccessToken.value = "";
  mideaCloudPassword.value = ""; // 清除密码
}

function handleDialogOpenChange(open: boolean) {
  if (!open) closeModal();
}

async function handleAuthorize(provider: ProviderRecord, force: boolean) {
  openModal(provider.platform);
  modalLoading.value = true;
  busyAction.value = `${provider.platform}:connect`;
  errorMessage.value = "";
  try {
    const response = await startAuthorization(provider.platform, { force });
    updateProvider(response.provider);
    sessions.value = { ...sessions.value, [provider.platform]: response.session };
    ensurePolling(provider.platform);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
    modalLoading.value = false;
  }
}

async function handleClick(provider: ProviderRecord) {
  // Home Assistant 或美的云需要先输入配置信息，直接打开弹窗
  if (provider.platform === "home_assistant" || provider.platform === "midea_cloud") {
    openModal(provider.platform);
    return;
  }

  const session = sessions.value[provider.platform];
  if (session && !session.is_terminal) {
    openModal(provider.platform);
    return;
  }
  await handleAuthorize(provider, provider.status === "connected");
}

async function handleHomeAssistantAuthorize() {
  const provider = modalProvider.value;
  if (!provider || provider.platform !== "home_assistant") return;

  modalLoading.value = true;
  busyAction.value = `${provider.platform}:connect`;
  errorMessage.value = "";

  try {
    const response = await startAuthorization(provider.platform, {
      payload: {
        base_url: homeAssistantBaseUrl.value.trim(),
        access_token: homeAssistantAccessToken.value.trim(),
      },
    });
    updateProvider(response.provider);
    sessions.value = { ...sessions.value, [provider.platform]: response.session };
    homeAssistantAccessToken.value = "";
    closeModal();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
    modalLoading.value = false;
  }
}

async function handleMideaCloudAuthorize() {
  const provider = modalProvider.value;
  if (!provider || provider.platform !== "midea_cloud") return;

  modalLoading.value = true;
  busyAction.value = `${provider.platform}:connect`;
  errorMessage.value = "";

  try {
    const response = await startAuthorization(provider.platform, {
      payload: {
        account: mideaCloudAccount.value.trim(),
        password: mideaCloudPassword.value.trim(),
        server: parseInt(mideaCloudServer.value),
      },
    });
    updateProvider(response.provider);
    sessions.value = { ...sessions.value, [provider.platform]: response.session };
    mideaCloudPassword.value = ""; // 清除密码
    closeModal();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
    modalLoading.value = false;
  }
}

async function handleDisconnect(provider: ProviderRecord) {
  if (!window.confirm(t("manage.auth.confirmDisconnect"))) return;
  busyAction.value = `${provider.platform}:disconnect`;
  errorMessage.value = "";
  try {
    await disconnectProvider(provider.platform);
    stopPolling(provider.platform);
    sessions.value = { ...sessions.value, [provider.platform]: null };
    await loadProviders();
    await loadSession(provider.platform);
    if (modalPlatform.value === provider.platform) closeModal();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
  }
}

onMounted(() => void initialize());
onBeforeUnmount(() => stopAllPolling());
</script>

<template>
  <div class="space-y-4">
    <div v-if="errorMessage" class="px-4 py-3 rounded-2xl bg-[#FFE8E8] text-sm text-[#E84343]">
      {{ errorMessage }}
    </div>

    <div v-if="loading" class="py-8 text-center text-sm text-[#888888]">
      {{ $t("common.loading") }}
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="provider in providers"
        :key="provider.platform"
        class="flex items-center justify-between p-4 rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30 hover:shadow-sm"
      >
        <div class="flex items-center gap-3">
          <span class="font-medium text-[#333333]">{{ locale === "zh-CN" ? provider.display_name_zh : provider.display_name }}</span>
          <span
            class="px-2.5 py-1 rounded-full text-xs font-medium"
            :style="{ background: providerStyle(provider).bg, color: providerStyle(provider).text }"
          >
            {{ t(`manage.auth.providerStatus.${provider.status}`) }}
          </span>
        </div>

        <div class="flex gap-2">
          <button
            v-if="provider.status !== 'connected'"
            :disabled="busyAction === `${provider.platform}:connect`"
            class="px-4 py-2 rounded-full border border-[#07C160] bg-white text-[#07C160] text-sm font-medium transition-all duration-200 hover:bg-[#07C160] hover:text-white hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:bg-white disabled:hover:text-[#07C160]"
            @click="handleClick(provider)"
          >
            {{ $t("manage.auth.actions.connect") }}
          </button>
          <button
            v-if="provider.configured"
            :disabled="busyAction === `${provider.platform}:disconnect`"
            class="px-4 py-2 rounded-full border border-[#EDEDED] bg-white text-[#888888] text-sm font-medium transition-all duration-200 hover:border-[#E84343]/30 hover:text-[#E84343] hover:bg-[#FFE8E8]/50 hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:bg-white disabled:hover:text-[#888888] disabled:hover:border-[#EDEDED]"
            @click="handleDisconnect(provider)"
          >
            {{ $t("manage.auth.actions.disconnect") }}
          </button>
        </div>
      </div>

      <div v-if="providers.length === 0" class="py-8 text-center text-sm text-[#888888]">
        {{ $t("manage.auth.empty") }}
      </div>
    </div>

    <Dialog :open="Boolean(modalProvider)" @update:open="handleDialogOpenChange">
      <DialogContent v-if="modalProvider" class="p-5 max-w-sm">
        <DialogHeader class="sr-only">
          <DialogTitle>{{ locale === "zh-CN" ? modalProvider.display_name_zh : modalProvider.display_name }}</DialogTitle>
        </DialogHeader>
        <DialogClose
          class="absolute right-4 top-4 w-8 h-8 flex items-center justify-center rounded-full border border-[#EDEDED] text-[#888888] transition-all duration-200 hover:bg-[#F7F7F7] hover:text-[#333333]"
        >
          ×
        </DialogClose>

        <div class="space-y-4">
          <h3 class="text-lg font-medium text-[#333333]">
            {{ locale === "zh-CN" ? modalProvider.display_name_zh : modalProvider.display_name }} {{ $t("manage.auth.actions.authorize") }}
          </h3>

          <div v-if="isHomeAssistantModal" class="space-y-3">
            <div class="space-y-1.5">
              <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
                {{ $t("manage.auth.fields.baseUrl") }}
              </label>
              <input
                v-model="homeAssistantBaseUrl"
                type="url"
                placeholder="http://homeassistant.local:8123"
                class="w-full rounded-2xl border border-[#EDEDED] bg-[#FCFCFC] px-4 py-3 text-sm text-[#333333] outline-none transition-all duration-200 focus:border-[#07C160] focus:bg-white"
              />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
                {{ $t("manage.auth.fields.accessToken") }}
              </label>
              <input
                v-model="homeAssistantAccessToken"
                type="password"
                :placeholder="$t('manage.auth.fields.accessTokenPlaceholder')"
                class="w-full rounded-2xl border border-[#EDEDED] bg-[#FCFCFC] px-4 py-3 text-sm text-[#333333] outline-none transition-all duration-200 focus:border-[#07C160] focus:bg-white"
              />
            </div>
            <div class="rounded-2xl border border-[#E8F1EA] bg-[#F5FBF7] px-4 py-3 text-xs text-[#4E6A57] leading-relaxed">
              <div v-if="$t('manage.auth.hint.home_assistant')" class="font-medium mb-1">{{ $t("manage.auth.hint.home_assistant") }}</div>
              <div class="text-[#6C8373]">{{ $t("manage.auth.hint.ha_token_info") }}</div>
              <div v-if="homeAssistantInstanceName" class="mt-2 pt-2 border-t border-[#E8F1EA] text-[#6C8373]">
                {{ $t("manage.auth.currentInstance") }}: {{ homeAssistantInstanceName }}
              </div>
            </div>
            <button
              :disabled="modalLoading || !homeAssistantBaseUrl.trim() || !homeAssistantAccessToken.trim()"
              class="w-full rounded-full bg-[#07C160] px-4 py-3 text-sm font-medium text-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
              @click="handleHomeAssistantAuthorize"
            >
              {{ $t("manage.auth.actions.save") }}
            </button>
          </div>

          <!-- 美的云表单 -->
          <div v-if="isMideaCloudModal" class="space-y-3">
            <!-- 账号输入 -->
            <div class="space-y-1.5">
              <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
                {{ $t("manage.auth.fields.account") }}
              </label>
              <input
                v-model="mideaCloudAccount"
                type="text"
                :placeholder="$t('manage.auth.fields.accountPlaceholder')"
                class="w-full rounded-2xl border border-[#EDEDED] bg-[#FCFCFC] px-4 py-3 text-sm text-[#333333] outline-none transition-all duration-200 focus:border-[#07C160] focus:bg-white"
              />
            </div>

            <!-- 密码输入 -->
            <div class="space-y-1.5">
              <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
                {{ $t("manage.auth.fields.password") }}
              </label>
              <input
                v-model="mideaCloudPassword"
                type="password"
                :placeholder="$t('manage.auth.fields.passwordPlaceholder')"
                class="w-full rounded-2xl border border-[#EDEDED] bg-[#FCFCFC] px-4 py-3 text-sm text-[#333333] outline-none transition-all duration-200 focus:border-[#07C160] focus:bg-white"
              />
            </div>

            <!-- 服务器选择 -->
            <div class="space-y-1.5">
              <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
                {{ $t("manage.auth.fields.server") }}
              </label>
              <div class="flex gap-2">
                <button
                  v-for="option in mideaServerOptions"
                  :key="option.value"
                  :class="[
                    'flex-1 px-4 py-2.5 rounded-full text-sm font-medium transition-all duration-200',
                    mideaCloudServer === option.value
                      ? 'bg-[#07C160] text-white shadow-sm'
                      : 'bg-[#F7F7F7] text-[#888888] hover:bg-[#EDEDED] hover:text-[#333333]'
                  ]"
                  @click="mideaCloudServer = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>

            <!-- 提示信息 -->
            <div class="rounded-2xl border border-[#E8F1EA] bg-[#F5FBF7] px-4 py-3 text-xs text-[#4E6A57] leading-relaxed">
              <div class="font-medium mb-1">{{ $t("manage.auth.hint.midea_cloud") }}</div>
              <div class="text-[#6C8373]">{{ $t("manage.auth.hint.midea_server_info") }}</div>
              <div v-if="mideaCloudInstanceName" class="mt-2 pt-2 border-t border-[#E8F1EA] text-[#6C8373]">
                {{ $t("manage.auth.currentInstance") }}: {{ mideaCloudInstanceName }}
              </div>
            </div>

            <!-- 提交按钮 -->
            <button
              :disabled="modalLoading || !mideaCloudAccount.trim() || !mideaCloudPassword.trim()"
              class="w-full rounded-full bg-[#07C160] px-4 py-3 text-sm font-medium text-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
              @click="handleMideaCloudAuthorize"
            >
              {{ $t("manage.auth.actions.save") }}
            </button>
          </div>

          <!-- 米家：只显示二维码 -->
          <div v-if="modalProvider.platform === 'mijia' && modalQrImageUrl" class="flex justify-center">
            <img
              :src="modalQrImageUrl"
              :alt="modalProvider.display_name_zh"
              class="w-52 aspect-square rounded-2xl border border-[#EDEDED]"
            />
          </div>

          <!-- 微信：只显示链接按钮（居中） -->
          <div v-if="modalProvider.platform === 'wechat' && modalSession?.action_url" class="flex justify-center">
            <a
              :href="modalSession.action_url"
              target="_blank"
              rel="noreferrer"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#E8F8EC] text-[#07C160] text-sm font-medium transition-all duration-200 hover:bg-[#07C160] hover:text-white hover:shadow-md"
            >
              {{ $t("manage.auth.actions.openLink") }}
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
              </svg>
            </a>
          </div>
          <div v-if="modalProvider.platform === 'mijia'" class="text-sm text-[#888888] text-center">
            {{ $t("manage.auth.hint.mijia") }}
          </div>
          <div v-if="modalProvider.platform === 'wechat'" class="text-sm text-[#888888] text-center">
            {{ $t("manage.auth.hint.wechat") }}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
