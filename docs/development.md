# 开发指南

## 环境准备

使用 Node.js 24+、Python 3.11+ 和独立虚拟环境，安装 [项目首页](../README.md#快速开始)中列出的依赖。前端依赖由 `package-lock.json` 固定，Python 依赖由 `backend/requirements.lock` 约束。

从仓库根目录分别启动服务：

```powershell
# 终端一：Windows
.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8100

# 终端二
npm run dev
```

macOS/Linux 将 Python 路径替换为 `.venv/bin/python`。日常使用也可通过 `backend/launch.py` 同时启动服务；启动器只管理本次启动的进程，端口被占用时退出并提示。

## 测试

前端行为回归与构建：

```bash
npm test
npm run build
```

后端测试使用临时数据库、模拟模型和本地签名身份，不访问现有作品或真实账号。

```powershell
# Windows
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

```bash
# macOS / Linux
.venv/bin/python -m unittest discover -s backend/tests -v
```

## 浏览器回归

首次使用安装浏览器：

```bash
npx playwright install chromium
```

Windows：

```powershell
$env:PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
npm run test:browser
```

macOS/Linux：

```bash
PYTHON="$(pwd)/.venv/bin/python" npm run test:browser
```

测试使用独立临时目录、端口、模拟模型服务及浏览器资料。Windows 没有 Playwright Chromium 时会尝试系统 Edge；可用 `NOVEL_BROWSER_CHANNEL` 指定 channel。测试产生的截图和日志存于本机 `logs/`，不进入源码包。

不要将根目录中的历史本地自动化纳入测试发现；它们可能依赖旧界面并操作本机作品。规范测试入口为上面的命令。

## 文档截图

`npm run docs:screenshots` 使用独立临时数据库和虚构作品捕获实际界面，不连接真实模型或账号。截图说明及参数见 [截图目录](screenshots/README.md)。

## 改动约定

前端统一通过 `src/api.js` 调用后端。涉及保存、鉴权、代理、SSE、正文替换和续传的改动，应补充相应回归；改动数据格式时应保留现有作品，避免静默覆盖。

目录职责见 [项目架构](architecture.md)，提交规范见 [贡献指南](../CONTRIBUTING.md)，打包与工作流配置见 [发布指南](releasing.md)。
