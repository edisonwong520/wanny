<script setup lang="ts">
import { DialogContent as DialogContentPrimitive, DialogOverlay, DialogPortal } from "reka-ui";

import { cn } from "@/lib/utils";

defineProps<{
  class?: string;
}>();
</script>

<template>
  <DialogPortal>
    <DialogOverlay class="fixed inset-0 z-50 bg-black/40" />
    <DialogContentPrimitive
      v-bind="$attrs"
      :class="
        cn(
          'fixed left-1/2 top-1/2 z-50 grid w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 gap-4 overflow-hidden rounded-[32px] border border-black/[0.05] bg-white p-5 shadow-2xl duration-200 sm:p-6',
          $props.class,
        )
      "
    >
      <slot />
    </DialogContentPrimitive>
  </DialogPortal>
</template>
