<template>
  <div class="txn-layout">
    <!-- 左侧：记账表单 -->
    <div class="txn-form-area">
      <!-- 快速记账 -->
      <div class="card ai-card">
        <h3>📝 快速记账</h3>
        <p class="ai-hint">输入消费描述，自动识别金额、分类和账户</p>


        <div class="ai-input-row">
          <input
            v-model="aiText"
            class="ai-input"
            placeholder="输入自然语言描述你的消费..."
            maxlength="500"
            @keydown.enter="doAIParse"
          />
          <button
            v-if="isSpeechSupported"
            class="btn btn-mic"
            :class="{ recording: isListening }"
            @click="toggleVoiceInput"
            :title="isListening ? '点击停止' : '语音输入'"
          >
            {{ isListening ? '🔴' : '🎤' }}
          </button>
          <button class="btn btn-ai" :disabled="aiLoading" @click="doAIParse">
            {{ aiLoading ? '解析中...' : '解析' }}
          </button>
        </div>

        <!-- AI 解析结果 -->
        <div v-if="aiResult" class="ai-result">
          <div class="ai-result-header">
            <span class="ai-confidence" :class="{ 'confidence-low': aiResult.confidence < 0.5 }">
              置信度: {{ (aiResult.confidence * 100).toFixed(0) }}%
            </span>
            <span v-if="aiResult.source === 'local_fallback'" class="ai-source-badge ai-fallback-badge">
              ⚠️ 离线模式
            </span>
            <span v-else-if="aiResultSource === 'voice'" class="ai-source-badge">🎤 语音识别</span>
            <span v-else class="ai-source-badge">💬 AI 识别</span>
            <button class="btn btn-primary btn-sm" @click="confirmAI">✓ 确认入账</button>
            <button class="btn btn-outline btn-sm" @click="cancelAI">取消</button>
          </div>
          <!-- 离线模式提示 -->
          <div v-if="aiResult.source === 'local_fallback'" class="ai-fallback-hint">
            ⚠️ AI 服务暂时不可用，已使用本地规则解析。建议核对并修正后再确认入账。
          </div>
          <!-- 可编辑的结果详情 -->
          <div class="ai-result-detail">
            <div class="ai-detail-row">
              <span class="ai-label">金额</span>
              <input
                v-model.number="editAIResult.amount"
                type="number"
                step="0.01"
                min="0.01"
                class="ai-edit-input"
              />
            </div>
            <div class="ai-detail-row">
              <span class="ai-label">分类</span>
              <select v-model="editAIResult.category_id" class="ai-edit-select">
                <option v-for="c in allCategories" :key="c.id" :value="c.id">
                  {{ c.icon }} {{ c.name }}
                </option>
              </select>
            </div>
            <div class="ai-detail-row">
              <span class="ai-label">账户</span>
              <select v-model="editAIResult.account_id" class="ai-edit-select">
                <option v-for="a in accounts" :key="a.id" :value="a.id">
                  {{ a.icon }} {{ a.name }}
                </option>
              </select>
            </div>
            <div class="ai-detail-row">
              <span class="ai-label">日期</span>
              <input type="date" v-model="editAIResult.transaction_date" class="ai-edit-input" />
            </div>
            <div class="ai-detail-row">
              <span class="ai-label">备注</span>
              <input
                v-model="editAIResult.note"
                type="text"
                maxlength="200"
                class="ai-edit-input"
                placeholder="可修改备注..."
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 手动记账 -->
      <div class="card manual-card">
        <h3>✏️ 手动记账</h3>
        <form class="txn-form" @submit.prevent="handleSubmit">
          <!-- 类型切换 -->
          <div class="type-toggle">
            <button type="button" class="type-btn expense" :class="{ active: form.type === 'expense' }" @click="switchType('expense')">💸 支出</button>
            <button type="button" class="type-btn income" :class="{ active: form.type === 'income' }" @click="switchType('income')">💰 收入</button>
          </div>

          <div class="form-group">
            <label>金额 (元)</label>
            <input v-model.number="form.amount" type="number" step="0.01" min="0.01" max="9999999999.99" placeholder="0.00" required />
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>分类</label>
              <select v-model="form.category_id" required>
                <option v-for="c in currentCategories" :key="c.id" :value="c.id">{{ c.icon }} {{ c.name }}</option>
              </select>
            </div>
            <div class="form-group flex-1">
              <label>账户</label>
              <select v-model="form.account_id" required>
                <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.icon }} {{ a.name }}</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label>日期</label>
            <input type="date" v-model="form.transaction_date" required />
          </div>

          <div class="form-group">
            <label>备注</label>
            <input v-model="form.note" type="text" maxlength="255" placeholder="写点什么..." />
          </div>

          <button type="submit" class="btn btn-primary btn-full">✓ 确认记账</button>
        </form>
      </div>
    </div>

    <!-- 右侧：流水列表 -->
    <div class="txn-list-area">
      <div class="card">
        <div class="txn-list-header">
          <h3>📋 交易流水</h3>
          <div class="txn-list-summary">
            <span class="summary-income">收: <b>¥ {{ fmt(txnData.total_income) }}</b></span>
            <span class="summary-expense">支: <b>¥ {{ fmt(txnData.total_expense) }}</b></span>
          </div>
        </div>

        <!-- 筛选 -->
        <div class="txn-filter-row">
          <input type="date" v-model="filterWeek" class="filter-input" title="按周筛选（选周一）" />
          <select v-model="filterCategory" class="filter-input">
            <option value="">全部分类</option>
            <option v-for="c in allCategories" :key="c.id" :value="c.id">{{ c.icon }} {{ c.name }}</option>
          </select>
          <select v-model="filterType" class="filter-input">
            <option value="">全部类型</option>
            <option value="expense">支出</option>
            <option value="income">收入</option>
          </select>
        </div>

        <!-- 列表 -->
        <div class="txn-list">
          <div v-if="!txnData.items?.length" class="empty-state">暂无交易记录</div>
          <div
            v-for="txn in txnData.items"
            :key="txn.id"
            class="txn-item"
            :class="txn.type"
          >
            <div class="txn-icon">{{ txn.category?.icon || '📌' }}</div>
            <div class="txn-info">
              <div class="txn-cat">{{ txn.category?.name || '未知' }}</div>
              <div class="txn-meta">
                <span>{{ txn.account?.name || '' }}</span>
                <span v-if="txn.note"> · {{ txn.note }}</span>
              </div>
            </div>
            <div class="txn-right">
              <div class="txn-amount" :class="txn.type">
                {{ txn.type === 'income' ? '+' : '-' }}¥ {{ fmt(txn.amount) }}
              </div>
              <div class="txn-date">{{ txn.transaction_date }}</div>
            </div>
            <button class="txn-delete" @click="doDelete(txn.id)" title="删除">🗑️</button>
          </div>
        </div>

        <!-- 分页 -->
        <div class="txn-pagination" v-if="txnData.total > pageSize">
          <button :disabled="page <= 1" @click="page--">上一页</button>
          <span>{{ page }} / {{ Math.ceil(txnData.total / pageSize) }}</span>
          <button :disabled="page >= Math.ceil(txnData.total / pageSize)" @click="page++">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, inject } from 'vue'
