<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>财报问答</h2>
        <p>上传 PDF 年报 → 百炼 Embedding + FAISS 建索 → DeepSeek 单文档问答</p>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :md="9">
        <div class="panel">
          <div class="panel-title">上传财报</div>
          <el-form :model="uploadForm" label-width="88px" class="upload-form">
            <el-form-item label="股票代码" required>
              <el-input v-model="uploadForm.stock_code" placeholder="如 688981.SH" clearable />
            </el-form-item>
            <el-form-item label="股票名称">
              <el-input v-model="uploadForm.stock_name" placeholder="可选" clearable />
            </el-form-item>
            <el-form-item label="报告类型">
              <el-select v-model="uploadForm.report_type" style="width: 100%">
                <el-option
                  v-for="t in reportTypes"
                  :key="t.value"
                  :label="t.label"
                  :value="t.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="报告期">
              <el-input v-model="uploadForm.report_period" placeholder="如 2025" clearable />
            </el-form-item>
            <el-form-item label="标题">
              <el-input v-model="uploadForm.title" placeholder="可选，默认用文件名" clearable />
            </el-form-item>
            <el-form-item label="PDF">
              <el-upload
                ref="uploadRef"
                drag
                :auto-upload="false"
                :limit="1"
                accept=".pdf,application/pdf"
                :on-change="onFileChange"
                :on-remove="onFileRemove"
              >
                <div class="el-upload__text">将 PDF 拖到此处，或<em>点击选择</em></div>
              </el-upload>
            </el-form-item>
            <el-button type="primary" :loading="uploading" style="width: 100%" @click="doUpload">
              上传并自动建索
            </el-button>
          </el-form>
        </div>

        <div class="panel" style="margin-top: 12px">
          <div class="panel-title-row">
            <div class="panel-title">文档列表</div>
            <el-button size="small" :loading="listLoading" @click="loadDocs">刷新</el-button>
          </div>
          <el-input
            v-model="filterCode"
            size="small"
            clearable
            placeholder="按股票代码筛选"
            style="margin-bottom: 8px"
            @change="loadDocs"
          />
          <el-table
            :data="docs"
            size="small"
            stripe
            highlight-current-row
            max-height="360"
            @current-change="onSelectDoc"
          >
            <el-table-column prop="stock_code" label="代码" width="100" />
            <el-table-column prop="title" label="标题" min-width="120" show-overflow-tooltip />
            <el-table-column label="状态" width="88">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="" width="64">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click.stop="doDelete(row)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :md="15">
        <div class="panel chat-panel">
          <div class="panel-title">
            问答
            <span v-if="currentDoc" class="muted">
              · {{ currentDoc.stock_name || currentDoc.stock_code }} · {{ currentDoc.title }}
              · {{ statusLabel(currentDoc.status) }}
            </span>
          </div>

          <div ref="chatBoxRef" class="chat-box">
            <div v-if="!messages.length" class="chat-empty muted">
              请先上传或选择已就绪的财报文档，然后提问。例如：营业收入、净利润、毛利率分别是多少？
            </div>
            <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
              <div class="msg-role">{{ m.role === 'user' ? '我' : '助手' }}</div>
              <div class="msg-body">
                <div class="msg-text">{{ m.content }}</div>
                <div v-if="m.sources?.length" class="sources">
                  <div class="sources-title">来源页码</div>
                  <div v-for="(s, i) in m.sources" :key="i" class="source-item">
                    <el-tag size="small" type="info">第 {{ s.page }} 页</el-tag>
                    <span class="snippet">{{ s.snippet }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="chat-input">
            <el-input
              v-model="question"
              type="textarea"
              :rows="3"
              placeholder="针对当前文档提问…"
              :disabled="!canAsk"
              @keydown.ctrl.enter="doAsk"
            />
            <div class="chat-actions">
              <span class="muted">Ctrl + Enter 发送</span>
              <el-button type="primary" :loading="asking" :disabled="!canAsk" @click="doAsk">
                发送
              </el-button>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const reportTypes = ref([
  { value: 'annual', label: '年报' },
  { value: 'semi', label: '半年报' },
  { value: 'quarter', label: '季报' },
  { value: 'other', label: '其他' },
])

const uploadForm = reactive({
  stock_code: '',
  stock_name: '',
  report_type: 'annual',
  report_period: '',
  title: '',
})
const fileRaw = ref(null)
const uploadRef = ref(null)
const uploading = ref(false)

const filterCode = ref('')
const docs = ref([])
const listLoading = ref(false)
const currentDoc = ref(null)
const pollTimer = ref(null)

const question = ref('')
const asking = ref(false)
const messages = ref([])
const chatBoxRef = ref(null)

const canAsk = computed(() => currentDoc.value?.status === 'ready' && !asking.value)

function statusLabel(s) {
  return (
    {
      uploaded: '已上传',
      indexing: '建索中',
      ready: '就绪',
      failed: '失败',
    }[s] || s
  )
}

function statusType(s) {
  return (
    {
      uploaded: 'info',
      indexing: 'warning',
      ready: 'success',
      failed: 'danger',
    }[s] || 'info'
  )
}

function onFileChange(file) {
  fileRaw.value = file?.raw || null
}

function onFileRemove() {
  fileRaw.value = null
}

async function doUpload() {
  if (!uploadForm.stock_code.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  if (!fileRaw.value) {
    ElMessage.warning('请选择 PDF 文件')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', fileRaw.value)
    fd.append('stock_code', uploadForm.stock_code.trim())
    fd.append('stock_name', uploadForm.stock_name.trim())
    fd.append('report_type', uploadForm.report_type)
    fd.append('report_period', uploadForm.report_period.trim())
    fd.append('title', uploadForm.title.trim())
    const doc = await api.ragUpload(fd)
    ElMessage.success('已上传，正在后台建索')
    fileRaw.value = null
    uploadRef.value?.clearFiles?.()
    await loadDocs()
    currentDoc.value = doc
    messages.value = []
    startPollIfNeeded()
  } finally {
    uploading.value = false
  }
}

async function loadDocs() {
  listLoading.value = true
  try {
    const data = await api.ragDocList({
      stock_code: filterCode.value.trim(),
      page: 1,
      size: 50,
    })
    docs.value = data?.items || []
    if (currentDoc.value) {
      const fresh = docs.value.find((d) => d.id === currentDoc.value.id)
      if (fresh) currentDoc.value = fresh
    }
  } finally {
    listLoading.value = false
  }
}

function onSelectDoc(row) {
  if (!row) return
  currentDoc.value = row
  messages.value = []
  startPollIfNeeded()
}

async function doDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」？`, '删除文档', { type: 'warning' })
    await api.ragDocDelete({ doc_id: row.id })
    if (currentDoc.value?.id === row.id) {
      currentDoc.value = null
      messages.value = []
    }
    ElMessage.success('已删除')
    await loadDocs()
  } catch {
    /* cancel */
  }
}

function startPollIfNeeded() {
  stopPoll()
  if (!currentDoc.value || !['uploaded', 'indexing'].includes(currentDoc.value.status)) return
  pollTimer.value = setInterval(async () => {
    if (!currentDoc.value) return
    try {
      const detail = await api.ragDocDetail({ doc_id: currentDoc.value.id })
      currentDoc.value = detail
      const idx = docs.value.findIndex((d) => d.id === detail.id)
      if (idx >= 0) docs.value[idx] = detail
      if (detail.status === 'ready') {
        ElMessage.success('建索完成，可以开始提问')
        stopPoll()
      } else if (detail.status === 'failed') {
        ElMessage.error(detail.error_msg || '建索失败')
        stopPoll()
      }
    } catch {
      /* ignore poll errors */
    }
  }, 2500)
}

function stopPoll() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function scrollChat() {
  await nextTick()
  const el = chatBoxRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function doAsk() {
  const q = question.value.trim()
  if (!q || !canAsk.value) return
  asking.value = true
  messages.value.push({ role: 'user', content: q })
  question.value = ''
  await scrollChat()
  try {
    const data = await api.ragAsk({
      doc_id: currentDoc.value.id,
      question: q,
    })
    messages.value.push({
      role: 'assistant',
      content: data?.answer || '（无回答）',
      sources: data?.sources || [],
    })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: `提问失败：${e?.message || e}`,
      sources: [],
    })
  } finally {
    asking.value = false
    await scrollChat()
  }
}

onMounted(async () => {
  try {
    const meta = await api.ragMeta()
    if (meta?.report_types?.length) reportTypes.value = meta.report_types
  } catch {
    /* keep defaults */
  }
  await loadDocs()
})

onBeforeUnmount(() => stopPoll())
</script>

<style scoped>
.panel-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}
.panel-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.panel-title-row .panel-title {
  margin-bottom: 0;
}
.upload-form {
  margin-top: 4px;
}
.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 640px;
}
.chat-box {
  flex: 1;
  min-height: 420px;
  max-height: 560px;
  overflow: auto;
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 10px;
  padding: 12px;
  background: #f8fafc;
}
.chat-empty {
  padding: 40px 12px;
  text-align: center;
  font-size: 13px;
}
.msg {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.msg-role {
  flex: 0 0 36px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  background: #e2e8f0;
  color: #334155;
}
.msg.user .msg-role {
  background: #0f766e;
  color: #fff;
}
.msg-body {
  flex: 1;
  min-width: 0;
}
.msg-text {
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 10px;
  padding: 10px 12px;
}
.sources {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
}
.sources-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
}
.source-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 6px;
  font-size: 12px;
}
.snippet {
  color: #475569;
  line-height: 1.4;
}
.chat-input {
  margin-top: 12px;
}
.chat-actions {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.muted {
  color: #6b7280;
  font-size: 13px;
  font-weight: 400;
}
</style>
