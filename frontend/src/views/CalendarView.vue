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
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
      </div>
    </div>

    <div class="panel">
      <el-table :data="items" stripe v-loading="loading">
        <el-table-column prop="event_date" label="日期" width="120" />
        <el-table-column prop="event_time" label="时间" width="90" />
        <el-table-column prop="country" label="国家" width="90" />
        <el-table-column prop="category" label="类别" width="110" />
        <el-table-column prop="title" label="事件" min-width="240" />
        <el-table-column prop="importance" label="重要性" width="120">
          <template #default="{ row }">
            <span v-if="!row.importance" class="muted">未知</span>
            <el-rate v-else :model-value="row.importance" disabled :max="3" />
          </template>
        </el-table-column>
        <el-table-column prop="previous_value" label="前值" width="90" />
        <el-table-column prop="forecast_value" label="预期" width="90" />
        <el-table-column prop="actual_value" label="实际" width="90" />
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          v-model:current-page="page"
          v-model:page-size="size"
          :page-sizes="[20, 50, 100]"
          @current-change="loadData"
          @size-change="onSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { api } from '@/api'

const range = ref([dayjs().format('YYYYMMDD'), dayjs().add(14, 'day').format('YYYYMMDD')])
const level = ref('medium')
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const mode = ref('range') // range | today

async function loadData() {
  loading.value = true
  try {
    let data
    if (mode.value === 'today') {
      data = await api.calendarToday({
        level: level.value || '',
        page: page.value,
        size: size.value,
      })
    } else {
      const [start, end] = range.value || []
      data = await api.calendarList({
        start_date: start,
        end_date: end,
        level: level.value || '',
        page: page.value,
        size: size.value,
      })
    }
    items.value = data?.items || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

function search() {
  mode.value = 'range'
  page.value = 1
  loadData()
}

function loadToday() {
  mode.value = 'today'
  page.value = 1
  loadData()
}

function onSizeChange() {
  page.value = 1
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
