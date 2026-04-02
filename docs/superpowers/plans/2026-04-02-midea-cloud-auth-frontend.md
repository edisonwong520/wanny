# 美的授权前端功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在前端 ManagePage.vue 中新增美的表单授权功能，允许用户输入账号、密码和选择服务器类型完成授权。

**Architecture:** 复用现有 Home Assistant 弹窗模式，在 ManagePage.vue 中新增美的表单状态变量、处理函数和 UI 区块，同时更新中英文国际化文案。

**Tech Stack:** Vue 3 + TypeScript + Tailwind CSS + vue-i18n

---

## 文件结构

| 文件 | 改动类型 | 责任 |
|------|----------|------|
| `frontend/src/i18n/zh-CN/console.ts` | 修改 | 新增美的相关中文文案 |
| `frontend/src/i18n/en/console.ts` | 修改 | 新增美的相关英文文案 |
| `frontend/src/pages/console/ManagePage.vue` | 修改 | 新增美的表单 UI 和处理逻辑 |

---

### Task 1: 新增中文国际化文案

**Files:**
- Modify: `frontend/src/i18n/zh-CN/console.ts`

- [ ] **Step 1: 在 manage.auth.fields 中新增美的表单字段标签**

在 `manage.auth.fields` 对象中添加以下字段（位于 `accessTokenPlaceholder` 之后）：

```typescript
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
```

- [ ] **Step 2: 在 manage.auth.hint 中新增美的提示信息**

在 `manage.auth.hint` 对象中添加以下字段（位于 `ha_token_info` 之后）：

```typescript
hint: {
  mijia: "使用米家 App 扫描二维码完成授权",
  wechat: "扫码授权完成后请回到本页",
  home_assistant: "",
  ha_token_info: "获取令牌：打开 Home Assistant 控制台 -> 点击左下角用户头像 -> '安全' -> '长期访问令牌'。",
  midea_cloud: "美的授权",
  midea_server_info: "请使用美的美居或 MSmartHome App 的账号密码。不同服务器对应不同 App 平台。",
},
```

- [ ] **Step 3: 验证改动**

运行前端开发服务器确认无语法错误：

```bash
cd frontend && npm run dev
```

Expected: 服务正常启动，无 TypeScript 编译错误

- [ ] **Step 4: 提交中文文案**

```bash
git add frontend/src/i18n/zh-CN/console.ts
git commit -m "feat(i18n): add Midea auth fields in zh-CN"
```

---

### Task 2: 新增英文国际化文案

**Files:**
- Modify: `frontend/src/i18n/en/console.ts`

- [ ] **Step 1: 在 manage.auth.fields 中新增美的表单字段标签**

在 `manage.auth.fields` 对象中添加以下字段（位于 `accessTokenPlaceholder` 之后）：

```typescript
fields: {
  baseUrl: "Instance URL",
  accessToken: "Long-Lived Access Token",
  accessTokenPlaceholder: "Paste a Home Assistant long-lived access token",
  account: "Account",
  accountPlaceholder: "Midea account (phone/email)",
  password: "Password",
  passwordPlaceholder: "Midea account password",
  server: "Server",
},
```

- [ ] **Step 2: 在 manage.auth.hint 中新增美的提示信息**

在 `manage.auth.hint` 对象中添加以下字段（位于 `ha_token_info` 之后）：

```typescript
hint: {
  mijia: "Scan the QR code with the Mijia app to finish authorization.",
  wechat: "After the WeChat authorization completes, return to this page.",
  home_assistant: "",
  ha_token_info: "Getting Token: Open Home Assistant -> Click your profile (bottom left) -> 'Security' -> 'Long-Lived Access Tokens'.",
  midea_cloud: "Midea Authorization",
  midea_server_info: "Use your Midea Meiju or MSmartHome App account. Different servers correspond to different App platforms.",
},
```

- [ ] **Step 3: 验证改动**

运行前端开发服务器确认无语法错误：

```bash
cd frontend && npm run dev
```

Expected: 服务正常启动，无 TypeScript 编译错误

- [ ] **Step 4: 提交英文文案**

