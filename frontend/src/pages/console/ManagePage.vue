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

const { t } = useI18n();

const providers = ref<ProviderRecord[]>([]);
const sessions = ref<Record<string, AuthorizationSession | null>>({});
const loading = ref(true);
const errorMessage = ref("");
const busyAction = ref("");
const pollingTimers = new Map<string, number>();
const modalPlatform = ref<string | null>(null);
const modalLoading = ref(false);

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
  if (session.image_url?.startsWith("data:image/")) return session.image_url;
  return null;
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
    closeAuthorizationModal();
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
}

function closeModal() {
  modalPlatform.value = null;
  modalLoading.value = false;
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
    const response = await startAuthorization(provider.platform, force);
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
  const session = sessions.value[provider.platform];
  if (session && !session.is_terminal) {
    openModal(provider.platform);
    return;
  }
  await handleAuthorize(provider, provider.status === "connected");
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
      加载中...
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="provider in providers"
        :key="provider.platform"
        class="flex items-center justify-between p-4 rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30 hover:shadow-sm"
      >
        <div class="flex items-center gap-3">
          <span class="font-medium text-[#333333]">{{ provider.display_name_zh }}</span>
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
            连接
          </button>
          <button
            v-if="provider.configured"
            :disabled="busyAction === `${provider.platform}:disconnect`"
            class="px-4 py-2 rounded-full border border-[#EDEDED] bg-white text-[#888888] text-sm font-medium transition-all duration-200 hover:border-[#E84343]/30 hover:text-[#E84343] hover:bg-[#FFE8E8]/50 hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:bg-white disabled:hover:text-[#888888] disabled:hover:border-[#EDEDED]"
            @click="handleDisconnect(provider)"
          >
            断开
          </button>
        </div>
      </div>

      <div v-if="providers.length === 0" class="py-8 text-center text-sm text-[#888888]">
        暂无可用的集成
      </div>
    </div>

    <Dialog :open="Boolean(modalProvider)" @update:open="handleDialogOpenChange">
      <DialogContent v-if="modalProvider" class="p-5 max-w-sm">
        <DialogHeader class="sr-only">
          <DialogTitle>{{ modalProvider.display_name_zh }}</DialogTitle>
        </DialogHeader>
        <DialogClose
          class="absolute right-4 top-4 w-8 h-8 flex items-center justify-center rounded-full border border-[#EDEDED] text-[#888888] transition-all duration-200 hover:bg-[#F7F7F7] hover:text-[#333333]"
        >
          ×
        </DialogClose>

        <div class="space-y-4">
          <h3 class="text-lg font-medium text-[#333333]">{{ modalProvider.display_name_zh }} 授权</h3>

          <div v-if="modalQrImageUrl" class="flex justify-center">
            <img
              :src="modalQrImageUrl"
              :alt="modalProvider.display_name_zh"
              class="w-52 aspect-square rounded-2xl border border-[#EDEDED]"
            />
          </div>

          <div v-if="modalSession?.action_url">
            <a
              :href="modalSession.action_url"
              target="_blank"
              rel="noreferrer"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#E8F8EC] text-[#07C160] text-sm font-medium transition-all duration-200 hover:bg-[#07C160] hover:text-white hover:shadow-md"
            >
              点击打开授权链接
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
              </svg>
            </a>
          </div>

          <div v-if="modalProvider.platform === 'wechat'" class="text-sm text-[#888888] text-center">
            使用微信扫描二维码完成授权
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>