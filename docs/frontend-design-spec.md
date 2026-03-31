# Wanny 前端设计规范

本文档定义 Wanny 前端界面的视觉与交互规范，AI 在开发前端时必须遵守。

## 1. 设计理念

Wanny 是类似 Jarvis 的 AI 智能家居管家平台，视觉风格应体现：
- **微信易用性**：简洁、高效、用户熟悉
- **AI 科技感**：现代、智能、可靠
- **克制高级感**：避免廉价霓虹风格，追求精致质感

## 2. 配色方案

基于微信配色，适配 AI 管家定位：

| 用途 | 色值 | 说明 |
|------|------|------|
| 主色调 | `#07C160` | 微信绿，用于主按钮、选中态、链接 |
| 主色浅 | `#9CDA62` | 辅助绿色 |
| 主背景 | `#FFFFFF` | 页面主背景 |
| 次背景 | `#F7F7F7` | 卡片容器背景、灰底区域 |
| 三级背景 | `#EDEDED` | 边框、分割线、禁用态背景 |
| 一级文本 | `#333333` | 标题、正文，避免纯黑减少视觉疲劳 |
| 二级文本 | `#888888` | 副标题、说明文字、时间戳 |
| 成功色 | `#07C160` | 在线、已连接、已通过 |
| 成功背景 | `#E8F8EC` | 成功状态浅绿底色 |
| 警告色 | `#E8A223` | 待处理、注意事项 |
| 警告背景 | `#FFF7E6` | 警告状态浅黄底色 |
| 错误色 | `#E84343` | 离线、异常、拒绝 |
| 错误背景 | `#FFE8E8` | 错误状态浅红底色 |

## 3. 圆角规范

| 元素类型 | 圆角值 | Tailwind 类 |
|----------|--------|-------------|
| 主按钮 | 全圆（胶囊） | `rounded-full` |
| 筛选按钮/Tab | 全圆（胶囊） | `rounded-full` |
| 状态标签 | 全圆（胶囊） | `rounded-full` |
| 输入框 | 中圆角 | `rounded-xl` |
| 卡片/容器 | 大圆角 | `rounded-2xl` |
| 弹窗 | 大圆角 | `rounded-2xl` |

## 4. 交互反馈规范

### 4.1 按钮 Hover 效果

**主按钮（绿色）**：
```html
class="rounded-full bg-[#07C160] text-white transition-all duration-200 hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5"
```
- 背景色加深 `#06AD56`
- 添加阴影 `shadow-md`
- 微上浮 `-translate-y-0.5`

**次要按钮（白底边框）**：
```html
class="rounded-full border border-[#EDEDED] bg-white text-[#333333] transition-all duration-200 hover:bg-[#F7F7F7] hover:border-[#07C160]/30 hover:-translate-y-0.5"
```
- 背景变灰 `hover:bg-[#F7F7F7]`
- 边框变绿 `hover:border-[#07C160]/30`
- 微上浮

**危险按钮（断开/拒绝）**：
```html
class="rounded-full border border-[#EDEDED] text-[#888888] transition-all duration-200 hover:border-[#E84343]/30 hover:text-[#E84343] hover:bg-[#FFE8E8]/50"
```
- 边框变红
- 文字变红
- 背景浅红

### 4.2 卡片/行 Hover 效果

```html
class="rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30 hover:shadow-sm"
```
- 边框变绿 `hover:border-[#07C160]/30`
- 浅绿晕染 `hover:bg-[#E8F8EC]/30`
- 微阴影 `hover:shadow-sm`

### 4.3 输入框 Focus 效果

```html
class="rounded-xl border border-[#EDEDED] outline-none transition-all duration-200 focus:border-[#07C160] focus:ring-2 focus:ring-[#07C160]/20"
```
- 边框变绿
- 绿色光晕 `ring-2 ring-[#07C160]/20`

## 5. 状态标签样式

使用统一的状态标签样式：

```html
<span class="px-2.5 py-1 rounded-full text-xs font-medium" :style="{ background: bgColor, color: textColor }">
  状态文本
</span>
```

| 状态 | background | text |
|------|------------|------|
| 在线/成功/已通过 | `#E8F8EC` | `#07C160` |
| 待处理/注意 | `#FFF7E6` | `#E8A223` |
| 离线/错误/拒绝 | `#FFE8E8` | `#E84343` |
| 默认/禁用 | `#F7F7F7` | `#888888` |

## 6. 导航与筛选样式

**Tab 导航**：
```html
<!-- 选中态 -->
<a class="px-4 py-2 rounded-full bg-[#07C160] text-white text-sm shadow-sm">
  标签
</a>
<!-- 未选中态 -->
<a class="px-4 py-2 rounded-full text-[#888888] text-sm hover:bg-[#F7F7F7] hover:text-[#333333]">
  标签
</a>
```

**筛选按钮组**：
```html
<!-- 选中态 -->
<button class="px-4 py-2 rounded-full bg-[#07C160] text-white text-sm shadow-sm">
  筛选项 (3)
</button>
<!-- 未选中态 -->
<button class="px-4 py-2 rounded-full bg-[#F7F7F7] text-[#888888] text-sm hover:bg-[#EDEDED]">
  筛选项 (5)
</button>
```

## 7. 动效规范

- **过渡时长**：`duration-200`（200ms）
- **缓动函数**：默认 ease
- **使用场景**：颜色变化、阴影、位移、边框
- **避免**：过度动画、弹跳效果、旋转特效

## 8. 响应式断点

使用 Tailwind 默认断点：
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px

移动端优先，使用 `md:` 或 `lg:` 断点调整布局。

## 9. 字体规范

```css
font-family: "Noto Sans SC", system-ui, sans-serif;
```

- 标题：`font-semibold`
- 正文：默认（400）
- 按钮/标签：`font-medium`

## 10. 间距规范

- 卡片内边距：`p-4`（16px）或 `p-5`（20px）
- 元素间距：`gap-2`（8px）或 `gap-3`（12px）或 `gap-4`（16px）
- 区域间距：`space-y-4` 或 `space-y-5`

## 11. 代码示例

### 11.1 主按钮

```vue
<button class="rounded-full bg-[#07C160] px-6 py-3 text-sm font-medium text-white transition-all duration-200 hover:bg-[#06AD56] hover:shadow-lg hover:-translate-y-0.5">
  开始使用
</button>
```

### 11.2 设备卡片

```vue
<div class="p-4 rounded-2xl border border-[#EDEDED] transition-all duration-200 hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/20 hover:shadow-sm">
  <div class="flex items-center justify-between mb-2">
    <span class="font-medium text-[#333333]">客厅空调</span>
    <span class="px-2.5 py-1 rounded-full text-xs font-medium bg-[#E8F8EC] text-[#07C160]">在线</span>
  </div>
  <div class="text-xs text-[#888888]">空调</div>
  <div class="mt-2 text-sm text-[#333333]">温度 26°C</div>
</div>
```

### 11.3 任务列表项

```vue
<div class="p-4 rounded-2xl cursor-pointer transition-all duration-200 border border-[#EDEDED] hover:border-[#07C160]/30 hover:bg-[#E8F8EC]/30">
  <div class="flex items-center gap-2 mb-2">
    <span class="px-2.5 py-1 rounded-full text-xs font-medium bg-[#FFF7E6] text-[#E8A223]">待处理</span>
    <span class="text-xs text-[#888888]">2 分钟前</span>
  </div>
  <div class="text-sm font-medium text-[#333333]">打开客厅空调</div>
  <div class="text-xs text-[#888888] mt-1">微信入口</div>
</div>
```