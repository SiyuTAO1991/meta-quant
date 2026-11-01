import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/backtest' },
  {
    path: '/backtest',
    name: 'backtest',
    component: () => import('@/views/BacktestView.vue'),
    meta: { title: '策略回测', icon: 'Histogram' },
  },
  {
    path: '/chan-backtest',
    name: 'chan-backtest',
    component: () => import('@/views/ChanBacktestView.vue'),
    meta: { title: '缠论回测', icon: 'TrendCharts' },
  },
  {
    path: '/factor',
    name: 'factor',
    component: () => import('@/views/FactorView.vue'),
    meta: { title: '因子库', icon: 'DataAnalysis' },
  },
  {
    path: '/multi-factor',
    name: 'multi-factor',
    component: () => import('@/views/MultiFactorView.vue'),
    meta: { title: '多因子打分', icon: 'Grid' },
  },
  {
    path: '/gbdt',
    name: 'gbdt',
    component: () => import('@/views/GbdtView.vue'),
    meta: { title: 'GBDT预测', icon: 'Cpu' },
  },
  { path: '/xgboost', redirect: '/gbdt' },
  { path: '/lightgbm', redirect: '/gbdt' },
  {
    path: '/rag',
    name: 'rag',
    component: () => import('@/views/RagView.vue'),
    meta: { title: '财报问答', icon: 'ChatDotRound' },
  },
  {
    path: '/crawl',
    name: 'crawl',
    component: () => import('@/views/CrawlView.vue'),
    meta: { title: '采集任务', icon: 'Setting' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
