# 官方更新采集：手动安装包（试点版）

## 当前版本能做什么
- GitHub Actions 每天日本时间约06:30自动触发；也可手动运行。
- 8个重点来源逐一请求，保存 HTTP 状态、错误、UTC 检查时间。
- AWS RSS 解析文章标题、URL、原始发布时间、原始更新时间、首次发现时间，保存去重历史。
- 其他7个 HTML 来源**只测试网页是否可读取**，并明确标记 `html_reachable_not_verified`；不能视为新闻条目核查成功。
- 这是验证采集链路的最小版本，不是27平台日报系统，也未连接 ChatGPT。

## 上传步骤（手动）
1. 解压 ZIP。在 GitHub 打开你已有的仓库，进入 `Code` 页面。
2. 使用 `Add file → Upload files` 上传 `requirements.txt`、`scripts/collect.py`、`config/sources.json`、`.gitignore`。GitHub 网页上传可拖动文件夹，确保最终路径正确。
3. **重要：隐藏文件夹 `.github/workflows/collect.yml`**。如果网页上传无法保留隐藏目录，请用 `Add file → Create new file`，在文件名输入 `.github/workflows/collect.yml`，把包中该文件内容粘贴进去并提交到 `main` 分支。
4. 在 `Settings → Actions → General → Workflow permissions` 选择 `Read and write permissions`（如果组织政策允许）。这是为了把 `data/` 自动提交回仓库；如不允许，仍可从 Actions 的 Artifacts 下载结果。
5. 在 `Actions → Collect official updates → Run workflow` 手动执行一次。
6. 打开运行记录，检查 `Collect and audit` 日志和 `Artifacts`。确认 `data/latest_audit.csv`、`data/latest_summary.json`、`data/latest_new_items.csv`。
7. 第二天检查是否自动运行。注意 GitHub 定时任务可能延迟；仓库必须启用 Actions，workflow 应位于默认分支。

## 时间说明
`cron: '30 21 * * *'` 使用 UTC，对应**次日日本时间06:30**，预留30分钟给07:00日报。GitHub 的计划运行可能延迟，不保证准点。

## 如何解读审计
- `feed_parsed`：RSS 真正解析到条目，但每条发布日期是否有值还需看 `date_verified`。
- `html_reachable_not_verified`：网页可打开，**未核查具体产品更新或日期**，不能计入有效新闻覆盖率。
- `failed`：网络、403、404、超时、解析等失败，原因见 `error`。
- `new_items`：首次被本脚本看到的条目；第一次运行会把 Feed 当前全部条目视为新发现，**不是过去24小时的新消息**。
- `published_raw`、`updated_raw` 为来源原文，`first_seen_utc` 为脚本第一次发现时间；三者不能混用。

## 重要限制
- Azure/Meta/Salesforce/HubSpot/Adobe/Braze/Dotdigital URL 是待验证的官方入口候选；访问失败不代表厂商没有更新。
- HTML 页面可能由 JavaScript 动态渲染；本版不从这些页面猜测发布日期。
- 若当前仓库已经存在同名 `.github/workflows/collect.yml`，请先备份并对照；不要同时保留两个相同用途的工作流。
- 不会自动修改你已有的 ChatGPT 定时任务。下一阶段再做各官方来源的可验证 RSS/API/HTML 条目解析与数据对接。
