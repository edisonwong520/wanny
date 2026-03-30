import { createI18n } from "vue-i18n";

const messages = {
  "zh-CN": {
    brand: {
      subtitle: "Jarvis Control Surface",
    },
    nav: {
      console: "控制台",
      landing: "宣传页",
    },
    landing: {
      eyebrow: "Home Agent / Shell / Memory",
      titleLead: "把微信、设备、长期记忆和 Shell 执行，",
      titleAccent: "收拢到一个 Jarvis 中枢",
      summary:
        "Wanny 让你通过一个控制界面管理家庭自动化、主动关怀、任务审批与语义记忆。今天先做一个入口页，下一阶段重点落到 Console。",
      primary: "进入 Jarvis Console",
      secondary: "查看控制蓝图",
      chips: {
        safety: "审批门禁",
        memory: "长期记忆",
        shell: "Shell 代理",
      },
      statA: {
        label: "运营模式",
        value: "Manual Gate",
      },
      statB: {
        label: "Memory Layer",
        value: "Vector + Profile",
      },
      statC: {
        label: "Device Fabric",
        value: "Mijia Live",
      },
      preview: {
        title: "今日总控预览",
        status: "系统在线，等待新的审批与调度。",
        line1: "queue.approvals = 3",
        line2: "memory.recall = semantic",
        line3: "shell.mode = guarded",
      },
      capabilityTitle: "这个入口页之后，Console 会接手什么",
      capabilityA: {
        title: "实时编排",
        body: "在一个界面里看到设备状态、告警、授权动作和自动化建议。",
      },
      capabilityB: {
        title: "任务门禁",
        body: "把复杂 Shell 执行放进可回放、可批准、可追踪的控制流。",
      },
      capabilityC: {
        title: "长期记忆",
        body: "把对话、偏好与环境线索沉淀成能被调用的 Jarvis 记忆层。",
      },
      blueprintTitle: "Console 的第一版信息架构",
      blueprintA: {
        title: "Mission Desk",
        body: "管理来自微信的指令、审批队列与执行日志。",
      },
      blueprintB: {
        title: "Device Fabric",
        body: "汇总设备拓扑、房间状态、规则矩阵与异常事件。",
      },
      blueprintC: {
        title: "Memory Atlas",
        body: "浏览语义记忆、结构化画像与主动建议引擎的命中记录。",
      },
      footer: "下一步，我们会把这里的预览卡片换成真实的 Jarvis Console。",
    },
    console: {
      nav: {
        overview: "总览",
        tasks: "任务",
        devices: "设备",
        manage: "管理",
      },
      topbar: {
        mode: "当前模式：离家",
      },
    },
    overview: {
      title: "总览",
      actions: {
        tasks: "查看任务",
        devices: "查看设备",
      },
      health: {
        bot: "微信",
        monitor: "设备",
        review: "复盘",
        memory: "记忆",
      },
      metrics: {
        components: "组件状态",
        tasks: "执行任务情况",
        suggestions: "建议数量",
        anomalies: "异常事件",
        devices: "关联设备数",
      },
      values: {
        components: "当前可用",
        tasks: "{approved} 完成",
      },
      notes: {
        components: "全部正常",
        tasks: "{pending} 待处理 · {failed} 异常",
        suggestions: "今天新增建议",
        anomalies: "需要关注",
        devices: "覆盖 {rooms} 个房间",
      },
      sections: {
        components: "组件状态",
        events: "最近动态",
        shortcuts: "常用入口",
      },
      events: {
        title: "最近动态",
        link: "打开管理",
      },
      mode: {
        label: "当前模式",
        value: "离家",
        note: "高风险操作仍需确认。",
      },
      links: {
        tasks: "去任务页",
        devices: "去设备页",
        manage: "去管理页",
      },
    },
    missions: {
      title: "任务",
      filters: {
        pending: "待审批",
        approved: "已通过",
        failed: "异常",
        all: "全部",
      },
      metrics: {
        pending: "待审批",
        approved: "已通过",
        failed: "异常",
        highRisk: "高风险",
      },
      status: {
        pending: "待审批",
        approved: "已通过",
        failed: "异常",
      },
      risk: {
        high: "高风险",
        medium: "中风险",
        low: "低风险",
      },
      actions: {
        approve: "批准",
        reject: "拒绝",
        inspect: "查看",
      },
      detail: {
        created: "时间",
        source: "来源",
        userMessage: "用户消息",
        intent: "系统理解",
        command: "执行内容",
        plan: "处理步骤",
        context: "参考信息",
        reply: "回复预览",
        timeline: "处理记录",
      },
      timeline: {
        approved: "你已批准这个任务。",
        rejected: "你已拒绝这个任务。",
      },
      empty: "当前筛选条件下没有任务。",
    },
    devices: {
      title: "设备",
      loading: "正在读取设备快照...",
      allRoomsSummary: "查看所有房间的设备快照、异常事件和自动化规则。",
      filters: {
        all: "全部房间",
      },
      metrics: {
        online: "在线设备",
        attention: "需关注设备",
        anomalies: "异常事件",
        rooms: "房间",
      },
      sections: {
        rooms: "房间",
        devices: "设备列表",
        detail: "当前设备",
        modes: "家居模式",
        policies: "自动规则",
        anomalies: "异常事件",
      },
      status: {
        online: "在线",
        attention: "留意",
        offline: "离线",
      },
      decisions: {
        ask: "需确认",
        always: "自动执行",
        never: "不自动执行",
      },
      severity: {
        high: "高",
        medium: "中",
        low: "低",
      },
      meta: {
        devices: "台设备",
        alerts: "条异常",
      },
      detail: {
        room: "房间",
        category: "类型",
        lastSeen: "最近更新时间",
        telemetry: "当前状态",
        note: "说明",
        capabilities: "可用功能",
      },
      mode: {
        label: "当前模式",
        changedAt: "切换时间",
      },
      anomaly: {
        recommendation: "建议处理",
      },
      sync: {
        initializing: "后台 worker 正在准备第一份设备快照，页面会自动更新。",
        pending: "后台 worker 正在刷新设备快照，页面会自动更新。",
        empty: "还没有可展示的设备快照。",
        error: "最近一次设备同步失败。",
      },
      empty: {
        devices: "当前房间筛选下没有设备。",
        policies: "当前模式和房间下没有策略规则。",
        anomalies: "当前没有需要处理的异常。",
      },
      errors: {
        load: "读取设备页数据失败，请稍后重试。",
      },
    },
    manage: {
      title: "管理",
      summary: "统一查看与维护微信和小米的授权状态、重新绑定流程以及最新会话。",
      badges: {
        memory: "记忆与偏好",
        safety: "安全与权限",
      },
      metrics: {
        preferences: "已记录偏好",
        suggestions: "建议记录",
        risky: "待确认风险操作",
        blocks: "最近拦截",
      },
      memory: {
        label: "记忆",
        title: "记住的内容",
        items: {
          a: "查看最近记住的偏好，比如温度、空气质量和常用设备设置。",
          b: "查看系统最近整理出的建议，确认哪些值得保留。",
          c: "以后可以在这里手动修改或删除不准确的记录。",
        },
      },
      safety: {
        label: "安全",
        title: "安全与权限",
        items: {
          a: "高风险操作默认先确认，比如删除文件或批量改动本地内容。",
          b: "这里会记录最近被拦下来的操作，方便你回看原因。",
          c: "以后可以在这里设置哪些动作允许自动执行，哪些必须先问你。",
        },
      },
      events: {
        label: "记录",
        title: "最近管理记录",
      },
      auth: {
        title: "平台授权",
        loading: "正在读取授权状态与当前会话...",
        empty: "当前还没有可管理的平台。",
        actions: {
          connect: "开始授权",
          viewSession: "查看授权",
          disconnect: "断开授权",
          openLink: "打开链接",
        },
        providerStatus: {
          connected: "已连接",
          not_connected: "未连接",
          disabled: "已停用",
          pending: "待完成",
        },
        sessionStatus: {
          idle: "尚未发起",
          pending: "等待扫码",
          scanned: "已扫码待确认",
          completed: "授权完成",
          expired: "已过期",
          failed: "授权失败",
        },
        errors: {
          load: "读取授权状态失败，请稍后重试。",
          action: "授权操作失败，请检查后端日志。",
        },
        confirmDisconnect: "确认断开这个平台的授权吗？",
        wechatHint: "由于微信限制，请打开以下链接扫码授权，结束后请返回此页面。",
      },
    },
    memory: {
      eyebrow: "Memory Atlas",
      title: "浏览语义记忆、画像偏好与主动关怀日志",
      summary:
        "这一屏会成为 Jarvis 的记忆观察台。主人需要看见系统记住了什么，以及这些记忆如何影响决策和主动建议。",
      items: {
        a: "语义记忆浏览器：按时间、来源与关键词查看向量记忆命中记录。",
        b: "画像面板：展示 UserProfile 的类别、键值、置信度与最后确认时间。",
        c: "主动关怀日志：展示 ProactiveLog 的消息内容、评分与反馈结果。",
      },
    },
    guard: {
      eyebrow: "Guard Rails",
      title: "把审批门禁、风险命令与系统审计集中管理",
      summary:
        "Guard Rails 不只是一个安全提示页，它应该成为主人理解 Jarvis 边界的地方，尤其是在本地自部署场景中。",
      items: {
        a: "审批策略面板：当前哪些任务类型强制人工确认，哪些未来可以升级为半自动。",
        b: "风险命令与阻断记录：最近哪些动作被拦截、为什么被拦截。",
        c: "执行审计：谁批准了什么、什么时候执行、结果如何、是否需要重试。",
      },
    },
    consoleData: {
      events: {
        1: {
          title: "有新任务等待处理",
          body: "这个任务会联网搜索并改动本地文件，所以先放到了任务页等你确认。",
        },
        2: {
          title: "发现设备异常",
          body: "客厅灯在离家模式下还开着，建议你去设备页看一下。",
        },
        3: {
          title: "系统整理了新的偏好建议",
          body: "管理页里新增了 2 条建议，方便你确认哪些需要保留。",
        },
        4: {
          title: "拦下了一次高风险操作",
          body: "系统拦住了一个会删除本地文件的操作，正在等你决定。",
        },
      },
      sources: {
        system: "系统建议",
        devices: "设备状态",
      },
      fabric: {
        modes: {
          away: {
            label: "离家",
            summary: "主人离家时，Jarvis 应优先关注节能、安全与异常提醒，但仍保留关键动作的人类确认。",
          },
          home: {
            label: "在家",
            summary: "主人在家时，设备更偏向舒适和陪伴场景，策略可以更主动但仍需要可见性。",
          },
          sleep: {
            label: "睡眠",
            summary: "夜间模式应该更安静、更克制，默认压低提醒强度，并减少非必要动作。",
          },
        },
        rooms: {
          living: {
            name: "客厅",
            climate: "26°C / 58% RH",
            summary: "客厅目前有一条照明异常，适合作为 Away 模式下的重点观察区域。",
          },
          bedroom: {
            name: "主卧",
            climate: "24°C / Auto",
            summary: "主卧环境稳定，空调策略可以逐步从手动确认走向更强的自动化。",
          },
          studio: {
            name: "书房",
            climate: "AQI 82 / 稍差",
            summary: "书房空气质量开始下滑，净化器相关策略值得优先观察。",
          },
          pet: {
            name: "宠物角",
            climate: "饮水余量 18%",
            summary: "宠物区域不适合激进自动化，任何断电或停泵动作都应以安全优先。",
          },
        },
        devices: {
          livingLight: {
            name: "客厅灯",
            category: "灯光",
            telemetry: "已开 / 68% 亮度",
            note: "离家模式下客厅灯仍亮着，说明建议动作和真实执行之间还有落差。",
            capabilities: {
              1: "亮度控制",
              2: "场景联动",
            },
          },
          entrySensor: {
            name: "入户传感器",
            category: "传感器",
            telemetry: "门已关闭 / 空闲",
            note: "门磁在线且状态正常，是判断你是否离家的重要依据。",
            capabilities: {
              1: "开合检测",
              2: "离家联动",
            },
          },
          bedroomAc: {
            name: "主卧空调",
            category: "空调",
            telemetry: "24°C / 自动模式",
            note: "空调运行平稳，适合后续把 Home 与 Sleep 场景的温控策略做成更细粒度矩阵。",
            capabilities: {
              1: "温度设定",
              2: "风速模式",
            },
          },
          studioPurifier: {
            name: "书房净化器",
            category: "空气护理",
            telemetry: "AQI 82 / 自动挡",
            note: "净化器在线，但空气质量正在下降，说明主动关怀策略需要更早触发。",
            capabilities: {
              1: "空气质量监测",
              2: "自动净化",
            },
          },
          petFountain: {
            name: "宠物饮水机",
            category: "宠物照护",
            telemetry: "剩余水量 18%",
            note: "设备最近一次心跳较早，建议把低水位提醒和在线状态一起呈现给主人。",
            capabilities: {
              1: "低水位提醒",
              2: "运行状态监测",
            },
          },
        },
        policies: {
          awayLight: {
            target: "客厅灯 / 开关",
            condition: "离家 10 分钟后，客厅灯亮度仍大于 0。",
            rationale: "这条规则暂时还是先确认，因为可能是你离家前特意留下的灯光。",
          },
          awayAc: {
            target: "主卧空调 / 开关",
            condition: "离家 20 分钟后，卧室仍无人活动。",
            rationale: "这条规则适合逐步改成自动执行，因为误判成本较低且节能收益明确。",
          },
          awayPurifier: {
            target: "书房净化器 / 开关",
            condition: "主人离家且 AQI 高于 75。",
            rationale: "净化器先保持确认制，避免在你不在家时出现不必要的长时间运行。",
          },
          awayPet: {
            target: "宠物饮水机 / 开关",
            condition: "宠物照护时段内禁止自动关闭。",
            rationale: "涉及宠物安全的设备默认不自动关闭，除非你明确改规则。",
          },
          homeLight: {
            target: "客厅灯 / 亮度",
            condition: "日落后且主人在家时，自动切换到 45% 舒适亮度。",
            rationale: "这是低风险又很容易感知到的动作，适合在在家模式下自动执行。",
          },
          homePurifier: {
            target: "书房净化器 / 开关",
            condition: "书房 AQI 高于 75 且主人正在书房停留。",
            rationale: "你在场时，净化器更适合先提醒再执行，这样更容易理解系统为什么这么做。",
          },
          sleepLight: {
            target: "客厅灯 / 开关",
            condition: "睡眠模式下，00:30 之后客厅无活动。",
            rationale: "夜间关灯是可预测且低风险的动作，适合自动执行。",
          },
          sleepAc: {
            target: "主卧空调 / 目标温度",
            condition: "入睡流程开始后，将目标温度调整到 25°C。",
            rationale: "温度偏好会随季节变化，暂时继续先确认。",
          },
        },
        alerts: {
          livingLight: {
            title: "离家模式下客厅灯仍处于开启状态",
            body: "系统认为这是一个偏低风险的节能动作，但现在仍需要你确认。",
            recommendation: "去任务页批准一次关闭动作，然后再决定是否把这条规则改成自动执行。",
          },
          studioAir: {
            title: "书房空气质量正在下降",
            body: "AQI 已进入轻度异常区间，净化器虽在线，但主动关怀尚未自动触发。",
            recommendation: "检查净化器策略阈值，必要时把书房 AQI 告警提前一个等级。",
          },
          petWater: {
            title: "宠物饮水机低水位且心跳变旧",
            body: "设备最近上报时间变早，低水位提醒与设备在线性需要一起确认。",
            recommendation: "优先确认水量与供电，再决定是否需要重新配对或更换设备。",
          },
        },
      },
      missions: {
        movie: {
          title: "下载与整理科幻电影资源",
          summary: "计划联网搜索、评估下载源并写入本地目录，因此仍处于待审批状态。",
          message: "帮我找几部新的科幻电影资源，整理好之后放进我的下载目录里。",
          intent: "任务需要联网搜索、比较候选资源、生成下载目录方案，并可能触发本地写入与文件重命名。",
          reply: "Sir，我已经整理好了执行计划，需要您的批准后再开始联网搜索与文件处理。",
          context: {
            1: "最近一周主人多次提到周末想看新的科幻片。",
            2: "系统曾执行过媒体文件整理任务，因此目录结构已有既定习惯。",
            3: "因为会写入本地文件，这类任务现在还需要你确认。",
          },
          plan: {
            1: "先搜索候选资源并输出可信来源列表，不直接执行下载。",
            2: "确认目标目录存在，并生成清晰的命名与整理方案。",
            3: "拿到主人批准后，再进入下载与整理执行链路。",
          },
          timeline: {
            1: "微信收到任务请求，开始做复杂任务判定。",
            2: "系统判断这个任务会联网搜索并写入文件，所以先放进待审批队列。",
          },
        },
        weather: {
          title: "查询明日上海天气并推送总结",
          summary: "低风险查询任务已批准，后续可直接返回整理后的结果。",
          message: "帮我看一下明天上海天气，顺便告诉我要不要带伞。",
          intent: "这是低风险信息查询任务，主要动作是请求天气服务并用自然语言总结结果。",
          reply: "明天上海有阵雨概率，建议随身带伞，晚间风力较弱。",
          context: {
            1: "天气类查询通常不需要复杂审批，但仍应保留结果回放。",
            2: "主人偏好看到一段简洁、结论先行的自然语言总结。",
          },
          plan: {
            1: "请求天气服务，获取明日逐小时天气数据。",
            2: "整理出降雨概率、温度区间和是否建议带伞。",
          },
          timeline: {
            1: "主人已批准任务，Jarvis 开始执行天气查询。",
            2: "查询完成并生成了最终回复，等待回传到微信。",
          },
        },
        cleanup: {
          title: "清理下载目录中的临时文件",
          summary: "任务涉及本地删除行为，虽然目标明确，但仍需要主人逐次确认。",
          message: "把下载目录里 3 天前的临时文件清掉，别删错。",
          intent: "任务将扫描本地目录并触发删除动作，风险来自误删和路径判断错误。",
          reply: "Sir，这个动作会涉及本地文件删除。我已经生成清理范围，需要您先确认。",
          context: {
            1: "主人明确强调过“别删错”，说明安全感比执行速度更重要。",
            2: "删除类操作现在仍然需要最严格的确认。",
          },
          plan: {
            1: "先列出会被删除的候选文件，而不是直接删除。",
            2: "展示文件数量、路径样例和时间条件。",
            3: "获得主人批准后，才执行真正的删除动作。",
          },
          timeline: {
            1: "任务进入待审批队列。",
            2: "系统预生成了删除命令草案，并请求主人确认。",
          },
        },
        purifier: {
          title: "根据空气质量建议启动净化器",
          summary: "主动关怀任务已经被接受，设备动作执行成功并记录到记忆层。",
          message: "检测到室内空气质量下降，是否为您开启空气净化器？",
          intent: "这是由主动关怀引擎触发的半自动任务，涉及环境状态判断与设备控制。",
          reply: "Sir，空气净化器已经打开，我会继续观察后续空气质量变化。",
          context: {
            1: "主人此前多次在空气质量较差时同意打开净化器。",
            2: "该建议命中了用户画像中的环境偏好规则。",
          },
          plan: {
            1: "确认当前在家状态与空气质量异常同时成立。",
            2: "在主人批准后执行净化器开机，并记录反馈闭环。",
          },
          timeline: {
            1: "主动关怀引擎生成建议并发给主人。",
            2: "主人同意后，设备指令执行成功，并记录进系统历史。",
          },
        },
        light: {
          title: "Away 模式下尝试关闭客厅灯",
          summary: "动作判断正确，但执行链路出现异常，需要进一步排查设备或授权状态。",
          message: "Away 模式下客厅灯还开着，尝试替您关闭。",
          intent: "这是设备异常纠偏任务，目标明确，但执行失败意味着需要进入人工排障。",
          reply: "Sir，我尝试关闭客厅灯但未成功，建议您检查设备在线状态或稍后重试。",
          context: {
            1: "当前规则对客厅灯仍要求先确认。",
            2: "设备可能瞬时离线，或者第三方平台返回了错误状态。",
          },
          plan: {
            1: "先确认策略允许执行该动作。",
            2: "调用设备控制接口并记录响应结果。",
          },
          timeline: {
            1: "系统检测到 Away 模式下客厅灯仍然开启。",
            2: "执行关闭动作失败，已标记为需要人工处理。",
          },
        },
      },
    },
  },
  en: {
    brand: {
      subtitle: "Jarvis Control Surface",
    },
    nav: {
      console: "Console",
      landing: "Landing",
    },
    landing: {
      eyebrow: "Home Agent / Shell / Memory",
      titleLead: "Unify chat, devices, memory and shell execution",
      titleAccent: "into one Jarvis control surface",
      summary:
        "Wanny is a single interface for household automation, proactive care, guarded task execution and semantic memory. We start with a landing page, then move fast into the Console.",
      primary: "Open Jarvis Console",
      secondary: "See the blueprint",
      chips: {
        safety: "Approval Gate",
        memory: "Long Memory",
        shell: "Shell Agent",
      },
      statA: {
        label: "Mode",
        value: "Manual Gate",
      },
      statB: {
        label: "Memory Layer",
        value: "Vector + Profile",
      },
      statC: {
        label: "Device Fabric",
        value: "Mijia Live",
      },
      preview: {
        title: "Operations Snapshot",
        status: "System online, waiting for the next approval or orchestration event.",
        line1: "queue.approvals = 3",
        line2: "memory.recall = semantic",
        line3: "shell.mode = guarded",
      },
      capabilityTitle: "What the Console will own next",
      capabilityA: {
        title: "Live orchestration",
        body: "Track devices, alerts, approvals and automation suggestions in one place.",
      },
      capabilityB: {
        title: "Guarded execution",
        body: "Turn shell work into replayable, approvable and traceable control flows.",
      },
      capabilityC: {
        title: "Persistent memory",
        body: "Store conversations, preferences and context as recallable Jarvis memory.",
      },
      blueprintTitle: "First-pass Console architecture",
      blueprintA: {
        title: "Mission Desk",
        body: "Manage chat-driven intents, approval queues and execution logs.",
      },
      blueprintB: {
        title: "Device Fabric",
        body: "View topology, room state, rule matrices and abnormal events.",
      },
      blueprintC: {
        title: "Memory Atlas",
        body: "Inspect semantic recall, profiles and proactive suggestion hits.",
      },
      footer: "Next, these preview cards become the real Jarvis Console.",
    },
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
        tasks: "Open tasks",
        devices: "Open devices",
      },
      health: {
        bot: "WeChat",
        monitor: "Devices",
        review: "Review",
        memory: "Memory",
      },
      metrics: {
        components: "Component status",
        tasks: "Task status",
        suggestions: "Suggestions",
        anomalies: "Anomalies",
        devices: "Linked devices",
      },
      values: {
        components: "Available",
        tasks: "{approved} done",
      },
      notes: {
        components: "All healthy",
        tasks: "{pending} pending · {failed} failed",
        suggestions: "New suggestions today",
        anomalies: "Need attention",
        devices: "Across {rooms} rooms",
      },
      sections: {
        components: "Component status",
        events: "Recent activity",
        shortcuts: "Shortcuts",
      },
      events: {
        title: "Recent activity",
        link: "Open manage",
      },
      mode: {
        label: "Current Mode",
        value: "Away",
        note: "Risky actions still need approval.",
      },
      links: {
        tasks: "Go to tasks",
        devices: "Go to devices",
        manage: "Go to manage",
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
        all: "All rooms",
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
  },
};

export const i18n = createI18n({
  legacy: false,
  locale: "zh-CN",
  fallbackLocale: "en",
  messages,
});
