# GitRadar V3 — 爆款发现 + 可选 AI 中文摘要

适用仓库：`w452187971/gitradar`

## 升级（请务必保留历史数据）

1. **先不要删除仓库中的 `data/history.json`、`data/projects.json`！** V3 继续使用 V2 的历史快照。
2. 仅将压缩包里的 `index.html`、`collect.py`、`.github/workflows/update.yml` 上传到原仓库对应路径，覆盖旧文件。
3. `.github` 隐藏文件夹上传不方便时，在 GitHub 网页上编辑现有的 `.github/workflows/update.yml`，替换为本包对应内容。
4. 确认仓库 Settings → Actions → General → Workflow permissions 允许 Read and write permissions。
5. 在 Actions → Update GitRadar data → Run workflow 手动执行一次。
6. 等待成功后刷新网站（可能需要几分钟才能发布）。

## AI 中文摘要（可选，可能产生 API 费用）

无需配置也能运行 V3。若希望生成 AI 中文摘要：在仓库 Settings → Secrets and variables → Actions → New repository secret，名称填 `OPENAI_API_KEY`，值填**你自己的 API 密钥**（不要把密钥发给别人，也不要写进仓库代码）。工作流将每天最多生成 12 个新增或简介发生变化的摘要，并缓存结果。仅基于英文描述和 README 摘录总结，不代表对项目的安全性或功能做过验证。默认使用 `gpt-4.1-mini`，需要账户支持该模型并有 API 额度。

## 局限

- 榜单是搜索条件筛选出的**候选池**，不是 GitHub 全站 Star 增长完整排名。
- 7 天增量需至少 8 天每日快照；首次升级不会立即出现真实的 7 天增长。
- 发现评分是启发式指标，不代表项目安全性、实际质量或已核实的爆火原因。
- GitHub API 有搜索结果上限和速率限制，定时任务可能延迟。
- 保留 V2 的 `data/history.json` 才能延续原有 Star 记录。
