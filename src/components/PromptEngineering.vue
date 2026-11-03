<script setup>
import { ref } from 'vue'
import { store } from '../store.js'

const activeCategory = ref('全局助理')
const categories = [
  '全局助理',
  '世界观构筑',
  '人物工坊',
  '故事结构',
  '情节引擎',
  '写作辅助'
]

// Sub-tabs state
const activeSubWorldview = ref('worldview_auto_construct')
const activeSubCharacter = ref('character_generate')
const activeSubGlobal = ref('long_outline_generate')
const activeSubEditor = ref('editor_continue')

// 恢复默认提示词
const resetPrompt = (key) => {
  if (confirm("确定要恢复该提示词到出厂默认值吗？")) {
    const defaultPrompts = {
      long_outline_generate: `你是一个顶级网文主笔编辑(EditorAgent)。你要为一个长篇小说规划细纲。
目标：生成第 {start} 章到第 {end} 章的大纲（共 {count} 章）。
严格输出 JSON 数组，格式：
[ { "chapterNum": "第X章", "title": "章名", "summary": "本章剧情详细要点(50-100字)" } ]
要求：
1. 紧密衔接上文："{last_summary}"
2. 参考核心角色和长线剧情节点。
3. 严格遵循 JSON 格式，不要返回 markdown 代码块，纯 JSON 数组。`,
      worldview_auto_construct: `你是一个顶级网文世界观架构师。你需要为一个叫做《{title}》的{tags}小说构筑一个大类。\n所在面板：{tab}。大类名称：“{category}”。\n请生成2到3个具体词条设定，要求网文味浓厚，有设定感和悬念。\n输出格式严格为 JSON 数组：\n[{"name": "词条名", "desc": "详细描述..."}]\n不要输出 markdown，纯 json 文本。`,
      worldview_expand_item: `你是一个顶级网文世界观架构师。目前正在构建小说《{title}》。\n在大类“{category}”中，有一个核心设定叫：“{name}”。\n其描述为：“{desc}”。\n请基于该设定，向下深挖出 1-2 个具体的“衍生子设定”（例如：如果父设定是某个组织，子设定可以是它的隐秘机构、核心功法或代表人物）。\n输出格式严格为 JSON 数组：\n[{"name": "子设定名称", "desc": "子设定详细描述..."}]\n不要输出 markdown，纯 json 文本。`,
      worldview_polish_item: `你是一个顶级网文世界观架构师。目前正在构建小说《{title}》（{tags}）的设定。\n当前大类：“{category}”。\n词条名称：“{name}”。\n原描述：“{desc}”。\n请根据以上信息，为该词条生成一段极具网文张力、悬念感和脑洞的详细设定描述（大约50-100字左右）。\n要求：直接输出描述内容，不要输出任何其他的解释文字、标题或 Markdown 标记。`,
      plot_generate_twist: `你是一位深谙好莱坞编剧理论与爆款网文节奏的情节架构师。\n小说《{title}》（{tags}）。\n请根据现有剧情进展，生成一个出人意料且符合逻辑的【剧情转折】。\n输出严格为 JSON 格式：\n{"type": "起|承|转|合|反转|高潮", "title": "节点标题", "tension": 80, "desc": "剧情描述（100字内）"}`,
      character_generate: `你是一位顶级网文角色设定师。请为小说《{title}》（{tags}）随机生成一个充满戏剧冲突和吸引力的新角色。\n要求：包含身份背景、核心性格、甚至某种秘密。\n输出严格为 JSON 格式：\n{"name": "姓名", "faction": "阵营/身份", "tags": ["标签1", "标签2", "标签3"], "description": "角色小传（100字左右）"}`,
      character_expand: `你是一位顶级网文角色设定师。目前小说《{title}》中有一名角色“{name}”（阵营：{faction}）。\n当前设定：“{description}”。\n请针对该角色进行脑洞扩写，增加更多不为人知的秘密、深层动机或伏笔。\n直接输出扩写后的角色小传，不要返回标题和 markdown。`,
      editor_continue: `你是一位深谙“现代言情、黑道大佬与甜宠拉扯”题材的白金级网文大神。请根据上下文，紧接着续写后续剧情。
【核心写作军规】
1. 强化危险与禁忌的性张力：这是“小白兔误入狼窝/被闺蜜的黑道小叔盯上”的题材。男女主同框时，必须刻画出男主作为上位者的绝对压迫感、危险气息，以及女主心底的局促、背德感与生理性紧张。
2. 细节烘托氛围 (Show, Don't Tell)：男主的情绪不要明写，通过他指尖弹烟灰的动作、解开衬衫顶扣的漫不经心、或是锁定猎物般的深邃眼神来展现。女主的紧张要通过呼吸错乱、视线闪躲、指节发白来体现。
3. 极限推拉的对话交锋：对话必须充满暧昧的试探、步步紧逼的压迫，或是看似长辈关心实则充满占有欲的潜台词。绝不要说废话。
4. 续写长度约200-500字，请务必“拖慢节奏”，把这种让人脸红心跳的危险氛围拉满。绝对不要轻易得出最终结论，绝对不要擅自写出“本章完”！
5. 直接输出纯续写内容，不要返回任何多余解释。`,
      editor_conclude: `你是一位顶级的现言小说作家，精通“暧昧拉扯”与“断章”技巧。请为当前章节写一个极其勾人的收尾。
【核心写作军规】
1. 定格危险与暧昧：收尾时不要空洞总结，请用一个极具侵略性的动作（如男主突然拉近距离、阴影笼罩女主）、一句意味深长的低语、或一个让女主心跳骤停的突发事件来定格画面。
2. 强化禁忌悬念：悬念要卡在两人关系即将越界、或者某种危险秘密即将曝光的最高潮瞬间。
3. 绝对半截断章：不要去解答当前的悬念！如果男主刚刚逼近，或者女主刚刚退无可退，请直接在此处“强行切断”，让读者抓心挠肝！
4. 字数控制在50-200字以内。
5. 直接输出纯正文收尾，不要多余废话。在输出内容的最后一行，必须单独输出一行“【本章完】”。`,
      editor_polish: `你是一位资深网文编辑。请对用户提供的文本进行润色。\n要求：\n1. 修复语病，提升文笔流畅度。\n2. 增强动作描写、情绪渲染和氛围感。\n3. 保持原有剧情走向不变。\n4. 直接输出润色后的文本，不要多余解释。`,
      editor_expand: `你是一位擅长环境描写和心理刻画的网文作家。请对用户提供的段落进行扩写。\n要求：\n1. 增加环境氛围烘托、人物心理活动、细致的动作表情描写。\n2. 使画面更加丰满立体，字数增加 1.5 到 2 倍左右。\n3. 严格遵循原意，直接输出扩写后文本。`,
      editor_shorten: `你是一位行文干练的网文作者。请对用户提供的段落进行缩写（精简）。\n要求：\n1. 剔除啰嗦、冗余的修饰，加快叙事节奏。\n2. 提炼核心剧情、关键对话和核心动作。\n3. 字数大幅度精简，直接输出精简后文本。`,
      outline_expand: `你是一位金牌网文大纲拆解师。当前小说《{title}》。\n现在有一卷大纲，标题为“{volumeTitle}”，简介为“{volumeDesc}”。\n请将其裂变为 3 到 5 个具体的【章节细纲】。每一章需要有标题和剧情要点（字数控制在50字左右）。\n输出严格为 JSON 数组：\n[{"chapterNum": "章节编号(如: 第1章)", "title": "章节标题", "summary": "本章剧情要点"}]`,
      chat_assistant: `你是一位陪伴式 AI 写作教练。你非常了解网文创作的套路和技巧，语言幽默风趣。你现在正在辅助作者构思小说《{title}》（{tags}）。请根据作者的问题，给出有启发性的建议和点子。`,
      book_generate: `你是一位畅销网文策划编辑。请帮作者构思一本极具潜力的爆款新书。\n题材：{genre}\n目标读者：{audience}\n视角：{perspective}\n篇幅：{length}\n核心构思：{prompt}\n严格输出 JSON 格式：\n{"title": "书名", "tags": ["标签1", "标签2"], "wordCount": "0万", "status": "构思中", "desc": "一段极具吸引力的新书简介（约50字）"}`
    }
    store.prompts[key] = defaultPrompts[key]
  }
}
</script>

