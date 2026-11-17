# 调研 B：SketchUp 建模逻辑核心规格 + Blender 数据模型映射

- 调研日期：2026-11-17
- 参照基线：SketchUp 2026（Sen 真机 SketchUp 26.0.429，Windows 11）；SketchUp 侧以 SketchUp Help Center（help.sketchup.com）为准，Blender 侧以 Blender Python API 文档（docs.blender.org）为准。
- 性质：只做调研，不含实现代码。凡未在官方文档原文中确认的行为，均在正文或文末“不确定”中标注，不当作已确认规格写。

## 0. 版本基线陷阱（必读）

1. **Help Center 已混入 SketchUp 2027 内容。** 2026-10-22 发布的 SketchUp 2027（27.0.264）新增 Procedures / Procedural Tools：Procedural Follow Me、Procedural Solid Tools、Copy Along、AutoFit Live Components，均为非破坏性程序化组件。Help Center 的 Follow Me 词条（2026-10-21 更新）已同时描述 classic Follow Me 与 Procedural Follow Me。本调研以 **SketchUp 2026 的 classic 行为**为基线；Procedural 体系是否纳入范围，需问 Sen（见 §11 Q1）。
2. **Blender 版本基线：4.x–5.x 全适配（Sen 已定，2026-11-17 记忆更新）。** 截至调研时，Blender 4.5 LTS（2025-09-09 首发，支持至 2027-07）与 Blender 5.2 LTS（2026-07-14，据第三方汇总，支持至 2028-07）并存；5.0 有 Python API 破坏性改动（`bpy.props` 字典式访问移除、BGL 移除等，据第三方汇总，未逐项在官方文档复核）。Sen 已定适配范围为 Blender 4.x–5.x，界面语言跟随 Blender 的语言设置——因此插件须做版本分支/兼容层（`bpy.app.version` 门控），并用 Blender 的翻译机制处理界面语言，不得只适配单一版本。本调研引用的 bmesh / Mesh API 均为 4.x 长期稳定的部分，5.x 兼容性须在实现前用 `docs.blender.org/api/current/` 逐项复核，并在 4.5 LTS 与 5.x 真机上双测。
3. **推断颜色未在官方文本中逐项给出。** 官方词条用图示表达各推断图标颜色，文本抓取无法读取 RGB。§1 的颜色标注除 Midpoint（官方正文明确写 light blue dot）外，均来自旧版手册/社区教程等二手来源，**须在 Sen 的 SketchUp 2026 真机上截图核对后才能定稿**。

## 总览：核心机制 → Blender 映射（摘要）

| SketchUp 机制 | Blender 映射（推荐） | 难度 |
|---|---|---|
| 推断引擎（全量） | 自研：BVH ray_cast + 候选点/线/面投影 + GPU 绘制 + 锁定状态机；不复用 Blender 内置 Snap（语义不同） | ★★★★★ 最高 |
| 边+面粘性几何、自动成面/愈合 | 单 Mesh + bmesh + 自研平面环检测/面重建；Blender 无自动成面，必须自写 | ★★★★☆ |
| Push/Pull | `bmesh.ops.extrude_face_region` + 自研“推到对面自动封口/打洞”逻辑 | ★★★★☆ |
| Follow Me（classic） | 自研放样（轮廓帧 + 路径分段 + 角部斜接）；Blender 无等价一键算子 | ★★★★☆ |
| Offset | `bmesh.ops.offset_edgeloops` / `inset_region` 仅作参考，SketchUp 语义需自研或重验证 | ★★★☆☆ |
| Intersect Faces | `bmesh.ops.bisect_plane` / Boolean EXACT 均不等价；需自研面-面求交 + 边分裂 | ★★★★☆ |
| Soften/Smooth/Hide | 边自定义层存 soft/smooth/hide 标志 + `BMEdge.smooth` / `BMFace.smooth` + 绘制层过滤；“Surface 实体”需自研选集语义 | ★★★☆☆ |
| Group / Component | Group = 独立 Mesh 的 Object（+ Empty 父级嵌套）；Component = 多 Object 共享同一 Mesh 数据块（Linked Duplicate 语义） | ★★★☆☆ |
| 材质（正反面/贴图） | 面 `material_index` + Loop UV；正反面双材质 Blender 无原生支持，需自定义层/双面方案取舍 | ★★★★☆ |
| Section Plane | 视图裁剪（`SpaceView3D.clip_planes` 不可编程依赖时改用 Boolean/绘制裁剪）+ 自研 Slice 生成边 | ★★★☆☆ |
| Tags / Scenes / Styles | Tags = 自定义属性 + Collection/可见性映射；Scenes = 相机+可见性快照；Styles 仅复刻与建模相关的显示项 | ★★☆☆☆ |

> 核心判断：**SketchUp 的“灵魂”在推断引擎 + 自动成面/粘性几何 + 编辑上下文（Context）三件套**，Blender 均无原生等价物，必须自研。bmesh 只提供拓扑操作原语，不提供 SketchUp 语义。任何“调几个 bpy.ops 就能复刻”的预期都不成立。

---

## 1. 推断引擎 Inference

官方来源：https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts （2026-09-29 更新，11 min read）

### 1.1 SketchUp 侧定义与行为（官方）

- 推断分三大类：**点推断（Point）**、**线性推断（Linear）**、**形状推断（Shape）**；SketchUp 经常把多个推断组合成复合推断。组件/动态组件有自己的推断类型。
- 每个推断有自己的颜色与 ScreenTip（悬停提示文字）。例：Line 工具悬停于另一条线中点时，显示浅蓝圆点 + “Midpoint”。
- 悬停鼓励（Encouraging）：把光标停在想推断的位置上，SketchUp 会优先与该点对齐；需要的推断不立即出现时，靠“悬停后慢慢移回”来引导。
- 推断线颜色：绘制方向/平面平行于轴或其他几何时，边或平面会变成红/绿/蓝/洋红（magenta）。

**点推断（官方表，全量）：**

| 类型 | 官方含义 |
|---|---|
| Origin point | 三条绘图轴交点 |
| Component Origin Point | 组/组件内的轴原点，即组/组件默认插入点 |
| Endpoint | 线、弧或弧段的端点 |
| Midpoint | 线、边或弧段的中点 |
| Arc Midpoint | 弧的中点 |
| Intersection | 线与另一条线或面相交的点 |
| On Face | 位于面上的点 |
| On Edge | 位于边上的点 |
| Center | 圆、弧或多边形的中心 |
| Guide Point | 参考点 |
| On Line | 沿参考线（Guide Line）上的点 |
| On Section | 绘图工具在剖面平面上生成边的点 |
| Intersection with Hidden Section | 隐藏剖面生成的边与绘图工具的交点 |

**线性推断（官方表，全量）：**

| 类型 | 官方含义 |
|---|---|
| On Red / Green / Blue Axis | 与红/绿/蓝绘图轴线性对齐 |
| From Point | 从某点出发的线性对齐；虚线颜色对应轴方向 |
| Through Point | 从一点起画，悬停另一点后按住 Shift，锁定“从起点穿过第二点”的方向 |
| Parallel | 与某边平行 |
| Extend Edge | 现有边的延长线 |
| Perpendicular | 与某边垂直 |
| Perpendicular to Face | 与某面垂直 |
| Tangent at Vertex | 弧的顶点与先前所画弧的顶点相切 |

**形状推断（官方表，全量）：**

| 类型 | 官方含义 |
|---|---|
| Square | 各边相等的矩形 |
| Golden Section | 符合黄金比例的矩形 |
| Half / Quarter / Three-Quarter Circle | 正好为半圆、四分之一圆、四分之三圆的弧 |
| Arc Side and Center | 绘图工具悬停于弧上时显示弧的边与中心推断 |
| Circle/Polygon Center | 悬停于圆边上时显示圆的中心推断 |

**锁定（官方表，全量）：**

| 按键 | 行为 |
|---|---|
| ↑ | 锁定绘制方向/平面到蓝轴 |
| ← | 锁定到绿轴 |
| → | 锁定到红轴（“Right locks Red”） |
| ↓ | 切换锁定到推断边/面的平行/垂直方向（即任何变洋红色的方向）；绘制方向与被推断的面边均变洋红 |
| Shift | 锁定当前活动的绘制方向/平面（如正沿蓝轴画，按住 Shift 即锁定蓝轴推断） |
| Shift+Alt（Win）/ Shift+Cmd（Mac） | 按住 Shift 锁定绘制平面的同时，锁定到同一被推断面的平面；Rotate / Protractor 工具则按 Alt/Cmd 解放工具、保持同一平面移动中心 |

补充（官方）：Circle、Rotate 等工具锁定的是**平面**而非方向——用带颜色的方向锁定工具轴/法线方向来锁定平面。

**Linear Inferencing Toggle（Line 工具，官方）：** 开始画线后、结束前，按 Cmd（Mac）/ Alt（Win）循环切换三种状态：All Inferences On（默认）→ All Inferences Off（忽略全部线性推断，但仍可找 On Face、Guide Point、Midpoint 等其他推断）→ Parallel and Perpendicular Only（仅平行/垂直线性推断）。

**参考线推断（Guide 推断）：** Guide Point / On Line 两类点推断即参考线体系的入口；参考线本身由 Tape Measure / Protractor 生成（工具清单与行为归调研 A）。推断引擎须把 Guide 实体纳入候选集，且 Guide 不参与成面。

**长度/角度推断：** 官方词条未单列“长度推断”类型。实际行为上，长度通过 Measurements/VCB 数字输入 + 长度捕捉（Length Snapping，见 §9）实现；角度通过 Protractor / Rotate 的角度捕捉实现。**不要虚构一个名为“长度推断”的官方推断类型**；本插件中长度/角度的精确控制归 VCB + Snapping 规格（调研 A/C 负责），推断引擎只负责“方向/位置”候选。

