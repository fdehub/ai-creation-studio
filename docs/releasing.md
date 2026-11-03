# 发布指南

## 源码包

从仓库根目录运行：

```bash
npm run release:source
```

打包脚本使用明确的文件与目录类型允许列表，检查常见内嵌凭据格式，输出 `release/ai-creation-studio-source.zip`。包内包含应用源码、文档、隔离测试、MIT LICENSE 和第三方声明。

源码包不会包含 `.env`、`runtime.env`、平台账号会话、数据库、上传素材、私人作品、日志、未使用的模板插图或历史本地自动化。发布前仍需检查本次改动及 Git 暂存内容；格式检查不能识别所有凭据，也不能清除以前的 Git 历史。

## 发布检查

1. 运行 [开发指南](development.md)中的相关测试及生产构建。
2. 检查更新日志、示例配置和文档链接。
3. 确认新增素材及第三方代码有相应授权，并保留版权声明。
4. 生成源码包，确认不含私有配置和用户数据。

不直接压缩整个工作目录。已移除历史脚本中的真实 Key 字面值；如果旧凭据曾公开，仍需到供应商处轮换。

## GitHub Actions

工作流模板位于 [.github/workflow-templates/ci.yml](../.github/workflow-templates/ci.yml)，包括 Windows/Linux 与 Python 版本矩阵、前端构建、后端回归及浏览器测试。

当前 GitHub 凭据没有 `workflow` 权限，**自动 CI 尚未开启**。启用方式：

1. 使用有工作流写权限的 GitHub 凭据。
2. 将模板复制到 `.github/workflows/ci.yml`。
3. 移除 `.gitignore` 中对该活动工作流文件的忽略规则，提交并推送。

模板本身不会执行，不能将本地测试通过表述为云端 CI 通过。

## 版本记录

面向使用者的版本变化写入 [CHANGELOG.md](../CHANGELOG.md)。详细审查证据集中在 [审查记录](README.md#审查记录)，不再放在仓库根目录。