import {
  fetchCategories, fetchAccounts, createTransaction, deleteTransaction,
  fetchTransactions, aiParse, aiParseAndSave,
} from '../api/index.js'

const props = defineProps({ year: Number, month: Number })
const emit = defineEmits(['saved'])
const showToast = inject('showToast', () => {})
const dataVersion = inject('dataVersion', ref(0))

// 防止 dataVersion 死循环：记录自己触发的版本号
let myLastEmittedVersion = 0

function notifyChange() {
  myLastEmittedVersion = dataVersion.value + 1
  emit('saved')
}

// ==================== 表单 ====================
const today = new Date().toISOString().substring(0, 10)
const form = ref({
  type: 'expense',
  amount: null,
  category_id: null,
  account_id: null,
  transaction_date: today,
  note: '',
})

const expenseCategories = ref([])
const incomeCategories = ref([])
const allCategories = ref([])
const accounts = ref([])

const currentCategories = computed(() =>
  form.value.type === 'expense' ? expenseCategories.value : incomeCategories.value
)

function switchType(t) {
  form.value.type = t
  form.value.category_id = currentCategories.value[0]?.id || null
}

async function loadFormData() {
  try {
    const [ec, ic, accs] = await Promise.all([
      fetchCategories('expense'),
      fetchCategories('income'),
      fetchAccounts(),
    ])
    expenseCategories.value = ec
    incomeCategories.value = ic
    allCategories.value = [...ec, ...ic]
    accounts.value = accs
    if (!form.value.category_id) {
      form.value.category_id = ec[0]?.id || null
    }
    if (!form.value.account_id) {
      form.value.account_id = accs[0]?.id || null
    }
  } catch (e) {
    console.error('加载表单数据失败:', e)
  }
}