**推断图标颜色（⚠️ 二手来源，待真机核对）：** Endpoint 绿、Midpoint 青/浅蓝、Intersection 黑、On Face 蓝、On Edge 红、Center（据旧手册为蓝/绿系，未确认）。来源：2006 年 Google SketchUp 用户手册“Integration Types”节、MasterSketchUp 教程。SketchUp 2026 的实际颜色/图标形状须 Sen 截图核对；插件实现时颜色应做成可配置常量，不要写死。

### 1.2 Blender 侧映射方案

Blender 内置 Snap（`ToolSettings.use_snap`、吸附到顶点/边/面/增量/体积）语义与 SketchUp 推断差异极大：无 From Point / Through Point / Parallel / Perpendicular / Extend Edge / 形状推断，无 Shift/方向键锁定状态机，无 ScreenTip。因此**必须自研推断引擎**，Blender 只提供底层拾取与绘制：

- **拾取：** `bpy_extras.view3d_utils.region_2d_to_origin_3d` + `region_2d_to_vector_3d` 由鼠标得射线；`mathutils.bvhtree.BVHTree.FromObject / FromBMesh` + `BVHTree.ray_cast` 求最近命中面；`Object.ray_cast` 作备选（注意：Edit Mode 下 Object 的 Mesh 数据不同步，须用 BMesh 的 BVH 或 `bmesh` 数据自建拾取，见 §10.3）。
  - 官方来源：https://docs.blender.org/api/current/bpy_extras.view3d_utils.html ；BVHTree：https://docs.blender.org/api/current/mathutils.bvhtree.html
- **候选生成（每帧，鼠标移动时）：**
  1. 点候选：射线附近（屏幕空间阈值，如 10px 内）的顶点（Endpoint）、边中点（Midpoint）、弧/圆中心（Center，须由“曲线实体”元数据提供——Blender 网格无圆/弧概念，中心须自存，见 §10.4）、边-边/边-面交点（Intersection，预计算或按需计算）、面内点（On Face，由 ray_cast 命中点提供）、边上最近点（On Edge，射线到边的最近点投影）。
  2. 线性候选：从当前起点 + 鼠标方向，与三轴、已有边方向（Parallel/Perpendicular/Extend）、悬停参考点（From Point）求夹角/共线，取最佳匹配。
  3. 形状候选：仅在 Rectangle / Arc 等工具内生效（Square、Golden Section、半圆/四分之一圆），由各工具在推断引擎回调中注入。
  4. 优先级：点推断 > 线性推断 > 自由面点；悬停鼓励用“最近悬停点加权”实现（记录悬停停留 > 约 300ms 的参考点，优先匹配其轴向/平行/垂直线——停留阈值无官方值，需实现时调参并由 Sen 真机体感验收）。
- **锁定状态机：** 独立模块，状态 = {无锁定， 轴锁定（R/G/B）， 洋红锁定（平行/垂直）， Shift 锁定当前方向/平面， 平面锁定}；方向键按下即锁定、再按同键解除（官方未明说“再按解除”，社区共识为再按解除——列入不确定项，须 Sen 确认）；Shift 为按住锁定、松开解除。锁定后鼠标移动只改变沿锁定方向/平面的参数（标量距离或平面内 2D 点）。
- **绘制：** 推断标记（圆点/方块）、推断虚线、预览边/面用 GPU 绘制（`gpu` + `blf` 画 ScreenTip 文字；Blender 5.0 已移除 BGL，须用 `gpu` 模块——版本基线锁定后复核）。标记颜色/形状做成主题常量表。
- **性能：** 大模型下每帧全量候选不可行。须做空间索引（BVH + 屏幕空间候选裁剪：只考察鼠标附近 N 像素内的元素）+ 脏标记缓存（几何不变时复用候选集）。

### 1.3 难点与取舍

1. **复合推断**（如 From Point + On Face 交点、两条推断线交点）是 SketchUp 最难复刻的部分：需实现“锁定第一约束后，在约束线上再求第二约束交点”的两阶段求解。建议分阶段：先做单约束 + 轴锁定 + From Point，再做双约束交点。
2. **“悬停鼓励”的时序语义**无官方量化描述，只能凭经验调参，真机体感验收。
3. **圆/弧中心推断**依赖“曲线实体”元数据（见 §10.4）；若第一阶段不做曲线实体，则 Center 推断只能对“以插件工具画的圆/弧”生效，对导入网格无效——须在方案中明说。
4. **参考线（Guide）** 须有独立实体类型与绘制/拾取通道，不能复用 Mesh 边。

---

## 2. 面的生成与愈合（粘性几何）

官方来源：
- https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts （Creating a face / Dividing faces / Healing deleted faces）
- https://help.sketchup.com/en/sketchup/dividing-splitting-and-exploding-lines-and-faces （Splitting / Healing / Divide / Weld）

### 2.1 SketchUp 侧定义与行为（官方）

- **基本实体：** 边（Edge/Line entity）与面（Face）是 SketchUp 模型的基本实体；边构成所有模型的结构基础。
- **成面：** “When you join several lines into a shape, they form a face.”（把几条线连成一个形状，即形成面。）Rectangle、Circle、Polygon 等形状工具也直接生成面。官方未在该词条写明“共面”二字，但面的平面性是 SketchUp 几何的前提：**非共面的闭合环不生成面**（此为 SketchUp 几何常识 + 论坛/教程共识，官方词条未逐字写出，列入不确定项，措辞上写“同一平面内的闭合环生成面”并标注来源级别）。
- **面分裂：** 在已有面上画一条线/曲线（起点终点落在面的边上），即把面切分成更小的面。
- **删边的影响：** 用 Eraser 点一条边，删除该边及其相邻面；右键点击面选 Erase 只删面（边保留）。删边造成开口（Opening）。
- **愈合（Healing）：**
  - 删掉分隔面的线/弧，面恢复成一个整面（“Removing the line or arc dividing a face heals the face”）。
  - 误删面后：Undo，或**重画导致面消失的那条线，SketchUp 会重新生成面**。
- **边分裂（自动）：** 画新线与已有线/弧相交（不必垂直），即把被穿过的线/弧分裂成段；“看起来是整条线”的段落实际已被分割，选中的只是其中一段。
- **等分（Divide）：** 右键线/弧 → Divide，移动光标改段数，或输入每段长度，点击后分成等长相连线段。
- **焊接（Weld）：** 选多条相交/相邻线段 → Weld Edges，生成一个 Curve 实体（SketchUp 的 polyline 等价物）；Curve 更易整体选择/成组；Curve 推拉时自动生成平滑面；Curve 作 Follow Me 路径时挤出结果的边为隐藏+柔化。
- **炸开曲线（Explode Curve）：** 圆/弧/多边形/曲线由多段组成，选中任一段即选中整体；Explode Curve 后拆成独立边段，可单独选。
- **粘性（Sticky，官方词条未用此词但行为即此）：** 同一编辑上下文（Context）内的边/面相互粘连——移动一条边/面会牵动相连几何；只有组/组件容器能隔离（见 §6）。本调研用“粘性几何”指代该行为集合。

**未在官方词条确认、须标注的细节：**
- 最小边长/清理阈值（社区常说约 0.001 英寸，极小边会被清理）：官方词条未给出数值，**不写入规格数值**，实现时以 Blender 浮点 + 可配置合并距离（merge distance）处理，并请 Sen 确认是否需要模拟“小几何清理”。
- 成面时的环优先级（如大环内有小环时先生成哪个面、重画边后内环面是否需要逐个愈合）：官方词条未述，论坛有案例讨论（删外环边再重画只生成大面，内环面需逐条重画边愈合）。实现规格须定义确定性算法（见 §2.2），并标注“与 SketchUp 原生优先级是否完全一致需真机对比测试”。

### 2.2 Blender 侧映射方案

Blender 的 Mesh/bmesh **没有自动成面**：`bmesh.ops` 的建边、建面全是显式调用；`edgenet_fill` / `edgeloop_fill` 只填充指定边网，不监听拓扑变化。因此必须自研一个**成面/愈合引擎（Face Healing Engine）**，挂在每次几何编辑之后：

- **数据载体：** 每个编辑上下文对应一个 Blender Mesh Object（见 §6/§10），上下文内全部“散几何”存在同一个 Mesh 里（这是粘性的物理基础：共享顶点即粘连）。
- **触发点：** 每次工具提交一条/多条边、删除边/面、移动顶点后，运行增量成面：
  1. 取受影响的边集合，找其所在平面（以边端点拟合平面，容差可配）。
  2. 在平面内做 2D 投影，用平面图环检测找最小闭合环（faces cycles），排除已被面覆盖的环。
  3. 对每个未成面且共面（平面度容差内）的环调用 `bm.faces.new(verts)` 建面；建面前先处理环内已有分裂边（环内有弦 → 应生成多个子面而非一个大面：先对环做约束三角化/多边形分割，再合并共面相邻三角为 n-gon——或直接用环检测找最小环，自然得到子面）。
  4. 删分隔边时：删边后检查其两侧面是否共面且合并后外环仍为简单多边形 → 是则 `bmesh.ops.dissolve_faces` / 手动删两面建一面（愈合）；否则保留两面。
  5. 删边时：同步删除以该边为边界的面（SketchUp 语义），除非该面还有其他边界支撑（bmesh 中删边不会自动删面，须显式处理：先收集 `edge.link_faces`，按规则删面）。
