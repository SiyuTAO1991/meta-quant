<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>财经日历</h2>
        <p>经济数据发布、政策会议与重要事件</p>
      </div>
      <div class="toolbar">
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYYMMDD"
          start-placeholder="开始"
          end-placeholder="结束"
        />
        <el-select v-model="level" clearable placeholder="重要性" style="width: 120px">
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
        <el-button @click="loadToday">今日</el-button>
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </div>

    <div class="panel">
      <el-table :data="items" stripe v-loading="loading">
        <el-table-column prop="event_date" label="日期" width="120" />
        <el-table-column prop="event_time" label="时间" width="90" />
        <el-table-column prop="country" label="国家" width="90" />
        <el-table-column prop="category" label="类别" width="110" />
        <el-table-column prop="title" label="事件" min-width="240" />
        <el-table-column prop="importance" label="重要性" width="100">
          <template #default="{ row }">
            <el-rate :model-value="row.importance || 0" disabled :max="3" />
          </template>
        </el-table-column>
        <el-table-column prop="previous_value" label="前值" width="90" />
        <el-table-column prop="forecast_value" label="预期" width="90" />
        <el-table-column prop="actual_value" label="实际" width="90" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { api } from '@/api'

const range = ref([dayjs().format('YYYYMMDD'), dayjs().add(14, 'day').format('YYYYMMDD')])
const level = ref('high')
const loading = ref(false)
const items = ref([])

async function loadData() {
  loading.value = true
  try {
    const [start, end] = range.value || []
    items.value = (await api.calendarList({ start_date: start, end_date: end, level: level.value || '' })) || []
  } finally {
    loading.value = false
  }
}

async function loadToday() {
  loading.value = true
  try {
    items.value = (await api.calendarToday({ level: level.value || '' })) || []
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