```bash
git add frontend/src/i18n/en/console.ts
git commit -m "feat(i18n): add Midea auth fields in en"
```

---

### Task 3: 新增美的表单状态变量和计算属性

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 新增美的表单状态变量**

在 `<script setup>` 中，找到 `homeAssistantAccessToken` 变量定义位置（约第 33 行），在其后添加美的状态变量：

```typescript
const homeAssistantBaseUrl = ref("http://127.0.0.1:8123");
const homeAssistantAccessToken = ref("");
// 美的表单状态
const mideaCloudAccount = ref("");
const mideaCloudPassword = ref("");
const mideaCloudServer = ref<"1" | "2">("2"); // 默认美的美居

// 美的服务器选项
const mideaServerOptions = [
  { value: "1", label: "MSmartHome" },
  { value: "2", label: "美的美居" },
];
```

- [ ] **Step 2: 新增 isMideaCloudModal 计算属性**

在 `isHomeAssistantModal` 计算属性定义之后（约第 58 行），添加美的判断：

```typescript
const isHomeAssistantModal = computed(() => modalProvider.value?.platform === "home_assistant");
const isMideaCloudModal = computed(() => modalProvider.value?.platform === "midea_cloud");
```

- [ ] **Step 3: 新增 mideaCloudInstanceName 计算属性**

在 `homeAssistantInstanceName` 计算属性定义之后（约第 66 行），添加美的实例名显示：

```typescript
const homeAssistantInstanceName = computed(() => {
  const preview = modalProvider.value?.payload_preview ?? {};
  const value = preview.instance_name;
  return typeof value === "string" ? value : "";
});

const mideaCloudInstanceName = computed(() => {
  const preview = modalProvider.value?.payload_preview ?? {};
  const value = preview.instance_name;
  return typeof value === "string" ? value : "";
});

const mideaCloudSavedAccount = computed(() => {
  const preview = modalProvider.value?.payload_preview ?? {};
  const value = preview.account;
  return typeof value === "string" ? value : "";
});

const mideaCloudSavedServer = computed(() => {
  const preview = modalProvider.value?.payload_preview ?? {};
  const value = preview.server;
  return typeof value === "number" ? String(value) : "2";
});
```

- [ ] **Step 4: 验证改动**

运行前端开发服务器确认无 TypeScript 编译错误：

```bash
cd frontend && npm run dev
```

Expected: 服务正常启动，无编译错误

---

### Task 4: 修改 openModal 函数初始化美的表单

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 在 openModal 函数中添加美的初始化逻辑**

找到 `openModal` 函数（约第 142-153 行），在 Home Assistant 初始化逻辑之后添加美的初始化：

```typescript
function openModal(platform: string) {
  modalPlatform.value = platform;
  const provider = providers.value.find((p) => p.platform === platform);
  if (platform === "home_assistant") {
    const preview = provider?.payload_preview ?? {};
    homeAssistantBaseUrl.value =
      typeof preview.base_url === "string" && preview.base_url
        ? preview.base_url
        : "http://127.0.0.1:8123";
    homeAssistantAccessToken.value = "";
  }
  if (platform === "midea_cloud") {
    const preview = provider?.payload_preview ?? {};
    mideaCloudAccount.value = typeof preview.account === "string" ? preview.account : "";
    mideaCloudPassword.value = "";
    mideaCloudServer.value = typeof preview.server === "number" ? String(preview.server) : "2";
  }
}
```

- [ ] **Step 2: 验证改动**

```bash
cd frontend && npm run dev
```

Expected: 无编译错误

---

### Task 5: 修改 closeModal 函数清除美的表单状态

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 在 closeModal 函数中清除美的密码**

找到 `closeModal` 函数（约第 155-159 行），添加美的密码清除：

```typescript
function closeModal() {
  modalPlatform.value = null;
  modalLoading.value = false;
  homeAssistantAccessToken.value = "";
  mideaCloudPassword.value = ""; // 清除密码
}
```

- [ ] **Step 2: 验证改动**

```bash
cd frontend && npm run dev
```

Expected: 无编译错误

---