- **边自动分裂：** 新边与同平面已有边相交时，在交点处分裂已有边（`bmesh.ops.bisect_edges` 或手动建顶点+替换边）并分裂新边；交点须做顶点合并（容差内视为同点）。这是成面前置步骤，不做则环检测失效。
- **法线方向：** 新面法线取“朝向当前视图/上方向”的确定性规则（SketchUp 新面默认正面朝上/朝外，细节无官方逐字描述——实现规则须写明并请 Sen 验收；提供 Reverse Faces 修正，见调研 A 右键菜单）。
- **性能：** 全模型环检测在大模型下不可行；必须增量化——只重算受影响平面/连通域。可复用 `bmesh.ops.edgenet_fill` 作单环填充备选，但环检测本身须自写（或用 `mathutils.geometry` 辅助做 2D 几何）。

### 2.3 难点与取舍

1. **环检测 + 共面判定 + 弦分割**是本插件第二难的算法（仅次于推断）。n-gon 带洞（环内有独立闭合环，如面上画圆）时，Blender 的 BMFace **不支持洞**（bmesh 无 HOLES 支持，`USE_BMESH_HOLES` 被禁用——见 Blender 源码注释），须用“外环面 + 内环边 + 内环面分裂”的方式模拟：即内环必须与外环通过分裂边连接，或以外环减内环的三角化再合并。SketchUp 的面是“带内环（inner loop）的面”，Blender 只能用多个面拼——**面模型语义存在根本差异**，规格中必须明确：插件内部以“面片集合 + 逻辑面 ID”表达 SketchUp 的带洞面，显示/选择时按逻辑面合并处理。
2. **浮点容差**：Blender 坐标为 float32（bmesh 内部 float），SketchUp 为 double。长距离/小尺寸模型下共面判定与交点合并的容差需仔细设计（见 §9）。
3. **Undo 粒度**：成面/愈合须与触发它的编辑合并为一次 Undo，否则用户一次 Undo 只撤销成面不撤销画线——须用 Blender 的 Undo 步进控制（调研 C 负责）。

---

## 3. 推拉 Push/Pull

官方来源：https://help.sketchup.com/en/sketchup/pushing-and-pulling-shapes-3d （2026-09-29 更新）

### 3.1 SketchUp 侧定义与行为（官方）

- Push/Pull 可把任意类型的面（圆、矩形、抽象面）拉成 3D 体，或从模型中切掉一块。快捷键 P。
- **拉出：** 点选面 → 移动光标扩展 → Measurements 显示挤出深度 → 再点一次定尺寸；**在选其他东西之前**，可随时输入精确距离 + Enter 修改。
- **双击复用：** 推拉加体积后，**双击另一个面**即以相同距离在该面复制一次挤出；**按住 Ctrl（Win）/ Option（Mac）再双击该面**，则在现有挤出之上叠加一个相同挤出。
- **切除：** 点面 → 向模型内推；推一部分只去掉一部分；**拖到出现 “offset is limited” 提示**即推到头、内容完全移除；再点完成，可用 Measurements 输精确距离。
- 官方词条**未提及**以下社区熟知的行为，须标注为“二手/待核”：
  - Ctrl/Option + 推拉 = 保留起始面、生成新面（“创建新起始面”，用于叠层）；二手来源一致但官方词条未写，须 Sen 在真机确认后写入规格。
  - 推拉到其他面/点时的推断对齐（拉到与某面齐平、拉到某点高度）；官方词条未述，属推断引擎 + Push/Pull 联动，须真机确认细节。
  - 曲面（多片小平面的圆柱侧面）不能一次推拉多个面（教程说法）；官方词条称“可推拉任何类型的面”，两者需调和：单面推拉 vs 预选多面推拉的行为差异须问 Sen / 真机确认。
  - 推拉方向始终沿面法线；推拉过程中面的边若遇非平面/自交时的失败行为：官方未述。

### 3.2 Blender 侧映射方案

- **基础挤出：** `bmesh.ops.extrude_face_region(bm, geom=[face])` 生成挤出几何（该算子本身不做位移），再 `bmesh.ops.translate` 沿面法线移动新顶点；或手动建侧面（对 SketchUp 语义控制更强：侧面材质继承、边 soft/smooth 继承、起始面保留与否）。推荐**手动建侧面**为主（语义可控），`extrude_face_region` 作对照实现。
  - 官方来源：https://docs.blender.org/api/current/bmesh.ops.html
- **交互：** Modal Operator：点面选中（高亮）→ 拖动实时预览（距离 = 鼠标射线在法线上的投影 + 推断修正）→ VCB 输入覆盖距离 → 点击确认。距离记忆：保存“上次推拉距离”供双击复用。
- **推入打洞/封口（关键自研逻辑）：**
  - 向内推时，实时计算挤出面沿法线反向与模型其他面的交点；当挤出面到达对侧面（共面/穿过）时，执行“删除被推出部分 + 愈合开口”：即把挤出体与原体做布尔差后清理内部面。简化实现：推到对侧面时直接删除挤出面与对侧面重叠区域并愈合边界（类似 SketchUp 的“推穿即打洞”）。**这一步不能直接调 Boolean 修改器**（会改变拓扑所有权与材质/选择语义，且对非流形失效）；须在 bmesh 内做受限布尔：仅处理“挤出棱柱 vs 单个体”的相交。
  - “Offset is limited” 的判定：挤出面到达对侧面平面时锁定距离上限，UI 显示提示。
- **双击复用：** 记录上次距离与方向；双击另一面时直接应用；Ctrl+双击时在原挤出顶面再叠加一次（须识别“该面”是上次挤出的顶面）。
- **预选多面：** 若 Sen 确认需要，逐面挤出（各自沿各自法线），相邻面挤出后的侧面缝合另行处理——列入不确定项。

### 3.3 难点与取舍

1. 推入打洞的受限布尔 + 愈合是 Push/Pull 最难处；第一阶段可先实现“拉出 + 推入（不穿透）+ 双击复用”，“推穿打洞”作为第二阶段验收项，但须在方案中明确分阶段。
2. 推拉曲面（圆柱顶面为多边形 n-gon 时无问题；侧面为多片小面时）——SketchUp 圆柱顶面是单个 n-gon 面，推拉无碍；本插件的圆也应生成 n-gon 顶面（见 §10.4），避免多面问题。

---

## 4. 跟随路径 Follow Me（classic）

官方来源：
- https://help.sketchup.com/en/sketchup/extruding-follow-me （旧版词条路径，内容与下条一致；2026-10-21 更新版已混入 Procedural 描述，以 classic 流程为准）
- https://help.sketchup.com/en/procedural-tools （Procedural 体系总述，2027 内容，作范围区分用）

### 4.1 SketchUp 侧定义与行为（官方，classic）

- Follow Me 引导一个面沿一条路径生成 3D 形体；适合沿周长/边缘的收边细节（顶角线、檐沟）与车削体（纺锤、碗）。
- **自动挤出：** ① 画轮廓面，须**大致垂直于路径**（不必与路径相连，只需垂直）；② 用 Select 工具选中连续的一组边作为路径（Shift 加选多边）；③ 激活 Follow Me（选中边不再高亮但保持选中）；④ 点击轮廓面，沿预选路径挤出。**若模型已分组，选择与轮廓须在同一组内才生效。**
- **手动挤出：** 不预选路径：激活工具 → 点击并拖动轮廓面沿路径走，鼠标触到路径时路径高亮为红；若起始边不接触轮廓，Follow Me 从该边开始挤出，而非从轮廓到该边；到达路径终点点击完成。
- **车削：** 轮廓 + 圆形路径（圆边）可车削出碗/瓶等回转体（官方词条有专节，流程同自动挤出，路径为闭合圆）。
- 官方词条**未述**角部处理细节：内外角处的斜接（miter）、尖角拉伸/截断、路径急转弯时轮廓自交的处理、轮廓非严格垂直时的投影规则——均须标注为“实现时须定义算法并真机对比”，不得声称“按官方算法”。

### 4.2 Blender 侧映射方案

Blender 无等价算子（`bpy.ops.mesh` 无 sweep；Geometry Nodes 的 Curve to Mesh / Extrude Mesh 语义不同且不适合交互式 SketchUp 流程）。**自研放样算法**：

1. **输入：** 轮廓面（BMFace，取其外环顶点序列 + 平面法线）+ 路径（有序边链，须连续；自动模式取预选边排序，手动模式取鼠标划过的边序）。
2. **帧计算：** 沿路径每段计算轮廓帧：以路径切线为前进方向，轮廓平面法线对齐切线；相邻段之间用法线插值/平行移动（parallel transport）避免扭转；路径顶点处用**角平分面（miter plane）**求交：轮廓在两段帧之间以角平分面截取，得到斜接缝。
3. **生成：** 每段生成侧面四边形带（轮廓环顶点 × 路径段），首尾封口（首面 = 轮廓面本身，尾面 = 末端轮廓）；路径闭合时首尾缝合；轮廓环带洞时暂不支持（列入限制）。
4. **角部策略（须定义并验收）：**
   - 外角（凸）：miter 延伸，设最大延伸比（如 miter 长度 > 轮廓尺寸 × K 时截断为 bevel，避免尖刺无限拉长——K 值无官方依据，须调参验收）。
   - 内角（凹）：miter 相交处裁剪重叠部分，删除自交侧面并愈合。
   - 锐角/自交：检测到轮廓自交时，取“裁剪后有效部分”或报错提示（取舍须问 Sen：是静默裁剪还是提示失败？）。
5. **材质/平滑：** 侧面继承轮廓面材质；路径为 Curve/焊接曲线时，侧面分段边置 soft+smooth（见 §2.1 Weld 行为）；路径为普通折线时分段边保持硬边。
6. **车削特例：** 路径为闭合圆时，帧计算退化为绕轴旋转放样，与通用算法统一处理即可，无须单独分支（但须测试闭合缝合无裂缝）。

### 4.3 难点与取舍

