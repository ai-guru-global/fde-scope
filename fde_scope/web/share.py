"""干系人只读分享（阶段 8 干系人验证 / 阶段 18 客户签收的参与通道）。

Token 模型——与管理员 API token（env）不同的**第二种凭据**，按资源发放：

- ``POST /api/engagements/{eid}/share`` 生成 ``secrets.token_urlsafe`` 明文
  token，**只在创建响应里出现一次**；engagement 落盘的是 sha256 + 8 位前缀
  （``assets["share_access"]``，经 ``ctx.save`` 原子写，不变式 4）。
- ``GET /share/{eid}?t=<token>`` 由 :class:`ApiTokenAuthMiddleware` 的 share
  分支校验：``sha256(t)`` 与存盘哈希 timing-safe 比对；无效 / 撤销 / 不存在
  **一律 404**——不向无凭据者确认某个 engagement 是否存在。
- 撤销即删除记录；审计事件只带 8 位前缀，绝不带 token（不变式 3/7）。
- 客户「签收」是**证据不是授权**：``share.ack`` 只进审计流；disengage 的
  ``handoff_signoff`` 门禁仍走控制台里 authed 的 accept 流程，分享链接永远
  不能推进状态机（只读，无 advance/gate 写路径）。

链接里的 token 会出现在浏览器历史与访问日志——这是 share link 的固有折衷；
 rotation（重新生成即吊销旧链接）是缓解手段，页面不伪造更强的保证。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Any

from ..audit import read_events
from ..engagement import EngagementContext
from ..engagement.phases import Phase, phase_by_slug
from ..engagement.retrospective import RetrospectiveReport, build_retrospective
from .deps import _validate_eid
from .layout import BASE_CSS, NOTICE_CSS

__all__ = [
    "SHARE_ASSET_KEY",
    "create_share",
    "record_of",
    "render_ack_page",
    "render_share_page",
    "revoke_share",
    "verify_share_token",
]

SHARE_ASSET_KEY = "share_access"
_ACK_ACTION = "share.ack"
_ZONES = {
    "pre_engagement": "A·定边界",
    "build": "B·造出来",
    "operationalization": "C·稳得住",
    "handoff": "D·交得出去",
}
#: 状态 → 工作台共用的 8px 圆点词汇（``layout`` 的 ``.dot``/``.d-*``），与控制台
#: 里的 ``mark()`` 同一张映射表：图形负责 3:1 的颜色判读，文字负责可读性。
#: ``✅❌⚠️🟢❔`` 是终端移植留下的字符——它们来自系统的 emoji 字体，不接受 ramp 的
#: 着色（深色主题下无法重染），不随字号对齐，屏幕阅读器读出的是图形名而不是状态。
#: 未识别的状态落到无色的 ``--faint`` 点，读作「尚无判定」，而不是为我们不懂的数据
#: 编造一个颜色。
_SLA_DOT = {"met": "d-ok", "on_track": "d-ok", "missed": "d-bad", "at_risk": "d-warn", "unknown": ""}

#: 分享页自己的版面，叠在 ``BASE_CSS`` 之上。凡是 ramp 已有答案的东西——面板、发丝线、
#: 墨色、间距阶、圆角、label-then-value 的 ``.stats``、``.sec-head``、字段 ``input``、
#: 按钮 ``.btn``——都来自共用层；这里只剩「一张纸 + 它的列宽」，没有第二个页面这样排版。
#: 原来的页面是灰底上叠五张圆角 12px 的白卡、自成一套 6 个十六进制灰阶、按钮蓝
#: ``#2563eb``（工作台的 ``--accent`` 是 #0A5EFA），即客户看到的第一个页面与本应用毫无
#: 关系。现在是一张纸自上而下读，分带用 ``.sec-head`` 的横线切开——报告不是卡片网格。
#: ``table``/``th``/``td`` 在这里照控制台量一遍而不提升进 ``COMPONENT_CSS``：那条规则
#: 是裸元素选择器，进了共用层会同时命中生成门户里每一张表，而那边由 ``.prose table`` 负责。
#: 只做浅色：未鉴权的读者没有本应用的 ``fde-theme`` 可选，按 ``prefers-color-scheme``
#: 半半地转深色只会让同一份报告在客户手机上是暗的、在 FDE 屏上是亮的。
_SHARE_CSS = (
    BASE_CSS
    + """
