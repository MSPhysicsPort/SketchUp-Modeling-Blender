# 调研 C：Blender 插件架构 + 复刻范围界定

> 调研日期：2026-11-17（以官方文档搜索结果为准，未在本机实跑 Blender 验证）
> 任务：只调研、不写实现代码。本文件供团队负责人统稿方案用。
> 参照：SketchUp 2026（Sen 机器：SketchUp 26.0.429、Windows 11）；Blender 侧以 docs.blender.org / blender.org 为准。

---

## 结论摘要（给负责人统稿用）

- **目标版本：Blender 5.2 LTS 为开发/验收基准**；扩展 manifest 最低版本建议写 `4.2.0`，但只承诺在 5.2 LTS 上测过（见 §1）。
- **打包：走 Blender 4.2+ 扩展（Extension）格式**（`blender_manifest.toml`），不用已弃用的 legacy `bl_info` 格式（见 §2）。
- **交互主力：Modal Operator + `gpu` 模块 draw handler**；GizmoGroup 只做 Move/Rotate/Scale 手柄备选（见 §3）。
- **快捷键：只写 `keyconfigs.addon`，加三档总开关，默认状态需 Sen 定**（见 §4）。
- **菜单落点：工具栏（WorkSpaceTool）+ 3D 视图头栏“SketchUp”菜单 + N 面板 + 右键菜单**，四处同源（见 §5）。
- **存储分三层：AddonPreferences（跨文件）/ Scene PropertyGroup（随文件）/ ID 自定义属性（随对象）**；撤销靠 `{'REGISTER','UNDO'}`，一次完整工具动作为一个撤销步（见 §6）。
- **测试分四层：纯 Python 单元 → headless bpy 集成 → Sen 真机 GUI 手工清单 → 回归 .blend 夹具**；modal/gizmo/按键交互无法 headless 测（见 §7）。
- **范围：核心建模在内；LayOut、3D Warehouse、渲染器复刻、Ruby API、.skp/DWG 等在外或待定**（见 §8）。

---

## 1. Blender 版本选择

### 1.1 当前版本线（2026-11-17 核查）

| 版本 | 类型 | 发布/支持 | 备注 |
|---|---|---|---|
| **5.3.0** | 常规版 | 2026-11-10 发布 | 最新常规版，非 LTS；含 Vulkan 默认等变化，API 仍在变，不适合做长期基准 |
| **5.2 LTS（5.2.3，2026-10-22）** | **LTS** | 2026-07-14 发布，**支持至 2028-07** | **推荐基准**：5.x 首个 LTS，API 已稳定 |
| 4.5 LTS | LTS | 2025-07-15 发布，支持至 2027-07 | 上一代 LTS；Intel Mac 的最后一条线，与本项目（Windows）关系不大 |
| 4.2 LTS | LTS | 已于 2026-07 结束支持 | 不要再以它为基准 |

来源：blender.org 5.2 发布页（Released July 14th, 2026；LTS until July 2028）、LTS 页、第三方版本汇总（核对日期 2026-11-12 左右）。

### 1.2 推荐

- **开发与验收基准：Blender 5.2 LTS（最新修正版）**。Sen 的 Windows 真机请装 5.2 LTS；Linux 这边的 headless 测试也用同一大版本，避免“两边行为不一致”。
- **manifest 的 `blender_version_min`：建议写 `"4.2.0"` 还是 `"5.2.0"`，需负责人/Sen 二选一：**
  - 选 `"5.2.0"`：最简单，代码不用做版本分支，验收口径唯一。缺点是 4.x 用户装不上。
  - 选 `"4.2.0"`：扩展能装到更多版本，但团队必须自律（只用 4.2/5.2 共有的 API 子集），且 4.x 只能“尽力兼容、不承诺测过”。
  - **本调研推荐：第一阶段写 `"5.2.0"`，先把一个版本做稳；后续如需扩版本再降 `blender_version_min` 并补回归。** 扩展机制要求 `blender_version_min` 至少为 `4.2.0`，写 5.2.0 完全合法。
- **Python 运行时：** 5.0 用 Python 3.11，**5.1 起用 Python 3.13**。纯 Python 插件（只用 `bpy`/`bmesh`/`mathutils`/标准库）不受 ABI 影响，同一个 zip 可跨 5.0–5.3；**一旦捆绑编译型 wheel（.pyd/.so）就必须按 Python 版本分别构建**。本项目应坚持**零编译依赖、零第三方 wheel**，避免这条坑。

### 1.3 影响本项目的 API 变化（必须遵守的红线）

| 变化 | 影响 | 对策 |
|---|---|---|
| `bgl` 模块在 5.0 被**移除**（3.5 起弃用） | 所有旧式 OpenGL 绘制代码在 5.x 直接报错 | 一律用 `gpu` 模块（`gpu.shader` / `gpu.types.GPUBatch` / `gpu.state`） |
| 内置 shader 名在 4.0 去掉 `3D_`/`2D_` 前缀 | `3D_UNIFORM_COLOR` 等旧名在 4.0+ 不存在 | 用 `UNIFORM_COLOR`、`POLYLINE_UNIFORM_COLOR` 等新名 |
| 字典式 context override 在 4.0 被**移除** | `bpy.ops.xxx({...})` 旧写法失效 | 用 `context.temp_override()`（3.4+） |
| `MeshEdge.bevel_weight` / `crease` 属性在 4.0 被移除 | 改用属性（attribute）`bevel_weight_edge` / `crease_edge` | 本项目如需倒角/折痕数据，走 attribute，不走旧属性 |
| `mesh.calc_normals()` 在 4.0 被移除 | 法线自动计算 | 不调用；依赖自动法线 |
| 旧 Action API（`action.fcurves` 等）在 5.0 被移除 | 与动画/动态组件相关 | 本项目若不做动画则无影响；做 Scenes/动画时用 slotted Action API |
| `scene.node_tree`（合成器）在 5.0 被移除 | 与渲染/合成相关 | 与建模无关，忽略 |
| `bpy.props` 字典式访问在 5.0 被移除 | 旧式属性存储写法失效 | 用正规 `bpy.props` + PropertyGroup |
| 用户 site 目录默认不再加载（5.x） | 不能指望 `pip install` 到用户 site | 自包含扩展，不依赖外部 pip 包 |

**相对稳定的 API（可放心依赖）：**

- `bmesh`：`bmesh.new()` / `from_mesh()` / `to_mesh()` / `from_edit_mesh()` / `update_edit_mesh()` / `bmesh.ops.*` 长期稳定，是本项目的几何主力。
- `bpy.types.Operator` 的 `invoke` / `modal` / `execute` + `bl_options` 机制长期稳定。
- `Gizmo` / `GizmoGroup` 自 2.8 起稳定，5.x 无破坏性变化报告。
- `SpaceView3D.draw_handler_add/remove` + `gpu` 绘制是官方推荐的视口叠加层做法，4.0–5.x 稳定。
- `mathutils`（Vector/Matrix）稳定。

---

## 2. Addon 结构：Extension vs Legacy

### 2.1 两种格式的官方定位

Blender 4.2 引入 Extensions 平台后，**旧式 addon（`bl_info`）被视为 deprecated（已弃用），但仍被支持**，可通过偏好设置里的 “Install legacy Add-on” 安装。官方敦促维护者转为 Extension 格式，以保证未来兼容并能上 extensions.blender.org。