1. 角部斜接 + 自交裁剪是 Follow Me 的算法核心，工作量与 Push/Pull 打洞相当。
2. 手动模式的“鼠标划过路径识别”（边序推断、回退、分支选择）是交互难点；第一阶段可先做自动模式，手动模式后补——须在里程碑中明确。
3. Procedural Follow Me（2027）不在 2026 基线内；若 Sen 要求“最新版”含 2027，则 Follow Me 须重做为“可编辑的程序化组件”（保留轮廓+路径参数、改输入即重算），工作量翻倍——见 §11 Q1。

---

## 5. 偏移 Offset、交线 Intersect Faces、柔化/平滑边

### 5.1 Offset

官方来源：https://help.sketchup.com/en/sketchup/offsetting-line-existing-geometry （2026-09-29 更新）

**SketchUp 行为（官方）：**
- 偏移 = 画一个与原形状等距的稍大/稍小版本；用于平面图内外墙、轮廓加厚、屋檐等。
- 可偏移线或面。偏移线时须**先选中两条以上相连且共面的线**；偏移面时直接点面。快捷键 F。
- 流程：激活 Offset → 点选中的线段之一或面 → 移动光标定偏移距离（Measurements 显示距离）→ 点击完成；可输入精确距离 + Enter，**在做其他修改或换工具前可反复重置距离**。
- 官方词条未述：偏移极限（Offset Limit，内缩到自交时的上限）、Ctrl 绕过极限、双击重复偏移（社区说法，须核）、偏移弧生成不可编辑 Curve 的细节——列入不确定项。

**Blender 映射：**
- 候选算子：`bmesh.ops.inset_region`（面向区域内缩）、`bmesh.ops.offset_edgeloops`（边环偏移）。两者语义与 SketchUp Offset 不完全一致（inset 针对选中面区域、offset_edgeloops 针对边环），**须逐项对照测试后决定是复用还是自研**，不得直接假设等价。
- 自研备选：平面内 2D 多边形偏移（直线段平移 + 角点求交 + 自交裁剪），复用 §2 的平面投影与环处理；弧/曲线段先离散为折线再偏移，偏移后按 SketchUp 语义标记为 Curve（不可编辑弧参数）。
- 交互：Modal + VCB 距离 + 双击复用（若确认）。

### 5.2 Intersect Faces（交线）

官方来源：Help Center 无独立专篇词条（检索未得）；行为定义来自 Entity Context Menus 词条 + 论坛版主级说明，**来源级别低于其他机制，须标注**：
- https://help.sketchup.com/en/context-menu-items-entities （Intersect Faces：With Model / With Selected / With Context 三档，见下）
- https://forums.sketchup.com/t/directions-to-use-intersect-faces-with-model-and-selection-and-context/43096 （版主 slbaumgartner 的定义，本节主要依据，须 Sen/真机复核）

**SketchUp 行为（综合，⚠️ 非纯官方）：**
- Intersect Faces 在两组面的相交处生成新边。须预选含面的选择（或右键隐式选择）；选中面构成第一组。
- 三档决定第二组：**With Model** = 模型中其他所有位置的面（含嵌套组/组件内）；**With Context** = 仅当前活动编辑上下文内的其他面（含嵌套容器内），仅在打开组/组件编辑时可用；**With Selection** = 与第一组相同的选择（须预选多于一个面，单面无法自交）。
- 生成的新边**始终放在当前活动编辑上下文**中（模型顶层或打开的组/组件内）；在容器外调用时，交线落在容器外、不切割容器内几何——要切割须先打开容器再 With Model。
- 常见副产物：多余边/面、极小边（可能被清理）、大模型下 With Model 很慢（须逐面两两测试）。

**Blender 映射：**
- 无等价算子。`bmesh.ops.bisect_plane` 只能平面切割；Boolean 修改器（EXACT）做体布尔，会改拓扑所有权且要求流形——均不等价于“只生成交线、不删改原面”。
- 自研：两组面逐对求交（三角化后三角-三角求交，或平面求交线 + 线段裁剪到两面内）→ 交线段去重/合并 → 在交线与原面边交点处分裂原面（`bmesh.ops.connect_verts` / 手动分裂 + §2 成面引擎重建被切面）。须用 BVH 做候选对裁剪，否则大模型不可用。
- 三档映射：With Model = 全场景 Mesh 对象（跨上下文取世界坐标求交、结果写回当前上下文对象）；With Context = 当前上下文对象内的面；With Selection = 选中面之间。跨上下文求交须处理对象变换矩阵（世界 ↔ 局部）。

### 5.3 Soften / Smooth / Hide

官方来源：https://help.sketchup.com/en/sketchup/softening-smoothing-and-hiding-geometry （2026-09-29 更新）

**SketchUp 行为（官方）：**
- 边有三个独立属性，组合控制外观：
  - **Soft（柔化）：** 边隐藏，且该边所界定的面成为一个 **Surface 实体**（选其中一面即选整个 Surface）。
  - **Smooth（平滑）：** 边加着色、使面看起来平滑；**单独应用 Smooth 时边仍可见**。
  - **Hide（隐藏）：** 边不可见，但相邻面**不**变成 Surface 实体（与 Soft 的关键区别）。Hide 适用于任何实体。
- Eraser + Ctrl（Win）/ Option（Mac）切换为 Smooth Edges 模式涂抹，即同时 Soft+Smooth；Alt（Win）/ Cmd（Mac）+ 点击撤销柔化/平滑。
- Soften Edges 对话框：选边 → Window > Soften Edges 或右键 Soften/Smooth Edges → 滑块设“将被柔化/平滑的最大角度”（越大柔化越多）；Smooth normals 复选框默认选中（不清则无平滑着色效果）；Soften coplanar 复选框柔化共面面之间的边（“本质上删除那些边”——官方措辞，实际为柔化而非真删除，须注意措辞）。
- Entity Info 可查看/修改单条边的 Soft、Smooth 复选框。
- 隐藏几何：View > Hidden Geometry / Hidden Objects 以虚影显示隐藏实体；隐藏的实体不可选，须显示后才能选；右键 Unhide 恢复。

**Blender 映射：**
- **Smooth：** `BMEdge.smooth`（边平滑标志）+ `BMFace.smooth`（面平滑着色）+ 4.1+ 的 Sharp 边/自定义法线体系。SketchUp 的 Smooth 是“边级平滑着色”，Blender 4.1+ 已移除 `use_auto_smooth`、改为按边 Sharp + 面 Smooth 自动处理——**版本基线锁定后须复核 current 文档**，不得沿用旧版 `use_auto_smooth` 写法。
- **Soft / Hide：** Blender 无边级 Soft/Hide 标志（`BMEdge.hide` 存在但语义为编辑模式隐藏，且不构成 Surface 实体）。须用**边自定义层**（`bm.edges.layers.int` / `bool` 层，存 soft/hide 标志）+ 自研绘制/选择逻辑：
  - 绘制：Soft/Hide 边在正常视图不画边线（须自研边线绘制或用 Overlay 控制——Blender 视口默认画全部边，须用自定义绘制回调过滤，或用 `Mesh` 的边显示控制；具体手段归调研 C 的视口绘制方案）。
  - 选择：Soft 边两侧面视为同一 Surface：点选时做连通域扩展（沿 Soft 边 flood fill），选中整个 Surface；Hidden Geometry 模式下 Soft/Hide 边以虚线显示且可单独选面。
- **Soften Coplanar：** 角度滑块逻辑自研：计算相邻面法线夹角，小于阈值则置 soft+smooth；Soften Coplanar 勾选时共面边（夹角 ≈ 0）也置 soft。

---

## 6. 组 Group 与组件 Component

官方来源：
- https://help.sketchup.com/en/sketchup/grouping-geometry （Grouping Geometry；经 prod-aws 镜像核对，内容一致）
- https://help.sketchup.com/en/sketchup/working-hierarchies-outliner （Hierarchies in the Outliner）
- https://help.sketchup.com/en/context-menu-items-entities （右键菜单：Make Group/Component、Explode、Make Unique 等）

### 6.1 SketchUp 侧定义与行为（官方 + 论坛共识）

- **Object：** 成组后的几何称为 Object，分 Group 与 Component 两类。Group 是“一组几何的选择集合”；Component 是更复杂、可复用的 Object。
- **创建：** 选几何 → Edit > Make Group（或右键 Make Group）；无预选时 Edit > Make Group 创建空组（进入编辑后在内绘图）。Component 创建有对话框（命名、原点/轴、Glue/Cut 选项等——对话框细节归调研 A 的组件创建规格）。
- **隔离（核心）：** 组/组件内的几何与外部几何**不粘连**——容器是粘性的边界。容器可嵌套：组内可有组/组件，组件内可有组/组件。
- **编辑上下文（Context）：** 双击 Object 进入其上下文编辑（其余模型变淡、容器边界变虚线）；点空白处或 Edit > Close Group/Component 退出。编辑只影响当前上下文内的实体；工具（Follow Me、Intersect 等）的生效范围均以 Context 为界。
- **Group vs Component（关键差异）：**
  - Group 副本：每份独立，编辑一份不影响其他副本（实现上 SketchUp 内部曾共享定义、编辑时自动分裂——用户可见行为为“独立”）。
  - Component 副本：全部为同一**定义（Definition）**的**实例（Instance）**，编辑任一实例即更新全部实例与定义；定义在 Components 面板按名列出，可保存复用于其他模型。
  - **Make Unique：** 右键组件实例 → Make Unique，该实例脱离原定义、成为独立新定义，其余实例保持链接。
  - **Explode：** Edit > Group/Component > Explode 或右键 Explode，容器解散、内容回到散几何（可能与周围几何重新粘连）。
  - Group → Component：选中组 → Make Component 转换；Component 有额外能力：改轴、Glue to 面、Cut Opening（在墙面开洞）、Dynamic Components（参数化，见 §6.3）。
