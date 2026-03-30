import { createRouter, createWebHistory } from "vue-router";

import ConsoleLayout from "@/layouts/ConsoleLayout.vue";
import LandingPage from "@/pages/LandingPage.vue";
import DevicesPage from "@/pages/console/DevicesPage.vue";
import ManagePage from "@/pages/console/ManagePage.vue";
import MissionsPage from "@/pages/console/MissionsPage.vue";
import OverviewPage from "@/pages/console/OverviewPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/console",
    },
    {
      path: "/landing",
      name: "landing",
      component: LandingPage,
    },
    {
      path: "/console",
      component: ConsoleLayout,
      children: [
        {
          path: "",
          name: "console-overview",
          component: OverviewPage,
        },
        {
          path: "missions",
          name: "console-missions",
          component: MissionsPage,
        },
        {
          path: "devices",
          name: "console-devices",
          component: DevicesPage,
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

export default router;
