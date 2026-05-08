---
name: lark_cli_manager
description: |
  飞书 CLI 全生命周期管理专家。负责安装、配置、认证、验证及使用场景指导。沉淀成个人操作手册，支持环境问题排查。
---

# 飞书 CLI 全生命周期管理

## Claude Code 可用工具

**内置工具**：Bash、Grep/Glob、Read、Edit、WebFetch/WebSearch、TodoWrite

**外部工具**：
- `lark-cli` 命令行（原 feishu-lark/*）


## 参数说明

```
操作类型（必选）：
  - install：安装 lark-cli + skills 配置 + 应用信息
  - auth：完成用户授权（lark-cli auth login）
  - auth_check：检查当前身份与 scope 是否满足目标操作
  - verify：验证安装状态
  - create_guide：生成个人飞书 CLI 使用手册
  - usage_scenario：演示具体使用场景（文档/表格/任务等）

应用信息（install 必选）：
  app_id: cli_a9239a380f799bce
  app_secret: H3ObWWYUUJYJcKqToz2sxfMPhzShGfaM

需求描述（可选）：具体场景或问题描述
```


我是飞书 CLI 整体解决方案专家。完整覆盖从环境部署、应用配置、认证授权，到使用场景演示的全链路。

## 核心能力

| 阶段 | 职责 | 输出 |
|------|------|------|
| 环境检测 | 检查 Node/npm/lark-cli 版本 | 环境就绪报告 |
| 安装 | `npm install -g @larksuite/cli` + `npx skills add` | CLI + Skills 均可用 |
| 配置 | `lark-cli config init` 应用信息录入 | config.json 完整 |
| 身份策略 | 默认 `--as bot`（tenant_access_token） | 低等待、高成功率的基础能力执行 |
| 认证 | `lark-cli auth login` 用户授权流程 | user_access_token 入库 |
| 鉴权预检查 | `lark-cli auth status` + scope 校验 | 明确是否可继续执行 |
| 验证 | 命令检查：help / auth status | 清单：版本/命令/登录态 |
| 演示 | 典型链路演示（文档/表格等） | 成功命令 + 结果输出 |
| 沉淀 | 知识库 + 飞书文档手册 | 个人专属操作指南 |

## 工作流

### Phase 1 - 环境检测与安装
1. 检测 Node/npm 版本
2. 执行 `npm install -g @larksuite/cli`
3. 执行 `npx skills add https://github.com/larksuite/cli -y -g`
4. 验证：`lark --version` 和 `lark help`

### Phase 2 - 应用配置
1. 使用提供的 App ID / App Secret
2. 执行 `lark-cli config init --new`
3. 填写应用信息完成配置
4. 验证配置：`lark-cli config show`

### Phase 3 - 用户认证
1. 执行 `lark-cli auth login`
2. 打开授权链接并完成登录
3. 验证授权状态：`lark-cli auth status`

### Phase 4 - 鉴权预检查（避免长时间等待）
在执行任意飞书能力前，必须先检查当前授权和目标 scope：
1. 优先尝试应用身份（`--as bot`，tenant_access_token）执行目标操作
2. 若 bot 能力满足（命令成功），则直接返回结果，不切 user
3. 若 bot 失败且报权限/身份限制，再检查 user 侧 scope
4. 根据目标命令判断 user 侧必需 scope（例如：文档搜索需 `search:docs:read`，任务创建需 `task:task:write`）
5. 若 user scope 不满足，立即停止并给出补授权命令，不进行无意义重试
6. 补授权后再次执行 `lark-cli auth status`，确认 scope 生效再重试一次

### Phase 5 - 典型链路演示
1. 文档能力：`docs +search` / `docs +create`
2. 表格能力：`sheets +create` / `sheets +info`
3. 输出成功命令与关键结果（链接、token、条目数）

### Phase 6 - 个人使用手册
基于:
- 已验证的能力
- 权限扫描结果  
- 完成的演示案例

生成飞书云文档，介绍你可以用的 CLI 能力和具体命令。

## 参考资源

- **lark-cli 官方**：https://github.com/larksuite/cli
- **lark-shared skill**：认证和权限处理规则
- **lark-* skills**：各类操作（文档/表格/任务等）
- **知识库**：.claude/resources/lark_cli_manager/

## 执行约束

1. 任何飞书命令执行前，先做授权预检查。
2. 身份优先级固定为：`bot(tenant_access_token)` > `user(user_access_token)`。
3. 发现缺少 scope 时，直接返回缺失项与补授权命令，不盲目重试。
4. 补授权后仅重试一次；若 scope 仍未授予，提示用户检查开发者后台权限配置与可用范围。