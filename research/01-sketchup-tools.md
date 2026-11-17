# SketchUp 2026 建模工具完整清单（调研稿）

> 调研日期：2026-11-17 · 参照基线：SketchUp 2026.0（Windows 64-bit 26.0.429，Sen 真机版本）· 平台：Windows 桌面版为准，Mac 差异仅在修饰键处注明。
> 依据：SketchUp Help Center（help.sketchup.com）官方文章 + Trimble 官方 Quick Reference Card（QRC 2025 Windows 版）。每个工具后附来源 URL。
> 本稿只做调研，不含实现代码。凡标注/处均未在官方文本中确证，见末尾“不确定 / 需问 Sen 的事项”，不要当成定稿行为写进代码。

## 0. 版本基线警告（重要）

1. **Help Center 当前页面已混入 SketchUp 2027 内容。** 2026-10-30 / 11-11 更新的 Solid Tools、Follow Me 文章记载了 Procedural Union / Procedural Subtract / Procedural Intersect / Procedural Follow Me（非破坏性程序化组件）。Ruby API Release Notes 明确：Procedures API 是 **SU2027.0** 新增（Ruby 3.4.9）。Sen 的 26.0.429 是 2026.0，**基线内不应包含 Procedural 变体**；本稿将其单列并标注“2027，待 Sen 定是否纳入”。
2. **当前版 Help Center 文章多为精简版**，修饰键细节大量缺失，须以 QRC 2025 补齐；QRC 与文章个别处矛盾（见 §8），以标注，需真机核对。
3. **Circle 默认边数、Tools/Draw 菜单的精确顺序**在官方文本中未找到可引用的完整表述，已列为未核实项，最可靠的办法是 Sen 在真机上截图菜单核对。
4. 以下快捷键均为 **Windows 默认快捷键**（Help Center《Default Keyboard Shortcuts》，2026-10-21 更新）。无默认快捷键的工具标注“无”。

## 1. 工具总数（按本稿口径）

| 类别 | 数量 | 工具 |
|---|---|---|
| 选择 | 2 | Select、Lasso Select |
| 绘图 | 10 | Line、Freehand、Rectangle、Rotated Rectangle、Circle、Polygon、Arc、2-Point Arc、3-Point Arc、Pie |
| 编辑/变换 | 9 | Move、Push/Pull、Rotate、Flip、Scale、Offset、Follow Me、Eraser、Paint Bucket |
| 测量/构造/标注 | 6 | Tape Measure、Protractor、Axes、Dimensions、Text、3D Text |
| 剖面 | 1 | Section Plane（+3 个显示开关，见 §5.6） |
| 实体布尔 | 6 | Outer Shell、Union、Subtract、Trim、Intersect、Split |
| 沙盒地形 | 7 | From Contours、From Scratch、Smoove、Stamp、Drape、Add Detail、Flip Edge |
| 相机/视图 | 8 | Orbit、Pan、Zoom、Zoom Window、Zoom Extents、Position Camera、Look Around、Walk |
| **合计（交互工具）** | **49** | — |
| 另：命令/模式（非独立绘图工具） | — | Make Component（G）、Search（Shift+S）、Field of View（Zoom 的模式）、标准视图/投影模式（Camera 菜单）、Flip Along（右键命令）、Interact / Component Options / Component Attributes（动态组件）、Classifier、Add Location |
| 2027 Procedural 变体（基线外） | 4 | Procedural Follow Me、Procedural Union、Procedural Subtract、Procedural Intersect |

---

## 2. 工具栏结构

### 2.1 Getting Started（默认工具栏）

来源：https://help.sketchup.com/en/sketchup/toolbars（2026-10-21 更新）

官方表述的工具序列（原文照录，含一处疑似笔误，见注）：

> Search、Select、Eraser、Line、Arc、Rectangle、Offset、Move、Rotate、Scale、Flip、Tape Measure、Paint Bucket、Rotate、Pan、Zoom、Zoom Extents、3D Warehouse、Extension Warehouse、Send to LayOut、Comments、User Info

该表把 Rotate 列了两次，且未列 Circle、Polygon、Push/Pull、Freehand——与 QRC 及实际界面经验不符，疑似官方页面笔误/漏列。**Getting Started 的精确构成与顺序已于 2026-11-17 由 Sen 真机截图核定（23 项，官方表三处错误已纠：漏 Push/Pull、Rotate 重列实为 Orbit、误列 Comments 实为 Extension Manager），见方案 §2.3。**下拉（flyout）关系已核实的部分：Freehand 藏在 Line 的下拉箭头后（Freehand 文章）；Arc 下拉含 4 个弧工具；形状工具下拉含 Rectangle / Rotated Rectangle / Circle / Polygon。

### 2.2 Large Tool Set（QRC 2025 Windows 版面布局，自上而下、两列）

来源：https://download.sketchup.com/QRC2025/HC-QRC2025-en-SU-Windows.pdf

QRC 排版为两列并列，还原为阅读顺序如下（工具名与 QRC 一致；括号为快捷键）：

1. Select（Spacebar）、Lasso
2. Paint Bucket（B）、Eraser（E）
3. Line（L）、Freehand
4. Rectangle（R）、Rotated Rectangle
5. Circle（C）、Polygon
6. Arc、2 Point Arc（A）
7. 3 Point Arc、Pie
8. Move（M）、Push/Pull（P）
9. Rotate（Q）、Follow Me
10. Scale（S）、Offset（F）
11. Tape Measure（T）、Dimensions
12. Protractor、Text
13. Axes、3D Text
14. （右侧另列）Orbit（O）、Pan（H）、Zoom（Z）、Zoom Window、Zoom Extents、Previous、Position Camera、Walk、Look Around、Section Plane、标准视图（Iso/Front/Back/Top/Right/Left）、样式开关、Solid Tools（Outer Shell、Intersect、Union、Subtract、Trim、Split）、Sandbox（From Contours、From Scratch、Smoove、Stamp、Drape、Add Detail、Flip Edge）、Dynamic Components（Interact、Configurator Tool、Component Attributes）、Warehouse（3D Warehouse、Share Component、Send to LayOut、Extension Warehouse、Share Model）、Classifier、Add Location、Location、Toggle Terrain、Make Component、Tag、Field of View、Flip。

Toolbars 文章对 Large Tool Set 的定义是：“Getting Started、Construction、Drawing、Measurement、Edit 各工具栏的全部工具及其变体”。QRC 布局与 2026.0 真机 Large Tool Set 是否逐项一致（QRC 为 2025 版），需 Sen 核对。

**真机截图核对（2026-11-17，Sen 发来的 26.0.429 截图，图标逐项与 QRC 对照；以第二张截图为准，第一张 Sen 确认弄错、作废）：** 本稿初版漏列 Make Component + Tag 一行，已确认 QRC 原表有此行、真机截图第 3 行即 Make Component | Tag，特此更正。真机浮动布局为单个两列面板、7 组、6 条分隔线，完整转录见方案 §2.3；第一张截图的双面板/右侧单列转录已全部作废。末行 4 项（3D Warehouse、Extension Warehouse、Send to LayOut、Extension Manager）已由 Sen 悬停提示截图确认身份，Sen 决定不用考虑（范围外）。绘图（10 项）、编辑（7 项）、视图（7 项）三个工具栏的构成与工具栏对话框列表亦经 Sen 截图核实，见方案 §2.3。

### 2.3 其他默认工具栏（Toolbars 文章原表）

| 工具栏 | 内容 |
|---|---|
| Camera | Orbit、Pan、Zoom、Zoom Window、Zoom Extents、Undo Previous Camera View、Position Camera、Look Around、Walk |
| Construction | Tape Measure、Dimensions、Protractor、Text、Axes、3D Text |
| Drawing | Line、Freehand、Rectangle、Rotated Rectangle、Circle、Arc、2-Point Arc、3-Point Arc、Pie（注：原文未列 Polygon，疑似漏列） |
| Edit | Move、Push/Pull、Rotate、Follow Me、Scale、Flip、Offset |
| Principal | Select、Make Component、Paint Bucket、Eraser |
| Sandbox | From Contours、From Scratch、Smoove、Stamp、Drape、Add Detail、Flip Edge |
| Section | Section Plane、Display Section Plane、Display Section Cut、Display Section Fill |
| Solid Tools | Outer Shell、Intersect、Union、Subtract、Trim、Split |
| Dynamic Components | Interact、Component Options、Component Attributes |
| Views | Iso、Top、Front、Right、Left、Back、Bottom |
| Standard | New、Open、Save、Cut、Copy、Paste、Erase、Undo、Redo、Print、Info（文件/剪贴板命令，非建模工具） |
| Styles / Shadows / Tags / Warehouse / Trimble Connect / Add Location / Classifier / Measurements | 样式、阴影、标签、仓库、协作、定位、BIM、Measurements 框——非建模工具，本稿仅列名，范围由方案定 |

Large Tool Set 只能停靠在窗口左侧；其余工具栏可停靠顶部/底部（Toolbars 文章）。

---

## 3. Draw 菜单与 Tools 菜单（重建稿，顺序未核实）

Help Center 没有发布 Tools/Draw 菜单的逐项顺序表。以下按各工具文章中“可在以下位置找到”的表述重建，**分组与归属有官方依据，菜单内顺序无官方依据**，需 Sen 真机截图确认后才能定稿为“完整复刻规格”。

**真机核实（2026-11-17）：** Tools/Draw/Camera/Edit 四个菜单的主列表顺序已按 Sen 真机截图核定，逐项转录见方案 §2.2；本节重建稿中的推断项以方案 §2.2 为准。绘图 3 组子菜单已展开核实（见方案 §2.2），标准视图子菜单已展开核实（见方案 §2.2），实体工具、撤销隐藏/取消锁定、模型交错待展开核实。

