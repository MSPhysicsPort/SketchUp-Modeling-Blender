# Blender SketchUp 插件 - 状态文档（living）

GitHub：https://github.com/MSPhysicsPort/SketchUp-Modeling-Blender（公开独立仓库，与 MSPhysics 仓库分开）

更新：2026-11-17 11:20 UTC
阶段：1.0.0 全量版已交付 Sen（P4+P5+P6，沙盒除外）；Sen 不再逐版验收，只交付可用版本

## 目标
在 Blender 里用 SketchUp 的建模逻辑完成建模；完整复刻 SketchUp 建模工具+逻辑+工具菜单；最终能在 Blender 里实际安装使用。参照 SketchUp 2026（classic 基线，2027 Procedural 功能不在基线内）。

## Sen 定下的约束
- 适配 Blender 4.x–5.x；界面语言跟随 Blender 的语言设置（2026-11-17 主聊天补充）。
- Sen 电脑 Blender 5.1.2（Windows 11）为主测版本（2026-11-17 本聊天告知）。
- Sen 真机 SketchUp 26.0.429、Windows 11。
- 工具栏末行 4 项（3D Warehouse、Extension Warehouse、发送到 LayOut、扩展程序管理器）不用考虑，范围外（Sen 2026-11-17 决定，身份经悬停提示截图确认）。
- 方案已批准，完全授权，D1–D15 按推荐默认值推进；分工两次被拒后，Sen 已定由 Ember 单人直接推进，不再派分工。
- 语言必须严格统一（Sen 2026-11-17 真机反馈后定）：中文界面全部中文、英文界面全部英文，不许混杂。
- 框架要求（Sen 2026-11-17 真机测试后定，0.5.0 起）：插件有个激活开关，开了进 SU 建模模式（快捷键都是 SU 功能），退出恢复 Blender 操作模式；同类工具优先用 Blender 原生（移动优先调原生移动，在其上加 SU 吸附/复制），体验尽量接近 SU。
- Sen 2026-11-17 反馈（0.5.0 真机）：① SU 模式下新建几何全在一个 Mesh 里，要求加群组/组件概念；② 工具切换必须能直接按快捷键、不许中间加 Esc；③ 下个版本完善所有工具再发（P4+P5+P6 全量，沙盒按已批 D10 不进首期）。

## 环境
- 本机：Linux，无 SketchUp，无 Windows 真机。
- Blender 四线均已验 headless（--background + bpy/bmesh + 翻译机制注册往返）：5.3.0、5.2.4 LTS、5.1.2、4.5.16 LTS。
- 翻译机制：locale 键 zh_HANS（+zh_CN 别名），条目键 ("*", msgid)；绘制文字一律显式查表 translate()（operator 文字 Blender 原样显示、不翻译，真机纠正）。
- 路径：tools/blender-<版本>-linux-x64/

