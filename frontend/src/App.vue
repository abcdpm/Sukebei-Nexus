<template>
  <div class="min-h-screen bg-bus-bg text-bus-text-main pb-12 font-sans">
    <nav class="sticky top-0 z-50 bg-bus-card border-b border-bus-border shadow-lg">
      <div class="max-w-[1600px] mx-auto px-4 h-14 flex items-center justify-between">
        <div class="text-bus-text-light font-bold text-xl tracking-wider cursor-pointer" @click="fetchRss(1)">
          Sukebei<span class="text-bus-primary">Nexus</span>
        </div>
        <div class="flex gap-3">
          <button @click="selectAll = !selectAll; handleSelectAll()" class="px-3 py-1.5 text-sm rounded bg-bus-bg border border-bus-border hover:bg-bus-card-hover transition-colors">
            {{ selectAll ? '取消全选' : '全选本页' }}
          </button>
          <button @click="pushSelected" :disabled="selectedCodes.length === 0" :class="{'opacity-50': pushing}" class="px-3 py-1.5 text-sm rounded bg-bus-blue-bg text-bus-text-light hover:bg-opacity-80 transition-colors disabled:opacity-50">
            {{ pushing ? '推送中...' : `推送 qB (${selectedCodes.length})` }}
          </button>
          <button @click="openSettings" class="px-3 py-1.5 rounded bg-bus-bg border border-bus-border hover:bg-bus-card-hover transition-colors">
            ⚙️ 设置
          </button>
        </div>
      </div>
    </nav>

    <main class="max-w-[1600px] mx-auto px-4 mt-6">
      <div v-if="loading" class="flex justify-center items-center py-32 text-bus-text-muted">
        <span class="animate-pulse text-lg tracking-widest">数据库读取中...</span>
      </div>

      <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <ItemCard v-for="item in items" :key="item.code" :item="item" @update="updateSelection" @open-viewer="openViewer" />
      </div>

      <div v-if="!loading && items.length > 0 && totalPages > 1" class="flex justify-center items-center mt-12 mb-8">
        <button @click="fetchRss(currentPage - 1)" :disabled="currentPage <= 1" class="px-3 py-1.5 bg-bus-card border border-bus-border rounded disabled:opacity-50 hover:bg-bus-card-hover mx-1">&lt;</button>
        <div class="flex gap-1 mx-2">
          <button v-for="p in visiblePages" :key="p" @click="fetchRss(p)" class="w-8 h-8 rounded border border-bus-border flex items-center justify-center transition-colors text-sm" :class="currentPage === p ? 'bg-bus-primary text-white border-bus-primary' : 'bg-bus-card hover:bg-bus-card-hover'">
            {{ p }}
          </button>
        </div>
        <button @click="fetchRss(currentPage + 1)" :disabled="currentPage >= totalPages" class="px-3 py-1.5 bg-bus-card border border-bus-border rounded disabled:opacity-50 hover:bg-bus-card-hover mx-1">&gt;</button>
      </div>
    </main>

    <div v-if="showSettings" class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[100]">
      <div class="bg-bus-card border border-bus-border rounded-xl w-[500px] max-w-[90%] shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-bus-border bg-bus-bg">
          <h2 class="text-xl text-bus-text-light font-bold">系统配置中心</h2>
        </div>
        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm text-bus-text-muted mb-1">Nyaa RSS 订阅源</label>
            <input v-model="settings.rss_url" type="text" class="w-full bg-bus-bg border border-bus-border p-2 rounded text-sm text-bus-text-light focus:border-bus-primary">
          </div>
          <div class="flex gap-3">
             <div class="w-2/3">
               <label class="block text-sm text-bus-text-muted mb-1">屏蔽前缀 (逗号分隔)</label>
               <input v-model="settings.block_prefixes" type="text" class="w-full bg-bus-bg border border-bus-border p-2 rounded text-sm text-bus-text-light focus:border-bus-primary">
             </div>
             <div class="w-1/3">
               <label class="block text-sm text-bus-text-muted mb-1">抓取间隔(分钟)</label>
               <input v-model="settings.rss_interval" type="number" min="1" class="w-full bg-bus-bg border border-bus-border p-2 rounded text-sm text-bus-text-light focus:border-bus-primary">
             </div>
          </div>
          <hr class="border-bus-border">
          <div class="space-y-2">
            <label class="block text-sm text-bus-text-muted mb-1">qBittorrent 连接信息</label>
            <input v-model="settings.qb_host" type="text" placeholder="http://192.168.0.2:8080" class="w-full bg-bus-bg border border-bus-border p-2 rounded text-sm text-bus-text-light focus:border-bus-primary">
            <div class="flex gap-3">
              <input v-model="settings.qb_user" type="text" placeholder="用户名" class="w-full bg-bus-bg border border-bus-border p-2 rounded text-sm text-bus-text-light focus:border-bus-primary">
              <input v-model="settings.qb_pass" type="password" placeholder="密码" class="w-full bg-bus-bg border border-bus-border p-2 rounded text-sm text-bus-text-light focus:border-bus-primary">
            </div>
          </div>
          <div v-if="testMsg" :class="testSuccess ? 'text-bus-green' : 'text-bus-danger'" class="text-xs bg-bus-bg p-2 rounded">{{ testMsg }}</div>
        </div>
        <div class="p-4 border-t border-bus-border bg-bus-bg flex justify-between items-center">
          <button @click="testConnection" :disabled="testing" class="text-sm text-bus-primary hover:underline">{{ testing ? '测试中...' : '⚡ 测试 qB' }}</button>
          <div class="flex gap-3">
            <button @click="showSettings = false" class="px-4 py-2 text-sm text-bus-text-muted">取消</button>
            <button @click="saveSettings" class="px-5 py-2 text-sm bg-bus-primary text-white rounded">保存配置</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="viewer.show" class="fixed inset-0 z-[200] bg-black/95 flex flex-col items-center justify-center select-none" @click="viewer.show = false">
      <div class="absolute top-4 right-6 text-white text-4xl cursor-pointer hover:text-bus-primary">&times;</div>
      <div class="absolute top-4 left-6 text-bus-text-muted">{{ viewer.index + 1 }} / {{ viewer.images.length }}</div>
      <button @click.stop="prevImg" class="absolute left-4 top-1/2 -translate-y-1/2 p-6 text-white text-5xl hover:text-bus-primary disabled:opacity-20" :disabled="viewer.index === 0">&#10094;</button>
      <img :src="viewer.images[viewer.index]" class="max-h-[90vh] max-w-[90vw] object-contain shadow-2xl rounded" @click.stop />
      <button @click.stop="nextImg" class="absolute right-4 top-1/2 -translate-y-1/2 p-6 text-white text-5xl hover:text-bus-primary disabled:opacity-20" :disabled="viewer.index === viewer.images.length - 1">&#10095;</button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ItemCard from './components/ItemCard.vue'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''
