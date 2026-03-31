# Wanny Frontend Rules

本文件只记录前端开发规则。处理前端任务时，除根目录 `README.md` 与根目录 `GEMINI.md` 外，还必须阅读本文件。

## 1. 技术栈

- 框架与构建：Vue 3、Vite、TypeScript
- Node 推荐版本：`24.11.1`
- 样式系统：Tailwind CSS
- UI 组件库：`shadcn-vue`
- 国际化：`vue-i18n`

## 2. 设计规范

**重要**：所有前端 UI 开发必须遵守 [`docs/frontend-design-spec.md`](../docs/frontend-design-spec.md) 中定义的设计规范，包括：

- 配色方案（微信绿 `#07C160` 为主色）
- 圆角规范（按钮/标签用 `rounded-full`，卡片用 `rounded-2xl`）
- 交互反馈（hover 上浮、浅绿晕染、阴影）
- 状态标签样式
- 动效规范

开发前请先阅读设计规范文档。

## 3. 基础体验要求

- 所有页面和组件必须默认支持响应式布局，兼容桌面与移动端
- 默认采用浅色主题，不以深色主题作为主视觉
- 必须追求高级、克制、现代的视觉质感，避免廉价或玩具感界面
- 所有组件都应提供清晰的 Hover、Active 和 Focus 反馈
- 按钮与点击入口必须优先保证文字对比度和可读性