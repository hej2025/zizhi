---
name: video-preprod-orchestrator
description: "前期策划编排Skill。用于把脚本、剧情、人设、分镜整合成可执行的短视频前期包。当用户提到脚本策划、分镜设计、人物设定、剧情结构时必须调用。"
---

# video_preprod_orchestrator

## 技能描述
统一调度前期四个核心 Skill（story_designer → script_writer + character_designer → storyboard_designer），输出标准化前期包，供素材生成阶段直接消费。包含显式的子 Skill 输入映射、并行执行标识、交叉校验规则和质量报告。

## 输入格式
```
projectName: string                   # 项目名称
theme: string                         # 视频主题
audience: string                      # 目标受众描述（传递给 story_designer/script_writer）
style: string                         # 风格
durationSec: number                   # 目标时长（秒）
language: 中文|英文                    # 语言
platform: string                      # 目标平台（douyin/bilibili/xiaohongshu 等，可选）
genre: <Genre enum>                   # 题材类型（传递给 story_designer，可选）
aspectRatio: string                   # 画面比例（默认从 platform 推断，如 douyin → 9:16）
constraints: object[]                 # 约束列表，每项含 { type: string, value: string }
rerunFrom: string                     # 部分重跑起点（可选：story/script/character/storyboard/validate_only）
previousOutput: object                # 上一轮前期包缓存（部分重跑时使用，可选）
```

## 执行步骤

> **核心原则**：先写剧本（脚本），再基于脚本结构化剧情和人设，最后将脚本转化为可执行的分镜表。脚本是一切创作的源头。

### Step 1: 脚本创作（串行 — 创作源头）
- **调用**：`script_writer`
- **说明**：脚本是整个前期策划的起点，后续的剧情结构、人设设计和分镜拆分都基于脚本展开。
- **输入映射**：
  ```
  theme            ← input.theme
  audience         ← input.audience
  style            ← input.style
  durationSec      ← input.durationSec
  language         ← input.language
  platform         ← input.platform
  forbiddenTerms   ← input.constraints[].where(type == "forbidden_term").value
  platformSensitiveTerms ← input.constraints[].where(type == "platform_sensitive").value
  ```
- **输出**：`script` — 含 sections[]（每段含 text/charCount/estSeconds/emotionLabel/beat/speakerIds 等）

### Step 2: 并行执行 ⚡（剧情结构化 + 人设设计，基于脚本，互不依赖）

#### Step 2a: 剧情结构化（可与 2b 并行）
- **调用**：`story_designer`
- **说明**：将脚本的叙事结构化为剧情 beats、冲突线和情绪曲线，使脚本具备可拍摄的结构骨架。
- **输入映射**：
  ```
  theme            ← input.theme
  genre            ← input.genre（若空则默认 "story"）
  style            ← input.style
  durationSec      ← input.durationSec
  audience         ← { ageRange: 从 input.audience 推断, interests: [], knowledgeLevel: "intermediate" }
  platform         ← input.platform
  scriptSections   ← Step1.script.sections[]
  ```
- **输出**：`storyPlan` — 含 beats[]（与 script sections 对齐）、emotionCurve、structureType

#### Step 2b: 人设设计（可与 2a 并行）
- **调用**：`character_designer`
- **说明**：从脚本中提取角色信息，为每个角色生成结构化的人设卡，供分镜和素材生成消费。
- **输入映射**：
  ```
  theme            ← input.theme
  audience         ← input.audience
  style            ← input.style
  durationSec      ← input.durationSec
  genre            ← input.genre
  scriptSections   ← Step1.script.sections[]
  speakerIds       ← Step1.script.sections[].speakerIds（聚合去重）
  rolesCount       ← input.constraints[].where(type == "max_characters").value 或由 durationSec 自动推断
  ```
- **输出**：`characterPlan` — 含 characterCards[]、relations[]

### Step 3: 分镜设计（串行 — 将脚本转化为可执行镜头表，依赖 Step 1 + 2a + 2b 全部完成）
- **调用**：`storyboard_designer`
- **说明**：基于脚本内容、剧情结构和角色人设，将脚本逐段转化为可执行的镜头表。这是"文字→画面"的关键转化步骤。
- **输入映射**：
  ```
  scriptSections   ← Step1.script.sections[]
  storyBeats       ← Step2a.storyPlan.beats[]
  characterCards   ← Step2b.characterPlan.characterCards[]
  durationSec      ← input.durationSec
  platform         ← input.platform
  aspectRatio      ← input.aspectRatio 或从 platform 推断
  ```