<template>
  <div class="prompt-engineering-container">
    <div class="header-actions">
      <div>
        <!-- Removing redundant page-title h2 since it's now in the topbar -->
        <p class="page-desc">调整各项 AI 创作功能的提示词。占位符会自动填入对应的作品资料。</p>
      </div>
    </div>

    <div class="settings-content prompt-layout">
      <!-- 左侧分类菜单 -->
      <div class="prompt-sidebar">
        <ul class="category-menu">
          <li 
            v-for="cat in categories" 
            :key="cat"
            :class="{ active: activeCategory === cat }"
          >
            <button class="prompt-category" :aria-pressed="activeCategory === cat" @click="activeCategory = cat">{{ cat }}</button>
          </li>
        </ul>
      </div>

      <!-- 右侧提示词内容区 -->
      <div class="prompt-main">
        
        <div class="ai-section" v-show="activeCategory === '全局助理'">
          <h4 class="sub-title">全局助理</h4>
          <p class="sub-desc">调整创作助手的回复方式，以及首页的新书生成提示词。</p>
          
          <div class="sub-tabs">
            <button class="sub-tab-btn" :class="{ active: activeSubGlobal === 'long_outline_generate' }" @click="activeSubGlobal = 'long_outline_generate'">分批生成大纲</button>
            <button class="sub-tab-btn" :class="{ active: activeSubGlobal === 'book_generate' }" @click="activeSubGlobal = 'book_generate'">一键构思新书</button>
            <button class="sub-tab-btn" :class="{ active: activeSubGlobal === 'chat_assistant' }" @click="activeSubGlobal = 'chat_assistant'">陪伴式对话助理</button>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubGlobal === 'long_outline_generate'">
            <div class="prompt-header">
              <h5 class="prompt-title">分批生成大纲</h5>
              <button class="text-btn" @click="resetPrompt('long_outline_generate')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{start}</code>起始章, <code>{end}</code>结束章, <code>{count}</code>本次推演章数, <code>{last_summary}</code>上一章摘要</p>
            <textarea class="prompt-textarea" v-model="store.prompts.long_outline_generate" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubGlobal === 'book_generate'">
            <div class="prompt-header">
              <h5 class="prompt-title">一键构思新书</h5>
              <button class="text-btn" @click="resetPrompt('book_generate')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{genre}</code>题材, <code>{audience}</code>受众, <code>{perspective}</code>视角, <code>{length}</code>篇幅, <code>{prompt}</code>用户输入</p>
            <textarea class="prompt-textarea" v-model="store.prompts.book_generate" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubGlobal === 'chat_assistant'">
            <div class="prompt-header">
              <h5 class="prompt-title">陪伴式对话助理</h5>
              <button class="text-btn" @click="resetPrompt('chat_assistant')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{tags}</code>标签</p>
            <textarea class="prompt-textarea" v-model="store.prompts.chat_assistant" rows="12"></textarea>
          </div>
        </div>

        <div class="ai-section" v-show="activeCategory === '世界观构筑'">
          <h4 class="sub-title">世界观构筑</h4>
          <p class="sub-desc">自定义世界观生成器所使用的系统提示词，利用占位符深度结合当前上下文。</p>
          
          <div class="sub-tabs">
            <button class="sub-tab-btn" :class="{ active: activeSubWorldview === 'worldview_auto_construct' }" @click="activeSubWorldview = 'worldview_auto_construct'">设定大类生成</button>
            <button class="sub-tab-btn" :class="{ active: activeSubWorldview === 'worldview_expand_item' }" @click="activeSubWorldview = 'worldview_expand_item'">词条深挖</button>
            <button class="sub-tab-btn" :class="{ active: activeSubWorldview === 'worldview_polish_item' }" @click="activeSubWorldview = 'worldview_polish_item'">脑洞扩写</button>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubWorldview === 'worldview_auto_construct'">
            <div class="prompt-header">
              <h5 class="prompt-title">设定大类一键生成</h5>
              <button class="text-btn" @click="resetPrompt('worldview_auto_construct')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{tags}</code>标签, <code>{tab}</code>面板名称, <code>{category}</code>类目名称</p>
            <textarea class="prompt-textarea" v-model="store.prompts.worldview_auto_construct" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubWorldview === 'worldview_expand_item'">
            <div class="prompt-header">
              <h5 class="prompt-title">词条衍生深挖</h5>
              <button class="text-btn" @click="resetPrompt('worldview_expand_item')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{category}</code>类目名称, <code>{name}</code>词条名称, <code>{desc}</code>当前描述</p>
            <textarea class="prompt-textarea" v-model="store.prompts.worldview_expand_item" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubWorldview === 'worldview_polish_item'">
            <div class="prompt-header">
              <h5 class="prompt-title">AI 脑洞扩写</h5>
              <button class="text-btn" @click="resetPrompt('worldview_polish_item')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{tags}</code>标签, <code>{category}</code>类目名称, <code>{name}</code>词条名称, <code>{desc}</code>原描述</p>
            <textarea class="prompt-textarea" v-model="store.prompts.worldview_polish_item" rows="12"></textarea>
          </div>
        </div>

        <div class="ai-section" v-show="activeCategory === '人物工坊'">
          <h4 class="sub-title">人物工坊</h4>
          <p class="sub-desc">自定义人物角色的随机生成和细节扩写指令。</p>
          
          <div class="sub-tabs">
            <button class="sub-tab-btn" :class="{ active: activeSubCharacter === 'character_generate' }" @click="activeSubCharacter = 'character_generate'">随机角色生成</button>
            <button class="sub-tab-btn" :class="{ active: activeSubCharacter === 'character_expand' }" @click="activeSubCharacter = 'character_expand'">角色小传扩写</button>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubCharacter === 'character_generate'">
            <div class="prompt-header">
              <h5 class="prompt-title">随机角色生成</h5>
              <button class="text-btn" @click="resetPrompt('character_generate')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{tags}</code>标签</p>
            <textarea class="prompt-textarea" v-model="store.prompts.character_generate" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubCharacter === 'character_expand'">
            <div class="prompt-header">
              <h5 class="prompt-title">角色小传扩写</h5>
              <button class="text-btn" @click="resetPrompt('character_expand')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{name}</code>角色名, <code>{faction}</code>身份阵营, <code>{description}</code>当前小传</p>
            <textarea class="prompt-textarea" v-model="store.prompts.character_expand" rows="12"></textarea>
          </div>
        </div>

        <div class="ai-section" v-show="activeCategory === '故事结构'">
          <h4 class="sub-title">故事结构</h4>
          <p class="sub-desc">自定义将卷大纲细化为章节小纲的系统指令。</p>
          <div class="setting-item prompt-item">
            <div class="prompt-header">
              <h5 class="prompt-title">章节细纲裂变</h5>
              <button class="text-btn" @click="resetPrompt('outline_expand')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{volumeTitle}</code>卷名, <code>{volumeDesc}</code>卷简介</p>
            <textarea class="prompt-textarea" v-model="store.prompts.outline_expand" rows="12"></textarea>
          </div>
        </div>

        <div class="ai-section" v-show="activeCategory === '情节引擎'">
          <h4 class="sub-title">情节引擎</h4>
          <p class="sub-desc">自定义情节生成器所使用的系统提示词，用于推演意料之外的剧情转折。</p>
          <div class="setting-item prompt-item">
            <div class="prompt-header">
              <h5 class="prompt-title">剧情转折生成</h5>
              <button class="text-btn" @click="resetPrompt('plot_generate_twist')">恢复默认</button>
            </div>
            <p class="prompt-vars">可用变量：<code>{title}</code>书名, <code>{tags}</code>标签</p>
            <textarea class="prompt-textarea" v-model="store.prompts.plot_generate_twist" rows="12"></textarea>
          </div>
        </div>

        <div class="ai-section" v-show="activeCategory === '写作辅助'">
          <h4 class="sub-title">写作辅助</h4>
          <p class="sub-desc">自定义写作编辑器内嵌的各项 AI 辅助指令。</p>
          
          <div class="sub-tabs">
            <button class="sub-tab-btn" :class="{active: activeSubEditor === 'editor_continue'}" @click="activeSubEditor = 'editor_continue'">自动续写</button>
            <button class="sub-tab-btn" :class="{active: activeSubEditor === 'editor_conclude'}" @click="activeSubEditor = 'editor_conclude'">悬念结章</button>
            <button class="sub-tab-btn" :class="{active: activeSubEditor === 'editor_polish'}" @click="activeSubEditor = 'editor_polish'">智能润色</button>
            <button class="sub-tab-btn" :class="{active: activeSubEditor === 'editor_expand'}" @click="activeSubEditor = 'editor_expand'">段落扩写</button>
            <button class="sub-tab-btn" :class="{active: activeSubEditor === 'editor_shorten'}" @click="activeSubEditor = 'editor_shorten'">精简缩写</button>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubEditor === 'editor_continue'">
            <div class="prompt-header">
              <h5 class="prompt-title">剧情自动续写</h5>
              <button class="text-btn" @click="resetPrompt('editor_continue')">恢复默认</button>
            </div>
            <p class="prompt-vars">上下文直接通过代码中的 <code>messages</code> 历史传入，此处为系统人格 (System Persona)。</p>
            <textarea class="prompt-textarea" v-model="store.prompts.editor_continue" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubEditor === 'editor_conclude'">
            <div class="prompt-header">
              <h5 class="prompt-title">悬念断章收尾</h5>
              <button class="text-btn" @click="resetPrompt('editor_conclude')">恢复默认</button>
            </div>
            <textarea class="prompt-textarea" v-model="store.prompts.editor_conclude" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubEditor === 'editor_polish'">
            <div class="prompt-header">
              <h5 class="prompt-title">智能润色</h5>
              <button class="text-btn" @click="resetPrompt('editor_polish')">恢复默认</button>
            </div>
            <p class="prompt-vars">所选文本直接通过用户消息传入，此处为润色专用的系统指令。</p>
            <textarea class="prompt-textarea" v-model="store.prompts.editor_polish" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubEditor === 'editor_expand'">
            <div class="prompt-header">
              <h5 class="prompt-title">段落扩写</h5>
              <button class="text-btn" @click="resetPrompt('editor_expand')">恢复默认</button>
            </div>
            <p class="prompt-vars">所选文本直接通过用户消息传入，此处为扩写专用的系统指令。</p>
            <textarea class="prompt-textarea" v-model="store.prompts.editor_expand" rows="12"></textarea>
          </div>

          <div class="setting-item prompt-item" v-show="activeSubEditor === 'editor_shorten'">
            <div class="prompt-header">
              <h5 class="prompt-title">精简缩写</h5>
              <button class="text-btn" @click="resetPrompt('editor_shorten')">恢复默认</button>
            </div>
            <p class="prompt-vars">所选文本直接通过用户消息传入，此处为缩写专用的系统指令。</p>
            <textarea class="prompt-textarea" v-model="store.prompts.editor_shorten" rows="12"></textarea>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
