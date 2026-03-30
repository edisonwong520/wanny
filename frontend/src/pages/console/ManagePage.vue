<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
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
import { cn } from "@/lib/utils";

const { t } = useI18n();

const providers = ref<ProviderRecord[]>([]);
const sessions = ref<Record<string, AuthorizationSession | null>>({});
const loading = ref(true);
const errorMessage = ref("");
const busyAction = ref("");
const pollingTimers = new Map<string, number>();
const modalPlatform = ref<string | null>(null);
const modalLoading = ref(false);

const modalProvider = computed(() => {
  if (!modalPlatform.value) {
    return null;
  }
  return providers.value.find((provider) => provider.platform === modalPlatform.value) ?? null;
});

const modalSession = computed(() => {
  if (!modalPlatform.value) {
    return null;
  }
  return sessions.value[modalPlatform.value] ?? null;
});

const modalQrImageUrl = computed(() => {
  const session = modalSession.value;
  if (!session) {
    return null;
  }

  if (
    session.image_url &&
    (session.image_url.startsWith("data:image/") ||
      /\.(png|jpg|jpeg|gif|webp|svg)(\?|$)/i.test(session.image_url))
  ) {
    return session.image_url;
  }

  if (!session.action_url) {
    return null;
  }

  if (session.action_url.startsWith("data:image/")) {
    return session.action_url;
  }

  try {
    const url = new URL(session.action_url);
    for (const key of ["qrcode", "qr", "image", "image_url"]) {
      const candidate = url.searchParams.get(key);
      if (candidate && (candidate.startsWith("data:image/") || candidate.startsWith("http"))) {
        return candidate;
      }
    }
  } catch {
    return null;
  }

  return null;
});

function updateProviderRecord(provider: ProviderRecord) {
  const nextProviders = [...providers.value];
  const index = nextProviders.findIndex((item) => item.platform === provider.platform);

  if (index >= 0) {
    nextProviders[index] = provider;
  } else {
    nextProviders.push(provider);
  }

  providers.value = nextProviders.sort((left, right) =>
    left.display_name.localeCompare(right.display_name),
  );
}

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

async function loadProviders() {
  const response = await fetchProviders();
  providers.value = response.providers.sort((left, right) =>
    left.display_name.localeCompare(right.display_name),
  );
}

async function loadAuthorizationSession(platform: string, shouldRefreshProviders = false) {
  const response = await fetchAuthorizationSession(platform);
  sessions.value = {
    ...sessions.value,
    [platform]: response.session,
  };
  updateProviderRecord(response.provider);

  if (modalPlatform.value === platform && response.session?.status === "completed") {
    closeAuthorizationModal();
  }

  if (response.session?.is_terminal) {
    stopPolling(platform);
    if (shouldRefreshProviders) {
      await loadProviders();
    }
  }
}

function ensurePolling(platform: string) {
  const session = sessions.value[platform];
  if (!session || session.is_terminal || pollingTimers.has(platform)) {
    return;
  }

  const timer = window.setInterval(async () => {
    try {
      await loadAuthorizationSession(platform, true);
    } catch (error) {
      stopPolling(platform);
      errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.load");
    }
  }, 2500);

  pollingTimers.set(platform, timer);
}

