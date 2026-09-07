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

- 不暴露全部 CLI 参数（仅预设/背景色/fit/并行数）
- 不做转换后自动打开浏览器

## exe 打包（2026-09-07 追加）

- 支持 PyInstaller 全量单文件打包：`打包EXE.bat`（GBK 编码），产出 `dist\ImageToCssArt.exe`（约 67MB，含 numpy/OpenCV/Pillow/tkinterdnd2/css_art，双击即用、可分发）
- frozen 模式：`ROOT` 基于 exe 所在目录；转换通过 `--convert-worker` 自执行模式调用内置转换器（子进程隔离保留）；依赖检查改为进程内 import（避免 subprocess 探测引发自繁殖）
- 窗口关闭（WM_DELETE_WINDOW）终止所有在跑的转换子进程；日志上限 1000 行

---

## 增量设计（2026-09-07 追加）：拖拽 + 并行 + 日志分块

用户批准的新增功能，叠加在原设计之上。原约束不变，仅以下条目被覆盖。

### 变更的约束

- gui.py 体积预算：<10 KB → **<16 KB**
- GUI 新增唯一第三方依赖 **tkinterdnd2**（仅装进项目 venv，约 1.5MB；不影响成品 HTML；不影响转换依赖 requirements.txt）
- 依赖探测范围：numpy/cv2/PIL + tkinterdnd2；一键安装命令 = `pip install -r requirements.txt tkinterdnd2`

### 功能 1：拖拽添加

- 根窗口改为 `TkinterDnD.Tk()`；图片列表 Listbox 注册 `drop_target_register(DND_FILES)` + `<<Drop>>` 事件
- 拖入文件：追加到列表，按解析后路径去重（与「添加图片」按钮行为一致）
- 拖入文件夹：仅收集**顶层**图片文件（扩展名 .png/.jpg/.jpeg/.bmp/.webp/.gif），不递归
- 纯函数 `scan_images(paths) -> list[Path]`：接受文件或目录路径混合列表，返回去重后的图片文件列表（目录只扫顶层）。此函数可单测
- tkinterdnd2 缺失时：GUI 其余功能不受影响，拖拽不可用并弹提示

### 功能 2：并行处理

- 「并行数」Spinbox 1–16，默认 2；转换期间 disabled，结束后恢复
- worker 架构：任务队列 `queue.Queue` + N 个 daemon worker 线程；每个 worker 循环 `get_nowait` 取任务，起 subprocess 转换（进程隔离不变）
- 队列预放 N 个 sentinel（每 worker 一个），worker 取到即退出；全部 worker 退出后日志输出 `全部完成 (成功 S/总数 T)`（S=退出码 0 的文件数，T=任务总数）
- 并行放大内存峰值：faithful 大图单进程可占数百 MB+，界面在并行数旁提示风险

### 功能 3：日志分块

- 维持单滚动面板（用户选定），每行日志前缀 `[W{n}]`（n=worker 序号 1..N），含 `=== 转换: name`、`OK → path`、`失败（退出码 N）` 各行的前缀
- 转换开始前并行数锁定，保证运行期间前缀稳定

### 增量测试场景

- 单测：`scan_images`（文件/目录混合、顶层不递归、去重、扩展名过滤）
- 手工：拖入文件、拖入文件夹、并行 2/4 张同时转、日志前缀对应、转换中改并行数被锁定