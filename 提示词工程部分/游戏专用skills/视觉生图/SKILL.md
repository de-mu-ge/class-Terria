# Skill：视觉生图（Visual Generation）

> 版本 v0.1 · 状态：可用（账号额度受限，见「已知阻塞」）
> 位置：`提示词工程部分/游戏专用skills/视觉生图/`

## 1. 这个 Skill 解决什么

给游戏生产**参考稿**：场景构图、氛围定调、UI 概念、角色剪影。它产出的是「可讨论的图」，不是最终资产。

最终资产仍需经过：**规范 → 参考稿 → 人工敲定 → 像素化/切图/精修**。未经敲定的稿子不得进入游戏。

## 2. 工具

| 文件 | 作用 |
|---|---|
| `generate_image.py` | 火山方舟 `doubao-seedream` 封装，单图 / 批量 |
| `.ark_key` | API Key（已加入 `.gitignore`，禁止提交、禁止外传） |

只依赖 Python 标准库。调用示例（`$py` 替换为实际 Python）：

```bash
# 单图
python generate_image.py --prompt "雪原中举火把的旅人，像素风" --out out.png --size 2K

# 批量（给一个场景批量出稿，推荐）
python generate_image.py --batch scenes.json --outdir ./稿

# 只校验清单，不出图（不消耗额度）
python generate_image.py --batch scenes.json --outdir ./稿 --dry-run
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--size` | `1K` / `2K` / `4K`，或 `2048x1152` |
| `--no-watermark` | 关闭水印（参考稿建议关闭，便于看清画面） |
| `--seed N` | 固定随机种子，便于复现同一张 |
| `--negative-prompt` | 负向提示词 |
| `--timeout` | 单次请求超时，默认 240s |

批量清单格式：

```json
[
  {"name": "scene01_plaza", "prompt": "……", "size": "2K"},
  {"name": "scene07_coast", "prompt": "……", "size": "2K"}
]
```

输出目录会生成 `manifest.json`，记录每条的提示词、载荷、状态、耗时、文件大小——用于回溯「这张图当时是什么提示词出来的」。

## 3. 提示词结构（本项目统一写法）

按固定七段写，顺序不要乱，模型对前半段权重更高：

```
[风格段] 2D 像素艺术 / 2D 动画背景 / 概念稿
[主体段] 画面里有什么，谁在做什么，位置关系
[环境段] 天气、时间、地形、植被、远近层次
[光照段] 主光源方向、冷暖对比、体积光/雾
[色彩段] 主色调 + 强调色，饱和度倾向
[镜头段] 视角（侧面/俯视/广角）、景深、构图留白
[约束段] 无文字、无 logo、无水印、无 UI 覆盖
```

约束段是本项目的硬要求：**画面内不得出现任何文字**（标题、地图名、按钮字都由 UI 层渲染，不交给生图模型）。

## 4. 项目风格预设

| 预设 | 用途 | 关键词骨架 |
|---|---|---|
| `REALITY` | 序章现实世界（Scene 01–06 前半） | 2D 日式动画背景、明亮温暖、粉/浅蓝/米白、柔和阳光、无人物的干净构图 |
| `PIXEL` | 未知世界（Scene 06 后半–07 及全部玩法画面） | 2D 像素艺术、16-bit、低饱和冷色、固定侧面视角、环境占主体、可读性强 |
| `UI` | 开始界面 / HUD 概念稿 | 像素风界面底板、留白给文字、无文字、构图 16:9 |
| `KEYART` | 定调主视觉 | 像素/厚涂、人物渺小于广阔环境、火光与冷蓝对比、电影感 |

## 5. 质量红线

1. 参考稿一律**不准带文字**，出现文字即废稿。
2. 不准直接把参考稿当最终游戏资产使用。
3. 人物外观只做「气质参考」，不追求与版权角色形象一致；正式立绘与 Sprite 由美术规范定义。
4. 出稿后必须记录：提示词、seed、尺寸、敲定结论，写进 `manifest.json` 或评审记录。
5. 商用素材授权与版权归属问题，以人工判断为准，不默认自动进入资产库。

## 6. 用量与配额

账号总图片用量 **118 张**，用完为止，没有补充。

| 阶段 | 策略 |
|---|---|
| 前期（定调、试错） | 可以放开用，目标是把风格、UI、色彩定死 |
| 后期（风格稳定后） | 只在关键节点用：封面、过场、标志性场景、需要人工判断的构图 |

用量记录在 `ledger.json`（自动累加，失败与 `--dry-run` 不计）。每次运行结束会打印「累计 / 剩余」。

判断一条稿值不值得出：

1. 它能不能改变一个**设计决定**？不能就不出。
2. 已有稿子能不能改出来？能就不出。
3. 出图前先 `--dry-run` 校验清单，别为拼写错误付一张图。

## 7. 已知阻塞（2026-10-31）

账号 `2127558110` 对 `doubao-seedream-5-0-pro` 触发 **SetLimitExceeded**：

> Your account has reached the set usage limit for the [doubao-seedream-5-0-pro] model, and the model service has been paused. To continue using this model, please visit the Model Activation page to adjust or close the "Safe Experience Mode".

处理：火山方舟控制台 → 模型激活/开通管理 → 关闭「安全体验模式」或提额。
`doubao-seedream-4-0-250828`、`doubao-seedream-3-0-t2i-250415` 在该 Key 下均为 404（无权限）。

恢复后执行：

```bash
python generate_image.py --batch ../../视觉稿/序章_v1/scenes.json --outdir ../../视觉稿/序章_v1 --no-watermark
```
