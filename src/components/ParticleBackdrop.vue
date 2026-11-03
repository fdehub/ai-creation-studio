<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const canvas = ref(null)
const running = ref(false)
let dispose = () => {}

onMounted(() => {
  const surface = canvas.value
  const host = surface.parentElement
  const ctx = surface.getContext('2d')
  if (!ctx) return

  const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  const pointer = { x: -1000, y: -1000 }
  let width = 0, height = 0, frame = 0, last = 0, visible = true
  let particles = [], sparks = [], accent = '', neutral = ''
  const colors = () => {
    const style = getComputedStyle(surface)
    accent = style.getPropertyValue('--accent-color').trim()
    neutral = style.getPropertyValue('--text-category').trim()
  }
  const allowed = () => visible && !document.hidden && !motion.matches && width > 0 && height > 0
  const clear = () => ctx.clearRect(0, 0, width, height)

  function draw(now) {
    frame = 0
    if (!allowed()) { running.value = false; return }
    frame = requestAnimationFrame(draw)
    if (now - last < 1000 / 30) return
    const dt = Math.min((now - (last || now)) / 1000, .05)
    last = now
    clear()
    for (const p of particles) {
      p.x += p.vx * dt; p.y += p.vy * dt
      if (p.x < -8) p.x = width + 8
      if (p.x > width + 8) p.x = -8
      if (p.y < -8) p.y = height + 8
      if (p.y > height + 8) p.y = -8
      const dx = pointer.x - p.x, dy = pointer.y - p.y
      const distance = Math.hypot(dx, dy)
      const pull = distance < 140 ? (1 - distance / 140) * .075 : 0
      p.drawX = p.x + dx * pull
      p.drawY = p.y + dy * pull + Math.sin(now / 1800 + p.phase) * 3
      ctx.globalAlpha = p.opacity * (.8 + Math.sin(now / 2000 + p.phase) * .2)
      ctx.fillStyle = p.accent ? accent : neutral
      ctx.beginPath(); ctx.arc(p.drawX, p.drawY, p.radius, 0, Math.PI * 2); ctx.fill()
      if (p.star) {
        ctx.globalAlpha *= .35
        ctx.strokeStyle = accent; ctx.lineWidth = .7
        ctx.beginPath(); ctx.moveTo(p.drawX - 4, p.drawY); ctx.lineTo(p.drawX + 4, p.drawY)
        ctx.moveTo(p.drawX, p.drawY - 4); ctx.lineTo(p.drawX, p.drawY + 4); ctx.stroke()
      }
    }
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i], b = particles[j]
        const distance = Math.hypot(a.drawX - b.drawX, a.drawY - b.drawY)
        if (distance > 75) continue
        ctx.globalAlpha = .14 * (1 - distance / 75)
        ctx.strokeStyle = accent; ctx.lineWidth = .6
        ctx.beginPath(); ctx.moveTo(a.drawX, a.drawY); ctx.lineTo(b.drawX, b.drawY); ctx.stroke()
      }
    }
    sparks = sparks.filter(p => p.life > 0)
    for (const p of sparks) {
      p.life -= dt; p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 12 * dt
      ctx.globalAlpha = Math.max(0, p.life / .8) * .65
      ctx.fillStyle = accent
      ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill()
    }
    ctx.globalAlpha = 1
  }
  function sync() {
    const active = allowed()
    running.value = active
    if (!active) {
      cancelAnimationFrame(frame); frame = 0; last = 0; sparks = []; clear()
    } else if (!frame) { last = 0; frame = requestAnimationFrame(draw) }
  }
  function resize() {
    const box = host.getBoundingClientRect()
    width = box.width; height = box.height
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
    surface.width = Math.round(width * ratio); surface.height = Math.round(height * ratio)
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    const count = Math.min(42, Math.max(18, Math.round(width / 25)))
    particles = Array.from({ length: count }, (_, i) => ({
      x: Math.random() * width, y: Math.random() * height,
      vx: (Math.random() - .5) * 13, vy: (Math.random() - .5) * 8,
      radius: 1 + Math.random() * 1.8, opacity: .25 + Math.random() * .4,
      phase: Math.random() * Math.PI * 2, accent: i % 3 !== 0, star: i % 8 === 0
    }))
    sync()
  }
  function move(event) {
    if (event.pointerType === 'touch') return
    const box = host.getBoundingClientRect()
    pointer.x = event.clientX - box.left; pointer.y = event.clientY - box.top
  }
  function leave() { pointer.x = pointer.y = -1000 }
  function burst(event) {
    if (!allowed() || event.button !== 0) return
    const box = host.getBoundingClientRect()
    const x = event.clientX - box.left, y = event.clientY - box.top
    sparks = sparks.slice(-18)
    for (let i = 0; i < 12; i++) {
      const angle = Math.PI * 2 * i / 12, speed = 18 + Math.random() * 40
      sparks.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, radius: 1 + Math.random(), life: .8 })
    }
  }

  colors()
  const sizeObserver = new ResizeObserver(resize)
  const visibilityObserver = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; sync() })
  const themeObserver = new MutationObserver(colors)
  sizeObserver.observe(host); visibilityObserver.observe(host)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  document.addEventListener('visibilitychange', sync)
  motion.addEventListener('change', sync)
  host.addEventListener('pointermove', move, { passive: true })
  host.addEventListener('pointerleave', leave, { passive: true })
  host.addEventListener('pointerdown', burst, { passive: true })
  resize()
  dispose = () => {
    cancelAnimationFrame(frame)
    sizeObserver.disconnect(); visibilityObserver.disconnect(); themeObserver.disconnect()
    document.removeEventListener('visibilitychange', sync)
    motion.removeEventListener('change', sync)
    host.removeEventListener('pointermove', move); host.removeEventListener('pointerleave', leave); host.removeEventListener('pointerdown', burst)
  }
})
onUnmounted(() => dispose())
</script>

<template>
  <canvas ref="canvas" class="particle-backdrop" aria-hidden="true" :data-animation="running ? 'running' : 'paused'"></canvas>
</template>

<style scoped>
.particle-backdrop { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:0; mask-image:linear-gradient(90deg,transparent 8%,#000 48%,#000 96%); }
@media(prefers-reduced-motion:reduce) { .particle-backdrop { display:none; } }
</style>
