# zizhi

本仓库用于管理一组可复用的 AI skills 及辅助脚本，方便在不同任务中快速查找对应能力、查看用途说明，并直接定位到实现文件。

## 内容概览

- `skills-lock.json`：skills 清单与来源信息
- `.agents/skills/`、`.claude/skills/`：具体 skills 定义
- `Scripts/`：仓库内的实用 Python 脚本

## Skills 索引

下表整理了当前仓库锁定的 skills 及中文功能说明，便于快速检索。

| Skill | 功能说明 |
| --- | --- |
| `agent-browser` | 浏览器自动化技能，用于打开网页、填写表单、点击按钮、抓取页面内容、测试 Web 应用和自动化浏览器操作。 |
| `algorithmic-art` | 使用 p5.js 和种子随机数生成算法艺术、图形作品与交互式视觉实验。 |
| `baoyu-article-illustrator` | 根据文章内容分析适合插图的位置，并生成对应插画建议。 |
| `baoyu-comic` | 生成知识漫画、教育漫画和分镜式漫画内容。 |
| `baoyu-compress-image` | 压缩图片并转换为 WebP 或 PNG，便于发布和存储。 |
| `baoyu-cover-image` | 生成文章封面图，支持多维度风格、配色与画面表现。 |
| `baoyu-danger-gemini-web` | 通过 Gemini Web 接口进行文本和图像生成，支持多轮对话和视觉输入。 |
| `baoyu-danger-x-to-markdown` | 将 X / Twitter 内容转换为 Markdown 文档。 |
| `baoyu-diagram` | 生成专业 SVG 图表，如架构图、流程图、时序图和思维导图。 |
| `baoyu-format-markdown` | 将 Markdown 内容整理为更清晰的结构，适合美化文章和说明文档。 |
| `baoyu-image-cards` | 生成适合社交平台传播的图片卡片和信息卡片系列。 |
| `baoyu-image-gen` | 使用多家图像模型进行文生图和图生图生成。 |
| `baoyu-imagine` | 新一代图像生成能力，支持文本、参考图、批量与多模型输出。 |
| `baoyu-infographic` | 生成高密度信息图，适合内容总结、知识展示和视觉化表达。 |
| `baoyu-markdown-to-html` | 把 Markdown 转成带样式的 HTML，适合公众号、网页和富文本输出。 |
| `baoyu-post-to-wechat` | 发布内容到微信公众号，支持文章、富文本和图文。 |
| `baoyu-post-to-weibo` | 发布内容到微博，支持普通微博和头条文章。 |
| `baoyu-post-to-x` | 发布内容到 X / Twitter，支持帖子、图片、视频和长文。 |
| `baoyu-slide-deck` | 生成专业幻灯片图片和演示稿素材，适合演示与汇报。 |
| `baoyu-translate` | 文档翻译技能，支持快速翻译、精翻和术语一致性处理。 |
| `baoyu-url-to-markdown` | 抓取任意 URL 并转换为 Markdown，适合保存网页内容。 |
| `baoyu-xhs-images` | 为小红书等平台生成图文卡片系列。 |
| `baoyu-youtube-transcript` | 提取 YouTube 视频字幕、转写文本和封面信息。 |
| `brand-guidelines` | 将 Anthropic 品牌风格应用到相关内容中。 |
| `canvas-design` | 用设计思维创建静态视觉作品，如海报、插画和艺术图。 |
| `claude-api` | 面向 Anthropic Claude API / SDK 的开发、调试、优化与迁移。 |
| `create-readme` | 为项目生成结构清晰、信息完整的 README。 |
| `doc-coauthoring` | 文档共创工作流，适合撰写提案、技术文档、规范和协作文档。 |
| `docx` | 处理 Word 文档，支持读取、编辑、整理和格式化。 |
| `find-skills` | 帮助查找和安装合适的 skill，适合根据需求快速定位可用能力。 |
| `frontend-design` | 生成高质量前端界面与组件，适合网页、落地页、仪表盘和交互页面设计。 |
| `internal-comms` | 用于撰写内部沟通材料，如状态更新、项目周报、领导汇报和事故说明。 |
| `mcp-builder` | 创建高质量 MCP Server 的指南，帮助把外部 API 封装成可用工具。 |
| `pdf` | PDF 文件处理技能，支持阅读、合并、拆分、旋转、加水印、OCR 和导出。 |
| `pptx` | PPTX 演示文稿处理技能，支持创建、读取、编辑、拆分与合并幻灯片。 |
| `release-skills` | 统一的发布工作流，适合版本管理、Release Notes 和发版。 |
| `seo-audit` | 站点 SEO、技术、内容和可读性审计。 |
| `skill-creator` | 创建、修改、优化和评估新 skills，用于沉淀可复用能力。 |
| `slack-gif-creator` | 生成适合 Slack 使用的动图 GIF，强调尺寸、动画节奏和平台约束。 |
| `summarize` | 对 URL、视频、播客、文章或本地文件进行总结与转写。 |
| `template-skill` | 技能模板示例，供创建新 skill 时参考。 |
| `theme-factory` | 为文档、幻灯片、网页等生成或套用主题风格。 |
| `web-artifacts-builder` | 构建复杂的 Web artifact，适合多组件、状态管理和 shadcn/ui 场景。 |
| `webapp-testing` | 使用 Playwright 测试本地 Web 应用，便于调试 UI、验证交互和查看日志。 |
| `xlsx` | 电子表格处理技能，支持打开、编辑、清洗、计算和导出表格数据。 |

## 其他目录中的去重 Skills

下面这些 skills 来自 `.github/skills/`、`.claude/skills/` 和 `.qoder/skills/`，且未包含在上面的主索引中。

| Skill | 来源 | 功能说明 |
| --- | --- | --- |
| `cn_short_video_publisher` | `.github` / `.claude` / `.qoder` | 中文短视频发布技能，用于组装抖音、视频号等平台的发布包。 |
| `dreamina` | `.claude` / `.qoder` | 即梦相关能力，用于通过 Dreamina CLI 生成图像或视频素材。 |
| `jimeng_video_generator` | `.claude` / `.qoder` | 即梦视频生成技能，统一处理文生视频、图生视频和素材生成。 |
| `lark_cli_setup` | `.github` / `.claude` / `.qoder` | 飞书 CLI 的安装、配置、认证和首次验证流程。 |
| `lark_cli_usage_guide` | `.github` / `.claude` / `.qoder` | 飞书 CLI 的功能索引与命令速查，帮助快速选择正确能力。 |
| `video_editor` | `.github` / `.claude` / `.qoder` | 视频剪辑技能，负责粗剪、精剪、转场、字幕和导出。 |
| `video_postprod_orchestrator` | `.github` / `.claude` / `.qoder` | 后期编排技能，整合配音、调色、剪辑、混音与发布准备。 |
| `video_preprod_orchestrator` | `.github` / `.claude` / `.qoder` | 前期策划编排技能，输出脚本、人物设定、剧情和分镜。 |
| `video_quality_reviewer` | `.github` / `.claude` / `.qoder` | 成片质量审核技能，用于核对素材一致性、字幕配音和成片质量。 |

## 本仓库脚本

- `Scripts/download_images.py`：批量下载漫画图片，支持章节列表、并行下载和多 URL 批处理。
- `Scripts/merge_images.py`：将下载后的图片按章节拼接并导出为 PDF，支持批量处理子目录。

## 备注

如果后续新增或移除 skills，建议同步更新 `skills-lock.json` 和本 README，保持索引一致。