<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  type MissionRecord,
  type MissionRisk,
  type MissionStatus,
  approveMission,
  fetchMissions,
  rejectMission,
} from "@/lib/missions";

const { t, locale } = useI18n();

const missions = ref<MissionRecord[]>([]);
const activeFilter = ref<"all" | MissionStatus>("pending");
const selectedMissionId = ref<string>("");
const loading = ref(false);
const errorMessage = ref("");
const processing = ref(false);

async function loadMissions(options: { silent?: boolean } = {}) {
  if (!options.silent) {
    loading.value = true;
  }
  errorMessage.value = "";
  try {
    const data = await fetchMissions();
    missions.value = data;
    if (selectedMissionId.value === "" && data.length > 0) {
      selectedMissionId.value = data[0].id;
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : t("missions.errors.load");
  } finally {
    if (!options.silent) {
      loading.value = false;
    }
  }
}

onMounted(() => {
  void loadMissions();
});

watch(
  () => locale.value,
  () => {
    void loadMissions();
  },
);

const filters = computed(() => [
  { id: "pending" as const, label: t("missions.filters.pending") },
  { id: "approved" as const, label: t("missions.filters.approved") },
  { id: "failed" as const, label: t("missions.filters.failed") },
  { id: "all" as const, label: t("missions.filters.all") },
]);

const summaryCards = computed(() => [
  {
    label: t("missions.metrics.pending"),
    value: missions.value.filter((mission) => mission.status === "pending").length,
  },
  {
    label: t("missions.metrics.approved"),
    value: missions.value.filter((mission) => mission.status === "approved").length,
  },
  {
    label: t("missions.metrics.failed"),
    value: missions.value.filter((mission) => mission.status === "failed").length,
  },
  {
    label: t("missions.metrics.highRisk"),
    value: missions.value.filter((mission) => mission.risk === "high").length,
  },
]);

const filteredMissions = computed(() => {
  if (activeFilter.value === "all") {
    return missions.value;
  }
  return missions.value.filter((mission) => mission.status === activeFilter.value);
});

watch(
  filteredMissions,
  (items) => {
    if (!items.some((mission) => mission.id === selectedMissionId.value)) {
      selectedMissionId.value = items[0]?.id ?? "";
    }
  },
  { immediate: true },
);

const selectedMission = computed(
  () =>
    filteredMissions.value.find((mission) => mission.id === selectedMissionId.value) ??
    filteredMissions.value[0] ??
    null,
);

function statusLabel(status: MissionStatus) {
  return t(`missions.status.${status}`);
}

function riskLabel(risk: MissionRisk) {
  return t(`missions.risk.${risk}`);
}

function statusClasses(status: MissionStatus) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    status === "pending" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    status === "approved" && "border-brand/10 bg-glow text-brand",
    status === "failed" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
  );
}

function riskClasses(risk: MissionRisk) {
  return cn(
    "rounded-full border px-3 py-1 text-xs font-semibold",
    risk === "high" && "border-[#EBA5A5]/30 bg-[#FFF1F1] text-[#B64B4B]",
    risk === "medium" && "border-[#E3C784]/30 bg-[#FFF7DF] text-[#8B6A16]",
    risk === "low" && "border-brand/10 bg-glow text-brand",
  );
}

function missionCardClasses(id: string) {
  return cn(
    "rounded-[28px] border p-5 transition cursor-pointer",
    selectedMissionId.value === id
      ? "border-brand/18 bg-glow/65"
      : "border-black/[0.05] bg-white hover:border-brand/10 hover:bg-[#fcfffd]",
  );
}

function selectMission(id: string) {
  selectedMissionId.value = id;
}

async function handleApprove() {
  const mission = selectedMission.value;
  if (!mission || processing.value) return;

  processing.value = true;
  try {
    await approveMission(mission.id);
    await loadMissions({ silent: true });
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "Approval failed";
  } finally {
    processing.value = false;
  }
}

async function handleReject() {
  const mission = selectedMission.value;
  if (!mission || processing.value) return;

  processing.value = true;
  try {
    await rejectMission(mission.id);
    await loadMissions({ silent: true });
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "Rejection failed";
  } finally {
    processing.value = false;
  }
}
</script>

