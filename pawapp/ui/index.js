/**
 * FDE Scope — frontend (runtime-loaded plugin module).
 *
 * Loaded by the QwenPaw host via usePluginLoader (same-origin Blob URL +
 * dynamic import). Self-registers a React route at /apps/fde-scope. React
 * and antd come from window.QwenPaw.host (no bundler in this context).
 *
 * Enterprise workbench (v0.2):
 * - compact header + left sidebar engagement list (selectable, progress bar)
 * - workspace: Progress + windowed Steps over the 18-phase SOP, current-phase
 *   card with gate summary and guided advance (force = Popconfirm)
 * - gates grid with per-gate re-check; blocked advances explain the next step
 * - tool tabs (forge / KPI / skills / deploy / handoff) with per-tab guidance
 */
(function () {
  var QwenPaw = window.QwenPaw;
  if (!QwenPaw || !QwenPaw.host || !QwenPaw.registerRoutes) {
    console.error("[fde-scope] window.QwenPaw not ready — cannot register.");
    return;
  }

  var host = QwenPaw.host;
  var React = host.React;
  var antd = host.antd;
  var h = React.createElement;
  var useState = React.useState;
  var useEffect = React.useEffect;

  var Alert = antd.Alert;
  var Button = antd.Button;
  var Card = antd.Card;
  var Empty = antd.Empty;
  var Input = antd.Input;
  var Modal = antd.Modal;
  var Popconfirm = antd.Popconfirm;
  var Progress = antd.Progress;
  var Select = antd.Select;
  var Space = antd.Space;
  var Statistic = antd.Statistic;
  var Steps = antd.Steps;
  var Tabs = antd.Tabs;
  var Tag = antd.Tag;
  var Tooltip = antd.Tooltip;
  var Typography = antd.Typography;
  var Upload = antd.Upload;
  var message = antd.message;

  var Text = Typography.Text;
  var Title = Typography.Title;

  var APP = "fde-scope";

  // semantic palette (GitHub-dark enterprise theme)
  var C = {
    ok: "#4ade80",
    warn: "#fbbf24",
    bad: "#f87171",
    muted: "#8b98a9",
    border: "#21262d",
    panel: "#161b22",
    accent: "#58a6ff",
  };

  var ZONE_LABEL = {
    pre_engagement: "A·Pre",
    build: "B·Build",
    operationalization: "C·Ops",
    handoff: "D·Handoff",
  };

  var ZONE_TIP = {
    pre_engagement: "Zone A · 售前阶段：接触客户、定义问题与成功标准",
    build: "Zone B · 构建阶段：语料锻造、技能沉淀、agent 装配",
    operationalization: "Zone C · 运营化阶段：部署 dry-run、灰度与 KPI 验证",
    handoff: "Zone D · 交接阶段：runbook、移交包与客户验收",
  };

  var ZONE_COLOR = {
    pre_engagement: "geekblue",
    build: "cyan",
    operationalization: "purple",
    handoff: "green",
  };

  var PROFILE_TIP =
    "交付模板：ticket=客服工单场景，manufacturing=制造/具身机器人场景。决定 18 阶段 SOP 中哪些阶段带 industrial 门禁与适用 gate。";
  var GATE_TIP =
    "Gate = 可执行合规检查。每次推进都会实时重跑当前阶段的全部 gate；任何一个 BLOCKED 都会拦截推进。";

  function api(path, opts) {
    // The host mounts PawApp routers under /api/<app_id> (PluginRegistry
    // contract) — NOT /<app_id>; the latter resolves to the SPA shell HTML.
    return fetch("/api/" + APP + path, opts).then(function (r) {
      if (!r.ok) {
        return r.text().then(function (t) {
          throw new Error(t || r.status);
        });
      }
      return r.json();
    });
  }

  function postForm(path, data) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(data).toString(),
    });
  }

  // -- small shared bits ------------------------------------------------------

  // Term: glossary word with dotted underline + tooltip
  function Term(props) {
    return h(
      Tooltip,
      { title: props.tip },
      h(
        "span",
        {
          style: {
            borderBottom: "1px dotted " + C.muted,
            cursor: "help",
          },
        },
        props.children
      )
    );
  }

  function zoneTag(zone) {
    return h(
      Tooltip,
      { title: ZONE_TIP[zone] || zone },
      h(Tag, { color: ZONE_COLOR[zone] || "default", style: { marginInlineEnd: 0 } }, ZONE_LABEL[zone] || zone)
    );
  }

  function profileTag(profile) {
    return h(
      Tooltip,
      { title: PROFILE_TIP },
      h(Tag, { color: profile === "manufacturing" ? "orange" : "cyan", style: { marginInlineEnd: 0 } }, profile)
    );
  }

  // Guide: one-line "what is this / what to do next" banner for each panel
  function Guide(props) {
    return h(Alert, {
      type: "info",
      showIcon: true,
      message: h("span", { style: { fontSize: 12 } }, props.children),
      style: { marginBottom: 12, padding: "6px 12px" },
    });
  }

  function gateSummary(gates) {
    var entries = Object.entries(gates || {});
    var passed = entries.filter(function (kv) { return kv[1].passed; }).length;
    return { total: entries.length, passed: passed };
  }

  // -- corpus forge panel ---------------------------------------------------
  function ForgePanel() {
    var _file = useState(null);
    var file = _file[0];
    var setFile = _file[1];
    var _running = useState(false);
    var running = _running[0];
    var setRunning = _running[1];
    var _result = useState(null);
    var result = _result[0];
    var setResult = _result[1];

    function forge() {
      if (!file) {
        message.warning("请先选择 CSV 文件");
        return;
      }
      var fd = new FormData();
      fd.append("file", file);
      fd.append("min_samples", "5");
      fd.append("synth_per_gap", "3");
      setRunning(true);
      api("/forge", { method: "POST", body: fd })
        .then(function (r) {
          setResult(r);
          message.success("语料锻造完成");
        })
        .catch(function (e) {
          message.error("锻造失败: " + (e.message || e));
        })
        .then(function () {
          setRunning(false);
        });
    }

    return h(Card, { size: "small" },
      h(Guide, null,
        "把客户现场导出的原始 CSV 锻造成训练语料：去 PII、丢脏行、对覆盖不足的类别自动补合成样本。",
        "上传一份真实数据 → 点「锻造语料」→ 看 real/synthetic/缺口分布。"
      ),
      h(Space, { wrap: true },
        h(Upload, {
          accept: ".csv",
          maxCount: 1,
          beforeUpload: function (f) {
            setFile(f);
            return false;
          },
        }, h(Button, null, file ? "重新选择 CSV（已选: " + file.name + "）" : "① 选择 CSV")),
        h(Tooltip, { title: "运行锻造管线：min_samples=5，每个缺口类别补 3 条合成样本" },
          h(Button, { type: "primary", loading: running, onClick: forge }, running ? "锻造中…" : "② 锻造语料")
        ),
        h("span", { style: { fontSize: 12, color: C.muted } }, "配置 FDE_SCOPE_MIMO_API_KEY 时自动启用 LLM 合成")
      ),
      result &&
        h("div", { style: { marginTop: 14 } },
          h(Space, { size: 24, wrap: true },
            h(Statistic, { title: "total", value: result.total }),
            h(Statistic, { title: "real", value: result.real, valueStyle: { color: C.ok } }),
            h(Statistic, { title: "synthetic", value: result.synthetic, valueStyle: { color: "#2dd4bf" } }),
            h(Statistic, { title: "dropped", value: result.dropped, valueStyle: result.dropped ? { color: C.warn } : undefined }),
            h(Statistic, { title: "PII masked", value: result.pii_masked })
          ),
          h("div", { style: { marginTop: 8, fontSize: 12, color: C.muted } },
            "覆盖缺口: " +
              ((result.gaps || []).map(function (g) { return g.category + "(" + g.current_count + ")"; }).join(", ") || "无") +
              " · report_id: " + result.report_id
          )
        )
    );
  }

  // -- KPI panel ------------------------------------------------------------
  function KpiPanel() {
    var _file = useState(null);
    var file = _file[0];
    var setFile = _file[1];
    var _profile = useState("manufacturing");
    var profile = _profile[0];
    var setProfile = _profile[1];
    var _result = useState(null);
    var result = _result[0];
    var setResult = _result[1];
    var _running = useState(false);
    var running = _running[0];
    var setRunning = _running[1];

    function run() {
      if (!file) {
        message.warning("请先选择 JSONL 样本文件");
        return;
      }
      var fd = new FormData();
      fd.append("file", file);
      fd.append("profile", profile);
      setRunning(true);
      api("/kpi", { method: "POST", body: fd })
        .then(setResult)
        .catch(function (e) {
          message.error(String(e.message || e));
        })
        .then(function () {
          setRunning(false);
        });
    }

    return h(Card, { size: "small" },
      h(Guide, null,
        "用一份 JSONL 样本快速验证业务指标是否可计算（Zone C 的 KPI gate 之前先自查）。",
        "选择与 engagement 一致的 ", h(Term, { tip: PROFILE_TIP }, "profile"), "，上传样本 → 点「计算 KPI」。"
      ),
      h(Space, { wrap: true },
        h(Tooltip, { title: PROFILE_TIP },
          h(Select, {
            value: profile,
            style: { width: 220 },
            onChange: setProfile,
            options: [
              { value: "manufacturing", label: "manufacturing · OEE/MTBF/抓取率" },
              { value: "ticket", label: "ticket · 客服指标" },
            ],
          })
        ),
        h(Upload, {
          accept: ".jsonl,.json",
          maxCount: 1,
          beforeUpload: function (f) {
            setFile(f);
            return false;
          },
        }, h(Button, null, file ? "已选: " + file.name : "选择样本 JSONL")),
        h(Button, { type: "primary", loading: running, onClick: run }, running ? "计算中…" : "计算 KPI")
      ),
      result &&
        h("div", { style: { marginTop: 14 } },
          h(Space, { size: 24, wrap: true },
            Object.entries(result.kpis).map(function (kv) {
              var v = kv[1];
              return h(Statistic, {
                key: kv[0],
                title: kv[0],
                value: typeof v === "number" ? +v.toFixed(4) : v,
              });
            })
          ),
          h("div", { style: { marginTop: 8, fontSize: 12, color: C.muted } },
            "samples: " + result.sample_count + " · profile: " + result.profile
          )
        )
    );
  }

  // -- skills panel -----------------------------------------------------------
  function SkillsPanel() {
    var _list = useState([]);
    var skills = _list[0];
    var setSkills = _list[1];
    var _drafts = useState([]);
    var drafts = _drafts[0];
    var setDrafts = _drafts[1];

    function load() {
      api("/skills?status=published").then(setSkills).catch(function () {});
      api("/skills/drafts").then(setDrafts).catch(function () {});
    }
    useEffect(function () {
      load();
    }, []);

    function publish(sid) {
      api("/skills/" + sid + "/publish", { method: "POST" })
        .then(function () {
          message.success("已发布");
          load();
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        });
    }

    function doExport(sid) {
      postForm("/skills/" + sid + "/export", { fmt: "qwenpaw" })
        .then(function (r) {
          Modal.info({
            title: "QwenPaw SKILL.md 导出",
            width: 640,
            content: h("pre", { style: { fontSize: 11, overflow: "auto", maxHeight: 400 } },
              r.files.map(function (f) {
                return "── " + f.name + " ──\n" + f.content + "\n";
              }).join("\n")
            ),
          });
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        });
    }

    function skillCard(r, isDraft) {
      return h(Card, {
          key: r.id,
          size: "small",
          style: { marginBottom: 8, borderColor: isDraft ? "rgba(251,191,36,0.4)" : undefined },
        },
        h("div", { style: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" } },
          h("b", null, r.title),
          h(Tag, null, r.category),
          isDraft && h(Tag, { color: "orange" }, r.source || "draft"),
          h("div", { style: { marginLeft: "auto" } },
            isDraft &&
              h(Popconfirm, {
                title: "发布这个技能草稿？",
                description: "发布后进入技能库，可被后续 engagement 复用。",
                okText: "发布",
                cancelText: "取消",
                onConfirm: function () { publish(r.id); },
              }, h(Button, { size: "small", type: "primary" }, "发布")),
            " ",
            h(Button, { size: "small", onClick: function () { doExport(r.id); } }, "导出 QwenPaw")
          )
        ),
        h("div", { style: { fontSize: 12, color: C.muted, marginTop: 4 } },
          r.id + (r.source_engagement ? " · 来自 " + r.source_engagement : "")
        )
      );
    }

    return h("div", null,
      h(Guide, null,
        "技能库 = 现场经验的复用飞轮：engagement 中沉淀的草稿在这里审阅、发布，发布后可导出为 QwenPaw SKILL.md。"
      ),
      h("div", { style: { fontWeight: 600, marginBottom: 8, fontSize: 13 } },
        "草稿审阅队列 ",
        drafts.length ? h(Tag, { color: "orange" }, drafts.length + " 待审") : null
      ),
      drafts.length
        ? drafts.map(function (r) { return skillCard(r, true); })
        : h(Empty, {
            image: Empty.PRESENTED_IMAGE_SIMPLE,
            description: "无待审草稿 — engagement 交付中产生的技能草稿会出现在这里",
          }),
      h("div", { style: { fontWeight: 600, margin: "14px 0 8px", fontSize: 13 } }, "已发布技能"),
      skills.length
        ? skills.map(function (r) { return skillCard(r, false); })
        : h(Empty, {
            image: Empty.PRESENTED_IMAGE_SIMPLE,
            description: "还没有沉淀 — 把现场经验变成可复用技能",
          })
    );
  }

  // -- SOP pipeline (compact full-view chips) -------------------------------
  function SopPipeline(props) {
    var phases = props.phases || [];
    var current = props.current;
    var idx = 0;
    for (var i = 0; i < phases.length; i++) {
      if (phases[i].slug === current) {
        idx = i;
        break;
      }
    }
    return h(
      "div",
      { style: { display: "flex", flexWrap: "wrap", gap: 4 } },
      phases.map(function (p, i) {
        var done = i < idx;
        var isCur = i === idx;
        return h(
          Tooltip,
          {
            key: p.slug,
            title:
              p.index + ". " + p.name + " — " + (ZONE_TIP[p.zone] || p.zone) +
              (p.gates && p.gates.length ? " · 🚦 " + p.gates.length + " 个 gate" : "") +
              (p.industrial ? " · 🏭 industrial" : ""),
          },
          h(
            "span",
            {
              style: {
                display: "inline-block",
                padding: "2px 8px",
                borderRadius: 8,
                fontSize: 11,
                border: isCur ? "1px solid " + C.accent : "1px solid " + C.border,
                background: isCur ? "rgba(88,166,255,0.15)" : done ? "rgba(74,222,128,0.08)" : "transparent",
                color: done ? C.muted : "#e6edf3",
                textDecoration: done ? "line-through" : "none",
                cursor: "default",
              },
            },
            p.index + ". " + p.name + (p.gates && p.gates.length ? " 🚦" : "")
          )
        );
      })
    );
  }

  // WindowedSteps: horizontal antd Steps around the current phase (18 phases
  // don't fit horizontally — show a ±3 window plus overall Progress instead).
  function WindowedSteps(props) {
    var phases = props.phases || [];
    var current = props.current;
    var idx = 0;
    for (var i = 0; i < phases.length; i++) {
      if (phases[i].slug === current) {
        idx = i;
        break;
      }
    }
    var from = Math.max(0, idx - 3);
    var to = Math.min(phases.length, idx + 4);
    var items = [];
    for (var j = from; j < to; j++) {
      var p = phases[j];
      items.push({
        title: h("span", { style: { fontSize: 12 } }, p.index + ". " + p.name),
        status: j < idx ? "finish" : j === idx ? "process" : "wait",
        description: j === idx ? (ZONE_LABEL[p.zone] || p.zone) : undefined,
      });
    }
    return h("div", null,
      from > 0 || to < phases.length
        ? h("div", { style: { fontSize: 11, color: C.muted, marginBottom: 4 } },
            "显示第 " + (from + 1) + "–" + to + " 阶段 / 共 " + phases.length + " 阶段（全览见下方阶段条）")
        : null,
      h(Steps, { size: "small", items: items })
    );
  }

  // -- gates panel --------------------------------------------------------
  function GatesPanel(props) {
    var eid = props.eid;
    var gates = props.gates || {};
    var entries = Object.entries(gates);
    if (!entries.length) {
      return h(Empty, {
        image: Empty.PRESENTED_IMAGE_SIMPLE,
        description: "当前 profile 无适用 gate — 可以直接推进",
      });
    }
    return h(
      "div",
      { style: { display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))" } },
      entries.map(function (kv) {
        var slug = kv[0];
        var g = kv[1];
        return h(
          Card,
          { key: slug, size: "small", style: { borderColor: g.passed ? "rgba(74,222,128,0.4)" : "rgba(248,113,113,0.4)" } },
          h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
            h("b", { style: { fontSize: 13 } }, g.name),
            h(Tag, { color: g.passed ? "green" : "red", style: { marginInlineEnd: 0 } }, g.passed ? "PASS" : "BLOCKED")
          ),
          (g.blockers.length || g.warnings.length)
            ? h(
                "ul",
                { style: { margin: "6px 0 0", paddingLeft: 18, fontSize: 12, color: C.muted } },
                g.blockers.map(function (b) {
                  return h("li", { key: b, style: { color: C.bad } }, "🚫 " + b);
                }),
                g.warnings.map(function (w) {
                  return h("li", { key: w, style: { color: C.warn } }, "⚠️ " + w);
                })
              )
            : h("div", { style: { marginTop: 6, fontSize: 12, color: C.ok } }, "✓ 全部检查项通过"),
          h(Tooltip, { title: "重新运行该 gate 的检查逻辑（例如补齐材料后再试）" },
            h(Button, {
              size: "small",
              style: { marginTop: 8 },
              onClick: function () {
                api("/engagements/" + eid + "/gate/" + slug, { method: "POST" })
                  .then(function () {
                    message.success(slug + " 重新校验完成");
                    props.refresh();
                  })
                  .catch(function (e) {
                    message.error(String(e.message || e));
                  });
              },
            }, "重新校验")
          )
        );
      })
    );
  }

  // -- handoff panel ---------------------------------------------------------
  function HandoffPanel(props) {
    var eid = props.eid;
    var _drafting = useState(false);
    var drafting = _drafting[0];
    var setDrafting = _drafting[1];
    var _packing = useState(false);
    var packing = _packing[0];
    var setPacking = _packing[1];
    var _last = useState(null);
    var last = _last[0];
    var setLast = _last[1];

    if (!eid) {
      return h(Empty, {
        image: Empty.PRESENTED_IMAGE_SIMPLE,
        description: "交接是针对具体 engagement 的 — 请先在左侧列表选择一个 engagement",
      });
    }

    function draft() {
      setDrafting(true);
      api("/handoff/" + eid + "/runbook", { method: "POST" })
        .then(function (r) {
          setLast(r);
          message.success(r.used_llm ? "🤖 Runbook 已由宿主 LLM 起草" : "Runbook 由模板生成（LLM 不可用）");
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        })
        .then(function () {
          setDrafting(false);
        });
    }

    function pack(accept) {
      setPacking(true);
      postForm("/handoff/" + eid, { accept: accept ? "true" : "false" })
        .then(function (r) {
          Modal.success({
            title: "移交包已组装",
            width: 560,
            content: h("pre", { style: { fontSize: 11, overflow: "auto", maxHeight: 360 } }, JSON.stringify(r, null, 2)),
          });
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        })
        .then(function () {
          setPacking(false);
        });
    }

    return h(Card, { size: "small" },
      h(Guide, null,
        "Zone D 交接两步走：① 用宿主 LLM 起草 runbook（失败自动回退模板，如实标注来源）→ ② 组装移交包。",
        "客户确认后再用「组装并标记客户已验收」。"
      ),
      h(Space, { wrap: true },
        h(Button, { type: "primary", loading: drafting, onClick: draft }, drafting ? "起草中…" : "🤖 ① LLM 起草 Runbook"),
        h(Button, { loading: packing, onClick: function () { pack(false); } }, "📦 ② 组装移交包"),
        h(Popconfirm, {
          title: "确认客户已验收？",
          description: "会在移交包中写入 accept=true，作为交付完成记录。",
          okText: "已验收",
          cancelText: "取消",
          onConfirm: function () { pack(true); },
        }, h(Button, { loading: packing }, "✅ 组装并标记客户已验收"))
      ),
      last &&
        h("div", { style: { marginTop: 10, fontSize: 12, color: C.muted } },
          "上次起草: " + last.path + (last.used_llm ? " · 🤖 LLM" : " · 模板回退")
        )
    );
  }

  // -- deploy plan panel ----------------------------------------------------
  function DeployPanel() {
    var _tenant = useState("acme");
    var tenant = _tenant[0];
    var setTenant = _tenant[1];
    var _profile = useState("ticket");
    var profile = _profile[0];
    var setProfile = _profile[1];
    var _mode = useState("balanced");
    var mode = _mode[0];
    var setMode = _mode[1];
    var _model = useState("qwen-max");
    var model = _model[0];
    var setModel = _model[1];
    var _agents = useState("数据员:数据分析\n日志员:日志分析:qwen3-14b");
    var agents = _agents[0];
    var setAgents = _agents[1];
    var _sources = useState("csv=examples/quickstart_csv/sample_tickets.csv");
    var sources = _sources[0];
    var setSources = _sources[1];
    var _plan = useState(null);
    var plan = _plan[0];
    var setPlan = _plan[1];
    var _running = useState(false);
    var running = _running[0];
    var setRunning = _running[1];
    var _err = useState(null);
    var err = _err[0];
    var setErr = _err[1];

    function parseAgents(text) {
      return text
        .split("\n")
        .map(function (s) { return s.trim(); })
        .filter(Boolean)
        .map(function (line) {
          var parts = line.split(":").map(function (s) { return s.trim(); });
          var a = { name: parts[0], role: parts[1] || "" };
          if (parts[2]) a.model = parts[2];
          return a;
        })
        .filter(function (a) { return a.name && a.role; });
    }

    function parseSources(text) {
      var out = {};
      text.split("\n").map(function (s) { return s.trim(); }).filter(Boolean).forEach(function (line) {
        var i = line.indexOf("=");
        if (i > 0) out[line.slice(0, i).trim()] = line.slice(i + 1).trim();
      });
      return out;
    }

    function run() {
      setRunning(true);
      setErr(null);
      api("/deploy/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant: tenant.trim() || "acme",
          profile: profile,
          approval_mode: mode,
          model: model.trim() || "qwen-max",
          agents: parseAgents(agents),
          sources: parseSources(sources),
        }),
      })
        .then(function (r) {
          setPlan(r);
          message.success("部署计划已生成（dry-run）");
        })
        .catch(function (e) {
          setPlan(null);
          setErr(String(e.message || e));
        })
        .then(function () {
          setRunning(false);
        });
    }

    var muted = { fontSize: 12, color: C.muted };

    function agentCard(a) {
      var tools = (a.tools || []).map(function (t) {
        return t.bound
          ? h(Tag, { color: "green", key: t.tool, title: t.note || "" }, t.tool + " → " + (t.source || ""))
          : h(Tag, { color: "red", key: t.tool, title: t.note || "" }, t.tool + " ✕");
      });
      var unbound = (a.unbound || []).length;
      return h(Card, { size: "small", key: a.name + a.role, style: { marginBottom: 8 } },
        h("div", { style: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" } },
          h("b", null, a.name),
          h(Tooltip, {
            title: a.role_bucket === "corpus"
              ? "corpus-only：角色没匹配上任何连接器工具桶，只拿到语料检索工具"
              : "已归入工具桶，自动绑定对应连接器工具",
          },
            h(Tag, { color: a.role_bucket === "corpus" ? "orange" : "cyan" }, a.role + " · " + (a.role_bucket || "corpus-only"))
          ),
          h(Tag, null, a.model || "runtime 注入"),
          h("span", { style: { marginLeft: "auto" } },
            h("span", { style: muted }, "bound " + (a.bound || []).length + " · unbound " + unbound)
          )
        ),
        h("div", { style: { marginTop: 4 } }, tools.length ? tools : h("span", { style: muted }, "仅语料工具")),
        unbound
          ? h("div", { style: { marginTop: 4, fontSize: 12, color: C.warn } },
              "⚠ " + unbound + " 个工具未绑定 — 在「数据源」里给对应连接器配 slug=源 即可绑定")
          : null
      );
    }

    var m = plan && plan.manifest;
    var sum = plan && plan.summary;
    var perm = m && m.permissions;
    var ruleLine = function (label, rules) {
      return h("div", { style: muted },
        label + "：" +
        ((rules || []).map(function (r) { return r[0] + (r[1] ? " (" + r[1] + ")" : ""); }).join(" · ") || "—"));
    };

    return h("div", null,
      h(Card, { size: "small", title: h(Tooltip, { title: "dry-run：只生成部署清单做预览，不 import AgentScope、不调模型、不真正部署" },
          h("span", null, "Agent 部署计划 · dry-run")) },
        h(Guide, null,
          "与 CLI deploy / Web 控制台走同一 build_deploy_plan：纯数据预览「哪个角色 Agent 拿到哪个连接器工具、对着哪个数据源」。",
          "填好 Agents 和数据源 → 点「生成部署计划」→ 检查是否有 unbound 工具。"
        ),
        h("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 } },
          h("div", null,
            h("div", { style: muted }, "Tenant（租户标识）"),
            h(Input, { value: tenant, placeholder: "如 acme", onChange: function (e) { setTenant(e.target.value); } })),
          h("div", null,
            h("div", { style: muted }, "模型"),
            h(Input, { value: model, placeholder: "如 qwen-max", onChange: function (e) { setModel(e.target.value); } })),
          h("div", null,
            h("div", { style: muted }, h(Term, { tip: PROFILE_TIP }, "Profile")),
            h(Select, { value: profile, style: { width: "100%" }, onChange: setProfile, options: [
              { value: "ticket", label: "ticket / 客服" },
              { value: "manufacturing", label: "manufacturing / 制造业" },
            ] })),
          h("div", null,
            h("div", { style: muted },
              h(Term, { tip: "审批模式决定未匹配工具的命运：conservative/balanced → ASK（人工确认），autonomous → DENY" }, "审批模式")),
            h(Select, { value: mode, style: { width: "100%" }, onChange: setMode, options: [
              { value: "conservative", label: "conservative · 例行外呼也 ASK" },
              { value: "balanced", label: "balanced · 仅高风险 ASK" },
              { value: "autonomous", label: "autonomous · 未匹配 DENY" },
            ] }))
        ),
        h("div", { style: { marginTop: 10 } },
          h("div", { style: { fontSize: 12, color: "#c9d1d9", marginBottom: 2 } },
            "Agents — 每行一个：", h("code", null, "名字:角色[:模型]"),
            h("span", { style: { color: C.muted } }, "（角色是自由文本 → 自动归 数据/日志/文件 工具桶；匹配不上 → corpus-only）")
          ),
          h(Input.TextArea, {
            rows: 3,
            value: agents,
            placeholder: "数据员:数据分析\n日志员:日志分析:qwen3-14b",
            onChange: function (e) { setAgents(e.target.value); },
          })
        ),
        h("div", { style: { marginTop: 8 } },
          h("div", { style: { fontSize: 12, color: "#c9d1d9", marginBottom: 2 } },
            "数据源 — 每行一个：", h("code", null, "slug=路径或URL"),
            h("span", { style: { color: C.muted } }, "（连接器工具按 slug 绑定到具体数据源）")
          ),
          h(Input.TextArea, {
            rows: 2,
            value: sources,
            placeholder: "csv=examples/quickstart_csv/sample_tickets.csv",
            onChange: function (e) { setSources(e.target.value); },
          })
        ),
        h("div", { style: { marginTop: 12 } },
          h(Button, { type: "primary", loading: running, onClick: run }, running ? "生成中…" : "生成部署计划（dry-run）")
        )
      ),
      err && h(Alert, { type: "error", showIcon: true, style: { marginTop: 10 },
        message: "校验失败（422）",
        description: h("pre", { style: { fontSize: 11, whiteSpace: "pre-wrap", margin: 0 } }, err) }),
      m && h("div", { style: { marginTop: 10 } },
        h(Space, { size: 24, wrap: true },
          h(Statistic, { title: "Agents", value: sum ? sum.agents : m.agents.length }),
          h(Statistic, { title: "Bound 工具", value: sum ? sum.bound_tools.length : 0, valueStyle: { color: C.ok } }),
          h(Statistic, {
            title: "Unbound 工具",
            value: sum ? sum.unbound_tools.length : 0,
            valueStyle: { color: sum && sum.unbound_tools.length ? C.warn : undefined },
          }),
          h(Statistic, { title: "Sandbox", value: (m.sandbox || {}).backend || "—", valueStyle: { fontSize: 16 } })
        ),
        h("div", { style: { marginTop: 10 } }, m.agents.map(agentCard)),
        perm && h(Card, { size: "small", title: "权限规则（" + ((m.approval_policy || {}).mode || "—") + "）" },
          ruleLine("ALLOW", perm.allow),
          ruleLine("DENY", perm.deny),
          ruleLine("ASK", perm.ask))
      ),
      h(Card, { size: "small", title: "注意事项", style: { marginTop: 10 } },
        h("ul", { style: Object.assign({ margin: 0, paddingLeft: 18, lineHeight: 1.8 }, muted) },
          h("li", null, "数据源优先级：Agent 级 toolkit.sources → tenant sources → 隐式字段（ticket 下 ticket_api 隐式喂 zammad/salesforce）；三处都没配的工具诚实标注 unbound，不进 Toolkit。"),
          h("li", null, "审批模式决定未匹配工具命运：绑定工具自动 ALLOW；conservative/balanced 未匹配 → ASK（HITL），autonomous → DENY。deny 恒含 access_other_tenant / delete_any / exec_shell。"),
          h("li", null, "skills_dirs 必须真实存在（含 SKILL.md），技能经 Toolkit(skills_or_loaders=…) 注册。"),
          h("li", null, "凭据只走环境变量（FDE_SCOPE_MIMO_API_KEY 等），不进 manifest / tenant_config。"),
          h("li", null, "连接器 sample 每调用最多 50 行（MAX_TOOL_ROWS），是预览不是导出通道。"),
          h("li", null, "装配 ≠ 服务：--serve 需 .[agentscope] extra + Redis + 可达模型；2.0 无 Agent.stop，停服用 TenantDeployer.stop()。")
        ))
    );
  }

  // -- engagement sidebar item ------------------------------------------------
  function EngagementItem(props) {
    var e = props.eng;
    var active = props.active;
    var pct = props.progress; // 0-100 or null
    return h(
      "div",
      {
        onClick: props.onClick,
        style: {
          padding: "8px 10px",
          marginBottom: 6,
          borderRadius: 6,
          cursor: "pointer",
          border: active ? "1px solid " + C.accent : "1px solid " + C.border,
          background: active ? "rgba(88,166,255,0.12)" : "transparent",
        },
      },
      h("div", { style: { display: "flex", alignItems: "center", gap: 6 } },
        h("b", { style: { fontSize: 13, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, e.customer),
        e.is_complete ? h(Tag, { color: "green", style: { marginInlineEnd: 0 } }, "完成") : null
      ),
      h("div", { style: { display: "flex", alignItems: "center", gap: 4, marginTop: 4, flexWrap: "wrap" } },
        profileTag(e.profile),
        zoneTag(e.current_zone),
        h("span", { style: { fontSize: 11, color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } },
          e.current_phase)
      ),
      pct != null
        ? h(Progress, { percent: pct, size: "small", showInfo: false, style: { marginTop: 4, marginBottom: 0 } })
        : null
    );
  }

  // -- main page ----------------------------------------------------------
  function FdeScopePage() {
    var _list = useState([]);
    var engagements = _list[0];
    var setEngagements = _list[1];
    var _sel = useState(null);
    var selected = _sel[0];
    var setSelected = _sel[1];
    var _detail = useState(null);
    var detail = _detail[0];
    var setDetail = _detail[1];
    var _phases = useState([]);
    var phases = _phases[0];
    var setPhases = _phases[1];
    var _gates = useState({});
    var gates = _gates[0];
    var setGates = _gates[1];
    var _creating = useState(false);
    var creating = _creating[0];
    var setCreating = _creating[1];
    var _form = useState({ customer: "", profile: "ticket" });
    var form = _form[0];
    var setForm = _form[1];
    var _advancing = useState(false);
    var advancing = _advancing[0];
    var setAdvancing = _advancing[1];
    // phase slug lists per profile, for sidebar mini progress bars
    var _pmap = useState({});
    var phaseMap = _pmap[0];
    var setPhaseMap = _pmap[1];

    function load() {
      api("/engagements").then(setEngagements).catch(function (e) {
        message.error("加载 engagements 失败: " + e);
      });
    }

    function select(eid) {
      setSelected(eid);
      Promise.all([
        api("/engagements/" + eid),
        api("/engagements/" + eid + "/gates"),
      ])
        .then(function (res) {
          setDetail(res[0]);
          setGates(res[1]);
          return api("/phases?profile=" + res[0].profile);
        })
        .then(function (p) {
          setPhases(p.phases || []);
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        });
    }

    useEffect(function () {
      load();
      // pre-fetch phase lists for both profiles (sidebar progress bars)
      ["ticket", "manufacturing"].forEach(function (prof) {
        api("/phases?profile=" + prof)
          .then(function (p) {
            setPhaseMap(function (prev) {
              var next = Object.assign({}, prev);
              next[prof] = (p.phases || []).map(function (x) { return x.slug; });
              return next;
            });
          })
          .catch(function () {});
      });
    }, []);

    function sidebarProgress(e) {
      var slugs = phaseMap[e.profile];
      if (!slugs || !slugs.length) return null;
      var idx = slugs.indexOf(e.current_phase);
      if (idx < 0) return null;
      return Math.round(((idx + 1) / slugs.length) * 100);
    }

    function advance(force) {
      setAdvancing(true);
      api("/engagements/" + selected + "/advance?force=" + force, { method: "POST" })
        .then(function (r) {
          if (!r.advanced) {
            if (r.reason === "complete") {
              message.info("已完成全部阶段 🎉 — 可以去「交接」组装移交包了");
            } else {
              Modal.warning({
                title: "推进被 gate 拦截",
                width: 520,
                content: h("div", null,
                  h("div", { style: { marginBottom: 8, color: C.muted, fontSize: 13 } },
                    "以下 blocker 必须解决后才能推进（gate 会在每次推进时实时重跑）："),
                  h("ul", { style: { paddingLeft: 18, margin: "0 0 8px", color: C.bad, fontSize: 13 } },
                    (r.result.blockers || []).map(function (b) {
                      return h("li", { key: b }, b);
                    })),
                  h("div", { style: { fontSize: 12, color: C.muted } },
                    "👉 到下方「Gates」面板逐条处理并用「重新校验」确认；确需绕过可用「Force 推进」（会留下审计记录）。")
                ),
              });
            }
          } else {
            message.success("已推进到 " + r.status.current_phase);
          }
          select(selected);
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        })
        .then(function () {
          setAdvancing(false);
        });
    }

    function create() {
      if (!form.customer.trim()) {
        message.warning("请填写客户名");
        return;
      }
      postForm("/engagements", { customer: form.customer, profile: form.profile })
        .then(function () {
          setCreating(false);
          setForm({ customer: "", profile: "ticket" });
          message.success("Engagement 已创建 — 在左侧列表选择它开始交付");
          load();
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        });
    }

    // progress of the selected engagement (over its full phase list)
    var progress = 0;
    if (detail && phases.length) {
      for (var i = 0; i < phases.length; i++) {
        if (phases[i].slug === detail.current_phase) {
          progress = Math.round(((i + 1) / phases.length) * 100);
          break;
        }
      }
    }

    var gs = gateSummary(gates);

    function tabLabel(text, tip) {
      return h(Tooltip, { title: tip, placement: "top" }, h("span", null, text));
    }

    // -- workspace for the selected engagement
    var workspace;
    if (!detail) {
      workspace = h(Card, { size: "small" },
        h(Empty, {
          description: engagements.length
            ? "从左侧列表选择一个 engagement 查看 SOP 进度与 gate 状态"
            : "还没有 engagement — 点击右上角「+ 新建 Engagement」开始第一个交付",
        })
      );
    } else {
      workspace = h("div", null,
        h(Card, {
          size: "small",
          style: { marginBottom: 12 },
          title: h(Space, { size: 8, wrap: true },
            h("span", null, detail.customer),
            profileTag(detail.profile),
            zoneTag(detail.current_zone),
            detail.is_complete ? h(Tag, { color: "green" }, "已完成") : null
          ),
          extra: h(Space, { size: 8 },
            h(Tooltip, { title: "重新拉取状态与 gate 结果" },
              h(Button, { size: "small", onClick: function () { select(detail.engagement_id); } }, "刷新")),
            h(Tooltip, { title: GATE_TIP },
              h(Button, {
                size: "small",
                type: "primary",
                loading: advancing,
                disabled: detail.is_complete,
                onClick: function () { advance(false); },
              }, "推进到下一阶段（gate 校验）")
            ),
            h(Popconfirm, {
              title: "Force 推进将绕过 gate 校验",
              description: "当前阶段未通过的 gate 会被跳过并记录。仅在你确认风险可接受时使用。",
              okText: "确认 force 推进",
              cancelText: "取消",
              okButtonProps: { danger: true },
              onConfirm: function () { advance(true); },
            },
              h(Button, { size: "small", danger: true, disabled: detail.is_complete }, "Force 推进")
            )
          ),
        },
          h("div", { style: { display: "flex", alignItems: "center", gap: 12, marginBottom: 8, flexWrap: "wrap" } },
            h("div", { style: { flex: 1, minWidth: 200 } },
              h(Progress, { percent: progress, size: "small" })
            ),
            h(Tooltip, { title: GATE_TIP },
              h("span", { style: { fontSize: 12, color: gs.total && gs.passed < gs.total ? C.warn : C.ok } },
                "🚦 gate " + gs.passed + "/" + gs.total + " 通过")
            ),
            h("span", { style: { fontSize: 12, color: C.muted } }, "当前阶段: " + detail.current_phase)
          ),
          h(WindowedSteps, { phases: phases, current: detail.current_phase }),
          h("div", { style: { marginTop: 10 } },
            h(SopPipeline, { phases: phases, current: detail.current_phase })
          )
        ),
        h(Card, {
          size: "small",
          style: { marginBottom: 12 },
          title: h(Tooltip, { title: GATE_TIP }, h("span", null, "Gates · 可执行合规检查")),
          extra: h("span", { style: { fontSize: 12, color: C.muted } },
            "处理 blocker 后点卡片上的「重新校验」"),
        },
          h(GatesPanel, { eid: detail.engagement_id, gates: gates, refresh: function () { select(detail.engagement_id); } })
        )
      );
    }

    return h(
      "div",
      { style: { padding: 12, maxWidth: 1400, margin: "0 auto" } },
      // compact header
      h("div", { style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 12 } },
        h(Title, { level: 4, style: { margin: 0 } }, "🛠️ FDE Scope"),
        h(Text, { type: "secondary", style: { fontSize: 12 } },
          "18 阶段交付 SOP · 可执行 gate · 72h raw data → deployed agent"),
        h("div", { style: { marginLeft: "auto" } },
          h(Button, { type: "primary", onClick: function () { setCreating(true); } }, "+ 新建 Engagement")
        )
      ),
      // sidebar + workspace
      h("div", { style: { display: "flex", gap: 12, alignItems: "flex-start" } },
        h("div", { style: { width: 300, flexShrink: 0 } },
          h(Card, {
            size: "small",
            title: "Engagements" + (engagements.length ? " (" + engagements.length + ")" : ""),
            extra: h(Tooltip, { title: "新建交付项目" },
              h(Button, { size: "small", type: "text", onClick: function () { setCreating(true); } }, "+")),
            bodyStyle: { maxHeight: 560, overflowY: "auto", padding: 8 },
          },
            engagements.length
              ? engagements.map(function (e) {
                  return h(EngagementItem, {
                    key: e.engagement_id,
                    eng: e,
                    active: e.engagement_id === selected,
                    progress: sidebarProgress(e),
                    onClick: function () { select(e.engagement_id); },
                  });
                })
              : h(Empty, {
                  image: Empty.PRESENTED_IMAGE_SIMPLE,
                  description: h("div", null,
                    h("div", { style: { marginBottom: 8 } }, "暂无 engagement"),
                    h(Button, { size: "small", type: "primary", onClick: function () { setCreating(true); } }, "创建第一个"))
                })
          )
        ),
        h("div", { style: { flex: 1, minWidth: 0 } },
          workspace,
          h(Tabs, {
            size: "small",
            defaultActiveKey: "forge",
            items: [
              {
                key: "forge",
                label: tabLabel("📄 语料锻造", "把客户原始 CSV 锻造成训练语料（去 PII + 补合成样本）"),
                children: h(ForgePanel),
              },
              {
                key: "kpi",
                label: tabLabel("📈 KPI", "用 JSONL 样本验证业务指标可计算性"),
                children: h(KpiPanel),
              },
              {
                key: "skills",
                label: tabLabel("📚 技能库", "审阅/发布技能草稿，导出 QwenPaw SKILL.md"),
                children: h(SkillsPanel),
              },
              {
                key: "deploy",
                label: tabLabel("🤖 部署计划", "Agent 装配 dry-run：预览角色→工具→数据源的绑定"),
                children: h(DeployPanel),
              },
              {
                key: "handoff",
                label: tabLabel("📦 交接", "Zone D：LLM 起草 runbook + 组装移交包（需先选中 engagement）"),
                children: h(HandoffPanel, { eid: detail ? detail.engagement_id : null }),
              },
            ],
          })
        )
      ),
      h(Modal, {
        open: creating,
        title: "新建 Engagement",
        onOk: create,
        onCancel: function () { setCreating(false); },
        okText: "创建",
        cancelText: "取消",
      },
        h("div", { style: { display: "grid", gap: 10 } },
          h("div", null,
            h("div", { style: { fontSize: 12, color: C.muted, marginBottom: 4 } }, "客户名"),
            h(Input, {
              placeholder: "如 BMW Spartanburg",
              value: form.customer,
              onChange: function (e) { setForm({ customer: e.target.value, profile: form.profile }); },
            })
          ),
          h("div", null,
            h("div", { style: { fontSize: 12, color: C.muted, marginBottom: 4 } },
              h(Term, { tip: PROFILE_TIP }, "Profile（交付模板）")),
            h(Select, {
              value: form.profile,
              style: { width: "100%" },
              onChange: function (v) { setForm({ customer: form.customer, profile: v }); },
              options: [
                { value: "ticket", label: "ticket / 客服工单" },
                { value: "manufacturing", label: "manufacturing / 具身机器人" },
              ],
            })
          )
        )
      )
    );
  }

  QwenPaw.registerRoutes(APP, [
    {
      path: "/apps/fde-scope",
      // The host's registerRoutes reads `component` (confirmed against the
      // console bundle: add({id, path, component})); `element` is kept as a
      // harmless alias for hosts using the React-style name.
      component: FdeScopePage,
      element: FdeScopePage,
    },
  ]);
  console.info("[fde-scope] registered route /apps/fde-scope");
})();
