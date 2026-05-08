---
name: video_postprod_orchestrator
description: 后期编排Skill。将素材、配音、声音设计、调色、剪辑与发布准备串成专业后期流水线。当用户提到配音、剪辑、调色、混音、字幕、发布准备时应优先调用。
---

# video_postprod_orchestrator

## 技能描述
串联后期处理全链路，将原始素材转化为可交付的最终成片与发布包。后期处理分为四个子阶段：声音设计（D.1）、调色与特效（D.2）、剪辑（D.3）、自检（D.4），其中声音设计与调色可并行执行，剪辑在两者完成后串行进行。支持精准打回、失败降级和人工接管。

## 输入格式
```
projectName: string
projectId: string
traceId: string
assetList: object[]                       # Phase C 生成的原始素材列表
assetValidationReport: object             # Phase C 素材验真报告
  postprodReady: boolean
scriptSections: object[]                  # 来自前期包的脚本段落
storyboard: object                        # 来自前期包的分镜表（含 shots/globalStyleTag/bgmCues/sfxDescriptions）
characterCards: object[]                  # 来自前期包的角色卡
preprodPackage: object                    # 完整前期包（含 bgmPlan/emotionCurve/globalVisualStyle/characterVisualAnchors/subtitleHints）
editingTool: 剪映|其他
targetPlatform: string                    # 目标平台（douyin/bilibili/youtube/xiaohongshu/generic）
aspectRatio: string                       # 画面比例（默认从 targetPlatform 推断）
targetResolution: 720p|1080p
platforms: [抖音, 视频号]
publishMode: package_only|auto
autoPublish: boolean
brandAssets: object                       # 品牌资源（可选，含 logo/watermark/brandColors）
```

## 执行步骤

> **核心原则**：后期处理遵循"声音设计∥调色 → 剪辑 → 自检"的专业分工流程。声音设计与调色操作完全独立（音频 vs 视频），可并行执行以加速后期处理；剪辑在两者完成后组装最终成片。

### ═══════════════════════════════════════════════════
### 前置门检
### ═══════════════════════════════════════════════════

### Step 0: 验收门检查
- 仅当 `assetValidationReport.postprodReady=true` 时进入后期，否则返回 `E_ASSET_NOT_READY`。
- 验证前期包完整性：`preprodPackage` 中 `bgmPlan` / `globalVisualStyle` / `emotionCurve` / `subtitleHints` 必须存在。
- 验证素材列表与分镜 shots 一一对应（数量匹配）。

### ═══════════════════════════════════════════════════
### PHASE D.1: 声音设计（可与 D.2 并行）⚡
### ═══════════════════════════════════════════════════

### Step 1: 配音生成（D.1.1 — 串行，声音设计的前置依赖）
- **调用**：`jimeng_tts_dubber`
- **输入映射**：
  ```
  scriptSections    ← input.scriptSections
  voiceStyle        ← input.characterCards[role=narrator].voiceStyle 或从 input.preprodPackage 推断
  speed             ← 默认 1.0，可按 targetPlatform 微调
  emotion           ← input.preprodPackage.emotionCurve（影响 TTS 语气）
  outputDir         ← .claude/ai_videos/<projectId>/audio/dubbing/
  ```
- **输出**：`dubbingResult` — 含 audioFiles / timeline / subtitleSyncMap / subtitleDraftPath
- **校验**：配音覆盖所有 scriptSections、时长合理（与脚本 estSeconds 偏差 ≤ 20%）。
- **字幕数据源绑定**：从 `dubbingResult.subtitleSyncMap` 获取字幕同步映射，后续所有字幕生成必须严格基于此映射。

### Step 1.5: TTS语音旁白生成（D.1.1b — 依赖 Step 1 字幕时间轴）
- **工具**：`edge-tts`（优先）或 `gtts-cli`（备选）
- **输入映射**：
  ```
  subtitleSyncMap   ← Step1.dubbingResult.subtitleSyncMap（字幕文本+时间轴）
  voiceName         ← 根据内容类型自动选择（搞笑→zh-CN-YunxiNeural, 专业→zh-CN-YunyangNeural, 卡通→zh-CN-YunxiaNeural）
  rate              ← 根据内容类型自动调整（搞笑→"+15%", 叙事→"+0%", 教程→"-5%"）
  outputDir         ← .claude/ai_videos/<projectId>/audio/narration/
  ```
