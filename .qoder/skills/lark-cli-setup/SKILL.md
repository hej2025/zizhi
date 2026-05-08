---
name: lark-cli-setup
description: "lark-cli 安装与配置：环境检测、npm 全局安装、skills 部署、应用配置、首次验证。当用户需要部署 lark-cli 开发环境、配置飞书应用、或排查初始化问题时使用。"
---

# lark-cli-setup — CLI 安装与配置

## 功能概述

完整覆盖 lark-cli 从零到一的部署流程：
1. **环境检测**：验证 Node/npm 版本
2. **全局安装**：`npm install -g @larksuite/cli`
3. **Skills 部署**：`npx skills add https://github.com/larksuite/cli`
4. **应用配置**：`lark-cli config init` 与应用信息录入
5. **首次验证**：version/help/config 命令检查
6. **身份策略**：优先应用身份（tenant_access_token），其次用户身份（user_access_token）

## 身份优先级策略（新增）

执行飞书能力时固定遵循：

1. **第一优先级：应用身份（bot / tenant_access_token）**
  - 命令形式：`--as bot`
  - 适用：创建文档、基础读写、应用级资源操作
  - 优点：无需等待用户交互授权、稳定

2. **第二优先级：用户身份（user / user_access_token）**
  - 命令形式：`--as user`（或默认 user）
  - 仅在 bot 身份无法满足场景时启用
  - 例如：用户私有资源、按发送者检索消息等

3. **切换条件**
  - 若 `--as bot` 成功：直接使用结果
  - 若 `--as bot` 报权限/身份限制：再检查 user 的 scope 并补授权

## 使用场景

- **首次部署**：全新机器安装 lark-cli
- **环境修复**：CLI 命令不可用，需要重新初始化
- **应用切换**：需要更换 App ID / App Secret
- **多机同步**：在新机器快速复制现有配置

## 前置要求

- **Node.js** >= 16.0.0（建议 >=18.0.0）
- **npm** >= 8.0.0
- **网络连接**：npm 仓库和 GitHub 可访问

## 使用步骤

### 步骤 A：环境检测

```bash
node --version
npm --version
which lark-cli  # 检查是否已安装
```

**预期输出**：
```
v18.x.x        # Node 版本
8.x.x          # npm 版本
（无输出 或 /usr/local/bin/lark-cli）
```

**处理**：
- 如果 Node 版本 <16：需要升级 Node（建议使用 nvm）
- 如果 npm 版本 <8：`npm install -g npm@latest`
- 如果已有 lark-cli：跳到步骤 D 应用配置

### 步骤 B：全局安装 lark-cli

```bash
npm install -g @larksuite/cli
```

**预期输出**：
```
added X packages in Xs
```

**常见问题**：
- **EACCES permission denied**：权限不足，解决方案：
  ```bash
  npm config set prefix ~/.npm-global
  export PATH=~/.npm-global/bin:$PATH
  npm install -g @larksuite/cli  # 重试
  ```
- **网络超时**：更换 npm 源
  ```bash
  npm config set registry https://registry.npmmirror.com
  npm install -g @larksuite/cli
  ```

### 步骤 C：部署 Skills

```bash
npx skills add https://github.com/larksuite/cli -y -g
```

**预期输出**：
```
✓ Downloading skills...
✓ Installing skills...
Successfully added XXX skills
```

**验证 skills 已装**：
```bash
lark-cli docs --help      # 验证 docs skill
lark-cli sheets --help    # 验证 sheets skill
```

### 步骤 D：应用配置

使用以下应用信息进行配置：

```
App ID：cli_a9239a380f799bce
App Secret：H3ObWWYUUJYJcKqToz2sxfMPhzShGfaM
```

发起配置流程：

```bash
lark-cli config init --new
```

按照提示：
1. Enter App ID → 粘贴 `cli_a9239a380f799bce`
2. Enter App Secret → 粘贴 `H3ObWWYUUJYJcKqToz2sxfMPhzShGfaM`
3. 确认后配置文件自动保存到 `~/.config/lark/config.json`

**验证配置**：
```bash
lark-cli config show
```

预期输出：
```json
{
  "appId": "cli_a9239a380f799bce",
  "appSecret": "H3ObWWYUUJYJcKqToz2sxfMPhzShGfaM",
  ...
}
```

### 步骤 E：首次验证

验证 CLI 整体就绪状态：

```bash
lark-cli --version
lark-cli help
lark-cli auth status
```

