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
  { id: "pending" as const, label: "待处理", count: missions.value.filter((m) => m.status === "pending").length },
  { id: "approved" as const, label: "已通过", count: missions.value.filter((m) => m.status === "approved").length },
  { id: "failed" as const, label: "已拒绝", count: missions.value.filter((m) => m.status === "failed").length },
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

async function handleApprove() {
  const mission = selectedMission.value;
  if (!mission || processing.value) return;
  processing.value = true;
  try {
    await approveMission(mission.id);
    await loadMissions({ silent: true });
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "操作失败";
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
    errorMessage.value = err instanceof Error ? err.message : "操作失败";
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
      加载中...
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
      <div class="space-y-3">
        <div class="flex gap-2">
          <button
            v-for="filter in filters"
            :key="filter.id"
            class="px-4 py-2 rounded-full text-sm transition-all duration-200"
            :class="activeFilter === filter.id
              ? 'bg-[#07C160] text-white shadow-sm'
              : 'bg-[#F7F7F7] text-[#888888] hover:bg-[#EDEDED]'"
            @click="activeFilter = filter.id"
          >
            {{ filter.label }} ({{ filter.count }})
          </button>
        </div>

        <div class="space-y-2">
          <div
            v-for="mission in filteredMissions"
            :key="mission.id"
            class="p-4 rounded-2xl cursor-pointer transition-all duration-200 border"
            :class="selectedMissionId === mission.id
              ? 'border-[#07C160] bg-[#E8F8EC]/50 shadow-sm'
              : 'border-[#EDEDED] hover:border-[#07C160]/30 hover:bg-[#F7F7F7]'"
            @click="selectMission(mission.id)"
          >
            <div class="flex items-center gap-2 mb-2">
              <span
                class="px-2.5 py-1 rounded-full text-xs font-medium"
                :style="{ background: statusStyle(mission.status).bg, color: statusStyle(mission.status).text }"
              >
                {{ t(`missions.status.${mission.status}`) }}
              </span>
              <span class="text-xs text-[#888888]">{{ mission.createdAt }}</span>
            </div>
            <div class="text-sm font-medium text-[#333333]">{{ mission.title }}</div>
            <div class="text-xs text-[#888888] mt-1">{{ mission.source }}</div>
          </div>

          <div v-if="filteredMissions.length === 0" class="py-8 text-center text-sm text-[#888888]">
            暂无任务
          </div>
        </div>
      </div>

      <div v-if="selectedMission" class="p-5 rounded-2xl bg-[#F7F7F7]">
        <div class="flex items-center gap-2 mb-3">
          <span
            class="px-2.5 py-1 rounded-full text-xs font-medium"
            :style="{ background: statusStyle(selectedMission.status).bg, color: statusStyle(selectedMission.status).text }"
          >
            {{ t(`missions.status.${selectedMission.status}`) }}
          </span>
        </div>

        <h3 class="text-lg font-medium text-[#333333] mb-2">{{ selectedMission.title }}</h3>
        <p class="text-sm text-[#888888] mb-5">{{ selectedMission.summary }}</p>

        <div class="flex gap-2 mb-5">
          <button
            :disabled="selectedMission.status !== 'pending' || processing"
            class="px-5 py-2 rounded-full bg-[#07C160] text-white text-sm font-medium transition-all duration-200 hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
            @click="handleApprove"
          >
            {{ processing ? "..." : "通过" }}
          </button>
          <button
            :disabled="selectedMission.status !== 'pending' || processing"
            class="px-5 py-2 rounded-full border border-[#EDEDED] bg-white text-[#888888] text-sm font-medium transition-all duration-200 hover:border-[#E84343]/30 hover:text-[#E84343] hover:bg-[#FFE8E8]/50 hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
            @click="handleReject"
          >
            {{ processing ? "..." : "拒绝" }}
          </button>
        </div>

        <div class="space-y-4 text-sm">
          <div>
            <div class="text-[#888888] mb-1.5">用户消息</div>
            <div class="text-[#333333]">{{ selectedMission.rawMessage }}</div>
          </div>
          <div>
            <div class="text-[#888888] mb-1.5">执行命令</div>
            <div class="font-mono text-[#07C160] bg-white p-3 rounded-xl">{{ selectedMission.commandPreview }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>