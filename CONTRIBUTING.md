# 参与开发

使用 Node.js 24+ 和独立 Python 虚拟环境，安装 package-lock.json 与 backend/requirements.txt 中的依赖。

提交前运行：

```bash
npm test
python -m unittest discover -s backend/tests -v
npm run build
```

涉及保存、鉴权、代理、正文替换、SSE 或续传的修改，请补充行为回归测试。后端测试必须设置临时 NOVEL_DATA_DIR，模型和网络测试使用模拟传输，不使用真实供应商 Key。

可选运行 npm run test:browser 验证实际页面、IndexedDB 恢复及流式代理。不要把根目录中的历史自动化脚本纳入测试发现；不要提交数据库、运行配置、私人素材和导出正文。

保持单用户安全边界，前端统一通过 src/api.js 访问后端。改变数据格式时应兼容现有作品，避免静默覆盖正文；需要替换时提供预览和恢复路径。

项目代码采用根目录 LICENSE 中的 MIT 许可证。提交代码时请确认你有权以该许可贡献，并保留所用第三方组件的版权与许可声明；图片等资源需同时提供来源和授权说明。
