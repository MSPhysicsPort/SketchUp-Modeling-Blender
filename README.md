# SketchUp Modeling for Blender

在 Blender 里用 SketchUp 的建模逻辑完成建模：完整复刻 SketchUp 的建模工具、建模逻辑与工具菜单。参照基线为 SketchUp 2026 classic 行为。

*English summary: a Blender extension that recreates SketchUp modeling tools, logic and menus inside Blender. Baseline: SketchUp 2026 classic behavior. Requires Blender 4.2+. The UI language follows Blender's language setting (Chinese/English).*

## 要求

- Blender **4.2+**（已在 4.5.16、5.1.2、5.2.4、5.3.0 上自测通过；主测版本 5.1.2，Windows 11）
- 界面语言跟随 Blender 的语言设置：中文界面全部中文、英文界面全部英文，不混杂

## 安装

1. 从 [Releases](../../releases) 下载 `sketchup_modeling-<版本>.zip`。
2. Blender → 编辑 → 偏好设置 → 插件（Get Extensions）→ 从磁盘安装，选择该 zip。
3. 启用后**默认什么都不变**：必须先开 SU 模式开关（3D 视图头栏 **SU Mode** 按钮，或 N 面板 → SketchUp → SketchUp Mode 开关，或 F3 搜 `Toggle SketchUp Mode`）。
4. 开 SU 模式后进入 SU 建模模式（SU 快捷键 + 吸附 + 编辑模式）；关掉则全部恢复 Blender 原状。

## 功能（1.0.0）

- **绘图**：直线、徒手画、矩形、旋转长方形、圆、多边形、圆弧、两点圆弧、三点圆弧、扇形；推断（端点/中点/中心/面上/轴向）+ VCB 数字输入
- **变换**：移动、旋转、缩放（优先 Blender 原生变换 + SU 吸附/复制/阵列）、推/拉（含推穿打洞、双击复用）、偏移、路径跟随（自动 + 手动逐边）、翻转
- **群组/组件**：嵌套、共享定义、双击进出编辑、设为唯一、炸开、锁定
- **编辑**：相交面（三档，含共面）、柔化边线、隐藏/取消隐藏、Surface、实体工具（Outer Shell / Union / Subtract / Trim / Intersect / Split）
- **组织**：Tags（标记）、材质与 Paint Bucket（四种模式、Alt 取样、真实尺寸 UV）、剖切面、参考线与绘图轴（随文件保存）
- **测量与标注**：卷尺（含整体缩放模型）、量角器、坐标轴工具、尺寸标注、文字、3D 文字（含中文）
- **相机与视图**：Orbit / Pan / Zoom / Zoom Window / Position Camera / Look Around / Walk、标准视图、充满视图、视图历史、场景、样式预设
- **选择与界面**：选择、套索（顺时针全含、逆时针相交）、搜索（Shift+S）、后边线（K）、右键菜单、Edit 菜单、完整工具栏、持久视口叠加层
- **工具直切**：任何工具进行中，直接按另一个工具的快捷键立即切换，不用先按 Esc（VCB 有数字输入时例外：字母先当 VCB 后缀）

快捷键（仅 SU 模式开启时生效）：Space=选择、Shift+Space=套索、L=直线、E=橡皮擦、R=矩形、C=圆、A=两点圆弧、M=移动、P=推/拉、Q=旋转、S=缩放、F=偏移、G=成组、T=卷尺、B=材质、K=后边线、O=Orbit、H=Pan、Z=Zoom、Shift+Z=充满视图、N=平行投影、F2=顶、F3=前、F4=左、F5=右、Shift+S=搜索。

沙盒工具不在首期范围内。

## 从源码打包

```sh
python3 build.py
```

输出 `build/sketchup_modeling-<版本>.zip`，同时做 T0 校验（manifest 字段、zip 顶层结构、根模块导入规则）。

## 测试

- T0 打包验证 + T1 单元测试（94 项）：`python3 tests/run_t1.py`
- T2 集成测试（119 项，需 Blender）：`tests/run_matrix.sh`（需先把各版本 Blender 便携版解压到 `tools/`，该目录不进仓库）
- 交互流程自测架：`tests/modal_harness.py`（假事件驱动真实 operator）+ GUI 真实按键 harness（`tests/gui_key_harness/`，需 Xvfb）

各版本测试说明见 `docs/`（`1.0.0-测试说明.md` 为当前版）。

## 已知限制（诚实标注）

- 旋转无交互拾取中心/折叠轴（轴心固定为选择中心）、缩放无包围盒手柄、旋转阵列需手输角度
- 两点透视为近似实现（调平地平线）：Blender 没有偏轴投影，做不出真两点透视
- 反面材质：Blender 无法给单个面指定反面材质；只有默认材质有独立的反面色，喷涂过的面正反同材质
- 容器材质：点容器喷涂时，材质会烤进当前默认材质的面（做不到 SU 的容器级动态继承）
- 剖切显示用布尔修改器：大模型活动剖切时刷新可能变慢
- Walk 是基础版（WASD + 拖动环视，无碰撞/重力）
- 按标记着色显示为包围框着色（非 SU 的面着色）

## 仓库结构

```
addon/      插件源码（Extension 格式，blender_manifest.toml）
build.py    打包 + T0 校验
tests/      T0/T1/T2 与交互流程自测
docs/       方案与各版本测试说明
research/   调研稿（SketchUp 工具清单、核心逻辑映射、架构与范围）
STATUS.md   进度状态（living 文档）
```

## 许可证

GPL-3.0-or-later，见 `LICENSE`。
