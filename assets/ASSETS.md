# 第三方素材登记

原则：**任何非本项目自制的素材，必须在此登记来源、作者、授权，并在素材目录内附授权说明文件。**
没有登记表的素材，一律不得进入游戏。
本项目自制（含程序化生成、模型出图）的素材同样登记，来源写清「怎么来的」，便于追溯。

## 一、第三方素材

| 名称 | 类型 | 作者 | 授权 | 来源 | 本地路径 | 用途 |
|---|---|---|---|---|---|---|
| MV Platformer Male (32x64) | 玩家角色 / 全套动画 | MoikMellah | **CC0 1.0** | [OpenGameArt](https://opengameart.org/content/mv-platformer-male-32x64) | `assets/characters/cc0_mv_platformer_male/` | 序章玩法阶段的玩家占位角色，正式角色定稿后替换；本轮未直接使用，保留备用 |

## 二、本项目自制 · 背景

来源统一为：`提示词工程部分/视觉稿/` 下的模型参考稿，由 `tools/prepare_assets.py` 转码落库
（现实段落保留原始比例、宽度上限 1920、LANCZOS 降采样；像素段落 2 倍图 NEAREST 缩放）。
同目录 `提示词工程部分/视觉稿/序章_v1/manifest.json` 记录了生成提示词。

| 本地文件 | 尺寸 | 来源 | 用途 |
|---|---|---|---|
| `assets/backgrounds/prologue/s01_plaza.png` | 1920×1280 | 视觉稿 `序章_v1/02_scene01_plaza.jpg` | Scene 01 / 02 樱花广场 |
| `assets/backgrounds/prologue/s03_port.png` | 1920×823 | 视觉稿 `序章_v1/03_scene03_port.jpg` | Scene 03 港口与客轮 |
| `assets/backgrounds/prologue/s04_deck.png` | 1920×1280 | 视觉稿 `序章_v1/04_scene04_deck.jpg` | Scene 04 甲板；Scene 05 用同一张叠加天气渐变 |
| `assets/backgrounds/prologue/s05_storm.png` | 1920×1280 | 视觉稿 `序章_v1/05_scene05_storm.jpg` | Scene 06 风暴海面（客轮外部） |
| `assets/backgrounds/prologue/s06_island.png` | 1920×823 | 视觉稿 `序章_v1/06_scene06_island.jpg` | Scene 06 浓雾中的岛屿 |
| `assets/backgrounds/prologue/s07_coast.png` | 1920×1080 | 视觉稿 `序章_v2/python/py1_coast_slice.png` | Scene 07 像素海岸（未知世界） |
| `assets/backgrounds/prologue/s05_cabin.png` | 1920×1080 | **程序化生成**：`tools/prepare_assets.py::build_cabin()` | Scene 05 / 06 客轮内舱（视觉稿没有内舱图，先用占位） |

## 三、本项目自制 · 角色

| 名称 | 类型 | 来源 | 本地路径 | 用途 |
|---|---|---|---|---|
| 千早爱音 像素占位 Sprite | 32×64 像素帧（倒地 / 呼吸 / 坐起 / 站立 / 行走 ×2） | **程序化生成**：`src/art/pixel_doll.py`，配色取 `角色设定/SKILL.md` 4.2 的官方基准色 | 运行时生成，不落盘 | Scene 07 未知世界段落 |
| 角色占位纸片 | 运行时绘制：角色代表色圆角矩形 + 名字 + 「占位」标记 | **程序化生成**：`src/ui/paper_doll.py` | 运行时生成，不落盘 | Scene 01–06 现实世界段落（正式纸片到位后自动替换） |

角色纸片正式素材目录约定：`assets/characters/paper_dolls/<角色ID>/<portrait>.png`
（透明背景、720×1080 画布、人物高 900px、脚底对齐底部）。缺哪张见根目录 `缺图清单.md`。

## 四、字体（已入库，SIL OFL 1.1）

按《整体风格与UI》第 6 节：像素阶段用 Fusion Pixel，现实阶段用思源黑体。
**Zpix 未采用**——它是付费商用授权，不符合「可入库、可分发」的要求。
下载可复现：`python tools/fetch_fonts.py`。

| 本地文件 | 名称 / 作者 | 授权 | 来源 | 用途 |
|---|---|---|---|---|
| `assets/fonts/fusion-pixel-12px-monospaced-zh_hans.ttf` | Fusion Pixel Font / TakWolf | **SIL OFL 1.1** | [GitHub](https://github.com/TakWolf/fusion-pixel-font) v2026.10.25 | 像素段落：标题 / 菜单 / HUD / 任务卡 / 操作提示（只用 12 / 24 / 48px 整数倍） |
| `assets/fonts/SourceHanSansCN-Regular.otf` | 思源黑体 Source Han Sans CN Regular / Adobe | **SIL OFL 1.1** | [GitHub](https://github.com/adobe-fonts/source-han-sans) | 现实段落：对话正文 / 名字条 / 广播字幕 / 手机群聊 |

授权原文同目录：`LICENSE-fusion-pixel-OFL.txt`、`LICENSE-source-han-sans.txt`。

回退顺序在 `data/config.json` 的 `fonts.candidates` 里：入库字体优先，
其后才是系统字体（`msyh.ttc` / `simsun.ttc` 等，仅作兜底，不随项目分发）；
全部缺失时退回渲染器默认字体，不崩溃。

补字体：把 `.ttf/.otf/.ttc` 放进 `assets/fonts/`，在 `data/config.json` 的
`fonts.candidates` 里把该路径排到最前，然后重跑 `python -m src --check-assets` 确认。

## 五、音频

本轮**没有**任何第三方或正式音频素材：

- 音乐：剧情文档需要的 6 条 BGM 全部缺失，`music` 指令安静跳过，不报错（见 `缺图清单.md` 第 3 节）。
- 音效 / 环境音：由 `src/audio/audio.py` 用正弦波、方波、滤波白噪声**程序化合成**
  （消息提示音、快门、广播杂音、海浪、风、风暴），属本项目自制，无授权问题。
  环境音支持分层（如 Scene 07 的「海浪 + 微风」同时播放）。

## 六、粒子演出

`src/ui/particles.py` 用图元程序化绘制，不需要任何图片素材：
樱花花瓣（Scene 01/02）、雨丝（Scene 05/06）、雾团（Scene 06）、浪花（Scene 07）。
参数在 `data/config.json` 的 `particles.presets`，场景里用 `{"cmd":"particles","preset":"sakura"}` 触发。

## 七、沙盒玩法（程序化，无图片素材）

`src/sandbox/textures.py` 用代码生成 16×16 的地块贴图与物品图标，不占用素材配额、无授权问题：

- 地块：草地 / 泥土 / 石块 / 铜矿 / 铁矿 / 树干 / 树叶 / 木板 / 石砖 / 工作台 / 火把；
- 物品图标：方块直接复用地块贴图，工具（镐/斧/剑）与矿物用 16×16 程序化图形；
- 配色取自 `data/tiles.json` 与 `data/items.json`，改颜色只需改 JSON。

要做成正式资产时，把 `TileTextures` / `ItemIcons` 换成读 `assets/tiles/<key>.png` 即可，接口不变。

## 八、使用约定

1. **CC0 不需要署名**，但本项目仍保留作者信息，便于追溯与致谢。
2. 素材原文件不得直接修改；需要改色或换装时，另存到 `assets/characters/<项目自建名>/` 并在此表新增一行。
3. 引用第三方素材的代码，必须在注释里写明素材名与授权。
4. 商用前重新核对一次授权状态（作者有权变更后续版本授权，但已发布的 CC0 版本不可撤回）。
5. 背景与角色形象源自《BanG Dream! It's MyGO!!!!!》，属二次创作，仅限个人 / 非商业同人用途（见 `角色设定/SKILL.md` 第 7 节）。

## 九、待办

- [ ] 正式角色（千早爱音等）纸片定稿：按 `缺图清单.md` 补 28 张，替换占位纸片
- [ ] 补 6 条 BGM
- [x] 像素字体 / 思源黑体入库（Fusion Pixel + Source Han Sans，OFL-1.1）
- [ ] 用正式素材替换 `s05_cabin.png` 与千早爱音像素 Sprite
- [ ] 音效 / 音乐素材同样需要在此登记
