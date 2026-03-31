import { reactive, computed } from "vue";

/**
 * 轻量级身份验证 Store。
 * 使用 LocalStorage 持久化登录状态。
 */
interface User {
  id: number;
  email: string;
  name: string;
}

const STORAGE_KEY = "wanny_auth_user";

// 初始化时从 LocalStorage 恢复
const savedUser = localStorage.getItem(STORAGE_KEY);
const initialState: { user: User | null } = {
  user: savedUser ? JSON.parse(savedUser) : null,
};

export const authStore = reactive(initialState);

export const isAuthenticated = computed(() => !!authStore.user);

export const currentUser = computed(() => authStore.user);

/**
 * 设置登录状态并持久化
 */
export function setAuth(user: User) {
  authStore.user = user;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

/**
 * 获取用于 API 请求的认证 Header
 */
export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (authStore.user?.email) {
    headers["X-Wanny-Email"] = authStore.user.email;
  }
  return headers;
}

/**
 * 清除登录状态
 */
export function clearAuth() {
  authStore.user = null;
  localStorage.removeItem(STORAGE_KEY);
}
