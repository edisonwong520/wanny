export default {
  butler: "AI 智能管家",
  questions: "你可以这么问：",
  prompts: [
    "帮我看看家里关门没有",
    "今天宠物喝了多少次水",
    "主卧灯光调成睡眠模式",
    "扫地机器人去打扫一下客厅",
    "如果我出门了，记得关空调",
    "帮我关掉所有不在用的灯",
    "现在的室内湿度适合睡觉吗？",
    "查询一下昨天的用电报告",
    "打开投影仪模式并拉下窗帘",
    "烧一壶开水，我要泡茶",
    "进入离家模式，开启布防",
    "饮水机的滤芯该更换了吗？",
    "厨房的天然气报警器状态正常吗？",
    "帮我看看猫砂盆需要清理了吗",
    "明早 7 点叫醒我，并播报天气",
    "把阳台的晾衣架升到最高",
    "客厅电视音量调小到 20%",
    "半小时后提醒我给花浇水",
    "家里所有的安全策略升为最高等级",
    "查询昨天监控录像摘要"
  ],
  briefFeatures: {
    wechat: { title: "微信入口", desc: "随说、随办、处处方便" },
    device: { title: "家电联动", desc: "米家、美的、样样都行" },
    memory: { title: "主动记忆", desc: "懂你、想你、回回契合" },
  },
  titleLead: "Wanny, 你的 Jarvis 智能管家",
  titleAccent: "",
  summary:
    "Wanny 让你通过一个控制界面管理家庭自动化、主动关怀、任务审批与语义记忆。今天先做一个入口页，下一阶段重点落到 Console。",
  primary: "进入控制台",
  secondary: "开始使用",
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
};
