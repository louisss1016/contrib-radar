#!/usr/bin/env python3
"""contrib-radar 执行进度事件（v3.7，零第三方依赖）。

所有入口脚本共享。设计约束：
- 进度只写 stderr —— stdout 保持机器可读契约（--json 输出不被污染）。
- 双通道互斥（按消费者自动选择）：
  * 管道模式（stderr 非 TTY，agent/CI 消费）：单行 JSON 事件，
    前缀 [CR-PROGRESS]，ensure_ascii=True —— Windows GBK(cp936)
    控制台/管道安全（不引入 emoji/非 ASCII，与 v3.6.1
    ensure_utf8_stdio 同一原则）。
  * 交互模式（stderr 为 TTY，人类直接观看）：ASCII 进度条刷新，
    不输出 JSON 行。设置 CR_PROGRESS_BAR=1 可在管道中强制交互模式。
- CR_QUIET=1 或 --quiet 时全部关闭。
- 本模块不改变任何打分/筛选/门控逻辑，纯旁路输出。

事件字段（管道模式）：
    phase    阶段名（机器可读，短横线命名，如 health-check / issue-scan）
    status   start | running | ok | warn | error | skip | done
    current  当前条目序号（从 1 开始；阶段级事件为 null）
    total    总条目数（未知为 null）
    item     当前条目名（owner/repo、#123、PR URL 等）
    detail   附加说明（纯 ASCII）

典型序列：
    pg.phase("health-check", total=3)                      # 阶段开始
    pg.item(1, 3, "owner/repo", "running", phase_name="health-check")
    pg.item(1, 3, "owner/repo", "ok", detail="7/12", phase_name="health-check")
    pg.phase("health-check", "done", detail="3 repos, 1 failed")

Agent 侧消费约定见 SKILL.md「执行可视化规范」：每行一个 JSON 事件，
按 phase/status 聚合成阶段步骤条与当前状态；异常状态（error/warn/skip）
必须原样呈现，不得渲染为成功。
"""

import json
import os
import sys

PREFIX = "[CR-PROGRESS]"

_QUIET = os.environ.get("CR_QUIET") == "1"


def set_quiet(value):
    """--quiet 开关：关闭全部进度输出（含事件与进度条）。"""
    global _QUIET
    _QUIET = bool(value)


def quiet():
    return _QUIET


def _interactive():
    """交互模式 = stderr 是 TTY，或显式 CR_PROGRESS_BAR=1。"""
    if _QUIET:
        return False
    if os.environ.get("CR_PROGRESS_BAR") == "1":
        return True
    try:
        return bool(sys.stderr) and sys.stderr.isatty()
    except Exception:  # noqa: BLE001
        return False


def bar(current, total, width=24):
    """ASCII 进度条，如 [=======>---------] 5/10；total 未知时退化为计数。"""
    if not total:
        return f"[{current}]"
    filled = max(0, min(width, int(round(current / total * width))))
    body = "=" * width if filled >= width else "=" * filled + ">" + "-" * (width - filled - 1)
    return f"[{body}] {current}/{total}"


def emit(phase, status="running", current=None, total=None, item=None, detail=None):
    """管道模式：发射一条 JSON 进度事件到 stderr。写入失败静默跳过。"""
    if _QUIET or _interactive():
        return
    event = {"phase": phase, "status": status}
    if current is not None:
        event["current"] = current
    if total is not None:
        event["total"] = total
    if item is not None:
        event["item"] = item
    if detail is not None:
        event["detail"] = str(detail)
    try:
        sys.stderr.write(PREFIX + " " + json.dumps(event, ensure_ascii=True) + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass


def phase(name, status="start", total=None, detail=None):
    """阶段级事件。start=阶段开始；done=阶段结束（detail 放汇总数字）。"""
    if _interactive() and not _QUIET:
        try:
            tag = {"start": ">>", "done": "<<"}.get(status, "--")
            line = f"\r{tag} {name}" + (f"  ({detail})" if detail else "") + "   \n"
            sys.stderr.write(line)
            sys.stderr.flush()
        except Exception:  # noqa: BLE001
            pass
        return
    emit(name, status=status, total=total, detail=detail)


def item(current, total, name, status="running", detail=None, phase_name=None):
    """条目级进度：管道模式发 JSON 事件；交互模式刷新 ASCII 进度条。"""
    if _interactive():
        try:
            head = f"{phase_name}  " if phase_name else ""
            sys.stderr.write("\r" + head + bar(current, total) + f"  {name}  [{status}]"
                             + (f"  {detail}" if detail else "") + "   ")
            sys.stderr.flush()
        except Exception:  # noqa: BLE001
            pass
        return
    emit(phase_name or "item", status=status, current=current, total=total,
         item=name, detail=detail)


def item_end():
    """交互模式换行收尾（批次结束时调用，避免后续输出接在进度条后）。"""
    if _interactive():
        try:
            sys.stderr.write("\n")
            sys.stderr.flush()
        except Exception:  # noqa: BLE001
            pass
