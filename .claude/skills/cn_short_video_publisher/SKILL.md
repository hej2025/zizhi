---
name: cn_short_video_publisher
description: 中文短视频发布Skill。负责抖音/视频号发布包组装，并在授权时执行可选发布。用户提到发布、上架、标题标签、封面文案时应触发。
---

# cn_short_video_publisher

## 技能描述
生成平台发布包并支持可选自动发布，默认模式为“仅生成发布包”。

## 输入格式
```
platforms: [抖音, 视频号]
finalVideoPath: string
subtitlePath: string
titleCandidates: string[]
tagCandidates: string[]
coverCopyCandidates: string[]
publishMode: package_only|auto
autoPublish: boolean
userConfirmed: boolean                    # 用户确认状态（必须为 true 才允许自动发布）
reviewVerdict: string                     # 审核结论（APPROVED/APPROVED_WITH_WARNINGS/APPROVED_FORCE）
```

## 执行步骤
1. 前置检查：仅接收“真实素材验真通过”后的最终成片与封面；若为占位素材返回 `E_ASSET_NOT_READY`。
2. 生成平台字段映射（标题、话题、简介、封面文案）。
3. 组装统一发布包 json。
4. 若 `autoPublish=true` 且 `publishMode=auto` 且 `userConfirmed=true`，执行平台发布动作并记录结果。
  - **用户确认门控**：若 `userConfirmed != true`，即使 `autoPublish=true`，也仅生成发布包，返回 `publishResult=skipped` 并在 `manualGuide` 中说明"用户未确认，已跳过自动发布"。
  - 自动发布必须包含“验证码握手”：检测到验证码时暂停，等待人工完成后继续。
  - 自动发布必须复用持久登录态目录，避免每次发布重复登录。
  - 自动发布前必须将发布包中的视频路径与封面路径规范化为绝对路径；Selenium 文件上传对相对路径会直接报错 `path is not absolute`。
  - 若出现短信验证码/刷脸验证，进入等待态后恢复执行，不得直接返回成功或失败。
  - 若点击发布后落回草稿/继续编辑页，必须接管草稿并继续发布。
5. 输出发布摘要和人工发布说明。

## 通用资源关联
- 自动发布默认复用 `.claude/resources/douyin_video_common/douyin_auto_publish.py`。
- 发布包默认对齐 `.claude/resources/douyin_video_common/publish_package.template.json`。
- 验证码等待与登录态复用策略，以公共脚本实现为准，避免各项目重复维护。
- 发布包若同时包含 `video.mainFile` / `cover.optimized` 结构与旧的 `finalVideoPath` / `coverImagePath` 结构，自动发布前都必须统一转换为绝对路径并做存在性校验。

## 输出格式
```markdown
## 发布结果
- status: ok|error
- errorCode: E_NONE|E_ASSET_NOT_READY|E_PLATFORM_AUTH_REQUIRED|E_PUBLISH_FAILED|E_USER_NOT_CONFIRMED
- publishPackagePath: <path>
- platformPayloads:
  - platform: 抖音|视频号
    title: <string>
    tags: [<string>]
    coverCopy: <string>
- publishResult: skipped|success|failed
- manualGuide: <string>
- publishEvidence:
  - screenshotPath: <path>
  - htmlSnapshotPath: <path>
  - detectedStatus: <已发布|待审核|未知>
```

## 注意事项
- 默认 `autoPublish=false`。
- **用户确认是自动发布的强制前提**：`userConfirmed=true` 是执行自动发布的必要条件，缺失时只生成发布包，不执行发布。
- 发布失败不影响交付，必须保留可人工发布的完整包。
- 默认 `publishMode=package_only`，建议首期仅输出发布包。
- 当自动发布返回 success 时，仍需执行一次状态核验（作品管理页是否出现“已发布/待审核”）。
- 若状态核验失败，返回 `E_PUBLISH_UNVERIFIED`，并保留证据快照供人工确认。
- 自动发布脚本应优先复用持久化 profile 副本而不是每轮临时复制 profile，否则容易重复触发扫码与刷脸。
- 抖音上传页实际可见“发布视频”按钮时，应优先显式点击该按钮再注入文件，不要仅依赖拖拽区或页面文本误判为已进入编辑态。
