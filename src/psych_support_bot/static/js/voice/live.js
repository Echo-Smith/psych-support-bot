// TTS live 全双工会话状态机（/v1/voice/tts/live）：LLM 流式句直灌（say），
// 服务端 PCM 帧直推 + sentence_end/round_end 控制面；WS 不可用回退句级 HTTP
// 队列（预取流水线，由注入的 fallbackToQueue 承接）。协议权威定义见
// src/psych_support_bot/infra/voice/protocol.py（前端镜像 js/voice/protocol.js）。
// 从 index.html 原样迁出（行为不变）；WS 地址/PCM 播放/字幕回调/定时器全部
// 注入，node --test 用假 WebSocket 钉住状态机迁移行为。

// round 收束硬上限——MiMo 免费期上游偶发挂死会让服务器 round_end 迟到两
// 分钟，黄框假死期间麦克风一直被挂起（第二次说话录不进的根因链）。取值
// 与服务端 _TTS_LIVE_UPSTREAM_RECV_TIMEOUT=30s 对齐（略小，前端先收束），
// 详见 docs/technical/VOICE_PROTOCOL.md 超时对齐表。
export const ROUND_TIMEOUT_MS = 25000;

export function createTtsLive(deps) {
  const { wsUrl, debug, pcm, playBlob, ui, fallbackToQueue } = deps;
  const timers = deps.timers || {
    setTimeout: (...a) => setTimeout(...a),
    clearTimeout: (...a) => clearTimeout(...a),
  };
  // 注入 WS 构造器：浏览器用原生 WebSocket；node 环境恰好也有全局 WebSocket
  // （undici，会真联网），测试必须显式给假的。
  const WebSocketCtor = deps.WebSocket || globalThis.WebSocket;
  const roundTimeoutMs = deps.roundTimeoutMs || ROUND_TIMEOUT_MS;

  const TTS_LIVE = {
    ws: null, failed: false, pending: [], roundStarted: false, ended: false,
    curBytes: [], curChars: 0,
    pendingTexts: [], // 已 say 未播的句子文本，随 sentence_end 出队随音频起播上屏
    pcm: false, sentenceStart: null, firstAudioMarked: false, sentenceSamples: 0, pendingEnd: false, finalTakeover: false, // PCM 流式播放态（②）+ 每句样本数（字幕按时长铺）+ 定稿接管标记
    chain: Promise.resolve(),
    roundDone: null,
  };

  function ttsLiveReset() {
    TTS_LIVE.ws = null; TTS_LIVE.failed = false;
    TTS_LIVE.pending = []; TTS_LIVE.roundStarted = false; TTS_LIVE.ended = false;
    TTS_LIVE.curBytes = []; TTS_LIVE.curChars = 0; TTS_LIVE.pendingTexts = [];
    TTS_LIVE.pcm = false; TTS_LIVE.sentenceStart = null; TTS_LIVE.firstAudioMarked = false; TTS_LIVE.sentenceSamples = 0;
    TTS_LIVE.pendingEnd = false; TTS_LIVE.finalTakeover = false;
    TTS_LIVE.chain = Promise.resolve();
    TTS_LIVE.roundDone = null;
    pcm.stopAll(); // 全量复位语义包含掐掉在排播的 PCM 队列
  }

  function ttsHexToBytes(hex) {
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
    return out;
  }

  // 当前句音频攒齐（sentence_end）→ 入串行播放链（句间零空等）。
  // 文本随播上屏：MiniMax 的分句边界与我们的 say 近似 1:1（LLM 句已短），
  // 出队错位最坏是某句文字提前/延后一拍，final 会统一纠正。
  function ttsLiveFlushSentence() {
    if (!TTS_LIVE.curBytes.length) return;
    const bytes = TTS_LIVE.curBytes;
    const chars = TTS_LIVE.curChars;
    const text = TTS_LIVE.pendingTexts.shift() || '';
    TTS_LIVE.curBytes = []; TTS_LIVE.curChars = 0;
    const blob = new Blob(bytes, { type: 'audio/mpeg' });
    TTS_LIVE.chain = TTS_LIVE.chain.then(() => playBlob(blob, chars, text));
  }

  async function ttsLiveEnsure() {
    if (TTS_LIVE.ws && TTS_LIVE.ws.readyState === 1) return TTS_LIVE.ws;
    const ws = new WebSocketCtor(wsUrl());
    ws.binaryType = 'arraybuffer';
    ws.onmessage = (e) => {
      // 连接代次守卫：abort 后 MiniMax 取消生效前仍会泵出残余 PCM 块，
      // 旧连接在途帧若入队就是"多条信息杂乱堆叠"的串音根因——一律作废
      if (TTS_LIVE.ws && TTS_LIVE.ws !== ws) return;
      // 二进制帧 = PCM 音频块（②协议）：直接入队，首块即排定起播
      if (TTS_LIVE.pcm && e.data instanceof ArrayBuffer) {
        TTS_LIVE.sentenceSamples += e.data.byteLength / 2; // s16le 单声道 → 样本数
        const start = pcm.feed(e.data);
        if (start != null) {
          if (TTS_LIVE.sentenceStart == null) TTS_LIVE.sentenceStart = start; // 当前句的首块时刻
          if (!TTS_LIVE.firstAudioMarked) {
            TTS_LIVE.firstAudioMarked = true;
            timers.setTimeout(() => { ui.turnMark('firstAudio'); ui.turnTryReport(); },
              Math.max(0, (start - pcm.state.ctx.currentTime) * 1000));
          }
        }
        return;
      }
      let ev; try { ev = JSON.parse(e.data); } catch (err) { return; }
      if (ev.type === 'ready') {
        // 能力协商：服务端声明 PCM → 流式起播；否则维持 mp3-b64 整句旧路径
        TTS_LIVE.pcm = !!(ev.audio && ev.audio.format === 'pcm');
        if (ev.audio && ev.audio.sample_rate) pcm.state.rate = ev.audio.sample_rate;
      } else if (ev.type === 'audio' && ev.b64) {
        TTS_LIVE.curBytes.push(ttsHexToBytes(ev.b64));
        TTS_LIVE.curChars += 4; // 粗略累加字数供播放看护估算
      } else if (ev.type === 'sentence_end') {
        if (TTS_LIVE.pcm) {
          // 定稿接管后正式气泡负责铺字，live 字幕退场（只出队、清计数）
          if (TTS_LIVE.finalTakeover) {
            TTS_LIVE.pendingTexts.shift();
            TTS_LIVE.sentenceStart = null; TTS_LIVE.sentenceSamples = 0;
            return;
          }
          // 文字贴语音铺：reveal 总时长 = 该句 PCM 实际时长；该句音频起播
          // 时刻若已过（合成快于实时、sentence_end 晚于起播），文字按已过
          // 时间追平进度。leadMs>0 则等音频开场再开始铺。
          const text = TTS_LIVE.pendingTexts.shift() || '';
          const at = TTS_LIVE.sentenceStart;
          const samples = TTS_LIVE.sentenceSamples;
          TTS_LIVE.sentenceStart = null; TTS_LIVE.sentenceSamples = 0;
          if (text) {
            const durMs = Math.max(700, Math.min(9000, (samples / pcm.state.rate) * 1000 / pcm.state.speed));
            const leadMs = (at != null && pcm.state.ctx) ? (at - pcm.state.ctx.currentTime) * 1000 : 0;
            const round = ui.getRound();
            if (leadMs > 20) {
              timers.setTimeout(() => ui.appendRound(round, text, 0, durMs), leadMs);
            } else {
              ui.appendRound(round, text, -leadMs, durMs);
            }
          }
        } else {
          ttsLiveFlushSentence();
        }
      } else if (ev.type === 'round_end') {
        if (TTS_LIVE.pcm) {
          TTS_LIVE.ws = null;
          const done = TTS_LIVE.roundDone; TTS_LIVE.roundDone = null;
          if (done) pcm.drained().then(done); // 队列播完才收黄框
        } else {
          ttsLiveFlushSentence();
          TTS_LIVE.ws = null;
          const done = TTS_LIVE.roundDone; TTS_LIVE.roundDone = null;
          if (done) done();
        }
      } else if (ev.type === 'error') {
        debug('tts live: ' + (ev.detail || 'error'));
        // 上游会话中断（配额/风控等）：剩余未获句尾事件的句子转投 HTTP 句
        // 队列续读，后半段不再静默消失；本页 WS 通道本会话弃用。
        // aborted 判定与过滤在接线侧（TTS_QUEUE 所有权不进本模块）。
        TTS_LIVE.failed = true;
        const rest = TTS_LIVE.pending.splice(0).concat(TTS_LIVE.pendingTexts.splice(0));
        fallbackToQueue(rest);
      }
    };
    ws.onclose = () => {
      if (TTS_LIVE.ws && TTS_LIVE.ws !== ws) return; // 废弃连接的尾巴事件
      // 连接中断：冲刷未完句，唤醒等待者（其上方 onmessage 已尽力收尾）
      ttsLiveFlushSentence();
      if (TTS_LIVE.ws === ws) TTS_LIVE.ws = null;
      const done = TTS_LIVE.roundDone; TTS_LIVE.roundDone = null;
      if (done) done();
    };
    await new Promise((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error('ws open failed'));
      timers.setTimeout(() => reject(new Error('ws open timeout')), 5000);
    });
    TTS_LIVE.ws = ws;
    return ws;
  }

  // 一轮朗读（全文）：say 全文 + end，MiniMax 原生攒句，音频按 sentence_end
  // 渐进串播，round_end 后等播放链排空再 resolve（保证朗读完整）。
  // 失败向上抛，由调用方回退 HTTP 句队列。
  async function ttsLiveRound(text) {
    // 新一轮：重置上一轮残留状态（ws 在 round_end 后已被服务端关闭）。
    // revise 整轮不逐句上屏（MiniMax 分句 ≠ 我们的句），文字照旧等 final。
    TTS_LIVE.pending = [];
    TTS_LIVE.curBytes = []; TTS_LIVE.curChars = 0; TTS_LIVE.pendingTexts = [];
    TTS_LIVE.sentenceStart = null; TTS_LIVE.firstAudioMarked = false; TTS_LIVE.sentenceSamples = 0;
    TTS_LIVE.pendingEnd = false; TTS_LIVE.finalTakeover = false;
    ui.resetShownChars(); // revise 整轮重读：live 泡作废，字数预算清零
    pcm.stopAll();
    TTS_LIVE.chain = Promise.resolve();
    TTS_LIVE.roundStarted = true; TTS_LIVE.ended = true;
    await ttsLiveEnsure();
    ttsLiveSend({ type: 'say', text });
    ttsLiveSend({ type: 'end' });
    await new Promise((resolve) => {
      TTS_LIVE.roundDone = () => { TTS_LIVE.chain.then(resolve); };
    });
  }

  function ttsLiveSend(obj) {
    if (TTS_LIVE.ws && TTS_LIVE.ws.readyState === 1) TTS_LIVE.ws.send(JSON.stringify(obj));
  }

  // 打断 = 断连弃用：abort 帧发出后立刻掐掉这条 WS——MiniMax 的 task_cancel
  // 生效前残余音频仍会下发，留着连接就是下一轮开头串进上一轮尾巴的杂音。
  function killLiveWs(ws) {
    if (!ws) return;
    try { ws.onmessage = ws.onclose = ws.onerror = null; ws.close(); } catch (err) { /* 已关 */ }
    if (TTS_LIVE.ws === ws) TTS_LIVE.ws = null;
  }

  // LLM 流式句：直灌同一 WS 会话（say），播放由 sentence_end 驱动；
  // ws 未就绪时排队 pending，就绪后 drain。不重置 curBytes——上一句的
  // 尾部音频可能仍在途，冲刷只由服务端 sentence_end 事件触发。
  function ttsLiveSay(text) {
    TTS_LIVE.pending.push(text);
    TTS_LIVE.pendingTexts.push(text);
    TTS_LIVE.roundStarted = true;
    if (TTS_LIVE.ws && TTS_LIVE.ws.readyState === 1) {
      ttsLiveDrainPending();
    } else if (!TTS_LIVE.failed) {
      ttsLiveEnsure().then(ttsLiveDrainPending).catch(() => { TTS_LIVE.failed = true; pcm.stopAll(); });
    }
  }

  function ttsLiveDrainPending() {
    while (TTS_LIVE.pending.length && TTS_LIVE.ws && TTS_LIVE.ws.readyState === 1) {
      ttsLiveSend({ type: 'say', text: TTS_LIVE.pending.shift() });
    }
    // says 补发完后若有等待中的 end（握手期排队的），此刻一并送达
    if (TTS_LIVE.pendingEnd && TTS_LIVE.ws && TTS_LIVE.ws.readyState === 1) {
      TTS_LIVE.pendingEnd = false;
      ttsLiveSend({ type: 'end' });
    }
  }

  // 流式轮收轮：end + 等 round_end（此时 chain 里可能还有未播完的句，
  // 等 chain 也结束再 resolve，保证朗读完整）
  async function ttsLiveEndRound() {
    TTS_LIVE.ended = true;
    // 先 drain 任何 pending says 再发 end
    ttsLiveDrainPending();
    if (TTS_LIVE.ws && TTS_LIVE.ws.readyState === 1) {
      ttsLiveSend({ type: 'end' });
    } else {
      // WS 还在握手（投机轮 18 句+final 同帧到达的常态时序）：end 排队等
      // drain，绝不静默丢——丢了 MiniMax 不吐尾句音频、task_finished 不来，
      // 表现为"朗读读到一半没了"（2026-09-10 四段例实证）
      TTS_LIVE.pendingEnd = true;
    }
    // 等上游 round_end + 本地 chain 全播完；**硬上限 roundTimeoutMs**——
    // 上游挂死时超时=掐队列强制收束（麦克风不能被黄框假死挂住）。
    await new Promise((resolve) => {
      const timer = timers.setTimeout(() => {
        debug('tts live: round timeout(' + roundTimeoutMs + 'ms), force finish');
        resolve();
      }, roundTimeoutMs);
      TTS_LIVE.roundDone = () => { timers.clearTimeout(timer); TTS_LIVE.chain.then(resolve); };
    });
    pcm.stopAll(); // 正常完成=空操作（源已播完）；超时兜底=掐掉滞留队列
  }

  return {
    state: TTS_LIVE, ttsLiveReset, ttsHexToBytes, ttsLiveFlushSentence,
    ttsLiveEnsure, ttsLiveRound, ttsLiveSend, killLiveWs, ttsLiveSay,
    ttsLiveDrainPending, ttsLiveEndRound,
  };
}
