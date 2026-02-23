<!-- 卡片组件 -->

<template>
  <div ref="cardRef" class="bg-bus-card border border-bus-border rounded-lg overflow-hidden flex flex-col hover:border-bus-primary transition-colors relative shadow-sm" :class="{'opacity-50 grayscale': item.is_downloaded}">
    
    <div class="absolute top-2 right-2 z-10 bg-black/50 rounded p-1 backdrop-blur-md">
      <input type="checkbox" v-model="item.selected" @change="$emit('update')" class="w-5 h-5 accent-bus-primary cursor-pointer">
    </div>

    <div v-if="item.is_downloaded" class="absolute top-2 left-2 z-10 bg-bus-green-bg text-bus-text-light text-xs px-2 py-1 rounded shadow">
      已推送记录
    </div>

    <div class="relative w-full aspect-video bg-[#1a1c1d] overflow-hidden cursor-pointer group flex-shrink-0" 
         @click="$emit('open-viewer', [item.meta?.cover, ...(item.meta?.samples || [])], 0)">
      
      <img v-if="showCover && item.meta?.cover" :src="item.meta.cover" @load="onCoverLoad"
           class="w-full h-full object-contain group-hover:opacity-90 transition-opacity" />
           
      <div v-else class="absolute inset-0 flex items-center justify-center text-bus-text-muted text-sm">
        {{ !item.meta?.cover ? (item.meta === null ? '后台排队刮削中...' : '暂无封面') : '图片加载中...' }}
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
        {{ formattedTitle }}
      </h3>

      <div class="relative group/thumbs mt-auto" v-if="showSamples && item.meta?.samples?.length > 0">
        <div class="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-bus-card to-transparent z-10 opacity-0 group-hover/thumbs:opacity-100 flex items-center justify-start pl-1 cursor-pointer transition-opacity"
             @mouseenter="startScroll(-1)" @mouseleave="stopScroll">
           <span class="text-white drop-shadow-md text-xl">&lt;</span>
        </div>
        
        <div ref="scrollContainer" class="flex gap-2 overflow-x-auto hide-scrollbar pb-1">
          <img v-for="(img, idx) in item.meta.samples" :key="idx" :src="img" loading="lazy"
               @click.stop="$emit('open-viewer', [item.meta.cover, ...item.meta.samples], idx + 1)"
               class="h-20 w-auto rounded object-cover cursor-pointer hover:opacity-80 transition-opacity shrink-0 border border-transparent hover:border-bus-primary" />
        </div>

        <div class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-bus-card to-transparent z-10 opacity-0 group-hover/thumbs:opacity-100 flex items-center justify-end pr-1 cursor-pointer transition-opacity"
             @mouseenter="startScroll(1)" @mouseleave="stopScroll">
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
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps(['item'])
defineEmits(['update', 'open-viewer'])

const cardRef = ref(null)
const scrollContainer = ref(null)

// 渐进式加载状态机
const showCover = ref(false)
const showSamples = ref(false)

const formattedTitle = computed(() => {
  let title = props.item.title
  if (!title) return ''
  let res = title.replace(/^[+\s]+/, '').replace(/^\[.*?\]\s*/, '')
  if (props.item.code) {
     const reg = new RegExp(`^${props.item.code}\\s*`, 'i')
     res = res.replace(reg, '')
  }
  return res.trim() || title
})

// 需求2: 监听卡片是否进入可视区域
let observer = null
onMounted(() => {
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) {
      // 1. 卡片进入屏幕，优先加载封面
      showCover.value = true
      // 2. 如果因为某些原因（比如无封面）导致 onCoverLoad 不触发，设置个兜底定时器展示小图
      setTimeout(() => { showSamples.value = true }, 1500)
      observer.disconnect()
    }
  }, { rootMargin: '200px' }) // 提前200px开始加载
  
  if (cardRef.value) observer.observe(cardRef.value)
})

onUnmounted(() => {
  if (observer) observer.disconnect()
  stopScroll()
})

// 当封面真正加载完成时，立刻放行加载详细图
const onCoverLoad = () => {
  showSamples.value = true
}

// 悬浮滚动逻辑
let scrollTimer = null
const startScroll = (direction) => {
  if (!scrollContainer.value) return
  stopScroll()
  scrollTimer = setInterval(() => {
    scrollContainer.value.scrollLeft += direction * 8
  }, 16)
}
const stopScroll = () => {
  if (scrollTimer) clearInterval(scrollTimer)
}
</script>