| 维度 | Legacy Add-on（旧） | Extension（新，推荐） |
|---|---|---|
| 元数据 | `__init__.py` 顶部的 `bl_info` 字典 | `blender_manifest.toml`（`bl_info` 必须删除） |
| 安装入口 | Preferences → Add-ons → Install legacy Add-on | Preferences → Get Extensions → Install from Disk |
| 模块命名空间 | 模块名即包名（如 `sketchup_tools`） | `bl_ext.{仓库名}.{扩展id}`（如 `bl_ext.user_default.sketchup_tools`） |
| 偏好设置访问 | `preferences.addons["模块名"]` | `preferences.addons[__package__]`（必须用 `__package__`，不能写死名字） |
| 依赖 | 无官方机制，靠用户手工装 | 可在 manifest 里声明 `wheels = [...]` 捆绑 wheel |
| 权限 | 无声明 | manifest 里声明 `permissions`（文件/网络/剪贴板等）并写理由 |
| 自包含要求 | 无强制 | 必须自包含；不能假设自身目录可写 |

**本项目决策：只做 Extension 格式。** 理由：Sen 装的是 5.2 LTS，Extension 是官方当前格式；同时维护两种格式会让注册/偏好/打包逻辑分叉，得不偿失。第一阶段交付的 .zip 就是 Extension zip。

### 2.2 Extension 的 manifest（`blender_manifest.toml`）

位于 zip 顶层（与 `__init__.py` 同级）。必需字段（官方手册）：

```toml
schema_version = "1.0.0"
id = "sketchup_modeling"          # 唯一标识，建议全小写+下划线，需负责人定最终名
version = "0.1.0"                 # 必须语义化版本 SemVer
name = "SketchUp Modeling Tools"  # 显示名
tagline = "Model in Blender with SketchUp tools and logic"  # ≤64 字符，无结尾标点
maintainer = "Ember / Sen"        # 维护者，需定
type = "add-on"
blender_version_min = "5.2.0"     # 见 §1.2 建议
license = ["GPL-3.0-or-later"]    # SPDX；Blender 插件惯例 GPL，需 Sen 定
# 可选：blender_version_max、website、permissions 等；可选字段为空时应省略而非留空
```

注意事项：

- `id` 一旦发布不要改（用户升级、偏好设置都认它）。
- `tagline` 最长 64 字符，不能以标点结尾（官方校验会拒）。
- 权限：本项目第一阶段**不需要网络/剪贴板/摄像头权限**，不要声明；如后续要做 3D Warehouse 联网再补（那会触发用户授权提示）。
- 不要在 manifest 和代码里同时留 `bl_info`——转 Extension 时官方步骤第 2 条就是删除 `bl_info`。

### 2.3 .zip 包结构（Extension）

```
sketchup_modeling-0.1.0.zip
├── blender_manifest.toml
├── __init__.py            # 只做注册/注销转发，保持薄
├── preferences.py         # AddonPreferences
├── keymaps.py             # 快捷键注册/注销
├── menus.py               # 3D 视图头栏菜单、右键菜单
├── panels.py              # N 面板
├── tools/
│   ├── __init__.py
│   ├── select.py
│   ├── line.py
│   ├── push_pull.py
│   └── ...                # 每个 SketchUp 工具一个模块（或按组分）
├── operators/             # 非 modal 的一次性命令（成组、炸开、翻转等）
├── core/
│   ├── __init__.py
│   ├── inference.py       # 推断引擎（纯逻辑，尽量不依赖 bpy，见 §7）
│   ├── geometry.py        # bmesh 封装：成面、愈合、布尔等
│   ├── vcb.py             # 数字输入解析（长度/角度/份数/比例）
│   ├── units.py           # 单位换算与格式化
│   └── state.py           # 会话状态（当前工具、锁定轴、VCB 缓冲）
├── draw/
│   ├── __init__.py
│   └── overlay.py         # gpu 绘制：推断标记、橡皮筋线、预览面、文字
├── data/
│   ├── tags.py            # Tag（图层）映射
│   ├── components.py      # 组/组件映射
│   └── materials.py       # 材质映射
├── icons/                 # 自定义图标（如用 bpy.utils.previews）
└── tests/                 # 不随包发布，或放包外；见 §7
```

打包规范要点：

- zip 内**顶层就是扩展内容**（`blender_manifest.toml` 在 zip 根目录），不要多套一层文件夹（否则 Blender 找不到 manifest）。构建脚本必须校验这一点。
- 所有模块间 import **必须用相对 import**（`from .core import inference`），不能用绝对包名（Extension 命名空间是 `bl_ext.*`，写死包名会断）。
- 代码里凡是取自身包名的地方用 `__package__`（偏好设置、资源路径）。
- **不要假设扩展目录可写**：用户数据/缓存走 `bpy.utils.extension_path_user(__package__, create=True)`。
- 多文件 addon 的 `register()`/`unregister()` 顺序：**先注册 PropertyGroup，再注册 Operator/Panel/Menu/Gizmo/Tool；注销时反序**。可用 `bpy.utils.register_classes_factory(classes)` 生成，但显式列表更易排错，建议显式列表 + 每个子模块自带 `register/unregister`、由 `__init__.py` 汇总调用。
- `register()` 里**禁止访问 `bpy.context` 和 `bpy.data`**（此时 context 是受限的 `_RestrictContext`，访问会报 AttributeError）；只做类注册、菜单 append、keymap 注册（且 keymap 注册要判空，见 §4）。

### 2.4 启用/禁用与热重载

- 启用时 Blender 执行 `register()`；禁用时执行 `unregister()`，必须**干净地**移除：所有类、菜单 append、keymap、draw handler、GizmoGroup、Tool、自定义属性（`del bpy.types.Scene.xxx`）。漏清 draw handler 会导致“幽灵叠加层”甚至崩溃。
- 开发期可用 Blender 的 “Developer Extras” + 脚本重载，但 Extension 的热重载不如单文件脚本顺滑；建议开发流程：改代码 → 重新打包 → 在测试 Blender 里禁用/启用（或重启 Blender）。不要指望 `importlib.reload` 能干净重载已注册的 RNA 类。

---

## 3. Modal Operator、Gizmo 与自定义绘制

### 3.1 Modal Operator：SketchUp 式交互工具的标准载体

SketchUp 的 Line、Push/Pull、Move、Rotate、Scale 等工具都是“持续交互、多点输入、实时预览、数字修正”的工具，在 Blender 里对应的就是 **Modal Operator**（Grab/Rotate/Scale/Fly 模式都是 modal operator）。

官方模式（`bpy.types.Operator` 文档示例）：

```
invoke(context, event):
    初始化状态（起点、锁定、VCB 缓冲）
    添加 draw handler（预览绘制）
    context.window_manager.modal_handler_add(self)
    return {'RUNNING_MODAL'}

modal(context, event):
    MOUSEMOVE     → 更新推断点/预览，重绘
    LEFTMOUSE PRESS → 确认当前点（多点工具则进入下一步；最后一步则提交并 FINISHED）
    RIGHTMOUSE / ESC → 取消（恢复原状，移除 handler，CANCELLED）
    数字/小数点/负号/单位键 → 写入 VCB 缓冲，不提交
    ENTER / TAB   → 提交 VCB 数值（按工具语义：确认长度/份数/角度）
    方向键/Shift  → 轴向锁定切换
    中键/Alt+左键等导航键 → 返回 {'PASS_THROUGH'}，让视图导航接管
    其他未处理事件 → {'RUNNING_MODAL'}

execute(context):
    真正把几何写入 bmesh/mesh（只在确认时调用一次）
    供脚本/重做调用；modal 完成时也应复用同一提交函数
```

关键约定（必须在工具规格里统一）：

