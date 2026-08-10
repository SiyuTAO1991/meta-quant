<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>采集任务管理</h2>
        <p>手动触发 Tushare / AkShare 采集，并查看执行日志</p>
      </div>
      <div class="toolbar">
        <el-input v-model="tsCodes" style="width: 280px" placeholder="可选：600519.SH,000001.SZ" />
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
            <el-button size="small" type="primary" :loading="triggering === row.task_id" @click="trigger(row)">
              触发
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="panel">
      <div class="page-header" style="margin-bottom: 10px">
        <h2 style="font-size: 16px; margin: 0">执行日志</h2>
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
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              @click="retry(row)"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const tasks = ref([])
const logs = ref([])
const tsCodes = ref('600519.SH,000001.SZ')
const loadingTasks = ref(false)
const loadingLogs = ref(false)
const triggering = ref('')

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
  } finally {
    loadingLogs.value = false
  }
}

async function refresh() {
  await Promise.all([loadTasks(), loadLogs()])
}

async function trigger(row) {
  triggering.value = row.task_id
  try {
    const data = await api.crawlTrigger({
      task_id: row.task_id,
      ts_codes: tsCodes.value,
    })
    ElMessage.success(data?.message || '已触发')
    await loadLogs()
  } finally {
    triggering.value = ''
  }
}

async function retry(row) {
  const data = await api.crawlRetry({ log_id: row.id })
  ElMessage.success(data?.message || '已重试')
  await loadLogs()
}

onMounted(refresh)
</script>
