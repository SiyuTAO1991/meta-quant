import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/market' },
  {
    path: '/market',
    name: 'market',
    component: () => import('@/views/MarketView.vue'),
    meta: { title: '行情 K 线', icon: 'TrendCharts' },
  },
  {
    path: '/finance',
    name: 'finance',
    component: () => import('@/views/FinanceView.vue'),
    meta: { title: '财务数据', icon: 'Coin' },
  },
  {
    path: '/macro',
    name: 'macro',
    component: () => import('@/views/MacroView.vue'),
    meta: { title: '宏观经济', icon: 'DataLine' },
  },
  {
    path: '/news',
    name: 'news',
    component: () => import('@/views/NewsView.vue'),
    meta: { title: '财经新闻', icon: 'ChatDotRound' },
  },
  {
    path: '/report',
    name: 'report',
    component: () => import('@/views/ReportView.vue'),
    meta: { title: '券商研报', icon: 'Document' },
  },
  {
    path: '/calendar',
    name: 'calendar',
    component: () => import('@/views/CalendarView.vue'),
    meta: { title: '财经日历', icon: 'Calendar' },
  },
  {
    path: '/catalyst',
    name: 'catalyst',
    component: () => import('@/views/CatalystView.vue'),
    meta: { title: '事件催化剂', icon: 'Bell' },
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
