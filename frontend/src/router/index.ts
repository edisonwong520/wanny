import { createRouter, createWebHistory } from "vue-router";

import ConsoleLayout from "@/layouts/ConsoleLayout.vue";
import LandingPage from "@/pages/LandingPage.vue";
import RegisterPage from "@/pages/RegisterPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
import DevicesPage from "@/pages/console/DevicesPage.vue";
import ManagePage from "@/pages/console/ManagePage.vue";
import MissionsPage from "@/pages/console/MissionsPage.vue";
import CareCenterPage from "@/pages/console/CareCenterPage.vue";
import { isAuthenticated } from "@/lib/auth";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      redirect: "/landing",
    },
    {
      path: "/landing",
      name: "landing",
      component: LandingPage,
    },
    {
      path: "/register",
      name: "register",
      component: RegisterPage,
    },
    {
      path: "/login",
      name: "login",
      component: LoginPage,
    },
    {
      path: "/console",
      component: ConsoleLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: "",
          redirect: "/console/care",
        },
        {
          path: "devices",
          name: "console-devices",
          component: DevicesPage,
        },
        {
          path: "missions",
          name: "console-missions",
          component: MissionsPage,
        },
        {
          path: "care",
          name: "console-care",
          component: CareCenterPage,
        },
        {
          path: "care/rules",
          redirect: "/console/care",
        },
        {
          path: "manage",
          name: "console-manage",
          component: ManagePage,
        },
        {
          path: "memory",
          redirect: "/console/manage",
        },
        {
          path: "guard",
          redirect: "/console/manage",
        },
      ],
    },
  ],
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach((to, _from, next) => {
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth);

  if (requiresAuth && !isAuthenticated.value) {
    next("/login");
  } else {
    next();
  }
});

export default router;