### 3.1 Draw 菜单（有据的部分）

- **Draw > Lines**：Line、Freehand（Freehand 文章：“Under the Draw menu, the Lines submenu”）。
- **Draw > Shapes**：Rectangle、Rotated Rectangle（Rotated Rectangle 文章：“Draw > Shapes > Rotated Rectangle”）、Circle、Polygon（归属按工具栏 Drawing 分组推断）。
- **Draw > Arcs**：Arc、Pie、2-Point Arc、3-Point Arc（Arcs 文章：“The Draw > Arcs submenu”）。
- **Draw > Sandbox**：From Contours、From Scratch（多方一致；Smoove 等是否也在 Draw > Sandbox 下未核实）。
- 其余 Draw 菜单项（如是否含 3D Text）未核实。

### 3.2 Tools 菜单（有据的部分）

各工具文章明确提到位于 Tools 菜单的：Select、Lasso（Selecting Geometry 文章列 Tools menu）、Offset（“Tools menu”）、Section Plane（“Tools > Section Plane”）、3D Text（“Tools > 3D Text”）、Dimensions（“Tools > Dimensions”）、Paint Bucket（旧版文档 Tools > Paint Bucket；现行文章未在正文中重申）、Protractor（“Tools > Protractor”，第三方引用，官方现行文章未逐字确认）、Axes（“Tools > Axes”，同上）、Tape Measure（Tools 菜单，旧版文档；现行文章为概述页）、Solid Tools（“Tools menu”；旧版结构为 Tools > Outer Shell + Tools > Solid Tools 子菜单）、Follow Me（Tools 菜单，第三方引用为主）、Move / Push/Pull / Rotate / Scale / Eraser（按 Edit 工具栏对应关系推断在 Tools 菜单）、Flip（Tools 菜单归属未核实）。

Tools 菜单是否还含：Sandbox 子菜单、Dynamic Components 相关、Add Location、Classifier、Search。**菜单逐项顺序必须以真机截图为准**，本稿不编造顺序。

### 3.3 Camera 菜单（有据的部分）

来源：https://help.sketchup.com/en/sketchup/viewing-model

Orbit、Pan、Zoom、Zoom Window、Zoom Extents、Previous、Next、Position Camera、Look Around、Walk、Field of View、标准视图（Top、Bottom、Front、Back、Left、Right、Iso）、Parallel Projection、Perspective、Two-Point Perspective。顺序未核实。

### 3.4 Edit 菜单中与建模直接相关的命令（有据）

Select All（Ctrl+A）、Deselect All（Ctrl+T，Windows）、Undo（Ctrl+Z）、Redo、Hide、Unhide、Delete Guides、Make Group、Make Component、Group/Component > Explode。完整 Edit 菜单不在本稿范围（属应用命令而非建模工具），但 Make Group / Explode / Hide / Delete Guides 与建模逻辑强相关，复刻时须一并实现（见 §6 右键菜单）。

---

## 4. 通用机制：推断引擎 + Measurements 框

### 4.1 推断（Inference）类型总表

来源：https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts

**点推断（Point）：** Origin point（原点）、Component Origin Point（组/组件原点/插入点）、Endpoint（端点，绿色圆）、Midpoint（中点，浅蓝/青色圆）、Arc Midpoint（弧中点）、Intersection（交点，红色 X）、On Face（面上点）、On Edge（边上点）、Center（圆/弧/多边形中心）、Guide Point（参考点）、On Line（参考线上点）、On Section（剖切面上成边点）、Intersection with Hidden Section（隐藏剖切面交点）。注：组/组件内部几何的推断显示为洋红色（magenta）。

**线推断（Linear）：** On Red Axis、On Green Axis、On Blue Axis、From Point（自某点的轴向对齐，虚线颜色对应轴向）、Through Point（自起点经悬停点锁定方向）、Parallel（平行于某边，洋红色）、Extend Edge（边的延长线）、Perpendicular（垂直于某边）、Perpendicular to Face（垂直于某面）、Tangent at Vertex（与前一弧顶点相切）。

**形状推断（Shape）：** Square（正方形）、Golden Section（黄金分割矩形）、Half/Quarter/Three-Quarter Circle（半圆/四分之一圆/四分之三圆弧）、Arc Side and Center、Circle/Polygon Center。

**推断优先级行为：** 光标在某位置停留（hover dwell）后，SketchUp 会优先与该点对齐。推断常组合成复合推断。绘图方向/平面颜色会随对齐的轴或几何变为红/绿/蓝/洋红。

### 4.2 推断锁定（全局适用）

| 按键 | 行为 |
|---|---|
| ↑ | 锁定到蓝轴（方向或平面） |
| ← | 锁定到绿轴 |
| → | 锁定到红轴（“Right locks Red”） |
| ↓ | 锁定到平行/垂直推断方向或平面（洋红色） |
| Shift（按住） | 锁定当前活动的推断方向/平面 |
| Shift+Alt（Win）/ Shift+Cmd（Mac） | 锁定绘图平面的同时锁定到同一推断面；Rotate/Protractor 则按 Alt/Cmd 可在保持平面角度的同时把中心移到别处 |
| Alt（Win）/ Cmd（Mac），仅 Line 工具，在已起笔未落笔时按 | 循环切换线性推断状态：All Inferences On（默认）→ All Inferences Off（仅保留 On Face、Guide Point、Midpoint 等非线性推断）→ Parallel and Perpendicular Only |

QRC 2025 写 Line 的锁定键为 Alt、Orbit 的重力关闭为 Alt，与正文（Shift 锁定、Ctrl 关闭 Orbit 重力）矛盾。可能为 QRC 排版错位。**以正文为准，QRC 冲突项待真机核对**（见 §8）。

### 4.3 Measurements 框（VCB）通用规则

来源：https://help.sketchup.com/en/using-measurements-box 、各工具文章。

- 位置：界面右下角。**不要点击它**：操作中直接敲键盘输入，输入内容即显示在框内；输入后按 Enter 生效。
- 含义随活动工具变化（长度、尺寸、距离、角度、半径、边数、比例、坐标等），各工具见 §5。
- **输入后可反复改**：在换工具或开始下一个新操作之前，可多次重新输入；一旦开始新操作/换工具，旧值即不可再用 Measurements 框修改。
- 单位：默认用模板单位；输入时可带单位覆盖：`10"`（英寸）、`10'`（英尺）、`10mm`、`10cm`、`10m`；可混写如 `3' 6"`。
- 分隔符：两个值之间用逗号（英文 locale）或分号（逗号作小数点的 locale）。只改其中一维：`3',` 只改第一维，`,3'` 只改第二维（矩形文章）。
- 负值：沿与鼠标指示相反的方向应用（如矩形 `-24,-24`）。
- 坐标（Move 等）：全局坐标用方括号 `[3', 4', 5']`（相对模型原点）；相对坐标用尖括号 `<3', 4', 5'>`（相对操作起点）。（Moving Entities 文章。Line 工具是否同样支持未在现行正文中确认。）
- 阵列（Move / Rotate 复制后）：`3x` 或 `3*` = 外部阵列（等距续排，与原间距相同）；`3/` 或 `/3` 形式 = 内部阵列（在原位置与第一个副本之间均分）。Measurements 文章表述为 `number + x/*//`；QRC 表述为“先移出第一个副本，输入数字+X/Enter”。两种写法（`3x` 与 `x3`）在不同来源出现，Help Center Measurements 文章用 `3x`，iPad 文章举例用 `x3`——**桌面版是否接受 `x3` 未核实**。
- 角度：直接输数字为度数；坡度用 `8:12`（rise:run）形式（Rotate 文章）。
- 精度/舍入、分数英寸输入（`4' 6 1/4"`）等细节未在现行官方正文中系统说明。

---

## 5. 工具逐项规格

> 阅读说明：每项含。未在官方文本中出现的行为标注，不写入定稿规格。

### 5.1 选择工具

#### 5.1.1 Select（选择）

- **位置：** Getting Started、Large Tool Set、Principal 工具栏、Tools 菜单。**快捷键：** Spacebar。
- **操作：** 单击选中一个实体（边/面/组/组件等），高亮显示；点空白处取消选择。双击组/组件进入其编辑上下文（见 §5.8）。框选：单击拖拽出临时选择框，**向右拖只选完全在框内的，向左拖选完全或部分在框内的**，松开鼠标生效。
- **双击/三击（在组/组件上下文外、针对散几何）：** 双击面 = 选中面 + 全部边界边；双击边 = 选中该边 + 每个相连面；三击任意实体 = 选中全部相连实体（如立方体整体）。
- **修饰键：** Ctrl（Win）= 加入选择集；Shift = 切换选中状态（选/取消）；Ctrl+Shift = 从选择集中减去。
- **推断：** 无绘图推断；悬停/选择时显示 Corner Inference Grips（组/组件包围盒角点推断图标，辅助 Move）。
- **Measurements：** 无。
- **来源：** http://help.sketchup.com/sketchup/selecting-geometry ；https://help.sketchup.com/en/default-keyboard-shortcuts

#### 5.1.2 Lasso Select（套索选择）

