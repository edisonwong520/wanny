<script setup lang="ts">
import { computed } from "vue";

import { cn } from "@/lib/utils";

type ButtonVariant = "default" | "secondary" | "ghost";
type ButtonSize = "default" | "sm";

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant;
    size?: ButtonSize;
    type?: "button" | "submit" | "reset";
    disabled?: boolean;
  }>(),
  {
    variant: "default",
    size: "default",
    type: "button",
    disabled: false,
  },
);

const classes = computed(() =>
  cn(
    "inline-flex items-center justify-center rounded-full text-sm font-medium transition-all duration-200 focus:outline-none",
    props.size === "default" ? "h-9 px-5" : "h-7 px-4",
    props.variant === "default" &&
      "bg-[#07C160] text-white hover:bg-[#06AD56] hover:shadow-md hover:-translate-y-0.5",
    props.variant === "secondary" &&
      "border border-[#EDEDED] bg-white text-[#333333] hover:bg-[#F7F7F7] hover:border-[#07C160]/30 hover:-translate-y-0.5",
    props.variant === "ghost" &&
      "text-[#888888] hover:text-[#333333] hover:bg-[#F7F7F7]",
    props.disabled && "cursor-not-allowed opacity-50 hover:translate-y-0",
  ),
);
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled">
    <slot />
  </button>
</template>