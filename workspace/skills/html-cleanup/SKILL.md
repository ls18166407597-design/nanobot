---
name: html-cleanup
description: 清洗网页 HTML 源码，提取纯文本，去除脚本、样式和 HTML 标签。
---

# HTML 清洗技能 (HTML Cleanup)

当需要从原始 HTML 源码（例如通过 `browser` 获得的页面源码或文件内容）中提取干净的纯文本时，请使用此技能。

## 使用场景
1. 对 `browser` 获取的内容进行二次清洗，以节省 Token 并提升检索精度。
2. 处理爬虫抓取的原始数据。
3. 将 HTML 转换为 AI 易于分析的文本格式。

## 核心脚本
脚本位置：`workspace/skills/html-cleanup/scripts/clean_html.py`

## 执行方式
通过 `exec` 工具运行该 Python 脚本，并通过标准输入传入 HTML 内容。

### 示例用法
```json
{
  "name": "exec",
  "arguments": {
    "command": "python workspace/skills/html-cleanup/scripts/clean_html.py",
    "input_data": "<html><body><h1>标题</h1><script>alert(1)</script><p>正文内容</p></body></html>"
  }
}
```

## 输出预期
干净的、已还原转义字符的纯文本内容。