- **执行流程**：
  1. **逐句生成**：遍历 `subtitleSyncMap` 中每条字幕，调用 `edge-tts --voice <voiceName> --rate=<rate> --text "<text>" --write-media line_XX.mp3` 生成独立音频文件。可并行提交所有 edge-tts 任务加速生成。
  2. **时长检测与适配**：对每条旁白音频检测时长（`ffprobe`），若 `旁白时长 > 字幕窗口时长 × 1.05`，使用 ffmpeg `atempo` 滤镜加速适配（atempo 范围 0.5-2.0，超出需链式应用：如 2.5x = atempo=2.0,atempo=1.25）。
  3. **时间轴混合**：使用 ffmpeg `adelay` 按字幕起始时间偏移每条旁白，再用 `amix` 混合为单条旁白音轨 `narration_mixed.wav`。
  4. **输出校验**：旁白音轨总时长与视频总时长匹配（±1s），每条旁白在对应字幕窗口内播放完毕。
- **输出**：`narrationResult` — 含 narrationTrackPath / perLineFiles[] / tempoAdjustments[]
- **降级策略**：edge-tts 不可用时降级到 gtts-cli；均不可用时跳过旁白生成（标记 `narrationSkipped=true`），后续混音仅使用 BGM。
- **注意**：旁白是后期**必选**步骤（除非用户明确要求"无旁白/纯BGM"），让视频内容可听可看，大幅提升信息传达效率。

### Step 2: 声音设计与混音（D.1.2 — 依赖 Step 1 配音 + Step 1.5 旁白完成）
- **调用**：`sound_designer`
- **输入映射**：
  ```
  dubbingTrack      ← { path: Step1.audioFiles[0].path, durationSec: Step1.totalNarrationDurationSec }
  narrationTrack    ← { path: Step1.5.narrationResult.narrationTrackPath, durationSec: <旁白音轨时长> }（若 Step 1.5 跳过则为 null）
  dubbingTimeline   ← Step1.timeline
  subtitleSyncMap   ← Step1.subtitleSyncMap
  bgmPlan           ← input.preprodPackage.bgmPlan
  bgmCues           ← input.storyboard.shots[].bgmCue（聚合为列表）
  sfxDescriptions   ← input.storyboard.shots[].sfx（聚合为列表）
  emotionCurve      ← input.preprodPackage.emotionCurve 或 input.storyboard.emotionCurve
  targetPlatform    ← input.targetPlatform
  videoDuration     ← sum(input.assetList[].durationSec)
  shotDurations     ← input.assetList[].{ shotId, durationSec }
  mixPreset         ← 根据内容类型自动选择（narration → speech_priority, story → cinematic）
  ```
- **输出**：`soundResult` — 含 mixedMasterAudio / stems / soundMixMetadata / cueSheet / qcFlags
- **校验**：
  - 混音母带时长与视频素材总时长匹配（±500ms）。
  - 响度在平台 LoudnessTarget ±1 LUFS 范围内。
  - 无 critical qcFlags（如 clipping_detected）；有 warning 级别可继续但记录。

### ═══════════════════════════════════════════════════
### PHASE D.2: 调色与特效（可与 D.1 并行）⚡
### ═══════════════════════════════════════════════════