- **Outliner：** 树形显示模型的组、组件、剖面平面；可导航、命名、重组层级（拖拽）、控制可见性、搜索过滤；排序分 Tags / Hierarchy 两档；重命名 Group 只改该组，重命名 Component 定义则改全部实例名。
- **命名：** Group 无名时 Outliner 显示 “Group”；Component 以定义名显示。

### 6.2 Blender 侧映射方案（核心架构决策）

| SketchUp | Blender 映射（推荐） | 说明 |
|---|---|---|
| 散几何（顶层 Context） | 一个名为如 `SU_Model` 的 Mesh Object（或每顶层连通域一个对象，见取舍） | 顶层上下文 = 一个 Mesh，共享顶点即粘连 |
| Group | 一个独立 Mesh 的 Object（`obj.data` 独立）；嵌套用 `obj.parent`（Empty 或 Mesh Object 作父级）表达 | 副本 = `obj.copy()` + `data.copy()`（深拷贝），编辑互不影响 |
| Component Definition | 一个共享的 Mesh 数据块（`bpy.data.meshes` 中的一个 Mesh） | 定义即 Mesh 数据块 |
| Component Instance | 多个 Object 共享同一 `obj.data`（Linked Duplicate 语义，Alt-D 等价） | 编辑任一实例的 Mesh 即更新全部实例——Blender 原生支持，无须自研联动 |
| Make Unique | `obj.data = obj.data.copy()`（Single User） | 即 `bpy.ops.object.make_single_user` 的数据版 |
| Explode | 把容器内 Mesh 的几何（经变换矩阵）合并入父上下文 Mesh，删除容器对象 | 须处理变换 + 材质槽合并 + §2 成面重算（爆炸后可能与周围几何成面） |
| 嵌套 | Object 父子链（`parent` + `matrix_parent_inverse`） | Outliner 层级 = Blender Outliner 的父子层级 + 自研 SketchUp 风格面板（调研 C） |
| 编辑上下文 | “活动上下文对象”状态：插件维护 `active_context`（Object 栈）；工具只读写该对象的 Mesh；进入/退出 = 切换活动对象 + 其余对象淡显（`Object.color` / 视图淡化）+ 锁定非上下文对象选择 | Blender 的 Edit Mode 一次只能编辑一个对象，天然契合“单上下文编辑”；多对象编辑须禁用 |
| 组件原点/轴 | Object 的原点（`matrix_world` 平移部分）+ 自定义轴（存 ID Property）；插入点 = 原点 | 组件的局部坐标系即 Object 变换 |
| Glue / Cut Opening | 第一阶段不支持（见 §6.3），组件创建对话框先不做 Glue/Cut 选项，或做占位并明示未实现 | 须问 Sen 优先级 |

**关键取舍（须在方案中明说）：**
1. **“一上下文 = 一 Mesh Object”是本插件的根架构。** 好处：粘性、隔离、组件联动全部由 Blender 数据模型原生承载；代价：顶层散几何若全放一个 Mesh，大模型下 bmesh 全量操作变慢——缓解靠增量算法与 BVH 缓存，不靠拆对象（拆对象会破坏粘性）。
2. **Group 副本的“编辑时自动分裂”不模拟**——直接深拷贝，行为等价且简单。
3. **组件内嵌套组件**：共享 Mesh 数据块只能表达“单层几何共享”；嵌套组件实例（定义 A 内含定义 B 的实例）在 Blender 中须表达为“Object 集合共享”——单个 Mesh 无法包含子 Object。因此：**含嵌套内容的组件定义不能只用一个 Mesh 表达**。方案：组件定义 = 一个 Collection（或一个 Empty 父级 + 子 Object 树），实例 = 该 Collection 的实例化（Collection Instance / `Object.instance_collection`）或整树 Linked Duplicate。Collection Instance 在 Blender 中不可直接编辑内部几何（须进原 Collection 编辑），与 SketchUp “双击任一实例进入定义编辑”有交互差异——须自研“进入实例编辑时跳转到定义 Collection 编辑”的流程。这是组件映射中最容易低估的点，**必须在方案中单列并请 Sen 确认交互取舍**（备选：限制组件嵌套深度为 1，或组件内只允许散几何+不嵌套容器——均须 Sen 定，见 §11 Q4）。
4. **Empty 父级 vs Mesh Object 父级：** 含散几何的容器用 Mesh Object 自身作父级；纯容器（只含子容器、无直接几何）用 Empty 作父级。须统一命名与 Outliner 显示规则。

### 6.3 Dynamic / Live Components（范围外，须 Sen 定）

- Dynamic Components（参数化公式、Component Options/Attributes 对话框）与 Live Components（Trimble 参数化云组件）均属 SketchUp Pro/Studio 的扩展体系，复刻工作量巨大（公式引擎 + 对话框 + 3D Warehouse 联动）。**建议明确列为范围外**，第一阶段只做普通组件；若 Sen 坚持要，须单独立项评估。
- Procedural Components（2027）同理见 §0/§4。

---

## 7. 材质 Materials

官方来源：
- https://help.sketchup.com/en/sketchup/applying-materials （Applying Materials）
- https://help.sketchup.com/en/sketchup/replacing-material （Replacing a Material，Paint Bucket 替换模式）
- 纹理定位（Texture > Position，四钉 Fixed/Free Pins、Projected）：Help Center 无独立专篇（检索未得专篇 URL），行为来自教程/论坛共识，**来源级别标注为二手，须真机复核**。

### 7.1 SketchUp 侧定义与行为

- **Paint Bucket（B）：** 可预选面/边再上材质，或直接点面/边上材质；恢复默认色用 In-Model 库顶部的 Default。样式（Styles）可阻止面/背面/边显示材质。
- **容器上材质：** 可对组/组件整体上材质（预选多对象或逐个点）。**容器材质 vs 面材质优先级：面上有直接材质时，面材质优先于容器材质显示；面无直接材质时显示容器材质。**（论坛/教程共识，官方词条称“可对组/组件上材质”但未逐字写优先级规则——标注来源级别。）
- **取样：** Alt + Paint Bucket = Sample（取样器），点已上材质的面取样，再点另一面应用。
- **替换模式（官方，Replacing a Material）：**
  - All Matching（Shift）：替换模型中所有与点击实体相同材质的面。
  - All Connected（Ctrl / Mac Option）：替换与选中面相连且相同材质的面。
  - All on Same Object（Ctrl+Shift / Option+Shift）：替换同一组/组件内相同材质的面。
- **正反面：** 每个面有正面（默认白）与反面（默认蓝灰）；材质可分别赋予正反面（点哪面赋哪面）；反面朝外会导致 Solid 判定失败、渲染发黑等问题——“正面朝外”是建模规范的一部分（见 §10.5 Solid 判定）。
- **贴图坐标（Texture Position，二手来源）：** 每面独立存 UV；右键面 → Texture > Position，四钉模式：红钉锚点（移动）、绿钉缩放/旋转、蓝钉剪切/垂直缩放、黄钉扭曲；Fixed Pins（四钉联动约束）与 Free Pins（四钉独立，透视匹配）两种模式；Texture > Projected 将纹理设为投影模式，取样后涂到曲面/Surface 上可保持连续对齐。材质本身有真实世界尺寸（纹理宽高，如 600mm 瓷砖），贴图按真实尺寸平铺。

### 7.2 Blender 侧映射方案

- **材质载体：** Blender `Material` 数据块 + Mesh 的材质槽（`Mesh.materials`）+ 每面 `material_index`（BMFace: `material_index`）。SketchUp 材质（颜色/纹理图/透明度/真实尺寸）→ Blender Principled BSDF 节点树（Base Color + Image Texture + Alpha）；SketchUp 材质库（In-Model）→ Blender `bpy.data.materials` + 插件材质面板（调研 C）。
- **正反面双材质（核心取舍）：** Blender 的面只有一个 `material_index`，**无原生正反面双材质**。备选方案：
  - A. **双面拆分法：** 不采用——会破坏拓扑。
  - B. **自定义层法（推荐）：** 每面存两个材质索引：`material_index` = 正面，Loop/面自定义 int 层 = 反面；视口显示用自定义着色/绘制区分正反面（须调研 C 的视口方案配合）；导出时按需处理。代价：Blender 原生视口/渲染器只认 `material_index`，反面材质在原生显示中不可见——须自研绘制或接受“反面材质仅在插件视图模式可见”。
  - C. **几何节点/着色器法：** 用 Geometry Nodes 的 Backface 判断 + 双材质混合，显示上可行但编辑语义（点反面上材质）仍须自研拾取区分正反面（ray_cast 法线方向判定）。
  - **须问 Sen**：反面独立材质是否为刚需？若否，第一阶段只做正面材质 + 反面统一默认色显示，大幅降低工作量（见 §11 Q5）。
- **容器材质：** Object 级材质槽（`material_slots[].link = 'OBJECT'`）对应容器材质；面无直接材质（`material_index` 指向空/默认槽）时显示对象级材质——Blender 的材质链接（OBDATA vs OBJECT）与此语义接近但不完全相同，须在实现中显式处理优先级（面材质 > 对象材质 > 默认）。
- **UV：** 每面独立 UV 与 Blender 的 Loop UV 天然对应：`Mesh.uv_layers`（Loop 层）/ bmesh `bm.loops.layers.uv`。SketchUp 的“真实尺寸平铺”→ UV = 世界坐标 / 纹理尺寸（按面平面投影生成初始 UV）；Texture Position 四钉 → 自研 Modal 工具改 Loop UV（仿射变换：平移/旋转/缩放/剪切/透视——Free Pins 的透视须用单应性矩阵改 UV，Loop UV 可直接存结果，无须额外数据结构）。
- **Projected 纹理：** 取样时记录源面 UV 投影矩阵（平面投影），涂到目标面时按同一投影矩阵生成 UV——数据上就是 UV 生成规则，无须特殊存储；须在材质/面自定义层存“projected”标志与投影平面参数（若需后续重算）。

