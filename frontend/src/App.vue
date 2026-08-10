<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <div class="brand-mark">MQ</div>
        <div>
          <div class="brand-name">Meta Quant</div>
          <div class="brand-sub">量化数据平台</div>
        </div>
      </div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.meta.icon" /></el-icon>
          <span>{{ item.meta.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-title">{{ route.meta.title }}</div>
        <div class="header-right">
          <el-tag :type="healthOk ? 'success' : 'danger'" effect="plain" size="small">
            API {{ healthOk ? '正常' : '异常' }}
          </el-tag>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const healthOk = ref(false)

const menus = computed(() =>
  router.getRoutes().filter((r) => r.meta?.title && r.path !== '/'),
)

onMounted(async () => {
  try {
    const h = await api.health()
    healthOk.value = h?.status === 'up'
  } catch {
    healthOk.value = false
  }
})
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.aside {
  background: #0b1220;
  color: #e5e7eb;
  border-right: 1px solid #111827;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px 12px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, #14b8a6, #0f766e);
  font-weight: 700;
}

.brand-name {
  font-weight: 700;
  font-size: 16px;
}

.brand-sub {
  font-size: 12px;
  color: #9ca3af;
}

.menu {
  border-right: none;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  color: #cbd5e1;
}

.menu :deep(.el-menu-item.is-active) {
  background: rgba(20, 184, 166, 0.15);
  color: #5eead4;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid var(--mq-border);
}

.header-title {
  font-size: 18px;
  font-weight: 600;
}

.main {
  padding: 18px;
}
</style>
