# 文本转向量（便携版）

> 本页面内容由 AI 汇总生成，仅供参考。
> 如内容涉及侵权，请联系邮箱 **lin_yb@88.com**，核实后删除。

一条文本进，一串 base64 出。内置 Python 3.12、numpy、tokenizers、onnxruntime 和 224MB 的
ONNX 模型，**解压即可运行，不装 Python、不联外网、不需要 pip**。

模型：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`（384 维，CPU，量化版）
输出是 384 个归一化 float32 + base64。

---

## 下载

| 文件 | 大小 | 说明 |
|:--|--:|:--|
| [text2vec-portable.zip](https://github.com/lyblyblyblin/text2vec-portable/releases/download/v1.0.0/text2vec-portable.zip) | 250 MB | 完整便携包（1318 个文件），解压即用 |

SHA-256 校验值：

```
69802b21a0f2c9ced997fc3c9858be672ac2fe50594f9e9dddbd1bdac8b26163
```

Windows 上校验：`certutil -hashfile text2vec-portable.zip SHA256`

## 一、三步开始

1. **解压**。二选一：
   - 右键 zip → 「全部解压缩」；（Win10/11 自带，不需要 7-Zip、不需要任何解压软件）
2. 双击 `向量.cmd`，输入文本，回车。屏幕打印 base64，并自动复制到剪贴板。
3. 完事。

解压后目录可以放在任意位置（`D:\text2vec\`、U 盘、网盘同步目录都行），**移动或改名都不影响**，
因为程序总是读自己旁边的 `model\`。

> 如果解压后杀毒软件拦了 `python.exe`，把该目录加白名单即可；这是官方 Python 3.12.8
> 嵌入式运行时，不是自编译的。

## 二、命令行用法

```bat
:: cmd
向量.cmd "你好世界"
```

```powershell
# PowerShell：拿变量
$b64 = .\向量.cmd "你好世界"
$b64.Length      # 2048
```

也可以绕过 cmd 直接调内置解释器，速度略快、编码更可控：

```powershell
.\python\python.exe .\embed.py "你好世界"
```

**一次只能传一条文本**（这是刻意的：批量化会引入 padding 和归一化差异，反而容易和已有结果对不上）。
输出是 2048 个字符的 base64，**末尾不带换行**，赋值时不会混进空行。

## 三、输出怎么用

base64 是 384 个 **float32 小端** 连续排列再 base64，共 1536 字节 / 2048 字符。
解回数字：

```bat
python\python.exe embed.py "你好世界" --decode
```

会打印维度、模长（归一化后应为 `1.000000`）和 384 个数值。
两段文本的相似度就是两个归一化向量的点积：

```python
import base64, struct
a = struct.unpack("<384f", base64.b64decode(b64_1))
b = struct.unpack("<384f", base64.b64decode(b64_2))
print(sum(x * y for x, y in zip(a, b)))   # 1.0 表示完全相同
```

## 四、自检与排错

```bat
python\python.exe embed.py --check
```

正常应输出：

```
Python      : 3.12.8
numpy       : 2.3.5
tokenizers  : 0.22.2
onnxruntime : 1.31.1
模型目录    : D:\text2vec\model
模型大小    : 224.2 MB
截断长度    : 128 token
输出维度    : 384
base64 长度 : 2048
状态        : OK
```

| 现象 | 原因 | 处理 |
|:--|:--|:--|
| 双击闪退 | 目录不完整 | 确认 `python\python.exe`、`model\model_optimized.onnx` 都在 |
| `找不到可用的模型目录` | 只解压了部分文件 | 重新完整解压；或用 `--model-dir` 指定 |
| 报 `msvcp140.dll` 缺失 | 系统缺 VC++ 运行库 | 包里已内置一份，若仍报错，装 [VC++ 2015-2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| 中文显示成方块 | 控制台代码页 | 先 `chcp 65001`，或直接用 PowerShell |
| 结果比已有的短 | 文本被截断 | 本模型上限 **128 token**（约 128 个汉字），超长部分不参与计算 |

## 五、目录说明

```
text2vec-portable\
├─ 向量.cmd          主入口（交互 / 带参数两种模式）
├─ embed.py          转向量脚本（纯 onnxruntime 实现）
├─ python\           嵌入式 Python 3.12.8 + 依赖 + VC 运行库
│  ├─ python.exe
│  ├─ python312._pth 已加 Lib\site-packages
│  ├─ msvcp140.dll   VC++ 运行库（随包分发，官方原版 14.44）
│  ├─ vcruntime140*.dll  同上
│  └─ Lib\site-packages\  numpy 2.3.5 / tokenizers 0.22.2 / onnxruntime 1.31.1
├─ THIRD-PARTY-NOTICES.txt   第三方组件许可汇总（分发时请保留）
└─ model\            5 个模型文件，共 240MB
```

## 六、版权与再分发

包里所有组件都是宽松许可，可以自由复制、传播、商用：

| 组件 | 许可 |
|:--|:--|
| Python 3.12.8 | PSF License |
| NumPy 2.3.5 | BSD 3-Clause |
| Tokenizers 0.22.2 | Apache 2.0 |
| ONNX Runtime 1.31.1 | MIT |
| 嵌入模型 | Apache 2.0 |
| VC++ 运行库 | 微软允许 app-local 随应用分发 |

唯一要求是**保留版权声明和许可文本**——已在 `THIRD-PARTY-NOTICES.txt` 里汇总，
各组件原始许可文件也都在包里（`python\LICENSE.txt`、各 `*.dist-info\` 内）。
分发时别删这个文件。

两条红线：微软的运行库 DLL **不能单独拆出来给人下载**（必须作为本包的一部分）；
模型若被你修改过（重新量化等），分发时要标注"已修改"。

## 七、和 fastembed 版的关系

旧版 `embed.py` 依赖 fastembed，需要先装 Python 再联网装包，在 Python 3.15 上还装不上
（onnxruntime 没有 3.15 的轮子）。这一版把推理逻辑直接写成 onnxruntime 调用：

| | 旧版（fastembed） | 本版（纯 onnxruntime） |
|:--|:--|:--|
| 依赖 | fastembed + 8 个间接包 | numpy / tokenizers / onnxruntime |
| 首次启动 | 联网查模型元信息，可能卡住 | 纯本地，约 1 秒 |
| 安装 | 需 Python 3.10~3.13 | 无需安装 |
| 结果 | 基准 | 同版本同平台**逐字节一致**（已对拍 8 组文本）；跨 onnxruntime 版本约 1e-4 级差异，余弦相似度不受影响 |

内部实现对应 fastembed 的 `PooledEmbedding`：token 级输出 → 按 attention_mask 做
**mean pooling**（float64 累加）→ 落回 float32 → L2 归一化 → base64。
截断长度取 `tokenizer_config.json` 里 `model_max_length`(512) 与 `max_length`(128) 的**较小值 128**，
这点和 fastembed 一致，请不要自行改大，否则结果会和已有输出对不上。

---

## 相关文档

| 文档 | 内容 |
|:--|:--|
| [向量工具说明-与许可边界.md](docs/向量工具说明-与许可边界.md) | 许可表、两条分发红线、包内目录结构 |
| [file-tree.txt](logs/file-tree.txt) | 完整文件清单（1319 个文件） |
| [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt) | 六个第三方组件的来源 / 许可 / 版权人 |

## 免责声明

本工具按「现状」提供，不附带任何明示或暗示的担保。使用前请自行评估；
因使用本工具产生的任何后果由使用者自行承担。第三方组件的许可与再分发条件见
[THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt)，分发时请务必保留该文件。

> 本页面内容由 AI 汇总生成，仅供参考。
> 如内容涉及侵权，请联系邮箱 **lin_yb@88.com**，核实后删除。
