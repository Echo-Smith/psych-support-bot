// 客户端分句：句末标点优先，无标点长段按长度切。
// 从 index.html 原样迁出（行为不变）。服务端权威实现在
// services/conversation.py:_split_complete_sentences（渲染粒度）；本函数是
// HTTP 句队列回退路径的朗读粒度，阈值略宽。两端语义由同一组 fixture
// 钉住（tests/frontend/sentences.test.mjs + tests/unit/test_conversation.py）。
export function splitIntoSentences(text) {
  const out = [];
  let cur = '';
  for (const ch of text) {
    cur += ch;
    const stripped = cur.trim();
    if ('。！？；!?;\n'.includes(ch)) {
      if (stripped) out.push(stripped);
      cur = '';
    } else if ('，、：, '.includes(ch) && stripped.length >= 40) {
      out.push(stripped);
      cur = '';
    }
  }
  if (cur.trim()) out.push(cur.trim());
  return out.filter(Boolean);
}