## 进度
- [x] 工作区建立：docs/、addon/、research/
- [x] 调研A/B/C（三份调研稿）
- [x] Blender 四线 headless 验证
- [x] 统稿方案 docs/方案.md（Sen 已批准）
- [x] D1 截图证据基本齐全（工具栏+菜单+子菜单，见方案 §2.2/§2.3）
- [x] P0 骨架实现（单人直接实施）+ 这边验收全绿
- [x] P0 语言统一修复 0.1.1：显式查表 + T2 假布局双语绘制捕获（62 项，四版本全绿），已交付
- [x] P1 地基（0.2.0）：推断几何层 + 成面/愈合引擎 + VCB modal 缓冲 + Select/Line/Eraser + 参考线数据与绘制 + 快捷键表（Space/L/E）+ 工具栏真实工具，已交付待 Sen 真机验收
- [x] Modal 自测架：假事件驱动真实 operator（tests/modal_harness.py + modal_flows.py），55 项检查；自测发现并修了 3 个真 bug（框选孤立顶点、修饰键双击计数、shift 变量未定义）
- [x] P2 形状工具（0.3.0）：矩形/旋转长方形/圆/多边形/圆弧/两点圆弧/三点圆弧/扇形/手绘线 + 曲线元数据（su_curves）+ Center 推断 + Divide/Weld/Explode/Convert + Entity Info 曲线面板；T0/T1（94 项）/T2（83 项）+ 形状流程 40+ 项，四版本全绿
- [x] P3 变换工具（0.4.0）：Move/Rotate/Scale 自研 modal 版 + PushPull/Offset/Follow Me/Flip；T0/T1（94 项）/T2（92 项）+ 21 个变换流程四版本全绿；**0.4.0 两次发送均失败，从未到 Sen 手上，已被 0.5.0 取代（切勿再记“已交付”）**
- [x] 快捷键失效根因诊断（GUI 真实按键 harness）：模式 keymap 优先于 3D View keymap，addon 的 Mesh/Object Mode keymap 不被查阅；修复 = 开模式时临时禁用冲突默认条目 + 关模式精确恢复。见 research/04-native-first-mapping.md 与 tests/gui_key_harness/
- [x] 0.5.0 框架重做：SU 模式开关（mode.py，头栏按钮 + N 面板 + F3 切换，默认关）+ Move/Rotate/Scale 改原生委托（transform.translate/rotate/resize + 吸附属性 + Ctrl 复制 + Repeat Array 对话框）+ 顺带修 Offset 预选边崩溃与形状工具 Esc 崩溃；T0/T1（94 项）/T2（108 项）+ 全部交互流程四版本全绿 + GUI 真实按键 11 键验证通过；已交付 Sen
- [x] 全量版 1.0.0：工具直切（无 Esc 切换，VCB 守卫，原生变换工具拖拽中除外）+ 群组/组件（嵌套/共享定义/双击进出/Outliner/Entity Info）+ 推穿打洞（布尔差集）+ Follow Me 手动（逐边/周长）+ Intersect Faces（三档，含共面）+ 柔化/隐藏/Surface + Tags + 材质/Paint Bucket（四模式/取样/真实尺寸 UV）+ 剖面（布尔切口/切片成组）+ 参考线与绘图轴持久化 + 卷尺/量角器/坐标轴 + 标注/文字/3D 文字 + 相机（7 工具/标准视图/历史/两点透视近似）+ 场景 + 样式 + Solid Tools（6 项）+ 套索/Search/Back Edges + 右键菜单 + Edit 菜单 + 工具栏补全（无 stub）+ 持久视口叠加层；沙盒除外（D10 已批）；T0/T1（94 项）/T2（119 项）四版本全绿 + GUI 真实按键验证直切与 F2；已交付 Sen
- [ ] 沙盒工具（D10 已批不进首期，后续再议）

## 方案要点
- 基线 2026 classic；49 个交互工具；菜单四处同源落点；根架构 1 上下文 = 1 Mesh Object。
- 4.x–5.x：manifest min 4.2.0 + core/compat.py 适配层 + 三版本测试矩阵；4.0/4.1 不支持（D6 默认值）。
- 语言跟随 + 显式查表：bpy.app.translations 注册字典（类级标签）+ translate() 显式查表（全部绘制文字）；中/英双语首期。
- 扩展 id：sketchup_modeling；许可证 GPL-3.0-or-later（D6 默认值）。
- 交付物：build/sketchup_modeling-1.0.0.zip + docs/1.0.0-测试说明.md（已发送；0.4.0 从未送达）。

## 已完成 / 未完成
- 已完成：调研、验证、方案统稿与核验、全部截图转录、方案批准、P0 实现与 headless 验证、语言统一修复、P1 实现与 headless 验证、P2/P3 实现、0.5.0 框架重做与全部自测、1.0.0 全量版（P4+P5+P6）与全部自测。
- 未完成：沙盒工具（D10 已批不进首期）。Sen 不再逐版真机验收（2026-11-17 定），这边自测通过后只交付可用版本。

## 已知问题
- 22 条中文词条与 Blender 内置译文冲突，仅影响个别类级标签措辞（绘制文字已不受影响）。
- 工具栏图标为 Blender 内置占位图标；右键菜单不在 P1 范围。
- 面内闭合环重叠问题待 P4 逻辑面模型；平行/垂直/复合推断待后阶段；首次启用快捷键提示弹窗已由模式开关 + 头栏按钮取代。
- 原生委托取舍（0.5.0 起）：Rotate 无交互拾取中心/折叠轴（轴心=选择中心）、Scale 无包围盒手柄、旋转阵列需手输角度、VCB 重输取消（改原生数字输入）、复制=两步 Undo。

## 待 Sen 定
- 无。0.5.0 交付后等 Sen 随手测试反馈，不再逐版验收。
