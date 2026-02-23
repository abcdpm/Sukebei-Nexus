<template>
  <div class="min-h-screen bg-bus-bg text-bus-text-main pb-12 font-sans">
    <nav class="sticky top-0 z-50 bg-bus-card border-b border-bus-border shadow-lg">
      <div class="max-w-[1600px] mx-auto px-4 h-14 flex items-center justify-between">
        <div class="text-bus-text-light font-bold text-xl tracking-wider cursor-pointer" @click="fetchRss(1)">
          Sukebei<span class="text-bus-primary">Nexus</span>
        </div>
        
        <div class="flex gap-3">
          <button @click="selectAll = !selectAll; handleSelectAll()" 
                  class="px-3 py-1.5 text-sm rounded bg-bus-bg border border-bus-border hover:bg-bus-card-hover transition-colors">
            {{ selectAll ? '取消全选' : '全选本页' }}
          </button>
          <button @click="pushSelected" :disabled="selectedCodes.length === 0" :class="{'opacity-50': pushing}"
                  class="px-3 py-1.5 text-sm rounded bg-bus-blue-bg text-bus-text-light hover:bg-opacity-80 transition-colors disabled:opacity-50">
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
        <span class="animate-pulse text-lg tracking-widest">少女祈祷中...</span>
      </div>

      <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        
        <div v-for="item in items" :key="item.code" 
             class="bg-bus-card border border-bus-border rounded-lg overflow-hidden flex flex-col hover:border-bus-primary transition-colors relative shadow-sm"
             :class="{'opacity-50 grayscale': item.is_downloaded}">
          
          <div class="absolute top-2 right-2 z-10 bg-black/50 rounded p-1 backdrop-blur-md">
            <input type="checkbox" v-model="item.selected" @change="updateSelection" class="w-5 h-5 accent-bus-primary cursor-pointer">
          </div>

          <div v-if="item.is_downloaded" class="absolute top-2 left-2 z-10 bg-bus-green-bg text-bus-text-light text-xs px-2 py-1 rounded shadow">
            已推送记录
          </div>

          <div class="relative w-full aspect-video bg-[#1a1c1d] overflow-hidden cursor-pointer group flex-shrink-0" 
               @click="openViewer([item.meta?.cover, ...(item.meta?.samples || [])], 0)">
            <img v-if="item.meta?.cover" :src="item.meta.cover" loading="lazy" 
                 class="w-full h-full object-contain group-hover:opacity-90 transition-opacity" />
            
            <div v-else class="absolute inset-0 flex items-center justify-center text-bus-text-muted text-sm">
              {{ item.meta === null ? '正在连接深海...' : '暂无封面或被屏蔽' }}
            </div>
            
            <div class="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
               <span class="bg-black/60 text-white p-3 rounded-full backdrop-blur-sm">🔍</span>
            </div>
          </div>

          <div class="p-4 flex-grow flex flex-col">
            <div class="flex justify-between items-center text-sm mb-2 border-b border-bus-border pb-2">
              <span class="text-bus-primary font-bold text-lg" :class="{'text-purple-400': item.code.includes('FC2')}">{{ item.code }}</span>
            </div>
            
            <h3 class="text-sm text-bus-text-light line-clamp-3 mb-3 flex-grow" :title="item.title">
              {{ formatTitle(item.title, item.code) }}
            </h3>

            <div class="relative group/thumbs mt-auto" v-if="item.meta?.samples?.length > 0">
              <div class="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-bus-card to-transparent z-10 opacity-0 group-hover/thumbs:opacity-100 flex items-center justify-start pl-1 cursor-pointer transition-opacity"
                   @mouseenter="startScroll($event, -1)" @mouseleave="stopScroll">
                 <span class="text-white drop-shadow-md text-xl">&lt;</span>
              </div>
              
              <div class="thumb-container flex gap-2 overflow-x-auto hide-scrollbar pb-1">
                <img v-for="(img, idx) in item.meta.samples" :key="idx" :src="img" 
                     @click.stop="openViewer([item.meta.cover, ...item.meta.samples], idx + 1)"
                     class="h-20 w-auto rounded object-cover cursor-pointer hover:opacity-80 transition-opacity shrink-0 border border-transparent hover:border-bus-primary" />
              </div>

              <div class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-bus-card to-transparent z-10 opacity-0 group-hover/thumbs:opacity-100 flex items-center justify-end pr-1 cursor-pointer transition-opacity"
                   @mouseenter="startScroll($event, 1)" @mouseleave="stopScroll">
                 <span class="text-white drop-shadow-md text-xl">&gt;</span>
              </div>
            </div>

            <div class="flex justify-end items-center mt-4 pt-3 border-t border-bus-border">
              <div class="flex gap-3 text-bus-text-muted text-xs flex-wrap">
                <a :href="item.code.includes('FC2') ? `https://adult.contents.fc2.com/article/${item.code.split('-')[2]}/` : `https://www.javbus.com/search/${item.code}`" target="_blank" class="hover:text-bus-primary transition-colors">官网</a>
                <a :href="`https://www.javbus.com/search/${item.code}`" target="_blank" class="hover:text-bus-primary transition-colors">JavBus</a>
                <a :href="`https://www.avbase.net/works?q=${item.code}`" target="_blank" class="hover:text-bus-primary transition-colors">Avbase</a>
                <a :href="`https://sukebei.nyaa.si/?f=0&c=0_0&q=${item.code}`" target="_blank" class="hover:text-bus-primary transition-colors">Nyaa</a>
              </div>
            </div>
          </div>
        </div>

      </div>

      <div v-if="!loading && items.length > 0 && totalPages > 1" class="flex justify-center items-center mt-12 mb-8">
        
        <button @click="fetchRss(currentPage - 1)" :disabled="currentPage <= 1" class="px-3 py-1.5 bg-bus-card border border-bus-border rounded disabled:opacity-50 hover:bg-bus-card-hover mx-1">
          &lt;
        </button>
        
        <div class="flex gap-1 mx-2">
          <button v-for="p in visiblePages" :key="p" @click="fetchRss(p)" 
                  class="w-8 h-8 rounded border border-bus-border flex items-center justify-center transition-colors text-sm"
                  :class="currentPage === p ? 'bg-bus-primary text-white border-bus-primary' : 'bg-bus-card hover:bg-bus-card-hover'">
            {{ p }}
          </button>
        </div>

        <button @click="fetchRss(currentPage + 1)" :disabled="currentPage >= totalPages" class="px-3 py-1.5 bg-bus-card border border-bus-border rounded disabled:opacity-50 hover:bg-bus-card-hover mx-1">
          &gt;
        </button>

      </div>
    </main>

    <div v-if="showSettings" class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[100]">
      <div class="bg-bus-card border border-bus-border rounded-xl w-[500px] max-w-[90%] shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-bus-border bg-bus-bg">
          <h2 class="text-xl text-bus-text-light font-bold">系统配置中心</h2>
        </div>
        <div class="p-6 space-y-5">
          <div>
            <label class="block text-sm text-bus-text-muted mb-2">Nyaa RSS 订阅源</label>
            <input v-model="settings.rss_url" type="text" class="w-full bg-bus-bg border border-bus-border p-2.5 rounded text-sm text-bus-text-light focus:outline-none focus:border-bus-primary transition-colors">
          </div>
          
          <div>
            <label class="block text-sm text-bus-text-muted mb-2">不刮削的番号前缀 (逗号分隔)</label>
            <input v-model="settings.block_prefixes" type="text" placeholder="如: XB-,MD-,JV-" class="w-full bg-bus-bg border border-bus-border p-2.5 rounded text-sm text-bus-text-light focus:outline-none focus:border-bus-primary transition-colors">
            <p class="text-[11px] text-gray-500 mt-1">命中这些前缀的番号将直接跳过网络刮削，提高加载速度。</p>
          </div>

          <hr class="border-bus-border">
          <div class="space-y-3">
            <label class="block text-sm text-bus-text-muted mb-1">qBittorrent 连接信息</label>
            <input v-model="settings.qb_host" type="text" placeholder="主机地址 (如: http://192.168.0.2:8080)" class="w-full bg-bus-bg border border-bus-border p-2.5 rounded text-sm text-bus-text-light focus:outline-none focus:border-bus-primary transition-colors">
            <div class="flex gap-3">
              <input v-model="settings.qb_user" type="text" placeholder="用户名" class="w-full bg-bus-bg border border-bus-border p-2.5 rounded text-sm text-bus-text-light focus:outline-none focus:border-bus-primary transition-colors">
              <input v-model="settings.qb_pass" type="password" placeholder="密码" class="w-full bg-bus-bg border border-bus-border p-2.5 rounded text-sm text-bus-text-light focus:outline-none focus:border-bus-primary transition-colors">
            </div>
          </div>
          <div v-if="testMsg" :class="testSuccess ? 'text-bus-green' : 'text-bus-danger'" class="text-xs bg-bus-bg p-2 rounded">
            {{ testMsg }}
          </div>
        </div>
        <div class="p-4 border-t border-bus-border bg-bus-bg flex justify-between items-center">
          <button @click="testConnection" :disabled="testing" class="text-sm text-bus-primary hover:underline">
            {{ testing ? '测试中...' : '⚡ 测试 qB 连接' }}
          </button>
          <div class="flex gap-3">
            <button @click="showSettings = false" class="px-4 py-2 text-sm text-bus-text-muted hover:text-bus-text-light">取消</button>
            <button @click="saveSettings" class="px-5 py-2 text-sm bg-bus-primary text-white rounded hover:bg-blue-500 transition-colors">保存配置</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="viewer.show" class="fixed inset-0 z-[200] bg-black/95 flex flex-col items-center justify-center select-none" @click="viewer.show = false">
      <div class="absolute top-4 right-6 text-white text-4xl cursor-pointer hover:text-bus-primary transition-colors">&times;</div>
      <div class="absolute top-4 left-6 text-bus-text-muted">{{ viewer.index + 1 }} / {{ viewer.images.length }}</div>
      
      <button @click.stop="prevImg" class="absolute left-4 top-1/2 -translate-y-1/2 p-6 text-white text-5xl hover:text-bus-primary transition-colors disabled:opacity-20" :disabled="viewer.index === 0">&#10094;</button>
      
      <img :src="viewer.images[viewer.index]" class="max-h-[90vh] max-w-[90vw] object-contain shadow-2xl rounded" @click.stop />
      
      <button @click.stop="nextImg" class="absolute right-4 top-1/2 -translate-y-1/2 p-6 text-white text-5xl hover:text-bus-primary transition-colors disabled:opacity-20" :disabled="viewer.index === viewer.images.length - 1">&#10095;</button>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'

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