- **位置：** Large Tool Set（QRC）。**快捷键：** Shift+Spacebar。
- **操作：** 两种方式：(a) Freehand 自由手绘选择区域，松开鼠标生效；(b) Segments 分段式：空白处单击起笔，后续每次单击新增一段，双击闭合生效。
- **方向规则：** 桌面版 Selecting Geometry 文章称“顺时针起笔包含区域内全部实体，逆时针起笔只含完全在区域内的实体”；iPad 版 Select Tool 文章称相反（顺时针只含完全在内的，逆时针含部分重叠的）。**两者直接矛盾，桌面版规则待真机核对。**
- **修饰键（QRC 2025）：** Shift = 加/减选择；Alt = 加入选择；Shift+Alt = 从选择中减去。与 Select 的 Ctrl 体系不一致，需真机核对。
- **来源：** 同上；QRC 2025 PDF。

### 5.2 绘图工具

#### 5.2.1 Line（直线 / 铅笔）

- **位置：** Getting Started、Drawing、Large Tool Set、Draw > Lines。**快捷键：** L。光标变铅笔。
- **操作：** 单击定起点，移动光标（预览线跟随，长度实时显示在 Measurements 框，线色表示对齐的轴），再单击定终点；可连续画折线，Esc 取消当前线段/重新开始。线（边）是全部模型的结构基础；多条边在同一平面闭合即生成面（见 §5.2.1 注）。
- **长度编辑：** 只要边不围成面，可用 Move 工具拖其端点改长度。
- **修饰键：** 方向键锁定轴向（§4.2）；Shift 锁定当前推断方向；Alt（起笔后）循环切换线性推断开关（§4.2）。Esc 重新开始。
- **推断：** 全部点/线推断；悬停某点可“预置”推断源；绘制中可锁定到面平面。
- **Measurements：** 输长度 + Enter；画完后、画下一条线/换工具前可反复重输改长度。坐标输入 `[x,y,z]` / `<x,y,z>` 是否支持未在现行正文确认。
- **面生成/分割/愈合（Line 文章相关段落）：** 边闭合 → 生成面；在线已存在面上画线 → 分割面；删边会连带删相邻面；删面后重画导致面消失的那条线即可恢复面（愈合）。
- **来源：** https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts

#### 5.2.2 Freehand（徒手画）

- **位置：** Line 下拉、Drawing 工具栏、Large Tool Set、Draw > Lines。**快捷键：** 无默认。
- **操作：** 选工具（光标为带曲线的铅笔）→ 可先用方向键锁定绘制平面（左=绿、上=蓝、右=红，出现锁定提示）→ 按住鼠标拖拽画线（线色对应绘制平面法向的轴），松开结束；首尾相接可闭合为面。
- **实体本质：** 画出的线成为 Curve 实体（多段直线组成），可像单条线一样定义/分割面；整体选中，但推断引擎能看到每一段的点/边推断。
- **修饰键：** 画完后 Ctrl+`-` 减少分段、Ctrl+`+` 增加分段（Win；Mac 为 Cmd）；**不能超过初始笔画产生的分段数**。方向键锁定平面。
- **Measurements：** 无数值输入记载。
- **编辑：** 不围成面时可用 Move 拖端点改长度。
- **来源：** https://help.sketchup.com/sketchup/drawing-freehand-shapes

#### 5.2.3 Rectangle（矩形）

- **位置：** Getting Started、Drawing、Large Tool Set、Draw > Shapes。**快捷键：** R。
- **操作：** 可画在地面、竖直面、已有面上、脱离几何处（对齐轴平面）、或由已有几何推断定位；单击定一角，沿对角线移动，单击定对角；Esc 重来。
- **修饰键（QRC 2025）：** Alt = 从中心开始画。现行正文未提及，需真机核对。
- **推断：** Square（正方形，蓝点 + ScreenTip）、Golden Section（黄金分割，蓝点 + ScreenTip）；Shift 可锁定该推断后拖拽。
- **Measurements：** `长,宽` + Enter（如 `8',20'`）；`3',` 只改第一维、`,3'` 只改第二维；负值反向。单位可覆盖模板单位。
- **来源：** https://help.sketchup.com/sketchup/drawing-basic-shapes ；QRC 2025 PDF（Alt 项）。

#### 5.2.4 Rotated Rectangle（旋转矩形）

- **位置：** 形状工具下拉、Drawing、Large Tool Set、Draw > Shapes > Rotated Rectangle。**快捷键：** 无默认。
- **操作（3 击）：** (1) 可选：方向键预设平面（如左箭头=绿平面）；(2) 单击定第一角；(3) 定第一条边（输精确长度 + Enter，或用推断移到第二端点）；(4) 移动量角器定角度、移离中心定宽度，单击完成。用于画与轴/几何成角度的矩形。
- **修饰键（QRC 2025）：** Shift = 锁定当前方向/平面；Alt = 锁定第一条边的绘制平面（第一次单击后）。
- **Measurements（QRC 2025）：** 定下前两个角后，输 `宽度,角度` + Enter（如 `90,20`）。现行正文未给出该格式，需真机核对。
- **推断：** 量角器平面推断、方向键平面锁定、Shift 角度锁定。
- **来源：** https://help.sketchup.com/sketchup/drawing-basic-shapes ；QRC 2025 PDF。

#### 5.2.5 Circle（圆）

- **位置：** Getting Started、Drawing、Large Tool Set、Draw > Shapes。**快捷键：** C。
- **实体本质：** 圆实体有半径，由多段直线连接；各段作为整体定义面的边/分割面，选一段即选中整个圆；推断引擎仍能看到每段的端点/中点推断。推拉后边显示为平滑（与 Polygon distinct sides 相对）。
- **操作：** 选工具 → Measurements 框显示当前边数（Sides），可先输入改边数 → 单击定圆心 → 移出半径（实时显示）→ 单击完成，生成圆形面。Esc 重来。
- **修饰键（QRC 2025）：** Shift = 锁定当前推断。方向键锁定平面（按 §4.2 通则；圆工具可锁定平面而非方向）。
- **Measurements：** 画前输边数；画完后、换工具/画下一个圆之前可改半径（输数字+单位，如 `6"`/`8'`/`34cm`/`7m`）或边数（数字 + `s`，如 QRC 的 Segments 规则；现行正文只写“可改半径或边数”，`s` 后缀格式未在正文逐字确认）。
- **默认边数：** 现行正文只说“默认边数”，未给出数字。本稿不写 24，需真机核对。之后可随时在 Entity Info 里改 Radius / Segments（右键圆边 → Entity Info）。
- **椭圆：** 画圆 → Scale 工具选中圆 → 拖中点（非角点）手柄拉成椭圆。
- **来源：** https://help.sketchup.com/sketchup/drawing-basic-shapes ；QRC 2025 PDF。

#### 5.2.6 Polygon（多边形）

- **位置：** 形状工具下拉、Large Tool Set、Draw > Shapes。**快捷键：** 无默认。
- **实体本质：** 有半径、≥3 条边、自中心点量起；整体作为一条线定义边/分割面，选一边即选中整个多边形；推断可见每段的端点/中点/From Point。推拉后边显示 distinct sides（与圆的平滑不同）。
- **操作：** 同圆：选工具 → Measurements 框显示当前边数，可输入改边数 → 单击定中心 → 移出半径 → 再单击完成。可画在面上或脱离几何处。
- **Measurements：** 画前/画完后（换工具前）可改边数与半径，规则同圆。
- **来源：** https://help.sketchup.com/sketchup/drawing-basic-shapes

#### 5.2.7 Arc（弧，量角器式）与 5.2.10 Pie（扇形）

- **位置：** Getting Started、Drawing、Large Tool Set、Draw > Arcs。**快捷键：** 无默认（A 是 2-Point Arc）。
- **实体本质：** 弧是含多段直线的单一实体；每段都可作推断；默认 **12 段**；可定义边、分割面。
- **操作（3 击）：** 选工具（光标为铅笔 + 量角器，指示绘制平面）→ 单击定圆心与平面 → 移到起点单击（出现表示半径的虚线）→ 移到终点单击（或输角度值 + Enter）。Arc 生成开放弧线；Pie 生成闭合扇形面。其余完全相同。
- **修饰键：** 画完后立即：输数字 + `s` 改段数（如 `10s`）；输数字 + `c` 按整圆段数定弧段数（如 `20c`）；Ctrl+`+` / Ctrl+`-` 增减段数（Win）。Esc 随时取消/重来。
- **推断：** 量角器平面推断；形状推断 Half/Quarter/Three-Quarter Circle；Tangent at Vertex（与前一弧相切）。
- **Measurements：** 半径、角度、段数（`s`/`c`）。角度输入格式细节未在正文展开。
- **编辑：** Entity Info 改半径/段数；Move 拖弧中点调弧、拖端点调长度与半径；推拉含弧的面会生成可编辑半径的特殊曲面实体。
- **来源：** https://help.sketchup.com/en/sketchup/drawing-arcs

#### 5.2.8 2-Point Arc（两点弧）

- **位置：** 同上，Draw > Arcs。**快捷键：** A。光标为带弧线的铅笔。
- **操作（3 击）：** 单击定起点 → 移到弦终点单击（或输长度 + Enter，生成直线，Measurements 框转为接受 Bulge 值）→ 沿弦垂向移动调 Bulge（凸起距离），方向键锁定平面 → 单击定 Bulge。
- **Measurements：** 画完后立即：默认接受 Bulge 值；输数字 + `R` 改半径；输数字 + `s` 改段数。QRC 2025 同：Bulge 输数字、Radius 输数字+R、Segments 输数字+S。
- **推断：** 端点/中点/弦方向；半圆捕捉（snap to half-circle，第三方表述，官方正文未逐字确认）。
- **来源：** https://help.sketchup.com/en/sketchup/drawing-arcs ；QRC 2025 PDF。