### 7.3 难点

正反面双材质 + 视口显示是材质部分最难处；若 Sen 确认反面材质为刚需，视口绘制方案（调研 C）须同步设计，不能后补。

---

## 8. 剖面 Section Plane、标签 Tags、场景 Scenes、样式 Styles

### 8.1 Section Plane（建模相关度：中，显示为主）

官方来源：https://help.sketchup.com/en/sketchup/slicing-model-peer-inside （Creating and Using Section Planes，2026-09-29 更新）

**SketchUp 行为（官方）：**
- 剖面沿平面切割模型以便向内看，**不移动/隐藏任何几何**；活动剖面隐藏平面一侧的全部内容。纯显示行为，不改模型。
- 可插入多个剖面，但**每个 Context 内只有一个活动切割**；组/组件各自有独立 Context，故多 Context 可各有一个活动切割。
- 创建：Section Plane 工具或 Tools > Section Plane → 点面放置 → 弹出命名/编号提示 → 确定。放置后可用 Move/Rotate 调整；右键 Reverse 反转切割方向、Align View 对齐相机、Active Cut 切换活动/双击切换。
- Section Fill：Styles 面板 Modeling Settings 中勾选 Section Fill，为闭合环的剖切区域填充颜色（须在组/组件层级内成闭合环）。
- Create Group from Slice：右键剖面 → 生成剖面交线处的成组几何（仅边，无面——据论坛说明，官方词条称“grouped geometry”，未明说无面，标注来源级别），可移动/炸开后用于分割模型。
- 可见性分两档独立控制：Display Section Planes（平面图形显隐）与 Display Section Cuts（切割效果显隐）；单个平面 Hide 后不再随全局开关切换，直至 Unhide。
- 导出：File > Export > Section Slice（.dwg，True Section / Screen Projection 等选项）——导出属范围外（见方案范围说明）。

**Blender 映射：**
- **切割显示：** Blender 视口无原生“剖面裁剪”；备选：① `SpaceView3D` 无公开剖面 API——**不可依赖**；② 对每个 Mesh 对象加 Boolean 修改器（以大方块为切割体，Difference）作“活动切割”预览——会改求值网格、影响编辑，须在编辑时临时禁用；③ 自研 GPU 裁剪（clip plane 着色器，`gpu` 模块 + 自定义绘制）——只影响显示、不改数据，最贴合 SketchUp 语义，但须调研 C 的视口绘制方案支持。推荐③为主、②为备选/导出 Slice 用。
- **剖面实体：** 用 Empty（或薄 Plane Object）+ ID Property（名称、编号、活动标志、反转标志）表达剖面；归属 Context = 其父级容器；活动唯一性由插件状态机保证（同 Context 内激活一个即停用其他）。
- **Create Group from Slice：** 用 `bmesh.ops.bisect_plane`（`clear_outer/clear_inner=False`，取交线）或自研平面-面求交（复用 §5.2 求交代码），生成边组 → 新 Group 对象。`bisect_plane` 官方文档：https://docs.blender.org/api/current/bmesh.ops.html
- **Section Fill：** 第一阶段不做（填充须闭合环检测 + 填充面生成 + 样式联动）；列为延后项。

**判断：剖面属“建模辅助显示”，非建模核心。** 建议里程碑：先做剖面放置 + 切割显示 + Active Cut/Reverse/Hide + Create Group from Slice；Section Fill 与导出延后/范围外。

### 8.2 Tags（建模相关度：中，组织/可见性）

官方来源：https://help.sketchup.com/en/sketchup/controlling-visibility-tags （2026-11-10 更新）

**SketchUp 行为（官方）：**
- Tags 是旧版 Layers 的更新形式，功能相同且更多；用于组织对象与控制可见性，一键隐藏一批 Tagged 对象；Tag 可见性可用于搭建 Scenes 与高效操作。
- 默认新建几何为 Untagged；可给单个面/边打 Tag，但 **Tags 最适合打在组/组件上**（最佳实践：几何保持 Untagged，只给容器打 Tag）。
- Tags 面板：Add Tag、Add Tag Folder（文件夹成组管理可见性）、Filter、Tag 工具、Color by Tag（按 Tag 颜色着色）、Details 菜单（Expand/Collapse All、Select All、Show New Tags in Scenes、Delete Tag、Explode Tag Folder、Purge Unused、Select All Tagged、Apply Tags to Scenes）、Dashes（虚线样式）、Sort、Material（每 Tag 一个材质，默认随机纯色）。
- 可见性：眼图标开/合；可多选 Tag/文件夹批量切换。
- Tag 工具：须先在面板单选一个 Tag → 点实体即打 Tag（闪紫色确认）；修饰键：Sample（Alt/Cmd，取样实体 Tag 为当前选）、Replace All（Shift，替换所有同 Tag 实体的 Tag）、Tag All Instances（Ctrl/Option，给组件全部实例打 Tag）。
- Tag Folders 可嵌套；新建 Tag 时若选中文件夹则建在文件夹内。

**Blender 映射：**
- **Tags ≠ Collections。** Blender Collection 是层级容器 + 视图层可见性，与 SketchUp Tag（扁平标签 + 文件夹 + 任意对象可打一个 Tag）的语义不同。推荐：**Tags 存为插件管理的 Scene 级列表（PropertyGroup Collection）+ 每对象一个 `tag` ID Property（字符串）**；可见性切换 = 按 Tag 批量设 `Object.hide_viewport`（+ `hide_render` 可选）；Tag Folders = 列表的父子关系；Color by Tag = 临时覆盖对象视口颜色（`Object.color`）；Dashes = 边绘制虚线（须视口绘制支持，延后）。
- 备选（不推荐）：用 Collection 表达 Tag——会与 §6 的容器层级冲突（一个对象只能在一个 Collection 层级路径下表达嵌套，Tag 却是正交维度），且 Collection 可见性是视图层级（`LayerCollection.exclude`）而非对象级，语义混淆。
- **面/边级 Tag：** 官方允许但不推荐；第一阶段只支持对象级 Tag，面/边级 Tag 列为不支持并在方案中明说（须 Sen 确认可接受）。

**判断：Tags 属建模组织核心，建议纳入第一阶段后期（与组/组件同批），但 Dashes 与 Color by Tag 可延后。**

### 8.3 Scenes（建模相关度：低，视图/演示）

官方来源：https://help.sketchup.com/en/sketchup/creating-scenes （2026-10-29 更新）

**SketchUp 行为（官方）：** Scenes 保存不同模型视图与属性，用于演示。创建前先设好视图、样式、雾、阴影、剖切、隐藏几何、Tag 可见性；Scene 保存的属性（Details 可选）：Camera Location、Visible Tags、Active Section Planes、Style and Fog、Shadow Settings、Environment、Axes 等；可 Update Scene、Apply Tags to Scene。

**Blender 映射：** Scene 快照 = {相机位姿 + 投影模式 + FOV、Tag 可见性表、活动剖面表、隐藏对象表、样式/显示选项表}，存 Scene 级 PropertyGroup 列表 + 自研 Scenes 面板（切换 = 逐项恢复）。Blender 的 `Scene` 数据块与 SketchUp Scene 同名但不同义——**不得用多 Blender Scene 表达 SketchUp Scenes**（会分裂数据）。相机用 Blender Camera 对象或视图位姿快照（`RegionView3D` 参数）。

**判断：Scenes 不属建模核心，建议延后（第二阶段后），第一阶段只预留数据结构。**

### 8.4 Styles（建模相关度：低，仅显示项与建模相关）

**与建模相关的 Styles 项（须复刻/模拟）：** 边显示（Edges 开关、By Axis 边着色、端点显示）、面样式（Shaded / Shaded with Textures / Wireframe / Hidden Line / X-Ray）、Hidden Geometry 显示、Section Planes/Cuts 显示开关、背景/天空/地面（仅显示）。其余（手绘边样式、雾、阴影、水印）属演示/渲染，范围外。

**Blender 映射：** 视口着色模式（`SpaceView3D.shading.type`：WIREFRAME / SOLID / MATERIAL）+ Overlay 开关 + 自研边绘制（By Axis 着色、X-Ray 透明）+ 插件 Styles 面板。**X-Ray 与 By Axis 须自研绘制**，Blender 原生 Overlay 不直接提供。

**判断：Styles 仅复刻影响建模判断的显示项（边/面样式、X-Ray、Hidden Geometry、剖面开关），其余延后/范围外。**

---

## 9. 坐标与单位

官方来源：
- https://help.sketchup.com/en/managing-units-measurement （Managing Units of Measurement，经 prod-aws 镜像核对）
- https://help.sketchup.com/en/sketchup-ipad/model-info-panel （Model Info 面板，单位区结构一致）

### 9.1 SketchUp 侧

- **坐标系：** 红 = X、绿 = Y、蓝 = Z；Z-up（蓝轴向上）。绘图轴可移动/重定向（Axes 工具），推断轴随绘图轴走——**推断引擎须支持自定义绘图轴**（轴原点 + 三方向），不能写死世界轴。
- **单位设置（Model Info > Units）：** Format（Architectural / Decimal / Engineering / Fractional）、Length/Area/Volume 各自单位（Decimal 下可分别设）、Display Precision（Architectural 可至 1/64 英寸、Engineering 可至 6 位小数）、Enable Length Snapping（绘图工具吸附到最接近的精度单位）、Enable Angle Snapping（角度吸附到精度单位）。**改单位只改显示，不改几何实际尺寸。** Display Precision 只影响显示数字，几何始终以完整内部精度存储（教程共识，官方词条未逐字写“完整精度”，标注来源级别）。
- **VCB/Measurements 输入：** 输入时可带单位后缀（如 `6in`、`15cm`），也可不带（用模型单位）；英制分数/英尺英寸格式（如 `6' 8 7/8"`）须解析。**数字解析器须支持：十进制、分数、英尺-英寸、单位后缀、负数、分隔符（矩形 `x,y` / 圆 `半径,段数` 等工具相关格式——具体格式归调研 A 各工具的 VCB 规格）。**