| 事项 | 约定 | 备注 |
|---|---|---|
| 确认 | 左键 PRESS（不是 RELEASE） | 与 Blender 内置工具一致；要判 `event.value == 'PRESS'`，避免 PRESS/RELEASE 各触发一次 |
| 取消 | 右键或 ESC | 与官方示例一致；**SketchUp 里右键是菜单**，这是最大冲突点——工具进行中右键应为取消还是菜单，需 Sen 定（见“不确定事项”） |
| 导航 | 中键旋转/Shift+中键平移/滚轮缩放 | modal 里必须 `PASS_THROUGH`，否则工具进行中无法看模型 |
| 多点工具 | 每次左键推进状态机，不立即 FINISHED | 如 Line：点1→点2→点3…，双击/闭合/ESC 结束 |
| 预览 | 只画不写 | 鼠标移动时**只更新 draw handler 数据**，不改 mesh；确认时才一次性写入（否则每移一次鼠标就产生撤销步/性能崩溃） |
| VCB 输入 | 在 modal 里拦截数字键 | 不能依赖 Blender 的 redo 面板；VCB 是 SketchUp 的核心，必须自建缓冲+显示 |
| 清理 | FINISHED/CANCELLED/异常都要移除 draw handler | 建议 `__del__` 里再兜底一次（官方示例注明 `__init__`/`__del__` 对 modal operator 有意义） |
| `bl_options` | `{'REGISTER', 'UNDO', 'BLOCKING'}` 视情况 | `UNDO` 保证确认后可 Ctrl+Z；`BLOCKING` 阻止其他输入抢光标（按工具需要决定，不要全加） |

**状态机建议：** 每个交互工具 = 一个 Modal Operator + 一个显式状态枚举（如 `WAIT_FIRST_POINT` / `WAIT_SECOND_POINT` / `WAIT_VCB`），状态转移只在 `modal()` 里发生；几何提交函数与状态机分离，便于 headless 测试直接调提交函数（见 §7）。

### 3.2 Gizmo（GizmoGroup）vs 自定义绘制（gpu draw handler）

| 维度 | GizmoGroup（`bpy.types.GizmoGroup` + `Gizmo`） | Draw Handler + `gpu` 模块 |
|---|---|---|
| 擅长 | 可拖拽的手柄（箭头/圆环/方块）、内置预设形状（`draw_preset_arrow/box/circle`）、选中高亮、与 Tool 系统联动 | 任意叠加绘制：推断标记（端点/中点/交点/面上点）、橡皮筋线、预览面、尺寸文字、参考线 |
| 事件 | 通过 `test_select` / `invoke` / `modal` 响应手柄拖拽；`draw_prepare` 里**拿不到鼠标事件**（只能靠 `test_select` 的区域坐标） | 在 modal operator 里直接拿到完整 `event`（鼠标坐标、按键、修饰键），绘制数据由 operator 持有 |
| 命中测试 | 内置 `draw_select` 选中渲染，Blender 帮你算点中了哪个手柄 | 需自己算：`view3d_utils.region_2d_to_*` + `BVHTree` / `ray_cast` |
| 生命周期 | `PERSISTENT` / `SHOW_MODAL_ALL` / `SCALE` 等 `bl_options` 控制；随 Tool 激活/失活 | 手动 `draw_handler_add/remove`，operator 结束必须移除 |
| 适用工具 | Move/Rotate/Scale 的三轴手柄、剖面手柄 | Line/PushPull/FollowMe 等的全部预览、推断系统 |
| 复杂度 | 中高（Gizmo + GizmoGroup + 绑定 operator/属性三件套） | 中（gpu batch + shader + 状态恢复） |
| 风险 | 与 Tool 系统耦合深，调试难；Python Gizmo 的 `test_select` 行为有已知坑 | 忘记恢复 `gpu.state` 会污染后续绘制；忘记移除 handler 会残留 |

**推荐分工：**

- **主力：Modal Operator + gpu draw handler。** 推断引擎的全部视觉反馈（标记、锁定轴虚线、预览几何、VCB 文字）都走这条路。这是 Knife/Loop Cut 等内置工具的实际做法，社区共识明确。
- **GizmoGroup：只在第二阶段为 Move/Rotate/Scale 做三轴手柄时引入**，且手柄最终调用的仍是同一个 modal operator（`target_set_operator`）。第一阶段不做 Gizmo，避免两套交互机制并行。
- **不用 Annotation / Grease Pencil 做预览。** 它们是持久数据（会存进文件、参与撤销），不适合做临时预览。

### 3.3 绘制细节（gpu 模块）

- 入口：`bpy.types.SpaceView3D.draw_handler_add(callback, args, 'WINDOW', 'POST_VIEW')`（3D 几何）和 `'POST_PIXEL'`（2D 文字/标记）；移除用 `draw_handler_remove(handle, 'WINDOW')`。
- Shader：`gpu.shader.from_builtin('UNIFORM_COLOR')`（实色）、`POLYLINE_UNIFORM_COLOR`（抗锯齿折线，SketchUp 风格的线宽/虚线需用它或自定义 shader）、`FLAT_COLOR` 等。**禁止用 `bgl`，禁止用带 `3D_` 前缀的旧 shader 名。**
- Batch：`gpu.types.GPUBatch` + `batch.draw(shader)`；顶点数据变化时重建 batch（推断预览每帧重建小 batch 是可接受的，大场景需缓存）。
- 状态：绘制回调开头设置 `gpu.state.blend_set` / `depth_test` / `line_width` 等，**结尾必须恢复默认值**，否则会污染 Blender 自身 UI。
- 文字：用 `blf` 模块（`blf.position` / `blf.size` / `blf.draw`）在 `POST_PIXEL` 里画 VCB 提示和推断标签；中文字体需注意 `blf.load` 字体路径（Windows 上找系统字体，见“不确定事项”）。
- 线程：所有 gpu 操作必须在主线程；禁止在后台线程建 shader/batch。
- Headless：`bpy.app.background` 为真时不要注册 draw handler、不要建 gpu 资源（无 GPU 上下文会失败）；绘制代码要能被测试跳过。

### 3.4 拾取与射线（推断引擎的输入）

- 屏幕→3D：`bpy_extras.view3d_utils` 的 `region_2d_to_origin_3d` / `region_2d_to_vector_3d` / `region_2d_to_location_3d` / `location_3d_to_region_2d`。
- 射线命中：`BVHTree.FromObject` / `BVHTree.FromBMesh` + `ray_cast`，或 `scene.ray_cast(depsgraph, origin, direction)`。推断引擎需要“最近的点/边/面 + 距离排序”，BVHTree 是正确工具；不要用 `object.ray_cast` 逐对象暴力循环（大场景慢）。
- 深度：推断要区分“鼠标正下方的几何”和“被遮挡的几何”，需用射线第一个命中 + 屏幕距离容差双重判断（细节归调研 B）。

---

## 4. 快捷键冲突处理

### 4.1 机制：KeyConfig / KeyMap / KeyMapItem

Blender 的快捷键分四层 keyconfig（官方 `bpy.types.KeyMaps` 文档）：

| KeyConfig | 含义 | 插件能不能写 |
|---|---|---|
| `default` | Blender 内置默认绑定 | 不能 |
| `active` | 当前预设（如 Blender / Industry Compatible / 2.7x），叠在 default 之上 | 不能 |
| `addon` | **插件的默认绑定**，用户可在偏好设置里改 | **只能写这一层** |
| `user` | 用户自己的修改，叠在 addon 之上 | 不能直接写（用户改 addon 快捷键后，修改存在 user 层） |

规则（官方文档原话精神）：

- **插件只操作 `keyconfigs.addon`，绝不改用户 keymap**，否则会覆盖用户自己的偏好。
- 注册时保存 `(keymap, keymap_item)` 元组列表，注销时逐个 `keymap_items.remove(kmi)`；**不要删除整个 keymap**（其他插件可能也在用同一个 keymap）。
- `keymaps.new(name=..., space_type=..., region_type=...)` 的 `name` 必须与已存在的 keymap 名一致（如 `'Window'`、`'3D View'`、`'Object Mode'`、`'Mesh'`），否则不生效。不能凭空发明 keymap 名。
- **Headless（`--background`）时 `wm.keyconfigs.addon` 为 None**，注册代码必须判空，否则 headless 测试会崩。
- Modal keymap：Python **不能新建** modal keymap，只能往已有的 modal keymap（如 “Knife Tool Modal Map”）里加项；本项目的 modal 内按键（数字、方向键、Shift）应在 `modal()` 里直接处理，不走 keymap。
- 用户可在 Preferences → Keymap 里看到并修改 addon 的快捷键；插件应在偏好设置里说明“去 Keymap 面板改键”。

