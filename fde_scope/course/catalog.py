"""D1..D8 as data: one ``Lab`` per course day, every assertion a measured fact.

This module is a *registry*, not a framework. It holds no logic (that is
:mod:`fde_scope.course.verifier`) and no vocabulary (that is
:mod:`fde_scope.course.checks`). What it holds is the rubric for each day of
``course-level-1/06`` in a form a machine can execute — which is the whole point
of the package: the book's 门禁 were prose, so a self-studying reader could not
tell "I ran the command" from "the command proved the lesson".

Every literal here was produced by running the real CLI
(``python -m fde_scope …`` with ``COLUMNS=200 NO_COLOR=1`` and a private
``FDE_SCOPE_HOME``) and pasting what came back. Nothing is aspirational. When
the tool says something different from the lesson, the *tool's* text is what the
check asserts, and the ``ask`` states the disagreement — e.g. D2 records that a
vague criterion is only **warned** about, because ``SuccessCriteriaGate`` still
passes with ``提升体验`` present; the lesson's "全部可度量" is a human rule, so it
also gets a ``ManualCheck``.

Two groups per lab, in this order:

``contract``  the lesson's own example data through the real tool — proves gate
    semantics, refusals, reproducibility and the numbers the book prints. These
    pass on a cold machine, and that is the point: they are the tool's promise,
    not the student's.

``writing``   ``ArtifactCheck`` on ``{{drafts}}/<file>`` with
    ``not_contains=("TODO",)`` — the student's own document. These **fail on a
    cold run by design**, and the hint names the directory to edit. A lab that is
    all-green before you wrote anything would be grading a template.

Deliberately absent: ``engage advance --force``. Advancing the state machine
would re-evaluate gates (AGENTS.md invariant 1) and bury a failing gate under a
phase change; the days here are graded *at* ``qualification``, where every
``gate check --gate <slug>`` reaches the gate regardless of phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .checks import (
    ArtifactCheck,
    Check,
    Command,
    CommandCheck,
    DeterminismCheck,
    ManualCheck,
    MetricCheck,
)

Profile = Literal["ticket", "manufacturing"]

#: the customer every worked example in ``course-level-1`` uses
CUSTOMER = "西岸家电"


@dataclass(frozen=True)
class Lab:
    """One day of the course, as executable data.

    Frozen and holding tuples for the same reason ``checks.py`` does: the
    registry doubles as the readable rubric, so a reader must be able to trust
    that nothing mutated it between printing and scoring.

    ``eid`` is the engagement id the lab creates inside its own scratch
    workspace (each run gets a private ``FDE_SCOPE_HOME``), which is what lets
    every lab hardcode its id without touching a student's real engagements.
    """

    day: str
    title: str
    gate: str
    deliverable: str
    eid: str
    profile: Profile
    setup: tuple[Command, ...] = ()
    setup_hint: str = ""
    checks: tuple[Check, ...] = ()


def _init(profile: Profile) -> Command:
    """``engage init`` for the day's engagement — the only shared setup step.

    ``--id`` is an option, not a positional (``engage init <id>`` exits 2 with
    ``Got unexpected extra argument(s)``), and the profile decides how many
    phases are visible: ticket 15, manufacturing 18.
    """
    return Command(argv=("engage", "init", "--id", "{{eid}}", "--customer", CUSTOMER, "--profile", profile))


# ---------------------------------------------------------------------------
# D1 · 入门日（G1）— 一条真实数据 → 一份看得懂的报告
# ---------------------------------------------------------------------------
D1 = Lab(
    day="D1",
    title="入门日 · 打通链路",
    gate="G1",
    deliverable="迷你链路证据包（connect 样例 + corpus 报告 + 三句话解释）",
    eid="lab-d1",
    profile="ticket",
    setup=(_init("ticket"),),
    setup_hint="先跑 `python -m fde_scope course doctor`：它检查 Python 版本、包是否可导入、数据根目录是否可写。",
    checks=(
        CommandCheck(
            id="status",
            gate="G1",
            ask="工具说得出现在哪个阶段（engagement 真的建出来了，不是 JSON 里写了个名字）",
            hint="engage init 之后 engage status 才有输出；id 用 {{eid}} 这种一次性档案，别复用真实档案。",
            command=Command(argv=("engage", "status", "{{eid}}", "--json"), read_only=True),
            contains=("customer", "current_phase", "visible_phase_count", CUSTOMER),
        ),
        MetricCheck(
            id="phase",
            gate="G1",
            ask="当前阶段是 qualification，且工单档案可见 15 个阶段",
            hint="阶段名和数量由 profiles/ticket.py 决定；改这里之前先读 docs/architecture.md。",
            command=Command(argv=("engage", "status", "{{eid}}", "--json"), read_only=True),
            path="current_phase",
            one_of=("qualification",),
        ),
        MetricCheck(
            id="visible-phases",
            gate="G1",
            ask="工单档案的可见阶段数 = 15（制造业档案是 18，两者不是同一张 SOP）",
            hint="18 个阶段里只有 15 个对 ticket profile 可见——这是 profile 裁剪，不是丢了阶段。",
            command=Command(argv=("engage", "status", "{{eid}}", "--json"), read_only=True),
            path="visible_phase_count",
            approx=15,
            tol=0,
        ),
        CommandCheck(
            id="connect",
            gate="G1",
            ask="connect 读到 20 行并打印 schema（字段 / 类型 / 可空 / PII 四列）",
            hint="--source 是必填；示例数据在 course-level-1/labs/_shared/fixtures/sample_tickets.csv。",
            command=Command(
                argv=(
                    "connect",
                    "--type",
                    "csv",
                    "--source",
                    "{{shared}}/fixtures/sample_tickets.csv",
                    "--sample-size",
                    "20",
                ),
                read_only=True,
            ),
            contains=("Sample extracted", "nullable", "PII?", "sample_size=20"),
        ),
        MetricCheck(
            id="preview-rows",
            gate="G1",
            ask="样例文件真的落盘：samples/preview.json 里 20 条",
            hint="preview.json 在数据根目录下（每条 lab 用自己的 FDE_SCOPE_HOME，不影响你的真实档案）。",
            file="{{home}}/samples/preview.json",
            path="#len",
            approx=20,
            tol=0,
        ),
        CommandCheck(
            id="corpus",
            gate="G1",
            ask="corpus 造出语料并写出 HTML 报告",
            hint="--input（不是 --source）；报告旁边的 corpus_report.json 才是给机器看的那份。",
            command=Command(
                argv=(
                    "corpus",
                    "--input",
                    "{{shared}}/fixtures/sample_tickets.csv",
                    "--out",
                    "{{out}}/main/t.html",
                )
            ),
            contains=("Corpus forged", "20 real + 395 synthetic = 415 total", "Report →"),
        ),
        MetricCheck(
            id="total",
            gate="G1",
            ask="报告 JSON 里的 total 和命令行打印的 415 是同一个数（G1「数字与实际一致」）",
            hint="命令行说 415，文件里也是 415，才算证据；只有一处有数字 = 只有一半证据。",
            file="{{out}}/main/corpus_report.json",
            path="total",
            approx=415,
            tol=0,
        ),
        MetricCheck(
            id="real-share",
            gate="G1",
            ask="415 条里只有 20 条是真实数据，其余 395 条是合成",
            hint="合成比例是 G4「如实标注」的对象——先把 real / synthetic 两个字段读出来再说结论。",
            file="{{out}}/main/corpus_report.json",
            path="real",
            approx=20,
            tol=0,
        ),
        ArtifactCheck(
            id="html",
            gate="G1",
            ask="HTML 报告存在且不是空壳（≥ 4000 字节）",
            hint="没生成报告就检查 --out 的目录是否可写；报告与 corpus_report.json 落在同一目录。",
            file="{{out}}/main/t.html",
            min_bytes=4000,
        ),
        CommandCheck(
            id="bad-input",
            gate="G1",
            ask="喂一个不存在的输入：corpus 明确报错并返回非 0（不是静默产出空报告）",
            hint="报错文案是会变化的契约——这条失败说明 CLI 换了说法，改 catalog 而不是改课程。",
            command=Command(
                argv=("corpus", "--input", "{{fixtures}}/does-not-exist.csv", "--out", "{{out}}/bad/t.html"),
                exit_code=2,
            ),
            contains=("CSV source not found",),
        ),
        ManualCheck(
            id="explain",
            gate="G1",
            ask="三句话对同伴解释这份报告（415 / 20 / 395 各是什么），对方能复述",
            rubric="G1：命令真跑过｜能解释｜报告数字与实际一致。前两条由上面 10 项机器判定，这条只有人能判。",
        ),
    ),
)

# ---------------------------------------------------------------------------
# D2 · 定义成功（G2）— 客户委托单
# ---------------------------------------------------------------------------
_CRIT = ("engage", "criterion", "add", "{{eid}}", "--text")

D2 = Lab(
    day="D2",
    title="定义成功 · 委托单",
    gate="G2",
    deliverable="客户委托单（≤1 页：可度量成功标准 ≥3 条 + 双发起人 + 放弃标准）",
    eid="lab-d2",
    profile="ticket",
    setup=(_init("ticket"),),
    setup_hint="委托单是写出来的，工具只判「有没有」「重没重」「够不够两个人签字」。",
    checks=(
        CommandCheck(
            id="blocked-empty",
            gate="G2",
            ask="空档案上 gate check 直接 BLOCKED 且退出码 1",
            hint="gate check <id> --gate success_criteria 不看当前阶段，所以 D2 不需要 advance。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "success_criteria"), exit_code=1),
            contains=("BLOCKED", "成功标准未定义"),
        ),
        CommandCheck(
            id="sponsor-collapse",
            gate="G2",
            ask="0 个发起人本身就是阻塞项（防 Sponsor Collapse，要求 ≥2）",
            hint="sponsor 是 engage stakeholder add 上的 flag，不是 --role 的值。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "success_criteria"), exit_code=1),
            contains=("sponsor", "要求 ≥2"),
        ),
        CommandCheck(
            id="empty-criterion",
            gate="G2",
            ask="空文本的成功标准被拒绝（退出码 2）",
            hint="「先占个位」写不进契约——这就是拒绝空文本的理由。",
            command=Command(argv=(*_CRIT, ""), exit_code=2),
            contains=("成功标准不能为空",),
        ),
        CommandCheck(
            id="vague-criterion",
            gate="G2",
            ask="「提升体验」这类形容词会被接受，但立刻打出无法验收的警告",
            hint="工具没有硬拦：SuccessCriteriaGate 仍会 PASS。G2 的「全部可度量」是人判的门禁，所以下面还有一条 ManualCheck。",
            command=Command(argv=(*_CRIT, "提升体验")),
            contains=("没有数字", "门禁 G2 会打回"),
        ),
        CommandCheck(
            id="measurable-1",
            gate="G2",
            ask="第一条带数字的标准；累计计数把上面那条形容词也算进去了",
            hint="「✅ 成功标准 N 条已记录」里的 N 是**累计条数**，不是「可度量条数」——G2 打回的是后者。",
            command=Command(argv=(*_CRIT, "自动解决率 ≥ 40%")),
            contains=("成功标准 2 条已记录",),
        ),
        CommandCheck(
            id="measurable-2",
            gate="G2",
            ask="第二条带数字的标准（累计 3 条里只有 2 条能验收）",
            hint="数到 3 不等于「≥3 条可度量」。删掉那条形容词，计数立刻掉下来——这就是 G2 要人判的原因。",
            command=Command(argv=(*_CRIT, "人工升级率 ≤ 10%")),
            contains=("成功标准 3 条已记录",),
        ),
        CommandCheck(
            id="measurable-3",
            gate="G2",
            ask="第三条带数字的标准（累计 4 条 = 3 条可度量 + 1 条形容词）",
            hint="`06` Day 2 要求「成功标准 ≥3 条：全部可度量」。工具只数总量，分开两者是你和验收方的活。",
            command=Command(argv=(*_CRIT, "首次响应 ≤ 5min")),
            contains=("成功标准 4 条已记录",),
        ),
        CommandCheck(
            id="duplicate",
            gate="G2",
            ask="同一条标准写第二遍被拒绝（退出码 2）",
            hint="凑数会被发现：文案完全相同即重复。",
            command=Command(argv=(*_CRIT, "自动解决率 ≥ 40%"), exit_code=2),
            contains=("重复的成功标准",),
        ),
        CommandCheck(
            id="sponsor-1",
            gate="G2",
            ask="第一个 sponsor 记录后，工具提醒「1 位 / 要求 ≥2」",
            hint="一个 sponsor 的项目由一个人定义成功——这就是 Sponsor Collapse。",
            command=Command(
                argv=(
                    "engage",
                    "stakeholder",
                    "add",
                    "{{eid}}",
                    "--name",
                    "客服总监",
                    "--role",
                    "运营",
                    "--sponsor",
                )
            ),
            contains=("sponsor", "当前发起人 1 位（要求 ≥2"),
        ),
        CommandCheck(
            id="sponsor-2",
            gate="G2",
            ask="第二个 sponsor 到位（数字化负责人）",
            hint="两个发起人来自不同部门才算数——--role 是自由文本，工具不看部门。",
            command=Command(
                argv=(
                    "engage",
                    "stakeholder",
                    "add",
                    "{{eid}}",
                    "--name",
                    "数字化负责人",
                    "--role",
                    "IT",
                    "--sponsor",
                )
            ),
            contains=("当前发起人 2 位",),
        ),
        MetricCheck(
            id="criteria-count",
            gate="G2",
            ask="criterion list 里确实是 4 条（3 条带数字 + 1 条被警告的形容词）",
            hint="机器只数得清数量；数量里混进几条不可度量的，是 G2 的人工部分。",
            command=Command(argv=("engage", "criterion", "list", "{{eid}}", "--json"), read_only=True),
            path="success_criteria#len",
            approx=4,
            tol=0,
        ),
        MetricCheck(
            id="gate-passes-anyway",
            gate="G2",
            ask="gate 放行（passed=true）——注意：形容词那条没有拦住它",
            hint="这是工具与门禁的已知差距：把「提升体验」删掉之前，G2 靠人判。见 course-level-1/03 §4 诚实标注。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "success_criteria", "--json")),
            path="passed",
            one_of=(True,),
        ),
        MetricCheck(
            id="warning-kept",
            gate="G2",
            ask="但那条警告留在 warnings 里（≥1 条）——放行不等于没意见",
            hint="gate 的 warnings 是给你、也是给验收方看的；交付时把它读出来，别只说 PASS。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "success_criteria", "--json")),
            path="warnings#len",
            gte=1,
        ),
        ArtifactCheck(
            id="委托单",
            gate="G2",
            ask="委托单写完了：{{drafts}}/委托单.md 里已经没有 TODO",
            hint="文件在这条 lab 的数据目录下：用 `python -m fde_scope course check D2 --keep` 打印工作区路径。",
            file="{{drafts}}/委托单.md",
            not_contains=("TODO",),
            min_bytes=600,
        ),
        ManualCheck(
            id="委托单质量",
            gate="G2",
            ask="委托单 ≤1 页：≥3 条全可度量（禁「提升体验」类）｜≥2 发起人｜写了放弃标准",
            rubric="放弃标准是「什么情况下这个项目该停」——没这条的委托单会演成无限 pilot。",
        ),
    ),
)

# ---------------------------------------------------------------------------
# D3 · 数据与现场体检（G3）
# ---------------------------------------------------------------------------
D3 = Lab(
    day="D3",
    title="现场与数据体检",
    gate="G3",
    deliverable="数据体检报告（字段表 + PII 处置 + 现场事实 + ≥3 条质量风险）",
    eid="lab-d3",
    profile="manufacturing",
    setup=(_init("manufacturing"),),
    setup_hint="D3 用 manufacturing profile：site_survey 是工业门禁，ticket profile 下它「不适用」而不是通过。",
    checks=(
        CommandCheck(
            id="site-blocked",
            gate="G3",
            ask="没有现场事实时 site_survey BLOCKED（location 缺失 + 资产清单为空）",
            hint="「不适用」和「未通过」是两件事：换个 profile 跑同一条命令会看到 not applicable。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "site_survey"), exit_code=1),
            contains=("现场勘察缺失", "资产清单为空"),
        ),
        CommandCheck(
            id="site-minimal",
            gate="G3",
            ask="只填 location 就能让门禁 PASS——同时留下「资产清单为空」的警告",
            hint="门禁的最低要求 ≠ 体检的完成标准。这条把两者的差距变成可见的警告。",
            command=Command(argv=("engage", "site", "set", "{{eid}}", "--location", "总装车间 A 线")),
            contains=("现场事实已记录", "资产 0 项"),
        ),
        CommandCheck(
            id="site-pass-warning",
            gate="G3",
            ask="此时 gate check 是 PASS 但带警告（0 项资产）",
            hint="PASS + warning 是最容易被念成「全绿」的状态——交接时要一起念。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "site_survey")),
            contains=("PASS", "资产清单为空"),
        ),
        CommandCheck(
            id="site-full",
            gate="G3",
            ask="补齐网络拓扑 / 班次 / OT-IT 隔离 / 5 项资产清单",
            hint="--network 可重复传；--assets-file 支持 CSV/JSON/JSONL（列：name/type/vendor/protocol/criticality）。",
            command=Command(
                argv=(
                    "engage",
                    "site",
                    "set",
                    "{{eid}}",
                    "--location",
                    "总装车间 A 线",
                    "--network",
                    "PROFINET",
                    "--network",
                    "OPC UA 汇聚",
                    "--shift-count",
                    "3",
                    "--ot-it-separated",
                    "--assets-file",
                    "{{fixtures}}/assets.csv",
                )
            ),
            contains=("资产 5 项", "班次 3"),
        ),
        MetricCheck(
            id="site-warnings-clear",
            gate="G3",
            ask="补齐之后 warnings 归零（passed=true, warnings=[]）",
            hint="这就是「把警告关掉」和「把事实补齐」的区别：数字变了，不是文案变了。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "site_survey", "--json")),
            path="warnings#len",
            approx=0,
            tol=0,
        ),
        CommandCheck(
            id="site-show",
            gate="G3",
            ask="site show 把现场事实回读成四行（可交接的口径）",
            hint="气隙 / 职工代表这两项在 D3 里是 False：它们属于 air_gap 与 works_council 门禁，不是漏填。",
            command=Command(argv=("engage", "site", "show", "{{eid}}"), read_only=True),
            contains=(
                "OT/IT 隔离: True",
                "网闸/气隙: False",
                "班次: 3",
                "网络: PROFINET, OPC UA 汇聚",
                "资产: 5 项",
            ),
        ),
        CommandCheck(
            id="ticket-corpus",
            gate="G3",
            ask="客服工单语料里 PII 被脱敏（2 个实体）",
            hint="connect 的 PII? 列是「字段可能是 PII」，corpus 的这个数字是「真脱敏了几个」——两个都要写进体检报告。",
            command=Command(
                argv=(
                    "corpus",
                    "--input",
                    "{{shared}}/fixtures/sample_tickets.csv",
                    "--out",
                    "{{out}}/ticket/t.html",
                )
            ),
            contains=("PII entities masked: 2",),
        ),
        MetricCheck(
            id="pii-count",
            gate="G3",
            ask="报告 JSON 里 pii_entities_masked = 2（与打印一致）",
            hint="PII 清单要带处置：脱敏 / 丢弃 / 保留，写清楚是谁决定的。",
            file="{{out}}/ticket/corpus_report.json",
            path="pii_entities_masked",
            approx=2,
            tol=0,
        ),
        MetricCheck(
            id="dropped",
            gate="G3",
            ask="去重与质量门槛丢掉的行数（dropped = 0：这 20 条没有重复）",
            hint="dropped=0 不是好消息，只是没信号——样本太小看不出重复。",
            file="{{out}}/ticket/corpus_report.json",
            path="dropped",
            approx=0,
            tol=0,
        ),
        CommandCheck(
            id="alarm-corpus",
            gate="G3",
            ask="12 条设备告警造出 572 条语料，12 个类别每类只有 1 条真实样本",
            hint="告警语料的 category 是报警类型，不是工单类型——合成量放大 46 倍不等于风险覆盖。",
            command=Command(
                argv=("corpus", "--input", "{{fixtures}}/alarm_corpus.jsonl", "--out", "{{out}}/alarm/t.html")
            ),
            contains=("12 real + 560 synthetic = 572 total", "Coverage gaps"),
        ),
        MetricCheck(
            id="alarm-gaps",
            gate="G3",
            ask="体检报告拿得出「≥3 条质量风险」：这里是 12 个覆盖缺口",
            hint="gaps 是列表，长度可判；条目的顺序不保证稳定，所以别断言「第一条是什么」。",
            file="{{out}}/alarm/corpus_report.json",
            path="coverage.gaps#len",
            approx=12,
            tol=0,
        ),
        MetricCheck(
            id="alarm-target",
            gate="G3",
            ask="每类目标 100 条，急停事件只有 1 条（安全相关的类别最薄）",
            hint="按类别取值而不是按顺序取值，才能写得出不依赖排序的断言。",
            file="{{out}}/alarm/corpus_report.json",
            path="coverage.category_counts.急停事件",
            approx=1,
            tol=0,
        ),
        ArtifactCheck(
            id="体检报告",
            gate="G3",
            ask="数据体检报告写完了：{{drafts}}/数据体检报告.md 里没有 TODO",
            hint="报告要把上面 12 项的结论写成人能读的一页：字段表 → PII 处置 → 现场事实 → 风险与下一步。",
            file="{{drafts}}/数据体检报告.md",
            not_contains=("TODO",),
            min_bytes=600,
        ),
        ManualCheck(
            id="体检结论",
            gate="G3",
            ask="字段表含类型与缺失率｜PII 清单带处置方式｜有明确结论｜≥3 条质量风险",
            rubric="connect 打印的是 nullable，不是缺失率——缺失率要自己按列数出来，并在报告里写清统计口径。",
        ),
    ),
)

# ---------------------------------------------------------------------------
# D4 · 语料报告与客户话术（G4）
# ---------------------------------------------------------------------------
D4 = Lab(
    day="D4",
    title="语料与话术",
    gate="G4",
    deliverable="语料报告 + 一段客户话术（零术语，合成比例如实标注）",
    eid="lab-d4",
    profile="ticket",
    setup=(_init("ticket"),),
    setup_hint="D4 复用 D1 的 corpus 命令，但断言换成「切分与来源字段」——同一份数据，另一组问题。",
    checks=(
        CommandCheck(
            id="corpus",
            gate="G4",
            ask="语料造完（415 条）并写出 JSON 报告",
            hint="报告是给机器看的，HTML 是给人看的，两个都算交付物。",
            command=Command(
                argv=(
                    "corpus",
                    "--input",
                    "{{shared}}/fixtures/sample_tickets.csv",
                    "--out",
                    "{{out}}/main/t.html",
                )
            ),
            contains=("Corpus forged",),
        ),
        MetricCheck(
            id="splits",
            gate="G4",
            ask="切分是 332 / 41 / 42，三块加起来正好 415（没有泄漏，也没有丢数据）",
            hint="train.items/eval.items/test.items 是列表，长度用 #len 取——直接取路径会拿到 None。",
            file="{{out}}/main/corpus_report.json",
            path="train.items#len",
            approx=332,
            tol=0,
        ),
        MetricCheck(
            id="eval-split",
            gate="G4",
            ask="eval 切分 41 条",
            hint="切分比例由 templates/corpus_config.yaml 决定；改配置之前先确认这 41 条够不够打分。",
            file="{{out}}/main/corpus_report.json",
            path="eval.items#len",
            approx=41,
            tol=0,
        ),
        MetricCheck(
            id="synthetic-share",
            gate="G4",
            ask="合成比例如实可查：395 / 415 ≈ 95%（数字在报告里，不在你的措辞里）",
            hint="G4 的「如实标注」是可验证的：报告里 real=20、synthetic=395，话术里就不许说「基于真实业务数据训练」。",
            file="{{out}}/main/corpus_report.json",
            path="synthetic",
            approx=395,
            tol=0,
        ),
        MetricCheck(
            id="golden-zero",
            gate="G4",
            ask="golden 集为 0 条——还没有人工标注的标准答案",
            hint="golden=0 意味着任何「准确率」都是自动判出来的，别把它写成人工核对过的。",
            file="{{out}}/main/corpus_report.json",
            path="golden",
            approx=0,
            tol=0,
        ),
        MetricCheck(
            id="diversity",
            gate="G4",
            ask="语义多样性指数 ≥ 0.9（合成语料把类别铺开了）",
            hint="多样性高不代表质量好：它只说明类别分布平，不说明每条都能用。",
            file="{{out}}/main/corpus_report.json",
            path="coverage.diversity_index",
            gte=0.9,
        ),
        MetricCheck(
            id="target-per-category",
            gate="G4",
            ask="每类目标 100 条（缺口是按这个目标算出来的）",
            hint="把目标写进报告，客户才能判断「补盲要补多少」。",
            file="{{out}}/main/corpus_report.json",
            path="coverage.target_per_category",
            approx=100,
            tol=0,
        ),
        ArtifactCheck(
            id="provenance",
            gate="G4",
            ask="每条语料带 provenance 字段（真实 / 合成 / golden 的来源可追）",
            hint="可追溯是「合成比例如实标注」能被复查的前提；没有 provenance，比例就是口头说法。",
            file="{{out}}/main/corpus_report.json",
            contains=("provenance",),
            min_bytes=100000,
        ),
        ArtifactCheck(
            id="话术",
            gate="G4",
            ask="客户话术里不出现内部术语（机器逐字拦 SLO / P95 / OEE / bad case / corpus 五个写法）",
            hint="话术在 {{drafts}}/客户话术.md。术语清单是可以机器判的——这是 G4「零术语」唯一能被自动化的部分。",
            file="{{drafts}}/客户话术.md",
            not_contains=("TODO", "SLO", "P95", "OEE", "bad case", "corpus"),
            min_bytes=300,
        ),
        ManualCheck(
            id="话术质量",
            gate="G4",
            ask="话术让非技术负责人读一遍就能复述：做什么、怎么算成功、现在做到哪",
            rubric="零术语是底线，不是目标；目标是对方愿意在验收单上签字。数字与 D4 报告一致（415 / 20 / 395）。",
        ),
    ),
)

# ---------------------------------------------------------------------------
# D5 · 验证与评估（G5）
# ---------------------------------------------------------------------------
_EVAL_MOCK = ("eval", "--agent", "mock")

D5 = Lab(
    day="D5",
    title="验证与评估",
    gate="G5",
    deliverable="原型证据 + 评估结果 + Top3 bad case + 一页验证记录",
    eid="lab-d5",
    profile="ticket",
    setup=(_init("ticket"),),
    setup_hint="评估不需要 LLM：--agent mock 是规则版，种子固定所以可复现。",
    checks=(
        CommandCheck(
            id="unknown-agent",
            gate="G5",
            ask="写错 agent 名会被明确拒绝（退出码 2），而不是静默改用别的",
            hint="可选值只有 mock / mimo；mimo 需要 FDE_SCOPE_MIMO_API_KEY（只从环境变量读）。",
            command=Command(
                argv=(*_EVAL_MOCK[:2], "bogus", "--test-set", "{{fixtures}}/test_set.jsonl"),
                exit_code=2,
            ),
            contains=("Unknown agent",),
        ),
        MetricCheck(
            id="unlabeled-accuracy",
            gate="G5",
            ask="没有 expected_category 的测试集：intent_accuracy = 1.000（无信号 = 判为对）",
            hint="这是 vacuous pass，不是好消息——所以课程让你先删标签跑通，再补标签看真实判分。",
            command=Command(
                argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set.jsonl", "--json"), read_only=True
            ),
            path="metrics.intent_accuracy",
            approx=1.0,
        ),
        MetricCheck(
            id="labeled-accuracy",
            gate="G5",
            ask="补上 expected_category 后：intent_accuracy = 0.000（子串判分，不是模型变差）",
            hint="score_intent_accuracy 判的是「类别名出现在回复里」；mock 的回复不含类别名，所以恒为 0。见 course-level-1/12 §2.4。",
            command=Command(
                argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set_labeled.jsonl", "--json"),
                read_only=True,
            ),
            path="metrics.intent_accuracy",
            approx=0.0,
        ),
        MetricCheck(
            id="escalation",
            gate="G5",
            ask="业务口径指标：人工升级率 0.200（5 条里有 1 条 escalated）",
            hint="G5 要「主指标 + 至少 1 个业务口径指标」；escalation_rate 就是那个业务口径。",
            command=Command(
                argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set.jsonl", "--json"), read_only=True
            ),
            path="metrics.escalation_rate",
            approx=0.2,
        ),
        MetricCheck(
            id="bad-case-id",
            gate="G5",
            ask="bad case 指到具体那条：c-003「这家店的服务太差了！我要投诉」",
            hint="bad_cases.cases 是列表，第 0 项的路径写成 cases.0.case_id。",
            command=Command(
                argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set.jsonl", "--json"), read_only=True
            ),
            path="bad_cases.cases.0.case_id",
            one_of=("c-003",),
        ),
        MetricCheck(
            id="bad-case-category",
            gate="G5",
            ask="失败按类别聚合：门店投诉 1 条（挑 Top3 时要按类别说，不是按条数罗列）",
            hint="字典的键可以是中文——路径写 bad_cases.by_category.门店投诉。",
            command=Command(
                argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set.jsonl", "--json"), read_only=True
            ),
            path="bad_cases.by_category.门店投诉",
            approx=1.0,
        ),
        CommandCheck(
            id="recommendation",
            gate="G5",
            ask="工具给的是下一步动作，不只是分数：建议补充某类语料",
            hint="bad case 的四段里「下一步动作」这栏，可以直接引用这句建议，再写清预计改善。",
            command=Command(
                argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set_labeled.jsonl"), read_only=True
            ),
            contains=("Top bad case category: 退款售后", "建议补充「退款售后」类语料"),
        ),
        DeterminismCheck(
            id="reproducible",
            gate="G5",
            ask="G5「同命令同结果可复现」：同一命令跑两遍，全部指标一致",
            hint="mock 用固定种子（MockReplyFn(seed=0)）；这里漂了说明管线不可复现，正是 Demo 债的样子。",
            command=Command(argv=(*_EVAL_MOCK, "--test-set", "{{fixtures}}/test_set.jsonl", "--json")),
            path="metrics",
        ),
        ArtifactCheck(
            id="验证记录",
            gate="G5",
            ask="验证记录写完了：{{drafts}}/验证记录.md 里没有 TODO",
            hint="向谁演示、对方提了什么、接受 / 拒绝了什么——拒绝的要写理由。",
            file="{{drafts}}/验证记录.md",
            not_contains=("TODO",),
            min_bytes=400,
        ),
        ManualCheck(
            id="top3",
            gate="G5",
            ask="Top3 bad case 每条四段：现象 → 根因假设 → 下一步动作 → 预计改善（只描述现象 = 未达）",
            rubric="再用策展数据检查一下：如果指标全绿但挖不出坏例子，G5 视为未达（06 的「常见坑」第一条）。",
        ),
    ),
)

# ---------------------------------------------------------------------------
# D6 · 运维化（G6）
# ---------------------------------------------------------------------------
_SLO = ("engage", "slo", "add", "{{eid}}")

D6 = Lab(
    day="D6",
    title="运维化",
    gate="G6",
    deliverable="SLO 卡（3 条 + 错误预算 + 告警路由）+ Runbook + 值班交接卡",
    eid="lab-d6",
    profile="manufacturing",
    setup=(_init("manufacturing"),),
    setup_hint=(
        "D6 用 manufacturing profile：kpi 读的是档案自己 profile 的指标表。工单档案跑工业样本不报错，"
        "只回一屏 0.0（intent_accuracy 之类）——静默错答比 traceback 更难发现，所以 KPI 项必须在 "
        "manufacturing 档案上跑。真正会炸的是 engage init --profile 打错（这个参数不校验）："
        "kpi 抛 KeyError: Unknown profile: 'bogus'，退出码 1。"
    ),
    checks=(
        CommandCheck(
            id="slo-blocked",
            gate="G6",
            ask="没有 SLO 时 slo 门禁 BLOCKED：错误预算 / 告警路由无从谈起",
            hint="SLO 不是「目标值」的另一种写法：目标 + 测量方式 + 预算 + 谁被叫醒，四件齐全才算运维化。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "slo"), exit_code=1),
            contains=("BLOCKED", "未定义任何 SLO"),
        ),
        CommandCheck(
            id="slo-no-route",
            gate="G6",
            ask="只给目标值的 SLO 会被接受，但立刻警告「未填告警路由」",
            hint="G6 的「告警路由明确」和 G2 的「全部可度量」一样是人判门禁：工具放行，警告留着。",
            command=Command(argv=(*_SLO, "--name", "自动解决率", "--target", "40%")),
            contains=("已定义", "未填告警路由"),
        ),
        CommandCheck(
            id="slo-routed",
            gate="G6",
            ask="补上错误预算与告警路由（谁 / 哪个渠道 / 多久响应）",
            hint="路由写成人能执行的一句话：值班 FDE / 企微群 / 15 分钟内响应。",
            command=Command(
                argv=(
                    *_SLO,
                    "--name",
                    "P95 响应延迟",
                    "--target",
                    "<=2s",
                    "--error-budget",
                    "月 30min",
                    "--alert-route",
                    "平台组 / 电话 / 5min",
                )
            ),
            contains=("已定义",),
        ),
        CommandCheck(
            id="slo-availability",
            gate="G6",
            ask="第三条 SLO：可用性 99.5% + 错误预算 1.68h/14d（`build_slo_template` 的默认值）",
            hint="错误预算不是拍的：14d × 24h × (1 − 99.5%) = 1.68h。工具把这条算式写在 "
            "fde_scope/engagement/operationalization.py 里，SLO 卡要能把算法念给客户听。",
            command=Command(
                argv=(
                    *_SLO,
                    "--name",
                    "可用性",
                    "--target",
                    "99.5%",
                    "--error-budget",
                    "1.68h / 14d",
                    "--alert-route",
                    "值班 FDE / 企微群 / 15min",
                )
            ),
            contains=("已定义", "window="),
        ),
        MetricCheck(
            id="slo-count",
            gate="G6",
            ask="SLO 卡上真的有 3 条（同名会各算一条，所以先把名字写准）",
            hint="slo add 不去重：同 name 再写一次是追加第二条，list 里能看到。",
            command=Command(argv=("engage", "slo", "list", "{{eid}}", "--json"), read_only=True),
            path="slos#len",
            gte=3,
        ),
        MetricCheck(
            id="slo-gate",
            gate="G6",
            ask="slo 门禁 passed=true——但警告仍在（第一条 SLO 没路由）：passed 只判「有没有 SLO」",
            hint="门禁只看「有没有路由」，且只把它记成 warning；错误预算它一眼都不看"
            "（fde_scope/engagement/operationalization.py:30-36）。G6 的②要靠盲测，不靠这里。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "slo", "--json")),
            path="passed",
            one_of=(True,),
        ),
        MetricCheck(
            id="oee",
            gate="G6",
            ask="现场 KPI 可复现：OEE 0.5111（示例产线数据算出来的，与 07 教案一致）",
            hint="数字来自 {{fixtures}}/assy.jsonl（总装线样本）；换数据就要重跑，别沿用旧截图。",
            command=Command(
                argv=("kpi", "{{eid}}", "--samples", "{{fixtures}}/assy.jsonl", "--json"), read_only=True
            ),
            path="kpis.oee",
            approx=0.511056,
            tol=1e-4,
        ),
        MetricCheck(
            id="grasp",
            gate="G6",
            ask="抓取成功率 73.3%——和 07 教案里那个数字是同一个（教案不许漂移）",
            hint="grasp_success_rate 的 JSON 是全精度 0.7333…，教案写 73%；tol=1e-4 让两边都能对上。",
            command=Command(
                argv=("kpi", "{{eid}}", "--samples", "{{fixtures}}/assy.jsonl", "--json"), read_only=True
            ),
            path="kpis.grasp_success_rate",
            approx=0.7333333333333333,
            tol=1e-4,
        ),
        MetricCheck(
            id="collision",
            gate="G6",
            ask="碰撞干预率 3.2%（越低越好，与 07 教案一致）",
            hint="collision_intervention_rate 是安全口径：它进 SLO 卡时目标值要写「≤」而不是「≥」。",
            command=Command(
                argv=("kpi", "{{eid}}", "--samples", "{{fixtures}}/assy.jsonl", "--json"), read_only=True
            ),
            path="kpis.collision_intervention_rate",
            approx=0.03214285714285714,
            tol=1e-4,
        ),
        ArtifactCheck(
            id="runbook",
            gate="G6",
            ask="Runbook 五类事件都写了回滚步骤（{{drafts}}/Runbook.md，无 TODO 且含「回滚」）",
            hint="每类四段：判断信号 → 处置步骤 → 回滚步骤 → 升级路径。写成说明书不算。",
            file="{{drafts}}/Runbook.md",
            not_contains=("TODO",),
            contains=("服务不可用", "指标暴跌", "数据异常", "权限配额", "上游依赖", "回滚"),
            min_bytes=800,
        ),
        ArtifactCheck(
            id="值班交接卡",
            gate="G6",
            ask="值班交接卡四栏齐全：当前状态 / 待办 / 已知风险 / 联系人",
            hint="这张卡是给凌晨 2 点被叫醒的人看的——他不需要认识你，只需要能照着做。",
            file="{{drafts}}/值班交接卡.md",
            not_contains=("TODO",),
            contains=("当前状态", "待办", "已知风险", "联系人"),
        ),
        ManualCheck(
            id="盲测",
            gate="G6",
            ask="找一位同学做「凌晨 2 点盲测」：他照你的文档念，能处理完才算过",
            rubric="盲测通过 = 他不需要问你任何问题。中途任何一次提问，回到 Runbook 补那段步骤，再测一次。",
        ),
    ),
)

# ---------------------------------------------------------------------------
# D7 · 交接与沉淀（G7）
# ---------------------------------------------------------------------------
D7 = Lab(
    day="D7",
    title="交接与沉淀",
    gate="G7",
    deliverable="交接包四件套 + 技能卡 + 退场计划",
    eid="lab-d7",
    profile="manufacturing",
    setup=(_init("manufacturing"),),
    setup_hint="四件套里的 Runbook 由 handoff 命令生成；SLO 必须先在 D6 那种命令里定义过，否则门禁会指出缺 slo_definition。",
    checks=(
        CommandCheck(
            id="handoff",
            gate="G7",
            ask="装配移交包（评估报告 + 培训材料 + 客户接受）并生成 Runbook",
            hint="handoff 先写 runbook_<id>.md 再打印摘要；--eval-report / --training-material 只记路径，不校验文件。",
            command=Command(
                argv=(
                    "handoff",
                    "{{eid}}",
                    "--eval-report",
                    "{{fixtures}}/eval_report.md",
                    "--training-material",
                    "{{drafts}}/培训材料.md",
                    "--accept",
                )
            ),
            contains=("Handoff package assembled", "customer accepted: ✅"),
        ),
        CommandCheck(
            id="signoff-blocked",
            gate="G7",
            ask="没定义 SLO 时 handoff_signoff 仍然 BLOCKED：缺 slo_definition",
            hint="这条是「四件套」里最容易漏的一件：报告可以贴，SLO 必须是档案里真定义过的对象。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "handoff_signoff"), exit_code=1),
            contains=("BLOCKED", "移交包缺失", "slo_definition"),
        ),
        CommandCheck(
            id="slo-added",
            gate="G7",
            ask="把 SLO 定义补进档案（三件套：目标 + 预算 + 路由）",
            hint="补完还要再装配一次移交包——包里的 slo_definition 是装配那一刻的快照，不是实时视图。",
            command=Command(
                argv=(
                    "engage",
                    "slo",
                    "add",
                    "{{eid}}",
                    "--name",
                    "自动解决率",
                    "--target",
                    ">=40%",
                    "--error-budget",
                    "月 2pp",
                    "--alert-route",
                    "值班 FDE / 企微群 / 15min",
                )
            ),
            contains=("已定义",),
        ),
        CommandCheck(
            id="handoff-again",
            gate="G7",
            ask="再装配一次：新定义的 SLO 才进入移交包",
            hint="「改了数据、忘了重跑交付物」是交接事故的经典成因；门禁看的是包，不是档案。",
            command=Command(
                argv=(
                    "handoff",
                    "{{eid}}",
                    "--eval-report",
                    "{{fixtures}}/eval_report.md",
                    "--training-material",
                    "{{drafts}}/培训材料.md",
                    "--accept",
                )
            ),
            contains=("Handoff package assembled",),
        ),
        MetricCheck(
            id="signoff-pass",
            gate="G7",
            ask="四件套齐 + 客户书面接受 → handoff_signoff passed=true",
            hint="门禁过了不等于客户打电话时活得——验收清单和退场计划是 G7 的人工部分。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "handoff_signoff", "--json")),
            path="passed",
            one_of=(True,),
        ),
        CommandCheck(
            id="advisory-recorded",
            gate="G7",
            ask="把 G7③ 适用边界 / G7④ 终止条件写进移交包",
            hint=(
                "③④ 只出 ⚠️、不阻塞——但它们是包里的字段，写了就查得到。"
                "注意这条命令把五件一次传齐：handoff 每次调用都是完整声明，"
                "证据路径（--eval-report / --training-material）不带就清空，"
                "而 ③④ 不带会从上一版保留——证据宁缺勿旧，叙述宁留勿删。"
            ),
            command=Command(
                argv=(
                    "handoff",
                    "{{eid}}",
                    "--eval-report",
                    "{{fixtures}}/eval_report.md",
                    "--training-material",
                    "{{drafts}}/培训材料.md",
                    "--boundary",
                    "只覆盖 6 个月内有线下 POS 流水的门店；新开店、加盟未回传数据、生鲜类目不在射程内",
                    "--termination",
                    "自动解决率连续两个 14d 窗口 <40% 即停用建议、回人工，由运维负责人判定",
                    "--accept",
                )
            ),
            contains=("boundary (G7③)", "termination (G7④)", "customer accepted: ✅"),
        ),
        MetricCheck(
            id="advisory-cleared",
            gate="G7",
            ask="写完 ③④ 之后 gate 的 warnings 归零（仍 passed=true）",
            hint="warning 不改退出码，所以「绿了但没人读警告」正是这条要钉住的差别。",
            command=Command(argv=("gate", "check", "{{eid}}", "--gate", "handoff_signoff", "--json")),
            path="warnings#len",
            one_of=(0,),
        ),
        ArtifactCheck(
            id="runbook-file",
            gate="G7",
            ask="工具生成的 Runbook 落盘：移交状态写着「客户接受 ✅」，SLO 表里有那条自动解决率",
            hint="这是工具生成的运维手册；D6 你自己写的五类事件 Runbook 是交付话术，两份都要交。",
            file="{{home}}/reports/runbook_{{eid}}.md",
            contains=("移交状态", "客户接受: ✅", "自动解决率"),
            min_bytes=800,
        ),
        CommandCheck(
            id="bad-category",
            gate="G7",
            ask="技能分类写错直接被拒（退出码 2），只有 4 个合法值",
            hint="CLI 的报错只说「见 --help」：合法值是 research / implementation / optimization / methodology。",
            command=Command(argv=("skill", "add", "--title", "临时", "--category", "现场处置"), exit_code=2),
            contains=("非法", "category"),
        ),
        CommandCheck(
            id="skill-add",
            gate="G7",
            ask="技能卡进库（草稿），id 由服务端生成：{{skill_id}}",
            hint="--body-file 读正文；id 不能自己指定（AGENTS.md 不变式 2），所以这条用 capture 抓回来。",
            command=Command(
                argv=(
                    "skill",
                    "add",
                    "--title",
                    "交接前必须补齐的三件事实",
                    "--category",
                    "methodology",
                    "--body-file",
                    "{{drafts}}/技能卡.md",
                    "--engagement",
                    "{{eid}}",
                ),
                capture=(("skill_id", r"草稿创建 (skill-[0-9a-f]{8})"),),
            ),
            contains=("草稿创建",),
        ),
        CommandCheck(
            id="skill-publish",
            gate="G7",
            ask="确认无误后发布：{{skill_id}} 变成 published",
            hint="发布是不可逆的（再发一次会报错，见下一条），所以先把「适用边界」写完。",
            command=Command(argv=("skill", "publish", "{{skill_id}}")),
            contains=("已发布",),
        ),
        CommandCheck(
            id="publish-twice",
            gate="G7",
            ask="重复发布被拒绝（只有草稿能发布）",
            hint="这条断言的是状态机：published 不能再 publish。写库纪律靠它兜底。",
            command=Command(argv=("skill", "publish", "{{skill_id}}"), exit_code=2),
            contains=("only drafts can be published",),
        ),
        CommandCheck(
            id="skill-show",
            gate="G7",
            ask="技能卡可被复查：标题 / 分类 / 状态 / 版本都在 skill show 里",
            hint="skill show 打印 v2 是因为发布时升了一次版本——版本号是证据的一部分。",
            command=Command(argv=("skill", "show", "{{skill_id}}"), read_only=True),
            contains=("methodology", "published", "交接前必须补齐的三件事实"),
        ),
        CommandCheck(
            id="skill-export",
            gate="G7",
            ask="导出成 AgentScope 格式（技能卡能被别的 runtime 消费）",
            hint="导出目录默认在数据根目录 .fde_scope/skills/export 下；--ontology 需要 fde-core schema 存在。",
            command=Command(
                argv=("skill", "export", "{{skill_id}}", "--format", "agentscope", "--out", "{{out}}/export")
            ),
            contains=("导出 1 个文件",),
        ),
        ArtifactCheck(
            id="技能卡",
            gate="G7",
            ask="技能卡写了「适用边界」——G7 明确要求这条",
            hint="没有适用边界的技能卡在下一个场景里就是误导；{{drafts}}/技能卡.md。",
            file="{{drafts}}/技能卡.md",
            not_contains=("TODO",),
            contains=("适用边界",),
            min_bytes=400,
        ),
        ArtifactCheck(
            id="验收清单",
            gate="G7",
            ask="验收清单有签字人",
            hint="逐条：谁验收 / 验收标准 / 签字人。没有名字的清单不是清单。",
            file="{{drafts}}/交接验收清单.md",
            not_contains=("TODO",),
            contains=("签字",),
        ),
        ArtifactCheck(
            id="培训材料",
            gate="G7",
            ask="培训材料（题纲即可）写完，且被 handoff 记进移交包",
            hint="handoff 只记路径不校验文件——所以这条由课程判，不由工具判。",
            file="{{drafts}}/培训材料.md",
            not_contains=("TODO",),
            min_bytes=300,
        ),
        ManualCheck(
            id="退场计划",
            gate="G7",
            ask="退场计划含 30/60 天支持安排与**终止条件**；技能卡有「场景→问题→做法→证据→适用边界」",
            rubric=(
                "终止条件现在在包里（handoff --termination），工具只查「有没有」——写「待定」也算有，"
                "所以能不能真的据此停手只能人判。30/60 天支持安排工具里根本没有字段，只能人判。"
                "答辩演练三问见 course-level-1/07。"
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# D8 · 变现日（G8）
# ---------------------------------------------------------------------------
D8 = Lab(
    day="D8",
    title="变现日 · 作品集与答辩",
    gate="G8（结业门）",
    deliverable="作品集三套包装（求职 / 汇报 / 接单）+ 结营答辩",
    eid="lab-d8",
    profile="ticket",
    setup=(_init("ticket"),),
    setup_hint="D8 检查的是「能否把这条链路讲成可交付的部署计划」，全程 --dry-run：不会真的起容器。",
    checks=(
        CommandCheck(
            id="corpus",
            gate="G8",
            ask="作品集里的证据文件可再生：语料报告重新产出",
            hint="答辩用的每个数字都要能当场重跑——这是「Demo 债」的反面。",
            command=Command(
                argv=(
                    "corpus",
                    "--input",
                    "{{shared}}/fixtures/sample_tickets.csv",
                    "--out",
                    "{{out}}/main/t.html",
                )
            ),
            contains=("Corpus forged",),
        ),
        CommandCheck(
            id="deploy-dry-run",
            gate="G8",
            ask="部署计划装好（dry-run）：沙箱 / 模型 / 权限三张清单都打印出来",
            hint="--tenant 换成你自己的租户名；dry-run 不启动任何容器。",
            command=Command(argv=("deploy", "--tenant", "lab-d8", "--dry-run")),
            contains=("Deployment plan assembled", "Permissions", "Sandbox: docker"),
        ),
        CommandCheck(
            id="deploy-with-corpus",
            gate="G8",
            ask="把语料报告接进部署：corpus_search / corpus_coverage 两个工具绑定成功",
            hint="--corpus 指向 corpus_report.json；--agent 的格式是 name:role[:model]。",
            command=Command(
                argv=(
                    "deploy",
                    "--tenant",
                    "lab-d8",
                    "--dry-run",
                    "--corpus",
                    "{{out}}/main/corpus_report.json",
                    "--agent",
                    "triage:工单分诊:qwen-max",
                )
            ),
            contains=("415 forged items (real=20, synthetic=395)", "category distribution + remaining gaps"),
        ),
        CommandCheck(
            id="deploy-bad-spec",
            gate="G8",
            ask="agent 规格写错会被拒绝（期望 name:role[:model]）",
            hint="这条是给「接单版」服务的：客户会照着你的命令敲，报错也要报得可修。",
            command=Command(
                argv=("deploy", "--tenant", "x", "--dry-run", "--agent", "bad-spec"), exit_code=2
            ),
            contains=("Invalid agent spec",),
        ),
        CommandCheck(
            id="flywheel-dry",
            gate="G8",
            ask="数据飞轮先 dry-run 看得见挂到哪个 agent",
            hint="飞轮是「上线之后怎么持续变好」——汇报版一页纸上要有这一栏。",
            command=Command(argv=("flywheel", "--agent", "lab-d8", "--dry-run")),
            contains=("DRY-RUN would attach flywheel",),
        ),
        CommandCheck(
            id="flywheel-jobs",
            gate="G8",
            ask="再评估节奏是明确的：周增量重训 + 月度全量评估（cron 可见）",
            hint="CLI 只打印任务描述符，不跑调度器；写进 SLO 卡时把 cron 表达式一起抄过去。",
            command=Command(argv=("flywheel", "--agent", "lab-d8")),
            contains=("weekly_incremental_retrain", "monthly_full_eval", "cron=0 2 * * 1"),
        ),
        CommandCheck(
            id="gate-map",
            gate="G8",
            ask="10 个工具门禁一目了然（通用 🏢 / 工业 🏭）",
            hint="作品集里写「过了哪些门禁」时，用 slug 而不是中文名字——招聘方会照着你写的命令去跑。",
            command=Command(argv=("gate", "list", "--profile", "manufacturing"), read_only=True),
            contains=("success_criteria", "handoff_signoff", "works_council", "air_gap"),
        ),
        ArtifactCheck(
            id="作品集索引",
            gate="G8",
            ask="作品集索引页：8 件产出都有「名称 / 日期 / 证据链接 / 一句话价值」",
            hint="求职 / 汇报 / 接单三套包装都从这一页派生——索引缺行，三套都站不住。",
            file="{{drafts}}/作品集索引.md",
            not_contains=("TODO",),
            contains=("证据",),
            min_bytes=800,
        ),
        ManualCheck(
            id="三套包装",
            gate="G8",
            ask="求职版（简历段落含数字 + STAR 故事 3 个）｜汇报版一页纸｜接单版服务清单 + 案例页",
            rubric="句式模板见 course-level-1/10。检查点：每个数字都有证据链接，每条「我做了」后面跟一句「数据显示」。",
        ),
        ManualCheck(
            id="结业门",
            gate="G8",
            ask="G1–G7 至少 6 关通过｜完成 10 分钟结营答辩｜等级已判定",
            rubric="用 `python -m fde_scope course all` 逐日核对机器项；跨日累计不在单条 lab 里判，所以这条是人（或全部 8 条机器分）来定。诚实标注为 0 一票否决。",
        ),
    ),
)


#: every lab the ``course`` command knows about, in the order a reader takes them
LABS: tuple[Lab, ...] = (D1, D2, D3, D4, D5, D6, D7, D8)

_BY_DAY = {lab.day: lab for lab in LABS}
_BY_EID = {lab.eid: lab for lab in LABS}


def lab_for(key: str) -> Lab:
    """Look a lab up by ``D5``, ``d5`` or the engagement id it creates.

    The engagement id is accepted as well because that is what a student sees in
    their own command history (``gate check lab-d5``), and mapping it back to a
    day is the difference between "the tool says pass" and "day 5 says pass".
    """
    lab = _BY_DAY.get(key.upper()) or _BY_EID.get(key)
    if lab is None:
        raise KeyError(f"unknown lab {key!r} — try one of {', '.join(_BY_DAY)}")
    return lab
