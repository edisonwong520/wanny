<script setup lang="ts">
import { DialogContent as DialogContentPrimitive, DialogOverlay, DialogPortal } from "reka-ui";

import { cn } from "@/lib/utils";

defineProps<{
  class?: string;
}>();
</script>

<template>
  <DialogPortal>
    <DialogOverlay class="fixed inset-0 z-50 bg-black/30" />
    <DialogContentPrimitive
      v-bind="$attrs"
      :class="
        cn(
          'fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white shadow-xl',
          $props.class,
        )
      "
    >
      <slot />
    </DialogContentPrimitive>
  </DialogPortal>
</template>