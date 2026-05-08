---
name: jimeng-video-generator
description: "即梦CLI素材生成Skill。统一处理文生视频与图生视频任务、参数探测、任务结果解析与重试恢复。用户提到即梦、文生视频、图生视频、生素材时必须触发。"
---

# jimeng_video_generator

## 技能描述
通过即梦 CLI 生成视频素材，包含命令探测与异常恢复。采用“先探测后执行”策略，减少命令变更风险。

## 输入格式
```
mode: text_to_video | image_to_video
shots: object[]
imageInputs: string[]
resolution: 720p|1080p
durationSec: 5|10|15
outputDir: string                         # 输出目录（默认 .qoder/ai_videos/<projectId>/assets/）
retryLimit: number
```

## 执行步骤
1. 安装检查：优先 `jm`，其次 `dreamina`，均缺失时返回 `E_CLI_NOT_FOUND`。
2. 帮助探测：执行 `<cli_cmd> -h`，提取可用子命令。
3. 运行时检查：若出现 `GLIBC_2.3x not found`，返回 `E_RUNTIME_INCOMPATIBLE`。
4. 登录检查：执行 `<cli_cmd> user_credit` 或等价状态命令，确认本地登录态。
5. 权限检查：若返回 `ret=3019` 或 `not vip user`，返回 `E_PERMISSION_DENIED`。
6. 根据 `mode` 动态匹配命令模板并执行生成；若 `image_to_video` 命中安全策略，必须提供“原创角色 text_to_video 回退方案”，保留目标风格但避免使用高风险参考图描述。
6.5. 并发策略：若项目含多个镜头（shots.length > 1），优先使用 VIP 模型（`seedance2.0fast_vip`）并行提交所有镜头（单批次上限 20 个任务），再并行轮询；若 VIP 不可用（余额不足或返回权限错误），回退为普通模型串行提交。
7. 提交验真：提交后必须立刻对返回结果做一致性检查。若出现“`submit_id` 存在，但 `gen_status=fail` / `fail_reason` 含 timeout”或首次 `query_result`/`list_task` 只返回 `gen_status=querying` 且没有 `queue_info`，判定为坏任务，必须重新提交新任务，旧 `submit_id` 不得继续用于 ETA 或下载。
8. 队列轮询：采用 `while true` 持续轮询并定期输出心跳（建议 10 分钟一次），同时维护 ETA 状态文件供人工查看与恢复执行。**多镜头并行模式下**，为每个 submit_id 启动独立后台轮询进程，使用 `wait` 统一等待全部完成；各进程独立下载并重命名素材文件。
9. 结果解析：下载 URL 必须支持多路径解析，优先 `result_json.videos[0].video_url`。
10. 素材验真：下载后执行完整性校验（文件大小>0、`ffprobe` 可读、时长>1s）；同时执行首帧有效性检测——抽取首帧图像计算像素方差，方差低于阈值（标准差 < 5）判定为纯黑/纯色帧，标记 `firstFrameCheck: black|uniform_color`；首帧无效时尝试用 `blackdetect` 自动裁剪至首个有效帧后重新校验。
11. 失败恢复：参数降级后重试一次；若文件损坏则强制重下。
12. 后期许可：仅当 `integrityCheck=pass` 且 `firstFrameCheck=valid` 且检测为真实视频片段（非占位）时，输出 `postprodReady=true`。

## 通用资源关联
- 默认复用 `.qoder/resources/douyin_video_common/poll_master_generic.sh` 执行持续轮询与下载。
- 需要 10 分钟心跳时，默认复用 `.qoder/resources/douyin_video_common/queue_report_10min_generic.sh`。
- 若资源目录脚本存在，不再在项目目录下临时重复生成同类脚本。

## 输出格式
```markdown
## 素材生成结果
- status: ok|error
- errorCode: E_NONE|E_AUTH|E_CLI_NOT_FOUND|E_RUNTIME_INCOMPATIBLE|E_PERMISSION_DENIED|E_CMD_UNSUPPORTED|E_GEN_TIMEOUT
- assets:
  - taskId: <string>
    outputPath: <string>
    durationSec: <number>
    resolution: <string>
    prompt: <string>
    queueStatus: <pending|running|done>
    integrityCheck: <pass|failed>
    firstFrameCheck: <valid|black|uniform_color>  # 首帧有效性检测结果
- retries: <number>
- recoverAdvice: <string>
- postprodReady: true|false
- postprodBlockReason: <string|null>
```

## 注意事项
- 不硬编码固定子命令，必须先解析 `<cli_cmd> -h`。
- `image_to_video` 缺图时直接返回 `E_ASSET_INVALID`。
- 参考图若为真人照片、平台敏感主体或高版权风险素材，应优先提示改写为原创角色设定，减少安全审核失败率。
- 权限不足时进入“非生成降级模式”，可执行 `.qoder/scripts/fallback_not_vip.sh` 生成交付模板。
- 不允许仅凭”任务成功”判定可用，必须通过本地素材校验后才可进入后期。
- 若素材未通过验真，必须显式阻断字幕/音频/封面优化，并返回阻断原因。
- 每个生成片段必须通过首帧检测，纯黑/纯色首帧不得进入后期链路；首帧无效时优先尝试 `blackdetect` 自动裁剪，裁剪失败再标记为 `postprodReady=false`。
- 生成提示词（prompt）中应包含前期包的 `globalVisualStyle` 和角色 `visualAppearance` 作为前缀，确保跨镜头视觉风格一致。
- 若提交返回 `submit_id` 但原始提交 JSON 同时记录了 `fail_reason=context deadline exceeded`，应优先判为“服务端可能已留任务、客户端提交已坏”的异常态，后续若缺少 `queue_info` 必须重提，不允许持续等待。
## 安全拦截处理（实战案例 game_cg_youth_5s，2026-04）
- 真人照片做 image_to_video 触发 `pre-TNS check did not pass`（防 deepfake），与 prompt 内容无关。
- **标准回退链路**：
  1. 检测到错误中含 `pre-TNS` 或 `content policy`
  2. 调用 `text2image`（model 5.0，cost 3 credits）生成动漫/赛博朋克风 AI 原创角色图
  3. 用生成的 AI 角色图重新执行 `image_to_video`（model 3.5pro，720p，cost 40 credits）
  4. 不得反复用相同真人图重试，会持续失败
- 回退时 prompt 必须去掉真实人物描述，改为原创角色风格描述（如"赛博朋克动漫女性角色，蓝色发丝，霓虹背景"）。