---
name: video_editor
description: 视频剪辑Skill。负责将调色素材和混音音频组装为成片，执行粗剪→精剪→终剪导出。用户提到剪辑、粗剪、精剪、转场、字幕、导出、卡点时应触发。
---

# video_editor

## 技能描述
专业非线性编辑 Skill。负责将调色后的素材（来自 `color_grader`）和混音音频（来自 `sound_designer`）组装为最终成片视频。实现粗剪→精剪→终剪导出的结构化编辑流程，管理多轨时间线（视频轨 + 叠加轨 + 音频轨 + 字幕轨）。本 Skill 是后期处理的最终组装环节，不做调色或混音——只做编辑与导出。

## 共享枚举引用
> 本 Skill 使用的枚举值定义于 `.claude/skills/_shared/enums.md`，包括 TransitionType、ShotType、VfxType、Emotion。

## 输入格式
```
gradedFootage: object[]                   # 来自 color_grader 的调色后素材
  - shotId: string
    path: string
    durationSec: number
    gradeStyle: <ColorGradeStyle enum>
mixedMasterAudio: object                  # 来自 sound_designer 的混音母带
  path: string
  durationSec: number
  format: string
soundCueSheet: object[]                   # 来自 sound_designer 的音频事件时间表
  - timeSec: number
    type: string                          #   bgm_start|bgm_stop|bgm_transition|sfx|duck_start|duck_end|beat_drop
    description: string
    shotId: string
soundMixMetadata: object                  # 来自 sound_designer 的混音元数据
vfxLayerDescriptions: object[]            # 来自 color_grader 的 VFX 层描述
storyboard: object                        # 来自前期包的分镜表
  shots: object[]                         #   镜头列表（含 transitionType、estSeconds 等）
  globalStyleTag: string
subtitleSyncMap: object[]                 # 来自 jimeng_tts_dubber 的字幕同步映射
  - sectionId: string
    text: string
    startMs: number
    endMs: number
    charCount: number
shotDurations: object[]                   # 来自 color_grader 的实际镜头时长（可能因速度变更而更新）
  - shotId: string
    durationSec: number
targetPlatform: string                    # 目标平台（douyin/bilibili/youtube/generic）
aspectRatio: string                       # 画面比例（9:16/16:9/1:1）
targetResolution: string                  # 目标分辨率（720p/1080p/4K）
coverFrameHint: object                    # 封面抽帧提示（可选）
  shotId: string
  timePct: number
lutMetadata: object                       # 来自 color_grader（可选，用于元数据嵌入）
editingTool: 剪映|其他                     # 编辑工具偏好
outputDir: string                         # 输出目录（默认 .claude/ai_videos/<projectId>/final/）
```

## 多轨时间线结构

```
V3: [叠加轨]     — 未烧入素材的 VFX 文字/图形（从 vfxLayerDescriptions 参考）
V2: [B-Roll 轨]  — 插入镜头/花絮素材（如有）
V1: [主视频轨]   — 调色后素材主序列
────────────────────────────────────────────────────
A1: [混音母带]   — 来自 sound_designer 的最终混音
A2: [字幕标记]   — 基于 subtitleSyncMap 的时间参考轨（无音频）
```

## 平台导出规格

| 平台 | 分辨率 | 编码 | 帧率 | 音频 | 比例 | 时长限制 |
|------|--------|------|------|------|------|---------|
| douyin | 1080×1920 | H.264 High | 30fps | AAC 48kHz stereo | 9:16 | 60s/180s/600s |
| bilibili | 1920×1080 | H.264 High | 30fps | AAC 48kHz stereo | 16:9 | ≤ 15min |
| youtube | 1920×1080 | H.264 High | 30fps | AAC 48kHz stereo | 16:9 | — |
| xiaohongshu | 1080×1920 | H.264 High | 30fps | AAC 48kHz stereo | 9:16/1:1 | 60s |
| generic | 1080p | H.264 High | 30fps | AAC 48kHz stereo | — | — |

## 字幕安全区规则

