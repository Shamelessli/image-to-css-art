# GUI 壳设计：image-to-css-art 桌面界面

日期：2026-09-07
状态：已批准

## 目标

为 `skills/image-to-css-art/scripts/image_to_css.py` 提供一个简洁精简的桌面 GUI 壳：

- 单文件 GUI，纯 Python 标准库（tkinter + subprocess），零新增依赖
- GUI 本体体积 <10 KB
- 使用项目目录 `.venv\Scripts\python.exe` 作为运行环境
- 支持批量转换多张图片
- 依赖缺失时提示并支持一键安装

## 架构

**方案 A：单文件 tkinter + subprocess 进程隔离**

- `gui.py`：纯标准库，不 import numpy/opencv/PIL
- 每次转换通过 subprocess 调用 venv python 执行 CLI，转换错误不崩溃 GUI
- 依赖检测通过子进程探测实现

## 组件

| 组件 | 职责 |
| --- | --- |
| `gui.py` | 窗口、控件、批量队列、子进程管理、日志转发 |
| `启动GUI.bat` | 用 venv python 启动 gui.py，双击即用 |
| 子进程 CLI | 逐张执行 `image_to_css.py convert`，实时转发 stdout/stderr |

## 界面布局

- 输入区：图片多选列表（Treeview）+「添加图片 / 移除选中 / 清空」
- 参数区：预设下拉框（preview/balanced/faithful，默认 faithful）、背景色输入（默认 #ffffff）、`--fit` 目标体积输入（可选，MiB）
- 输出区：输出目录选择（未选择时默认与每张输入图片同目录）+「开始转换」按钮
- 日志区：只读文本框，实时滚动显示每张进度与结果（✓/✗ + 输出路径）
- 「打开输出文件夹」按钮

## 数据流

1. 用户多选图片 → 加入队列列表
2. 点「开始转换」→ 逐张启动子进程
3. 子进程参数：`<venv> scripts/image_to_css.py convert <输入> -o <输出目录>/<同名>.html --preset <预设> --background <色> [--fit <MiB>]`
4. 输出名规则：与输入同目录时同名冲突处理 —— 输出统一到所选输出目录，文件名 = 输入文件名去扩展名 + `.html`；同名输入（如 `a.jpg` 与 `a.png`）自动追加扩展名区分（`a.jpg.html` / `a.png.html`）
5. 每张完成更新日志与状态

## 错误处理

- 依赖缺失：启动时探测（子进程 `import numpy, cv2, PIL`），缺失弹窗提示 +「一键安装」按钮（`pip install -r requirements.txt`，需联网，进度输出到日志）
- 子进程非零退出：日志标 ✗ 并显示 stderr 尾部，继续处理下一张
- 无 venv 或无 CLI 文件：启动即弹错退出
- 转换中禁用「开始转换」防止并发

## 测试

- 手工测试场景：
  1. 依赖缺失时一键安装流程
  2. 单张转换成功、批量 5 张转换、含中文路径
  3. 同名不同扩展输入的输出命名
  4. 人为制造转换失败（损坏图片）验证日志报错不崩溃
  5. 日志实时滚动
- 验证命令：`.\.venv\Scripts\python.exe scripts/check.py` 应不受影响

## 非目标

- 不暴露全部 CLI 参数（仅预设/背景色/fit）
- 不做转换后自动打开浏览器
- 不打包为 exe（体积优先，bat 启动足够）