export default {
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
      tasks: "进入任务",
      devices: "查看详情",
      authorize: "暂无设备，请去授权",
    },
    metrics: {
      online: "在线设备",
      offline: "离线设备",
      tasks: "待处理任务",
    },
    empty: {
      auth: "暂无授权设备",
      sync: "已授权但暂无设备数据，请等待同步完成",
      noEvents: "设备运行正常，无异常动态",
    },
    sections: {
      events: "最近动态",
      viewAll: "查看全部",
    },
    events: {
      offline: "{name} 已离线",
    },
  },
  missions: {
    title: "任务",
    filters: {
      pending: "待处理",
      approved: "已通过",
      failed: "已失败",
      all: "全部",
    },
    metrics: {
      pending: "待处理",
      approved: "已通过",
      failed: "已失败",
      highRisk: "高风险",
    },
    status: {
      pending: "待处理",
      approved: "已启用",
      failed: "失败",
    },
    risk: {
      high: "高风险",
      medium: "中等",
      low: "低风险",
    },
    actions: {
      approve: "批准执行",
      reject: "拒绝",
      inspect: "详情",
    },
    detail: {
      created: "时间",
      source: "来源",
      userMessage: "用户指令",
      intent: "Jarvis 理解",
      command: "待执行命令",
      plan: "执行步骤",
      context: "背景上下文",
      reply: "回复预览",
      timeline: "任务轨迹",
    },
    timeline: {
      approved: "您批准了这个任务。",
      rejected: "您拒绝了这个任务。",
    },
    empty: "当前筛选条件下没有任务。",
    errors: {
      load: "无法加载任务列表，请稍后刷新。",
    },
  },
  devices: {
    title: "设备",
    loading: "正在读取设备快照...",
    allRoomsSummary: "查看所有房间的设备快照、异常事件和自动化规则。",
    filters: {
      all: "全部",
    },
    metrics: {
      online: "在线设备",
      attention: "异常设备",
      anomalies: "异常事件",
      rooms: "房间",
      offline: "离线设备",
      controls: "功能控制",
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
      attention: "异常",
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
      controls: "项控制",
    },
    groups: {
      general: "通用",
    },
    highlights: {
      mode: "模式",
      targetTemp: "目标温度",
      currentTemp: "当前温度",
      refrigerator: "冷藏区",
      freezer: "冷冻区",
      power: "电源",
      state: "状态",
      volume: "音量",
      source: "输入源",
      primary: "主要参数",
      secondary: "次要参数",
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
      noDevices: "暂无设备",
      devices: "当前房间筛选下没有设备。",
      policies: "当前模式和房间下没有策略规则。",
      anomalies: "当前没有需要处理的异常。",
    },
    actions: {
      refresh: "刷新",
      apply: "应用",
      run: "执行",
      expand: "展开",
      collapse: "收起",
    },
    controlKinds: {
      sensor: "读取",
      toggle: "开关",
      range: "范围",
      enum: "枚举",
      action: "动作",
      text: "文本",
    },
    values: {
      empty: "暂无",
    },
    enum: {
      on: "开启",
      off: "关闭",
      cool: "制冷",
      heat: "制热",
      auto: "自动",
      dry: "除湿",
      fanOnly: "送风",
      heatCool: "冷热自动",
      swing: "扫风",
      vertical: "上下扫风",
      horizontal: "左右扫风",
      low: "低",
      medium: "中",
      high: "高",
      sleep: "睡眠",
      none: "无",
      playing: "播放中",
      paused: "已暂停",
      idle: "空闲",
      docked: "已回充",
      cleaning: "清扫中",
      returning: "返回中",
    },
    hints: {
      readOnly: "这个节点当前是只读状态。",
    },
    feedback: {
      refreshQueued: "刷新请求已提交，设备信息会在后台更新。",
      actionSuccess: "{name} 已更新。",
      actionFailed: "{name} 执行失败，已回滚到之前状态。",
    },
    errors: {
      load: "读取设备页数据失败，请稍后重试。",
      action: "设备控制执行失败，请稍后重试。",
    },
  },
  manage: {
    title: "管理",
    summary: "统一查看与维护微信、米家和 Home Assistant 的授权状态、重新绑定流程以及最新会话。",
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
      empty: "暂无可用的集成",
      actions: {
        connect: "连接",
        viewSession: "查看授权",
        disconnect: "断开",
        openLink: "点击打开授权链接",
        authorize: "授权",
        save: "保存并验证",
      },
      fields: {
        baseUrl: "实例地址",
        accessToken: "长期访问令牌",
        accessTokenPlaceholder: "填入 Home Assistant Long-Lived Access Token",
        account: "账号",
        accountPlaceholder: "美的账号（手机号/邮箱）",
        password: "密码",
        passwordPlaceholder: "美的账号密码",
        server: "服务器",
      },
      hint: {
        mijia: "使用米家 App 扫描二维码完成授权",
        wechat: "扫码授权完成后请回到本页",
        home_assistant: "",
        ha_token_info: "获取令牌：打开 Home Assistant 控制台 -> 点击左下角用户头像 -> ‘安全’ -> ‘长期访问令牌’。",
        midea_cloud: "美的云授权",
        midea_server_info: "请使用美的美居或 MSmartHome App 的账号密码。不同服务器对应不同 App 平台。",
      },
      servers: {
        msmartHome: "MSmartHome",
        meiju: "美的美居",
      },
      currentInstance: "当前实例",
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
          rationale: "净化器先保持确认制，避免在你不在家时出现 un必要的长时间运行。",
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
};
