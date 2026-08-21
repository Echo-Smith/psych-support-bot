# GitHub 仓库配置指南

> 一次性配置，配完就不用再管了。由 repo owner（`redmaplewww`）操作。

---

## 1. 创建 `dev` 分支

本地已创建，只需推送（网络恢复后执行）：

```bash
git push origin dev
```

或者在 GitHub 网页上直接创建：`main` 分支旁点击下拉 → 输入 `dev` → Create branch。

---

## 2. 分支保护规则

进入 `Settings → Branches → Add branch protection rule`。

### `main` 分支规则

| 规则 | 设置 |
|------|------|
| Require a pull request before merging | ✅ 开启 |
| └ Required number of approvals | **1** |
| └ Dismiss stale pull request approvals when new commits are pushed | ✅ 开启 |
| └ Require review from Code Owners | ⬜（暂不需要） |
| Require status checks to pass before merging | ✅ 开启 |
| └ Require branches to be up to date before merging | ✅ 开启 |
| └ Status checks: `Lint & Format`, `Tests (Python 3.12)`, `Secret Leak Scan` | 全部勾选 |
| Do not allow bypassing the above settings | ✅ 开启 |

### `dev` 分支规则

| 规则 | 设置 |
|------|------|
| Require a pull request before merging | ✅ 开启 |
| └ Required number of approvals | **1** |
| Require status checks to pass before merging | ✅ 开启 |
| └ Status checks: `Lint & Format`, `Tests (Python 3.12)` | 勾选 |
| Do not allow bypassing the above settings | ⬜（dev 可放宽，允许管理员绕过） |

---

## 3. Actions Secrets

进入 `Settings → Secrets and variables → Actions`。

| Secret 名 | 用途 | 值 |
|-----------|------|-----|
| `OPENAI_API_KEY` | CI 中的 LLM 集成测试 | 小红书 dots3 API Key |
| `OPENAI_BASE_URL` | CI 中的 LLM 接口地址 | `https://note3-prev-api.askdiandian.com/v1` |
| `OPENAI_MODEL` | CI 中的模型名 | `dots3-note-prev` |
| `LANGFUSE_PUBLIC_KEY` | CI trace 上报（可选） | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | CI trace 上报（可选） | Langfuse secret key |
| `LANGFUSE_HOST` | CI trace 上报（可选） | `https://us.cloud.langfuse.com` |

> ⚠️ `OPENAI_API_KEY` 不要放在 `.env` 文件里提交，只通过 Secrets 注入。

---

## 4. 通用仓库设置

进入 `Settings → General`：

| 设置 | 推荐值 |
|------|--------|
| Default branch | `main` |
| Allow merge commits | ⬜ 关闭 |
| Allow squash merging | ✅ 开启（推荐 squash） |
| Allow rebase merging | ⬜ 关闭 |
| Automatically delete head branches | ✅ 开启 |
| Allow pull request editing by maintainers | ✅ 开启（方便互改） |

---

## 5. 协作流程速查

### 日常开发

```bash
# 首次 setup
make setup

# 开始新功能
git checkout dev && git pull origin dev
git checkout -b feat/your-feature

# 写代码...
make lint && make test

# 提交
git add . && git commit -m "feat(scope): 描述"
git push origin feat/your-feature

# GitHub 上创建 PR: feat/your-feature → dev
# 等 CI 全绿 + review 通过 → squash merge
```

### 发布到 main

```bash
# dev 测试无误后，创建 PR: dev → main
# review 通过 → squash merge → main 始终保持可发布状态
```

### 两人分工建议

| 领域 | 负责 |
|------|------|
| AI 工作流、质询机制、安全规则 | 深入 AI 逻辑的一方 |
| 基础设施、可观测性、CI/CD、前端 | 基建方 |
| 共同关注 | 数据库迁移、安全 eval cases、PR 互审 |

---

## 6. 网络问题排查

如果 `git push` 出现 `SSL_ERROR_SYSCALL`：

```bash
# 检查是否需要代理
git config --global http.proxy http://127.0.0.1:7890  # 换成你的代理端口
git config --global https.proxy http://127.0.0.1:7890

# 或切换为 SSH 协议
git remote set-url origin git@github.com:redmaplewww/psych-support-bot.git

# 测试连接
ssh -T git@github.com
```
