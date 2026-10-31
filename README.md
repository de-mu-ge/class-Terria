# 直到再次相遇 · 序章（第二轮：可运行流程）

2D 像素风生存沙盒游戏的序章。前段是 Galgame 式线性演出（真实世界），
Scene 06 闪白处切换到像素渲染管线，Scene 07 交还操作权后进入生存模式占位画面。

本轮目标：**开始界面 → Scene 01→07 → 控制权交接 → 生存占位**，能跑通、能推进、不卡死。

---

## 1. 环境

- Conda 环境 `game`（Python 3.10）
- 渲染 **pygame-ce**，所有绘制收敛在 `Renderer` 抽象类后面
- Pillow 仅用于 `tools/prepare_assets.py` 做资产转码（运行游戏不需要）

```bash
conda activate game
pip install -r requirements.txt
```

## 2. 运行

```bash
python -m src                     # 从开始界面启动，正常游玩
python -m src --scene 03          # 单独调试某个 Scene（进入该场后仍会自然接下一场）
python -m src --list-scenes       # 列出全部场景与演出指令数
python -m src --check-assets      # 检查素材缺口（缺图清单的唯一数据来源）
python -m src --smoke --headless  # 自检：开始界面 → 01…07 → 生存占位，自动跑完退出
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--scene NN` | 只从指定 Scene 开始（`3` / `03` / `s03` 都认） |
| `--headless` | 无窗口（SDL dummy），配合 `--capture` 出图 |
| `--autoplay` | 自动推进对话（验证用，不等于跳过演出） |
| `--speed N` | 时间倍率，默认 1.0 |
| `--capture DIR --capture-times 3,6,9` | 在指定游戏秒截图到 DIR |
| `--debug` | 显示场景 ID / 镜头 / 指令下标（运行中 F1 也可切换） |
| `--no-audio` | 禁用音频（无声卡环境） |
| `--window-scale N` | 覆盖窗口整数倍缩放（默认 2×，即 1920×1080） |

## 3. 操作

| 输入 | 行为 |
|---|---|
| 左键 / 空格 / 回车 | 推进对话（打字中按下 = 立刻显示全文） |
| 按住 Ctrl | 快进整段（连续翻页） |
| ↑ ↓ ← → / W S A D | 菜单选择、音量调节 |
| Esc | 场景内：弹出「返回开始界面？」二次确认；设置界面：返回 |
| F1 | 调试信息开关 |
| 生存占位画面：← → / A D | 左右移动（证明操作权已交接） |

开始界面菜单：**开始游戏 / 继续（本轮置灰）/ 设置（只有音量）/ 退出**。

## 4. 目录结构

```
src/
  core/     引擎无关层：FixedTimestepLoop、SceneStack、StateMachine、Timeline、ResourceManager、类型/事件
  render/   Renderer 抽象 + PygameRenderer（960×540 逻辑画布，整数倍最近邻放大）
  ui/       对话框、名字条、手机群聊、广播字幕、HUD/信号、任务卡、操作提示、照片定格、菜单/确认/滑条、占位纸片
  scenes/   Scene 基类、数据驱动演出（Director/Stage/Effects）、title/settings/survival、路由
  data/     数据读取与校验（内容在根目录 data/*.json）
  assets/   素材路径解析（只读）
  art/      程序化像素角色（未知世界占位 Sprite）
data/
  config.json      分辨率、帧率、调色板、字体、对话框/HUD/转场所有数值与 UI 文案
  characters.json  五名角色、代表色、立绘清单、占位规则
  dialogues.json   全部台词段（含说话人、立绘、表情、动作备注、镜头、音效、停顿）
  scenes.json      7 个 Scene 的舞台、背景、音乐、镜头序列（timeline 指令流）
assets/
  backgrounds/prologue/   7 张背景（6 张由视觉稿转码，1 张程序化占位）
  characters/…            角色纸片目录（当前为空 → 占位纸片）、CC0 备用素材
  fonts/                  Fusion Pixel 12px（像素段）+ 思源黑体 CN Regular（现实段），均 OFL-1.1
  ASSETS.md               素材登记表（第三方 / 自制 / 字体 / 音频）
tools/
  prepare_assets.py       视觉稿 → 游戏背景转码
  fetch_fonts.py          下载并安装两套 OFL 字体（可复现）
  flow_check.py           交互流程自检（菜单、快进、Esc、单独启动、状态干净）
  verify_script.py        台词与《第一轮剧情.md》逐句比对
  gen_missing_report.py   生成《缺图清单.md》
  scan_secrets.py         推送前密钥自查
  scrub_manifest.py       清洗生图 manifest 里的预签名 URL
```