async function initializePage() {
  loading.value = true;
  errorMessage.value = "";

  try {
    await loadProviders();
    await Promise.all(
      providers.value.map(async (provider) => {
        await loadAuthorizationSession(provider.platform);
        ensurePolling(provider.platform);
      }),
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.load");
  } finally {
    loading.value = false;
  }
}

function providerStatusLabel(provider: ProviderRecord) {
  return t(`manage.auth.providerStatus.${provider.status}`);
}

function providerStatusTone(provider: ProviderRecord) {
  if (provider.status === "connected") {
    return "border-brand/10 bg-[#F1FFF7] text-[#067A3C]";
  }
  if (provider.status === "disabled") {
    return "border-[#E6CFA2] bg-[#FFF8E8] text-[#9E6A16]";
  }
  return "border-black/[0.08] bg-[#F7F4EA] text-[#6B6254]";
}

function sessionStatusLabel(session: AuthorizationSession | null) {
  if (!session) {
    return t("manage.auth.sessionStatus.idle");
  }
  return t(`manage.auth.sessionStatus.${session.status}`);
}

function sessionStatusTone(session: AuthorizationSession | null) {
  if (!session) {
    return "border-black/[0.08] bg-[#F7F4EA] text-[#6B6254]";
  }
  if (session.status === "completed") {
    return "border-brand/10 bg-[#F1FFF7] text-[#067A3C]";
  }
  if (session.status === "failed" || session.status === "expired") {
    return "border-[#F0C8C8] bg-[#FFF4F4] text-[#A44545]";
  }
  if (session.status === "scanned") {
    return "border-[#E6CFA2] bg-[#FFF8E8] text-[#9E6A16]";
  }
  return "border-black/[0.08] bg-[#F7F4EA] text-[#6B6254]";
}

function isBusy(platform: string, action: "connect" | "disconnect") {
  return busyAction.value === `${platform}:${action}`;
}

function openAuthorizationModal(platform: string) {
  modalPlatform.value = platform;
}

function closeAuthorizationModal() {
  modalPlatform.value = null;
  modalLoading.value = false;
}

function handleDialogOpenChange(open: boolean) {
  if (!open) {
    closeAuthorizationModal();
  }
}

function connectActionLabel(provider: ProviderRecord) {
  const session = sessions.value[provider.platform];
  if (session && !session.is_terminal) {
    return t("manage.auth.actions.viewSession");
  }
  return t("manage.auth.actions.connect");
}

async function handleStartAuthorization(provider: ProviderRecord, force: boolean) {
  openAuthorizationModal(provider.platform);
  modalLoading.value = true;
  busyAction.value = `${provider.platform}:connect`;
  errorMessage.value = "";

  try {
    const response = await startAuthorization(provider.platform, force);
    updateProviderRecord(response.provider);
    sessions.value = {
      ...sessions.value,
      [provider.platform]: response.session,
    };
    ensurePolling(provider.platform);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
    modalLoading.value = false;
  }
}

async function handleAuthorizeClick(provider: ProviderRecord) {
  const session = sessions.value[provider.platform];
  if (session && !session.is_terminal) {
    openAuthorizationModal(provider.platform);
    return;
  }

  await handleStartAuthorization(provider, provider.status === "connected");
}

async function handleDisconnect(provider: ProviderRecord) {
  if (!window.confirm(t("manage.auth.confirmDisconnect"))) {
    return;
  }

  busyAction.value = `${provider.platform}:disconnect`;
  errorMessage.value = "";

  try {
    await disconnectProvider(provider.platform);
    stopPolling(provider.platform);
    sessions.value = {
      ...sessions.value,
      [provider.platform]: null,
    };
    await loadProviders();
    await loadAuthorizationSession(provider.platform);
    if (modalPlatform.value === provider.platform) {
      closeAuthorizationModal();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
  }
}

onMounted(() => {
  void initializePage();
});

onBeforeUnmount(() => {
  stopAllPolling();
});
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-[30px] border border-black/[0.05] bg-white p-5 sm:p-6">
      <div class="space-y-5">
        <h1 class="text-3xl font-semibold text-ink">{{ t("manage.auth.title") }}</h1>

        <section
          v-if="errorMessage"
          class="rounded-[24px] border border-[#F0C8C8] bg-[#FFF4F4] px-4 py-4 text-sm leading-7 text-[#A44545]"
        >
          {{ errorMessage }}
        </section>

        <div
          v-if="loading"
          class="rounded-[24px] border border-black/[0.05] bg-[#fcfcfc] p-8 text-sm text-muted"
        >
          {{ t("manage.auth.loading") }}
        </div>

        <div v-else-if="providers.length" class="space-y-4">
          <article
            v-for="provider in providers"
            :key="provider.platform"
            :class="
              cn(
                'rounded-[24px] border p-4 transition',
                modalPlatform === provider.platform
                  ? 'border-brand/20 bg-[#FBFFF9]'
                  : 'border-black/[0.05] bg-[#fcfcfc]',
              )
            "
          >
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div class="flex-1">
                <div class="flex flex-wrap items-center gap-3">
                  <div class="w-[8ch] shrink-0">
                    <div class="text-lg font-semibold text-ink">
                      {{ provider.display_name_zh }}
                    </div>
                    <div class="mt-1 text-sm text-[#6C665B]">
                      {{ provider.display_name }}
                    </div>
                  </div>
                  <div
                    :class="
                      cn(
                        'inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold',
                        providerStatusTone(provider),
                      )
                    "
                  >
                    {{ providerStatusLabel(provider) }}
                  </div>
                  <div
                    v-if="
                      sessions[provider.platform] &&
                      sessions[provider.platform]?.status !== 'completed'
                    "
                    class="cursor-pointer"
                    :class="
                      cn(
                        'inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold',
                        sessionStatusTone(sessions[provider.platform] ?? null),
                      )
                    "
                    @click="openAuthorizationModal(provider.platform)"
                  >
                    {{ sessionStatusLabel(sessions[provider.platform] ?? null) }}
                  </div>
                </div>
              </div>

              <div class="flex flex-wrap gap-2 lg:justify-end">
                <Button
                  v-if="
                    provider.status !== 'connected' ||
                    (sessions[provider.platform] && !sessions[provider.platform]?.is_terminal)
                  "
                  variant="secondary"
                  :disabled="isBusy(provider.platform, 'connect')"
                  @click="handleAuthorizeClick(provider)"
                >
                  {{ connectActionLabel(provider) }}
                </Button>
                <Button
                  v-if="provider.configured"
                  variant="ghost"
                  :disabled="isBusy(provider.platform, 'disconnect')"
                  @click="handleDisconnect(provider)"
                >
                  {{ t("manage.auth.actions.disconnect") }}
                </Button>
              </div>
            </div>
          </article>
        </div>
        <div
          v-else
          class="rounded-[24px] border border-dashed border-black/[0.08] px-4 py-8 text-sm text-muted"
        >
          {{ t("manage.auth.empty") }}
        </div>
      </div>
    </section>

    <Dialog :open="Boolean(modalProvider)" @update:open="handleDialogOpenChange">
      <DialogContent v-if="modalProvider" class="p-0">
        <DialogHeader class="sr-only">
          <DialogTitle>{{ modalProvider.display_name_zh }}</DialogTitle>
          <DialogDescription>{{ modalProvider.display_name }}</DialogDescription>
        </DialogHeader>

        <DialogClose
          class="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full border border-black/[0.06] bg-white text-xl leading-none text-[#6C665B] transition hover:bg-[#f7f7f7]"
        >
          ×
        </DialogClose>

        <div class="max-h-[85vh] space-y-4 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
          <div
            v-if="modalQrImageUrl"
            class="overflow-hidden rounded-[24px] border border-black/[0.05] bg-[#fffdf8] p-4"
          >
            <img
              :src="modalQrImageUrl"
              :alt="modalProvider.display_name_zh"
              class="mx-auto aspect-square w-full max-w-[320px] rounded-[20px] object-contain"
            />
          </div>

          <div
            v-if="modalProvider.platform === 'wechat' && modalSession?.action_url"
            class="rounded-[20px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#6C665B]"
          >
            {{ t("manage.auth.wechatHint") }}
          </div>

          <div v-if="modalSession?.action_url || modalSession?.verification_url" class="space-y-3">
            <a
              v-if="modalSession?.action_url"
              :href="modalSession.action_url"
              target="_blank"
              rel="noreferrer"
              class="block break-all rounded-[20px] border border-brand/10 bg-[#F1FFF7] px-4 py-4 text-sm leading-7 text-[#067A3C]"
            >
              {{ modalSession.action_url }}
            </a>
            <a
              v-if="modalSession?.verification_url"
              :href="modalSession.verification_url"
              target="_blank"
              rel="noreferrer"
              class="block break-all rounded-[20px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#8B5A11]"
            >
              {{ modalSession.verification_url }}
            </a>
          </div>

          <div v-if="modalSession?.action_url" class="flex flex-wrap gap-2">
            <a
              :href="modalSession.action_url"
              target="_blank"
              rel="noreferrer"
              class="inline-flex h-9 items-center justify-center rounded-full border border-[#9AD5B1] bg-[#F1FFF7] px-4 text-xs font-semibold text-[#067A3C] transition hover:-translate-y-0.5 hover:border-[#07C160] hover:bg-[#E9FAF0]"
            >
              {{ t("manage.auth.actions.openLink") }}
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