**预期输出**：
```
@larksuite/cli/X.X.X

Usage: lark-cli [options] [command] ...

[identity: bot]  # 或 [identity: user]
```

**下一步**：如需用户身份操作，执行 `lark-cli auth login` 完成用户授权。

### 步骤 F：授权预检查（关键）

在调用任何飞书能力前，先执行授权预检查，避免长时间等待后才发现缺权限：

```bash
lark-cli auth status
```

检查点：
1. 先判断是否可用 `--as bot`（tenant_access_token）直接完成目标操作
2. 若必须使用 user，再确认 `identity` 为 `user`
3. `tokenStatus` 应为 `valid`
4. `scope` 中包含目标操作需要的权限

常见能力与必需 scope 示例：

| 能力 | 最小 scope |
|------|------------|
| 文档搜索 (`docs +search`) | `search:docs:read` |
| 创建任务 (`task +create`) | `task:task:write` |
| 查询我的任务 (`task +get-my-tasks`) | `task:task:read` |

身份选择建议：

| 场景 | 首选身份 | 失败后兜底 |
|------|----------|------------|
| 创建飞书文档 | bot | user |
| 文档全文检索 | bot（若支持） | user + `search:docs:read` |
| 按发送者检索消息 | user | 需 `search:message` |
| 任务创建/查询 | user | 需 `task:task:write/read` |

若缺少 scope，直接补授权：

```bash
# 文档搜索
lark-cli auth login --scope "search:docs:read"

# 任务读写
lark-cli auth login --scope "task:task:read task:task:write"
```

补授权后再次执行 `lark-cli auth status`，确认 scope 已生效再继续执行目标命令。

可复用的一键预检查脚本：

```bash
#!/bin/bash
set -e

echo "== lark-cli 授权预检查 =="
STATUS=$(lark-cli auth status)
echo "$STATUS"

SCOPES=$(echo "$STATUS" | sed -n 's/.*"scope": "\(.*\)".*/\1/p')
# 可选场景: docs | sheets | task | all
SCENARIO="task"

case "$SCENARIO" in
  docs)
    REQUIRED=("search:docs:read")
    ;;
  sheets)
    REQUIRED=("sheets:spreadsheet:create" "sheets:spreadsheet:read" "sheets:spreadsheet:write_only")
    ;;
  task)
    REQUIRED=("task:task:read" "task:task:write")
    ;;
  all)
    REQUIRED=(
      "search:docs:read"
      "sheets:spreadsheet:create" "sheets:spreadsheet:read" "sheets:spreadsheet:write_only"
      "task:task:read" "task:task:write"
    )
    ;;
  *)
    echo "[ERR] 不支持的场景: $SCENARIO"
    exit 1
    ;;
esac

MISSING=()

for s in "${REQUIRED[@]}"; do
  if echo "$SCOPES" | tr ' ' '\n' | grep -qx "$s"; then
    echo "[OK] 已授予 $s"
  else
    echo "[MISS] 缺少 $s"
    MISSING+=("$s")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  SCOPE_STR="${MISSING[*]}"
  echo "建议执行: lark-cli auth login --scope \"$SCOPE_STR\""
  exit 2
fi

echo "[PASS] 当前场景权限齐备，可继续执行能力命令。"
```

## 配置文件位置

配置文件存放位置：

| 平台 | 路径 |
|------|------|
| macOS / Linux | `~/.config/lark/config.json` |
| Windows | `%APPDATA%\lark\config.json` |

**手动编辑配置**可以直接修改该文件。

## 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `command not found: lark-cli` | CLI 未安装或 PATH 不含 npm bin 目录 | 重新 `npm install -g` 或检查 PATH |
| `npm ERR! code EACCES` | npm 全局安装无权限 | 使用 `npm config set prefix` 改为用户目录 |
| `skills add` 失败 | 网络问题或 GitHub 不可达 | 检查网络，或更换 npm 源 |
| `lark-cli config show` 为空 | 配置尚未初始化 | 运行 `lark-cli config init --new` |
| `[identity: bot]` 但需要 user 操作 | 当前身份是 bot，某些操作需要 user 身份 | 运行 `lark-cli auth login` 获得 user 权限 |

## 知识库集成

成功部署后，下一步建议：
1. 运行 `@lark_cli_manager auth` 完成用户认证
2. 运行 `@lark_cli_manager auth_check` 做能力前鉴权预检查
3. 运行 `@lark_cli_manager create_guide` 生成个人使用手册
