---
name: weather
description: 获取当前天气和预报（无需 API 密钥）。
homepage: https://wttr.in/:help
metadata: {"nanobot":{"emoji":"🌤️","requires":{"bins":["curl"]}}}
---

# 天气 (Weather)

两个免费服务，无需 API 密钥。

## wttr.in (首选)

快速单行:
```bash
curl -s "wttr.in/London?format=3"
# 输出: London: ⛅️ +8°C
```

紧凑格式:
```bash
curl -s "wttr.in/London?format=%l:+%c+%t+%h+%w"
# 输出: London: ⛅️ +8°C 71% ↙5km/h
```

完整预报:
```bash
curl -s "wttr.in/London?T"
```

格式代码: `%c` 状况 · `%t` 温度 · `%h` 湿度 · `%w` 风 · `%l` 地区 · `%m` 月相

提示:
- URL 编码空格: `wttr.in/New+York`
- 机场代码: `wttr.in/JFK`
- 单位: `?m` (公制) `?u` (美制)
- 仅今天: `?1` · 仅当前: `?0`
- PNG: `curl -s "wttr.in/Berlin.png" -o /tmp/weather.png`

## Open-Meteo (后备, JSON)

免费，无 Key，适合程序化使用:
```bash
curl -s "https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current_weather=true"
```

查找城市的坐标，然后查询。返回包含温度、风速、天气代码的 JSON。

文档: https://open-meteo.com/en/docs
