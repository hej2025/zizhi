---
name: lark-cli-usage-guide
description: "lark-cli 快速索引与命令速查：根据操作类型快速判断身份、路由到专门的 Skill（lark-doc/lark-sheets/lark-task/lark-calendar/lark-im/lark-base/lark-shared）。当用户需要了解哪些能力可用、如何快速找到正确工具时使用。"
---

# lark-cli-usage-guide — 使用场景指南

## 典型使用场景速查

| 场景 | 核心命令 | 相关 Skill | 典型用途 |
|------|---------|----------|---------|
| **文档管理** | `lark-cli docs` | lark-doc | 创建/编辑/搜索云文档 |
| **电子表格** | `lark-cli sheets` | lark-sheets | 读写表格数据、追加行数据 |
| **任务清单** | `lark-cli task` | lark-task | 创建待办、跟踪任务进度 |
| **日程管理** | `lark-cli calendar` | lark-calendar | 查看日程、查询忙闲、预约 |
| **群聊通讯** | `lark-cli im` | lark-im | 发送消息、管理群组 |
| **多维表格** | `lark-cli bitable` | lark-base | 创建/查询多维表格 |
| **权限认证** | `lark-cli auth` | lark-shared | 登录授权、身份切换 |

## 快速指南

使用 lark-cli 时遵循以下步骤：

1. **先选身份策略：bot 优先，user 次之**
  - 默认优先 `--as bot`（tenant_access_token）执行
  - 仅当 bot 无法满足时，才切换 user（user_access_token）

2. **再检查授权状态**：`lark-cli auth status`
  - 若要用 user：应显示 `[identity: user]`
  - `tokenStatus` 应为 `valid`

3. **按操作检查 user scope（仅在需要 user 时）**
  - 文档搜索：`search:docs:read`
  - 任务创建：`task:task:write`
  - 任务查询：`task:task:read`
  - 如果缺少 scope，先执行 `lark-cli auth login --scope "..."`
  - 如授权后 scope 仍未出现，停止重试并提示用户去开发者后台开通权限/可用范围

4. **选择正确 Skill**：根据具体操作使用对应 Skill
   - 文档操作 → `@lark-doc skill`
   - 表格操作 → `@lark-sheets skill`  
   - 任务管理 → `@lark-task skill`
   - 日程管理 → `@lark-calendar skill`
   - 群聊通讯 → `@lark-im skill`
   - 多维表格 → `@lark-base skill`
   - 权限问题 → `@lark-shared skill`

5. **常用命令速查**：

| 操作类型 | 命令 | 说明 |
|---------|------|------|
| 查看帮助 | `lark-cli help` | 查看所有可用命令 |
| 查看身份 | `lark-cli auth status` | 确认当前身份（user/bot） |
| 登录授权 | `lark-cli auth login` | 完成用户授权 |
| 文档创建 | `lark-cli docs --help` | 默认先用 `--as bot` |
| 表格操作 | `lark-cli sheets --help` | 查看表格命令 |
| 任务管理 | `lark-cli task --help` | 查看任务命令 |
| 日程查看 | `lark-cli calendar --help` | 查看日程命令 |
| 消息发送 | `lark-cli im --help` | 查看群聊命令 |
| 配置查看 | `lark-cli config show` | 查看当前应用配置 |

## 鉴权失败快速处理

1. 缺权限时优先看报错中的 `missing_scope`。
2. 按报错执行最小化补授权命令，不做无意义轮询。
3. 补授权后只重试一次：
  - 成功则继续
  - 仍失败则转开发者后台检查：权限是否开通、应用是否发布、用户是否在可用范围

## 快速查询表

### 命令速查

```bash
# 帮助
lark-cli help

# 配置
lark-cli config show
lark-cli config set <key> <value>

# 认证
lark-cli auth login
lark-cli auth status
lark-cli auth logout

# 文档
lark-cli docs +create --as bot --title "标题" --markdown "内容"
lark-cli docs +search --query "搜索词"

# 表格
lark-cli sheets +create --as bot --title "表格" --headers '["列1","列2"]'
lark-cli sheets +append --as bot --url "<表格链接>" --rows '[["v1","v2"]]'

# 任务
lark-cli task +create --as user --summary "任务"
lark-cli task +get-my-tasks --as user

# 日程
lark-cli calendar +agenda --as user
lark-cli calendar +freebusy --as user --user-ids "ou_xxx,ou_yyy"

# 消息
lark-cli im +messages-send --as bot --chat-id "oc_xxx" --text "消息"
lark-cli im +chat-create --as bot --name "群名"

# 权限
lark-cli auth status
```

## 下一步

- 关注官方文档更新：https://github.com/larksuite/cli
- 保存常用命令到本地脚本库
- 定期备份重要数据
- 贡献你的最佳实践场景
