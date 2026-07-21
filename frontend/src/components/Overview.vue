<template>
  <div class="overview-page">
    <!-- 概览卡片 -->
    <div class="overview-cards">
      <div class="card overview-card income">
        <div class="card-label">📥 总收入</div>
        <div class="card-amount">¥ {{ fmt(overview.total_income) }}</div>
      </div>
      <div class="card overview-card expense">
        <div class="card-label">📤 总支出</div>
        <div class="card-amount">¥ {{ fmt(overview.total_expense) }}</div>
      </div>
      <div class="card overview-card" :class="balanceClass">
        <div class="card-label">💰 结余</div>
        <div class="card-amount">¥ {{ fmt(overview.balance) }}</div>
      </div>
      <div class="card overview-card count">
        <div class="card-label">📝 交易笔数</div>
        <div class="card-amount">{{ overview.transaction_count }}</div>
      </div>
    </div>

    <!-- 预算 + 图表 -->
    <div class="mid-row">
      <!-- 预算执行 -->
      <div class="card budget-panel">
        <div class="panel-header">
          <h3>🎯 预算执行</h3>
          <button class="btn-link" @click="showBudgetForm = !showBudgetForm">
            {{ showBudgetForm ? '收起' : '设置' }}
          </button>
        </div>

        <!-- 预算设置表单 -->
        <form v-if="showBudgetForm" class="budget-inline-form" @submit.prevent="handleSaveBudget">
          <div class="form-row">
            <div class="form-group flex-1">
              <input v-model.number="budgetAmount" type="number" step="0.01" min="0.01" placeholder="预算金额" required />
            </div>
            <div class="form-group" style="width:140px">
              <select v-model.number="budgetThreshold">
                <option :value="0.50">50%</option>
                <option :value="0.70">70%</option>
                <option :value="0.80">80%</option>
                <option :value="0.90">90%</option>
                <option :value="1.00">100%</option>
              </select>
            </div>
            <button type="submit" class="btn btn-primary btn-sm">保存</button>
          </div>
        </form>

        <div v-if="budgetStatus" class="budget-status-mini">
          <div class="budget-mini-header">
            <span>月度预算</span>
            <b>¥ {{ fmt(budgetStatus.budget_amount) }}</b>
          </div>
          <div class="progress-bar-wrap">
            <div class="progress-bar" :class="budgetProgressClass" :style="{ width: Math.min(budgetStatus.percentage, 100) + '%' }">
              <span v-if="budgetStatus.percentage > 15">{{ budgetStatus.percentage }}%</span>
            </div>
            <span v-if="budgetStatus.percentage <= 15" class="progress-text-outside">{{ budgetStatus.percentage }}%</span>
          </div>
          <div class="budget-mini-details">
            <span>已花 <b :class="budgetStatus.is_over_budget ? 'text-danger' : 'text-success'">¥ {{ fmt(budgetStatus.spent_amount) }}</b></span>
            <span>剩余 <b>¥ {{ fmt(budgetStatus.remaining) }}</b></span>
            <span :class="budgetStatus.is_over_budget ? 'text-danger' : (budgetStatus.is_alert ? 'text-warning' : 'text-success')">
              {{ budgetStatus.is_over_budget ? '💥超支' : (budgetStatus.is_alert ? '⚠️预警' : '✅正常') }}
            </span>
          </div>
        </div>
        <div v-else class="empty-state" style="padding:20px">请设置本月预算</div>
      </div>

      <!-- 支出分类饼图 -->
      <div class="card chart-card">
        <h3>📊 支出分类分布</h3>
        <div class="chart-wrap">
          <canvas ref="pieCanvas"></canvas>
        </div>
        <div v-if="!catStats.length" class="empty-state chart-empty">暂无数据</div>
      </div>
    </div>

    <!-- 趋势图 -->
    <div class="card chart-card trend-card">
      <h3>📈 年度收支趋势</h3>
      <div class="chart-wrap trend-wrap">
        <canvas ref="trendCanvas"></canvas>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, inject } from 'vue'
import { Chart, registerables } from 'chart.js'
import {
  fetchOverview, fetchCategoryStats, fetchMonthlyStats,
  fetchBudgets, fetchBudgetStatus, createBudget,
} from '../api/index.js'

Chart.register(...registerables)

const props = defineProps({ year: Number, month: Number })
const emit = defineEmits(['saved'])
const showToast = inject('showToast', () => {})
const dataVersion = inject('dataVersion', ref(0))

// 防止 dataVersion 死循环：记录当前组件自己触发的最新版本号
let myLastEmittedVersion = 0