const settings = ref({ qb_host: '', qb_user: '', qb_pass: '', rss_url: '', block_prefixes: '' })

// 需求3: 清理标题工具函数
const formatTitle = (title, code) => {
  if (!title) return ''
  // 去除开头的 ++ [FHD] 等修饰符
  let res = title.replace(/^[+\s]+/, '').replace(/^\[.*?\]\s*/, '')
  // 去除标题中包含的番号本身
  if (code) {
     const reg = new RegExp(`^${code}\\s*`, 'i')
     res = res.replace(reg, '')
  }
  return res.trim() || title
}

// 生成当前可视的页码列表 (例如展示当前页及前后2页)
const visiblePages = computed(() => {
  const pages = []
  const start = Math.max(1, currentPage.value - 2)
  const end = Math.min(totalPages.value, currentPage.value + 2)
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }
  return pages
})

onMounted(() => {
  document.title = 'SukebeiNexus'
  fetchRss(1)
})

// 核心：请求并异步刮削
const fetchRss = async (page) => {
  if (page < 1) return
  loading.value = true
  currentPage.value = page
  items.value = []
  window.scrollTo({ top: 0, behavior: 'smooth' })
  try {
    const res = await fetch(`${API_BASE}/api/rss?page=${page}`)
    const json = await res.json()
    totalPages.value = json.total_pages || 1
    items.value = json.data.map(item => ({ ...item, selected: false, meta: null }))
    // 并发触发图片刮削
    items.value.forEach(fetchMetadata)
  } catch (e) {
    console.error('RSS获取失败')
  } finally {
    loading.value = false
  }
}

