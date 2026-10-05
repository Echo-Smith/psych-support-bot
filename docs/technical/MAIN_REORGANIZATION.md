# Main-compatible delivery reorganization

Scope: Echo-Smith / Marsh Echo-owned pull requests only. PR #2 and #29 stay open; other authors' PRs and branches are untouched. Mirror is a separate project.

## Build and deployment foundation

Base: upstream main 255169f. Keep Dockerfile and docker-compose.yml, including the default 8000 port and Redis service. The server Compose variant keeps its existing data volumes. Container builds use the lockfile and install the project after its source is copied.

Migration assets have one canonical home in src/psych_support_bot/infra/db/migrations, included in the installed wheel. The root alembic.ini remains a checkout CLI entrypoint. Startup and CLI use those same revisions. Supported database upgrades include main's versioned migration schema and its unversioned create_all schema. Unknown or partial schemas stop instead of guessing a revision.

For an existing default Compose deployment whose database is inside the old container at /app/psych_support_bot.db, back it up and copy it into the new app-data volume before replacing that container. Existing server Compose data at /app/data keeps its location. This change does not deploy, reset or erase any environment.

Local validation: 74 unit tests passed; installed wheel startup/health/static passed. Package versions equal the previously audited lock; the registry changes to upstream PyPI. Main's older conversation integration tests call an external model and expose its existing fallback bug; that implementation is carried into the dialogue replacement, not hidden by this infrastructure change. Verification: fresh, versioned and unversioned main database upgrades; existing-user preservation; installed-wheel startup; default/server Compose validation and container smoke. Docker is unavailable locally, so container validation runs in GitHub CI and its result is recorded separately.

## Review order

The first replacement PR targets upstream main. Dependent replacements target the previous branch in Echo-Smith's fork so their review diffs show only their own increment. Promote them to upstream after the prerequisite is merged; avoid creating several cumulative PRs against the same unchanged upstream main.

## 第二层：对话及产品 API 基础

来自原 #22/#23/#24/#26 的稳定后端快照 b7202bc。身份认证、安全护栏、Prompt 分层、近史上下文、知识检索、练习记录、报告及问卷 API 相互引用，保留为同一后端层，前端资源单独提交。额外提前接入 fcd6130 的会话归属校验与消息同时间戳排序修复；流式接口及其归属测试在语音层恢复。

SQLite 迁移仍使用第一层的包内 runner，新增记录、练习、认证及报告字段迁移随后端交付。无 Mirror 文件或接口。

验证：完整单元与集成测试首轮 555 通过，唯一失败为本层尚不存在的流式接口测试；该测试归还第四层，当前读取与普通续聊的跨用户拒绝检查全部通过。构建与迁移启动单独验证。

## 第三层：产品前端

只同步 b7202bc 的静态前端、图标与 manifest，对应第二层已有的认证、练习、评估分页、打卡与个人记录 API；不引入语音或画像记忆实现。源码及隔离 wheel 的页面/静态资源启动验证与后端 CI 共同保障接口兼容。

## 第四层：语音、流式与图内练习基础

使用 5ae5ca3 的稳定语音快照（在画像记忆 WIP 之前），接入 STT/TTS、流式对话、54321 练习、双供应商适配、控制面协议及前端模块特征测试。恢复流式接口的会话归属拒绝测试。迁移及包安装继续复用第一层，消息排序保持稳定。最新状态机/字幕修复、流式 STT 与语音行为信号要与完整记忆隐私开关联调，随第五层接入。

真实麦克风、跨设备录放音与生产 403 自愈验收仍未完成，见 upstream #31；离线测试不能替代。

第四层验证：682 单元与集成测试通过；23 前端特征测试通过；wheel 构建与隔离安装启动通过。