## 5. 本轮实现范围

**演出（严格照《第一轮剧情.md》，82 句台词逐句一致）**

| Scene | 落地的演出 |
|---|---|
| 01 春日的集合 | 黑屏淡入 → 天空（镜头上抬取景）→ 下移穿过樱花 → 爱音从右侧滑入 → 推近至上半身 → 对话框；手机群聊独立 UI 层：三条立希消息依次出现、每条提示音、停留 2s；切回爱音两句；侧面中景走向集合点后淡出 |
| 02 五个人的集合 | 五人同框（爽世中央偏左、立希旁边、灯中央偏右、乐奈右侧长椅、爱音自左侧走入）；爱音抵达 → 灯 → 乐奈 → 出发准备四段对话；镜头在三段之间移到对应人物；乐奈起身、拉远淡出 |
| 03 出发前往英国 | 港口远景 → 镜头下移找到五人 → 九句对话 → 登船（五人依次淡出离开）→ 客轮离港 |
| 04 海上的旅行 | 海面 → 抬升到甲板 → 五人日常对话；鱼跃出水面特效；合照流程 → 快门音 → 相纸定格 2.0s（静态构图：甲板裁切 + 五个小人 + MyGO!!!!! 说明）→ 拉远停在海上 3s |
| 05 异常天气 | 同一张甲板图叠加**渐变遮罩**由晴转阴（不换图）；云层取景移动；船体整体位移 2–3px / 0.5Hz；广播用字幕条 + 风暴环境音；切内舱后强晃、灯光闪烁；右上角信号图标 在线 → 信号弱 → **无信号**（斜杠 + 闪烁） |
| 06 未知岛屿 | 风暴中的客轮 → 冷色遮罩 → 浓雾 → 岛屿交叉淡化 → 三段推近（远山剪影 → 森林 → 山峰，各 1.5s）→ 停留 3s → 切回内舱、灯灭、`「大家……！」` → 闪白 0.15s → 黑屏 2s →**切换渲染管线** |
| 07 直到再次相遇 | 黑屏 3s（海浪先入）→ 像素海岸淡入 → 爱音 Sprite 倒地 → 呼吸 → 坐起 → 站起 → 左右张望 → 呼喊 → 镜头拉远 → 对话框收回 → 操作提示 + HUD + 初始任务卡 → 交接给生存占位画面 |

**系统**

- 对话框：面板 36–924 × 393–516、名字条 180×39 @ y363、外框 2px `#C9A227`、正文 18px / 行高 27、40 字/秒打字机、点击续句、按住 Ctrl 快进、已读记录（内存）
- 字体：像素段 **Fusion Pixel 12px**（标题 48 / 菜单 24 / HUD 12，只用整数倍），现实段 **思源黑体 CN Regular**，均 OFL-1.1 已入库
- 粒子：樱花花瓣（Scene 01/02）、雨丝（Scene 05/06）、雾团（Scene 06）、浪花（Scene 07），数据驱动、固定种子可复现
- 转场：淡入 0.6s、淡出 0.5s、闪白 0.15s、交叉淡化 0.4s，全部从 `data/config.json` 读
- HUD：左上两条 288×18（生命 / 体温）、底部 8 格 ×96 快捷栏、右上信号图标
- 音频：程序化合成音效与环境音（海浪 / 风 / 风暴 / 提示音 / 快门 / 广播杂音），支持多层环境音叠加，无音频设备时自动静音
- 缺资源一律降级：背景缺 → 占位色块；纸片缺 → 占位纸片；音乐缺 → 跳过；字体缺 → 系统回退

## 6. 验收对照

