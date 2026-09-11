# TTS Live 控制面协议（/v1/voice/tts/live）

全双工 TTS 管道：浏览器开一条 WS，LLM 流式产出的句子以 `say` 推入，服务端
逐句合成、音频以 **二进制 PCM 帧** 直推，控制面走 **JSON 文本帧**。

**权威定义**（改协议先改这里，四处同步）：

| 层 | 位置 | 说明 |
|---|---|---|
| 模型（服务端） | `src/psych_support_bot/infra/voice/protocol.py` | pydantic 模型 + 解析/导出 |
| 常量（前端） | `static/js/voice/protocol.js` | 事件名/构造器，与模型同名同源 |
| 机读 Schema | `docs/technical/voice-protocol.schema.json` | `scripts/export_voice_protocol.py` 生成 |
| 交叉校验 | `tests/unit/test_voice_protocol.py` + `tests/frontend/protocol.test.mjs` | 前后端常量漂移即红 |

## 传输面

- **控制面**：JSON 文本帧，模型见 `protocol.py`。
- **音频面**：二进制帧 = 裸 PCM（s16le mono），采样率由 `ready` 事件声明
  （MiniMax 32000 / MiMo 24000）。前端 WebAudio 队列零转换首块即播。
- 鉴权：query `?token=`（浏览器 WS 无法自定义 Header），`AUTH_ENABLED` 时校验。

## 消息目录

客户端 → 服务端：

| type | 字段 | 语义 |
|---|---|---|
| `say` | `text: str` | 合成一句（LLM 流式句或整轮全文）；空文本忽略 |
| `end` | — | 本轮结束：say 队列排空后关上游会话 |
| `abort` | — | 打断：取消上游合成；前端同时掐本地连接，残余帧由连接代次守卫作废 |

服务端 → 客户端：

| type | 字段 | 语义 |
|---|---|---|
| `ready` | `audio: {format:"pcm", sample_rate:int}` | 会话就绪 + 音频面声明；此后二进制帧即音频块 |
| `sentence_end` | — | 当前句音频边界（MiMo=say 粒度；MiniMax=is_final）。驱动字幕铺字/下一句 |
| `round_end` | — | 本轮终点：此后不再有音频帧，前端可收束。**error 之后必补发** |
| `error` | `detail: str` | 上游故障。触发前端降级契约（见下） |

## 时序

**流式轮（LLM 句级直灌）**

```
浏览器 → say(句1) → say(句2) → … → end
服务端 → ready → [PCM帧…] → sentence_end → [PCM帧…] → sentence_end → … → round_end
```

**整轮全文（ttsLiveRound：revise 重读 / 投机轮）**：`say(全文)` + `end`，其余同上。

**打断**：`abort` → 前端立即 `killLiveWs`（连接作废，不等服务端）；服务端发
`task_cancel` 后关连。在途残余帧被连接代次守卫丢弃（防串音）。

## 降级契约（error 的前端行为）

1. 把「已 say 未播」的剩余句子转投 HTTP 句级队列（`/v1/voice/speak/stream`）续读——
   上游半途故障不表现为"音频静默消失"。
2. 置 `TTS_LIVE.failed = true`：本页会话内 WS 通道弃用，后续轮直接走 HTTP 队列。
3. `error` 后服务端必发 `round_end`：前端总能收到终态，黄框不悬挂。

## 超时对齐（三方互相兜底，数值耦合是有意的）

| 位置 | 值 | 说明 |
|---|---|---|
| 服务端上游 recv 空闲 | 30s（`_TTS_LIVE_UPSTREAM_RECV_TIMEOUT`） | 句间间隔实测 <1s，卡 30s=上游挂起 |
| 前端 round 收束硬上限 | 25s（`ttsLiveEndRound`） | **略小于服务端**：前端先收束，麦克风不被假死挂起 |
| MiMo 流 read 超时 | 8s（adapter `_mimo_stream`） | 句级合成块间隔 <1s，卡 8s=上游挂起 |

改其中任何一个，其余两个的注释必须同步复核。

## 兼容性约定

- 新增服务端事件：前端未知 type 一律忽略（安全）。
- 新增字段：必须可选；未知字段两端都忽略（前向兼容）。
- 删除/改义事件：破坏性变更，前端同批发布，schema 与协议文档同步重生成
  （`.venv/bin/python scripts/export_voice_protocol.py`）。
