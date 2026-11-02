#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文本 -> 384 维向量 -> base64。

只用 onnxruntime + tokenizers + numpy 三个轮子，不依赖 fastembed、
不联网、不需要 pip。模型目录里放 5 个文件即可：

    config.json
    model_optimized.onnx
    special_tokens_map.json
    tokenizer.json
    tokenizer_config.json

用法（一次一条文本，标准输出就是 base64，没有换行、没有 JSON）：

    python.exe embed.py "你好世界"

想直接看数字：

    python.exe embed.py "你好世界" --decode

自检环境：

    python.exe embed.py --check
"""

import argparse
import base64
import json
import math
import os
import struct
import sys
from pathlib import Path

DIM = 384
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# 默认模型目录（安装脚本会把模型放到这里）
DEFAULT_MODEL_DIR = r"C:\paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
REQUIRED_FILES = (
    "config.json",
    "model_optimized.onnx",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)

_model = None        # (Embedder) 单例，进程内复用
_model_dir = None    # 实际使用的模型目录


def log(msg):
    sys.stderr.write(str(msg) + "\n")
    sys.stderr.flush()


def _setup_stdout():
    """Windows 控制台默认 GBK，中文诊断可能炸；统一按 UTF-8 输出并容忍失败。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _model_candidates(explicit):
    """按优先级列出候选模型目录：显式参数 > 脚本同级 model/ > 环境变量 > 默认安装路径。"""
    if explicit:
        return [Path(explicit)]
    here = Path(__file__).resolve().parent
    cands = [here / "model"]
    env = (os.environ.get("EMBED_MODEL_DIR") or "").strip()
    if env:
        cands.append(Path(env))
    cands.append(Path(DEFAULT_MODEL_DIR))
    return cands


def resolve_model_dir(explicit=None):
    """找出可用的模型目录；找不到就抛出带明细的异常。"""
    cands = _model_candidates(explicit)
    partial = None
    for d in cands:
        try:
            if not d or not d.is_dir():
                continue
        except OSError:
            continue
        missing = [f for f in REQUIRED_FILES if not (d / f).is_file()]
        if not missing:
            return d
        if partial is None:
            partial = (d, missing)

    lines = ["找不到可用的模型目录。已尝试："]
    for d in cands:
        lines.append("  - %s" % d)
    if partial:
        d, missing = partial
        lines.append("")
        lines.append("%s 里缺少这些文件：" % d)
        for f in missing:
            lines.append("  ! %s" % f)
    lines.append("")
    lines.append("请把模型的 5 个文件放进 embed.py 同级的 model\\ 目录，")
    lines.append("或用 --model-dir 指定目录，或设环境变量 EMBED_MODEL_DIR。")
    raise SystemExit("\n".join(lines))