| 验收项 | 结论 | 怎么复核 |
|---|---|---|
| `python -m src` 从开始界面启动不报错 | ✅ | 实机运行；`python -m src --smoke --headless` 亦无 traceback |
| Scene 01–07 可推进，台词与文档逐句一致 | ✅ | `python tools/verify_script.py` → 82 句、顺序一致 |
| 任意 Scene 可 `--scene NN` 单独启动 | ✅ | `python -m src --scene 5` 等 |
| 手机群聊 / 广播 / 任务提示三个特殊 UI 正常出现与消失 | ✅ | Scene 01 群聊、Scene 05 字幕条、Scene 07 任务卡 |
| Scene 06 淡入淡出、闪白、黑屏时长正确 | ✅ | `scenes.json` 中 `flash.duration=0.15`、`black.duration=2.0`，数值直接来自配置 |
| Scene 07 像素段与前面现实段视觉上明确不同 | ✅ | 现实段：动画背景 + 纸片立绘；像素段：硬像素背景 + 32×64 Sprite（无立绘） |
| 缺图不崩溃，显示占位纸片 | ✅ | 当前 28 张纸片全缺，全流程正常 |
| 全程无 traceback、无黑屏卡死 | ✅ | `--smoke` 跑完 7 场 + 生存占位，退出码 0 |
| 退出后重进状态干净 | ✅ | `tools/flow_check.py` 第 6 项：已读记录清空、回到开始界面 |

## 7. 数据怎么改（不动代码）

- **改台词**：`data/dialogues.json`。每行 = 说话人 + 立绘 ID + 表情备注 + 文本 + 动作备注 + 镜头 + 音效 + 停顿。
  `action` 只给美术/QA 看，不在游戏里显示。
- **改镜头 / 演出顺序**：`data/scenes.json` 的 `timeline`。可用指令：
  `bg / camera / doll_show / doll_hide / doll_move / doll_portrait / sprite / dialogue / chat /
  subtitle / subtitle_hide / tint / tint_clear / shake / shake_stop / flash / fade_in / fade_out /
  black / wait / signal / signal_hide / photo / effect / hud / hint / task / sfx / music / ambience /
  pipeline / end / handoff`
- **改界面数值**：`data/config.json`（对话框、HUD、转场、镜头预设、字体、调色板、全部 UI 文案）。

代码里没有剧情台词；`python -m src --list-scenes` 会打印每个 Scene 的指令数，方便对照。

## 8. 本轮没做 / 已知限制

1. **没有角色立绘**：28 张纸片全缺，用代表色占位（见《缺图清单.md》）。像素 Sprite 同样是程序化占位。
2. **没有 BGM**：剧情要求的 6 条音乐一条都没有，`music` 指令安静跳过；音效与环境音是程序化合成的。
3. **无正式船舱内景**：`s05_cabin.png` 是程序化占位背景。
4. **HUD 数值两处规范冲突**：`整体风格与UI/SKILL.md` 写「条 96×6、单格 32×32」，
   本轮 epoch 提示词写「条 288×18、单格 96」，**按本轮提示词实现**，待统一后改 `data/config.json` 即可。
5. **未使用 `p3_storm_transit.jpg`**：该稿本身是像素化笔触，用在 Scene 06 闪白之前会违反
   「闪白前不得出现像素」的硬约束，故 Scene 06 改用 `s05_storm.png`。
6. 生存玩法、采矿、建造一律未做；玩家获得控制权后只有「左右移动 + HUD + 任务卡」。
7. 已读记录只存内存，退出即清空；「继续」按要求置灰不可用。
8. 粒子（花瓣 / 雨丝 / 雾团 / 浪花）是程序化图元，不是手绘序列帧；要更精细可替换 `src/ui/particles.py`。

## 9. 自检命令

```bash
python tools/verify_script.py       # 台词逐句比对（应输出 82 句一致）
python tools/flow_check.py          # 交互流程自检（应全部通过）
python -m src --check-assets        # 素材缺口
python tools/gen_missing_report.py  # 重新生成《缺图清单.md》
python -m src --smoke --headless    # 全流程跑通
python tools/scan_secrets.py        # 推送前密钥自查（应输出「干净」）
```

> 视觉生图的 `manifest.json` 曾把预签名图片 URL（查询串里带 AK ID）写进仓库，被 GitHub
> push protection 拦下。现已修掉：`generate_image.py` 只记录对象地址，旧清单用
> `python tools/scrub_manifest.py` 清洗。新增生图结果后，推送前务必跑一次 `scan_secrets.py`。