| 参数 | 竖屏 (9:16) | 横屏 (16:9) | 说明 |
|------|------------|------------|------|
| 单行最大 CJK 字数 | 14 | 22 | 超出自动断行 |
| 单行最大 Latin 字符 | 28 | 44 | 超出自动断行 |
| 最大宽度 | ≤ 画面宽度 90% | ≤ 画面宽度 90% | 左右留白 |
| 底部安全边距 | ≥ 36px | ≥ 36px | 避免平台 UI 遮挡 |
| 字幕区域 | 底部 10-15% | 底部 8-12% | 不与 VFX lower_third 重叠 |
| 抖音额外避让 | 顶部 15%（头像区）/ 底部 20%（交互栏） | — | 平台 UI 遮挡 |
| 推荐字号 | 14px (720p) / 20px (1080p) | 22px (1080p) | 过大字号易溢出边缘 |
| 左右安全边距 | ≥ 60px (720p) / ≥ 80px (1080p) | ≥ 40px | ASS MarginL/MarginR |
| 底部安全边距（ASS MarginV） | ≥ 180px (720p) / ≥ 250px (1080p) | ≥ 80px | 避免平台底栏遮挡 |

## 节奏模式规则

| 模式 | 每镜头时长 | 适用场景 | 情绪强度 |
|------|----------|---------|---------|
| 快剪 | 1-2s | 蒙太奇、快节奏段落 | intensity ≥ 0.7 |
| 标准 | 3-5s | 叙述、解说 | 0.3 < intensity < 0.7 |
| 慢切 | 5-8s | 情感段落、留白 | intensity ≤ 0.3 |
| 静止 | 8-15s | 特写、沉浸 | 刻意设计 |

## 执行步骤

### Step 1: 前置校验
- 验证所有 `gradedFootage` 文件存在且可播放（`ffprobe` 可读、时长 > 0）。
- 验证 `mixedMasterAudio` 文件存在且时长与 `sum(shotDurations[].durationSec)` 匹配（允许偏差 ±500ms）。
- 交叉检查 `soundCueSheet` 时间戳是否落在 `shotDurations` 累计时间线范围内。
- 检测音视频同步漂移：若整体漂移 > 200ms，标记 `sync_drift` 并以音频时间线为准（配音是时间主线）。
- 验证 `subtitleSyncMap` 的时间范围与混音母带时长一致。
- 若 `editingTool == 剪映`，检测剪映可用性；不可用则预设降级到通用导出。

### Step 2: 多轨时间线初始化
- 创建多轨时间线结构（V3/V2/V1/A1/A2）。
- 按分镜 `storyboard.shots[]` 顺序将 `gradedFootage` 加载到 V1 主视频轨。
- 将 `mixedMasterAudio` 加载到 A1 混音母带轨。
- 将 `subtitleSyncMap` 条目作为标记加载到 A2 字幕标记轨。
- 参考 `vfxLayerDescriptions` 标记 V3 叠加轨中的 VFX 元素位置。
- 设定时间线总长为 `mixedMasterAudio.durationSec`（音频为时间主线）。

### Step 3: 粗剪组装
- 按分镜顺序在 V1 轨上放置各 shot，应用分镜指定的 `transitionType`（引用 TransitionType 枚举）：
  - `cut`：硬切，0 帧重叠。
  - `dissolve`：交叉溶解，15-30 帧重叠。
  - `fade_to_black` / `fade_from_black`：15-20 帧。
  - `wipe` / `swipe_left` / `swipe_right`：20-30 帧。
  - `zoom_transition`：10-20 帧 + 缩放关键帧。
  - `match_cut`：内容匹配切，0 帧重叠但需确保构图连贯。
  - `j_cut`：下一 shot 音频提前 0.5-1s 开始（视频轨偏移）。
  - `l_cut`：当前 shot 音频延伸 0.5-1s 至下一 shot（视频轨偏移）。
  - `whip_pan`：5-10 帧极快水平扫过。
- 每个 transition 的持续时间从 `storyboard.shots[].transitionDuration` 读取，未指定时使用 TransitionType 默认值。
- 粗剪完成后验证关键同步点：
  - 配音词边界不应被 transition 切断（检查 `subtitleSyncMap` 与 transition 区间是否重叠）。
  - BGM beat_drop（来自 `soundCueSheet`）应与画面切点对齐（±2 帧 ≈ ±67ms @30fps）。
- 输出：可观看的粗剪版本，包含基础 transition。

### Step 4: 精剪 — 节奏与卡点
- **节奏审查与修正**：
  - 检查各 shot 实际播放时长与节奏模式规则的一致性（参考 `emotionCurve.intensity`）。
  - 过长（无配音/无视觉变化 > 3s 的段落）→ 裁剪至合理长度。
  - 过短（画面尚未被观众识别就已切走，< 1s）→ 延伸或与相邻 shot 合并。
  - transition 时机不当 → 调整重叠帧数 ±5 帧。
