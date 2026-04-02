<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import {
  type MissionRecord,
  type MissionStatus,
  approveMission,
  fetchMissions,
  rejectMission,
} from "@/lib/missions";
import { formatDateTime } from "@/lib/utils";

const { t, locale } = useI18n();

const missions = ref<MissionRecord[]>([]);
const activeFilter = ref<"all" | MissionStatus>("pending");
const selectedMissionId = ref<string>("");
const loading = ref(false);
const errorMessage = ref("");
const processing = ref(false);

async function loadMissions(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true;
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
    if (!options.silent) loading.value = false;
  }
}

onMounted(() => void loadMissions());
watch(() => locale.value, () => void loadMissions());

const filters = computed(() => [
  { id: "pending" as const, label: t("missions.filters.pending"), count: missions.value.filter((m) => m.status === "pending").length },
  { id: "approved" as const, label: t("missions.filters.approved"), count: missions.value.filter((m) => m.status === "approved").length },
  { id: "failed" as const, label: t("missions.filters.failed"), count: missions.value.filter((m) => m.status === "failed").length },
]);

const filteredMissions = computed(() => {
  if (activeFilter.value === "all") return missions.value;
  return missions.value.filter((mission) => mission.status === activeFilter.value);
});

watch(filteredMissions, (items) => {
  if (!items.some((mission) => mission.id === selectedMissionId.value)) {
    selectedMissionId.value = items[0]?.id ?? "";
  }
}, { immediate: true });

const selectedMission = computed(() =>
  filteredMissions.value.find((mission) => mission.id === selectedMissionId.value) ?? filteredMissions.value[0] ?? null
);

function statusStyle(status: MissionStatus) {
  if (status === "pending") return { bg: "#FFF7E6", text: "#E8A223" };
  if (status === "approved") return { bg: "#E8F8EC", text: "#07C160" };
  return { bg: "#FFE8E8", text: "#E84343" };
}

function selectMission(id: string) {
  selectedMissionId.value = id;
}

function canApproveMission(mission: MissionRecord) {
  return mission.canApprove;
}

function canRejectMission(mission: MissionRecord) {
  return mission.canReject;
}

function pendingHint(mission: MissionRecord) {
  if (mission.sourceType === "device_clarification") {
    return t("missions.hints.deviceClarificationPending");
  }
  return "";
}

