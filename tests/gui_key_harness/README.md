# GUI 按键 harness（Xvfb + 真实 X 按键事件）

唯一能验证“真实按键 → 工具激活”链路的办法：headless 测不到事件分发。
2026-11-17 靠它定位了 0.4.0 快捷键失效的根因（模式 keymap 优先于 3D View keymap，
addon 的 Mesh/Object Mode keymap 不被查阅），并验证了 0.5.0 的修复。

## 文件

- `xsend_keys.py`：ctypes + libX11（无 XTest 依赖），用 XSendEvent 向 Blender 窗口发真实按键。
  用法：`python3 xsend_keys.py :99 <ready文件> "l,esc,m,esc" [每键等待秒数]`。
  注意：序列第一个键常因焦点未稳而丢失，正式序列前加一个热身键。
- `gui_mode_verify.py`：Blender 内脚本。装包 → 打印模式关状态 → 开 SU 模式并打印状态 →
  写 READY → 每 0.5s 记状态 → 50s 后关模式、打印恢复状态、退出。
  使用前把 `ZIP_PATH_PLACEHOLDER` 换成要测的 zip 绝对路径。
- `gui_key_test_noreinstall.py`：不重装、只记状态（用于“重启后插件自启动”的对照实验）。

## 运行

```sh
Xvfb :99 -screen 0 1280x1024x24 &
DISPLAY=:99 HOME=/tmp/fakehome_gui timeout 80 <blender> --factory-startup \
  --python tests/gui_key_harness/gui_mode_verify.py > /tmp/gui.log 2>&1 &
python3 tests/gui_key_harness/xsend_keys.py :99 /tmp/gui_key_state.txt "l,esc,..." 1.1
grep -E "^\[" /tmp/gui_key_state.txt   # 模式开关各阶段的状态
grep -oE "tool='SKETCHUP_OT_[a-z_0-9]+'" /tmp/gui_key_state.txt | sort -u
```

M/Q/S（原生委托）不写 session 状态，harness 里看不到是正常的，以“无 Python 报错”为准；
其功能由 `transform_flows.py` 的 EXEC 场景覆盖。
