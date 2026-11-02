# 量化研报复现 · 工作区环境自检与补齐报告

- 检查完成：2026-11-02 17:1x（Asia/Shanghai）
- 工作区：`E:\量化研报复现`
- 现有素材：`研报\20161031-华泰证券-多因子系列之三：华泰单因子测试之成长类因子.pdf`（50 页，3.0 MB）
- 结论：PDF 识别、Word 编辑排版、Python 运行测试、图片视觉识别 **四项能力全部可用**；
  分析/测试库与 OCR 已按授权补齐到工作区 `.pylibs`。

---

## 1. 依赖来源

| 能力 | 组件 | 来源路径 |
|---|---|---|
| Python 解释器 | CPython 3.12.14 | `C:\Users\Asus\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe` |
| 基础数据栈 | pandas 3.1.0、numpy 2.5.4 | `E:\量化研报复现\.pylibs`（新增，优先于解释器自带） |
| Office 文档 | python-docx 1.2.0、python-pptx 1.0.2、openpyxl 3.1.5、XlsxWriter 3.2.9、lxml | 解释器自带 site-packages |
| 图像底层 | Pillow 13.0.0 | `.pylibs`（自带亦有一份） |
| PDF 文本 | pypdf 6.21.4 | `.pylibs` |
| PDF 布局/渲染 | PyMuPDF 2.0（pdfium）、pdfplumber 0.11.10、pypdfium2 5.14.0 | `.pylibs` |
| OCR | RapidOCR 1.4.4（onnxruntime 1.31.1、自带中英模型） | `.pylibs` |
| 统计/ML | scipy 1.18.1、statsmodels 0.15.0、scikit-learn 1.9.1、seaborn 0.13.2、matplotlib 3.11.2 | `.pylibs` |
| 测试 | pytest 9.2.0、pytest-cov 7.1.0 | `.pylibs` |
| 文档转换/渲染 | LibreOffice Kit（native 后端 + pdfium 光栅化，单文件 178 MB） | `D:\dsh\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit` |
| 转换 CLI | `libreoffice-kit\lib\cli.js`，由 `D:\dsh\resources\runtime\primary-runtime\dependencies\node\bin\node.exe` 执行 | 同上 |
| 视觉识别 | DSH `read_image` + 当前多模态模型 | 无需本地安装 |
| 中文字体 | SimHei / SimSun / Microsoft YaHei | `C:\Windows\Fonts` |

其他解释器（均非本项目主环境）：
- `C:\Python315\python.exe`（PATH 默认）：空环境，只有 pip。
- `C:\Program Files\Python310\python.exe`：torch 1.12.1+cu113、opencv、scipy 1.15.3、matplotlib 3.6.1，**无 pandas**。

---

## 2. 补齐内容

安装位置：`E:\量化研报复现\.pylibs`（66 个包，781.8 MB，工作区本地、免管理员、整体删除即回滚）。

```powershell
python -m pip install --target 'E:\量化研报复现\.pylibs' --upgrade `
  matplotlib scipy statsmodels scikit-learn seaborn tabulate pyyaml tqdm `
  pytest pytest-cov pymupdf pdfplumber rapidocr-onnxruntime pypdf
```

实测版本：numpy 2.5.4 / pandas 3.1.0 / scipy 1.18.1 / statsmodels 0.15.0 /
scikit-learn 1.9.1 / matplotlib 3.11.2 / seaborn 0.13.2 / pytest 9.2.0 /
PyMuPDF 2.0 / pdfplumber 0.11.10 / RapidOCR 1.4.4 / pypdf 6.21.4。

---

## 3. 验证记录（全部实际执行）

| 项目 | 结果 |
|---|---|
| PDF 文本抽取 | 50 页，每页 1062–4976 字符，0 空页；无扫描页，无需 OCR |
| PDF 转图 | PyMuPDF 120 dpi 单页 330 KB；LibreOffice Kit/pdfium 144 dpi 全 50 页 |
| Word 生成→PDF | python-docx（标题/加粗/3×3 表格/2.5 cm 边距）→ PDF 50 KB，`%PDF-` 校验通过 |
| 排版渲染 | PDF→PNG 1224×1584，中文、标题线、表格线正确（仅提示缺 Courier 字体） |
| 统计 | OLS 系数 `[0.015, 2.008, -0.708]`、R² 0.98，statsmodels 与 sklearn 一致 |
| 绘图 | matplotlib + SimHei，中文标题/坐标轴无方块 |
| OCR | 单页 50 个文本框、7 秒，中文识别准确（"金融工程/量化选股"、"华泰证券"、正文段落） |
| 测试 | `pytest` 1 passed；缓存正常写入 |
| 视觉 | 图片与 PDF 页面内容可直接辨认（含表格、公式） |
| 残留清理 | 自检产物已全部删除，工作区只剩 `.pylibs`、`.cache`、`研报`、报告与 `env.cmd` |