### Task 6: 修改 handleClick 函数支持美的

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 在 handleClick 函数中添加美的判断**

找到 `handleClick` 函数（约第 183-196 行），修改判断条件以包含美的：

```typescript
async function handleClick(provider: ProviderRecord) {
  // Home Assistant 或美的需要先输入配置信息，直接打开弹窗
  if (provider.platform === "home_assistant" || provider.platform === "midea_cloud") {
    openModal(provider.platform);
    return;
  }

  const session = sessions.value[provider.platform];
  if (session && !session.is_terminal) {
    openModal(provider.platform);
    return;
  }
  await handleAuthorize(provider, provider.status === "connected");
}
```

- [ ] **Step 2: 验证改动**

```bash
cd frontend && npm run dev
```

Expected: 无编译错误

---

### Task 7: 新增 handleMideaCloudAuthorize 处理函数

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 新增 handleMideaCloudAuthorize 函数**

在 `handleHomeAssistantAuthorize` 函数之后（约第 223 行），添加美的授权处理函数：

```typescript
async function handleMideaCloudAuthorize() {
  const provider = modalProvider.value;
  if (!provider || provider.platform !== "midea_cloud") return;

  modalLoading.value = true;
  busyAction.value = `${provider.platform}:connect`;
  errorMessage.value = "";

  try {
    const response = await startAuthorization(provider.platform, {
      payload: {
        account: mideaCloudAccount.value.trim(),
        password: mideaCloudPassword.value.trim(),
        server: parseInt(mideaCloudServer.value),
      },
    });
    updateProvider(response.provider);
    sessions.value = { ...sessions.value, [provider.platform]: response.session };
    mideaCloudPassword.value = ""; // 清除密码
    closeModal();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("manage.auth.errors.action");
  } finally {
    busyAction.value = "";
    modalLoading.value = false;
  }
}
```

- [ ] **Step 2: 验证改动**

```bash
cd frontend && npm run dev
```

Expected: 无编译错误

---

### Task 8: 新增美的表单 UI 模板

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 在弹窗模板中添加美的表单区块**

在 `<Dialog>` 内容区域，找到 Home Assistant 表单区块结束位置（约第 351 行 `</div>` 之后），添加美的表单：

```vue
<!-- 美的表单 -->
<div v-if="isMideaCloudModal" class="space-y-3">
  <!-- 账号输入 -->
  <div class="space-y-1.5">
    <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
      {{ $t("manage.auth.fields.account") }}
    </label>
    <input
      v-model="mideaCloudAccount"
      type="text"
      :placeholder="$t('manage.auth.fields.accountPlaceholder')"
      class="w-full rounded-2xl border border-[#EDEDED] bg-[#FCFCFC] px-4 py-3 text-sm text-[#333333] outline-none transition-all duration-200 focus:border-[#07C160] focus:bg-white"
    />
  </div>

  <!-- 密码输入 -->
  <div class="space-y-1.5">
    <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
      {{ $t("manage.auth.fields.password") }}
    </label>
    <input
      v-model="mideaCloudPassword"
      type="password"
      :placeholder="$t('manage.auth.fields.passwordPlaceholder')"
      class="w-full rounded-2xl border border-[#EDEDED] bg-[#FCFCFC] px-4 py-3 text-sm text-[#333333] outline-none transition-all duration-200 focus:border-[#07C160] focus:bg-white"
    />
  </div>

  <!-- 服务器选择 -->
  <div class="space-y-1.5">
    <label class="text-xs font-medium uppercase tracking-[0.12em] text-[#888888]">
      {{ $t("manage.auth.fields.server") }}
    </label>
    <div class="flex gap-2">
      <button
        v-for="option in mideaServerOptions"
        :key="option.value"
        :class="[
          'flex-1 px-4 py-2.5 rounded-full text-sm font-medium transition-all duration-200',
          mideaCloudServer === option.value
            ? 'bg-[#07C160] text-white shadow-sm'
            : 'bg-[#F7F7F7] text-[#888888] hover:bg-[#EDEDED] hover:text-[#333333]'
        ]"
        @click="mideaCloudServer = option.value"
      >
        {{ option.label }}
      </button>
    </div>
  </div>

  <!-- 提示信息 -->
  <div class="rounded-2xl border border-[#E8F1EA] bg-[#F5FBF7] px-4 py-3 text-xs text-[#4E6A57] leading-relaxed">
    <div class="font-medium mb-1">{{ $t("manage.auth.hint.midea_cloud") }}</div>
    <div class="text-[#6C8373]">{{ $t("manage.auth.hint.midea_server_info") }}</div>
    <div v-if="mideaCloudInstanceName" class="mt-2 pt-2 border-t border-[#E8F1EA] text-[#6C8373]">
      {{ $t("manage.auth.currentInstance") }}: {{ mideaCloudInstanceName }}
    </div>
  </div>

  <!-- 提交按钮 -->
  <button
    :disabled="modalLoading || !mideaCloudAccount.trim() || !mideaCloudPassword.trim()"
    class="w-full rounded-full bg-[#07C160] px-4 py-3 text-sm font-medium text-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
    @click="handleMideaCloudAuthorize"
  >
    {{ $t("manage.auth.actions.save") }}
  </button>
</div>
```

