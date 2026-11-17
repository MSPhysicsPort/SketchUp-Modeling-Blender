# 调研 04：原生优先映射（Native-first mapping）

日期：2026-11-17。Sen 在 0.4.0 真机测试后提出两点框架要求：(1) 插件要有激活开关，进出 SU 建模模式；(2) 同类工具优先用 Blender 原生工具，在原生工具之上叠加 SU 的吸附、复制等体验。本文记录调研结论与映射决策，依据为本地 Blender 实测（探针 + X 事件真机 harness），不是凭记忆。

## 1. 快捷键失效根因（已复现、已修复）

0.4.0 把单字母快捷键只注册在 addon keyconfig 的 "3D View" keymap 里。Xvfb + 真实 X 按键事件复现（Blender 5.1.2）：

- 注册本身没问题：addon keyconfig 里 "3D View" keymap 11 个条目齐全且 active；直接 `bpy.ops.sketchup.tool_line("INVOKE_DEFAULT")` 能进 modal、能切编辑模式。
- 事件分发时，Blender 先查模式 keymap（Mesh / Object Mode），再查 "3D View"。Mesh keymap 吃掉了 R/S/A/L/E/M/F/P，Object Mode 吃掉了 A/R/S/M；只有模式 keymap 里没绑定的键（E/Q 等）才能落到我们的条目上。这就是 Sen 看到的“快捷键没有反应”。
- 进一步探针证明：addon keyconfig 的 "Mesh" / "Object Mode" keymap **根本不被事件系统查阅**（只绑在 addon Mesh keymap 里的 Y 键永远不触发，即使插件随启动加载；反之，禁用默认 Mesh 的 L 条目后，我们的 L 立刻生效——走的是 addon "3D View" 条目）。devtalk 上的优先级说法（user > addon > builtin）只在**同一个 keymap 内**成立。

修复（0.5.0）：SU 模式开启时，(a) 三个 keymap（3D View / Mesh / Object Mode）都注册（Mesh/Object Mode 的注册无害，个别版本若查阅则生效）；(b) 临时禁用 active keyconfig 里 Mesh / Object Mode / Frames keymap 中与我们键位冲突的默认条目（`active=False`，只动冲突项），事件落到 addon "3D View" 条目；关闭模式时逐项恢复。被禁用的条目清单记在插件偏好里，重启后也能精确恢复，不碰用户自己禁用的条目。Frames keymap 的 SPACE（播放动画）是全局的，必须禁用否则 SPACE=选择到不了。

验证：X 事件 harness 逐键实测，11 个键全部触发对应工具；`G`（未绑定）仍走 Blender 抓取，证明未绑定键正常落空；关模式后默认条目、吸附、轴心、对象模式全部恢复。

## 2. 模式开关（SU Mode）

- 开关状态：`WindowManager.sketchup_mode`，N 面板勾选 + 3D 视图头栏按钮 + `sketchup.toggle_mode` operator，三者同一代码路径。
- 默认关闭：启用插件不改变 Blender 的任何行为；开模式才注册快捷键、禁用冲突默认项、配置吸附、进编辑模式。
- 开模式时保存：吸附开关/元素/目标/对齐旋转、变换轴心、当前模式；关模式时原样恢复。
- 开模式时确保 SketchUp Model 对象存在且进入编辑模式（原生变换工具在编辑模式下作用于网格元素；对象模式下只会移动整个对象）。

## 3. 原生工具映射表

