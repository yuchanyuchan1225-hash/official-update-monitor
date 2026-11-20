修正版 v1.1（2026-11-20）

替换 GitHub 仓库根目录 collector.py 即可。
根目录 sources.json 不需要替换：附件中的 sources.json 仅供核对和本地测试，原仓库配置保持不变。
不要替换 config/sources.json，不要删除 data/history.json、data/audit.csv 或 data/audit.json。

改动：
1. 修正带时区 ISO 日期的转换。
2. HTML 页面新增严格的“标题含发布日期+更新关键词+官方域名”的链接解析备用方案。不能保证动态网页提取成功。
3. 保留原 new_items（历史中首次发现），另输出 recent_new_items（首次发现且发布日期/更新日期在本次运行前24小时内）。
4. data/audit.json 增加 recent_new_items、recent_window_hours；data/latest_recent.json 保存最近24小时的新增条目。
5. data/audit.csv 保留原列结构，避免破坏已有历史文件。

重要限制：
- 未验证各网站的在线页面结构，HTML 解析成功率仍需实际运行核实。
- recent_new_items 不包含“历史中已经出现，但今天被更新”的条目。要监测内容修订，需要后续增加版本追踪。
- Meta 目前只覆盖版本表，不代表完整 Marketing API 变更。
- Dotdigital 当前仍是固定文章 URL，不是滚动索引。需后续验证新的官方入口后再替换。
- 首次运行可产生很多历史 new_items，不应作为今日新闻。

操作：
GitHub -> 仓库根目录 -> collector.py -> Edit -> 替换为修正版完整代码 -> Commit changes。
然后 Actions -> Collect official updates -> Run workflow。
查看 Actions 日志和 data/audit.json、data/latest_recent.json。