#### 5.2.9 3-Point Arc（三点弧）

- **位置：** 同上。**快捷键：** 无默认。
- **操作（3 击）：** 单击定起点 → 移开后单击定第二点（出现代表 pivot 的小点）→ 移开鼠标出现弧线预览，方向键调平面 → 单击完成。
- **修饰键（QRC 2025）：** Alt+`+`/`-` 改段数（QRC 原文含 Mac Option 表述，Windows 对应键未核实）。
- **Measurements：** 官方正文未给出 3-Point Arc 专用的 Measurements 格式。
- **来源：** https://help.sketchup.com/en/sketchup/drawing-arcs ；QRC 2025 PDF。

### 5.3 编辑/变换工具

#### 5.3.1 Move（移动）

- **位置：** Getting Started、Edit、Large Tool Set、Tools 菜单（推断）。**快捷键：** M。
- **操作：** 先用 Select/Lasso 选中 → 选 Move → 在模型中单击一点作对齐参考点 → 移动鼠标（推断点与 Measurements 值随之变化）→ 单击目标点完成。未预选时可直接点选要移动的项。**拉伸（Stretching）：** 选中部分几何（如一条边、一个面、一个顶点）移动时，未选中相连几何随之变形；移动线端点可改线长；移动弧中点/端点可编辑弧。
- **修饰键：** Ctrl（Win）= 切换复制模式（可连续多次复制）；Shift = 按住锁定当前推断方向；Alt = Autofold（允许移动时增加额外边/面以保持面平整）；方向键锁定轴向。**复制后阵列：** 见 §4.3（`3x`/`3*` 外部、`3/` 内部）。**Stamp 模式**为 iPad 专属工具模式，桌面版无此模式（iPad Move 文章）。
- **推断：** 全部推断；Shift/方向键锁定；Corner Inference Grips 辅助对齐组/组件角点；可锁定到面/轴。
- **Measurements：** 距离（可正可负，如 `20'`、`-35mm`，带单位覆盖模板单位）；全局坐标 `[3', 4', 5']`；相对坐标 `<3', 4', 5'>`。移动中或刚完成后输入均可。
- **特殊：** Move 工具悬停在垂直于期望旋转轴的面上时会出现旋转手柄 + 量角器，可旋转组件（Basic Edits 文章）。细节未展开。
- **来源：** https://help.sketchup.com/en/sketchup/moving-entities-around ；QRC 2025 PDF；https://help.sketchup.com/en/sketchup/basic-edits

#### 5.3.2 Push/Pull（推拉）

- **位置：** Edit、Large Tool Set、Tools 菜单（推断）。**快捷键：** P。
- **操作：** 选工具 → 单击要拉伸的面（面变阴影）→ 移动鼠标扩展（Measurements 框显示拉伸深度）→ 再单击定尺寸。推入模型则切割体积：部分推入只去掉一部分；拖到出现“offset is limited”提示即完全贯穿。适用于任意面（矩形、圆形、抽象面）。
- **修饰键：** Ctrl（Win）/ Option（Mac）= 推拉出面的副本（原面保留在原位），可叠加相同拉伸；**双击另一面 = 对该面应用上一次推拉量**；Ctrl + 双击 = 在现有拉伸上叠加一个相同的新拉伸。
- **推断：** 可推拉到与已有面平齐（用已有面定推拉终点，第三方/QRC 外表述，官方现行正文未逐字确认）；推拉方向恒为面法向。
- **Measurements：** 输精确距离 + Enter；完成前/刚完成后（未选他物前）可重输。负值含义未在正文确认。
- **限制：** 拉伸量小于约 1 英寸（2.54cm）时边会透显（渲染限制）；曲面/平滑面推拉行为未在正文确认。
- **来源：** https://help.sketchup.com/en/sketchup/pushing-and-pulling-shapes-3d ；QRC 2025 PDF。

#### 5.3.3 Rotate（旋转）

- **位置：** Getting Started、Edit、Large Tool Set。**快捷键：** Q。
- **操作：** 选中几何 → 选 Rotate（量角器形光标）→ 把光标移到期望旋转平面上（平面垂直于某轴时光标变红/绿/蓝），Shift 锁定平面（锁定后按 Alt 可在保持平面角度的同时把量角器移到别处推断）→ 单击定旋转顶点 → 单击定角度起点 → 移动并单击完成旋转。**折叠（Folding）：** 沿一条折线旋转：量角器光标自折线一端点单击拖到另一端点松开，定出折叠轴，再旋转。
- **修饰键：** Ctrl = 旋转一个副本（可接阵列 `3x`/`3/` 作环形阵列）；Shift 锁定平面；Alt 释放量角器平面约束（见上）；方向键辅助选平面（第三方转述，官方正文未逐字确认）。
- **推断：** 面法向平面推断、轴向颜色、顶点/端点/中点推断；Corner Inference Grips（2026 新增相关，细节未核实）。
- **Measurements：** 输角度（度，如 `34.1`）；输坡度 `8:12`；负值逆时针。旋转中或刚完成后输入。
- **来源：** Help Center《Flipping, Mirroring, Rotating and Arrays》（prod-aws 镜像，英文正文已通过搜索摘要核对）；QRC 2025 PDF。

#### 5.3.4 Flip（翻转）与 Flip Along（沿轴翻转命令）

- **Flip 工具：** 位于 Getting Started、Edit、Large Tool Set。快捷键：无默认（QRC 列 Flip，无键）。操作：预选几何或激活后悬停单击开始 → 出现三个轴向翻转平面，单击/拖拽目标平面完成翻转（绕红/绿/蓝轴镜像）。修饰键：Ctrl 切换翻转/复制（QRC）/ 进入 Copy 模式后拖平面到期望位置松开生成镜像副本（正文）。Measurements：无。
- **Flip Along 命令：** 右键组/组件 → Flip Along → Component's Red / Green / Blue（Basic Edges 文章）。与 Flip 工具的关系（Flip 工具是否为 Flip Along 的可视化替代、Flip Along 是否仍保留）。
- **来源：** 《Flipping, Mirroring, Rotating and Arrays》；https://help.sketchup.com/en/sketchup/basic-edits ；QRC 2025 PDF。

#### 5.3.5 Scale（缩放）

- **位置：** Getting Started、Edit、Large Tool Set。**快捷键：** S。
- **操作：** 选中几何 → 选 Scale → 出现黄色包围盒 + 绿色手柄（角手柄、边手柄、面手柄）。**角手柄** = 等比缩放（保持比例）；**边/面手柄** = 单向拉伸/挤压。单击手柄后该手柄与对侧手柄变红，Measurements 框显示 100%；移动鼠标缩放，Esc 重来。缩放整个模型改用 Tape Measure（量一距离后输目标尺寸，确认 resize 提示）。
- **修饰键（QRC 2025 + 摘要）：** Ctrl = 按住绕中心缩放；Shift = 按住等比缩放（不扭曲）。现行英文正文全文未能打开（prod-aws 抓取失败），以上引自搜索摘要 + QRC，需二次核对。
- **Measurements：** 输比例因子（如 `1.5` = 150%）；输带单位的长度（如 `10m`）则缩放到该绝对尺寸；多值输入（如 `10m,10',10`）的说法仅见论坛旧帖。角手柄缩放时可输三维比例？。
- **组件缩放：** 可缩放单个实例；右键 Reset Scale / Scale Definition（见 §6）。Live Component 缩放手柄为 2026 新增，属 Live Components 范围。
- **来源：** Help Center《Scaling Your Model or Parts of Your Model》（摘要）；QRC 2025 PDF。

#### 5.3.6 Offset（偏移）

- **位置：** Getting Started、Edit、Large Tool Set、Tools 菜单。**快捷键：** F。
- **操作：** 可偏移线或面。偏移线须先选中 ≥2 条相连且共面的线。选 Offset → 单击选中的线段或面 → 移动鼠标定偏移距离（Measurements 框显示距离）→ 单击完成。偏移弧会生成不可编辑的 Curve 实体（原弧仍可编辑）。
- **修饰键（QRC 2025）：** Alt = 允许结果重叠。现行正文未提及。
- **双击复用：** 刚做完一次偏移后，双击另一面即以相同偏移量对该面偏移（旧版正文；现行精简正文未保留该句）。
- **Measurements：** 输数字 + 单位 + Enter；换工具/改图前可反复重设距离。
- **推断：** 共面约束；偏移方向由鼠标侧决定。
- **来源：** https://help.sketchup.com/en/sketchup/offsetting-line-existing-geometry ；QRC 2025 PDF。

#### 5.3.7 Follow Me（跟随路径）

- **位置：** Edit、Large Tool Set、Tools 菜单（推断）。**快捷键：** 无默认。
- **前提：** 一个截面（profile，闭合面，须大致垂直于路径，不必与路径相连）+ 一条连续边构成的路径；路径与截面须在同一组/组件上下文内。
- **自动方式：** Select 选中连续路径边 → 激活 Follow Me（选中状态保留但不高亮）→ 单击截面，截面沿整条路径拉伸。
- **手动方式：** 激活 Follow Me → 单击并拖拽截面沿路径移动，光标触及路径时路径高亮为红色 → 到达路径末端单击完成；Esc 重来。若路径起始边不接触截面，拉伸自该边起算，而非自截面起算。
- **车削（Lathed）：** 画圆作路径 + 半截面（cutaway）对齐圆心 → 选中圆 → Follow Me 单击截面，生成回转体。
- **修饰键（QRC 2025）：** Alt = 以面的周长作拉伸路径。现行正文未提及。
- **Measurements：** 无数值输入记载。
- **Procedural Follow Me（2027，基线外）：** 生成非破坏性程序化组件，可事后编辑路径与截面；Entity Info 无专属控件。是否纳入待 Sen 定。
- **来源：** http://help.sketchup.com/article/3000096 （Extruding with Follow Me）；QRC 2025 PDF。