async function handleSubmit() {
  if (!form.value.amount || form.value.amount <= 0) {
    showToast('请输入有效金额', 'error')
    return
  }
  try {
    await createTransaction({
      type: form.value.type,
      amount: form.value.amount,
      category_id: form.value.category_id,
      account_id: form.value.account_id,
      transaction_date: form.value.transaction_date,
      note: form.value.note,
    })
    showToast('记账成功！')
    form.value.amount = null
    form.value.note = ''
    await loadTxns()
    notifyChange()
  } catch (e) {
    showToast(e.message, 'error')
  }
}

// ==================== AI 解析 ====================
const aiText = ref('')
const aiLoading = ref(false)
const aiResult = ref(null)
const aiResultSource = ref(null) // 'text' | 'voice'

// 用户可编辑的 AI 解析结果副本
const editAIResult = ref({
  amount: null,
  category_id: null,
  account_id: null,
  transaction_date: today,
  note: '',
})

/** 根据分类名称匹配 category_id，找不到返回 null */
function findCategoryId(name, type) {
  const list = type === 'income' ? incomeCategories.value : expenseCategories.value
  const found = list.find(c => c.name === name)
  return found ? found.id : list[0]?.id || null
}

/** 根据账户名称匹配 account_id */
function findAccountId(name) {
  const found = accounts.value.find(a => a.name === name)
  return found ? found.id : accounts.value[0]?.id || null
}

async function doAIParse(source = 'text') {
  if (!aiText.value.trim()) return
  aiLoading.value = true
  aiResult.value = null
  aiResultSource.value = source
  try {
    const r = await aiParse(aiText.value)
    aiResult.value = r
    // 初始化可编辑副本
    editAIResult.value = {
      amount: parseFloat(r.amount) || 0,
      category_id: findCategoryId(r.category_name, r.type),
      account_id: findAccountId(r.account_name),
      transaction_date: r.transaction_date || today,
      note: r.note || '',
    }
  } catch (e) {
    showToast('解析失败: ' + e.message, 'error')
  } finally {
    aiLoading.value = false
  }
}

function cancelAI() {
  aiResult.value = null
  aiResultSource.value = null
}

async function confirmAI() {
  if (!aiResult.value || !editAIResult.value.amount) {
    showToast('请输入有效金额', 'error')
    return
  }
  try {
    // 使用用户编辑后的值（而非原始 AI 结果）
    const cat = allCategories.value.find(c => c.id === editAIResult.value.category_id)
    const acc = accounts.value.find(a => a.id === editAIResult.value.account_id)
    await createTransaction({
      type: aiResult.value.type,
      amount: editAIResult.value.amount,
      category_id: editAIResult.value.category_id,
      account_id: editAIResult.value.account_id,
      transaction_date: editAIResult.value.transaction_date,
      note: editAIResult.value.note,
    })
    showToast('记账成功！')
    aiText.value = ''
    aiResult.value = null
    aiResultSource.value = null
    await loadTxns()
    notifyChange()
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error')
  }
}