const items = ref([])
const loading = ref(false)
const selectAll = ref(false)
const selectedCodes = ref([])
const showSettings = ref(false)
const pushing = ref(false)
const testing = ref(false)
const testMsg = ref('')
const testSuccess = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)

const settings = ref({ qb_host: '', qb_user: '', qb_pass: '', rss_url: '', block_prefixes: '', rss_interval: 15 })

const visiblePages = computed(() => {
  const pages = []
  const start = Math.max(1, currentPage.value - 2)
  const end = Math.min(totalPages.value, currentPage.value + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

// 需求3: 写入URL并在翻页时同步
const fetchRss = async (page, pushState = true) => {
  if (page < 1) return
  loading.value = true
  currentPage.value = page
  
  if (pushState) {
    const url = new URL(window.location)
    url.searchParams.set('page', page)
    window.history.pushState({ page }, '', url)
  }
  
  items.value = []
  window.scrollTo({ top: 0, behavior: 'smooth' })
  
  try {
    const res = await fetch(`${API_BASE}/api/rss?page=${page}`)
    const json = await res.json()
    totalPages.value = json.total_pages || 1
    
    // 处理本地图片路径补全
    items.value = json.data.map(item => {
      if (item.meta) {
        if (item.meta.cover?.startsWith('/')) item.meta.cover = API_BASE + item.meta.cover
        if (item.meta.samples) {
            item.meta.samples = item.meta.samples.map(s => s.startsWith('/') ? API_BASE + s : s)
        }
      }
      return { ...item, selected: false }
    })
  } catch (e) {
    console.error('RSS加载失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  document.title = 'SukebeiNexus'
  // 从 URL 读取页码，无页码默认为 1
  const params = new URLSearchParams(window.location.search)
  const p = parseInt(params.get('page')) || 1
  fetchRss(p, false)
  
  // 监听浏览器的前进后退按钮，实现无刷新页面切换
  window.addEventListener('popstate', () => {
    const p = parseInt(new URLSearchParams(window.location.search).get('page')) || 1
    fetchRss(p, false)
  })
})

// --- 其余状态方法 ---
const viewer = ref({ show: false, images: [], index: 0 })
const openViewer = (imagesList, startIndex) => {
  const validImages = imagesList.filter(url => url && url.trim() !== '')
  if (validImages.length === 0) return
  viewer.value = { show: true, images: validImages, index: startIndex }
}
const prevImg = () => { if (viewer.value.index > 0) viewer.value.index-- }
const nextImg = () => { if (viewer.value.index < viewer.value.images.length - 1) viewer.value.index++ }

const openSettings = async () => {
  testMsg.value = ''
  try {
    const res = await fetch(`${API_BASE}/api/settings`)
    settings.value = await res.json()
  } catch (e) {}
  showSettings.value = true
}

const saveSettings = async () => {
  await fetch(`${API_BASE}/api/settings`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings.value) })
  showSettings.value = false
  fetchRss(1) 
}

const testConnection = async () => {
  testing.value = true
  testMsg.value = '正在连接...'
  try {
    const res = await fetch(`${API_BASE}/api/qb/test`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings.value) })
    const data = await res.json()
    testSuccess.value = res.ok
    testMsg.value = data.message || data.detail
  } catch (e) {
    testSuccess.value = false
    testMsg.value = '网络请求失败，请检查后端或局域网设置'
  } finally {
    testing.value = false
  }
}

const handleSelectAll = () => {
  items.value.forEach(item => { if (!item.is_downloaded) item.selected = selectAll.value })
  updateSelection()
}

const updateSelection = () => {
  selectedCodes.value = items.value.filter(i => i.selected)
}

const pushSelected = async () => {
  if (selectedCodes.value.length === 0) return
  pushing.value = true
  try {
    const payload = selectedCodes.value.map(i => ({ code: i.code, title: i.title, link: i.link }))
    const res = await fetch(`${API_BASE}/api/qb/download`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items: payload }) })
    if (res.ok) {
      items.value.forEach(item => { if (item.selected) { item.is_downloaded = true; item.selected = false; }})
      updateSelection()
      selectAll.value = false
    } else {
      const data = await res.json()
      alert('推送失败: ' + data.detail)
    }
  } catch (e) { alert('推送请求异常') } finally { pushing.value = false }
}
</script>