### Step 3: 调色与 VFX 合成（D.2 — 与 Step 1+2 并行启动）
- **调用**：`color_grader`
- **输入映射**：
  ```
  rawFootage        ← input.assetList[].{ shotId, path, durationSec, resolution }
  globalVisualStyle ← input.preprodPackage.globalVisualStyle
  emotionCurve      ← input.preprodPackage.emotionCurve
  shotDescriptions  ← input.storyboard.shots[].{ shotId, visualPrompt, emotionLabel, visualTone, lighting, setting }
  overlayInstructions ← input.storyboard.shots[].overlay（聚合为列表，过滤非空）
  speedEffects      ← 从 storyboard 或 constraints 中提取速度变更指令（如有）
  brandAssets       ← input.brandAssets
  targetPlatform    ← input.targetPlatform
  aspectRatio       ← input.aspectRatio
  coverFrameHint    ← input.storyboard.coverFrameHint 或从 emotionCurve 推断
  ```
- **输出**：`colorResult` — 含 gradedFootage[] / lutMetadata / vfxLayerDescriptions / continuityReport / updatedShotDurations / qcFlags
- **校验**：
  - 调色后素材数量 = 分镜 shot 数量。
  - `continuityReport.maxDeltaE` < 8（可接受的色彩连续性）。
  - 无 critical qcFlags（如 footage_corrupt）。
  - 若有速度变更，`updatedShotDurations` 非空。

### ═══════════════════════════════════════════════════
### 同步屏障：交叉校验音视频对齐
### ═══════════════════════════════════════════════════

### Step 4: D.1 + D.2 完成，交叉校验
- 等待 Step 2（声音设计）和 Step 3（调色）均完成。
- **时长对齐校验**：
  - 计算 `soundResult.mixedMasterAudio.durationSec` 与 `sum(colorResult.updatedShotDurations[].durationSec)` 的差值。
  - 若差值 ≤ 500ms → 可接受，由 video_editor 在精剪阶段微调。
  - 若 500ms < 差值 ≤ 1s → 标记 WARNING，video_editor 可处理。
  - 若差值 > 1s → 需要 `sound_designer` 基于 `updatedShotDurations` 重新混音（速度变更导致的时长变化）。
- **合并时间元数据**：生成统一的 `masterTimeline`，包含每个 shot 的视频时长、音频覆盖范围和字幕时间段。
- **异常处理**：若任一子阶段失败（Step 1/2/3），在此处汇总错误并决定是否可部分降级继续。

### ═══════════════════════════════════════════════════
### PHASE D.3: 剪辑（串行，依赖 D.1 + D.2 完成）
### ═══════════════════════════════════════════════════

### Step 5: 视频剪辑（D.3）
- **调用**：`video_editor`
- **输入映射**：
  ```
  gradedFootage     ← Step3.colorResult.gradedFootage
  mixedMasterAudio  ← Step2.soundResult.mixedMasterAudio
  soundCueSheet     ← Step2.soundResult.cueSheet
  soundMixMetadata  ← Step2.soundResult.soundMixMetadata
  vfxLayerDescriptions ← Step3.colorResult.vfxLayerDescriptions
  storyboard        ← input.storyboard
  subtitleSyncMap   ← Step1.dubbingResult.subtitleSyncMap
  shotDurations     ← Step3.colorResult.updatedShotDurations 或 input.assetList[].{ shotId, durationSec }
  targetPlatform    ← input.targetPlatform
  aspectRatio       ← input.aspectRatio
  targetResolution  ← input.targetResolution
  coverFrameHint    ← input.storyboard.coverFrameHint
  lutMetadata       ← Step3.colorResult.lutMetadata
  editingTool       ← input.editingTool
  outputDir         ← .claude/ai_videos/<projectId>/final/
  ```
- **输出**：`editResult` — 含 finalVideoPath / coverImagePath / subtitleFilePath / exportReport / editDecisionList / qcFlags
- **校验**：
  - 成片文件存在且可播放（`ffprobe` 可读）。
  - `exportReport.durationSec` 与预期偏差 ≤ 1s。
  - `exportReport.resolution` 匹配平台要求。
  - `exportReport.firstFrameValid == true`（非纯黑/纯色首帧）。
  - `exportReport.subtitleDubbingSync == aligned`（字幕与配音同步）。
  - 若前期包含标题 → `editResult` 中应包含标题叠加信息。

### ═══════════════════════════════════════════════════
### PHASE D.4: 自检（提交外部审核前的质量关卡）
### ═══════════════════════════════════════════════════