async function handleApprove() {
  const mission = selectedMission.value;
  if (!mission || processing.value) return;
  processing.value = true;
  try {
    await approveMission(mission.id);
    await loadMissions({ silent: true });
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : t("manage.auth.errors.action");
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
    errorMessage.value = err instanceof Error ? err.message : t("manage.auth.errors.action");
  } finally {
    processing.value = false;
  }
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="errorMessage" class="px-4 py-3 rounded-2xl bg-[#FFE8E8] text-sm text-[#E84343]">
      {{ errorMessage }}
    </div>

    <div v-if="loading" class="py-8 text-center text-sm text-[#888888]">
      {{ $t("common.loading") }}
    </div>

    <div v-else class="gap-4">
      <div class="space-y-3">
        <div class="flex gap-1.5">
          <button
            v-for="filter in filters"
            :key="filter.id"
            class="px-3 py-1.5 rounded-full text-xs transition-all duration-200"
            :class="activeFilter === filter.id
              ? 'bg-[#07C160] text-white shadow-sm'
              : 'bg-[#F7F7F7] text-[#888888] hover:bg-[#EDEDED]'"
            @click="activeFilter = filter.id"
          >
            {{ filter.label }} ({{ filter.count }})
          </button>
        </div>

        <div class="space-y-4">
          <template v-if="filteredMissions.length > 0">
            <div v-for="mission in filteredMissions" :key="mission.id" class="space-y-2">
              <!-- 任务卡片 -->
              <div
                class="p-4 rounded-2xl cursor-pointer transition-all duration-200 border"
                :class="selectedMissionId === mission.id
                  ? 'border-[#07C160] bg-[#E8F8EC]/50 shadow-sm'
                  : 'border-[#EDEDED] hover:border-[#07C160]/30 hover:bg-[#F7F7F7]'"
                @click="selectMission(mission.id)"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs text-[#888888]">{{ formatDateTime(mission.createdAt) }}</span>
                  <span
                    class="px-2.5 py-1 rounded-full text-xs font-medium"
                    :style="{ background: statusStyle(mission.status).bg, color: statusStyle(mission.status).text }"
                  >
                    {{ t(`missions.status.${mission.status}`) }}
                  </span>
                  
                </div>
                <div class="text-sm font-medium text-[#333333]">{{ mission.title }}</div>
              </div>

              <!-- 详情区域 (仅在选中时展示在该任务下方) -->
              <div v-if="selectedMissionId === mission.id" class="p-5 rounded-2xl bg-[#f0f9f2] border border-[#07C160]/20 ml-2 mr-2 mb-4 animate-in fade-in slide-in-from-top-1 duration-300">

                <p class="text-sm text-[#555555] mb-5 leading-relaxed">{{ mission.summary }}</p>

                <!-- 仅待处理状态展示按钮 -->
                <div v-if="mission.status === 'pending'" class="flex gap-2 mb-3">
                  <button
                    v-if="canApproveMission(mission)"
                    :disabled="processing"
                    class="px-5 py-2 rounded-full bg-[#07C160] text-white text-sm font-medium transition-all duration-200 hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
                    @click="handleApprove"
                  >
                    {{ processing ? "..." : $t("missions.actions.approve") }}
                  </button>
                  <button
                    v-if="canRejectMission(mission)"
                    :disabled="processing"
                    class="px-5 py-2 rounded-full border border-[#dce6dd] bg-white text-[#888888] text-sm font-medium transition-all duration-200 hover:border-[#E84343]/30 hover:text-[#E84343] hover:bg-[#FFE8E8]/50 hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
                    @click="handleReject"
                  >
                    {{ processing ? "..." : $t("missions.actions.reject") }}
                  </button>
                </div>
                <p v-if="mission.status === 'pending' && pendingHint(mission)" class="mb-5 text-xs leading-5 text-[#888888]">
                  {{ pendingHint(mission) }}
                </p>

                <div class="space-y-4 text-sm bg-white/50 p-4 rounded-xl">
                  <div class="grid gap-4 md:grid-cols-2">
                    <div>
                      <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.source") }}</div>
                      <div class="text-[#333333] bg-white/80 p-2 rounded-lg border border-[#07C160]/5">{{ mission.source }}</div>
                    </div>
                    <div>
                      <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.intent") }}</div>
                      <div class="text-[#333333] bg-white/80 p-2 rounded-lg border border-[#07C160]/5">{{ mission.intent }}</div>
                    </div>
                  </div>
                  <div>
                    <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.userMessage") }}</div>
                    <div class="text-[#333333] bg-white/80 p-2 rounded-lg border border-[#07C160]/5">{{ mission.rawMessage }}</div>
                  </div>
                  <div v-if="mission.confirmMessage">
                    <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.reply") }}</div>
                    <div class="text-[#333333] bg-white/80 p-2 rounded-lg border border-[#07C160]/5">{{ mission.confirmMessage }}</div>
                  </div>
                  <div v-if="mission.resultMessage">
                    <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.result") }}</div>
                    <div class="text-[#333333] bg-[#E8F8EC]/70 p-2 rounded-lg border border-[#07C160]/10">{{ mission.resultMessage }}</div>
                  </div>
                  <div v-if="mission.commandPreview">
                    <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.command") }}</div>
                    <div class="font-mono text-[11px] text-[#07C160] bg-[#1e1e1e] p-3 rounded-lg overflow-x-auto shadow-inner">
                      {{ mission.commandPreview }}
                    </div>
                  </div>
                  <div v-if="mission.plan.length > 0">
                    <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.plan") }}</div>
                    <div class="space-y-2">
                      <div
                        v-for="(step, index) in mission.plan"
                        :key="`${mission.id}-plan-${index}`"
                        class="text-[#333333] bg-white/80 p-2 rounded-lg border border-[#07C160]/5"
                      >
                        {{ index + 1 }}. {{ step }}
                      </div>
                    </div>
                  </div>
                  <div v-if="mission.timeline.length > 0">
                    <div class="text-[#888888] text-xs mb-1.5 font-medium uppercase tracking-wider">{{ $t("missions.detail.timeline") }}</div>
                    <div class="space-y-2">
                      <div
                        v-for="item in mission.timeline"
                        :key="item.id"
                        class="rounded-lg border border-[#07C160]/5 bg-white/80 p-2"
                      >
                        <div class="text-[11px] text-[#888888] mb-1">{{ item.time }}</div>
                        <div class="text-[#333333]">{{ item.message }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="py-12 text-center">
            <div class="text-3xl mb-2">🍃</div>
            <div class="text-sm text-[#888888]">{{ $t("missions.empty") }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