| SU 工具 | Blender 原生基础 | 叠加的 SU 行为 | 状态 |
|---|---|---|---|
| Move (M) | `transform.translate`（INVOKE 交互 / EXEC 定值） | 吸附属性直传；Ctrl 调用时先 `mesh.duplicate` 再移动（复制）；快照供阵列后续算位移 | 0.5.0 完成 |
| Rotate (Q) | `transform.rotate` | 调用前把 3D 游标放到选择中心 + 轴心设 CURSOR（SU 模式）；Ctrl 复制；EXEC 时 `center_override` 定轴心 | 0.5.0 完成（折叠轴、交互拾取中心未做，见 §5） |
| Scale (S) | `transform.resize` | 同上，轴心在选择中心；EXEC 时 `center_override` | 0.5.0 完成（包围盒手柄、单轴手柄未做，见 §5） |
| 阵列 (3x / /3) | 无原生等价物 | `sketchup.array_repeat`：位移由快照与当前选择中心差推导；旋转阵列需在对话框里输角度（交互旋转不回报告角度） | 0.5.0 完成 |
| Line / 矩形 / 圆 / 多边形 / 圆弧 / 扇形 / 手绘线 | 无原生等价物（Blender 没有 SU 式推断绘图） | 保留自研 modal 工具 + 推断引擎 + VCB | 已有 |
| Push/Pull (P) | 无原生等价物（`extrude` 语义不同：SU 推拉是面法向棱柱 + 打洞/凹坑） | 保留自研 | 已有 |
| Offset (F) | 无原生等价物（`mesh.inset` 是内嵌面，不是 SU 偏移） | 保留自研 | 已有 |
| Follow Me | 无原生等价物 | 保留自研自动模式 | 已有 |
| Flip | `transform.mirror` 有交互镜像，但轴选择方式不同 | 保留自研（方向键选轴）；后续可评估原生委托 | 已有 |
| Select | Blender 框选语义不同（SU 右拖包含/左拖穿越 + 双击/三击规则） | 保留自研 | 已有 |
| Eraser | 无原生等价物（删边愈合/软化/隐藏三态） | 保留自研 | 已有 |

## 4. 吸附映射（SU 推断 → Blender snap）

实测探针（5.1.2 `tool_settings.bl_rna`）：`snap_elements` 合法值含 INCREMENT / GRID / VERTEX / EDGE / FACE / VOLUME / EDGE_MIDPOINT / EDGE_PERPENDICULAR / FACE_MIDPOINT / FACE_PROJECT / FACE_NEAREST；`snap_target` 含 CLOSEST / CENTER / MEDIAN / ACTIVE。

SU 模式配置：`use_snap=True`，元素 = VERTEX + EDGE + EDGE_MIDPOINT + FACE + FACE_MIDPOINT，目标 CLOSEST，不开旋转对齐。对应关系：端点→VERTEX、边上→EDGE、中点→EDGE_MIDPOINT、面上→FACE、面中心→FACE_MIDPOINT。原生变换调用时也直传同样的吸附属性（`snap=True, snap_elements={...}, snap_target='CLOSEST'`），覆盖非 SU 模式下的单独调用。

Blender snap 覆盖不了的 SU 推断（诚实缺口）：圆/弧中心点（Center）、切点、From Point、平行/垂直推断线、推断颜色与 ScreenTip。绘图类工具仍用自研推断引擎补这些。

## 5. 已知取舍与缺口（0.5.0）

- Rotate 不再有交互拾取中心/折叠轴：轴心固定为选择中心（3D 游标）。SU 式“点一下定中心”后续可加一个拾取前置步骤再委托原生旋转。
- Scale 不再有包围盒手柄：原生缩放用轴约束键（X/Y/Z）与数字输入；SU 式手柄（角/边/面）未复刻。
- 阵列的旋转角度无法从交互旋转中自动得知：旋转阵列对话框需手动输入角度（上一次 EXEC 旋转的角度会自动预填）。
- 移动/旋转/缩放的 VCB 重输（输完再改）随原生委托消失：原生工具有自己的数字输入，体验接近但不是 VCB 语义。
- Undo 粒度：原生变换自带一步 Undo；复制（duplicate+move）是两步（Blender 原生 Shift+D 同样如此）。

## 6. 证据来源

- 本地探针：`transform.translate/rotate/resize` 的 RNA 属性（含 `snap/snap_elements/snap_target/center_override`）、`mesh.duplicate`、EXEC 模式在编辑模式下的行为（需退出编辑模式或读 edit bmesh 才能看到结果）、`center_override` 的世界坐标语义。
- X 事件 harness：Xvfb + ctypes/XSendEvent 真实按键，`--debug-events` 确认事件到达与分发；重启对照实验排除“注册时机”假说；Y 键隔离实验锁定“addon Mesh keymap 不被查阅”。
- devtalk 帖子（keymap 优先级在同一 keymap 内成立、须把快捷键加到对应 keymap）：https://devtalk.blender.org/t/addon-shortcuts/2410
- HEAVYPOLY（Blender 5.2 扩展）的实战经验：禁用默认 keyconfig 冲突条目 + addon keyconfig 加自己的条目；Object Non-modal 在 Mesh 之后、3D View 之前。