### 9.2 Blender 侧映射

- **坐标系：** Blender 亦为 Z-up、右手系，X/Y/Z 与 SketchUp 红/绿/蓝**方向一致**，无需坐标变换（与 Y-up 软件不同，这是好消息）。但 Blender 默认单位为米（`UnitSettings.system='METRIC'`、`scale_length=1.0`、`length_unit='METERS'`），SketchUp 模板常为英寸/毫米——**插件内部统一用米（Blender 单位）存储，显示/输入层做单位换算**，不得改 `scale_length` 迁就 SketchUp 单位（会破坏与其他 Blender 功能的协作）。
  - 官方来源：`bpy.types.UnitSettings`，https://docs.blender.org/api/current/bpy.types.UnitSettings.html
- **精度：** SketchUp 内部为 double；Blender Mesh/bmesh 坐标为 **float32**。影响：① 大坐标（建筑尺度、远离原点）下 float32 的绝对误差可达毫米级，成面/求交容差须按量级自适应；② 极小几何（毫米以下细节）在 float32 下易退化。**规格须定：插件容差 = max(绝对容差, 相对容差 × 场景尺度)，并建议用户在原点附近建模。** 是否需要“双精度影子模型”（自存 double 坐标、仅同步 float32 到 Blender）是重大架构取舍：精度高但同步复杂、Undo/编辑全须经影子层——**建议第一阶段不用影子模型**（先验证 float32 在 Sen 的实际模型尺度下是否够用），列入不确定项请 Sen 确认典型模型尺度（见 §11 Q6）。
- **Length/Angle Snapping：** 自研：VCB 输入后/鼠标移动时按 Snapping 增量取整（Length Snapping 默认开启与否按模板——SketchUp Decimal 模板默认开启，社区多建议关闭以保精度；插件默认取舍须问 Sen）。
- **绘图轴：** 存 Scene 级自定义轴（原点 + X/Y/Z 方向矩阵），推断引擎与 VCB 坐标输入均以绘图轴为基准；Axes 工具（调研 A）负责修改它。

---

## 10. Blender 数据模型总映射与关键取舍

### 10.1 映射总表

| SketchUp 概念 | Blender 表达 | 备注 |
|---|---|---|
| Model | `.blend` 文件 + 一个 Scene | 不用多 Scene |
| Edge | `BMEdge` / `Mesh.edges` | 须附 soft/smooth/hide/curve 标志（自定义层） |
| Face（含内环） | 1 个或多个 `BMFace` + 逻辑面 ID（面自定义层） | Blender 面无洞，带洞面须拆分 + 逻辑合并 |
| Vertex | `BMVert` / `Mesh.vertices` | 共享顶点 = 粘连 |
| Curve / Arc / Circle / Polygon（曲线实体） | 边集合 + 曲线元数据（自定义层/ID Property：类型、中心、半径、段数、平面） | 网格本身无曲线概念，元数据须自存；Explode Curve = 删元数据 |
| Surface（Soft 边连成的面组） | Soft 边连通域（运行时计算）+ 选集扩展 | 无独立数据块 |
| Group | 独立 Mesh 的 Object（+ 父子嵌套） | 见 §6 |
| Component Definition | 共享 Mesh 数据块 / 含嵌套时为 Collection | 见 §6.2 取舍 3 |
| Component Instance | 共享 `data` 的 Object / Collection Instance | 见 §6.2 |
| Guide Point / Guide Line | 独立 Empty / 自定义绘制 + 插件数据列表 | 不进 Mesh，不参与成面 |
| Section Plane | Empty + ID Property | 见 §8.1 |
| Tag | Scene 级 Tag 列表 + 对象 `tag` 属性 | 见 §8.2 |
| Scene（SketchUp） | Scene 级快照列表 | 见 §8.3 |
| Material | `Material` 数据块 + 面 `material_index` + 反面自定义层 | 见 §7 |
| Drawing Axes | Scene 级自定义轴 | 见 §9 |
| Hidden | 边/面/对象自定义 hide 标志 + `Object.hide_viewport` | 边/面级 hide 须自研绘制过滤 |

### 10.2 bmesh API 清单（本插件依赖的核心算子，均以 current 文档为准）

官方来源：https://docs.blender.org/api/current/bmesh.html 、https://docs.blender.org/api/current/bmesh.ops.html 、https://docs.blender.org/api/current/bmesh.types.html

- 结构：`bmesh.from_edit_mesh(mesh)` / `bmesh.new()` / `bmesh.update_edit_mesh(mesh)`；`BMVert.co`、`BMEdge.verts` / `link_faces`、`BMFace.verts` / `loops` / `normal` / `material_index` / `smooth`、`BMLoop`（UV/颜色按 Loop 存）。
- 创建/删除：`bm.verts.new`、`bm.edges.new`、`bm.faces.new`、`bmesh.ops.delete`（`context` 参数：VERTS/EDGES/FACES 等，须逐项确认删边是否连带删面——默认不连带，须自处理，见 §2.2）、`bmesh.ops.dissolve_faces` / `dissolve_edges` / `dissolve_verts`（愈合用）、`bmesh.ops.dissolve_limit`（角度溶解，Soften Coplanar 参考）。
- 连接/分裂：`bmesh.ops.connect_verts`（面内连边分裂面）、`bmesh.ops.bisect_edges`（边分段）、`bmesh.ops.subdivide_edges`（Divide 参考）、`bmesh.ops.weld_verts`（顶点合并）。
- 挤出/变换：`bmesh.ops.extrude_face_region`（不位移，须另调 `translate`）、`extrude_edge_only`、`extrude_vert_indiv`、`bmesh.ops.translate` / `rotate` / `scale`。
- 填充/偏移：`bmesh.ops.edgenet_fill` / `edgeloop_fill`（单环填充参考）、`bmesh.ops.inset_region` / `offset_edgeloops`（Offset 参考，须验证）、`bmesh.ops.holes_fill`。
- 法线/其他：`bmesh.ops.recalc_face_normals`、`reverse_faces`、`bisect_plane`（剖面/求交参考）、`bmesh.ops.remove_doubles`（历史名，现为 `weld_verts` 体系，版本复核）。
- 自定义层：`bm.{verts,edges,faces,loops}.layers.{int,float,string,bool,uv,...}`；UV 层：`bm.loops.layers.uv`。

### 10.3 Edit Mode vs Object Mode（核心取舍，定稿）

- **定稿建议：插件工具一律在 Edit Mode 下操作活动上下文对象的 bmesh**（`bmesh.from_edit_mesh`），理由：① bmesh 编辑 API 只在 Edit Mode 下与视口实时同步；② Blender 的 Edit Mode 一次一对象，天然对应 SketchUp 的单 Context 编辑；③ 拾取须用 BMesh 的 BVH（`BVHTree.FromBMesh`），Object Mode 的 `Object.ray_cast` 读的是未同步的 Mesh 数据，编辑中不可用。
- **代价与处理：** ① 进入/退出上下文 = 切换活动对象 + 进/出 Edit Mode，须处理模式切换的 Undo 步进与选择同步；② 跨上下文拾取（推断参考其他容器内的点、Intersect With Model）须读其他对象的 Mesh 数据（Object Mode 数据，可读）+ 变换到世界坐标，再与当前 bmesh 的局部坐标换算——拾取层须同时支持“活动 bmesh + 其他对象 Mesh”双源；③ Object Mode 下的 Blender 原生工具（移动/缩放对象）与插件工具的状态机须互斥（插件工具激活时锁定模式切换，或退出插件工具后恢复）。
- **备选（不推荐）：** 全程 Object Mode + `bmesh.new()` / `to_mesh()` 同步——每次编辑全量同步，性能差且丢失 Edit Mode 的选择/撤销集成。

### 10.4 曲线实体（Circle / Arc / Polygon / Curve）元数据

- SketchUp 的圆/弧/多边形是“带参数的曲线实体”：选中一段即选中整体、可改段数（Entity Info）、圆心可推断、Explode 后变散边。Blender 网格只有折线边，**无曲线概念**。
- 映射：边集合 + 元数据（存边自定义 int 层：curve_id；存对象/场景级字典：curve_id → {类型， 中心， 半径， 段数， 平面法线， 起止角}）。画圆/弧/多边形工具创建边时同时写元数据；编辑（移动顶点、Explode、Divide）时维护/失效元数据；推断 Center、Entity Info 段数编辑、Weld 后的 Curve 行为均读元数据。
- 风险：用户用 Blender 原生工具改边后元数据失效——插件须在工具入口校验元数据有效性（中心/半径与实际边的一致性），失效则降级为散边（不报错）。

### 10.5 流形 / 非流形与 Solid 判定

- SketchUp 是**面建模器（face modeler）**：允许非流形（悬边、单面、T 形连接边）；Solid（实体）是“每个边恰好被两个面共享、且全部正面朝外”的组/组件才有的性质，Solid Tools（布尔）只对 Solid 生效。官方词条对 Solid 的定义分散在 Solid Tools 词条中，本调研未逐字复核 Solid 定义原文——**Solid 判定规则列入不确定项**，须补查 Solid Tools 官方词条后定稿。
- Blender/bmesh **支持非流形**（`BMEdge.link_faces` 可为任意数），与 SketchUp 的面模型兼容——这是 bmesh 适合本插件的重要原因。**不得假设流形**：成面、推拉、求交算法均须处理悬边/单面/T 边。
- Blender Boolean 修改器（EXACT）要求（近似）流形输入，对 SketchUp 式非流形模型可能失败——这也是 §5.2 不用 Boolean 做 Intersect 的原因之一。Solid Tools（Union/Subtract/Trim/Intersect/Split/Outer Shell）若纳入范围，须先做 Solid 判定 + 非流形拒绝/提示；Solid Tools 本身建议列为**第二阶段**（布尔算法可复用 Blender Boolean EXACT，但须做 SketchUp 语义包装：结果容器化、定义保留等——细节须另行调研）。