const fetchMetadata = async (item) => {
  try {
    const res = await fetch(`${API_BASE}/api/metadata/${item.code}`)
    const data = await res.json()
    // 自动补全本地缓存图片的绝对路径
    if (data.cover && data.cover.startsWith('/')) {
        data.cover = API_BASE + data.cover
    }
    if (data.samples) {
        data.samples = data.samples.map(s => s.startsWith('/') ? API_BASE + s : s)
    }
    item.meta = data
  } catch (e) {
    item.meta = { cover: '', samples: [] }
  }
}

// 图片查看器逻辑
const viewer = ref({ show: false, images: [], index: 0 })

const openViewer = (imagesList, startIndex) => {
  const validImages = imagesList.filter(url => url && url.trim() !== '')
  if (validImages.length === 0) return
  viewer.value = { show: true, images: validImages, index: startIndex }
}

const prevImg = () => { if (viewer.value.index > 0) viewer.value.index-- }
const nextImg = () => { if (viewer.value.index < viewer.value.images.length - 1) viewer.value.index++ }

// 缩略图平滑滚动逻辑
let scrollTimer = null
const startScroll = (e, direction) => {
  const container = e.target.parentElement.querySelector('.thumb-container')
  if (!container) return
  stopScroll()
  scrollTimer = setInterval(() => {
    container.scrollLeft += direction * 8
  }, 16)
}
const stopScroll = () => {
  if (scrollTimer) clearInterval(scrollTimer)
}

// 设置与操作
const openSettings = async () => {
  testMsg.value = ''
  try {
    const res = await fetch(`${API_BASE}/api/settings`)
    settings.value = await res.json()
  } catch (e) {}
  showSettings.value = true
}

const saveSettings = async () => {
  await fetch(`${API_BASE}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings.value)
  })
  showSettings.value = false
  fetchRss(1) 
}

const testConnection = async () => {
  testing.value = true
  testMsg.value = '正在连接...'
  try {
    const res = await fetch(`${API_BASE}/api/qb/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })
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
    const res = await fetch(`${API_BASE}/api/qb/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: payload })
    })
    if (res.ok) {
      items.value.forEach(item => {
        if (item.selected) { item.is_downloaded = true; item.selected = false; }
      })
      updateSelection()
      selectAll.value = false
    } else {
      const data = await res.json()
      alert('推送失败: ' + data.detail)
    }
  } catch (e) {
    alert('推送请求异常')
  } finally {
    pushing.value = false
  }
}
</script>