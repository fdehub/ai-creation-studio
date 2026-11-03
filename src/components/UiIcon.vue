<script setup>
defineProps({ name: String, size: { type: [Number, String], default: 18 } })
const paths = {
  stop: ['M5 5h14v14H5z'],
  expand: ['M8 3H3v5M16 21h5v-5M3 3l7 7M21 21l-7-7'],
  shrink: ['M10 3v7H3M14 21v-7h7M3 3l7 7M21 21l-7-7'],
  align: ['M4 5h16M4 10h16M4 15h16M4 20h10'],
  globe: ['M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20ZM2 12h20M12 2c5 5 5 15 0 20-5-5-5-15 0-20Z'],
  book: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H20', 'M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z'],
  chat: ['M21 15a3 3 0 0 1-3 3H8l-5 3V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v9Z'],
  film: ['M4 3h16v18H4z', 'M4 8h16M4 16h16M8 3v18M16 3v18'],
  plus: ['M12 5v14M5 12h14'],
  arrow: ['M5 12h14M12 5l7 7-7 7'],
  check: ['M20 6 9 17l-5-5'],
  search: ['M21 21l-5-5'],
  pen: ['m16 3 5 5-12 12-6 1 1-6L16 3Z', 'm14 5 5 5'],
  settings: ['M4 7h16M4 17h16M8 4v6M16 14v6'],
  history: ['M3 12a9 9 0 1 0 3-6.7L3 8', 'M3 3v5h5M12 7v5l3 2'],
  moon: ['M20.9 13a9 9 0 0 1-9.9-9.9A9 9 0 1 0 20.9 13Z'],
  sun: ['M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'],
  layers: ['m12 3 10 5-10 5L2 8l10-5Z', 'm2 12 10 5 10-5M2 16l10 5 10-5'],
  users: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8'],
  spark: ['m12 3 2.7 6.3L21 12l-6.3 2.7L12 21l-2.7-6.3L3 12l6.3-2.7L12 3Z'],
  grid: ['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z']
}
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="ui-icon">
    <path v-for="(d, i) in paths[name] || paths.grid" :key="i" :d="d" />
    <circle v-if="name === 'search'" cx="10.5" cy="10.5" r="7.5" />
    <circle v-if="name === 'sun'" cx="12" cy="12" r="4" />
    <circle v-if="name === 'users'" cx="9" cy="7" r="4" />
  </svg>
</template>

<style scoped>
.ui-icon { display: inline-block; flex-shrink: 0; vertical-align: middle; }
</style>
