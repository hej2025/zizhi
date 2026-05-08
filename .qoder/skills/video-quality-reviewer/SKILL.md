---
name: video-quality-reviewer
description: "成片质量审核Skill。在后期处理完成后、发布之前，对成片进行全维度质量审核，核对素材与成片的一致性、字幕配音匹配度等。审核不通过时输出打回指令与修复建议。当用户提到审核、质检、核对、校验成片时应触发。"
---

# video_quality_reviewer

## 技能描述
对后期处理输出的成片进行独立质量审核，逐项核对前期策划（脚本/分镜/人设）与最终成片的一致性，确保字幕、配音、BGM、画面等各维度达标后才允许进入发布环节。审核不通过时生成结构化的打回指令，指明具体问题和修复方向，由后期编排重新调整。

## 输入格式
```
projectId: string
traceId: string
finalVideoPath: string                  # 成片视频路径
subtitlePath: string                    # 字幕文件路径（SRT/LRC）
audioFiles: object[]                    # 配音音频文件列表
preprodPackage:                         # 前期包（作为核对基准）
  scriptSections: object[]              #   脚本段落
  storyboard: object[]                  #   分镜表
  characterCards: object[]              #   角色卡
  globalVisualStyle: string             #   全局画风描述
  characterVisualAnchors: object[]      #   角色视觉锚点
  bgmPlan: object                       #   BGM 规划
postprodResult:                         # 后期处理结果
  mediaValidation: object               #   后期自检报告
  subtitleSyncMap: object[]             #   字幕-配音同步映射
  editSummary: object                   #   剪辑摘要
coverImagePath: string                  # 封面图路径
maxRetries: number                      # 最大打回重试次数（默认 2）
```

## 审核维度与评分规则

### 1. 字幕-配音一致性 (权重: 关键)
- **文本一致性**: 逐段比对字幕文本与配音口播文本（来源 `subtitleSyncMap`），计算字符匹配率
  - PASS: 匹配率 ≥ 95%
  - WARN: 匹配率 80%-95%（允许通过但标记）
  - FAIL: 匹配率 < 80%
- **时间轴同步**: 比对字幕起止时间与配音起止时间的偏差
  - PASS: 平均偏差 ≤ 200ms 且最大偏差 ≤ 500ms
  - FAIL: 平均偏差 > 200ms 或任一段偏差 > 500ms
- **打回指令**: `REDO_SUBTITLE` — 从 `subtitleSyncMap` 重新生成字幕轨

### 2. 字幕画面安全性 (权重: 关键)
- **安全区检测**: 字幕是否超出画面可视范围
  - 底部安全边距 ≥ 36px
  - 单行宽度 ≤ 画面宽度 90%
  - 单行字数: 1080p ≤ 16字, 720p ≤ 12字
  - 竖屏 720p: FontSize ≤ 14, MarginV ≥ 180, MarginL/R ≥ 60
  - 竖屏 1080p: FontSize ≤ 20, MarginV ≥ 250, MarginL/R ≥ 80
- **可读性检测**: 字幕字号是否可读、对比度是否足够
  - PASS: 所有帧字幕均在安全区内
  - FAIL: 存在字幕越界帧
- **打回指令**: `REDO_SUBTITLE_LAYOUT` — 重新调整字幕安全区与断行

### 3. 首帧与画面质量 (权重: 关键)
- **首帧检测**: 视频首帧是否为纯黑/纯色
  - 抽取首帧计算像素标准差，标准差 < 5 判定为无效
  - PASS: 首帧标准差 ≥ 5（有真实画面）
  - FAIL: 首帧标准差 < 5（纯黑/纯色）
- **首页标题检测**: 若前期包含标题，检测首镜头 0.5-4s 区间是否存在标题文字叠加
  - PASS: 标题存在且位置居中、未超出画面
  - WARN: 标题存在但位置偏移或部分遮挡
  - FAIL: 前期包含标题但成片首页无标题叠加
- **封面质量**: 封面是否从有效帧抽取
  - PASS: 封面非纯黑/纯色，分辨率匹配目标比例
  - FAIL: 封面为黑帧或占位图
- **打回指令**: `REDO_FIRST_FRAME` — 裁剪黑帧开头; `REDO_COVER` — 从 30%-50% 位置重新抽帧; `REDO_TITLE_OVERLAY` — 在首镜头添加标题 drawtext