- [ ] **Step 2: 验证前端渲染**

启动开发服务器并在浏览器中测试：

```bash
cd frontend && npm run dev
```

浏览器访问 `http://localhost:5173`，登录后进入 Manage 页面，点击美的的"连接"按钮。

Expected:
- 弹窗正常打开
- 显示账号、密码输入框
- 服务器选择按钮正确显示（MSmartHome / 美的美居）
- 点击服务器按钮可切换选中状态
- 提示信息区域显示正确

---

### Task 9: 集成测试与最终提交

**Files:**
- Modify: `frontend/src/pages/console/ManagePage.vue`

- [ ] **Step 1: 手动测试完整授权流程**

测试步骤：
1. 启动前端开发服务器
2. 启动后端服务
3. 登录前端控制台
4. 进入 Manage 页面
5. 点击美的"连接"按钮
6. 输入账号、密码
7. 选择服务器类型
8. 点击"保存并验证"
9. 验证授权成功后弹窗关闭，状态变为"已连接"

Expected: 授权流程正常完成，provider 状态更新为 connected

- [ ] **Step 2: 测试已有授权场景**

如果已有美的授权：
1. 点击美的行
2. 验证弹窗显示已保存的账号
3. 验证服务器选择显示正确保存值
4. 验证提示区域显示当前实例名

Expected: 已保存信息正确回显

- [ ] **Step 3: 测试断开授权**

1. 点击"断开"按钮
2. 确认断开
3. 验证状态变为"未连接"

Expected: 断开功能正常

- [ ] **Step 4: 测试国际化切换**

1. 切换语言到英文
2. 验证所有美的文案显示英文
3. 切换回中文
4. 验证文案恢复中文

Expected: 国际化切换正常

- [ ] **Step 5: 最终提交**

```bash
git add frontend/src/pages/console/ManagePage.vue
git commit -m "feat(frontend): add Midea authorization form in ManagePage"

# 如果之前 i18n 改动未提交，一并提交
git status
```

---

## Self-Review Checklist

**1. Spec Coverage:**
- ✅ Task 1-2: 国际化文案（fields: account/password/server, hint: midea_cloud/midea_server_info）
- ✅ Task 3: 状态变量
- ✅ Task 4-5: openModal/closeModal 函数修改
- ✅ Task 6: handleClick 函数修改
- ✅ Task 7: handleMideaCloudAuthorize 处理函数
- ✅ Task 8: UI 模板（账号输入、密码输入、服务器选择、提示信息、提交按钮）

**2. Placeholder Scan:**
- ✅ 无 TBD/TODO
- ✅ 无 "implement later"
- ✅ 所有代码步骤包含完整代码块
- ✅ 所有验证步骤包含具体命令

**3. Type Consistency:**
- ✅ mideaCloudServer 类型为 `"1" | "2"`，与 parseInt 使用一致
- ✅ mideaServerOptions value 类型为 string，与 mideaCloudServer 比较一致
- ✅ 计算属性命名风格与 Home Assistant 版本一致