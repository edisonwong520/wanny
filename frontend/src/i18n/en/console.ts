export default {
  console: {
    nav: {
      overview: "Overview",
      tasks: "Tasks",
      devices: "Devices",
      manage: "Manage",
    },
    topbar: {
      mode: "Current mode: Away",
    },
  },
  overview: {
    title: "Overview",
    actions: {
      tasks: "Go to tasks",
      devices: "View details",
      authorize: "Authorize Service",
    },
    metrics: {
      online: "Online",
      offline: "Offline",
      tasks: "Pending Tasks",
    },
    empty: {
      auth: "No authorized platforms yet",
      sync: "Authorized but no device data, waiting for sync",
      noEvents: "Running normally, no abnormal activity",
    },
    sections: {
      events: "Recent Activity",
      viewAll: "View All",
    },
    events: {
      offline: "{name} is offline",
    },
  },
  missions: {
    title: "Tasks",
    filters: {
      pending: "Pending",
      approved: "Approved",
      failed: "Failed",
      all: "All",
    },
    metrics: {
      pending: "Pending",
      approved: "Approved",
      failed: "Failed",
      highRisk: "High Risk",
    },
    status: {
      pending: "Pending",
      approved: "Approved",
      failed: "Failed",
    },
    risk: {
      high: "High risk",
      medium: "Medium",
      low: "Low",
    },
    actions: {
      approve: "Approve",
      reject: "Reject",
      inspect: "Inspect",
    },
    detail: {
      created: "Time",
      source: "Source",
      userMessage: "User Message",
      intent: "What Wanny understands",
      command: "What will run",
      plan: "Steps",
      context: "Extra context",
      reply: "Reply preview",
      timeline: "History",
    },
    timeline: {
      approved: "You approved this task.",
      rejected: "You rejected this task.",
    },
    empty: "There are no tasks under the current filter.",
  },
  devices: {
    title: "Devices",
    loading: "Loading cached device snapshot...",
    allRoomsSummary: "Review device snapshots, anomalies and automation rules across every room.",
    filters: {
      all: "All",
    },
    metrics: {
      online: "Online devices",
      attention: "Needs attention",
      anomalies: "Anomalies",
      rooms: "Rooms",
    },
    sections: {
      rooms: "Rooms",
      devices: "Devices",
      detail: "Current Device",
      modes: "Home Modes",
      policies: "Auto Rules",
      anomalies: "Anomalies",
    },
    status: {
      online: "Online",
      attention: "Watch",
      offline: "Offline",
    },
    decisions: {
      ask: "Confirm first",
      always: "Auto run",
      never: "Do not auto run",
    },
    severity: {
      high: "HIGH",
      medium: "MEDIUM",
      low: "LOW",
    },
    meta: {
      devices: "devices",
      alerts: "alerts",
    },
    detail: {
      room: "Room",
      category: "Category",
      lastSeen: "Last Seen",
      telemetry: "Current State",
      note: "Notes",
      capabilities: "Capabilities",
    },
    mode: {
      label: "Current Mode",
      changedAt: "Changed At",
    },
    anomaly: {
      recommendation: "Recommended Action",
    },
    sync: {
      initializing: "The worker is preparing the first device snapshot. This page will update automatically.",
      pending: "The worker is refreshing the device snapshot. This page will update automatically.",
      empty: "There is no device snapshot to display yet.",
      error: "The most recent device sync failed.",
    },
    empty: {
      noDevices: "No devices found",
      devices: "There are no devices under the current room filter.",
      policies: "There are no policies for the current mode and room.",
      anomalies: "There are no anomalies to handle right now.",
    },
    errors: {
      load: "Unable to load device dashboard data. Please try again.",
    },
  },
  manage: {
    title: "Manage",
    summary: "Review provider authorization status, rebind flows and the latest active session from one place.",
    badges: {
      memory: "Memory and preferences",
      safety: "Safety and permissions",
    },
    metrics: {
      preferences: "Saved preferences",
      suggestions: "Suggestion logs",
      risky: "Risky actions waiting",
      blocks: "Recent blocks",
    },
    memory: {
      label: "Memory",
      title: "What Wanny remembers",
      items: {
        a: "Review saved preferences like temperature, air quality and favorite device settings.",
        b: "Check the latest suggestions the system prepared and decide what should stay.",
        c: "Later you can edit or remove inaccurate records here.",
      },
    },
    safety: {
      label: "Safety",
      title: "Safety and permissions",
      items: {
        a: "Risky actions ask first by default, such as deleting files or making large local changes.",
        b: "This area keeps a recent list of blocked actions and why they were stopped.",
        c: "Later you can decide which actions may run automatically and which must always ask.",
      },
    },
    events: {
      label: "Logs",
      title: "Recent management records",
    },
    auth: {
      title: "Platform Authorization",
      loading: "Loading provider status and active authorization sessions...",
      empty: "There are no providers available to manage right now.",
      actions: {
        connect: "Start Authorization",
        viewSession: "View Authorization",
        disconnect: "Disconnect",
        openLink: "Open Link",
      },
      providerStatus: {
        connected: "Connected",
        not_connected: "Not connected",
        disabled: "Disabled",
        pending: "Pending",
      },
      sessionStatus: {
        idle: "Idle",
        pending: "Waiting for scan",
        scanned: "Scanned, waiting for confirmation",
        completed: "Completed",
        expired: "Expired",
        failed: "Failed",
      },
      errors: {
        load: "Unable to load provider authorization state. Please try again.",
        action: "The authorization action failed. Please check backend logs.",
      },
      confirmDisconnect: "Disconnect authorization for this provider?",
      wechatHint: "Due to WeChat restrictions, open the link below to scan and authorize, then return to this page.",
    },
  },
  memory: {
    eyebrow: "Memory Atlas",
    title: "Browse semantic recall, user profiles and proactive care logs",
    summary:
      "This page is the memory observation deck for Jarvis. The owner should see what the system remembers and how those memories shape behavior.",
    items: {
      a: "Semantic recall browser: inspect vector memory hits by time, source and keyword.",
      b: "Profile panel: inspect UserProfile categories, values, confidence and confirmation time.",
      c: "Proactive care logs: inspect ProactiveLog messages, scores and user feedback.",
    },
  },
  guard: {
    eyebrow: "Guard Rails",
    title: "Manage approval gates, risky commands and system audit in one place",
    summary:
      "Guard Rails should become the place where the owner understands Jarvis boundaries, especially for local self-hosted deployments.",
    items: {
      a: "Approval strategy panel: which task types still require manual confirmation and which may later become semi-automatic.",
      b: "Blocked command history: what was intercepted recently and why it was stopped.",
      c: "Execution audit: who approved what, when it ran, what happened and whether it needs a retry.",
    },
  },
  consoleData: {
    events: {
      1: {
        title: "A new task is waiting",
        body: "This task will search online and change local files, so it was moved into Tasks for approval.",
      },
      2: {
        title: "A device issue was found",
        body: "The living room light is still on in Away mode, so it is worth checking on the Devices page.",
      },
      3: {
        title: "New preference suggestions were prepared",
        body: "Manage now includes 2 new suggestions for you to review and keep if helpful.",
      },
      4: {
        title: "A risky action was blocked",
        body: "The system stopped a local delete action and is waiting for your decision.",
      },
    },
    sources: {
      system: "System suggestion",
      devices: "Device status",
    },
    fabric: {
      modes: {
        away: {
          label: "Away",
          summary: "When the owner is out, Jarvis should prioritize safety, energy savings and anomaly detection while keeping critical actions visible.",
        },
        home: {
          label: "Home",
          summary: "When the owner is home, device behavior should lean toward comfort and companionship without becoming opaque.",
        },
        sleep: {
          label: "Sleep",
          summary: "Night mode should be quieter and more conservative, with fewer interruptions and fewer unnecessary actions.",
        },
      },
      rooms: {
        living: {
          name: "Living Room",
          climate: "26°C / 58% RH",
          summary: "The living room currently carries a lighting anomaly, so it is the best place to inspect Away-mode behavior.",
        },
        bedroom: {
          name: "Bedroom",
          climate: "24°C / Auto",
          summary: "The bedroom climate is stable, which makes it a good candidate for gradual automation upgrades.",
        },
        studio: {
          name: "Studio",
          climate: "AQI 82 / Slightly poor",
          summary: "Air quality is slipping in the studio, so purifier policy behavior deserves close attention.",
        },
        pet: {
          name: "Pet Corner",
          climate: "Water reserve 18%",
          summary: "Pet-care devices should stay conservative. Any power-off action should remain safety-first.",
        },
      },
      devices: {
        livingLight: {
          name: "Living room light",
          category: "Lighting",
          telemetry: "Power on / 68% brightness",
          note: "The light is still on in Away mode, which exposes a gap between policy suggestion and real-world execution.",
          capabilities: {
            1: "Brightness control",
            2: "Scene automation",
          },
        },
        entrySensor: {
          name: "Entry sensor",
          category: "Sensor",
          telemetry: "Door closed / idle",
          note: "The door sensor is healthy and remains a key signal for validating Away-mode assumptions.",
          capabilities: {
            1: "Open-close detection",
            2: "Presence orchestration",
          },
        },
        bedroomAc: {
          name: "Bedroom AC",
          category: "Climate",
          telemetry: "24°C / Auto mode",
          note: "The AC is behaving predictably, which makes bedroom climate policies a strong candidate for finer automation.",
          capabilities: {
            1: "Temperature setpoint",
            2: "Fan mode control",
          },
        },
        studioPurifier: {
          name: "Studio purifier",
          category: "Air Care",
          telemetry: "AQI 82 / Auto",
          note: "The purifier is online, but air quality is trending down. Proactive care may need to trigger earlier here.",
          capabilities: {
            1: "Air quality sensing",
            2: "Automatic purification",
          },
        },
        petFountain: {
          name: "Pet fountain",
          category: "Pet Care",
          telemetry: "Water reserve 18%",
          note: "The last heartbeat is getting old, so low-water reminders and connectivity should be surfaced together.",
          capabilities: {
            1: "Low water reminder",
            2: "Runtime monitoring",
          },
        },
      },
      policies: {
        awayLight: {
          target: "Living room light / power",
          condition: "Away mode lasts for 10 minutes and brightness is still above zero.",
          rationale: "This remains ASK because lighting behavior can still carry owner intent right before leaving.",
        },
        awayAc: {
          target: "Bedroom AC / power",
          condition: "Away mode lasts for 20 minutes and no bedroom activity is detected.",
          rationale: "This rule is a good candidate for ALWAYS because the downside is low and the energy savings are clear.",
        },
        awayPurifier: {
          target: "Studio purifier / power",
          condition: "The owner is away and AQI climbs above 75.",
          rationale: "The purifier still stays on ASK to avoid unnecessary long runs while the owner is out.",
        },
        awayPet: {
          target: "Pet fountain / power",
          condition: "Automatic shutdown is forbidden during the pet-care window.",
          rationale: "Any pet-safety device should default to NEVER power off unless the owner explicitly overrides the rule.",
        },
        homeLight: {
          target: "Living room light / brightness",
          condition: "After sunset, set comfort brightness to 45% when the owner is home.",
          rationale: "This is low-risk and high-touch, so Home mode can safely treat it as ALWAYS.",
        },
        homePurifier: {
          target: "Studio purifier / power",
          condition: "Studio AQI rises above 75 while the owner is actively in the room.",
          rationale: "When the owner is present, ASK keeps proactive care legible instead of invisible.",
        },
        sleepLight: {
          target: "Living room light / power",
          condition: "After 00:30, no living-room activity remains in Sleep mode.",
          rationale: "Night-time light shutdown is predictable and low risk, so ALWAYS is appropriate here.",
        },
        sleepAc: {
          target: "Bedroom AC / target temperature",
          condition: "Shift the target temperature to 25°C when the sleep routine begins.",
          rationale: "Temperature preferences can drift by season, so ASK remains the safer choice for now.",
        },
      },
      alerts: {
        livingLight: {
          title: "The living room light is still on in Away mode",
          body: "Jarvis identified this as a low-stakes energy correction, but the current policy still requires owner confirmation.",
          recommendation: "Jump into Mission Desk, approve a one-off shutdown, then decide whether this rule should be promoted.",
        },
        studioAir: {
          title: "Studio air quality is trending down",
          body: "AQI has entered a mild anomaly zone. The purifier is online, but proactive care has not escalated yet.",
          recommendation: "Review the purifier threshold and consider moving studio AQI alerts one step earlier.",
        },
        petWater: {
          title: "The pet fountain has low water and a stale heartbeat",
          body: "The latest device report is old enough that water level and connectivity should now be checked together.",
          recommendation: "Confirm water and power first, then decide whether the device needs to be re-paired or replaced.",
        },
      },
    },
    missions: {
      movie: {
        title: "Download and organize sci-fi movie resources",
        summary: "The plan includes network search, source evaluation and local writes, so the task is still pending approval.",
        message: "Find a few new sci-fi movie resources for me and organize them into my downloads folder.",
        intent: "The task requires network search, ranking candidate sources, preparing a local folder plan and possibly renaming files.",
        reply: "Sir, I have prepared an execution plan. I need your approval before network search and file operations begin.",
        context: {
          1: "The owner mentioned wanting new sci-fi movies several times this week.",
          2: "The system has already handled media organization tasks, so a folder convention exists.",
          3: "Because this task writes local files, it still needs your approval first.",
        },
        plan: {
          1: "Search and list candidate sources first instead of downloading immediately.",
          2: "Confirm the target directory and prepare a clear naming plan.",
          3: "Only after approval should the download and organization flow begin.",
        },
        timeline: {
          1: "WeChat received the request and started complex-task classification.",
          2: "The system detected online search and file writes, so the task moved into the approval queue.",
        },
      },
      weather: {
        title: "Query tomorrow's Shanghai weather and send a summary",
        summary: "This low-risk information task is already approved and can return a structured reply.",
        message: "Check tomorrow's Shanghai weather and tell me if I should bring an umbrella.",
        intent: "This is a low-risk information task that should request weather data and summarize it in plain language.",
        reply: "Tomorrow in Shanghai there is a chance of rain, so bringing an umbrella is recommended.",
        context: {
          1: "Weather lookups usually do not need strict approval, but replay is still valuable.",
          2: "The owner prefers concise, conclusion-first replies.",
        },
        plan: {
          1: "Call the weather service and retrieve hourly weather data for tomorrow.",
          2: "Summarize rain probability, temperature range and umbrella advice.",
        },
        timeline: {
          1: "The owner approved the task and Jarvis started the weather request.",
          2: "The query finished and the final response draft is ready for WeChat.",
        },
      },
      cleanup: {
        title: "Clean temporary files in the downloads folder",
        summary: "The task implies local deletion, so it still requires explicit owner approval each time.",
        message: "Delete temporary files older than 3 days in the downloads folder, but do not remove the wrong files.",
        intent: "The task will scan a local directory and delete files. The main risks are wrong path judgment and accidental deletion.",
        reply: "Sir, this action involves local file deletion. I have prepared the cleanup scope and need your approval first.",
        context: {
          1: "The owner explicitly emphasized safety over speed by saying not to delete the wrong files.",
          2: "Delete actions still require the strictest confirmation.",
        },
        plan: {
          1: "List candidate files first instead of deleting immediately.",
          2: "Show file counts, sample paths and time-based filters.",
          3: "Only execute the real deletion after approval.",
        },
        timeline: {
          1: "The task entered the approval queue.",
          2: "The system prepared a deletion preview and requested confirmation.",
        },
      },
      purifier: {
        title: "Start the air purifier based on air quality",
        summary: "This proactive-care task was accepted, executed successfully and recorded into memory.",
        message: "Indoor air quality dropped. Should I turn on the air purifier for you?",
        intent: "This is a semi-automatic proactive-care task that combines environment judgment and device control.",
        reply: "Sir, the air purifier is now on and I will continue to monitor the environment.",
        context: {
          1: "The owner has approved purifier activation multiple times under poor air quality.",
          2: "The suggestion matched an environment preference in the user profile.",
        },
        plan: {
          1: "Confirm both home presence and degraded air quality.",
          2: "After approval, execute device control and record the feedback loop.",
        },
        timeline: {
          1: "The proactive-care engine generated a suggestion and sent it to the owner.",
          2: "The owner approved it, the device action succeeded and the result was saved in history.",
        },
      },
      light: {
        title: "Try to turn off the living room light in Away mode",
        summary: "The judgment was valid, but the execution chain failed and now needs manual diagnosis.",
        message: "The living room light is still on in Away mode. Try turning it off.",
        intent: "This is a device-correction task with a clear target, but the failure means device or authorization status should be checked.",
        reply: "Sir, I tried to turn off the living room light but it failed. Please inspect device connectivity or retry later.",
        context: {
          1: "The current rule for the living room light still asks before acting.",
          2: "The device may have gone briefly offline, or the provider returned an invalid state.",
        },
        plan: {
          1: "Confirm the policy still allows the action.",
          2: "Call the device-control interface and capture the provider response.",
        },
        timeline: {
          1: "The system detected that the living room light remained on in Away mode.",
          2: "The off action failed and the task now needs manual handling.",
        },
      },
    },
  },
};