### 4. 素材-分镜一致性 (权重: 重要)
- **镜头数量**: 成片实际镜头数与分镜表 `shots` 数量比对
  - PASS: 偏差 ≤ 1 个镜头
  - WARN: 偏差 2 个镜头（标记但可通过）
  - FAIL: 偏差 > 2 个镜头
- **时长覆盖**: 成片总时长与脚本预期总时长比对
  - PASS: 偏差 ≤ 10%
  - WARN: 偏差 10%-20%
  - FAIL: 偏差 > 20%
- **画风一致性**: 抽取各镜头关键帧，检测色调/风格是否与 `globalVisualStyle` 一致
  - PASS: 无明显画风跳变
  - WARN: 存在轻微色调偏差
  - FAIL: 存在动漫/实拍等风格混杂
- **打回指令**: `REDO_GENERATION` — 对不一致镜头注入 globalVisualStyle 后重新生成

### 5. BGM 匹配度 (权重: 重要)
- **情绪一致性**: BGM 情绪标签与前期包 `bgmPlan.bgmMood` 比对
  - PASS: BGM 情绪与场景情绪一致
  - WARN: 部分段落 BGM 情绪偏差（如 warm 场景用了 tense BGM）
  - FAIL: BGM 情绪与场景严重不匹配
- **节奏对齐**: BGM 切点是否与分镜 `bgmCue` 对齐
  - PASS: 切点偏差 ≤ 1s
  - FAIL: 切点偏差 > 2s 或缺少切点
- **打回指令**: `REDO_BGM` — 根据 bgmPlan 重新选取/对齐 BGM

### 6. 音频质量 (权重: 标准)
- **编码规范**: 音频流是否为 AAC 48kHz stereo
  - PASS: 匹配
  - WARN: 不匹配但可播放（如 44.1kHz）
  - FAIL: 无音频流
- **响度**: 音频响度是否归一
  - PASS: 响度在标准范围
  - WARN: 轻微偏差
- **打回指令**: `REDO_AUDIO` — 重新执行音频优化

### 7. 色彩连续性 (权重: 重要)
- **镜头间色彩一致性**: 相邻 shot 的色彩过渡是否自然
  - 对比 `color_grader` 输出的 `continuityReport`，检查 maxDeltaE
  - PASS: maxDeltaE < 5，所有过渡自然流畅
  - WARN: 5 ≤ maxDeltaE < 8，轻微色彩跳变但不影响观感
  - FAIL: maxDeltaE ≥ 8，明显色彩不一致
- **调色风格一致性**: 调色是否与 `globalVisualStyle` 和 `ColorGradeStyle` 一致
  - PASS: 调色风格统一，与前期包画风描述匹配
  - WARN: 个别 shot 调色偏差但整体可接受
  - FAIL: 出现风格混杂（如部分 shot 暖调、部分冷调且非刻意设计）
- **肤色稳定性**: 若画面含人物，肤色是否跨 shot 一致
  - PASS: 肤色一致
  - WARN: 轻微肤色偏移
  - FAIL: 明显肤色不一致（如同一角色在不同 shot 中肤色差异明显）
- **打回指令**: `REDO_COLOR_GRADE` — 重新执行调色；具体标记 `continuity_break`（连续性断裂）、`grade_style_mismatch`（风格不匹配）、`skin_tone_drift`（肤色漂移）、`overgraded`（过度调色）、`undergraded`（调色不足）

### 8. 声音混音质量 (权重: 重要)
- **配音清晰度**: 配音是否在所有段落中清晰可闻，不被 BGM/SFX 遮蔽
  - PASS: 配音始终清晰，BGM 适当支撑
  - WARN: 1-2 处配音略被 BGM 遮蔽
  - FAIL: 多处配音被 BGM/SFX 严重遮蔽
- **SFX 时间对齐**: 音效是否与画面动作同步
  - PASS: 所有 SFX 与画面动作精确同步
  - WARN: 个别 SFX 偏移但不影响观感
  - FAIL: 多处 SFX 明显错位或缺失
- **削波检测**: 音频是否存在削波（clipping）
  - PASS: 无削波
  - FAIL: 检测到削波
