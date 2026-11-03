# 模型与运行配置

## 配置模型

进入 **策略与设置 → AI 引擎策略**，添加兼容 Chat Completions 的服务地址、模型名及自己的 API Key，再分配给各 Agent。

服务地址应为基础路径，例如 `https://api.openai.com/v1`；应用会追加 `/chat/completions`。平台账号登录及其调用边界见 [账号接入](accounts.md)。

所有模型请求经过后端。默认允许 `api.openai.com`，并兼容部署者在进程环境或 `.env` 中设置的 `*_BASE_URL` 主机。新增服务商时，由部署者设置 `NOVEL_PROVIDER_HOSTS`；前端不能扩大允许列表。

工作台保存用户填写的 API Key 配置，请在可信浏览器中使用。本机 `backend/.env`、`runtime.env` 和账号凭据目录不进入源码发布包。

## 运行参数

可参考 [runtime.env.example](../backend/runtime.env.example) 创建本机 `backend/runtime.env`。不要覆盖已有 `.env`。优先级为：进程环境 → `runtime.env` → `.env`。

| 参数 | 用途 |
| --- | --- |
| `NOVEL_DATA_DIR` | 数据目录；默认固定为 `backend/`，与启动位置无关 |
| `NOVEL_ACCESS_TOKEN` | 后端访问令牌；远程部署必须设置随机长令牌 |
| `NOVEL_ALLOWED_HOSTS` | 接受的 Host 主机名，逗号分隔；本机默认为 localhost、127.0.0.1、[::1] |
| `NOVEL_ALLOWED_ORIGINS` | 允许的前端来源，包含协议和端口 |
| `NOVEL_PROVIDER_HOSTS` | 允许的公网模型主机；只允许 HTTPS 443；设置后替换默认列表 |
| `NOVEL_LOCAL_PROVIDER_HOSTS` | 显式允许访问的可信本地模型主机；默认为空 |
| `VITE_API_BASE_URL` | 前端构建时的 API 基础地址；默认 `/api` |
| `NOVEL_API_PROXY` | Vite 开发/预览代理的后端地址；默认 `http://127.0.0.1:8100` |
| `NOVEL_FRONTEND_PORT` | 开发前端端口；默认 5273 |

## 本机与远程访问

本机模式为受信任的本机页面签发会话令牌。设置 `NOVEL_ACCESS_TOKEN` 后会关闭自动签发，由页面提示输入后端访问令牌。它与模型供应商的 API Key 是两种不同凭据。

当前是共享令牌的单用户应用，令牌持有者可以访问全部作品并使用已连接的平台账号。远程部署需使用 HTTPS 反向代理，将 `/api` 转发到后端，配置令牌及允许的域名和来源，并限制直接访问后端端口。

开发服务器限制文件读取范围，禁止从前端端口直接读取后端配置、数据库和私人恢复文件。进一步的边界见 [安全说明](../SECURITY.md)。