- **输出**：`storyboard` — 含 shots[]、globalStyleTag、shotFallbackPlan

### Step 4: 交叉校验 + 合并（质量门禁）
- 合并所有子 Skill 输出后，执行交叉校验规则（详见下方章节）
- 校验不通过的项记录到 `qualityReport`

### Step 5: 生成衍生数据与后期约束
- 合并 `globalVisualStyle`、`characterVisualAnchors`、`bgmPlan`
- 生成 `timingBudget`、`subtitleHints`、`shotFallbackPlan`
- 生成 `qualityReport`（前期质量评分）

## 交叉校验规则（Step 4 详情）

合并所有子 Skill 输出后，逐项校验。每条规则产出 `pass` / `warn` / `fail`：

### 4.1 时长一致性
- `|sum(shots.estSeconds) - durationSec| ≤ durationSec × 0.05`
- 否则 **FAIL**，要求 storyboard_designer 调整镜头时长分配

### 4.2 角色覆盖
- `storyboard.shots[].characterIds` 的并集 ⊆ `characterPlan.characterCards[].id`
  - 否则 **FAIL**（分镜引用了不存在的角色）
- `characterCards` 中 `role ≠ cameo` 的角色必须在至少 1 个 shot 中出现
  - 否则 **WARN**（设计了但没用到的角色）

### 4.3 台词完整性
- `script.sections[].text` 中的所有对白句必须在某个 `shot.line.text` 中出现
  - 否则 **WARN**（脚本台词在分镜中丢失）

### 4.4 情绪连贯性
- 同一 `beatId` 下：`story.beat.emotionLabel` ≈ `script.section.emotionLabel` ≈ `shot.emotionLabel`
  - 允许 shot 级别有细粒度变化，但整体方向必须一致
  - 不一致时 **WARN**

### 4.5 BGM 信息合并与冲突解决
- BGM 信息可能来自三个来源：`script.sections[].bgmMood` / `story.beats[].bgmStyle` / `input.constraints[type=="bgm"]`
- 冲突解决优先级：`input.constraints > story.bgmStyle > script.bgmMood`
- 合并为唯一的 `bgmPlan`，标记最终采用的来源

## constraints[] 消费规范

| constraint.type | 消费方 | 传递方式 |
|----------------|--------|---------|
| `forbidden_term` | script_writer | 注入 `forbiddenTerms[]` |
| `platform_sensitive` | script_writer | 注入 `platformSensitiveTerms[]` |
| `bgm` | orchestrator BGM 合并 | 直接合并到 `bgmPlan` |
| `aspect_ratio` | storyboard_designer | 注入 `aspectRatio` |
| `max_characters` | character_designer | 注入 `rolesCount` |
| `style_reference` | storyboard_designer | 注入 `visualPrompt` 前缀 |
| `brand_color` | character_designer | 注入 `colorScheme` 约束 |

- 未被消费的 constraint 必须出现在 `warnings[]` 中：`"constraint '{type}' was not consumed by any sub-skill"`

## 部分重跑（Partial Re-run）

当 `input.rerunFrom` 存在时，跳过已完成的步骤，使用 `input.previousOutput` 缓存数据：

| rerunFrom | 跳过 | 重新执行 | 适用场景 |
|-----------|------|---------|---------|
| `script` | 无 | Step 1 → 2 → 3 → 4 → 5 | 脚本需要调整（全流程重跑） |
| `story` | Step 1 | Step 2a → 3 → 4 → 5 | 仅剧情结构需要调整 |
| `character` | Step 1 | Step 2b → 3 → 4 → 5 | 仅人设需要调整 |
| `storyboard` | Step 1, 2 | Step 3 → 4 → 5 | 仅分镜需要调整 |
| `validate_only` | Step 1, 2, 3 | Step 4 → 5 | 仅重新校验 |

- 跳过的步骤使用 `input.previousOutput.{planName}` 的缓存数据
- 部分重跑时 `version` 递增（如 "1.0" → "1.1"）

