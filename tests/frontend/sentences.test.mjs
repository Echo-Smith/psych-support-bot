// 分句一致性（前端侧）：splitIntoSentences 对照共享 fixture（服务端权威口径
// 在 tests/unit/test_sentence_fixture.py）。行为不变性由本文件钉住——抽取或
// 调整朗读粒度时，改动即红。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { splitIntoSentences } from '../../src/psych_support_bot/static/js/voice/sentences.js';

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(here, 'fixtures', 'sentences.json'), 'utf8'));

test('golden：纯句末标点文本与服务端逐字一致', () => {
  for (const c of fixture.golden_both_agree) {
    assert.deepEqual(splitIntoSentences(c.input), c.expected, c.name);
  }
});

test('client 朗读粒度语义（软标点 40 / 尾句兜底 flush）', () => {
  for (const c of fixture.client_only) {
    assert.deepEqual(splitIntoSentences(c.input), c.expected, c.name);
  }
});

test('空输入产出空数组', () => {
  assert.deepEqual(splitIntoSentences(''), []);
  assert.deepEqual(splitIntoSentences('   '), []);
});
