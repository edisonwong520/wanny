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
    "inline-flex items-center justify-center rounded-full border text-sm font-semibold transition duration-200 focus:outline-none focus:ring-2 focus:ring-brand/20",
    props.size === "default" ? "h-11 px-5" : "h-9 px-4 text-xs",
    props.variant === "default" &&
      "border-brand bg-brand text-white shadow-[0_14px_28px_rgba(7,193,96,0.16)] hover:-translate-y-0.5 hover:shadow-[0_16px_32px_rgba(7,193,96,0.22)]",
    props.variant === "secondary" &&
      "border-black/[0.06] bg-surface text-ink hover:-translate-y-0.5 hover:bg-[#fcfcfc]",
    props.variant === "ghost" &&
      "border-transparent bg-transparent text-muted hover:border-brand/10 hover:bg-glow hover:text-brand",
    props.disabled && "cursor-not-allowed opacity-60",
  ),
);
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled">
    <slot />
  </button>
</template>
