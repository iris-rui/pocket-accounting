<template>
  <div class="chat-page">
    <!-- 聊天头部 -->
    <div class="chat-header">
      <div class="chat-header-left">
        <span class="chat-avatar">🦘</span>
        <div class="chat-header-info">
          <h3 class="chat-title">小袋 · 毒舌财务管家</h3>
          <span class="chat-subtitle">数据不撒谎，但我嘴很毒 😈</span>
        </div>
      </div>
    </div>

    <!-- 聊天消息区域 -->
    <div class="chat-messages" ref="chatContainer">
      <!-- 空状态提示 -->
      <div v-if="messages.length === 0 && !loading" class="message-row ai">
        <span class="message-avatar">🦘</span>
        <div class="message-bubble">
          <p>把账单发过来，我来告诉你这个月钱都花哪去了。</p>
          <p>别指望我嘴下留情 😏</p>
          <span class="message-time">{{ nowTime }}</span>
        </div>
      </div>

      <!-- 消息列表 -->
      <template v-for="(msg, idx) in messages" :key="idx">
        <!-- 用户消息 — 头像在左侧 -->
        <div v-if="msg.role === 'user'" class="message-row user">
          <span class="message-avatar">👤</span>
          <div class="message-bubble bubble-user">
            <p>{{ msg.text }}</p>
            <span class="message-time">{{ msg.time }}</span>
          </div>
        </div>

        <!-- AI 消息 -->
        <div v-else class="message-row ai">
          <span class="message-avatar">{{ msg.icon || '🦘' }}</span>
          <div class="message-bubble">
            <div v-if="msg.label" class="bubble-label">{{ msg.label }}</div>
            <p v-if="msg.text">{{ msg.text }}</p>
            <span class="message-time">{{ msg.time }}</span>
          </div>
        </div>
      </template>

      <!-- 加载中 -->
      <div v-if="loading" class="message-row ai">
        <span class="message-avatar">🦘</span>
        <div class="message-bubble bubble-typing">
          <div class="typing-dots">
            <span></span><span></span><span></span>
          </div>
          <span class="typing-text">{{ loadingText }}</span>
        </div>
      </div>
    </div>

    <!-- 聊天输入区 -->
    <div class="chat-input-area">
      <div class="chat-input-row">
        <button
          v-if="isSpeechSupported"
          class="btn-mic-chat"
          :class="{ recording: isListening }"
          @click="toggleVoiceInput"
          :title="isListening ? '点击停止录音' : '语音输入'"
          :disabled="loading"
        >
          {{ isListening ? '🔴' : '🎤' }}
        </button>
        <input
          v-model="chatInput"
          class="chat-input"
          placeholder="说说你花了多少钱..."
          :disabled="loading"
          @keyup.enter="handleSend"
        />
        <button class="btn-send" :disabled="loading || !chatInput.trim()" @click="handleSend">
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, inject } from 'vue'
import { fetchAIAdvice } from '../api/index.js'

const props = defineProps({ year: Number, month: Number })
const showToast = inject('showToast', () => {})

const chatInput = ref('')
const loading = ref(false)
const loadingText = ref('让我看看你的账单...')
const chatContainer = ref(null)
const messages = ref([])

const nowTime = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

function timeNow() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// ==================== 发送消息 ====================
async function handleSend() {
  const text = chatInput.value.trim()
  if (!text || loading.value) return
  chatInput.value = ''

  messages.value.push({ role: 'user', text, time: timeNow() })
  scrollToBottom()

  loading.value = true
  loadingText.value = '让我看看你的账单...'
  await doAdvice()
  loading.value = false
  scrollToBottom()
}

// ==================== AI 财务分析 ====================
async function doAdvice() {
  try {
    const advice = await fetchAIAdvice(props.year, props.month)

    if (advice.spending_summary) {
      messages.value.push({
        role: 'ai',
        type: 'text',
        label: '📋 消费概况',
        text: advice.spending_summary,
        icon: '📊',
        time: timeNow(),
      })
    }

    if (advice.advice) {
      messages.value.push({
        role: 'ai',
        type: 'text',
        label: '💀 毒舌点评',
        text: advice.advice,
        icon: '🦘',
        time: timeNow(),
      })
    }
  } catch (e) {
    messages.value.push({
      role: 'ai',
      type: 'text',
      text: '😵 分析失败：' + e.message,
      label: '⚠️ 错误',
      time: timeNow(),
    })
  }
}

// ==================== 语音输入 ====================
const isSpeechSupported = ref(false)
const isListening = ref(false)
let recognition = null
let speechDestroyed = false

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
      chatInput.value = transcript
      handleSend()
    }
  }

  recognition.onerror = (event) => {
    if (speechDestroyed) return
    console.warn('语音识别错误:', event.error)
    isListening.value = false
    const messages = {
      'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许',
      'no-speech': '未检测到语音，请重试',
      'audio-capture': '未找到麦克风设备',
      'network': '语音识别需要网络连接',
    }
    showToast(messages[event.error] || ('语音识别失败: ' + event.error), 'error')
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
      recognition.stop()
      setTimeout(() => {
        try { recognition.start(); isListening.value = true } catch (e2) { /* ignore */ }
      }, 100)
    }
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  initSpeechRecognition()
})

// 月份切换时清空对话（数据已过时）
watch(() => [props.year, props.month], () => {
  messages.value = []
})

onUnmounted(() => {
  speechDestroyed = true
  if (recognition) {
    try { recognition.abort() } catch (e) { /* ignore */ }
    recognition = null
  }
})
</script>