#### 5.3.8 Eraser（橡皮擦）

- **位置：** Getting Started、Principal、Large Tool Set。**快捷键：** E。
- **操作：** 单击一条边 → 删除该边及相邻面；单击拖拽可连续擦除多条边。**Eraser 工具本身不直接删面**——面是随其边界边被删而消失；要只删面须右键面 → Erase。删除边/面可制造开口；删错后 Undo 或重画线愈合。
- **修饰键：** Ctrl（Win）/ Option（Mac）= 切换 Soften/Smooth 模式（软化+平滑边，见 §6.4）；Shift = 隐藏（Hide）而不删除；Alt = 取消软化/平滑（QRC 2025）。另有来源称 Ctrl+Shift 取消软化，与 QRC 的 Alt 说法冲突，待真机核对。
- **Measurements：** 无。
- **来源：** https://help.sketchup.com/en/sketchup/erasing-and-undoing ；https://help.sketchup.com/en/sketchup/softening-smoothing-and-hiding-geometry ；QRC 2025 PDF。

#### 5.3.9 Paint Bucket（油漆桶）+ Sample（取样）

- **位置：** Getting Started、Principal、Large Tool Set、Tools 菜单（推断）。**快捷键：** B。激活即打开 Materials 面板。
- **操作：** 在 Materials 面板选材质 → 单击面/组/组件上色。预选多个面/组/组件后单击其中之一，材质应用于整个选择集。画在组/组件上时，只影响内部仍为 Default 材质的面，已有显式材质的面不受影响（第三方转述，官方正文未逐字确认）。
- **修饰键（QRC 2025，Windows）：** Ctrl = 填充材质（涂所有相邻同材质面）；Shift = 替换材质（涂全模型同材质面）；Ctrl+Shift = 在同一对象内替换材质；Alt = 按住取样材质（变吸管）。注：iPad 版有 Sample / Object Faces / Connected Faces / All Faces 四种工具模式，桌面版以修饰键实现对应行为。
- **推断/Measurements：** 无。
- **材质系统要点（范围相关）：** 材质 = 颜色 + 纹理图 + 不透明度；Materials 面板含 Select / Edit 页；纹理定位用右键 Texture > Position（四色图钉：红移、绿缩放旋转、蓝切变、黄扭曲，第三方表述）；默认面色：正面白、反面蓝（样式 Face 设置）。PBR 材质、Generate Textures（AI）为 2025/2026 新增，是否纳入复刻待 Sen 定。
- **来源：** QRC 2025 PDF；https://help.sketchup.com/en/sketchup-ipad/paint-bucket-tool （iPad 模式对照）；https://help.sketchup.com/zh-cn/navigating-materials-panel （Materials 面板）。

### 5.4 测量/构造/标注工具

#### 5.4.1 Tape Measure（卷尺）

- **位置：** Getting Started、Construction、Large Tool Set、Tools 菜单（推断）。**快捷键：** T。
- **三种用途：** (a) 测距：单击起点 → 移到终点，距离显示在 Measurements 框；Esc 换起点重测。(b) 建参考线/参考点（见 §5.4.1a）。(c) 缩放整个模型/选中部分：量一距离后输目标尺寸 + Enter，确认 resize 提示（QRC：“Resize: measure a distance, type intended size, and Enter”）。
- **§5.4.1a 参考线/参考点规则（Using Guides 文章 + QRC）：** 从**边**拉出 → 无限长参考线（平行于该边）；从**端点/交点**拉出 → 参考点（带尾线）；从端点拉到另一端点 → 过两点的参考线。参考线/点为临时虚线，不干扰几何，可作推断。Ctrl = 切换“创建参考线 / 仅测量”模式（默认创建参考线；按 Ctrl 关闭创建）。用 Select/Eraser 单删，或 Edit > Delete Guides 全删（当前上下文内）。
- **修饰键：** Ctrl 切换创建参考线；方向键锁定推断方向。
- **Measurements：** 测距读数；建参考线时输偏移距离；建参考点时输距离或坐标（`[x,y,z]`/` <x,y,z>`，旧版文档说法）；resize 时输目标尺寸。
- **来源：** https://help.sketchup.com/en/sketchup/measuring-angles-and-distances-model-precisely ；https://help.sketchup.com/en/using-guides ；QRC 2025 PDF。

#### 5.4.2 Protractor（量角器）

- **位置：** Construction、Large Tool Set、Tools 菜单（推断）。**快捷键：** 无默认。
- **操作：** 测角与建带角度参考线。量角器颜色与起始平面一致；可悬停不同部位或用方向键选平面，Shift 锁定平面 → 单击定角顶点 → 定参考方向 → 移动定角度。建参考线时须先定顶点与参考方向，再输角度。
- **修饰键（QRC 2025）：** Ctrl = 切换是否创建参考线；方向键 = 切换锁定旋转平面。
- **Measurements：** 输角度（度）或坡度（如 `1:9`、`4:12`，旧版文档说法）。
- **推断：** 平面推断、Shift 平面锁定、顶点推断。
- **来源：** 同上两文；QRC 2025 PDF。

#### 5.4.3 Axes（坐标轴）

- **位置：** Construction、Large Tool Set、Tools 菜单（推断）。**快捷键：** 无默认。
- **概念：** 全局坐标系（原点 0,0,0）不可改；Axes 工具改的是**绘图/工作坐标系**（初始与全局一致），影响工具推断方向与太阳方向等；Scenes 可保存 Axes Location。
- **操作：** 激活后双击任意点立即把轴系放到该点；或 3 击：单击定原点（红色虚线轴随光标）→ 单击定红轴方向（默认红轴激活，按 Alt 可改选蓝/绿轴）→ 移动并单击定其余两轴。右键面 → Align Axes 可把轴系对齐到面；右键轴线 → Move（仅移原点不转方向）/ Reset（恢复默认）/ Hide（隐藏）/ Place（重放）/ Align View（相机对齐）。
- **Measurements：** 无记载。
- **组件轴：** 右键组件 → Change Axes 可重定义组件原点与轴向。
- **来源：** Help Center《Adjusting the Drawing Axes》（多语言镜像摘要已核对）；论坛关于全局/绘图坐标系的说明（非官方，转述时已标注）。

#### 5.4.4 Dimensions（尺寸标注）

- **位置：** Construction、Large Tool Set、Tools > Dimensions。**快捷键：** 无默认。
- **操作：** 选工具（光标变箭头）→ 选线/圆/弧 → 拖出放置尺寸线。可标注线长、圆直径、弧半径；尺寸实体与所选实体关联，随模型变化动态更新。手动改文字后不再动态更新。右键尺寸 → Edit Text / Text Position（Start/Center/End）。
- **尺寸类型细节（线性/对齐/直径/半径的判定规则、两点标注、标注平面推断）**：现行英文正文全文未能打开（抓取失败），仅凭摘要，**细节未核实**，需二次核对或真机确认。
- **来源：** Help Center《Adding Text, Labels, and Dimensions to a Model》（摘要）；https://help.sketchup.com/en/context-menu-items-entities （Dimension 右键项）。

#### 5.4.5 Text（文字 / 标签）

- **位置：** Construction、Large Tool Set。**快捷键：** 无默认。
- **两种文字：** (a) Screen text（屏幕文字）：固定于屏幕，不附着实体，用于整模型标签；(b) Leader text（指引文字）：带指引线/箭头指向特定实体。均由 Text 工具创建。右键指引线 → Arrow（None/Dot/Closed Arrow/Open Arrow）、Leader（View Based/Pushpin/Hidden）、Edit Text。
- **操作细节（单击空白处 vs 单击实体、文字框编辑、字体/字号设置位置）**：现行正文全文未能打开，**细节未核实**。
- **来源：** 同上。

#### 5.4.6 3D Text（3D 文字）

- **位置：** Construction、Large Tool Set、Tools > 3D Text。**快捷键：** 无默认。
- **操作：** 选工具 → 弹出 Place 3D Text 对话框 → 输入文字、选字体/字号/对齐、选 Filled（生成面）/ Extruded（拉伸厚度）→ 放置到模型中（生成真实边/面几何，可再 Move/Rotate/Scale）。对话框各选项（字体、高度、粗体/斜体、填充/拉伸、放置平面）细节未在摘要中展开。
- **来源：** Help Center《Adding Text, Labels, and Dimensions to a Model》（摘要）。

### 5.5 剖面

#### 5.5.1 Section Plane（剖切面）

