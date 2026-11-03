# AI 创作平台 · AI Creation Studio

面向小说、故事与 AI 漫剧创作的单用户、自托管工作台，基于 Vue 3 + FastAPI。支持作品管理、章节编辑、AI 续写与润色、人物和世界观、大纲生成及断点续传、漫剧分镜、素材图片持久化、作品内全文检索。

当前版本：0.2.0。项目代码采用 [MIT 许可证](LICENSE)，第三方声明见 [third_party/](third_party/README.md)。未使用的模板插图和模板组件已从发布范围排除；新加入的图片等资源需确认来源和授权，项目代码许可不替代第三方资源授权。

## 安装与启动

需要 Node.js 24+、Python 3.11+（本次本机验证为 Python 3.14）。建议使用独立虚拟环境。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
npm ci
.venv\Scripts\python backend\launch.py
```

Windows 也可双击 `start_project.bat`。首次运行会创建虚拟环境并安装依赖。已有虚拟环境升级后，请重新执行上面的 `pip install -r` 和 `npm ci`。

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci
.venv/bin/python backend/launch.py
```

打开 [本机工作台](http://127.0.0.1:5273)。启动器仅监听本机，遇到端口占用会退出，按 Ctrl+C 只停止它本次启动的进程。

分开启动时，在根目录运行：

```bash
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8100
npm run dev
```

## 平台账号登录

设置中新增 ChatGPT 官方 OAuth 与 Muse 网页会话登录，可选择模型并绑定 Agent。Muse 浏览器适配已直接集成，无需另行部署 muse2api；它不是 Muse 官方 OAuth。当前两种交互式账号登录都面向本机运行。

更新依赖并重启后，打开“策略与设置 → AI 引擎策略 → 平台账号登录”。详细流程、权限范围与验证限制见 [ACCOUNT_INTEGRATION.md](ACCOUNT_INTEGRATION.md)。原有 API Key 方式继续可用。

Muse 登录后可读取设置页的周用量、重置说明和额外剩余额度。数值按 Muse 实际显示，不推算未知的周 Token 总量；读取失败时保留上次结果并标明错误。

## 模型配置

在“策略与设置 → AI 引擎策略”配置兼容 Chat Completions 的服务地址、模型名和自己的 API Key，并分配给各 Agent。服务地址应为基础路径，例如 `https://api.openai.com/v1`，应用自动追加 `/chat/completions`。

所有模型请求经过统一后端代理。后端默认只允许 `api.openai.com`，并兼容本机已有 `.env` / 进程环境中 `*_BASE_URL` 指定的服务主机。新增供应商时由部署者配置 `NOVEL_PROVIDER_HOSTS`，不能通过前端请求扩大白名单。

应用源码不包含真实 API Key。正常使用时在工作台中配置自己的 Key；现有浏览器配置存储方式保持不变，不要在不信任的浏览器或公共设备中输入 Key。本机私有 `backend/.env` / `runtime.env` 不进入源码包。

## 运行参数与访问控制

可参考 `backend/runtime.env.example` 创建独立的 `backend/runtime.env`；不要覆盖已有 `.env`。进程环境变量优先，其次 runtime.env，再次 .env。

| 参数 | 用途 |
| --- | --- |
| `NOVEL_DATA_DIR` | 数据目录，默认固定为 backend 目录，与启动位置无关 |
| `NOVEL_ACCESS_TOKEN` | 后端访问令牌；远程部署必须设置随机长令牌 |
| `NOVEL_ALLOWED_HOSTS` | 接受的 Host 主机名，逗号分隔；本地默认 localhost、127.0.0.1、[::1] |
| `NOVEL_ALLOWED_ORIGINS` | 允许的前端来源，必须包含协议和端口 |
| `NOVEL_PROVIDER_HOSTS` | 允许的公网模型主机名，只允许 HTTPS 443；设置后替换默认列表 |
| `NOVEL_LOCAL_PROVIDER_HOSTS` | 显式允许访问的本地模型主机；默认为空 |
| `VITE_API_BASE_URL` | 前端构建时 API 基础地址，默认 `/api` |
| `NOVEL_API_PROXY` | Vite 开发/预览代理的后端地址，默认 `http://127.0.0.1:8100` |
| `NOVEL_FRONTEND_PORT` | 开发前端端口，默认 5273 |

本机模式自动为受信任的本机页面签发会话令牌。设置 `NOVEL_ACCESS_TOKEN` 后自动签发关闭，页面会提示输入后端访问令牌。它与模型供应商的 API Key 是两种不同凭据。

这是共享令牌的单用户应用，适合一个可信用户管理自己的作品，不提供多用户账户及作品归属隔离。公网部署应使用 HTTPS 反向代理，将 `/api` 转发到后端，设置访问令牌、允许的域名和页面来源，并限制直接访问后端端口。不要将 Vite 开发服务器作为生产服务器。

开发服务器仅允许读取前端入口、源码及依赖目录，禁止直接读取后端、数据库、环境配置和私人恢复文件。后端访问控制仍独立生效。

## 保存、恢复与备份

- 按作品分别排队保存，同一作品的写入串行执行。顶部显示待保存数量和实际失败信息，可点击“保存作品”。
- 未提交草稿保存在当前浏览器的 IndexedDB。重新打开页面后如有不同的草稿，可选择恢复草稿或保留后端版本。清除站点数据会清除这些草稿；数据目录备份不包含浏览器草稿。
- 尚未保存或本地草稿写入未完成时，关闭页面会触发浏览器提示。请等待保存完成后退出；断电等强制终止无法由页面保证最后一次按键落盘。
- 正文发生变化前，后端保留最近 20 个版本，可从顶部“历史版本”恢复。频繁写作时版本会滚动淘汰，不能替代独立备份。
- 润色、扩写和缩写仅在完整接收非空结果后替换原文；失败、取消时保留原文。
- 结构生成先展示预览，应用时保留现有正文、分卷和章节 ID；新大纲超出的章节追加，原有多余章节保留。
- 人物、世界观、剧情及漫剧任务绑定发起时的作品；切换作品或离开页面会取消等待。重新推演和续传检测请求期间的编辑，避免覆盖新内容。取消本地等待不保证供应商已停止计费。
- 素材图片实际保存到数据目录的 uploads 中。旧版仅有 blob URL 的图片需要重新上传。

数据目录包含 `ai_novel.db`、`memory.db` 和 `uploads/`。停掉前后端后整体复制到安全位置即可备份；恢复时同样先停止服务。已有 backend 数据库直接继续使用，根目录那个旧的同名数据库不会自动合并。旧版无作品归属的记忆记录保留在原表，新索引从保存的作品重建并按作品隔离。

建议同一作品只在一个页面中编辑；本版本不提供多人协作或跨页面版本冲突合并。

## 功能状态

编辑、模型代理、流式生成、作品保存、图片存储与作品内搜索已接通。中文检索支持作品内子串匹配。聊天记录按作品保存在当前浏览器 IndexedDB，刷新和切换页面后可继续；它不随服务器数据备份或跨设备同步。

创作分析使用当前作品的字数、章节及角色提及统计，不代表模型对文笔或情节质量的评判。漫剧工坊生成分镜文字和绘画提示词，尚不直接生成成片。版权检测、全网防盗、舆情监控尚未接入；“智能哨兵”只检查后端连接。聊天插入与替换会返回编辑器并写入对应章节；替换要求事先选择正文，原文发生变化时会取消。

“我的作品”可以在未配置模型时创建空白草稿。配置模型后，新建作品可生成设定和大纲；有正文的作品应使用故事结构预览功能保留正文。

## 测试与构建

```bash
npm test
python -m unittest discover -s backend/tests -v
npm run build
```

可选浏览器回归：

```bash
npx playwright install chromium
npm run test:browser
```

Windows 未安装 Playwright Chromium 时，浏览器测试会尝试使用系统 Edge；可通过 `NOVEL_BROWSER_CHANNEL` 指定 channel。浏览器测试使用独立临时目录、模拟模型服务和独立浏览器资料，不读取现有作品或真实浏览器配置。

GitHub Actions 配置模板位于 [ci/github-actions.yml](ci/github-actions.yml)，包含 Windows/Linux 与 Python 版本矩阵及浏览器回归。首次发布使用的 GitHub 凭据没有 `workflow` 权限，因此暂不自动运行。要启用，请使用有工作流写权限的凭据，将模板复制到 `.github/workflows/ci.yml`，移除对应忽略规则并提交。

不要直接运行根目录中的历史 `test_playwright.py` / `test_chained.py` 等脚本作为回归测试；它们依赖旧 UI、可能调用真实模型并操作本机作品。本次保留了这些文件，新的测试入口为上述命令。

## 发布源码

不要直接压缩整个工作目录。数据库、图片上传目录、私人正文、导出文件和运行配置已加入忽略规则；已有文件仍保留在本机。

```bash
npm run release:source
```

此命令只打包明确列出的应用源码、MIT LICENSE、隔离测试、第三方版权声明和文档，输出到 `release/`，不包含 `.env`、私人作品、旧测试脚本或 `src/recoveredData.js`。打包前会检测常见格式的源码内嵌凭据，命中即停止。

历史 `test_playwright.py` 中的真实 Key 已移除，改为读取环境变量（优先 `EDITOR_API_KEY`，其次 `OPENAI_API_KEY`），地址和模型也由环境提供。该脚本默认拒绝运行，需要明确设置 `NOVEL_RUN_LEGACY_TEST=1`；日常测试继续使用隔离的 `npm run test:browser`。移除源码字面值不能清除以前的 Git 历史，也不能撤销已泄漏的凭据；如旧版本曾公开，请在供应商处轮换相应 Key。

最新发布审查见 [FINAL_CODE_REVIEW.md](FINAL_CODE_REVIEW.md)，修复记录见 [UPGRADE_NOTES.md](UPGRADE_NOTES.md)，原始审查快照见 [OPEN_SOURCE_REVIEW.md](OPEN_SOURCE_REVIEW.md)。
