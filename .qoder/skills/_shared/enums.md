# Shared Enums — 前期策划跨 Skill 共享枚举

本文件定义前期策划所有 Skill 共享的枚举值，各 Skill 引用此处定义以避免枚举漂移。
修改本文件时必须同步检查所有引用方。

---

## Emotion（情绪标签）

适用于 script_writer、story_designer、character_designer、storyboard_designer。

```
neutral | hopeful | excited | tense | sad | angry |
humorous | mysterious | nostalgic | inspiring | fearful | tender
```

## Beat（节拍类型）

适用于 script_writer、story_designer。

```
hook | setup | rising_action | climax | falling_action |
resolution | callback | cta | recap | cold_open
```

## TransitionHint（段落间过渡关系）

适用于 script_writer。

```
continuation | contrast | escalation | reveal |
flashback | parallel | conclusion
```

## VoiceStyle（角色声线风格）

适用于 character_designer、jimeng_tts_dubber。

```
warm_narrator | authoritative | youthful_energetic |
calm_professional | playful | dramatic | whisper |
elderly_wise | child | robotic
```

## Genre（题材类型）

适用于 story_designer。

```
tutorial | vlog | story | review | ad |
documentary | comedy_skit | news_commentary | unboxing |
interview | music_video | animation_short | motivational |
comparison | behind_the_scenes
```

## CharacterRole（角色类型）

适用于 character_designer。

```
protagonist | antagonist | supporting | narrator |
mentor | comic_relief | cameo
```

## ShotType（镜头景别）

适用于 storyboard_designer。

```
wide | medium | close_up | extreme_wide | over_shoulder |
extreme_close_up | medium_close_up | full_shot |
two_shot | point_of_view | insert
```

## CameraMove（镜头运动）

适用于 storyboard_designer。

```
static | pan_left | pan_right | zoom_in | zoom_out |
push_in | pull_out | tilt_up | tilt_down |
tracking | crane_up | crane_down | orbit | handheld
```

## TransitionType（镜头转场）

适用于 storyboard_designer。

```
cut | dissolve | fade_to_black | fade_from_black |
wipe | swipe_left | swipe_right | zoom_transition |
match_cut | j_cut | l_cut | whip_pan
```

## LineType（台词类型）

适用于 storyboard_designer。

```
dialogue | narration | voiceover | silence
```

## CtaType（行动号召类型）

适用于 script_writer。

```
subscribe | like | comment | share | link | purchase | follow
```

## OverlayType（画面叠加类型）

适用于 storyboard_designer。

```
lower_third | center_title | caption | watermark | none
```

## RelationType（角色关系类型）

适用于 character_designer。

```
colleague | friend | rival | lover | family |
mentor_mentee | stranger | competitor
```

---

# 🔊 后期处理 — 音频与声音设计枚举

## AudioTrackType（音频轨道类型）

适用于 sound_designer、video_editor、video_postprod_orchestrator。

```
dubbing | bgm | sfx | foley | ambience | mixed_master
```

| 值 | 说明 | 典型电平 (dBFS) |
|---|------|----------------|
| `dubbing` | TTS 或录制的配音/旁白 | -6 dB（参考电平） |
| `bgm` | 背景音乐轨道 | -12 ~ -18 dB（语音段进一步衰减） |
| `sfx` | 与画面动作同步的点状音效 | 视上下文而定 |
| `foley` | 合成/录制的日常声效（脚步、衣物等） | -18 ~ -24 dB |
| `ambience` | 环境/氛围底噪（房间调、风声、人群等） | -20 ~ -30 dB |
| `mixed_master` | 所有轨道的最终立体声混音 | 按平台 LUFS 目标 |

## AudioMixPreset（混音预设）

适用于 sound_designer。

```
speech_priority | music_priority | balanced | ambient | cinematic
```