- **位置：** Section 工具栏、Large Tool Set、Tools > Section Plane。**快捷键：** 无默认。
- **操作：** 插入前确保除目标组/组件上下文外无其他选中/打开的实体 → 选工具 → 单击一个面放置剖切面（剖切面随面法向对齐；Shift 可锁定方向，旧版说法）→ 弹出命名/符号对话框（旧版行为，现行正文未重申）。剖切面切开模型以便向内看，不移动/隐藏几何。
- **同一上下文内只有一个活动剖切**（激活一个即停用同上下文其他剖切面，Entity Context Menus 文章）；不同组/组件上下文可各有活动剖切（多剖切同时显示的做法，第三方说法）。
- **配套开关（Section 工具栏 / View 菜单）：** Display Section Planes（显示全部剖切面）、Display Section Cuts（显示全部剖切效果）、Display Section Fill（剖切填充）。平面可见性与剖切效果可见性可分别控制；单个剖切面可右键 Hide（之后不再随全局开关切换，直到 Unhide）。
- **剖切填充：** Styles 面板 Edit > Modeling Settings > Section Fill 复选框 + 颜色；仅当剖切处几何在组/组件层级内成闭合环时才填充；右键剖切面 → Troubleshoot Section Fill 可标出环开口处的顶点（红圈）。2026/2027 新增按材质的剖切填充图案（hatch），属版本边界。
- **右键菜单：** 见 §6（Active Cut、Align View、Create Group from Slice、Reverse）。
- **移动/旋转剖切面：** 用 Move/Rotate 工具（未在现行正文展开）。
- **来源：** https://help.sketchup.com/en/sketchup/slicing-model-peer-inside （Creating and Using Section Planes）；https://help.sketchup.com/en/context-menu-items-entities

### 5.6 实体布尔工具（Solid Tools，Pro）

> 共通前提：Solid = 有限闭合体积的组/组件，无缺面、无不交于边的面。工具位于 Tools 菜单、Solid Tools 工具栏、Procedures 工具栏（仅 Union/Subtract/Intersect）。两种用法：预选后右键 Solid Tools 子菜单执行，或先激活工具再依次点选实体。Union/Outer Shell 结果成为一个 Group。Subtract/Trim 的点选顺序决定谁切谁。

| 工具 | 行为 | 点选顺序 |
|---|---|---|
| Outer Shell | 只保留重叠实体的外表面，删除内部几何（含内部空腔） | 任选 ≥2 个，可继续追加 |
| Union | 合并 ≥2 个实体为单一实体，保留重叠处的内部空隙 | 任选 ≥2 个，可继续追加 |
| Subtract | 第一实体切第二实体，**切削体被删除** | 先选切削体，再选被切体；预选时按选择顺序判定 |
| Trim | 同 Subtract，但**切削体保留**在模型中 | 同上 |
| Intersect | 只保留重叠部分的几何 | 任选 ≥2 个 |
| Split | 沿相交边分割重叠实体（结果为三部分：两者各减去重叠 + 重叠体本身，第三方表述；官方正文只说“沿相交边分割”） | 选第一实体，再选相交的第二实体 |

- **快捷键：** 均无默认。
- **Measurements/推断：** 无。
- **Procedural 变体（2027，基线外）：** Procedural Union / Subtract / Intersect 生成程序化组件，保留原始实体、可事后编辑、Entity Info 有 Controls（可反转相减顺序、选择是否保留原始实体）。是否纳入待 Sen 定。
- **来源：** https://help.sketchup.com/en/sketchup/modeling-complex-3d-shapes-solid-tools

### 5.7 沙盒地形工具（Sandbox Tools）

> 共通：生成/编辑 TIN（Triangulated Irregular Network，三角网），结果包为一个 Group。工具栏须经 View > Toolbars 开启；From Contours / From Scratch 亦在 Draw > Sandbox 下。地形须为“函数型”（function）：垂直线只交地形于一点，带悬挑/洞穴的地形无法用这些工具处理（第三方转述 Help Center）。

| 工具 | 行为（官方依据程度） |
|---|---|
| From Contours | 选中不同高度的等高线 → 激活 → 生成 TIN Group。等高线须先用 Move + Measurements 抬到各自高度。 |
| From Scratch | 激活 → 单击定 TIN 起点 → 用鼠标或 Measurements 定长宽，生成扁平矩形 TIN。网格间距可用 Measurements 输入（旧版说法）。 |
| Smoove | 选中 TIN 区域 → 激活（区域内顶点高亮）→ Measurements 输半径 → 移动鼠标改高程（输值更精确；负值成洼、正值成丘）。作用半径内顶点按衰减移动。 |
| Stamp | 把建筑轮廓/物体底面“压印”进地形，生成平坦基座并与周围坡度融合。要求（Help Center 所述前提，细节未展开）：物体须在 TIN 上方、须为组/组件等。 |
| Drape | 把位于 TIN 上方的边投影到地形表面（如道路、路径）。操作：选中边 → 激活 Drape → 单击 TIN。细节。 |
| Add Detail | 在 TIN 上增加细节（细分三角网）。操作细节未在官方摘要中展开。 |
| Flip Edge | 翻转相邻两三角形的公共边，消除等高线转地形后出现的不 wanted 平坦区。单击目标边。细节。 |

- **快捷键：** 均无默认。**Measurements：** Smoove 半径/高程、From Scratch 长宽/间距（部分未核实）。
- **来源：** https://help.sketchup.com/en/sketchup/creating-terrain-scratch ；https://help.sketchup.com/en/sketchup/sculpting-and-fine-tuning-terrain ；https://help.sketchup.com/en/sketchup/toolbars （Sandbox 工具栏构成）。Stamp/Drape/Add Detail/Flip Edge 的官方细节页未找到全文，**本节除 From Contours/From Scratch/Smoove 外均为弱依据**，需 Sen 定是否纳入首期范围。

### 5.8 相机/视图工具

#### 5.8.1 Orbit（环绕）

- **位置：** Camera 工具栏、Getting Started、Large Tool Set、Camera > Orbit。**快捷键：** O。中键按住拖拽可临时 Orbit（任何工具下）；中键双击重定视图中心（QRC）。
- **操作：** 选工具 → 在绘图区单击 → 任意方向移动，光标绕绘图区中心旋转。双击绘图区使模型居中。
- **修饰键：** Viewing 文章称按住 Ctrl（Win）/ Option（Mac）可侧滚相机（暂停“重力”保持竖边竖直）；QRC 2025 称 Alt。**两者矛盾，待真机核对。** Orbit 下按住 Shift 临时切换为 Pan。
- **来源：** https://help.sketchup.com/en/sketchup/viewing-model ；QRC 2025 PDF。

#### 5.8.2 Pan（平移）

- **位置：** 同上，Camera > Pan。**快捷键：** H。临时切换：三键鼠标按住滚轮 + 左键；或 Orbit 下按住 Shift；QRC 称 Shift+中键拖拽。
- **操作：** 选工具 → 单击拖拽，相机沿画面平面垂直/水平移动。
- **来源：** 同上。

#### 5.8.3 Zoom（缩放）+ Field of View（视野）

- **位置：** Camera 工具栏、Getting Started、Camera > Zoom。**快捷键：** Z。滚轮滚动可随时缩放（以光标为中心；上滚放大、下滚缩小）。
- **操作：** 选工具 → 单击向上拖放大、向下拖缩小（以屏幕中心为缩放中心）。
- **Field of View：** 选 Zoom 或 Camera > Field of View → 输度数或毫米值；或按住 Shift 拖拽 Zoom 手动调视野（QRC 同）。FOV 值范围/默认值未在正文确认。
- **来源：** 同上；QRC 2025 PDF。

#### 5.8.4 Zoom Window（窗口缩放）/ Zoom Extents（充满视图）/ Previous / Next

- **Zoom Window：** 无默认快捷键。单击拖拽画框，松开后框内区域充满绘图区。
- **Zoom Extents：** Shift+Z。单击即显示整个模型并居中。
- **Previous / Next（Camera 菜单）：** 返回上一视图 / 前进到下一视图（视图历史）。工具栏按钮为 Previous（QRC）/ Undo Previous Camera View（Toolbars 文章）。快捷键未核实。
- **来源：** 同上。

#### 5.8.5 Position Camera（放置相机）/ Look Around（环视）/ Walk（漫游）

- **位置：** Camera 工具栏、Large Tool Set、Camera 菜单。**快捷键：** 均无默认。
- **Position Camera：** 单击模型中一点 → 相机视点置于该点正上方 5' 6"（默认眼高）；Measurements 输新值改高度。或单击一点后拖拽到目标方向，定出视点 + 朝向（两步法，摘要未展开细节）。用完后 SketchUp **自动切换到 Look Around**。
- **Look Around：** 模拟定点转头：单击拖拽左/右/上/下转动视线；Measurements 框随时接受 Eye Height 值（相对地面，而非所站表面）。光标为眼睛。
- **Walk：** 模拟行走：单击拖拽开始走，出现小十字准星，离准星越远走得越快；上/下/左/右移动穿越模型，可上下坡/楼梯并保持眼高；默认开启碰撞检测（不能穿墙），可用修饰键覆盖（**具体修饰键未在摘要中确认**）。Walk 仅在 Perspective 模式下可用（旧版说法）。
- **来源：** Help Center《Walking through a Model》（摘要，多语言镜像一致）；https://help.sketchup.com/en/sketchup/viewing-model （Camera 菜单归属）。

#### 5.8.6 标准视图与投影模式（Camera 菜单命令，非工具）

- 标准视图：Top、Bottom、Front、Back、Left、Right、Iso。
- 投影：Parallel Projection（正交，线长按比例）、Perspective（默认透视）、Two-Point Perspective（两点透视，两消失点）。
- 来源：同 Viewing 文章。

### 5.9 其他工具/命令（边界项，是否复刻待 Sen 定）