### 4.2 冲突现实：SketchUp 单字母键 vs Blender 单字母键

SketchUp 的 Large Tool Set 大量使用**无修饰单字母键**（L/R/P/M/Q/S 等，具体清单归调研 A），而 Blender 在 Object/Edit 模式下同样大量使用单字母键（G 移动、R 旋转、S 缩放、E 挤出、F 成面、P 分离、L 选中相连、M 移入集合……）。**两者几乎必然正面冲突，不存在“全量共存”的方案，必须做取舍。**

### 4.3 推荐方案：三档总开关 + 作用域收窄

在 AddonPreferences 里提供：

| 档位 | 行为 | 适用 |
|---|---|---|
| **0：关闭** | 不注册任何 SketchUp 快捷键，只用菜单/工具栏/N 面板 | 与其他重度 Blender 用户共存；排查冲突时 |
| **1：SketchUp 模式（推荐默认，需 Sen 定）** | 注册全套 SketchUp 单字母键到 `3D View` / `Object Mode` / `Mesh` keymap；同时提供一个“临时切回 Blender 键”的开关 operator（建议绑一个不冲突的组合键，如 `Ctrl+Alt+K`，或 N 面板里的开关按钮） | Sen 的主力用法：在 Blender 里当 SketchUp 用 |
| **2：仅组合键** | SketchUp 工具只绑 `Alt+字母` / `Ctrl+Alt+字母` 等不冲突的组合键，单字母留给 Blender | 想两套都用、愿意多按修饰键的用户 |

实现要点：

- 档位切换 = 注销旧 keymap 项 + 注册新 keymap 项（动态 `register_keymaps()` / `unregister_keymaps()`），不要只靠 `poll` 挡（`poll` 挡不住 keymap 层面的抢占——先匹配到的 keymap 项会吃掉按键）。
- 每个 keymap 项的 `poll` 里再加一道“当前在 3D 视图且不在文本输入框”的判断，避免在属性栏输数字时触发工具。
- 提供“冲突报告”：注册时扫描 `keyconfigs.active` 里同键位的已有绑定，列出被覆盖的 Blender 功能，写进偏好设置面板或日志，让用户知情（不要静默覆盖）。
- 提供一键“恢复 Blender 默认”：注销全部 addon keymap 项（即档位 0）。
- 快捷键表要做成**数据表驱动**（一个 Python 字典/JSON：工具 → 键位），不要散落在各处 `keymap_items.new` 调用里；调研 A 的快捷键清单直接填进这张表。
- **默认档位需 Sen 定**：本调研倾向默认档位 1（因为项目目标就是“在 Blender 里用 SketchUp 逻辑建模”，默认关闭等于没复刻），但必须在首次启用时弹窗/面板明确告知“已接管单字母键，可在偏好设置里关掉”。

### 4.4 其他注意

- Industry Compatible 预设的用户：keymap 结构不同，冲突表会不同；第一阶段只保证 Blender 默认预设，Industry Compatible 列为“已知未测”。
- macOS 的 Cmd 键与 Windows 的 Ctrl 键在 keymap 里都用 `oskey` 区分；本项目目标 Windows，可先不处理 Cmd，但代码里不要把 `oskey` 写死。

---

## 5. 菜单 / 面板落点：SketchUp 菜单在 Blender 里的对应

### 5.1 Blender 侧可用的落点

| 落点 | API | 特点 |
|---|---|---|
| **3D 视图头栏菜单** | `bpy.types.Menu` + `VIEW3D_MT_editor_menus.append`（新增顶级菜单）或往现有菜单（`VIEW3D_MT_view`/`VIEW3D_MT_object` 等）`append/prepend` | 最接近 SketchUp 的顶部菜单栏；可放完整 Tools 菜单结构 |
| **工具栏（左侧 T 栏）** | `bpy.types.WorkSpaceTool` + `bpy.utils.register_tool` / `unregister_tool` | SketchUp Large Tool Set 的对应物；支持分组、分隔符、图标、工具设置面板 |
| **N 面板（右侧边栏）** | `bpy.types.Panel`，`bl_space_type='VIEW_3D'`，`bl_region_type='UI'`，`bl_category='SketchUp'` | 放工具按钮阵列、VCB 输入框、Tag/材质/组件面板；常驻可见 |
| **右键上下文菜单** | 往 `VIEW3D_MT_object_context_menu` / `VIEW3D_MT_edit_mesh_context_menu` 等 `append` | SketchUp 右键菜单的对应物；必须按选择状态动态显示（`poll` / `draw` 里判断） |
| **Pie 菜单** | `bpy.types.Menu` + `wm.call_menu_pie`（经 keymap 触发） | 适合“快速切工具”的径向菜单；可选，不做主力 |
| **工具设置（Tool Settings）** | `WorkSpaceTool.draw_settings` + `TOOL_PROPS` region | 每个工具的参数（段数、偏移距离等）显示在这里，类似 SketchUp 的工具选项 |
| **状态栏/头栏文字** | `context.area.header_text_set()`（modal 期间） | 显示当前工具提示和 VCB 数值，类似 SketchUp 的状态栏 |
| **顶栏（Topbar）File/Edit 菜单** | 理论上可 append，但**不建议** | Blender 的顶栏是全局的，往 File/Edit 里塞 SketchUp 菜单会污染所有编辑器；SketchUp 的 File/Edit/View 菜单与 Blender 的语义差异大，复刻价值低 |

### 5.2 推荐落点表（SketchUp 结构 → Blender 落点）

| SketchUp 侧 | Blender 落点 | 备注 |
|---|---|---|
| Large Tool Set（工具栏图标） | **工具栏 WorkSpaceTool**，按 SketchUp 分组（选择/绘图/修改/相机/辅助）分 `group` + `separator` | 图标：先用 Blender 内置 icon 名近似，后续可换自定义图标（`bpy.utils.previews`）；图标风格需 Sen 定 |
| Tools 菜单（完整结构、顺序） | **3D 视图头栏新增 “SketchUp” 顶级菜单**，内按 SketchUp 的 Tools 菜单顺序分子菜单；同时在 N 面板里放一份按钮版（同源数据表驱动） | 头栏菜单是“完整复刻”的主载体；N 面板是快捷入口。两者必须由同一份菜单定义数据生成，避免 drift |
| 右键菜单（建模相关项） | **右键上下文菜单 append**，按选择类型（面/边/组/组件/空选）分段显示 | 只复刻建模相关项；视图/显示类右键项归 Blender 原生 |
| VCB / Measurements 输入框 | **三处同显**：① modal 期间头栏文字（主显示）；② N 面板里的输入框（可点击输入）；③ 工具设置区（参数回显） | 三处读写同一份 VCB 状态（`WindowManager` 上的 PropertyGroup），避免三份状态不一致 |
| Entity Info / Tags / Materials / Components 面板 | **N 面板**，`bl_category='SketchUp'` 下分子面板（或 `bl_parent_id` 折叠子面板） | 对应 SketchUp 的 Default Tray；Blender 的 Properties 编辑器不做主力（离 3D 视图太远） |
| Scenes（场景） | N 面板 + 头栏菜单 | 映射到 Blender 的相机 + 视图记忆（细节归调研 B） |
| 剖面（Section） | N 面板 + 工具栏工具 | 映射到 Blender 的 Clipping / Boolean 方案（细节归调研 B） |

### 5.3 关键约束（必须向 Sen 说清楚）

