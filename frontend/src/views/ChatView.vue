<script setup lang="ts">
import HistorySidebar from '@/components/layout/HistorySidebar.vue'
import ChatWindow from '@/components/chat/ChatWindow.vue'
import ParametersPanel from '@/components/parameters/ParametersPanel.vue'

defineOptions({ name: 'ChatView' })
</script>

<template>
  <!-- 外层 flex-col：承接 App keep-alive 的纵向布局；内层 flex-row：历史 | 对话 | 参数 三栏 -->
  <div class="flex flex-1 flex-col min-w-0 min-h-0 overflow-hidden">
    <div class="flex flex-1 flex-row min-w-0 min-h-0 overflow-hidden">
      <HistorySidebar />
      <div class="flex flex-1 flex-col min-w-0 min-h-0 overflow-hidden">
        <ChatWindow />
      </div>
      <ParametersPanel />
    </div>
  </div>
</template>