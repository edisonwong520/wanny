export type TranslateFn = (key: string) => string;

export type MissionStatus = "pending" | "approved" | "failed";
export type MissionRisk = "high" | "medium" | "low";
export type DeviceStatus = "online" | "attention" | "offline";
export type PolicyDecision = "ask" | "always" | "never";

export interface HealthCard {
  label: string;
  value: string;
  tone: string;
}

export interface OverviewEvent {
  id: string;
  time: string;
  title: string;
  body: string;
  route: string;
}

export interface MissionTimelineItem {
  id: string;
  time: string;
  message: string;
}

export interface MissionRecord {
  id: string;
  title: string;
  summary: string;
  status: MissionStatus;
  risk: MissionRisk;
  source: string;
  createdAt: string;
  rawMessage: string;
  intent: string;
  commandPreview: string;
  suggestedReply: string;
  context: string[];
  plan: string[];
  timeline: MissionTimelineItem[];
}

export interface DeviceModeRecord {
  id: string;
  label: string;
  summary: string;
  changedAt: string;
}

export interface RoomRecord {
  id: string;
  name: string;
  climate: string;
  summary: string;
  deviceCount: number;
  alertCount: number;
}

export interface DeviceRecord {
  id: string;
  name: string;
  roomId: string;
  roomName: string;
  category: string;
  status: DeviceStatus;
  telemetry: string;
  lastSeen: string;
  note: string;
  capabilities: string[];
}

export interface PolicyRecord {
  id: string;
  modeId: string;
  roomId: string;
  target: string;
  condition: string;
  decision: PolicyDecision;
  rationale: string;
}

export interface DeviceAlertRecord {
  id: string;
  roomId: string;
  severity: MissionRisk;
  title: string;
  body: string;
  recommendation: string;
}

export interface ConsoleMockData {
  healthCards: HealthCard[];
  snapshotLines: string[];
  recentEvents: OverviewEvent[];
  proactiveCount: number;
  anomalyCount: number;
  activeModeId: string;
  modes: DeviceModeRecord[];
  rooms: RoomRecord[];
  devices: DeviceRecord[];
  policies: PolicyRecord[];
  deviceAlerts: DeviceAlertRecord[];
  missions: MissionRecord[];
}