- **Blender 不允许插件“替换”主菜单栏。** SketchUp 的 File/Edit/View/Camera/Draw/Tools/Window/Extensions/Help 整条菜单栏无法 1:1 搬过来；能做的是在 3D 视图头栏**新增**一个 “SketchUp” 菜单 + 工具栏 + N 面板。**“完整复刻工具菜单”在本项目里应理解为“Tools 菜单 + Large Tool Set + 建模右键菜单的完整复刻”，而非整条 SketchUp 菜单栏的像素级复刻。** 这一点需 Sen 在方案评审时确认（见“不确定事项”第 1 条）。
- 工具栏的 `WorkSpaceTool` 是**按模式（Object/Edit/Sculpt 等）分**的（`bl_context_mode`）；SketchUp 没有 Object/Edit 模式之分，本项目需决定：工具只在 Object 模式注册，还是 Object + Edit 双注册（推荐双注册，工具内部自己处理“当前在哪个对象里画”的逻辑，见调研 B 的数据模型映射）。
- 菜单/工具栏/N 面板的**定义必须数据表驱动**（一份 Python 数据结构描述：id、标签、图标、快捷键、operator、分组、顺序），三个 UI 落点都从这张表生成；调研 A 的清单就是这张表的输入。

---

## 6. 设置与数据存储 + 撤销

### 6.1 三层存储（按生命周期分）

| 层 | 载体 | 存什么 | 生命周期 | 示例 |
|---|---|---|---|---|
| **L1：用户偏好（跨文件）** | `AddonPreferences`（存于 `userpref.blend`） | 快捷键档位、推断开关默认、推断颜色/容差、默认单位、语言、图标风格 | 跨 Blender 会话、跨 .blend 文件 | `inference_enabled`、`shortcut_mode`、`default_unit` |
| **L2：场景状态（随文件）** | `PropertyGroup` + `PointerProperty` 挂在 `bpy.types.Scene` 上 | 当前 Tag、当前材质、剖面可见性、场景级推断开关、SketchUp 式单位设置 | 随 .blend 文件保存/加载；新文件用默认值 | `scene.sketchup.current_tag`、`scene.sketchup.active_material` |
| **L3：对象/网格数据（随对象）** | ID 自定义属性（`obj["sketchup_xxx"]`）+ 正规 `bpy.props`（挂在 Object/Mesh 上） | 组/组件身份（definition id、是否为组件实例）、Tag 归属、锁定/隐藏、每面材质（经 `material_index`） | 随对象复制/链接/保存 | `obj["sketchup_definition_id"]` |
| **L0：会话临时状态（不保存）** | `PropertyGroup` 挂在 `WindowManager` 上，或 operator 实例属性 | 当前激活工具、VCB 缓冲、轴向锁定、推断高亮 | 只在当前会话/当前 operator 内有效，关文件即失 | `wm.sketchup.vcb_buffer` |

规则：

- **L1/L2/L3 必须用 `bpy.props` + PropertyGroup**（自动保存、自动生成 UI、可撤销、可动画），不要用 Python 全局变量存持久状态（重启即失，且多窗口会乱）。
- **L3 优先用正规 `bpy.props`**（挂在 `bpy.types.Object` 上），只在“动态键、实验字段”时用 ID 自定义属性（`obj["key"]`）；ID 属性无类型校验、无 UI，滥用会变成“暗数据”。
- 注册时 `bpy.types.Scene.sketchup = PointerProperty(...)`，注销时必须 `del bpy.types.Scene.sketchup`，否则禁用插件后属性残留。
- `AddonPreferences.bl_idname` 必须等于 `__package__`（Extension 命名空间要求），访问时用 `context.preferences.addons[__package__].preferences`。
- 外部文件（预设、缓存、日志）走 `bpy.utils.extension_path_user(__package__, create=True)`，不要写扩展目录、不要写 Blender 安装目录。

### 6.2 SketchUp 式状态的具体映射（存储机制层面；语义映射归调研 B）

| SketchUp 概念 | Blender 存储建议 | 备注 |
|---|---|---|
| 当前材质 | L2（Scene）存材质指针 + L3 每面 `material_index` | 材质本身用 `bpy.data.materials`（Principled BSDF）；SketchUp 的“正反面材质”需双材质槽或自定义属性，细节归调研 B |
| Tag（图层） | L2 存 Tag 列表（CollectionProperty）+ L3 每对象存 tag 名；可见性经 Collection 的 `hide_viewport` / ViewLayer 控制 | SketchUp 的 Tag ≠ Blender Collection（一个对象可属多个 Collection，但 SketchUp 里一个对象只有一个 Tag）；需用 L3 属性强制“单 Tag”语义，不能只靠 Collection 归属 |
| 组（Group） | 单个 Object（Mesh）+ L3 标记 `is_group=True` + 父子关系 | 组内编辑 = 进入该 Object 的“编辑上下文”（本项目自建上下文栈，不是 Blender Edit Mode） |
| 组件（Component） | **链接复本（linked duplicate）**：多个 Object 共享同一个 Mesh datablock（`ob2.data = ob1.data`）；或**集合实例**（Empty + `instance_type='COLLECTION'`） | 单网格组件用链接复本（最轻、最像 SketchUp）；多对象组件用集合实例。两者都要存 `definition_id` 以便“编辑定义时同步所有实例” |
| 剖面（Section Plane） | L2 存剖面列表 + 空对象（Empty）表示剖面位置/法线 | 剖切显示经材质/布尔/裁剪实现（细节归调研 B） |
| 参考线/参考点 | 独立的 Object（曲线/Empty）+ L3 标记，或 L2 列表 + draw handler 绘制 | 无限长参考线在 Blender 里没有原生对应物，需自建（细节归调研 B） |
| 场景（Scene） | L2 存场景列表（相机位姿 + 可见性 + 剖面状态） | 映射到 Blender 相机对象 + 视图参数快照 |

### 6.3 撤销（Undo）

- **所有改数据的 operator 必须加 `bl_options = {'REGISTER', 'UNDO'}`**（官方 Add-on Tutorial 的标准写法）。`UNDO` 会在 operator 完成时推一个撤销步；缺了它，Ctrl+Z 无法撤销该操作——这是最常见的插件 bug。
- **粒度：一次完整的工具动作 = 一个撤销步。** 如画一条线（多点）完成时推一个撤销步；推拉完成时推一个撤销步。Modal 过程中的鼠标移动**绝不**推撤销步（预览不写数据，自然无撤销问题）。
- **Modal operator 的撤销：** 在 `modal()` 返回 `{'FINISHED'}` 时，Blender 按 `UNDO` 标志推撤销步；返回 `{'CANCELLED'}` 时不推（且必须手动恢复预览期间的任何临时修改——正确做法是预览期间不改数据，取消时无事可做）。
- **非 operator 路径**（如 Gizmo 拖拽回调、handler 回调里改数据）：手动 `bpy.ops.ed.undo_push(message="...")`。不要在循环/每帧里调用。
- **不要嵌套调用带 UNDO 的 `bpy.ops`**：在 operator 的 `execute()` 里调用另一个带 UNDO 的 `bpy.ops` 会产生多余的撤销步/redo 面板混乱。几何操作应直接调 `bmesh` / `bpy.data` API，不要调 `bpy.ops.mesh.*`（除非明确需要其 redo 语义并处理好 `undo` 位置参数）。
- **Redo（F9 / Adjust Last Operation）：** 依赖 operator 的属性（`bpy.props`）重放；modal 工具如需支持“改参数重做”，需把关键参数（长度、份数、角度）存为 operator 属性，并在 `execute()` 里用属性重算。第一阶段可先做到“可撤销、不可 redo 改参”，在方案里写明。
- **撤销与 L2/L3 属性：** 经 `bpy.props` 注册的属性修改会自动进撤销系统；直接改 Python 对象的属性不会。不要用“Python 对象存状态 + 手动同步”的做法。
- **待核实：** Blender 5.x 的 `bl_undo_group` / `UNDO_GROUPED` 语义（连续同类操作合并撤销步，如 SketchUp 的连续画线是否应合并）；第一阶段不依赖它，列为后续优化项。

---