| 值 | 配音 | BGM | SFX | 环境音 | 适用场景 |
|---|------|-----|-----|--------|---------|
| `speech_priority` | -6 dB | -18 dB | -14 dB | -24 dB | 教程、旁白为主 |
| `music_priority` | -10 dB | -8 dB | -12 dB | -20 dB | 音乐视频、蒙太奇 |
| `balanced` | -8 dB | -14 dB | -12 dB | -22 dB | 通用平衡 |
| `ambient` | -10 dB | -16 dB | -10 dB | -14 dB | ASMR、自然、氛围 |
| `cinematic` | -6 dB | -10 dB | -8 dB | -16 dB | 剧情短片、电影感 |

## LoudnessTarget（平台响度目标）

适用于 sound_designer。

| 平台 | 目标 LUFS | True Peak 上限 | 说明 |
|------|-----------|---------------|------|
| `douyin` | -14 LUFS | -1 dBTP | 移动端优先，较响 |
| `bilibili` | -16 LUFS | -1 dBTP | 网页/桌面端，标准广播级 |
| `youtube` | -14 LUFS | -1 dBTP | YouTube 自动归一到 -14 |
| `xiaohongshu` | -14 LUFS | -1 dBTP | 移动端优先 |
| `generic` | -16 LUFS | -1 dBTP | 安全默认值 |

---

# 🎨 后期处理 — 调色与特效枚举

## ColorGradeStyle（调色风格）

适用于 color_grader。

```
natural | cinematic_warm | cinematic_cool | vintage |
high_contrast | low_key | high_key | desaturated | neon | pastel
```

| 值 | 说明 | 特征 |
|---|------|------|
| `natural` | 最小化调色，真实还原 | 中性白平衡，标准对比度，完整饱和度 |
| `cinematic_warm` | 好莱坞暖调 | 暖色提亮暗部，琥珀高光，青色阴影 |
| `cinematic_cool` | 冷调戏剧感 | 蓝移阴影，去饱和肤色，高对比 |
| `vintage` | 复古/怀旧感 | 褪色黑色，暖色偏移，降低锐度 |
| `high_contrast` | 大胆冲击力 | 压暗黑色，提亮高光，鲜艳饱和 |
| `low_key` | 暗调、情绪化氛围 | 以阴影为主，有限高光，深黑 |
| `high_key` | 明亮、通透、乐观 | 最小阴影，整体明亮，柔和对比 |
| `desaturated` | 克制、纪录感 | 降低 30-50% 饱和度，中性色调 |
| `neon` | 赛博朋克/未来感 | 特定色相高饱和，暗背景，发光效果 |
| `pastel` | 柔和、温柔美学 | 提亮黑色，降低饱和度，暖色偏移 |

## VfxType（视觉特效类型）

适用于 color_grader、video_editor。

```
text_overlay | lower_third | logo_watermark | speed_ramp_slow |
speed_ramp_fast | lens_flare | particle | screen_shake |
split_screen | picture_in_picture | ken_burns | transition_flash
```

| 值 | 说明 | 层类型 |
|---|------|--------|
| `text_overlay` | 动画文字/标题叠加 | 叠加层 |
| `lower_third` | 画面下方三分之一处的名牌/标题条 | 叠加层 |
| `logo_watermark` | 品牌 logo 水印（透明度 30-50%） | 叠加层 |
| `speed_ramp_slow` | 慢动作效果（0.25x–0.75x） | 时间线 |
| `speed_ramp_fast` | 快进/延时效果（1.5x–4x） | 时间线 |
| `lens_flare` | 模拟镜头光晕 | 合成层 |
| `particle` | 粒子系统（灰尘、火花、雪花等） | 合成层 |
| `screen_shake` | 画面震动（冲击力强调） | 变换层 |
| `split_screen` | 多画面分屏布局 | 布局层 |
| `picture_in_picture` | 画中画小窗 | 布局层 |
| `ken_burns` | 静态图片的平移/缩放（视差效果） | 变换层 |
| `transition_flash` | 镜头间白闪/黑闪过渡 | 转场层 |
