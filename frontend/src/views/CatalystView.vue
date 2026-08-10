<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>事件催化剂看板</h2>
        <p>重要宏观事件 + 个股重要新闻驱动事件</p>
      </div>
      <div class="toolbar">
        <el-input v-model="tsCode" style="width: 150px" placeholder="可选股票代码" clearable />
        <el-input v-model="eventType" style="width: 140px" placeholder="事件类型" clearable />
        <el-select v-model="level" style="width: 120px">
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
        <el-button @click="loadToday">今日总览</el-button>
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </div>

    <div class="cards">
      <div v-for="item in items" :key="item.id || item.title + item.event_date" class="card">
        <div class="card-top">
          <el-tag size="small" effect="plain">{{ item.category || 'event' }}</el-tag>
          <span class="muted">{{ item.event_date }}</span>
        </div>
        <div class="card-title">{{ item.title }}</div>
        <div class="card-meta">
          <span>{{ item.country || item.stock_code || '-' }}</span>
          <el-rate :model-value="item.importance || 0" disabled :max="3" />
        </div>
      </div>
      <el-empty v-if="!items.length && !loading" description="暂无催化剂事件" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { api } from '@/api'

const tsCode = ref('')
const eventType = ref('')
const level = ref('high')
const loading = ref(false)
const items = ref([])

async function loadData() {
  loading.value = true
  try {
    items.value =
      (await api.catalystEvent({
        ts_code: tsCode.value.trim(),
        event_type: eventType.value,
        start_date: dayjs().subtract(7, 'day').format('YYYYMMDD'),
        end_date: dayjs().add(30, 'day').format('YYYYMMDD'),
        level: level.value,
      })) || []
  } finally {
    loading.value = false
  }
}

async function loadToday() {
  loading.value = true
  try {
    items.value = (await api.catalystToday({ level: level.value })) || []
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.card {
  background: #fff;
  border: 1px solid var(--mq-border);
  border-radius: 12px;
  padding: 14px;
}

.card-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
  min-height: 44px;
}

.card-meta {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--mq-muted);
  font-size: 13px;
}
</style>