### 10.6 自定义属性 / ID Property 与数据存储

- 官方来源：https://docs.blender.org/api/current/bpy.props.html （`bpy.props` / PropertyGroup / CollectionProperty）、ID Property（`obj["key"]` 字典式访问，5.0 有改动——版本基线锁定后复核）。
- 规则：**插件状态分两类**：① 随文件保存的模型数据（Tag 列表、Scenes 快照、绘图轴、曲线元数据、剖面参数、材质真实尺寸）→ `bpy.props` 的 Scene/Object 级 PropertyGroup + ID Property，须可序列化；② 不随文件保存的会话状态（推断缓存、活动上下文栈、上次推拉距离、BVH 缓存）→ 内存模块变量 + `bpy.app.handlers` 清理。**不得把会话状态写进 ID Property**（会污染文件与 Undo）。
- 命名空间：全部自定义属性加 `su_` 前缀（如 `su_tag`、`su_curve_id`），避免与用户/其他插件冲突。

---

## 11. 不确定 / 需问 Sen 的事项

以下事项**不得由调研员自行决定**，须 Sen 拍板或真机确认后才能写入最终方案：

| # | 问题 | 为什么必须问 | 建议默认值（供 Sen 否决） |
|---|---|---|---|
| Q1 | 参照基线是 SketchUp 2026（classic）还是含 2027 的 Procedures（Procedural Follow Me / Solid Tools / Copy Along）？ | 2027 程序化体系工作量翻倍，且 Sen 真机为 26.0.429，无法验证 2027 行为 | 只做 2026 classic；Procedural 列为范围外 |
| Q2（已定范围，仍需 Sen 的真机版本作主测版本） | Sen 已定适配 Blender 4.x–5.x、界面语言跟随 Blender 设置；Sen 真机具体装的是哪个版本（主测版本）？ | 5.0 有 API 破坏性改动；BGL 移除、ID Property 改动均与版本相关；须以 Sen 真机版本为主测、另一 LTS 为兼容测 | 4.5 LTS 与 5.2 LTS 双基线 + 版本门控兼容层 |
| Q3 | 推断图标颜色/形状、方向键“再按解除”、Shift 锁定细节，以 Sen 的 SketchUp 2026 真机截图为准确认？ | 官方文本未给颜色 RGB 与部分时序细节 | 请 Sen 截取推断图例 + 实测锁定行为后定稿 |
| Q4 | 含嵌套内容的组件定义，用 Collection Instance 方案（双击实例跳转到定义编辑）是否可接受？还是限制组件嵌套？ | 单 Mesh 无法表达嵌套组件定义，交互取舍影响架构 | Collection Instance + 跳转编辑；嵌套不限深度 |
| Q5 | 面反面独立材质是否为刚需？ | Blender 无原生双材质，刚需则视口方案须重设计 | 第一阶段只做正面材质 + 反面默认显示 |
| Q6 | 典型模型尺度（建筑米级 / 产品毫米级 / 毫米以下细节）？是否需要双精度影子模型？ | float32 精度是否够用取决于尺度与离原点距离 | 先不用影子模型，真机大模型测试后再定 |
| Q7 | Push/Pull 的 Ctrl 保留起始面、推到面/点对齐、预选多面推拉，是否需要？以真机实测为准？ | 官方词条未述，社区说法不一 | 先做单面拉出/推入 + 双击复用，其余真机确认后补 |
| Q8 | Follow Me 内外角自交时：静默裁剪还是提示失败？手动模式是否第一阶段就要？ | 官方未述角部算法，交互取舍影响实现 | 自交时裁剪 + 状态栏提示；手动模式第二阶段 |
| Q9 | Solid Tools（布尔）是否在范围内？Dynamic / Live Components 是否在范围内？ | 两者均为大工作量扩展体系 | 均列为范围外/第二阶段后，由 Sen 定优先级 |
| Q10 | Length Snapping 默认开还是关？默认单位/精度模板用哪个（毫米/厘米/米）？ | 影响 VCB 默认行为与新手体验 | 默认关 Length Snapping（保精度）；模板毫米、精度 0.0mm（供 Sen 改） |
| Q11 | 面/边级 Tag 是否需要？还是只支持对象级 Tag？ | 面/边级 Tag 增加数据与可见性复杂度 | 只支持对象级 Tag |
| Q12 | 成面环优先级（大环套小环、重画边后的愈合顺序）是否须与 SketchUp 原生逐项一致？还是“合理确定性算法 + 真机抽查”即可？ | 官方未述优先级，逐项一致须大量真机对比测试 | 合理确定性算法 + 重点场景真机对比 |

**另需补查的官方资料（调研员后续或实现前补）：**
- Solid Tools 官方词条（Solid 定义与六个布尔工具的精确语义）。
- Components 官方词条全文（Make Component 对话框：名称、描述、Glue to、Cut Opening、Always face camera、Scale 定义等逐项）。
- Texture Position 官方词条（若 Help Center 有专篇，须找到 URL；本次检索未得专篇）。
- SketchUp Ruby API 的 `Face` / `Edge` 语义文档（`ruby.sketchup.com`，作行为交叉验证用，非 Help Center 但为官方 API 文档）。
- Blender `docs.blender.org/api/current/` 的 Mesh / bmesh / gpu / SpaceView3D 复核（锁定版本后逐项复核本调研引用的 API 名与签名）。

---

## 来源列表

### SketchUp Help Center（官方，已全文或摘要核对）

1. Introducing Drawing Basics and Concepts — https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts
2. Pushing and Pulling Shapes into 3D — https://help.sketchup.com/en/sketchup/pushing-and-pulling-shapes-3d
3. Dividing, Splitting, and Exploding Lines and Faces — https://help.sketchup.com/en/sketchup/dividing-splitting-and-exploding-lines-and-faces
4. Offsetting a Line from Existing Geometry — https://help.sketchup.com/en/sketchup/offsetting-line-existing-geometry
5. Softening, Smoothing, and Hiding Geometry — https://help.sketchup.com/en/sketchup/softening-smoothing-and-hiding-geometry
6. Creating and Using Section Planes — https://help.sketchup.com/en/sketchup/slicing-model-peer-inside
7. Controlling Visibility with Tags — https://help.sketchup.com/en/sketchup/controlling-visibility-tags
8. Creating Scenes — https://help.sketchup.com/en/sketchup/creating-scenes
9. Hierarchies in the Outliner — https://help.sketchup.com/en/sketchup/working-hierarchies-outliner
10. Entity Context Menus — https://help.sketchup.com/en/context-menu-items-entities
11. Applying Materials — https://help.sketchup.com/en/sketchup/applying-materials
12. Replacing a Material — https://help.sketchup.com/en/sketchup/replacing-material
13. Extruding with Follow Me — https://help.sketchup.com/en/sketchup/extruding-follow-me （2026-10-21 版含 Procedural 描述，本调研取 classic 部分）
14. SketchUp Procedures — https://help.sketchup.com/en/procedural-tools （2027 内容，作范围区分）
15. Managing Units of Measurement — https://help.sketchup.com/en/managing-units-measurement （经 prod-aws 镜像核对）
16. Grouping Geometry — https://help.sketchup.com/en/sketchup/grouping-geometry （经 prod-aws 镜像核对）
17. Soften/Smooth Panel — https://help.sketchup.com/en/sketchup-ipad/soften-smooth-panel （iPad 版，面板选项与桌面版基本一致，作交叉参考）

### Blender 官方文档

18. BMesh 模块 — https://docs.blender.org/api/current/bmesh.html
19. BMesh Operators — https://docs.blender.org/api/current/bmesh.ops.html
20. BMesh Types — https://docs.blender.org/api/current/bmesh.types.html （本次抓取到 4.1 版，current 版须锁定版本后复核）
21. Mesh (bpy.types.Mesh) — https://docs.blender.org/api/current/bpy.types.Mesh.html
22. bpy_extras.view3d_utils — https://docs.blender.org/api/current/bpy_extras.view3d_utils.html
23. BVHTree — https://docs.blender.org/api/current/mathutils.bvhtree.html
24. Property Definitions (bpy.props) — https://docs.blender.org/api/current/bpy.props.html
25. UnitSettings — https://docs.blender.org/api/current/bpy.types.UnitSettings.html
26. Blender 4.5 LTS 发布页 — https://www.blender.org/releases/4-5/

### 二手来源（仅作交叉参考，已在正文标注，不作规格依据）

- SketchUp Community 论坛：Intersect Faces 三档定义（slbaumgartner）、容器材质优先级、推断锁定“再按解除”等。
- Google SketchUp 2006 用户手册：推断颜色表（Endpoint 绿 / Midpoint 青 / Intersection 黑 / On Face 蓝 / On Edge 红）。
- MasterSketchUp / SketchUp For Dummies：推断分类与悬停鼓励、Soft/Smooth/Hide 区别。
- SketchUp Ruby API 文档 Native Procedures：https://ruby.sketchup.com/file.native_procedures.html （Procedural Follow Me 参数，2027 内容）。
- 第三方 Blender 版本汇总（5.2 LTS 日期、5.0 破坏性改动）：cinevva 指南、GitHub 版本笔记——版本基线须以 blender.org 官方发布页复核后定稿。