## 7. 自动化测试：`blender --background` 的可行做法与限制

### 7.1 可行的命令（官方手册 Command Line Arguments）

```bash
# Linux（本机 CI / 开发机）
blender --background --factory-startup --python-exit-code 1 --python tests/run_headless.py -- --verbose

# Windows（Sen 的机器 / CI 的 Windows runner）
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python-exit-code 1 --python tests\run_headless.py -- --verbose
```

标志说明（官方手册）：

| 标志 | 作用 |
|---|---|
| `-b` / `--background` | 无 GUI 运行（常用于无界面渲染/自动化） |
| `--factory-startup` | 跳过用户 `startup.blend`、偏好设置和已启用插件，保证可复现 |
| `--python <file>` / `-P` | 执行指定 Python 脚本（在 Blender 内置 Python 里跑，`bpy` 可用） |
| `--python-exit-code <n>` | 脚本抛异常时以该码退出（0 表示禁用）；**必须放在 `--python` 之前**，否则不生效；没有它，脚本崩了退出码仍为 0，CI 发现不了 |
| `--` | 之后的参数留给脚本自己解析（`sys.argv` 里 `--` 之后的部分） |

其他有用标志：`--factory-startup` + `--config <dir>`（隔离配置目录，CI 用）、`-noaudio`、`--python-expr`（单行表达式，快速冒烟）。

### 7.2 分层测试建议

| 层 | 内容 | 运行环境 | 能测什么 | 不能测什么 |
|---|---|---|---|---|
| **T0：静态检查** | `python -m py_compile` / `ruff` / `flake8`、manifest 校验（TOML 合法、必需字段齐全、zip 顶层结构正确） | 系统 Python，无 Blender | 语法、导入、打包结构 | 任何 Blender 行为 |
| **T1：纯逻辑单元测试** | `pytest` / `unittest`，测 `core/` 里的纯函数：VCB 解析、单位换算、推断几何计算（点到线/面距离、轴向投影）、成面算法（用自建的轻量几何结构，不依赖 bmesh） | 系统 Python，无 Blender | 逻辑正确性、边界条件、回归 | bmesh/Blender 数据交互 |
| **T2：Headless bpy 集成测试** | `blender --background --python tests/run.py`，测：扩展安装/启用/禁用（`bpy.ops.preferences.addon_enable`）、类注册无报错、operator 的 `execute()`（直接调 `bpy.ops.sketchup.xxx` 或直接实例化调函数）、bmesh 几何操作结果（顶点/边/面数、法线、材质索引）、组/组件/Tag 映射、文件保存/重开 round-trip、撤销（`bpy.ops.ed.undo()` 后数据复原） | Blender headless | 除交互外的几乎全部数据逻辑 | 见下 |
| **T3：真机 GUI 手工清单** | Sen 在 Windows 5.2 LTS 上按检查表操作：每个工具的鼠标交互、推断标记显示、VCB 输入、快捷键、菜单/工具栏/N 面板、Gizmo（如有）、撤销/重做、中文显示 | Sen 的 Windows 真机 | 全部交互体验 | 无法自动化 |
| **T4（可选）：GUI 冒烟脚本** | 在有界面的 Blender 里用 `--python` + `bpy.app.timers` 驱动的半自动脚本（如自动建场景、截图 `bpy.ops.screen.screenshot`、比对像素） | 有界面的 Blender | 粗粒度回归（“没崩、画面大体对”） | 精确的鼠标/键盘交互仍需人工 |

### 7.3 Headless 的硬限制（必须如实写进方案）

- **没有窗口/区域/视图**：`bpy.context.window` / `area` / `region` / `space_data` / `region_3d` 在 headless 下为 None 或不可用；`keyconfigs.addon` 为 None（keymap 注册必须判空）；`SpaceView3D.draw_handler_add` 无意义（无 GPU 上下文）。
- **Modal operator 无法 headless 测交互**：没有事件循环，`modal()` 收不到真实鼠标/键盘事件；只能直接调 `execute()` 或把状态机抽出来用合成事件对象测（`event` 是 `bpy.types.Event`，不能随意构造——建议把状态机逻辑抽成纯函数，输入为“（x, y, 按键）”三元组，与 `bpy.types.Event` 解耦，T1 层测状态机，T2 层测 `execute()`）。
- **Gizmo 无法 headless 测**：Gizmo 的选中/拖拽依赖视口渲染和事件系统。
- **gpu/blf 绘制无法 headless 测**：无 GPU 上下文，`gpu.shader.from_builtin` 等会失败；绘制代码必须用 `bpy.app.background` 守卫，测试时跳过。
- **射线拾取需 depsgraph**：`scene.ray_cast` / `BVHTree.FromObject` 在 headless 下可用（纯几何计算），但“屏幕坐标→射线”需要 `region_3d`（headless 无），所以推断引擎要分两层：**几何层**（输入射线，输出命中，可 headless 测）+ **屏幕层**（输入鼠标像素，输出射线，只能真机测）。
- **截图/渲染**：headless 可以渲染（Cycles/EEVEE），但 EEVEE 在无 GPU 的 Linux 上可能失败；不要把渲染结果作为核心断言。

### 7.4 对代码结构的要求（由测试分层倒推）

- **`core/` 必须与 `bpy` 解耦**：推断几何、VCB 解析、单位换算写成纯 Python（只用 `math` / 标准库，或用可替换的向量类型），T1 层不用 Blender 就能测。
- **每个工具的“提交函数”必须独立**：`def apply_line(bm, p1, p2, ...)` 这种纯 bmesh 函数，T2 层直接调并断言结果；modal operator 只是“事件 → 参数 → 提交函数”的薄壳。
- **测试夹具**：准备一组 `.blend` 文件（空场景、带组/组件的场景、带材质的场景），T2 层加载后断言；夹具文件放仓库 `tests/fixtures/`，不随扩展 zip 发布。
- **CI**：Linux 上装 Blender 便携版（解压即用，无需安装）跑 T0+T1+T2；Windows 真机只跑 T3 手工清单（Sen 测）。不要在 CI 里跑 GUI 测试。

---

## 8. 范围界定：三类清单

> 判定原则：项目目标是“在 Blender 里用 SketchUp 的建模逻辑完成建模”+“完整复刻建模工具和工具菜单”。凡是**建模本体**的在内；凡是**另一个产品/在线服务/另一种语言生态**的在外；凡是**建模相关但工作量巨大或语义不清**的待 Sen 定。

### 8.1 在范围内（In Scope）

| 项目 | 一句话理由 | 备注 |
|---|---|---|
| Large Tool Set 全部建模工具（选择、直线、矩形、圆形、圆弧、多边形、徒手画、推拉、移动、旋转、缩放、偏移、跟随路径、量角器、卷尺、标注、油漆桶、橡皮等） | 项目目标第一条就是完整复刻建模工具 | 完整清单归调研 A；本调研只定架构落点 |
| Tools 菜单完整结构（分组、顺序） | 项目目标第二条 | 落点见 §5；整条 SketchUp 菜单栏不复刻（见 §5.3） |
| 建模相关右键菜单 | 建模流程的一部分（成组、炸开、翻转、隐藏、锁定等） | 只含建模项 |
| 推断引擎（端点/中点/交点/面上点/轴向锁定/参考线） | SketchUp 建模逻辑的核心，没有它就不叫 SketchUp 逻辑 | 语义归调研 B；架构见 §3 |
| VCB / Measurements 数字输入 | SketchUp 精确建模的核心，没有它无法精确建模 | 见 §3.1 |
| 面的生成与愈合、边线相交打断 | SketchUp “画线成面”的核心逻辑 | 归调研 B 的几何规格 |
| 组与组件（创建、编辑、炸开、Make Unique、实例同步） | SketchUp 组织模型的核心机制 | 存储见 §6.2；语义归调研 B |
| Tag（图层）管理（创建、分配、可见性） | SketchUp 组织/显示模型的核心机制 | 存储见 §6.2 |
| 材质基础（创建、赋予、编辑颜色/贴图、取色） | 建模时必须能给面赋材质 | 复用 Blender 材质系统，不自建渲染器；“正反面材质”语义归调研 B |
| 剖面（Section Plane）基础（创建、移动、显隐、剖切显示） | 建筑/室内建模的常用机制，属建模本体 | 显示实现（裁剪/布尔）归调研 B |
| 场景（Scenes）基础（保存/恢复相机视角+可见性状态） | 建模时查看模型的机制，属建模本体 | 不含 LayOut 联动、不含动画导出 |
| 实体信息（Entity Info）查看/改名/改 Tag | 建模时查看/编辑对象属性的面板 | N 面板实现 |
| 尺寸标注与文字标注（基础） | 建模图纸表达的一部分，属建模工具 | 复杂排版不在内 |
| 实体工具（Solid Tools：并集/减/交/修剪/分割）基础 | 建模布尔操作，属建模本体 | 用 Blender 布尔实现；放较后阶段 |
| 单位与精度设置、模型信息 | 建模的基础设置 | 映射到 Blender 场景单位 |