// ==================== 概览数据 ====================
const overview = ref({ total_income: '0', total_expense: '0', balance: '0', transaction_count: 0 })
const catStats = ref([])
const monthlyStats = ref([])

const balanceClass = computed(() => {
  const b = parseFloat(overview.value.balance)
  if (b > 0) return 'positive'
  if (b < 0) return 'negative'
  return ''
})

// ==================== 图表 ====================
const pieCanvas = ref(null)
const trendCanvas = ref(null)
let pieChart = null
let trendChart = null

async function loadStats() {
  try {
    const [ov, cs, ms] = await Promise.all([
      fetchOverview(props.year, props.month),
      fetchCategoryStats(props.year, props.month, 'expense'),
      fetchMonthlyStats(props.year),
    ])
    overview.value = ov
    catStats.value = cs
    monthlyStats.value = ms
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error('加载统计数据失败:', e)
  }
}

function renderCharts() {
  if (pieChart) pieChart.destroy()
  if (pieCanvas.value && catStats.value.length > 0) {
    pieChart = new Chart(pieCanvas.value, {
      type: 'doughnut',
      data: {
        labels: catStats.value.map(c => `${c.category_icon} ${c.category_name}`),
        datasets: [{
          data: catStats.value.map(c => parseFloat(c.amount)),
          backgroundColor: [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#C9CBCF', '#7BC8A4', '#E8A87C', '#85C1E9',
            '#F1948A', '#BB8FCE', '#73C6B6', '#F7DC6F', '#B0BEC5',
          ],
          borderWidth: 2,
          borderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { padding: 10, usePointStyle: true, font: { size: 11 } },
          },
        },
      },
    })
  }

  if (trendChart) trendChart.destroy()
  if (trendCanvas.value) {
    trendChart = new Chart(trendCanvas.value, {
      type: 'line',
      data: {
        labels: monthlyStats.value.map(m => m.month.substring(5) + '月'),
        datasets: [
          {
            label: '收入',
            data: monthlyStats.value.map(m => parseFloat(m.income)),
            borderColor: '#4CAF50',
            backgroundColor: 'rgba(76,175,80,0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 4,
          },
          {
            label: '支出',
            data: monthlyStats.value.map(m => parseFloat(m.expense)),
            borderColor: '#FF5252',
            backgroundColor: 'rgba(255,82,82,0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => '¥' + v } } },
      },
    })
  }
}

// ==================== 预算 ====================
const budgetStatus = ref(null)
const showBudgetForm = ref(false)
const budgetAmount = ref('')
const budgetThreshold = ref(0.80)

const budgetProgressClass = computed(() => {
  if (!budgetStatus.value) return ''
  if (budgetStatus.value.is_over_budget) return 'danger'
  if (budgetStatus.value.is_alert) return 'warning'
  return 'safe'
})

async function loadBudget() {
  try {
    const statuses = await fetchBudgetStatus(props.year, props.month)
    budgetStatus.value = statuses[0] || null

    const budgets = await fetchBudgets(props.year, props.month)
    const total = budgets.find(b => b.category_id === null)
    if (total) {
      budgetAmount.value = parseFloat(total.amount)
      budgetThreshold.value = parseFloat(total.alert_threshold)
    }
  } catch (e) {
    console.error('加载预算失败:', e)
  }
}

async function handleSaveBudget() {
  if (!budgetAmount.value || parseFloat(budgetAmount.value) <= 0) {
    showToast('请输入有效预算金额', 'error')
    return
  }
  try {
    await createBudget({
      year: props.year,
      month: props.month,
      amount: parseFloat(budgetAmount.value),
      category_id: null,
      alert_threshold: budgetThreshold.value,
    })
    showToast('预算保存成功！')
    showBudgetForm.value = false
    await loadBudget()
    notifyChange()
  } catch (e) {
    showToast(e.message, 'error')
  }
}

// ==================== 工具 ====================
function fmt(val) {
  const n = parseFloat(val)
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

async function refreshAll() {
  await Promise.all([loadStats(), loadBudget()])
}

/** 通知父组件数据变更（仅在用户主动操作后调用） */
function notifyChange() {
  myLastEmittedVersion = dataVersion.value + 1
  emit('saved')
}

// ==================== 生命周期 ====================
onMounted(() => {
  refreshAll()
})

onUnmounted(() => {
  if (pieChart) { pieChart.destroy(); pieChart = null }
  if (trendChart) { trendChart.destroy(); trendChart = null }
})

watch(() => [props.year, props.month], () => {
  refreshAll()
})

watch(dataVersion, (newVal) => {
  if (newVal === myLastEmittedVersion) return
  refreshAll()
})
</script>