export function createConsoleMockData(t: TranslateFn): ConsoleMockData {
  return {
    healthCards: [
      { label: t("overview.health.bot"), value: "ONLINE", tone: "text-brand" },
      { label: t("overview.health.monitor"), value: "POLLING", tone: "text-[#257B53]" },
      { label: t("overview.health.review"), value: "03:00", tone: "text-ink" },
      { label: t("overview.health.memory"), value: "CHROMA", tone: "text-[#4a4a4a]" },
    ],
    snapshotLines: [
      t("overview.snapshot.a"),
      t("overview.snapshot.b"),
      t("overview.snapshot.c"),
      t("overview.snapshot.d"),
    ],
    recentEvents: [
      {
        id: "event-1",
        time: "14:08",
        title: t("consoleData.events.1.title"),
        body: t("consoleData.events.1.body"),
        route: "/console/missions",
      },
      {
        id: "event-2",
        time: "13:56",
        title: t("consoleData.events.2.title"),
        body: t("consoleData.events.2.body"),
        route: "/console/devices",
      },
      {
        id: "event-3",
        time: "03:00",
        title: t("consoleData.events.3.title"),
        body: t("consoleData.events.3.body"),
        route: "/console/manage",
      },
      {
        id: "event-4",
        time: "02:41",
        title: t("consoleData.events.4.title"),
        body: t("consoleData.events.4.body"),
        route: "/console/manage",
      },
    ],
    proactiveCount: 4,
    anomalyCount: 3,
    activeModeId: "away",
    modes: [
      {
        id: "away",
        label: t("consoleData.fabric.modes.away.label"),
        summary: t("consoleData.fabric.modes.away.summary"),
        changedAt: "13:52",
      },
      {
        id: "home",
        label: t("consoleData.fabric.modes.home.label"),
        summary: t("consoleData.fabric.modes.home.summary"),
        changedAt: "08:10",
      },
      {
        id: "sleep",
        label: t("consoleData.fabric.modes.sleep.label"),
        summary: t("consoleData.fabric.modes.sleep.summary"),
        changedAt: "23:30",
      },
    ],
    rooms: [
      {
        id: "living",
        name: t("consoleData.fabric.rooms.living.name"),
        climate: t("consoleData.fabric.rooms.living.climate"),
        summary: t("consoleData.fabric.rooms.living.summary"),
        deviceCount: 2,
        alertCount: 1,
      },
      {
        id: "bedroom",
        name: t("consoleData.fabric.rooms.bedroom.name"),
        climate: t("consoleData.fabric.rooms.bedroom.climate"),
        summary: t("consoleData.fabric.rooms.bedroom.summary"),
        deviceCount: 1,
        alertCount: 0,
      },
      {
        id: "studio",
        name: t("consoleData.fabric.rooms.studio.name"),
        climate: t("consoleData.fabric.rooms.studio.climate"),
        summary: t("consoleData.fabric.rooms.studio.summary"),
        deviceCount: 1,
        alertCount: 1,
      },
      {
        id: "pet",
        name: t("consoleData.fabric.rooms.pet.name"),
        climate: t("consoleData.fabric.rooms.pet.climate"),
        summary: t("consoleData.fabric.rooms.pet.summary"),
        deviceCount: 1,
        alertCount: 1,
      },
    ],
    devices: [
      {
        id: "living-light",
        name: t("consoleData.fabric.devices.livingLight.name"),
        roomId: "living",
        roomName: t("consoleData.fabric.rooms.living.name"),
        category: t("consoleData.fabric.devices.livingLight.category"),
        status: "attention",
        telemetry: t("consoleData.fabric.devices.livingLight.telemetry"),
        lastSeen: "14:05",
        note: t("consoleData.fabric.devices.livingLight.note"),
        capabilities: [
          t("consoleData.fabric.devices.livingLight.capabilities.1"),
          t("consoleData.fabric.devices.livingLight.capabilities.2"),
        ],
      },
      {
        id: "entry-sensor",
        name: t("consoleData.fabric.devices.entrySensor.name"),
        roomId: "living",
        roomName: t("consoleData.fabric.rooms.living.name"),
        category: t("consoleData.fabric.devices.entrySensor.category"),
        status: "online",
        telemetry: t("consoleData.fabric.devices.entrySensor.telemetry"),
        lastSeen: "14:07",
        note: t("consoleData.fabric.devices.entrySensor.note"),
        capabilities: [
          t("consoleData.fabric.devices.entrySensor.capabilities.1"),
          t("consoleData.fabric.devices.entrySensor.capabilities.2"),
        ],
      },
      {
        id: "bedroom-ac",
        name: t("consoleData.fabric.devices.bedroomAc.name"),
        roomId: "bedroom",
        roomName: t("consoleData.fabric.rooms.bedroom.name"),
        category: t("consoleData.fabric.devices.bedroomAc.category"),
        status: "online",
        telemetry: t("consoleData.fabric.devices.bedroomAc.telemetry"),
        lastSeen: "14:02",
        note: t("consoleData.fabric.devices.bedroomAc.note"),
        capabilities: [
          t("consoleData.fabric.devices.bedroomAc.capabilities.1"),
          t("consoleData.fabric.devices.bedroomAc.capabilities.2"),
        ],
      },
      {
        id: "studio-purifier",
        name: t("consoleData.fabric.devices.studioPurifier.name"),
        roomId: "studio",
        roomName: t("consoleData.fabric.rooms.studio.name"),
        category: t("consoleData.fabric.devices.studioPurifier.category"),
        status: "online",
        telemetry: t("consoleData.fabric.devices.studioPurifier.telemetry"),
        lastSeen: "14:04",
        note: t("consoleData.fabric.devices.studioPurifier.note"),
        capabilities: [
          t("consoleData.fabric.devices.studioPurifier.capabilities.1"),
          t("consoleData.fabric.devices.studioPurifier.capabilities.2"),
        ],
      },
      {
        id: "pet-fountain",
        name: t("consoleData.fabric.devices.petFountain.name"),
        roomId: "pet",
        roomName: t("consoleData.fabric.rooms.pet.name"),
        category: t("consoleData.fabric.devices.petFountain.category"),
        status: "offline",
        telemetry: t("consoleData.fabric.devices.petFountain.telemetry"),
        lastSeen: "13:31",
        note: t("consoleData.fabric.devices.petFountain.note"),
        capabilities: [
          t("consoleData.fabric.devices.petFountain.capabilities.1"),
          t("consoleData.fabric.devices.petFountain.capabilities.2"),
        ],
      },
    ],
    policies: [
      {
        id: "policy-away-light",
        modeId: "away",
        roomId: "living",
        target: t("consoleData.fabric.policies.awayLight.target"),
        condition: t("consoleData.fabric.policies.awayLight.condition"),
        decision: "ask",
        rationale: t("consoleData.fabric.policies.awayLight.rationale"),
      },
      {
        id: "policy-away-ac",
        modeId: "away",
        roomId: "bedroom",
        target: t("consoleData.fabric.policies.awayAc.target"),
        condition: t("consoleData.fabric.policies.awayAc.condition"),
        decision: "always",
        rationale: t("consoleData.fabric.policies.awayAc.rationale"),
      },
      {
        id: "policy-away-purifier",
        modeId: "away",
        roomId: "studio",
        target: t("consoleData.fabric.policies.awayPurifier.target"),
        condition: t("consoleData.fabric.policies.awayPurifier.condition"),
        decision: "ask",
        rationale: t("consoleData.fabric.policies.awayPurifier.rationale"),
      },
      {
        id: "policy-away-pet",
        modeId: "away",
        roomId: "pet",
        target: t("consoleData.fabric.policies.awayPet.target"),
        condition: t("consoleData.fabric.policies.awayPet.condition"),
        decision: "never",
        rationale: t("consoleData.fabric.policies.awayPet.rationale"),
      },
      {
        id: "policy-home-light",
        modeId: "home",
        roomId: "living",
        target: t("consoleData.fabric.policies.homeLight.target"),
        condition: t("consoleData.fabric.policies.homeLight.condition"),
        decision: "always",
        rationale: t("consoleData.fabric.policies.homeLight.rationale"),
      },
      {
        id: "policy-home-purifier",
        modeId: "home",
        roomId: "studio",
        target: t("consoleData.fabric.policies.homePurifier.target"),
        condition: t("consoleData.fabric.policies.homePurifier.condition"),
        decision: "ask",
        rationale: t("consoleData.fabric.policies.homePurifier.rationale"),
      },
      {
        id: "policy-sleep-light",
        modeId: "sleep",
        roomId: "living",
        target: t("consoleData.fabric.policies.sleepLight.target"),
        condition: t("consoleData.fabric.policies.sleepLight.condition"),
        decision: "always",
        rationale: t("consoleData.fabric.policies.sleepLight.rationale"),
      },
      {
        id: "policy-sleep-ac",
        modeId: "sleep",
        roomId: "bedroom",
        target: t("consoleData.fabric.policies.sleepAc.target"),
        condition: t("consoleData.fabric.policies.sleepAc.condition"),
        decision: "ask",
        rationale: t("consoleData.fabric.policies.sleepAc.rationale"),
      },
    ],
    deviceAlerts: [
      {
        id: "alert-living-light",
        roomId: "living",
        severity: "medium",
        title: t("consoleData.fabric.alerts.livingLight.title"),
        body: t("consoleData.fabric.alerts.livingLight.body"),
        recommendation: t("consoleData.fabric.alerts.livingLight.recommendation"),
      },
      {
        id: "alert-studio-air",
        roomId: "studio",
        severity: "low",
        title: t("consoleData.fabric.alerts.studioAir.title"),
        body: t("consoleData.fabric.alerts.studioAir.body"),
        recommendation: t("consoleData.fabric.alerts.studioAir.recommendation"),
      },
      {
        id: "alert-pet-water",
        roomId: "pet",
        severity: "high",
        title: t("consoleData.fabric.alerts.petWater.title"),
        body: t("consoleData.fabric.alerts.petWater.body"),
        recommendation: t("consoleData.fabric.alerts.petWater.recommendation"),
      },
    ],
    missions: [
      {
        id: "mission-movie",
        title: t("consoleData.missions.movie.title"),
        summary: t("consoleData.missions.movie.summary"),
        status: "pending",
        risk: "high",
        source: "WeChat / @edison",
        createdAt: "14:08",
        rawMessage: t("consoleData.missions.movie.message"),
        intent: t("consoleData.missions.movie.intent"),
        commandPreview: "gemini -p \"search sci-fi sources, evaluate download options, prepare local folder plan\" --yolo",
        suggestedReply: t("consoleData.missions.movie.reply"),
        context: [
          t("consoleData.missions.movie.context.1"),
          t("consoleData.missions.movie.context.2"),
          t("consoleData.missions.movie.context.3"),
        ],
        plan: [
          t("consoleData.missions.movie.plan.1"),
          t("consoleData.missions.movie.plan.2"),
          t("consoleData.missions.movie.plan.3"),
        ],
        timeline: [
          {
            id: "movie-t1",
            time: "14:08",
            message: t("consoleData.missions.movie.timeline.1"),
          },
          {
            id: "movie-t2",
            time: "14:08",
            message: t("consoleData.missions.movie.timeline.2"),
          },
        ],
      },
      {
        id: "mission-weather",
        title: t("consoleData.missions.weather.title"),
        summary: t("consoleData.missions.weather.summary"),
        status: "approved",
        risk: "low",
        source: "WeChat / @edison",
        createdAt: "13:40",
        rawMessage: t("consoleData.missions.weather.message"),
        intent: t("consoleData.missions.weather.intent"),
        commandPreview: "curl wttr.in/Shanghai?format=j1",
        suggestedReply: t("consoleData.missions.weather.reply"),
        context: [
          t("consoleData.missions.weather.context.1"),
          t("consoleData.missions.weather.context.2"),
        ],
        plan: [
          t("consoleData.missions.weather.plan.1"),
          t("consoleData.missions.weather.plan.2"),
        ],
        timeline: [
          {
            id: "weather-t1",
            time: "13:41",
            message: t("consoleData.missions.weather.timeline.1"),
          },
          {
            id: "weather-t2",
            time: "13:42",
            message: t("consoleData.missions.weather.timeline.2"),
          },
        ],
      },
      {
        id: "mission-cleanup",
        title: t("consoleData.missions.cleanup.title"),
        summary: t("consoleData.missions.cleanup.summary"),
        status: "pending",
        risk: "high",
        source: "WeChat / @edison",
        createdAt: "12:25",
        rawMessage: t("consoleData.missions.cleanup.message"),
        intent: t("consoleData.missions.cleanup.intent"),
        commandPreview: "find ~/Downloads -name '*.tmp' -mtime +3 -delete",
        suggestedReply: t("consoleData.missions.cleanup.reply"),
        context: [
          t("consoleData.missions.cleanup.context.1"),
          t("consoleData.missions.cleanup.context.2"),
        ],
        plan: [
          t("consoleData.missions.cleanup.plan.1"),
          t("consoleData.missions.cleanup.plan.2"),
          t("consoleData.missions.cleanup.plan.3"),
        ],
        timeline: [
          {
            id: "cleanup-t1",
            time: "12:25",
            message: t("consoleData.missions.cleanup.timeline.1"),
          },
          {
            id: "cleanup-t2",
            time: "12:26",
            message: t("consoleData.missions.cleanup.timeline.2"),
          },
        ],
      },
      {
        id: "mission-purifier",
        title: t("consoleData.missions.purifier.title"),
        summary: t("consoleData.missions.purifier.summary"),
        status: "approved",
        risk: "medium",
        source: t("consoleData.sources.system"),
        createdAt: "09:15",
        rawMessage: t("consoleData.missions.purifier.message"),
        intent: t("consoleData.missions.purifier.intent"),
        commandPreview: "mijia.set(device='purifier_living_room', property='power', value='on')",
        suggestedReply: t("consoleData.missions.purifier.reply"),
        context: [
          t("consoleData.missions.purifier.context.1"),
          t("consoleData.missions.purifier.context.2"),
        ],
        plan: [
          t("consoleData.missions.purifier.plan.1"),
          t("consoleData.missions.purifier.plan.2"),
        ],
        timeline: [
          {
            id: "purifier-t1",
            time: "09:15",
            message: t("consoleData.missions.purifier.timeline.1"),
          },
          {
            id: "purifier-t2",
            time: "09:16",
            message: t("consoleData.missions.purifier.timeline.2"),
          },
        ],
      },
      {
        id: "mission-light",
        title: t("consoleData.missions.light.title"),
        summary: t("consoleData.missions.light.summary"),
        status: "failed",
        risk: "medium",
        source: t("consoleData.sources.devices"),
        createdAt: "07:48",
        rawMessage: t("consoleData.missions.light.message"),
        intent: t("consoleData.missions.light.intent"),
        commandPreview: "mijia.set(device='living_room_light', property='power', value='off')",
        suggestedReply: t("consoleData.missions.light.reply"),
        context: [
          t("consoleData.missions.light.context.1"),
          t("consoleData.missions.light.context.2"),
        ],
        plan: [
          t("consoleData.missions.light.plan.1"),
          t("consoleData.missions.light.plan.2"),
        ],
        timeline: [
          {
            id: "light-t1",
            time: "07:48",
            message: t("consoleData.missions.light.timeline.1"),
          },
          {
            id: "light-t2",
            time: "07:49",
            message: t("consoleData.missions.light.timeline.2"),
          },
        ],
      },
    ],
  };
}
