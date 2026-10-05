<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>采集任务管理</h2>
        <p>手动触发 Tushare / AkShare 采集，并查看执行日志（耗时任务后台执行）</p>
      </div>
      <div class="toolbar">
        <el-button @click="refresh">刷新</el-button>
      </div>
    </div>

    <div class="panel">
      <el-table :data="tasks" stripe v-loading="loadingTasks">
        <el-table-column prop="task_id" label="任务ID" width="140" />
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="cron" label="Cron" width="140" />
        <el-table-column prop="description" label="说明" min-width="220" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="triggering === row.task_id" @click="openTrigger(row)">
              触发
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="panel">
      <div class="page-header" style="margin-bottom: 10px">
        <h2 style="font-size: 16px; margin: 0">执行日志</h2>
        <span v-if="polling" class="muted" style="font-size: 12px">后台任务执行中，自动刷新中…</span>
      </div>
      <el-table :data="logs" stripe v-loading="loadingLogs">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="task_id" label="任务" width="120" />
        <el-table-column prop="task_name" label="名称" width="140" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rows_affected" label="影响行数" width="100" />
        <el-table-column prop="message" label="消息" min-width="220" show-overflow-tooltip />
        <el-table-column prop="started_at" label="开始时间" width="170" />
        <el-table-column prop="finished_at" label="结束时间" width="170" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="row.status === 'failed'" size="small" @click="retry(row)">重试</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="`触发任务：${currentTask?.name || ''}`"
      width="520px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="采集日期" prop="range">
          <el-date-picker
            v-model="form.range"
            type="daterange"
            value-format="YYYYMMDD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="needStock" label="股票代码" prop="tsCodes">
          <el-input
            v-model="form.tsCodes"
            type="textarea"
            :rows="3"
            placeholder="多个代码用逗号分隔，如 600519.SH,000001.SZ；日线留空=按交易日采集全市场 A 股"
          />
          <div class="form-tip">不填则采集 A 股全市场（约五千只，耗时较长）；填写则仅采集指定股票</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="!!triggering" @click="submitTrigger">确认触发</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { api } from '@/api'

const tasks = ref([])
const logs = ref([])
const loadingTasks = ref(false)
const loadingLogs = ref(false)
const triggering = ref('')
const dialogVisible = ref(false)
const currentTask = ref(null)
const formRef = ref()
const polling = ref(false)
let pollTimer = null

const form = reactive({
  range: [dayjs().subtract(30, 'day').format('YYYYMMDD'), dayjs().format('YYYYMMDD')],
  tsCodes: '',
})

const needStock = computed(() => currentTask.value?.need_stock !== false)

const formRules = {
  range: [{ required: true, message: '请选择采集日期', trigger: 'change' }],
}

async function loadTasks() {
  loadingTasks.value = true
  try {
    tasks.value = (await api.crawlTaskList()) || []
  } finally {
    loadingTasks.value = false
  }
}

async function loadLogs() {
  loadingLogs.value = true
  try {
    const data = await api.crawlLog({ task_id: '', start_date: '', page: 1, size: 50 })
    logs.value = data?.items || []
    const hasRunning = logs.value.some((i) => i.status === 'running')
    if (hasRunning) startPolling()
    else stopPolling()
  } finally {
    loadingLogs.value = false
  }
}

async function refresh() {
  await Promise.all([loadTasks(), loadLogs()])
}

function startPolling() {
  if (pollTimer) return
  polling.value = true
  pollTimer = setInterval(async () => {
    try {
      const data = await api.crawlLog({ task_id: '', start_date: '', page: 1, size: 50 })
      logs.value = data?.items || []
      if (!logs.value.some((i) => i.status === 'running')) {
        stopPolling()
      }
    } catch {
      // ignore transient poll errors
    }
  }, 3000)
}

function stopPolling() {
  polling.value = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function openTrigger(row) {
  currentTask.value = row
  form.range = [dayjs().subtract(30, 'day').format('YYYYMMDD'), dayjs().format('YYYYMMDD')]
  form.tsCodes = ''
  dialogVisible.value = true
}

async function submitTrigger() {
  if (!formRef.value || !currentTask.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  const [start, end] = form.range || []
  if (!start || !end) {
    ElMessage.warning('请选择采集日期')
    return
  }

  triggering.value = currentTask.value.task_id
  try {
    const data = await api.crawlTrigger({
      task_id: currentTask.value.task_id,
      ts_codes: needStock.value ? form.tsCodes.trim() : '',
      start_date: start,
      end_date: end,
    })
    ElMessage.success(data?.message || '任务已提交后台执行')
    dialogVisible.value = false
    await loadLogs()
    startPolling()
  } finally {
    triggering.value = ''
  }
}

async function retry(row) {
  const data = await api.crawlRetry({ log_id: row.id })
  ElMessage.success(data?.message || '已提交重试')
  await loadLogs()
  startPolling()
}

onMounted(refresh)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--mq-muted, #6b7280);
  line-height: 1.4;
}
</style>