<template>
  <div class="space-y-5">
    <section v-if="errorMessage" class="rounded-[24px] border border-[#F0C8C8] bg-[#FFF4F4] px-4 py-4 text-sm leading-7 text-[#A44545]">
      {{ errorMessage }}
    </section>

    <section v-if="loading" class="rounded-[28px] border border-black/[0.05] bg-white p-8 text-sm text-muted">
      {{ t("missions.loading") || "Loading missions..." }}
    </section>

    <section v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="item in summaryCards"
        :key="item.label"
        class="rounded-[26px] border border-black/[0.05] bg-white p-5"
      >
        <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ item.label }}</div>
        <div class="mt-4 text-3xl font-semibold text-ink">{{ item.value }}</div>
      </article>
    </section>

    <section v-if="!loading" class="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <div class="space-y-4">
        <div class="flex flex-wrap gap-3">
          <button
            v-for="filter in filters"
            :key="filter.id"
            :class="
              cn(
                'rounded-full border px-4 py-2 text-sm font-medium transition',
                activeFilter === filter.id
                  ? 'border-brand/12 bg-glow text-brand'
                  : 'border-black/[0.06] bg-white text-muted hover:border-brand/10 hover:text-ink',
              )
            "
            type="button"
            @click="activeFilter = filter.id"
          >
            {{ filter.label }}
          </button>
        </div>

        <article
          v-for="mission in filteredMissions"
          :key="mission.id"
          :class="missionCardClasses(mission.id)"
          @click="selectMission(mission.id)"
        >
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <span :class="statusClasses(mission.status)">{{ statusLabel(mission.status) }}</span>
                <span :class="riskClasses(mission.risk)">{{ riskLabel(mission.risk) }}</span>
                <span class="text-xs uppercase tracking-[0.24em] text-muted">{{ mission.createdAt }}</span>
              </div>
              <h2 class="mt-4 text-lg font-semibold text-ink">{{ mission.title }}</h2>
              <p class="mt-2 text-sm text-muted">{{ mission.source }}</p>
            </div>
            <button
              class="rounded-full border border-black/[0.06] bg-white px-4 py-2 text-sm font-medium text-ink transition hover:border-brand/10 hover:bg-glow"
              type="button"
              @click.stop="selectMission(mission.id)"
            >
              {{ t("missions.actions.inspect") }}
            </button>
          </div>

          <p class="mt-4 text-sm leading-7 text-[#4a4a4a]">{{ mission.summary }}</p>
        </article>

        <div
          v-if="filteredMissions.length === 0"
          class="rounded-[28px] border border-dashed border-black/[0.08] bg-white/70 px-5 py-8 text-sm text-muted"
        >
          {{ t("missions.empty") }}
        </div>
      </div>

      <aside class="space-y-4" v-if="selectedMission">
        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="flex flex-wrap items-center gap-2">
            <span :class="statusClasses(selectedMission.status)">{{ statusLabel(selectedMission.status) }}</span>
            <span :class="riskClasses(selectedMission.risk)">{{ riskLabel(selectedMission.risk) }}</span>
          </div>

          <h2 class="mt-4 text-2xl font-semibold text-ink">{{ selectedMission.title }}</h2>
          <p class="mt-3 text-sm leading-7 text-[#4a4a4a]">{{ selectedMission.summary }}</p>

          <div class="mt-5 grid gap-3 sm:grid-cols-2">
            <div class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4">
              <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("missions.detail.created") }}</div>
              <div class="mt-3 text-sm font-medium text-ink">{{ selectedMission.createdAt }}</div>
            </div>
            <div class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4">
              <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ t("missions.detail.source") }}</div>
              <div class="mt-3 text-sm font-medium text-ink">{{ selectedMission.source }}</div>
            </div>
          </div>

          <div class="mt-5 flex flex-wrap gap-3">
            <Button
              :disabled="selectedMission.status !== 'pending' || processing"
              @click="handleApprove"
            >
              {{ processing ? "..." : t("missions.actions.approve") }}
            </Button>
            <Button
              variant="secondary"
              :disabled="selectedMission.status !== 'pending' || processing"
              @click="handleReject"
            >
              {{ processing ? "..." : t("missions.actions.reject") }}
            </Button>
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.userMessage") }}</div>
          <div class="mt-4 rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] p-4 text-sm leading-7 text-[#4a4a4a]">
            {{ selectedMission.rawMessage }}
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.intent") }}</div>
          <div class="mt-4 text-sm leading-7 text-[#4a4a4a]">{{ selectedMission.intent }}</div>

          <div class="mt-5 text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.command") }}</div>
          <div class="mt-3 rounded-[22px] border border-brand/10 bg-glow/70 p-4 font-mono text-sm leading-7 text-brand">
            {{ selectedMission.commandPreview }}
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.plan") }}</div>
          <div class="mt-4 space-y-3">
            <div
              v-for="step in selectedMission.plan"
              :key="step"
              class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#4a4a4a]"
            >
              {{ step }}
            </div>
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.context") }}</div>
          <div class="mt-4 space-y-3">
            <div
              v-for="item in selectedMission.context"
              :key="item"
              class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4 text-sm leading-7 text-[#4a4a4a]"
            >
              {{ item }}
            </div>
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.reply") }}</div>
          <div class="mt-4 text-sm leading-7 text-[#4a4a4a]">
            {{ selectedMission.suggestedReply }}
          </div>
        </section>

        <section class="rounded-[28px] border border-black/[0.05] bg-white p-5">
          <div class="text-xs uppercase tracking-[0.24em] text-muted">{{ t("missions.detail.timeline") }}</div>
          <div class="mt-4 space-y-3">
            <div
              v-for="entry in selectedMission.timeline"
              :key="entry.id"
              class="rounded-[22px] border border-black/[0.05] bg-[#fcfcfc] px-4 py-4"
            >
              <div class="flex items-center justify-between gap-4">
                <div class="text-sm leading-7 text-[#4a4a4a]">{{ entry.message }}</div>
                <div class="text-xs uppercase tracking-[0.22em] text-muted">{{ entry.time }}</div>
              </div>
            </div>
          </div>
        </section>
      </aside>
    </section>
  </div>
</template>
