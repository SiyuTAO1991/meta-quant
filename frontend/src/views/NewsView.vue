<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>财经新闻</h2>
        <p>个股新闻与全市场热点资讯</p>
      </div>
      <div class="toolbar">
        <el-radio-group v-model="mode">
          <el-radio-button value="hot">热点</el-radio-button>
          <el-radio-button value="stock">个股</el-radio-button>
        </el-radio-group>
        <el-input v-if="mode === 'stock'" v-model="tsCode" style="width: 150px" placeholder="股票代码" />
        <el-input v-if="mode === 'stock'" v-model="keyword" style="width: 150px" placeholder="关键词" />
        <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <div class="panel">
      <el-table :data="items" stripe v-loading="loading" @row-click="openDetail">
        <el-table-column prop="published_at" label="时间" width="170" />
        <el-table-column prop="stock_code" label="代码" width="110" />
        <el-table-column prop="title" label="标题" min-width="280" />
        <el-table-column prop="sentiment" label="情绪" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.sentiment === 'positive' ? 'danger' : row.sentiment === 'negative' ? 'success' : 'info'"
            >
              {{ row.sentiment || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="is_important" label="重要" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_important" type="warning" size="small">是</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
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

    <el-drawer v-model="drawer" title="新闻详情" size="40%">
      <template v-if="detail">
        <h3>{{ detail.title }}</h3>
        <p class="muted">{{ detail.published_at }} · {{ detail.source }} · {{ detail.stock_code }}</p>
        <el-divider />
        <p style="white-space: pre-wrap; line-height: 1.7">{{ detail.content || '暂无正文' }}</p>
        <el-link v-if="detail.source_url" :href="detail.source_url" target="_blank" type="primary">
          打开原文
        </el-link>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api'

const mode = ref('hot')
const tsCode = ref('600519.SH')
const keyword = ref('')
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
    const data =
      mode.value === 'hot'
        ? await api.newsHot({ page: page.value, size })
        : await api.newsStock({
            ts_code: tsCode.value.trim(),
            keyword: keyword.value,
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
  detail.value = await api.newsDetail({ news_id: row.id })
  drawer.value = true
}

watch(mode, () => {
  page.value = 1
  loadData()
})

onMounted(loadData)
</script>