- **卡点剪辑（Beat-Sync Cutting）**：
  - 从 `soundCueSheet` 提取 `beat_drop` 和 `bgm_transition` 标记时间。
  - 将画面切点向最近的音乐节拍对齐（±1-3 帧微调）。
  - 对齐优先级：配音同步（最高）> BGM 卡点 > SFX 同步（最低）。
  - 若对齐 BGM 会破坏配音同步，放弃 BGM 卡点对齐。
- **L-cut / J-cut 精细应用**：
  - J-cut（下一段音频提前开始）：适用于场景转换、制造悬念，提前 0.5-1s。
  - L-cut（当前音频延伸至下一段画面）：适用于反应镜头、平滑过渡，延伸 0.5-1s。
  - 通过 V1 轨的 in/out 点偏移实现，A1 混音母带不做修改。
- **裁剪点优化**：
  - 进入镜头时：优先在运动开始处切入（不在静态画面切入）。
  - 离开镜头时：在动作完成前或自然停顿处切出（保持能量）。
- **所有编辑决策记录到 `editDecisionList`**：
  ```
  - shotId: <string>
    action: trimmed_start|trimmed_end|extended|beat_sync_shift|j_cut|l_cut|transition_adjust|merged
    frames: <number>                      # 调整帧数（正=延伸/后移，负=裁剪/前移）
    reason: <string>                      # 调整原因
  ```

### Step 5: 字幕轨道
- 严格基于 `subtitleSyncMap` 渲染字幕（字幕内容 = 配音口播文本，时间轴 = 配音时间轴；禁止独立估算）。
- 字幕样式：
  - 位置：按字幕安全区规则放置。
  - 字体：平台默认或品牌指定。
  - 背景：半透明黑色药丸底（透明度 60%）。
  - 动画：逐段淡入淡出（200ms），不使用复杂动画。
- 安全区强制校验：
  - 单行字数超限 → 自动断行。
  - 底部/侧边超出安全区 → 调整位置。
  - 与 VFX `lower_third` 层冲突 → 字幕上移避让。
  - 抖音平台：额外避让顶部 15% 和底部 20%。
- 输出字幕文件（SRT 格式）+ 烧入字幕（视平台需求）。
  - 抖音/小红书：烧入字幕（硬编码到视频）。
  - B 站：同时输出软字幕文件和烧入版本。

### Step 5.5: 首页标题叠加
- 若前期包指定了视频标题（`preprodPackage.title` 或 `storyboard.title`），必须在成片首镜头叠加标题文字。
- 叠加参数（竖屏 9:16 默认值）：
  - 位置：画面水平居中，垂直 40%-50% 区域
  - 字号：fontsize=56（720p）/ fontsize=80（1080p），根据标题长度自适应缩小
  - 颜色：白色文字 + 黑色描边（borderw=3）
  - 时间：0.5s 淡入，持续至 3.0-4.0s，0.5s 淡出（`enable='between(t,0.5,3.5)'` + alpha fade）
  - 字体：系统中文字体（优先 Noto Sans CJK / WenQuanYi）
- 标题不得与字幕重叠：标题在画面中上部，字幕在画面下部。
- ffmpeg 实现参考：`drawtext=text='标题':fontsize=56:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.42:enable='between(t,0.5,3.5)':alpha='if(lt(t,1),t-0.5,if(gt(t,3),3.5-t,1))'`

### Step 6: 封面抽帧
- 确定封面源：
  - 若 `coverFrameHint` 指定了 shotId → 从该调色 shot 中抽取。
  - 若 `coverFrameHint` 指定了 timePct → 在最终时间线的对应位置抽取。
  - 若无提示 → 从 `emotionCurve` 中 intensity 最高的 shot 抽取（取该 shot 的中间帧）。
- 封面质量要求：
  - 不在 transition 过渡中抽取（避免溶解/淡入淡出残影）。
  - 不含字幕叠加（clean frame）。
  - 不含运动模糊（选择运动最少的帧）。
  - 封面帧必须已经过调色（从 `gradedFootage` 抽取）。
- 按平台要求输出：
  - 抖音/小红书：1080×1920（9:16）。
  - B 站/YouTube：1920×1080（16:9）+ 1280×720 缩略图。
- 首帧有效性同步检查：检测最终视频首帧像素标准差，< 5 判定为无效（纯黑/纯色），自动裁剪至首个有效帧。

### Step 7: 终剪导出
- 按平台导出规格表渲染最终视频。
- 编码参数：
  - 视频：H.264 High Profile，CRF 18-23（质量优先），30fps。
  - 音频：直接复用 `mixedMasterAudio`（已归一化），不重新编码。