| 项 | 说明 | 官方依据 |
|---|---|---|
| Make Component | 选中几何 → 生成组件（定义 + 实例），弹 Create Component 对话框（名称、描述、轴、粘附/切割面选项）。快捷键 G。 | Default Shortcuts；Grouping/Components 文章摘要 |
| Search | Shift+S，搜索命令/工具列表。 | Default Shortcuts；QRC |
| Interact / Component Options / Component Attributes / Configurator | 动态组件（Dynamic Components）交互与参数。属组件系统扩展，非核心建模工具。 | Toolbars 文章；QRC |
| Classifier | BIM/IFC 分类。 | Toolbars 文章 |
| Add Location | 地理定位（导入地形/影像/3D 建筑）。 | Toolbars 文章 |
| Live Components / Modify Face（Chamfer/Fillet/Inflate/Twist/Wave） | 参数化 Live 组件；右键 Face > Modify Face。2025/2026 功能，范围待定。 | Entity Context Menus 文章 |
| Soften Edges 面板 | 按法向夹角阈值批量软化/平滑（Angle between normals 滑杆、Smooth normals、Soften coplanar）。Window > Default Tray > Soften Edges。 | Softening 文章 |
| Back Edges（K） | 显示背面边（虚线）。视图开关，非工具。 | Default Shortcuts |
| Image Igloo（I） | Photo Matching 相关。 | Default Shortcuts |

### 5.10 组与组件的操作语义（工具之外的核心逻辑，摘要）

- **Group：** 选中几何 → Edit > Make Group / 右键 Make Group；也可无选中时 Edit > Make Group 建空组。复制组后编辑其中一个副本不影响其他副本（副本自动独立）。单击选中整体；双击进入编辑上下文（其余模型淡化，组边界变虚线）；上下文外单击空白或右键 Close Group 退出。
- **Component：** 定义（Definition）+ 实例（Instance）；编辑任一实例，所有实例同步更新。Make Unique 使选中实例脱离原定义（多选时共用一个新定义）。组可转组件（右键 Make Component）；组件转组须先 Explode 再成组。
- **Explode：** 右键/ Edit > Group/Component > Explode，容器消失，几何回到父上下文；炸开后内部实体继承容器的 Tag（旧版说法）。
- **Lock/Unlock：** 锁定后不可移动/编辑。**Change Axes：** 重定义组件轴。**Reset Scale / Reset Skew / Scale Definition：** 见 §6。
- **来源：** Help Center《Grouping Geometry》（摘要）、《Basic Edits》；https://help.sketchup.com/en/context-menu-items-entities

---

## 6. 右键上下文菜单（按实体类型）

来源（主）：https://help.sketchup.com/en/context-menu-items-entities （2026-09-29 更新，8 min read）。该文按实体类型列出菜单项；**未列出的项不等于不存在**（见 §6.5 缺口说明）。

### 6.1 几乎所有实体共有（All）

| 菜单项 | 含义 |
|---|---|
| Entity Info | 打开 Entity Info 面板/对话框 |
| Erase | 删除选中实体（含面；区别于 Eraser 工具不直接删面） |
| Make Component / Make Group | 把选中几何建成组/组件（单个实体或已是组/组件时不可用） |
| Hide / Unhide | 隐藏/取消隐藏（隐藏实体显示为 ghosted ghost 态——原文如此；通常须开 Hidden Geometry 才可见） |
| Save Out | 保存选中实体：To Device / To Trimble Connect / To 3D Warehouse |
| Reload | 自源文件重载：From Device / From Trimble Connect / From 3D Warehouse |
| Zoom Selection | 相机缩放到选中整体可见并居中 |

### 6.2 按实体类型

**3D Polyline：** Divide、Explode、Explode Curve、Find Center、Select（子菜单）、Soften。
**Circle：** Convert to Polygon、Divide、Explode Curve、Find Center、Select、Soften。
**Component：** Change Axes、Dynamic Components（Component Options、Component Attributes、Swap Component、Redraw）、Edit Component、Explode、Intersect Faces（With Model / With Selected / With Context）、Lock/Unlock、Make Unique、Reload、Reset Scale、Reset Skew、Save As、Scale Definition、Unglue、3D Warehouse。
**Curve：** Convert to Polygon、Divide、Explode Curve、Find Center、Select、Soften。
**Dimension：** Edit Text、Invert Selection、Text Position（Start/Center/End）。
**Face/Surface：** Align View、Align Axes、Area（选中/按 Tag/按材质计总面积）、Combine Textures（须两张平行纹理面）、Intersect Faces、Make Unique Texture、Modify Face（Chamfer/Fillet/Inflate/Twist/Wave，Live Component 参数窗）、Orient Faces（使相连面与选中面朝向一致）、Reverse Faces（翻转正反面）。
**Group：** Edit Group / Close Group、Explode、Intersect Faces、Lock/Unlock、Make Component、Reset Scale、Reset Skew、Soften/Smooth Edges（打开 Soften Edges 面板）、Unglue。
**Image：** Export、Explode、Invert Selection、Reload、Shadows（Cast/Receive）、Unglue、Use As Material。
**Leader Line：** Arrow（None/Dot/Closed Arrow/Open Arrow）、Edit Text、Leader（View Based/Pushpin/Hidden）。
**Line（Edge）：** Divide、Select、Soften。
**Polygon：** Explode Curve、Find Center、Select、Soften。
**Section Plane：** Active Cut（勾选；激活即停用同上下文其他剖切面）、Align View、Create Group from Slice（在剖切面与面相交处生成成组的新边）、Reverse（反转剖切方向）。

**Select 子菜单（边/面相关）：** Bounding Edges、Connected Faces、All Connected、All With Same Tag、All With Same Material、Invert Selection；Deselect Faces（反向操作）；Deselect Edges（仅边选择集时，见 Selecting Geometry 文章）。

### 6.3 关键右键命令的行为细则

- **Divide（等分）：** 右键线/弧 → Divide → 线上出现分点标记；移动鼠标或输数字改分段数（Measurements 框），单击/Enter 确认。线围成曲面时不可用。分段数输入方式细节未在正文展开。
- **Weld Edges（焊接边）：** 选中相交/相邻的多条边 → 右键 Weld Edges → 生成单一 Curve 实体（Entity Info 显示为 Curve）。**该文 Entity Context Menus 表中未列 Weld Edges**，依据为《Dividing, Splitting, and Exploding Lines and Faces》文章。
- **Explode Curve：** 把弧/圆/多边形/曲线打散为普通边。
- **Convert to Polygon：** 把圆/弧转为可编辑的多边形弧，拉伸时生成标准分面。
- **Intersect Faces：** With Model（与全部重叠实体求交）、With Selected（仅与选中项求交）、With Context（在当前上下文内两实体求交）。求交生成交线/新面；求交后常需手动清理多余几何。
- **Reverse Faces / Orient Faces：** 反转面的正反面；Orient 使全部相连面朝向与选中面一致。面的正反面以颜色区分（默认正面白、反面蓝）。
- **Soften（右键）：** 软化分面表面。右键菜单中的 Soften 与 Eraser+Ctrl、Soften Edges 面板的关系：三者均可软化/平滑；Soften Edges 面板提供角度阈值批量控制。**右键 Soften 是否同时 Smooth（着色平滑）未在该文确认**。
- **Flip Along：** 未列入 Entity Context Menus 文章的 Component/Group 表，但 Basic Edits 文章明确记载（右键组件 → Flip Along → 三轴）。**该文的表不完整，Flip Along 应补列**。
- **Area：** 计选中实体的总表面积，可按 Tag / 材质分项（2026 新增功能表述，细节未展开）。

### 6.4 边属性：Soft / Smooth / Hidden（与右键/橡皮擦联动）

来源：https://help.sketchup.com/en/sketchup/softening-smoothing-and-hiding-geometry

- **Soft：** 边被隐藏，且其边界的面合并为一个 Surface 实体（单击选中整个曲面）。
- **Smooth：** 增加着色使面看起来平滑；单独应用 Smooth 时边仍可见。
- **Hidden：** 边不可见，但相邻面**不**合并为 Surface 实体。
- Eraser + Ctrl 与 Soften Edges 对话框均同时应用 Soft + Smooth。Soften Edges 面板：Angle between normals 滑杆（小于该角的边被软化/平滑）、Smooth normals 复选、Soften coplanar（合并共面边，**永久删除这些边**，不可选择性撤销——第三方表述）。
- Hide：选中 → 右键 Hide 或 Edit > Hide；View > Hidden Geometry 显示隐藏几何（虚线）；选中后 Unhide 恢复；Edit > Unhide All / Last（未在正文确认）。

### 6.5 右键菜单缺口说明（该官方表未覆盖、但他处有据的项）

以下项在 Entity Context Menus 文章的表中**未出现**，但在其他官方文章/界面中有据，复刻清单须补列，菜单归属需真机核对：

- Weld Edges（边选择集）、Flip Along（组/组件）、Texture 子菜单（Position / Edit / Reset 等，面）、Make Unique Texture（已在 Face 表中）、Soften/Smooth Edges（Group 表中有；Face/Edge 表中未列）、Entity Info 中 Radius/Segments 编辑（圆/弧/多边形边）、Change Axes（Component 表中有）、Axes 右键菜单（Place/Move/Reset/Hide/Align View，独立于实体菜单）、Guide（参考线）右键菜单（未找到官方表）、空白处右键菜单（未找到官方表）。

---

## 7. 默认快捷键总表（Windows，官方）

来源：https://help.sketchup.com/en/default-keyboard-shortcuts （2026-10-21 更新）。**全表仅 21 项**，其余工具/命令均无默认快捷键（可自定义）。

| 工具/命令 | 快捷键 |
|---|---|
| Select | Spacebar |
| Lasso Select | Shift+Spacebar |
| Paint Bucket | B |
| Eraser | E |
| Line | L |
| Rectangle | R |
| Circle | C |
| 2 Point Arc | A |
| Move | M |
| Push/Pull | P |
| Rotate | Q |
| Scale | S |
| Offset | F |
| Tape Measure | T |
| Orbit | O（+ 单击拖拽；中键拖拽亦可） |
| Pan | H（+ Shift+单击拖拽） |
| Zoom | Z（+ 滚轮） |
| Zoom Extents | Shift+Z |
| Make Component | G |
| Image Igloo | I |
| Back Edges | K |
| Search | Shift+S |