### Step 6: 自动质量检查
- 对最终成片执行全面自检：
  - ☐ **音视频同步**：抽检时间线 25%、50%、75% 处的字幕-配音对齐（偏差 ≤ 200ms）。
  - ☐ **字幕可读性**：验证无截断、无越界、安全区合规。
  - ☐ **封面质量**：封面图片清晰、无残影、分辨率匹配平台要求。
  - ☐ **色彩连续性**：检查 `colorResult.continuityReport` 无严重问题。
  - ☐ **声音混音**：验证配音清晰度（不被 BGM 遮蔽）、无削波。
  - ☐ **文件格式**：编码/分辨率/帧率/音频规格符合平台要求。
  - ☐ **时长范围**：在平台时长限制内。
  - ☐ **首帧有效**：非纯黑/纯色首帧。
  - ☐ **无意外静音**：无 > 2s 的静音段（除非刻意设计）。
  - ☐ **BGM 情绪匹配**：比对 BGM 情绪标签与前期包 `bgmPlan.bgmMood` 的一致性。
  - ☐ **首页标题**: 若前期包含标题，验证首镜头是否叠加标题文字。
  - ☐ **字幕边距实测**: 竖屏场景下验证字幕未溢出（FontSize/MarginV/MarginL/R 符合安全区参数）。
- 若自检不通过：
  - 识别失败原因对应的子 Skill。
  - 回退到对应 Step 并附带修复指令（最多内部重试 2 次 / 子 Skill）。
  - 记录自检失败历史。
- 若自检通过：编译最终交付物，准备提交外部审核。

### Step 7: 打包审核交付物
- 编译审核包：
  ```
  reviewPackage:
    finalVideoPath: <path>
    coverImagePath: <path>
    subtitleFilePath: <path>
    exportReport: { ... }
    soundMixMetadata: { ... }
    lutMetadata: { ... }
    editDecisionList: [ ... ]
    colorContinuityReport: { ... }
    soundQcFlags: [ ... ]
    selfQcReport: { passed: true|false, warnings: [...] }
  ```
- 输出后期结果，等待独立审核（Phase D.5 `review_agent`）。

### ═══════════════════════════════════════════════════
### 审核处理（Phase D.5 → D.6）
### ═══════════════════════════════════════════════════

### Step 8: 审核打回处理
- 若 `review_agent` 返回 `REJECTED`，根据 `redoActions` 精准路由到对应子 Skill：

| 打回指令 | 路由目标 | 重跑范围 | 说明 |
|---------|---------|---------|------|
| `REDO_DUBBING` | Step 1 → Step 1.5 → Step 2 → Step 5 | 重新配音→重新旁白→重新混音→重新剪辑 | 配音质量问题 |
| `REDO_NARRATION` | Step 1.5 → Step 2 → Step 5 | 重新TTS旁白→重新混音→重新剪辑 | 旁白语速/语调/时间轴问题 |
| `REDO_SOUND_MIX` | Step 2 → Step 5 | 仅重新混音→重新剪辑 | BGM/SFX/混音问题 |
| `REDO_COLOR_GRADE` | Step 3 → Step 5 | 重新调色→重新剪辑 | 色彩连续性/调色风格问题 |
| `REDO_VFX` | Step 3(VFX only) → Step 5 | 仅修复 VFX→重新剪辑 | VFX 叠加问题 |
| `REDO_EDITING` | Step 5 | 仅重新剪辑 | 节奏/转场/卡点问题 |
| `REDO_SUBTITLE` | Step 5(字幕通道) | 仅修复字幕轨 | 字幕安全区/同步问题 |
| `REDO_COVER` | Step 5(封面通道) | 仅重新抽帧封面 | 封面质量问题 |
| `REDO_AUDIO` | Step 2(响度) | 仅重做音频优化 | 响度/编码问题 |
| `REDO_FIRST_FRAME` | Step 5(首帧) | 重新执行首帧裁剪 | 首帧为黑帧/纯色 |
| `REDO_ALL` | Step 1 → 2 → 3 → 5 | 全后期重做 | 多维度严重问题 |
| `REDO_GENERATION` | ⬆ 上报 Phase C | 编排器无法修复 | 素材根本性问题 |
| `REDO_TITLE_OVERLAY` | Step 5(标题通道) | 仅添加首页标题 | 首页缺少标题叠加 |
| `REDO_SUBTITLE_LAYOUT` | Step 5(字幕通道) | 仅修复字幕安全区 | 字幕溢出画面 |

