<template>
  <div class="app">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-inner">
        <div class="logo">
          <span class="logo-icon">🦘</span>
          <h1>口袋记账</h1>
        </div>
        <nav class="nav-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="nav-tab"
            :class="{ active: currentTab === tab.id }"
            @click="currentTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </nav>
        <div class="month-selector">
          <button class="btn-icon" @click="prevMonth" title="上月">◀</button>
          <input type="month" v-model="monthStr" class="month-picker" />
          <button class="btn-icon" @click="nextMonth" title="下月">▶</button>
          <button class="btn-icon" @click="goToday" title="本月">📅</button>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <Overview v-if="currentTab === 'overview'" :year="year" :month="month" @saved="onDataChanged" />
      <TransactionPage v-else-if="currentTab === 'transaction'" :year="year" :month="month" @saved="onDataChanged" />
      <AIAdvice v-else-if="currentTab === 'ai-advice'" :year="year" :month="month" />
    </main>

    <!-- Toast -->
    <TransitionGroup name="toast" tag="div" class="toast-container">
      <div v-for="t in toasts" :key="t.id" :class="['toast', t.type]">{{ t.message }}</div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref, computed, provide } from 'vue'
import Overview from './components/Overview.vue'
import TransactionPage from './components/TransactionPage.vue'
import AIAdvice from './components/AIAdvice.vue'

const tabs = [
  { id: 'overview', label: '总览' },
  { id: 'transaction', label: '记账' },
  { id: 'ai-advice', label: '财务分析' },
]

const currentTab = ref('overview')

// 月份管理
const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)

const monthStr = computed({
  get: () => {
    const m = String(month.value).padStart(2, '0')
    return `${year.value}-${m}`
  },
  set: (val) => {
    if (val) {
      const [y, m] = val.split('-')
      year.value = parseInt(y)
      month.value = parseInt(m)
    }
  },
})

function prevMonth() {
  if (month.value === 1) { month.value = 12; year.value-- }
  else month.value--
}

function nextMonth() {
  if (month.value === 12) { month.value = 1; year.value++ }
  else month.value++
}

function goToday() {
  const d = new Date()
  year.value = d.getFullYear()
  month.value = d.getMonth() + 1
}

// 数据变更通知（跨组件刷新信号）
const dataVersion = ref(0)
provide('dataVersion', dataVersion)
function onDataChanged() { dataVersion.value++ }

// Toast
const toasts = ref([])
let toastId = 0
function showToast(message, type = 'success', duration = 2500) {
  const id = ++toastId
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, duration)
}
provide('showToast', showToast)
</script>