### 8.2 不在范围内（Out of Scope）

| 项目 | 一句话理由 |
|---|---|
| **LayOut** | 是另一个独立的 2D 排版/出图产品，不是 Blender 插件能复刻的，也不在“建模”目标内 |
| **3D Warehouse** | 是 Trimble 的在线模型库服务，需账号/联网/API，非本地建模功能；且扩展声明网络权限会增加用户授权与安全审查负担 |
| **渲染器复刻**（SketchUp 风格渲染、V-Ray 等） | Blender 自带 Cycles/EEVEE，直接用原生渲染即可；复刻渲染器是另一个大项目 |
| **Ruby API 兼容**（让 SketchUp 的 Ruby 插件在 Blender 里跑） | 两种语言/两种运行时/两种数据模型，兼容层工作量不亚于重写 SketchUp，且 SketchUp Ruby API 表面极大 |
| **插件扩展生态**（.rbz 安装、Extension Warehouse） | 与 Ruby API 同理；且运行第三方 Ruby 代码有安全风险 |
| **.skp 文件读写** | .skp 是 Trimble 未公开规范的专有二进制格式，须经官方 SketchUp SDK（C API）或逆向工程实现，工作量大、版本兼容风险高、且有授权/法律不确定性；Blender 原生也不支持 .skp（见 §8.4 补充） |
| **.dwg 读写** | DWG 是 Autodesk 专有格式，需 ODA 等第三方库/授权，非纯 Python 插件能承担 |
| **.dxf 读写（自研）** | Blender 原生无 DXF 导入导出，自研 DXF 解析是 CAD 交换项目，不在建模目标内（可用 Blender 原生格式中转） |
| **动态组件（Dynamic Components）** | 是带公式/参数/交互行为的独立子系统，依赖 SketchUp 的属性公式引擎与 Ruby 行为，与普通组件是两套机制 |
| **照片匹配（Match Photo）** | 是照片校准/相机反求的独立功能，与建模工具无直接关系 |
| **高级相机工具（Advanced Camera Tools）** | 是影视级相机/胶片模拟的独立功能，与建模无关 |
| **地理定位 / 地形导入（Add Location）** | 依赖在线地图/地形服务与 Trimble 账号，非本地建模功能 |
| **Trimble Connect 协作** | 在线协作服务，需账号/联网，非本地建模功能 |
| **报告生成（Generate Report）/ IFC 分类** | 是 BIM/算量方向的独立功能，不在“建模逻辑”目标内 |
| **动画导出 / 视频导出** | 属演示/输出功能，Blender 自带时间轴与视频序列器，直接用原生即可 |

### 8.3 待 Sen 定（To Be Decided）

| 项目 | 一句话理由 | 需 Sen 定的点 |
|---|---|---|
| **沙盒工具（Sandbox：From Contours / From Scratch / Smoove / Drape / Add Detail / Flip Edge）** | 属建模工具但 SketchUp 里是自带扩展（非核心工具集），且地形网格逻辑较独立 | 是否纳入“完整复刻”？如纳入，放第几阶段？ |
| **地形/网格 sculpt 类工具** | 与沙盒相关；Blender 自带 Sculpt 模式，是否需要 SketchUp 式地形工具需权衡 | 是否做？还是引导用户用 Blender Sculpt？ |
| **.obj / .fbx / .stl / .dae / .gltf 导入导出** | Blender 原生已支持这些格式，无需插件自研；问题是“是否需要 SketchUp 风格的导入导出选项/单位处理” | 是否只用 Blender 原生导入导出（推荐），还是要包一层 SketchUp 式选项？ |
| **样式（Styles）/ 阴影（Shadows）显示** | SketchUp 的边线风格/阴影是其视觉标识，但 Blender 视口显示机制完全不同（Workbench/EEVEE） | 是否要复刻 SketchUp 式显示风格（如手绘边线、阴影开关）？做到什么程度？ |
| **组件库 / 本地组件浏览器** | SketchUp 的 Components 面板可浏览本地 .skp 组件库；Blender 有 Asset Browser | 是否做 SketchUp 式组件库面板，还是直接用 Blender Asset Browser？ |
| **快捷键默认档位**（见 §4.3） | 直接影响 Sen 的日常使用体验 | 默认开 SketchUp 单字母键，还是默认关闭？ |
| **右键语义**（工具进行中右键 = 取消 vs 菜单） | SketchUp 与 Blender 的惯例冲突（见 §3.1） | 工具进行中右键取消、工具空闲时右键菜单？还是其他方案？ |
| **中文字体/界面语言** | VCB 提示、推断标签、面板文字的中英文 | 插件界面默认中文还是英文？是否做中英切换（参考 MSPhysics 的语言切换）？ |
| **Blender 最低版本**（见 §1.2） | 影响兼容工作量 | manifest 写 5.2.0（只保 5.2 LTS）还是 4.2.0（尽力兼容 4.x）？ |
| **扩展 id 与显示名、许可证** | 影响发布与升级 | id、显示名、维护者、GPL 还是其他许可证？ |

### 8.4 补充：.skp 为什么在外（给 Sen 的解释口径）

- .skp 是 Trimble 的**专有二进制格式，从未公开过规范**，文件头/结构随 SketchUp 大版本变化（新版文件旧版打不开是常态）。
- 官方途径是 **SketchUp SDK（C API）**：需引入 C 库、处理 Windows 构建、遵守 SDK 授权，纯 Python 扩展无法直接用；且 SDK 的版本与 SketchUp 版本绑定，维护负担重。
- 社区有逆向工程项目（如 OpenSKP，Python/TypeScript/.NET/Dart/C++ 五种语言实现读写），但属于逆向实现，**保真度（尤其动态组件、复杂材质、场景）与长期维护均无官方保证**，且引入第三方逆向库有法律/合规不确定性，需 Sen 明确授权才可评估。
- **替代路径（推荐）：** 模型交换走 Blender 原生支持的格式（.obj/.fbx/.stl/.gltf/.dae），SketchUp 侧用 Pro 版导出这些格式即可互通；.blend 文件本身就是本插件的“原生格式”，不需要 .skp。
- 如 Sen 坚持要 .skp 互通，应单独立项评估（SDK 路线 vs OpenSKP 路线），不在第一阶段范围内。

---

## 不确定 / 需问 Sen 的事项

（汇总本调研中无法自行决定的事项，按优先级排；负责人统稿时可直接转问卷）