class Embedder(object):
    """直接跑 ONNX 会话的最小实现，算法与 fastembed 的 TextEmbedding 等价。"""

    def __init__(self, model_dir, threads=None):
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import AddedToken, Tokenizer
        except ImportError as exc:
            raise SystemExit(
                "缺少运行库：%s\n"
                "本工具自带 python\\ 目录，请用包内 python\\python.exe 运行；\n"
                "若在系统 Python 里跑，需要 pip install numpy tokenizers onnxruntime" % exc
            )

        self.np = np
        d = Path(model_dir)
        self.model_dir = d

        # ---- 1. tokenizer：与 fastembed 的 load_tokenizer 保持同一套参数 ----
        tcfg = json.loads((d / "tokenizer_config.json").read_text("utf-8"))
        cfg = json.loads((d / "config.json").read_text("utf-8"))

        # 截断长度取 model_max_length / max_length 里较小的那个（本模型是 128，不是 512）
        limits = []
        for key in ("model_max_length", "max_length"):
            v = tcfg.get(key)
            if isinstance(v, bool) or not isinstance(v, int):
                continue
            if 0 < v <= sys.maxsize:
                limits.append(v)
        if not limits:
            raise SystemExit("%s\\tokenizer_config.json 里没有可用的 model_max_length / max_length" % d)
        max_ctx = min(limits)

        tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        tok.enable_truncation(max_length=max_ctx,
                              direction=tcfg.get("truncation_side") or "right")

        stm = d / "special_tokens_map.json"
        if stm.is_file():
            tokens_map = json.loads(stm.read_text("utf-8"))
            for value in tokens_map.values():
                items = value if isinstance(value, list) else [value]
                for item in items:
                    if isinstance(item, str):
                        tok.add_special_tokens([item])
                    elif isinstance(item, dict):
                        tok.add_special_tokens([AddedToken(**item)])

        pad_token = tcfg.get("pad_token") or "<pad>"
        pad_id = cfg.get("pad_token_id")
        if pad_id is None:
            pad_id = tok.token_to_id(pad_token)
        if pad_id is None:
            raise SystemExit("%s 里找不到 pad token %r 对应的 id" % (d, pad_token))
        tok.enable_padding(
            direction=tcfg.get("padding_side") or "right",
            pad_id=pad_id,
            pad_type_id=tcfg.get("pad_token_type_id") or 0,
            pad_token=pad_token,
            length=None,
        )
        self.tok = tok
        self.max_ctx = max_ctx

        # ---- 2. ONNX 会话 ----
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if threads:
            so.intra_op_num_threads = int(threads)
        model_file = d / "model_optimized.onnx"
        self.sess = ort.InferenceSession(str(model_file), so,
                                         providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}

    def embed_raw(self, text):
        """单条文本 -> float32 原始向量（未归一化）。"""
        np = self.np
        enc = self.tok.encode(text)
        ids = np.array([enc.ids], dtype=np.int64)
        mask = np.array([enc.attention_mask], dtype=np.int64)
        feed = {"input_ids": ids}
        if "attention_mask" in self.input_names:
            feed["attention_mask"] = mask
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        out = self.sess.run(None, feed)[0]
        arr = np.asarray(out)

        if arr.ndim == 3:
            # 模型只吐 token 级向量 (1, L, 384)，要自己做 mean pooling。
            # 累加必须走 float64、最后再落回模型 dtype，否则和 fastembed 差在末位。
            m = mask if "attention_mask" in self.input_names else np.ones(arr.shape[:2], dtype=np.int64)
            total = np.sum(arr, axis=1, where=m[:, :, None].astype(bool), dtype=np.float64)
            count = np.sum(m, axis=1, keepdims=True)
            arr = (total / np.maximum(count, 1e-9)).astype(arr.dtype)
        if arr.ndim == 2:
            arr = arr[0]
        return np.asarray(arr, dtype=np.float32).reshape(-1)


# ---------------------------------------------------------------- 编码

def _norm_f32(vec):
    """与印象笔记台账 note_vector.py 的 norm() 同一算法（float32 累加 + 一次除法）。"""
    import numpy as np
    a = np.asarray(vec, dtype=np.float32)
    # 注意：这里刻意用 numpy float32 逐元素累加（从 int 0 起累加 np.float32 会保持
    # float32 精度），与 note_vector.py 里 `sum(x * x for x in vec)` 的舍入完全一致；
    # 换成 float64 累加会让末位差 1 ulp，base64 字符串就对不上了。
    s = math.sqrt(sum(x * x for x in a))
    if not s:
        return a
    return a / np.float32(s)


def to_base64(vec):
    """归一化 float32 小端 -> base64。与 note_vector.py 的 to_b64 逐字节一致。"""
    import numpy as np
    a = _norm_f32(vec)
    return base64.b64encode(a.astype("<f4").tobytes()).decode()


