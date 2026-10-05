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

验证：555 后端单元与集成测试通过；归属与迁移 11 项复验通过。隔离 wheel 启动通过，fork CI 的测试和容器任务均通过。

## 第三层：产品前端

只同步 b7202bc 的静态前端、图标与 manifest，对应第二层已有的认证、练习、评估分页、打卡与个人记录 API；不引入语音或画像记忆实现。源码及隔离 wheel 的页面/静态资源启动验证与后端 CI 共同保障接口兼容。

## 第四层：语音、流式与图内练习基础

使用 5ae5ca3 的稳定语音快照（在画像记忆 WIP 之前），接入 STT/TTS、流式对话、54321 练习、双供应商适配、控制面协议及前端模块特征测试。恢复流式接口的会话归属拒绝测试。迁移及包安装继续复用第一层，消息排序保持稳定。最新状态机/字幕修复、流式 STT 与语音行为信号要与完整记忆隐私开关联调，随第五层接入。

真实麦克风、跨设备录放音与生产 403 自愈验收仍未完成，见 upstream #31；离线测试不能替代。

第四层验证：682 单元与集成测试通过；23 前端特征测试通过；wheel 构建与隔离安装启动通过。

## 第五层：Psy 记忆与完整交付集成

恢复原 #30 最终源快照 0b64c5c 的 Psy 画像、记忆演进、智能调度、质询确认、隐私同意/删除与后台清理、上下文切片联动及连续性修复。相关流式 STT、TTS 轮次守卫、字幕同步及行为信号一起交付，保证前端、画像同意开关及后端协议一致。来源历史和协作者贡献继续保存在 #30；此层包含已进入 Echo-Smith 交付历史的协作代码，不替代或关闭其他作者独立 PR。

保留 main 的构建与编排入口，调整 1Panel 打包脚本为包内迁移，并统一 main 的 8000 端口、锁定 PyPI 依赖及数据卷。部署包仅含环境模板，不包含真实密钥、数据库、Mirror 或本地未跟踪内容。旧审计文件使用旧锁文件指纹，不复制为当前交付的证明。

尚未完成：upstream #31 语音真机验收；#32 真实模型长期回放/每周 gate 运行日志。未进行生产部署或真实供应商评测。

完整 schema 检查发现旧版本链漏建 plan_enrollments；应用的 create_all 一直在启动时掩盖该缺口。新增末尾补齐迁移，既支持纯 Alembic 空库升级，也保留已由旧 create_all 创建的计划记录。回滚保留该表，避免删除早于本版本的用户数据。含百分号数据库 URL 及全部 ORM 表/列检查纳入迁移回归。

真实回复 eval runner 依赖 LLM API Key，原先在无凭据时以降级模板参与语义/结构验收会产生误判（首轮 7 个案例失败）；现与 judge 一样明确列为需配置凭据的 slow 验收。离线 CI 不把这些未运行项记为成功；保留 #32 的真实模型验收要求。

最终验证：1128 后端测试通过；2 项真实模型验收因无凭据跳过；3 个既有语义检索缺口按 strict xfail 保留；32 前端测试通过。完整 src/tests Ruff 检查通过。wheel 及 1Panel 包的隔离启动、全部 ORM 表/列迁移、旧计划记录保留与百分号 URL 回归通过。默认 Compose 也透传 .env，使身份、语音及记忆配置与 server 入口一致。
