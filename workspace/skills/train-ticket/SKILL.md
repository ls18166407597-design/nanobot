---
name: train-ticket
description: 使用 train_ticket 工具查询 12306 车票（城市/车站解析、日期规范化、余票检索）。
metadata:
  {
    "nanobot": {
      "tags": ["travel", "ticket", "12306"],
      "scope": "business"
    }
  }
---

# 火车票查询技能 (Train Ticket)

当用户要查询火车票、余票、车次时，优先使用本技能。

## 适用场景
- 查询「某天 A 到 B 的火车票」。
- 查询高铁/动车等特定车型余票。
- 用户给的是自然语言日期（今天/明天/后天）。

## 执行规则
1. 优先调用 `train_ticket`，不要改用通用联网检索。
2. 必填信息不全时先澄清：出发地、到达地、日期。
3. 用户给城市就用城市，给具体车站则优先车站。
4. 返回结果时保留关键字段：车次、站点、时间、余票。
5. 回复首行保留系统标准：`查询来源: 12306`（由系统自动注入）。

## 推荐调用
- 基础查询：
  `train_ticket(action="search", from_city="上海", to_city="杭州", date="明天")`
- 指定车站：
  `train_ticket(action="search", from_city="上海", to_city="杭州", from_station="上海虹桥", to_station="杭州东", date="2026-02-13")`
- 指定车型：
  `train_ticket(action="search", from_city="上海", to_city="杭州", date="明天", train_types="G")`

## 失败处理
- 若提示缺参数：先向用户补问，不盲试。
- 若提示站点解析失败：改问用户“具体车站名”后重试。
- 若仍失败：明确返回失败原因，不编造票务结果。