- 重做完成后重新执行 Step 6（自检）→ Step 7（打包）→ 再次提交审核。
- 重做历史记录在 `redoHistory` 中。

### Step 9: 用户确认等待（Phase D.6）
- 审核通过（APPROVED / APPROVED_WITH_WARNINGS / APPROVED_FORCE）后，向用户展示审核报告摘要，等待用户明确确认：
  - 展示内容：成片路径、8 维度评分（含新增的色彩连续性和声音混音质量）、综合得分、WARN 项、优化建议（APPROVED_FORCE 时附带风险提示）。
  - 用户可选择：
    - ✅ **确认发布**（`userConfirmed=true`）→ 继续执行 Step 10-11。
    - ✏️ **要求修改** → 根据用户反馈解析为 `redoActions`，回到 Step 8 的对应重做环节。
    - 📦 **仅保留发布包** → 执行 Step 10 生成发布包，但跳过 Step 11 的自动发布（`publishMode` 覆写为 `package_only`）。
  - 未收到用户确认前，禁止执行任何发布动作。

### ═══════════════════════════════════════════════════
### 发布与交付（Phase E → F）
### ═══════════════════════════════════════════════════

### Step 10: 发布包生成
- 用户确认后，调用 `cn_short_video_publisher` 生成发布包。
- 发布包包含：成片视频、封面图片、字幕文件、标题/标签/文案、平台元数据。

### Step 11: 自动发布（条件执行）
- 仅当 `autoPublish=true` 且 `publishMode=auto` 且 `userConfirmed=true` 时执行发布动作。
- 发布后写回结果。

## 通用资源关联
- 默认优先复用 `.claude/resources/douyin_video_common/auto_finalize_generic.sh` 进行自动收敛导出。
- 发布包结构默认对齐 `.claude/resources/douyin_video_common/publish_package.template.json`。

## 输出格式
```markdown
## 后期结果
- status: ok|error
- errorCode: E_NONE|E_ASSET_NOT_READY|E_ASSET_INVALID|E_DUBBING_FAILED|E_SOUND_MIX_FAILED|E_COLOR_GRADE_FAILED|E_EXPORT_FAILED|E_JIANYING_UNAVAILABLE|E_REVIEW_REJECTED|E_SYNC_BARRIER_FAILED
- summary: <string>                                        # 一句话总结
- finalVideoPath: <path>
- subtitlePath: <path>
- coverImagePath: <path>
- publishPackagePath: <path>
- editingToolUsed: 剪映|其他|通用导出
- publishResult: skipped|success|failed
- soundDesignResult:                                       # 声音设计结果摘要
    mixedMasterAudio: <path>
    stemsDir: <path>
    loudness_lufs: <number>
    mixPreset: <AudioMixPreset enum>
    bgmGenre: <string>
    sfxCount: <number>
- colorGradeResult:                                        # 调色结果摘要
    gradeStyle: <ColorGradeStyle enum>
    maxDeltaE: <number>
    vfxLayersApplied: <number>
    speedRampsApplied: <number>
    skinToneConsistent: true|false
- editResult:                                              # 剪辑结果摘要
    shotCount: <number>
    transitionCount: <number>
    editDecisionCount: <number>
    beatSyncPoints: <number>
    durationSec: <number>
- reviewResult:                                            # 审核结果摘要
    verdict: APPROVED|APPROVED_WITH_WARNINGS|REJECTED|APPROVED_FORCE
    reviewRound: <number>
    overallScore: <number>
    redoHistory: [<string>]
    userConfirmed: true|false|pending
- mediaValidation:
    hasVideo: true|false
    hasAudio: true|false
    audioCodec: <string>
    audioSampleRate: <number>
    audioChannels: <number>
    subtitleSafeArea: pass|failed
    firstFrameCheck: pass|black|uniform_color
    subtitleDubbingSync: aligned|drifted
    bgmEmotionMatch: pass|mismatch
    colorConsistency: pass|warn|fail
    soundMixQuality: pass|warn|fail
- parallelExecution:                                       # 并行执行信息
    d1Duration: <number>                                   #   D.1 声音设计总耗时（秒）
    d2Duration: <number>                                   #   D.2 调色总耗时（秒）
    d3Duration: <number>                                   #   D.3 剪辑总耗时（秒）
    parallelSaved: <number>                                #   并行节省的时长（秒）
- nextStep: 归档或人工发布
```

