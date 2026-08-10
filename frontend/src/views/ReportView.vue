<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>券商研报 / 一致预期</h2>
        <p>盈利预测、目标价与评级检索</p>
      </div>
      <div class="toolbar">
        <el-input v-model="tsCode" style="width: 150px" placeholder="股票代码" />
        <el-input v-model="org" style="width: 140px" placeholder="机构" />
        <el-input v-model="rating" style="width: 120px" placeholder="评级" />
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </div>

    <div class="panel">
      <el-table :data="items" stripe v-loading="loading" @row-click="openDetail">
        <el-table-column prop="report_date" label="日期" width="120" />
        <el-table-column prop="stock_code" label="代码" width="110" />
        <el-table-column prop="broker" label="机构" min-width="160" />
        <el-table-column prop="rating" label="评级" width="100" />
        <el-table-column prop="target_price" label="目标价" width="100" />
        <el-table-column prop="eps_forecast_current" label="当年EPS" width="110" />
        <el-table-column prop="eps_forecast_next" label="次年EPS" width="110" />
        <el-table-column prop="revenue_forecast" label="营收预测" width="120" />
      </el-table>
      <div style="margin-top: 12px; display: flex; justify-content: flex-end">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          v-model:current-page="page"
          :page-size="size"
          @current-change="loadData"
        />
      </div>
    </div>

    <el-drawer v-model="drawer" title="研报详情" size="36%">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="代码">{{ detail.stock_code }}</el-descriptions-item>
        <el-descriptions-item label="机构">{{ detail.broker }}</el-descriptions-item>
        <el-descriptions-item label="日期">{{ detail.report_date }}</el-descriptions-item>
        <el-descriptions-item label="评级">{{ detail.rating }}</el-descriptions-item>
        <el-descriptions-item label="目标价">{{ detail.target_price }}</el-descriptions-item>
        <el-descriptions-item label="当年EPS">{{ detail.eps_forecast_current }}</el-descriptions-item>
        <el-descriptions-item label="次年EPS">{{ detail.eps_forecast_next }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ detail.source_file }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api'

const tsCode = ref('600519.SH')
const org = ref('')
const rating = ref('')
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const drawer = ref(false)
const detail = ref(null)

async function loadData() {
  loading.value = true
  try {
    const data = await api.reportList({
      ts_code: tsCode.value.trim(),
      org: org.value,
      rating: rating.value,
      page: page.value,
      size,
    })
    items.value = data?.items || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  detail.value = await api.reportDetail({ report_id: row.id })
  drawer.value = true
}

onMounted(loadData)
</script>