- 嵌入元数据：
  - 标题（来自前期包）。
  - 创建时间戳。
  - LUT 参考（来自 `lutMetadata`，如有）。
  - 音频混音参考（来自 `soundMixMetadata`，如有）。
- 若 `editingTool == 剪映`，优先使用剪映流程导出；导出失败时降级到通用导出（ffmpeg）并记录原因。
- 导出后验证：
  - 视频流可读（`ffprobe` 确认）。
  - 音频流存在。
  - 首帧非纯黑/纯色（像素标准差 ≥ 5）。
  - 总时长与预期偏差 ≤ 10%。
- 生成 `exportReport`。

## 通用资源关联
- 当使用通用导出链路时，优先复用 `.claude/resources/douyin_video_common/auto_finalize_generic.sh`。
- 若脚本参数可满足当前项目，不再生成重复的临时导出脚本。

## 输出格式
```markdown
## 剪辑结果
- status: ok|error
- errorCode: E_NONE|E_ASSET_NOT_READY|E_ASSET_INVALID|E_SYNC_DRIFT|E_EXPORT_FAILED|E_JIANYING_UNAVAILABLE
- finalVideoPath: <path>
- coverImagePath: <path>
- coverThumbnailPath: <path>              # 缩略图（如有）
- subtitleFilePath: <path>                # SRT/ASS 字幕文件
- editingToolUsed: 剪映|其他|通用导出
- exportReport:
    finalVideo: <path>
    coverImage: <path>
    subtitleFile: <path>
    durationSec: <number>
    resolution: <string>
    codec: <string>
    fps: <number>
    fileSize_mb: <number>
    shotCount: <number>
    transitionCount: <number>
    audioCodec: <string>
    audioSampleRate: <number>
    audioChannels: <number>
    firstFrameValid: true|false
    subtitleDubbingSync: aligned|drifted
- editDecisionList:
  - shotId: <string>
    action: <string>                      # trimmed_start|trimmed_end|extended|beat_sync_shift|j_cut|l_cut|transition_adjust|merged
    frames: <number>
    reason: <string>
- qcFlags: [<string>]                    # sync_drift|subtitle_overflow|cover_blur|first_frame_invalid|transition_artifact 等
- warnings: [<string>]
```

## 注意事项
- **接收预处理输入**：本 Skill 不做调色（由 `color_grader` 完成）或混音（由 `sound_designer` 完成），只负责组装和编辑导出。不引用原始素材或配音文件。
- **音频是时间主线**：当音视频同步存在疑虑时，以 `mixedMasterAudio` 时间线为准。配音时间是规范的时间参考。
- **所有编辑决策记录**：每次裁剪、位移、调整都必须记录到 `editDecisionList`，供审核阶段追溯和打回修复参考。
- **粗剪→精剪是迭代过程**：精剪内部可能循环 2-3 次才能满意，但最终只输出一个版本。
- **不尝试修复根本性问题**：若调色素材或混音音频存在根本性质量问题，标记 qcFlags 并上报至编排器——不要在编辑阶段硬修。
- **字幕安全是硬约束**：字幕定位必须考虑平台特定的 UI 遮挡区域，这是必须遵守的硬约束而非建议。
- **字幕唯一数据源**：字幕内容和时间轴严格来自 `subtitleSyncMap`，禁止独立生成或估算。
- **封面从调色素材抽取**：封面必须从已调色的 `gradedFootage` 中抽取，确保封面色调与正片一致。
- **首帧有效画面**：终剪导出后必须检测首帧有效性，纯黑/纯色首帧需自动裁剪至首个有效帧再导出。
- **BGM 剪辑点对齐**：通过 `soundCueSheet` 中的 `beat_drop` 标记实现 BGM 与画面的卡点对齐，确保音乐节奏与视觉节奏同步。
- **默认优先剪映**：若用户指定剪映，优先使用剪映流程；不可用时降级到通用导出（ffmpeg）并在输出中记录降级原因。
- **首页标题叠加是默认行为**：若前期包含标题信息，终剪必须在首镜头叠加标题文字（drawtext），不得遗漏。
- **竖屏字幕参数实测值**：720p 竖屏推荐 FontSize=14、MarginV≥180、MarginL/R≥60；1080p 竖屏推荐 FontSize=20、MarginV≥250、MarginL/R≥80。过大字号或不足边距会导致字幕溢出画面。
