import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import './creator.css'
import { dialog } from './dialog.js'

createApp(App).directive('dialog', dialog).mount('#app')