.prompt-engineering-container {
  padding: 32px 40px;
  max-width: 100%;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 32px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.settings-content {
  background: var(--panel-bg);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}

.prompt-layout {
  display: flex;
  min-height: 600px;
}

.prompt-sidebar {
  width: 200px;
  background: var(--surface-subtle);
  border-right: 1px solid var(--border-color);
  padding: 24px 0;
  flex-shrink: 0;
}

.category-menu {
  list-style: none;
  padding: 0;
  margin: 0;
}

.category-menu li {
  padding: 12px 24px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.category-menu li:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.category-menu li.active {
  background: var(--panel-bg);
  color: var(--primary-color);
  font-weight: 600;
  border-left-color: var(--primary-color);
}

.prompt-main {
  flex: 1;
  padding: 32px 48px;
  overflow-y: auto;
}

.ai-section {
  margin-bottom: 24px;
}

.sub-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.sub-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 24px 0;
}

/* Sub-tabs styles */
.sub-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 8px;
}

.sub-tab-btn {
  padding: 8px 16px;
  font-size: 14px;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
  font-weight: 500;
}

.sub-tab-btn:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.sub-tab-btn.active {
  background: var(--hover-bg);
  color: var(--primary-color);
  font-weight: 600;
}

.setting-item {
  display: block;
}

.prompt-item {
  background: var(--surface-subtle);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 24px;
}

.prompt-header {
  flex-wrap: wrap;
  gap: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.prompt-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.prompt-vars {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
}

.prompt-vars code {
  background: var(--border-color);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  color: var(--text-secondary);
}

.prompt-textarea {
  width: 100%;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  outline: none;
  box-sizing: border-box;
  resize: vertical;
  background: var(--panel-bg);
  transition: border-color 0.2s;
}

.prompt-textarea:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.text-btn {
  white-space: nowrap;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}

.text-btn:hover {
  color: var(--primary-color);
  background: var(--hover-bg);
}
@media(max-width:550px) { .prompt-item{padding:12px} .prompt-textarea{padding:12px;font-size:13px} .prompt-title{font-size:14px} }
</style>