## 通用资源关联
- 产出字段必须可直接供 `.qoder/resources/douyin_video_common/` 脚本链路消费（特别是时长预算与字幕断句建议）。
- 前期包需包含 `projectName` 对应的标准目录约定，便于后续轮询、收敛、发布脚本复用。

## 输出格式
```markdown
## 前期包
- status: ok|error
- errorCode: E_NONE|E_INPUT_INVALID|E_SUBSTEP_FAILED|E_CROSS_VALIDATION_FAILED
- summary: <一句话总结>
- preprodPackage:
  - scriptSections: [...]                      # 来自 script_writer（含 charCount/estSeconds/emotionLabel/speakerIds 等）
  - storyBeats: [...]                          # 来自 story_designer（含 estSeconds/emotionLabel/characterHints 等）
  - characterCards: [...]                      # 来自 character_designer（含结构化 visualAppearance/emotionByBeat 等）
  - storyboard: [...]                          # 来自 storyboard_designer（含扩展 shots 结构）
  - globalVisualStyle: <string>                # 全局画风描述（综合提炼自 globalStyleTag + visualTone）
  - characterVisualAnchors:                    # 角色视觉锚点列表
    - id: <string>
      name: <string>
      referencePrompt: <string>                #   供生成阶段注入 prompt
      colorScheme: <object>
  - bgmPlan:                                   # BGM 规划（三源头合并后的唯一版本）
    - segments:
      - beatIds: [<string>]                    #   覆盖的 beat 范围
        bgmMood: <string>                      #   情绪标签
        bgmStyle: <string>                     #   BGM 风格
        bgmTransition: switch|continue         #   是否在此段结尾切换
    - totalDurationSec: <number>
    - conflictResolutionLog: <string>          #   冲突解决记录（如有）
  - timingBudget:                              # 结构化时长预算
    - targetSec: <number>
    - actualEstSec: <number>
    - byBeat:
      - beatId: <string>
        estSec: <number>
        shotCount: <number>
    - overflowWarningSec: <number>             # 正值表示超时秒数
  - subtitleHints:                             # 字幕提示
    - shotId: <string>
      text: <string>
      speakerId: <string>
      lineType: <LineType enum>                #   台词类型
      startSec: <number>                       #   在视频中的预估绝对起始秒
      endSec: <number>
      style: default|emphasis|whisper
  - shotFallbackPlan:                          # 兜底方案
    - shotId: <string>
      risk: <string>
      fallback:
        visualPrompt: <string>
        shotType: <ShotType enum>
  - qualityReport:                             # 前期质量报告
    - overallScore: <number>                   #   综合评分 0-100
    - checks:
      - name: timing_consistency|character_coverage|dialogue_completeness|emotion_continuity|bgm_coherence
        result: pass|warn|fail
        detail: <string>                       #   校验细节
    - warnings: [<string>]
  - version: <string>                          # 版本号（如 "1.0"，部分重跑时递增）
  - generatedAt: <string>                      # 生成时间戳
- nextStep: 进入素材生成
```

## 注意事项
- 任一子 Skill 失败时立即返回 `E_SUBSTEP_FAILED`，不做静默忽略，错误信息中需指明哪个子 Skill 失败及原因。
- 输出字段命名必须稳定，便于下游解析。
- 口播句子应优先短句化，降低后期字幕越界风险。
- Step 2a（脚本）和 Step 2b（人设）可并行执行，加速前期策划；但 Step 3（分镜）必须等待前三者全部完成。
- 交叉校验是前期质量的核心保障：任一 FAIL 项需自动触发对应子 Skill 重跑（但不全流程重跑）。
- 前期包必须包含 `bgmPlan` 字段，供后期 BGM 选取和剪辑卡点使用；缺失时应报错 `E_INPUT_INVALID`。
- `globalVisualStyle` 和 `characterVisualAnchors` 是素材生成阶段的强制输入，缺失时应报错，不允许静默使用默认值。
- 前期包的连贯性是全链路质量的基础：画风统一、BGM 预规划、角色一致性都从此处传递到下游。
- `qualityReport.overallScore` 是 Phase B Gate 的核心判据，≥ 70 才可进入素材生成。
- 部分重跑通过 `rerunFrom` 实现局部修复，避免整个前期包重做浪费时间。
- 所有 `constraints[]` 必须被显式消费或在 `warnings[]` 中声明未消费，不允许静默丢弃。
