<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";

const props = defineProps<{ apiKey: string; apiBaseUrl?: string }>();

onMounted(() => {
  const s = document.createElement("script");
  s.src = `${props.apiBaseUrl || "http://localhost:8000"}/widget.js`;
  s.dataset.apiKey = props.apiKey;
  s.dataset.theme = "light";
  document.body.appendChild(s);
});

onBeforeUnmount(() => {
  (window as any).THTWAAT?.destroy?.();
});
</script>

<template>
  <div aria-hidden="true" />
</template>