## 注意事项
- **并行执行**：Step 1+1.5+2（D.1 声音设计）和 Step 3（D.2 调色）可并行执行；但 Step 1 是 Step 1.5 和 Step 2 的前置依赖（配音先于旁白和混音），Step 1.5 是 Step 2 的前置依赖（旁白先于混音）。Step 5（D.3 剪辑）必须等待 D.1 和 D.2 全部完成。
- **同步屏障**：Step 4 是 D.1 和 D.2 之间的同步点，负责交叉校验音视频时长对齐，处理速度变更导致的时长漂移。
- **分工明确**：调色在 `color_grader` 完成，混音在 `sound_designer` 完成，`video_editor` 只负责组装和编辑——三者职责不交叉。
- **任一子 Skill 失败时**立即返回对应错误码，不做静默忽略；错误信息中需指明哪个子 Skill 失败及原因。
- **字幕唯一数据源**：字幕的唯一数据源是配音 `subtitleSyncMap`（来自 Step 1），禁止独立生成字幕时间轴或估算字幕文本。
- **TTS旁白是后期必选步骤**：除非用户明确要求"无旁白/纯BGM"，否则 Step 1.5 必须执行。旁白让视频可听可看，大幅提升信息传达和观看体验。旁白使用 `edge-tts` 工具，逐句生成并按字幕时间轴对齐混合。
- **旁白与BGM混音比例**：旁白为主轨（不衰减），BGM 音量压低至 15%-30%（`volume=0.15~0.3`），确保旁白清晰可辨不被 BGM 掩盖。
- **BGM 选取**必须参考前期包 `bgmPlan` 的情绪标签和风格建议，通过 `sound_designer` 执行。
- **审核与打回**：后期处理完成后必须等待 `review_agent` 独立审核通过后才可进入发布环节；审核打回时仅重做 `redoActions` 指定的环节，不全流程重跑。
- **用户确认门**：审核通过后必须等待用户明确确认（`userConfirmed=true`）才可执行发布。
- **发布时机**：发布包生成（Step 10）和自动发布（Step 11）必须在审核通过且用户确认之后执行。
- **降级策略**：
  - `edge-tts` TTS 旁白生成失败 → 降级到 `gtts-cli`；若均不可用，跳过旁白（`narrationSkipped=true`），仅保留 BGM + 字幕。
  - `sound_designer` BGM 生成失败 → 降级为仅配音/旁白 + 静态 BGM 背景（最基本可听版本）。
  - `color_grader` 调色失败 → 降级为使用原始素材跳过调色（确保可交付）。
  - `video_editor` 剪映不可用 → 降级到通用 ffmpeg 导出。
- **后期默认优先剪映**，若不可用则降级到通用导出并记录原因。
- 当 `publishMode=package_only` 时，无论 `autoPublish` 值如何都只输出发布包。
- **首帧有效画面**：终剪导出后首帧为黑帧/纯色帧时必须自动修复再交付。
- **stems 保留**：`sound_designer` 输出的分轨 stems 必须保留，审核打回时可单轨重做而非全部重新合成。
- **编辑决策追溯**：`video_editor` 的 `editDecisionList` 必须保留，审核时可追溯每个剪辑决策的原因。