.sheet{max-width:860px;margin:0 auto;padding:var(--sp6) var(--sp4) var(--sp5)}
.brand{display:flex;align-items:center;gap:var(--sp2);flex-wrap:wrap;margin-bottom:var(--sp4)}
.sheet h1{margin:0;font-size:var(--fs-display);font-weight:650;line-height:1.2;
letter-spacing:var(--track-tight);text-wrap:balance;overflow-wrap:anywhere}
.sub{color:var(--muted);font-size:var(--fs-sm);margin:var(--sp2) 0 var(--sp5);max-width:68ch}
.sheet section{margin:0 0 var(--sp5)}
.hint{margin:var(--sp2) 0 0}
table{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}
th{font-size:var(--fs-xs);letter-spacing:0;color:var(--muted);text-align:left;padding:var(--sp2);
border-bottom:1px solid var(--border-strong);font-weight:600}
td{padding:var(--sp2);border-bottom:1px solid var(--border);vertical-align:top}
.blockers{margin:var(--sp1) 0 0;color:var(--muted);font-size:var(--fs-sm);line-height:1.7}
.acks{margin:0;color:var(--muted);font-size:var(--fs-sm);line-height:1.8}
.ackrow{display:flex;gap:var(--sp2);flex-wrap:wrap;align-items:stretch;margin-top:var(--sp3)}
.ackrow input{flex:1 1 220px;width:auto}
/* ``.sec-head`` 的分带横线与 ``.n`` 计数照旧，只是本页面不带图标精灵：``.sec-head``
   是 flex + gap，少一个 ``.ic`` 不改变任何对齐，为四张标题内联一整套 sprite 不值。 */
.phases{margin:0;padding-left:var(--sp4);font-size:var(--fs-sm);line-height:1.9}
.phases .done{color:var(--muted)}
.phases .now{font-weight:650;color:var(--accent-text)}
@media(max-width:640px){.sheet{padding:var(--sp4) var(--sp3) var(--sp5)}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""
)


def record_of(ctx: EngagementContext) -> dict[str, Any] | None:
    """存盘的分享记录（``token_sha256``/``token_prefix``/``created_at``），无则 ``None``。"""
    record = ctx.assets.get(SHARE_ASSET_KEY)
    if isinstance(record, dict) and isinstance(record.get("token_sha256"), str) and record["token_sha256"]:
        return record
    return None