def from_base64(s):
    raw = base64.b64decode(s + "=" * ((4 - len(s) % 4) % 4))
    raw = raw[:len(raw) // 4 * 4]
    return list(struct.unpack("<%df" % (len(raw) // 4), raw))


def embed_base64(text, model_dir=None, threads=None):
    """对外主接口：一条文本 -> 2048 字符的 base64 字符串。"""
    global _model, _model_dir
    text = (text or "").strip()
    if not text:
        raise ValueError("文本为空")
    if _model is None or (_model_dir and model_dir and Path(model_dir) != _model_dir):
        # 一律走 resolve：显式传了 --model-dir 也要校验 5 个文件齐不齐，
        # 否则会在 Embedder 深处抛 FileNotFoundError，报错看不出是哪一步。
        _model_dir_path = resolve_model_dir(model_dir)
        _model = Embedder(_model_dir_path, threads=threads)
        _model_dir = _model_dir_path
    return to_base64(_model.embed_raw(text))


# ---------------------------------------------------------------- CLI

def _print_check(model_dir=None):
    import numpy
    import onnxruntime
    import tokenizers

    print("Python      : %s" % sys.version.split()[0])
    print("解释器      : %s" % sys.executable)
    print("numpy       : %s" % numpy.__version__)
    print("tokenizers  : %s" % tokenizers.__version__)
    print("onnxruntime : %s" % onnxruntime.__version__)
    d = resolve_model_dir(model_dir)
    print("模型目录    : %s" % d)
    size = (d / "model_optimized.onnx").stat().st_size / 1048576.0
    print("模型大小    : %.1f MB" % size)
    m = Embedder(d)
    print("截断长度    : %d token" % m.max_ctx)
    v = m.embed_raw("自检")
    print("输出维度    : %d" % len(v))
    b = to_base64(v)
    print("base64 长度 : %d" % len(b))
    print("模长        : %.6f" % math.sqrt(sum(float(x) * float(x) for x in _norm_f32(v))))
    print("状态        : OK")


def main(argv=None):
    _setup_stdout()
    ap = argparse.ArgumentParser(
        prog="embed.py",
        description="一条文本 -> 384 维向量的 base64（与印象笔记台账同格式）",
    )
    ap.add_argument("text", nargs="?", help="要转向量的文本（一次一条）")
    ap.add_argument("--model-dir", help="模型目录，默认取脚本同级 model\\，再退到 %s" % DEFAULT_MODEL_DIR)
    ap.add_argument("--check", action="store_true", help="自检环境并打印模型信息")
    ap.add_argument("--decode", action="store_true", help="把结果解成数字打印出来，便于核对")
    ap.add_argument("--threads", type=int, help="ONNX 线程数，默认交给运行时决定")
    ap.add_argument("-v", "--verbose", action="store_true", help="把诊断信息打到 stderr")
    args = ap.parse_args(argv)

    try:
        if args.check:
            _print_check(args.model_dir)
            return 0

        text = (args.text or "").strip()
        if not text:
            log("文本为空。用法：embed.py \"要转向量的文本\"")
            return 2

        b64 = embed_base64(text, model_dir=args.model_dir, threads=args.threads)

        if args.verbose:
            log("[i] 模型目录：%s" % _model_dir)
            log("[i] 截断长度：%d token" % _model.max_ctx)

        if args.decode:
            vals = from_base64(b64)
            norm = math.sqrt(sum(x * x for x in vals))
            print("dim      : %d" % len(vals))
            print("l2_norm  : %.6f%s" % (norm, "  (已归一化)" if abs(norm - 1.0) < 1e-3 else ""))
            print("base64   : %s" % b64)
            print("vector   :")
            for i, x in enumerate(vals):
                print("  [%3d] %.8f" % (i, x))
            return 0

        # 正常路径：标准输出只有 base64，不带换行
        sys.stdout.write(b64)
        sys.stdout.flush()
        return 0

    except ValueError as exc:
        log(str(exc))
        return 2
    except SystemExit as exc:
        if exc.code:
            log(str(exc.code))
        return 1
    except Exception as exc:  # noqa: BLE001
        log("[x] 出错：%s: %s" % (type(exc).__name__, exc))
        log("    加 -v 或跑 --check 看环境详情。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