- **响度达标**: 混音母带响度是否达到平台 LoudnessTarget
  - PASS: 响度在目标 ±1 LUFS
  - WARN: 响度偏差 1-2 LUFS
  - FAIL: 响度偏差 > 2 LUFS
- **BGM 情绪与节奏**: BGM 情绪标签是否与场景匹配、节奏是否与剪辑卡点对齐
  - PASS: 情绪匹配、节奏对齐
  - WARN: 部分段落 BGM 情绪偏差或节奏未卡点
  - FAIL: BGM 情绪严重不匹配
- **打回指令**: `REDO_SOUND_MIX` — 重新执行声音设计/混音；具体标记 `dubbing_masked`（配音被遮蔽）、`bgm_too_loud`（BGM 过响）、`bgm_too_quiet`（BGM 过弱）、`sfx_mistimed`（SFX 错位）、`sfx_missing`（SFX 缺失）、`clipping_detected`（削波）、`loudness_off_target`（响度偏离）、`silence_gap`（意外静音）

## 执行步骤

1. **输入完整性校验**: 确认所有必需输入存在（成片、字幕、配音、前期包、后期结果）；缺失时返回 `E_REVIEW_INPUT_MISSING`。
2. **技术指标提取**: 使用 `ffprobe` 提取成片的视频流/音频流参数、总时长、分辨率；抽取首帧和多个关键帧。
3. **逐维度审核**: 按上述 8 个维度逐一审核，每个维度输出 `PASS` / `WARN` / `FAIL` 及具体数据。
4. **综合判定**:
   - **APPROVED**: 所有关键维度 PASS，重要维度无 FAIL → 允许进入发布。
   - **APPROVED_WITH_WARNINGS**: 存在 WARN 但无 FAIL → 允许发布，附带优化建议。
   - **REJECTED**: 任一关键维度 FAIL，或 2 个以上重要维度 FAIL → 打回重新处理。
5. **打回指令生成**: 当 REJECTED 时，汇总所有 FAIL 维度的修复指令列表（`redoActions`），指明具体需要重做的环节和原因。
6. **重试计数**: 记录当前审核轮次（`reviewRound`），超过 `maxRetries` 时标记为 `APPROVED_FORCE`（强制通过并附带风险提示），避免无限循环。
7. **用户确认提示生成**: 当 verdict 为 APPROVED / APPROVED_WITH_WARNINGS / APPROVED_FORCE 时，生成结构化的用户确认提示（`userConfirmationPrompt`），包含审核报告摘要和用户可选操作，设置 `awaitingUserConfirmation=true`，阻断发布直到用户明确确认。