// ==================== 语音输入 (Web Speech API) ====================
const isSpeechSupported = ref(false)
const isListening = ref(false)
let recognition = null
let speechDestroyed = false  // 防止卸载后回调修改状态

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    isSpeechSupported.value = false
    return
  }

  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = false
  recognition.continuous = false
  recognition.maxAlternatives = 1

  recognition.onresult = (event) => {
    if (speechDestroyed) return
    const transcript = event.results[0][0].transcript.trim()
    if (transcript) {
      if (aiText.value && !aiText.value.endsWith(' ')) {
        aiText.value += ' '
      }
      aiText.value += transcript
      doAIParse('voice')
    }
  }

  recognition.onerror = (event) => {
    if (speechDestroyed) return
    console.warn('语音识别错误:', event.error)
    isListening.value = false
    const msgs = {
      'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许',
      'no-speech': '未检测到语音，请重试',
      'audio-capture': '未找到麦克风设备',
      'network': '语音识别需要网络连接',
    }
    showToast(msgs[event.error] || ('语音识别失败: ' + event.error), 'error')
  }

  recognition.onend = () => {
    if (speechDestroyed) return
    isListening.value = false
  }

  isSpeechSupported.value = true
}

function toggleVoiceInput() {
  if (!recognition) {
    showToast('浏览器不支持语音识别', 'error')
    return
  }
  if (isListening.value) {
    recognition.stop()
    isListening.value = false
  } else {
    try {
      recognition.start()
      isListening.value = true
    } catch (e) {
      // 已在录音中，先停止再重新开始
      recognition.stop()
      setTimeout(() => {
        try {
          recognition.start()
          isListening.value = true
        } catch (e2) {
          console.error('语音识别启动失败:', e2)
          showToast('语音识别启动失败，请重试', 'error')
        }
      }, 100)
    }
  }
}

// ==================== 流水列表 ====================
const txnData = ref({ total: 0, items: [], total_income: '0', total_expense: '0' })
const page = ref(1)
const pageSize = 15
const filterWeek = ref('')
const filterCategory = ref('')
const filterType = ref('')

async function loadTxns() {
  try {
    const params = {
      year: props.year,
      month: props.month,
      page: page.value,
      page_size: pageSize,
    }
    if (filterWeek.value) params.week = filterWeek.value
    if (filterCategory.value) params.category_id = filterCategory.value
    if (filterType.value) params.type = filterType.value
    txnData.value = await fetchTransactions(params)
  } catch (e) {
    console.error('加载流水失败:', e)
  }
}

async function doDelete(id) {
  if (!confirm('确定删除这条记录吗？')) return
  try {
    await deleteTransaction(id)
    showToast('已删除')
    await loadTxns()
    notifyChange()
  } catch (e) {
    showToast(e.message, 'error')
  }
}

function fmt(val) {
  const n = parseFloat(val)
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

function fmtAI(val) {
  const n = parseFloat(val)
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

onMounted(() => {
  loadFormData()
  loadTxns()
  initSpeechRecognition()
})

onUnmounted(() => {
  speechDestroyed = true
  if (recognition) {
    try { recognition.abort() } catch (e) { /* ignore */ }
    recognition = null
  }
})
// 筛选条件/分页变化 → 加载流水（300ms 防抖，避免快速切换时竞态请求）
let txnDebounceTimer = null
watch([filterWeek, filterCategory, filterType, page], () => {
  clearTimeout(txnDebounceTimer)
  txnDebounceTimer = setTimeout(() => loadTxns(), 300)
}, { flush: 'pre' })

// 月份切换：重置页码，通过 watcher 链触发一次 loadTxns
watch(() => [props.year, props.month], () => { page.value = 1 })

// 外部数据变更通知（其他组件做了操作）
watch(dataVersion, (newVal) => {
  if (newVal === myLastEmittedVersion) return
  loadTxns()
  loadFormData()
})
</script>
