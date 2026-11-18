# 官方更新采集试点（第一阶段）

这是一个只做“发现与留痕”的最小版本：不连接 AI，不生成日报，不修改任何现有 ChatGPT 自动任务。

## 当前范围与来源状态

| 平台 | 当前入口 | 采集方式 | 已核实的事实 |
|---|---|---|---|
| AWS | `aws.amazon.com/new/feed/` | RSS | 官方 RSS 入口存在；每次运行仍实际探测。 |
| Azure | Azure Updates | HTML | 官方更新页存在；页面可能依赖浏览器渲染。 |
| Meta Marketing API | Graph / Marketing API Versions | HTML | 官方版本变更入口存在；不是保证免登录抓取成功。 |
| Salesforce | Release Note Changes | HTML | 官方发布说明页存在。 |
| HubSpot | Product Blog RSS | RSS | 官方 RSS 入口存在；账户内 Product Updates 不等于公开全量更新。 |
| Adobe Experience Cloud | Central Release Notes | HTML | 官方集中发布说明入口存在。 |
| Braze | What's new in Braze | HTML | 官方发布说明页存在；未假定有 RSS。 |
| Dotdigital | Personalization release note | HTML | 已找到官方的带日期更新页；滚动更新索引尚待运行验证。 |

“存在入口”不等于“本程序已成功采到条目”。首次真实运行的 `data/audit.json` 与 `data/audit.csv` 才是成功或失败证据。

## 运行

需要 Python 3.10+，无第三方依赖。

```powershell
python collector.py --dry-run
python collector.py
```

`--dry-run` 只检查配置，不发网络请求。正式运行会写入：

| 文件 | 用途 |
|---|---|
| `data/history.json` | 去重索引与每条记录的 `first_discovered_at`。 |
| `data/audit.json` | 本次运行的完整结构化审计，包括失败原因。 |
| `data/audit.csv` | 可追加的审计表，便于筛选和复核。 |

字段语义严格分开：

- `published_at`：来源给出的发布日期；没有就为 `null`。
- `updated_at`：来源给出的更新时间；没有就为 `null`。RSS 的单一日期会同时记录为两者，原始文本保留在 `date_raw`。
- `first_discovered_at`：本程序第一次看到该条目的 UTC 时间，绝不冒充发布日期。

HTML 页面目前以链接发现为最小策略。审计会标记为 `accessible_candidates`，而非采集成功：它只表示页面可访问且发现候选链接。它会保存没有日期的候选项，但不会猜测日期；这些结果适合作为下一阶段为每个页面增加专用解析器的证据基础。

## 自动运行

`.github/workflows/collect.yml` 在 **06:50 JST**（21:50 UTC）每天触发，满足“JST 07:00 前”。GitHub 定时任务可能有调度延迟；若“严格不晚于 07:00”是硬性要求，应换用有 SLA 的调度器，而不是把 GitHub cron 当作实时系统。

工作流会提交 `data/` 下的审计和历史。仓库需要允许 GitHub Actions 具备 **Read and write permissions**；否则采集可以运行，但提交会失败并留在工作流日志中。