## 输出格式
```markdown
## 审核结果
- status: ok|error
- errorCode: E_NONE|E_REVIEW_INPUT_MISSING
- reviewRound: <number>                      # 当前审核轮次（从 1 开始）
- verdict: APPROVED|APPROVED_WITH_WARNINGS|REJECTED|APPROVED_FORCE
- overallScore: <number>                     # 综合评分 0-100
- dimensions:
  - name: subtitle_dubbing_sync              # 字幕-配音一致性
    result: PASS|WARN|FAIL
    textMatchRate: <number>                  # 文本匹配率 (0-100%)
    avgTimeDriftMs: <number>                 # 平均时间偏差 (ms)
    maxTimeDriftMs: <number>                 # 最大时间偏差 (ms)
    details: <string>
  - name: subtitle_safe_area                 # 字幕画面安全性
    result: PASS|WARN|FAIL
    outOfBoundsFrames: <number>              # 越界帧数
    details: <string>
  - name: first_frame_quality                # 首帧与画面质量
    result: PASS|WARN|FAIL
    firstFrameStdDev: <number>               # 首帧像素标准差
    coverValid: true|false
    details: <string>
  - name: storyboard_consistency             # 素材-分镜一致性
    result: PASS|WARN|FAIL
    shotCountDelta: <number>                 # 镜头数偏差
    durationDeltaPct: <number>               # 时长偏差百分比
    styleCoherence: pass|warn|fail
    details: <string>
  - name: bgm_match                          # BGM 匹配度
    result: PASS|WARN|FAIL
    emotionAlignment: pass|warn|fail
    cuePointDriftMs: <number>                # 切点偏差 (ms)
    details: <string>
  - name: audio_quality                      # 音频质量
    result: PASS|WARN|FAIL
    codec: <string>
    sampleRate: <number>
    channels: <number>
    details: <string>
  - name: color_continuity                   # 色彩连续性
    result: PASS|WARN|FAIL
    maxDeltaE: <number>                      # 最大色差值
    gradeStyleMatch: pass|warn|fail          # 调色风格一致性
    skinToneConsistent: pass|warn|fail       # 肤色稳定性
    details: <string>
  - name: sound_mix_quality                  # 声音混音质量
    result: PASS|WARN|FAIL
    dubbingClarity: pass|warn|fail           # 配音清晰度
    sfxAlignment: pass|warn|fail             # SFX 时间对齐
    clippingDetected: true|false             # 削波检测
    loudnessLufs: <number>                   # 实际响度
    loudnessOnTarget: pass|warn|fail         # 响度达标
    details: <string>
- redoActions:                               # 仅 REJECTED 时非空
  - action: REDO_SUBTITLE|REDO_SUBTITLE_LAYOUT|REDO_FIRST_FRAME|REDO_COVER|REDO_TITLE_OVERLAY|REDO_GENERATION|REDO_BGM|REDO_AUDIO|REDO_COLOR_GRADE|REDO_VFX|REDO_SOUND_MIX|REDO_EDITING|REDO_DUBBING|REDO_ALL
    reason: <string>                         # 打回原因
    targetPhase: postprod|generation         # 需要回退到哪个阶段
    severity: critical|important             # 严重程度
    fixHint: <string>                        # 修复建议
- warnings: [<string>]                       # WARN 项的优化建议
- summary: <string>                          # 一句话审核总结
- nextStep: 进入发布|打回后期处理|打回素材生成|强制通过（附风险提示）
- userConfirmation:                          # 用户确认相关（审核通过时生成）
  - awaitingUserConfirmation: true|false     # 是否等待用户确认
  - userConfirmed: true|false|pending        # 用户确认状态
  - userConfirmationPrompt:                  # 展示给用户的确认提示
    - finalVideoPath: <string>               #   成片路径
    - overallScore: <number>                 #   综合得分
    - dimensionSummary:                      #   各维度评分摘要
      - name: <string>
        result: PASS|WARN|FAIL
        score: <number>
    - warnItems: [<string>]                  #   WARN 项列表
    - riskItems: [<string>]                  #   风险提示（APPROVED_FORCE 时非空）
    - optimizationSuggestions: [<string>]    #   优化建议
    - userOptions:                           #   用户可选操作
      - confirmPublish: "确认发布"           #     进入自动发布
      - requestChanges: "修改后重新审核"     #     指定修改内容后打回
      - packageOnly: "仅保留发布包"          #     跳过自动发布
```

## 注意事项
- 审核是独立环节，不依赖后期处理的自检结果（`mediaValidation`），而是独立执行检测，但会参考自检结果作为辅助。
- 所有技术检测（ffprobe、像素分析等）必须基于实际文件执行，不接受上游传递的数值声明。
- 打回时 `redoActions` 必须精确到具体动作（如 `REDO_SUBTITLE` 而非笼统的"重做后期"），避免不必要的全流程重跑。
- `maxRetries` 默认为 2（即最多打回 2 次），第 3 次审核若仍不通过则 `APPROVED_FORCE` 强制放行，附带完整风险报告。
- 审核不阻断前后文沉淀：即使 REJECTED，前期包和当前成片仍保留，供人工参考。
- 打回到素材生成阶段（`targetPhase: generation`）的成本远高于打回到后期（`targetPhase: postprod`），审核报告应明确区分。
- 若后期自检（`mediaValidation`）已报告某维度 FAIL，审核应优先复核该维度。
- **用户确认机制**: 审核通过后（APPROVED/APPROVED_WITH_WARNINGS/APPROVED_FORCE）必须生成 `userConfirmationPrompt`，向用户展示审核报告摘要并提供三个选项（确认发布 / 修改后重新审核 / 仅保留发布包）；在用户响应前 `awaitingUserConfirmation=true`，禁止任何发布动作。
- `userConfirmationPrompt` 必须包含足够的信息供用户做出判断，至少包含：成片路径、综合得分、各维度评分、WARN 项、优化建议；APPROVED_FORCE 时还需包含风险提示。