def create_share(ctx: EngagementContext) -> tuple[str, dict[str, Any]]:
    """生成新 token（明文只经返回值出现一次）并把它替换进 context（rotation 即吊销）。"""
    token = secrets.token_urlsafe(24)
    record = {
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "token_prefix": token[:8],
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    ctx.assets[SHARE_ASSET_KEY] = record
    return token, record


def revoke_share(ctx: EngagementContext) -> bool:
    """删除分享记录；返回之前是否存在（幂等）。"""
    return ctx.assets.pop(SHARE_ASSET_KEY, None) is not None


def verify_share_token(eid: str, token: str | None) -> EngagementContext | None:
    """校验分享 token：合法且未撤销时返回该 engagement 的 context，否则 ``None``。

    一律 ``None``（页面上游映射 404）——不存在与撤销对调用者不可区分。
    """
    if not token or not eid:
        return None
    try:
        _validate_eid(eid)
    except Exception:
        return None
    from ..storage import get_storage_backend

    try:
        ctx = get_storage_backend().load_engagement(eid)
    except (KeyError, ValueError):
        return None
    record = record_of(ctx)
    if record is None:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not hmac.compare_digest(digest, record["token_sha256"]):
        return None
    return ctx


# ---------------------------------------------------------------------------
# 只读分享页
# ---------------------------------------------------------------------------
def _esc(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _dot(cls: str | None = "") -> str:
    """工作台共用的 8px 状态圆点；``cls`` 缺失（未知状态）即「尚无判定」的 ``--faint``。

    圆点从不单独出现——调用处必须紧跟一个词，图形负责颜色、文字负责读法。
    """
    return f'<span class="dot {cls}"></span>' if cls else '<span class="dot"></span>'


def _phase_row(phase: Phase, current: Phase) -> str:
    """阶段清单的一行：已完成＝静音，当前＝重墨高亮，未来＝常规墨色。

    不用删除线表示「过去」。删除线在语义上是「作废」，而一条走完的阶段是交付事实；
    原页面把两者混在一起，读起来像这份进度被撤回了一半。层级差就够了。
    """
    if phase.slug == current.slug:
        cls = "now"
    elif phase.index < current.index:
        cls = "done"
    else:
        cls = ""
    attr = f' class="{cls}"' if cls else ""
    return f"<li{attr}>{_esc(phase.slug)}（{_esc(phase.name)}）</li>"


def _gate_row(g: dict[str, Any]) -> str:
    """门禁台账的一行：名称 + 判定，未过时把阻塞项列在判定之下。

    阻塞项只在真有内容时出现。原来的写法是「未过」后面无条件跟一个 ``<ul>``，
    于是没有阻塞明细的门禁渲染出一对空项目符号——一个声称「这里有原因」却
    什么都没有的结构，比不写更糟。
    """
    if g["passed"]:
        verdict, blockers = _dot("d-ok") + " 通过", ""
    elif g["blockers"]:
        verdict = _dot("d-bad") + " 未过"
        blockers = '<ul class="blockers">' + "".join(f"<li>{_esc(b)}</li>" for b in g["blockers"]) + "</ul>"
    else:
        verdict, blockers = _dot("d-bad") + " 未过", ""
    return f"<tr><td><b>{_esc(g['name'])}</b></td><td>{verdict}{blockers}</td></tr>"


def render_share_page(
    ctx: EngagementContext,
    token: str,
    gates: list[dict[str, Any]],
) -> str:
    """渲染干系人只读页：进度 + SLA 时钟 + gate 台账 + 签收表单。

    ``gates`` 是调用方用默认注册表现查的结果（``{"slug","name","passed",
    "blockers","warnings"}``）——与控制台 ``GET /gates`` 同一来源，只读不落盘。
    """
    report: RetrospectiveReport = build_retrospective(ctx, list(read_events(ctx.id)))
    current = phase_by_slug(ctx.current_phase)
    phases = ctx.visible_phases
    done = [p for p in phases if p.index < current.index]
    acks = [e for e in read_events(ctx.id) if e.get("action") == _ACK_ACTION]

    sla_rows = "".join(
        f"<tr><td>{_esc(m.label)}</td><td>≤{m.deadline_days}d</td>"
        f"<td>{_dot(_SLA_DOT.get(m.status))} {_esc(m.status)}</td><td>{_esc(m.note)}</td></tr>"
        for m in report.sla
    )
    phase_rows = "".join(_phase_row(p, current) for p in phases)
    gate_rows = "".join(_gate_row(g) for g in gates)
    ack_html = (
        "".join(
            f"<li>{_esc(e.get('ts', ''))[:19].replace('T', ' ')} — {_esc((e.get('detail') or {}).get('label') or '客户签收')}</li>"
            for e in acks[-3:]
        )
        or "<li>尚无签收记录</li>"
    )
    last_ack = acks[-1] if acks else None
    passed = sum(1 for g in gates if g["passed"])
    elapsed = f"{report.elapsed_days:.1f}d" if report.elapsed_days is not None else "—"
    # ISO 微秒加 +00:00 是存储格式，不是给干系人读的：这一行是「什么时候开的工」，
    # 到分钟已经超出这份进度的分辨率，而签收列表本来也只截到分钟。
    started = _esc((report.started_at or "")[:16].replace("T", " "))
    zone = _esc(_ZONES.get(current.zone.value, current.zone.value))
    # 每个阶段都有适用门禁吗？没有——18 个阶段共用 10 条门禁，未覆盖的阶段查回空表。
    # SLA 一侧不需要这种兜底：``_MILESTONES`` 是固定元组，里程碑恒在。
    empty_gates = '<tr><td class="hint" colspan="2">当前阶段无适用门禁。</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>交付进度 · {_esc(ctx.customer)}</title>
<link rel="icon" href="/static/favicon.svg">
<style>{_SHARE_CSS}</style>
</head>
<body>
<main class="sheet">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">只读分享</span></div>
<h1>{_esc(ctx.customer)} · 交付进度</h1>
<p class="sub">{_esc(ctx.profile)} 档案 · 本页数据为渲染时刻快照</p>

<div class="stats">
<div class="stat"><div class="lab">区</div><div class="num">{zone}</div></div>
<div class="stat"><div class="lab">当前阶段</div><div class="num">{_esc(current.name)}</div></div>
<div class="stat"><div class="lab">阶段进度</div><div class="num">{len(done)}/{len(phases)}</div></div>
<div class="stat"><div class="lab">已历时</div><div class="num">{elapsed}</div></div>
</div>
<p class="hint">阶段代码 <code>{_esc(current.slug)}</code> · 开始于 {started or "—"}</p>

<section>
<div class="sec-head"><h2>SLA 里程碑</h2><span class="n">{len(report.sla)}</span></div>
<table><thead><tr><th>里程碑</th><th>契约</th><th>状态</th><th>说明</th></tr></thead>
<tbody>{sla_rows}</tbody></table>
</section>

<section>
<div class="sec-head"><h2>阶段清单</h2><span class="n">{len(phases)}</span></div>
<ol class="phases">{phase_rows}</ol>
</section>

<section>
<div class="sec-head"><h2>门禁现况</h2><span class="n">{passed}/{len(gates)}</span></div>
<table><tbody>{gate_rows or empty_gates}</tbody></table>
<p class="hint">门禁按当前阶段的注册表现查，只读结果；推进与判定只在工作台发生。</p>
</section>

<section>
<div class="sec-head"><h2>客户签收</h2><span class="n">{len(acks)}</span></div>
<ul class="acks">{ack_html}</ul>
<form method="post" action="/share/{_esc(ctx.id)}/ack?t={_esc(token)}" class="ackrow">
<input type="text" name="label" maxlength="80" placeholder="签收人 / 备注（可选）"
aria-label="签收人 / 备注（可选）">
<button class="btn" type="submit">{"确认签收（记录到项目审计）" if not last_ack else "再次确认"}</button>
</form>
<p class="hint">签收是证据记录，不会推进任何阶段；正式验收仍由 FDE 在工作台完成。</p>
</section>

<footer><span>FDE Scope · 只读分享页</span><span>链接由 FDE 生成并可随时吊销</span></footer>
</main>
</body>
</html>
"""


def render_ack_page(eid: str) -> str:
    """签收后的轻确认页（带返回分享页的链接——token 由浏览器历史/表单保留）。

    共用 :data:`layout.NOTICE_CSS`：这是一张居中的单面板回执，与六个「本安装没有
    这份资产」通知页同一件东西，原来它自写第三套（还漏了 viewport，客户在手机上
    打开时按 980px 排版）。标题不带判定图形——本页唯一的事实是「已记录」，
    没有成/败可读，勾号在这里只是装饰。
    """
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>签收已记录 · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">只读分享</span></div>
<h1>签收已记录</h1>
<p>这条确认已写入项目审计（时间戳 + 备注）。它不会推进任何阶段。</p>
<p><a href="javascript:history.back()">← 返回进度页</a></p>
<p class="hint">交付编号 <code>{_esc(eid)}</code></p>
</div>
</main>
</body>
</html>
"""