1. **“完整复刻工具菜单”的边界**：Blender 无法替换主菜单栏，只能在 3D 视图头栏新增 “SketchUp” 菜单 + 工具栏 + N 面板。是否接受“Tools 菜单 + Large Tool Set + 建模右键菜单完整复刻，File/Edit/View 等整条菜单栏不复刻”？（见 §5.3）
2. **Blender 最低版本**：manifest 写 `5.2.0`（只保 5.2 LTS）还是 `4.2.0`（尽力兼容 4.x）？（见 §1.2）
3. **快捷键默认档位**：默认开启 SketchUp 单字母键（接管 G/R/S 等），还是默认关闭、只用菜单？（见 §4.3）
4. **右键语义**：工具进行中，右键 = 取消（Blender 惯例）还是 = 弹出菜单（SketchUp 惯例）？（见 §3.1）
5. **沙盒工具与地形**：是否纳入复刻范围？放第几阶段？（见 §8.3）
6. **样式/阴影显示**：是否要复刻 SketchUp 式视口风格？做到什么程度？（见 §8.3）
7. **界面语言**：默认中文还是英文？是否做中英切换？（见 §8.3）
8. **导入导出**：.obj/.fbx/.stl 等是否只用 Blender 原生，不包 SketchUp 式选项？（见 §8.3）
9. **.skp 互通**：是否接受“不在范围内，走 Blender 原生格式中转”？如坚持要，是否授权评估 SDK/OpenSKP 路线？（见 §8.4）
10. **扩展 id / 显示名 / 许可证 / 维护者**：定名与许可证（建议 GPL-3.0-or-later，与 Blender 插件惯例一致）。
11. **Sen 的 Blender 安装情况**：Sen 的 Windows 机器上是否已装 Blender？装的是哪个版本？如未装，是否接受装 5.2 LTS 做真机测试？
12. **中文字体**：VCB/推断标签如需显示中文，Windows 上用哪个系统字体文件？（技术上可用 `blf.load` 加载 `C:\Windows\Fonts\*.ttf`，但需确认 Sen 机器上的字体可用性；或先只显示英文/数字，中文界面放后面阶段。）

---

## 来源列表

（官方文档优先；第三方资料仅用于版本/兼容性交叉核对，已注明）

### 官方（docs.blender.org / blender.org）

- Blender 5.2 LTS 发布页：https://www.blender.org/download/releases/5-2/ （发布日期 2026-07-14、LTS 支持至 2028-07）
- Blender LTS 页：https://www.blender.org/download/lts/4-2/ （4.2 LTS 已结束支持、4.5 LTS 支持至 2027-07、5.2 LTS 支持至 2028-07）
- Add-ons（Legacy vs Extension）：https://docs.blender.org/manual/id/4.2/advanced/extensions/addons.html （Extension 自包含、转 Extension 四步、`__package__` 命名空间）
- Add-on Tutorial：https://docs.blender.org/manual/en/4.2/advanced/scripting/addon_tutorial.html （`bl_info` / `register` / `unregister` / `{'REGISTER','UNDO'}`）
- How to Create Extensions（5.1/5.2/5.3 Manual）：https://docs.blender.org/manual/sr/latest/advanced/extensions/getting_started.html （manifest 必需字段、`blender_version_min` 至少 4.2.0、SemVer）
- Operator（Modal Execution 示例）：https://projects.blender.org/archive/blender-archive/raw/commit/bc15e0e2952bac0458ae61c97d4d8187e55cd1cc/doc/python_api/examples/bpy.types.Operator.5.py （`invoke` / `modal` / `modal_handler_add` / LEFTMOUSE 确认 / RIGHTMOUSE+ESC 取消）
- Gizmo API：https://docs.blender.org/api/current/bpy.types.Gizmo.html （`draw` / `draw_select` / `target_set_operator` / `draw_custom_shape`）
- KeyMaps（Add-on Keymap Registration）：https://www.blender.org/api/current/bpy.types.KeyMaps.html （只写 `keyconfigs.addon`、保存 `(km, kmi)`、modal keymap 不能新建）
- AddonPreferences：https://docs.blender.org/api/current/bpy.types.AddonPreferences.html （`bl_idname` 须为 `__package__`、偏好访问方式）
- Panel：https://docs.blender.org/api/current/bpy.types.Panel.html （`bl_space_type='VIEW_3D'` + `bl_region_type='UI'` + `bl_category` = N 面板）
- BMesh Module：https://docs.blender.org/api/2.79a/bmesh.html （`from_mesh` / `to_mesh` / `from_edit_mesh` / `update_edit_mesh`；API 长期稳定，2.79 文档与 current 一致）
- Command Line Arguments（5.1 Manual）：https://docs.blender.org/UATEST/manual/en/dev/advanced/command_line/arguments.html （`--background` / `--python` / `--python-exit-code` / `--factory-startup`）
- WorkSpaceTool 注册 API（commit f29b80f）：https://projects.blender.org/archive/blender-archive/commit/f29b80ff79ec7c6a2532d0b0eb5841d00cc7af1b （`bpy.utils.register_tool` / `unregister_tool` / `after` / `separator` / `group`）
- Collection 实例（Manual）：https://docs.blender.org/manual/ru/3.0/scene_layout/object/properties/instancing/collection.html （集合实例 / Empty + `instance_type='COLLECTION'`）

### 第三方（交叉核对用，非官方口径）

- Blender LTS vs 常规版（2026-11 核查）：https://aztech3d.com/en/guides/blender-lts-vs-regular-release/ （5.2.3 LTS、5.3 预期 2026-11-10）
- Blender 5.3 发布：https://www.3dart.it/en/blender-5-3-whats-new-tips-videos/ （5.3 于 2026-11-10 发布）
- Blender 5.x 版本时间线与 Python 3.13：https://app.cinevva.com/guides/blender-5-for-game-artists （5.0/5.1/5.2 时间线、Python 3.13、Action API 移除）
- Python 3.13 兼容指南：https://www.strayspark.studio/blog/blender-5-1-addon-compatibility-python-313-guide （纯 Python 插件不受 ABI 影响、编译 wheel 需 cp313）
- BGL→gpu 迁移 / 版本矩阵：https://github.com/Impertio-Studio/Blender-Bonsai-ifcOpenshell-Sverchok-Claude-Skill-Package/blob/HEAD/docs/research/vooronderzoek-blender.md （bgl 在 5.0 移除、shader 前缀、override 移除等）
- gpu 绘制规范：https://github.com/Impertio-Studio/Blender-Bonsai-ifcOpenshell-Sverchok-Claude-Skill-Package/blob/HEAD/skills/blender/core/blender-core-gpu/SKILL.md （`gpu.state` 恢复、draw handler 生命周期）
- Keymap 注册实践：https://blog.spencermagnusson.com/blender_keyboard_shortcuts/ （四层 keyconfig、headless 下 `keyconfigs.addon` 为 None）
- Headless 测试实践：https://github.com/TrevorHumble/blender-captions/blob/HEAD/skills/captions-test/SKILL.md （三层测试、`--factory-startup` 隔离）；https://deepwiki.com/oguna/Blender-XFileImporter/6-testing-and-quality-assurance （parser 与 importer 分层）
- SKP 格式说明：https://www.file-extension.info/format/skp ；https://file-extensions.com/docs/skp （专有二进制、未公开规范、经 SDK 读写）；OpenSKP：https://github.com/luzpaz/openskp/blob/HEAD/README.md （逆向实现，五语言读写）

---

## 备注

- 本调研未在本机安装/运行 Blender，所有 API 结论来自官方文档与公开资料的搜索核对；**第一阶段开工后，第一件事应是在 Linux 上装 Blender 5.2 LTS 便携版，实跑 `blender --background --python` 验证 §2/§7 的关键断言**（manifest 安装、keymap 判空、draw handler 守卫），再写工具代码。
- 与调研 A/B 的接口：调研 A 的工具清单+快捷键表 → 填入 §4.3 的快捷键数据表与 §5.2 的菜单数据表；调研 B 的推断/几何/组组件语义 → 落入 §3.1 的状态机与 §6.2 的存储映射。本文件不重复调研 A/B 的内容，只定架构与落点。