---

## 4. 用法

**推荐入口**（自动设好 PYTHONPATH / UTF-8 / matplotlib 缓存目录）：

```powershell
& 'E:\量化研报复现\env.cmd' -c "import pandas; print(pandas.__version__)"
& 'E:\量化研报复现\env.cmd' .\script.py
& 'E:\量化研报复现\env.cmd' -m pytest tests -q
```

**直接调用** 3.12 时必须带环境变量：

```powershell
$py='C:\Users\Asus\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH='E:\量化研报复现\.pylibs'
$env:PYTHONIOENCODING='utf-8'
$env:MPLCONFIGDIR='E:\量化研报复现\.cache\mpl'
& $py .\script.py
```

**PDF → 图（给视觉模型看）**：

```powershell
$node='D:\dsh\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
$cli='D:\dsh\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js'
& $node $cli render --input 'x.pdf' --output-dir '.\pages'
```

---

## 5. 关键兼容补丁

`.pylibs\sitecustomize.py`（随 `PYTHONPATH` 自动加载）解决两个沙箱限制：

1. **`tempfile.mkdtemp()` 不可写**：Python 3.12 在 Windows 用 `0o700` 建目录，沙箱令牌拿不到该目录权限，
   导致 pip / pytest / matplotlib 等一切临时目录写入失败。补丁让 `os.mkdir` 忽略 mode，恢复继承权限。
2. **matplotlib 字体缓存**：默认写 `C:\Users\Asus\.matplotlib`（只读），改指工作区 `.cache\mpl`。

删除该文件即恢复 Python 原生行为。

---

## 6. 已知限制

| 限制 | 说明 / 规避 |
|---|---|
| Word COM 未启用 | 沙箱内 `New-Object -ComObject Word.Application` 挂起；排版链路改用 python-docx + LibreOffice，无需 Word |
| Word 原生域/目录 | python-docx 不会自动更新 TOC/交叉引用域；LibreOffice 转换时可刷新，或改用静态目录 |
| 公式 | python-docx 无公式 API，OMML 需手写 XML；复杂公式建议以图片插入或最后在 Word 里补 |
| pdfplumber 表格 | 该研报第 10 页表格（纯线条/文字排版）`extract_tables()` 返回 0；表格优先用页面渲染图 + 视觉识别 |
| OCR 速度 | 约 7 秒/页（144 dpi），50 页整本约 6 分钟；文本型 PDF 不必 OCR |
| 字体 | LibreOffice 提示缺 `Courier`，仅影响等宽英文外观 |
| 沙箱 TLS | PowerShell 的 `Invoke-WebRequest`/`curl.exe` 在沙箱内报 `SEC_E_NO_CREDENTIALS`；网络本身正常，下载用 pip / Node / `web_fetch` |
| 默认 python | PATH 上的 `python` 是 3.15 空环境，务必用 `env.cmd` 或 3.12 绝对路径 |

---

## 7. 回滚

| 改动 | 操作 |
|---|---|
| 新增库 | 删除 `E:\量化研报复现\.pylibs` |
| 兼容补丁 | 删除 `.pylibs\sitecustomize.py` |
| 缓存 | 删除 `.cache` |
| 工作区 ACL 修复 | 运行 `pwsh -NoProfile -File 'E:\dsh-acl-recovery-20261102\acl-backup-a7d7281c060949e394ebdc995f9da5d6.json.ps1' -Path 'E:\量化研报复现' -AllowRoot 'E:\量化研报复现' -Restore 'E:\dsh-acl-recovery-20261102\acl-backup-a7d7281c060949e394ebdc995f9da5d6.json'` |
| 入口脚本 | 删除 `env.cmd` |
