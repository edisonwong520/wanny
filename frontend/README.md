# Wanny Frontend

Wanny 的前端工作区负责两类界面：

- Landing Page：用于展示 Jarvis 的能力、入口与整体定位
- Jarvis Console：用于管理设备、任务、记忆、审批流与运行状态

## 技术栈

- Vue 3
- Vite
- TypeScript
- Tailwind CSS
- shadcn-vue
- vue-i18n

## 运行方式

建议使用现代 LTS Node 版本，推荐 `24.11.1`，兼容 `22+`。

```bash
npm install
npm run dev
```

## 目录说明

```text
frontend/
├── src/
│   ├── components/      # 通用界面组件与 UI 基础组件
│   ├── i18n/            # 中英文文案
│   ├── lib/             # 工具函数
│   ├── pages/           # 页面级视图（Landing / Console）
│   └── router/          # 前端路由
├── components.json      # shadcn-vue 配置
├── tailwind.config.ts   # Tailwind 样式配置
└── vite.config.ts       # Vite 配置
```

## 当前阶段

目前已经搭建了：

- 一个可继续演进的 Landing Page
- 一个为 Jarvis Console 预留的信息架构占位页

下一阶段将围绕 Console 逐步接入真实后端接口与设备状态。