另：Select All Ctrl+A、Deselect All Ctrl+T（Windows）、Undo Ctrl+Z（Edit 菜单命令，非工具快捷键表所列，但正文有据）。

---

## 8. 不确定 / 需问 Sen 的事项

### 8.1 须 Sen 在真机上确认（截图/实测最可靠）

1. **Tools 菜单与 Draw 菜单的逐项内容与顺序**（含子菜单划分、分隔线位置）。Help Center 无完整菜单表，本稿 §3 仅为重建稿，不能作为复刻规格定稿。——请 Sen 截 Tools / Draw / Camera / Edit 四个菜单的图。
2. **Getting Started 与 Large Tool Set 的精确构成与顺序**（Toolbars 文章疑似笔误、QRC 为 2025 版）。请 Sen 截两个工具栏的图。
3. **Circle 默认边数**（官方正文未给数字）。
4. **Lasso 顺时针/逆时针选择规则**（桌面版与 iPad 版官方文章互相矛盾）。
5. **Orbit 侧滚修饰键**：Ctrl（Viewing 文章）vs Alt（QRC 2025）。
6. **Line 锁定键**：Shift（正文）vs Alt（QRC 2025）；以及 Alt 循环切换线性推断在 2026.0 是否存在。
7. **Eraser 取消软化修饰键**：Alt（QRC）vs Ctrl+Shift（论坛/第三方）。
8. **Rectangle 的 Alt 从中心画、Offset 的 Alt 允许重叠、Follow Me 的 Alt 周长路径**：仅 QRC 有载，正文无载，2026.0 是否仍有效。
9. **Rotated Rectangle 的 `宽度,角度` 输入格式**：仅 QRC 有载。
10. **阵列输入是否接受 `x3` 写法**（Help Center 桌面文章用 `3x`，iPad 文章举例 `x3`）。
11. **空白处右键菜单、参考线右键菜单、轴线右键菜单的完整内容**（未找到官方表）。
12. **Scale 工具 Measurements 多值输入、Dimensions/Text/3D Text 对话框细节**（相关英文正文抓取失败，仅凭摘要，细节弱依据）。

### 8.2 须 Sen 拍板范围

13. **Procedural 变体**（Procedural Follow Me / Union / Subtract / Intersect）是否纳入？它们是 SketchUp 2027 功能，Sen 的 26.0.429 没有。建议：首期不纳入，记为二期/可选。
14. **Sandbox 7 工具**是否纳入首期？官方细节弱、地形 TIN 逻辑独立，建议单独立项/后置。
15. **动态组件 / Live Components / Modify Face / Classifier / Add Location / Photo Matching / Scan Essentials** 是否在“建模工具完整复刻”范围内？建议：首期排除，理由是它们属扩展系统而非核心建模逻辑。
16. **相机漫游工具**（Position Camera / Look Around / Walk）是否纳入？Blender 已有 Walk Navigation，复刻程度（眼高/碰撞检测）需定。
17. **标注类**（Dimensions / Text / 3D Text）做到什么深度？（动态关联尺寸、指引线样式、3D 文字字体对话框。）
18. **材质系统深度**：PBR 材质、Generate Textures（AI）、Texture Position 图钉、剖切填充图案（hatch）是否纳入？
19. **LayOut / 3D Warehouse / Extension Warehouse / Trimble Connect / 协作评论**：建议明确排除（非 Blender 插件范畴），请 Sen 确认。
20. **语言**：已定——插件界面语言跟随 Blender 的语言设置（2026-11-17 记忆更新）；工具名以英文原名为准绳，中文译名在统稿时对照 Blender 语言包习惯定。（本稿工具名暂用英文原名。）

### 8.3 本稿已知的弱依据点（复核清单）

- Scale、Rotate/Flip、Text/Dimensions/3D Text、Axes、Walking、Grouping 的部分细节引自搜索摘要或非英文镜像，未能全文打开英文正文；写规格定稿前应二次打开核对。
- QRC 2025（非 2026 版）用作修饰键补齐来源；2026 版 QRC 未找到。QRC 与正文冲突处已逐项标注。
- iPad/Web 版文档仅作对照引用（Lasso 方向、Paint Bucket 模式、Move 的 Stamp 模式），桌面版行为以桌面文章为准；凡两者冲突处已标注。
- 本稿未核实：各工具在组/组件上下文内的行为差异细节（如 Follow Me 要求同上下文、推断在组内变洋红色除外）、锁定（Lock）对各工具的影响、隐藏几何对推断的影响、超大模型性能相关限制。

---

## 9. 来源列表

### 官方 Help Center（全文已打开核对）

- Toolbars：https://help.sketchup.com/en/sketchup/toolbars
- Default Keyboard Shortcuts：https://help.sketchup.com/en/default-keyboard-shortcuts
- Introducing Drawing Basics and Concepts：https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts
- Using the Measurements Box：https://help.sketchup.com/en/using-measurements-box
- Selecting Geometry：http://help.sketchup.com/sketchup/selecting-geometry
- Drawing Basic Shapes：https://help.sketchup.com/sketchup/drawing-basic-shapes
- Drawing Arcs：https://help.sketchup.com/en/sketchup/drawing-arcs
- Drawing Freehand Shapes：https://help.sketchup.com/sketchup/drawing-freehand-shapes
- Moving Entities Around：https://help.sketchup.com/en/sketchup/moving-entities-around
- Pushing and Pulling Shapes into 3D：https://help.sketchup.com/en/sketchup/pushing-and-pulling-shapes-3d
- Offsetting a Line from Existing Geometry：https://help.sketchup.com/en/sketchup/offsetting-line-existing-geometry
- Extruding with Follow Me：http://help.sketchup.com/article/3000096
- Modeling Complex 3D Shapes with the Solid Tools：https://help.sketchup.com/en/sketchup/modeling-complex-3d-shapes-solid-tools
- Viewing a Model：https://help.sketchup.com/en/sketchup/viewing-model
- Entity Context Menus：https://help.sketchup.com/en/context-menu-items-entities
- Creating and Using Section Planes：https://help.sketchup.com/en/sketchup/slicing-model-peer-inside?Itm_source=blog&itm_medium=text&itm_campaign=Vues-orthographiques-Enscape
- SketchUp Desktop 2026.0 Release Notes：http://help.sketchup.com/en/release-notes/sketchup-desktop-20260

### 官方 Help Center（搜索摘要核对，未全文打开）

- Precise Modeling with Measurements：https://help.sketchup.com/en/sketchup/measuring-angles-and-distances-model-precisely
- Using Guides：https://help.sketchup.com/en/using-guides
- Erasing and Undoing：https://help.sketchup.com/en/sketchup/erasing-and-undoing
- Softening, Smoothing, and Hiding Geometry：https://help.sketchup.com/en/sketchup/softening-smoothing-and-hiding-geometry
- Dividing, Splitting, and Exploding Lines and Faces：https://help.sketchup.com/en/sketchup/dividing-splitting-and-exploding-lines-and-faces
- Basic Edits：https://help.sketchup.com/en/sketchup/basic-edits
- Creating 3D Terrain：https://help.sketchup.com/en/sketchup/creating-terrain-scratch
- Sculpting and Fine Tuning Terrain：https://help.sketchup.com/en/sketchup/sculpting-and-fine-tuning-terrain
- Walking through a Model：https://help.sketchup.com/en/sketchup/walking-through-model （URL 据论坛引用，正文摘要来自多语言镜像）
- Adding Text, Labels, and Dimensions to a Model：https://prod-aws-help.sketchup.com/en/sketchup/adding-text-labels-and-dimensions-model （英文正文抓取失败，依据搜索摘要）
- Scaling Your Model or Parts of Your Model：http://prod-aws-help.sketchup.com/en/sketchup/scaling-your-model-or-parts-your-model （抓取失败，依据搜索摘要 + QRC）
- Flipping, Mirroring, Rotating and Arrays：https://prod-aws-help.sketchup.com/ru/sketchup/flipping-mirroring-rotating-and-arrays （镜像，依据搜索摘要 + QRC）
- Adjusting the Drawing Axes：https://help.sketchup.com/it/sketchup/adjusting-drawing-axes （多语言镜像摘要）
- Grouping Geometry：https://prod-aws-help.sketchup.com/fr/sketchup/grouping-geometry （镜像摘要）
- Navigating the Materials Panel：https://help.sketchup.com/zh-cn/navigating-materials-panel
- Paint Bucket Tool（iPad，对照）：https://help.sketchup.com/en/sketchup-ipad/paint-bucket-tool
- Move Tool / Scale Tool / Eraser Tool / Measurement Tools（iPad，对照用）：https://help.sketchup.com/en/sketchup-ipad/move-tool 等

### Trimble 官方速查卡

- Quick Reference Card 2025 Windows：https://download.sketchup.com/QRC2025/HC-QRC2025-en-SU-Windows.pdf （修饰键补齐来源；与正文冲突处已标注）

### 版本判定依据

- Ruby API Release Notes（Procedures API 为 SU2027.0 新增；SU2026.0 = 26.0.429）：https://ruby.sketchup.com/file.ReleaseNotes.html

---

*调研员 A 完成。定稿规格须待 Sen 确认 §8.1 菜单截图与 §8.2 范围拍板后，由团队负责人统稿。*
