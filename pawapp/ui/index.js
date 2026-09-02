/**
 * FDE Scope — frontend (runtime-loaded plugin module).
 *
 * Loaded by the QwenPaw host via usePluginLoader (same-origin Blob URL +
 * dynamic import). Self-registers a React route at /apps/fde-scope. React
 * and antd come from window.QwenPaw.host (no bundler in this context).
 *
 * Minimal workbench (skeleton v0.1):
 * - cross-project matrix (engagement list with phase/zone/progress)
 * - 18-phase SOP pipeline with the current phase highlighted
 * - enforceable gates panel (blockers/warnings, re-check)
 * - advance (gate-blocked) + create engagement
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

  var Button = antd.Button;
  var Card = antd.Card;
  var Empty = antd.Empty;
  var Input = antd.Input;
  var Modal = antd.Modal;
  var Progress = antd.Progress;
  var Select = antd.Select;
  var Space = antd.Space;
  var Statistic = antd.Statistic;
  var Table = antd.Table;
  var Tabs = antd.Tabs;
  var Tag = antd.Tag;
  var Upload = antd.Upload;
  var message = antd.message;

  var APP = "fde-scope";

  var ZONE_LABEL = {
    pre_engagement: "A·Pre",
    build: "B·Build",
    operationalization: "C·Ops",
    handoff: "D·Handoff",
  };

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
      h(Space, { wrap: true },
        h(Upload, {
          accept: ".csv",
          maxCount: 1,
          beforeUpload: function (f) {
            setFile(f);
            return false;
          },
        }, h(Button, null, "选择 CSV")),
        h(Button, { type: "primary", loading: running, onClick: forge }, running ? "锻造中…" : "锻造语料"),
        h("span", { style: { fontSize: 12, color: "#8b98a9" } }, "配置 FDE_SCOPE_MIMO_API_KEY 时自动启用 LLM 合成")
      ),
      result &&
        h("div", { style: { marginTop: 14 } },
          h(Space, { size: 24, wrap: true },
            h(Statistic, { title: "total", value: result.total }),
            h(Statistic, { title: "real", value: result.real, valueStyle: { color: "#4ade80" } }),
            h(Statistic, { title: "synthetic", value: result.synthetic, valueStyle: { color: "#2dd4bf" } }),
            h(Statistic, { title: "dropped", value: result.dropped }),
            h(Statistic, { title: "PII masked", value: result.pii_masked })
          ),
          h("div", { style: { marginTop: 8, fontSize: 12, color: "#8b98a9" } },
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
      h(Space, { wrap: true },
        h(Select, {
          value: profile,
          style: { width: 200 },
          onChange: setProfile,
          options: [
            { value: "manufacturing", label: "manufacturing · OEE/MTBF/抓取率" },
            { value: "ticket", label: "ticket · 客服指标" },
          ],
        }),
        h(Upload, {
          accept: ".jsonl,.json",
          maxCount: 1,
          beforeUpload: function (f) {
            setFile(f);
            return false;
          },
        }, h(Button, null, "选择样本 JSONL")),
        h(Button, { type: "primary", loading: running, onClick: run }, "计算 KPI")
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
          h("div", { style: { marginTop: 8, fontSize: 12, color: "#8b98a9" } },
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
        h("div", { style: { display: "flex", alignItems: "center", gap: 8 } },
          h("b", null, r.title),
          h(Tag, null, r.category),
          isDraft && h(Tag, { color: "orange" }, r.source || "draft"),
          h("div", { style: { marginLeft: "auto" } },
            isDraft && h(Button, { size: "small", type: "primary", onClick: function () { publish(r.id); } }, "发布"),
            " ",
            h(Button, { size: "small", onClick: function () { doExport(r.id); } }, "导出 QwenPaw")
          )
        ),
        h("div", { style: { fontSize: 12, color: "#8b98a9", marginTop: 4 } },
          r.id + (r.source_engagement ? " · 来自 " + r.source_engagement : "")
        )
      );
    }

    return h("div", null,
      h("div", { style: { fontWeight: 600, marginBottom: 8 } }, "草稿审阅队列"),
      drafts.length ? drafts.map(function (r) { return skillCard(r, true); }) : h(Empty, { description: "无待审草稿" }),
      h("div", { style: { fontWeight: 600, margin: "14px 0 8px" } }, "已发布技能"),
      skills.length ? skills.map(function (r) { return skillCard(r, false); }) : h(Empty, { description: "还没有沉淀 — 把现场经验变成可复用技能" })
    );
  }

  // -- SOP pipeline -------------------------------------------------------
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
      { style: { display: "flex", flexWrap: "wrap", gap: 6 } },
      phases.map(function (p, i) {
        var done = i < idx;
        var isCur = i === idx;
        return h(
          "div",
          {
            key: p.slug,
            title: (ZONE_LABEL[p.zone] || p.zone) + (p.industrial ? " · 🏭 industrial" : ""),
            style: {
              padding: "4px 10px",
              borderRadius: 8,
              fontSize: 12,
              border: isCur ? "1px solid #10b981" : "1px solid rgba(148,163,184,0.25)",
              background: isCur ? "rgba(16,185,129,0.12)" : done ? "rgba(16,185,129,0.05)" : "transparent",
              color: done ? "#9ca3af" : "#e6edf3",
              textDecoration: done ? "line-through" : "none",
            },
          },
          p.index + ". " + p.name + (p.gates && p.gates.length ? " 🚦" : "")
        );
      })
    );
  }

  // -- gates panel --------------------------------------------------------
  function GatesPanel(props) {
    var eid = props.eid;
    var gates = props.gates || {};
    var entries = Object.entries(gates);
    if (!entries.length) {
      return h(Empty, { description: "当前 profile 无适用 gate" });
    }
    return h(
      "div",
      { style: { display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))" } },
      entries.map(function (kv) {
        var slug = kv[0];
        var g = kv[1];
        return h(
          Card,
          { key: slug, size: "small", style: { borderColor: g.passed ? "rgba(74,222,128,0.4)" : "rgba(248,113,113,0.4)" } },
          h("div", { style: { display: "flex", justifyContent: "space-between" } },
            h("b", null, g.name),
            h(Tag, { color: g.passed ? "green" : "red" }, g.passed ? "PASS" : "BLOCKED")
          ),
          h(
            "ul",
            { style: { margin: "6px 0 0", paddingLeft: 18, fontSize: 12, color: "#8b98a9" } },
            g.blockers.map(function (b) {
              return h("li", { key: b }, "🚫 " + b);
            }),
            g.warnings.map(function (w) {
              return h("li", { key: w }, "⚠️ " + w);
            })
          ),
          h(Button, {
            size: "small",
            style: { marginTop: 6 },
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
      return h(Empty, { description: "先在 SOP 工作台选择一个 engagement" });
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
      h("div", { style: { fontSize: 13, color: "#8b98a9", marginBottom: 10 } },
        "Zone D 交接：先用宿主 LLM 起草 runbook（失败自动回退模板，如实标注来源），再组装移交包。"
      ),
      h(Space, { wrap: true },
        h(Button, { type: "primary", loading: drafting, onClick: draft }, drafting ? "起草中…" : "🤖 LLM 起草 Runbook"),
        h(Button, { loading: packing, onClick: function () { pack(false); } }, "📦 组装移交包"),
        h(Button, { loading: packing, onClick: function () { pack(true); } }, "✅ 组装并标记客户已验收")
      ),
      last &&
        h("div", { style: { marginTop: 10, fontSize: 12, color: "#8b98a9" } },
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

    var muted = { fontSize: 12, color: "#8b98a9" };

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
          h(Tag, { color: a.role_bucket === "corpus" ? "orange" : "cyan" }, a.role + " · " + (a.role_bucket || "corpus-only")),
          h(Tag, null, a.model || "runtime 注入"),
          h("span", { style: { marginLeft: "auto" } },
            h("span", { style: muted }, "bound " + (a.bound || []).length + " · unbound " + unbound)
          )
        ),
        h("div", { style: { marginTop: 4 } }, tools.length ? tools : h("span", { style: muted }, "仅语料工具")),
        unbound
          ? h("div", { style: { marginTop: 4, fontSize: 12, color: "#fbbf24" } },
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
      h(Card, { size: "small", title: "Agent 部署计划 · dry-run" },
        h("div", { style: Object.assign({ marginBottom: 10 }, muted) },
          "与 CLI deploy / Web 控制台走同一 build_deploy_plan：纯数据预览「哪个角色 Agent 拿到哪个连接器工具、对着哪个数据源」，不 import AgentScope、不调模型。"
        ),
        h("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 } },
          h("div", null, h("div", { style: muted }, "Tenant"), h(Input, { value: tenant, onChange: function (e) { setTenant(e.target.value); } })),
          h("div", null, h("div", { style: muted }, "模型"), h(Input, { value: model, onChange: function (e) { setModel(e.target.value); } })),
          h("div", null, h("div", { style: muted }, "Profile"),
            h(Select, { value: profile, style: { width: "100%" }, onChange: setProfile, options: [
              { value: "ticket", label: "ticket / 客服" },
              { value: "manufacturing", label: "manufacturing / 制造业" },
            ] })),
          h("div", null, h("div", { style: muted }, "审批模式"),
            h(Select, { value: mode, style: { width: "100%" }, onChange: setMode, options: [
              { value: "conservative", label: "conservative · 例行外呼也 ASK" },
              { value: "balanced", label: "balanced · 仅高风险 ASK" },
              { value: "autonomous", label: "autonomous · 未匹配 DENY" },
            ] }))
        ),
        h("div", { style: { marginTop: 8 } },
          h("div", { style: muted }, "Agents（每行：名字:角色[:模型]）"),
          h(Input.TextArea, { rows: 3, value: agents, onChange: function (e) { setAgents(e.target.value); } })
        ),
        h("div", { style: { marginTop: 8 } },
          h("div", { style: muted }, "数据源（每行：slug=路径或URL）"),
          h(Input.TextArea, { rows: 2, value: sources, onChange: function (e) { setSources(e.target.value); } })
        ),
        h("div", { style: { marginTop: 10, display: "flex", gap: 8, alignItems: "center" } },
          h(Button, { type: "primary", loading: running, onClick: run }, "生成部署计划"),
          h("span", { style: muted }, "角色是自由文本 → 自动归 数据/日志/文件 工具桶；匹配不上 → corpus-only")
        )
      ),
      err && h(Card, { size: "small", style: { marginTop: 10, borderColor: "rgba(248,113,113,0.4)" } },
        h("b", null, "校验失败（422）"), h("pre", { style: { fontSize: 11, whiteSpace: "pre-wrap" } }, err)),
      m && h("div", { style: { marginTop: 10 } },
        h(Space, { size: 24, wrap: true },
          h(Statistic, { title: "Agents", value: sum ? sum.agents : m.agents.length }),
          h(Statistic, { title: "Bound 工具", value: sum ? sum.bound_tools.length : 0, valueStyle: { color: "#4ade80" } }),
          h(Statistic, {
            title: "Unbound 工具",
            value: sum ? sum.unbound_tools.length : 0,
            valueStyle: { color: sum && sum.unbound_tools.length ? "#fbbf24" : undefined },
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
    }, []);

    function advance(force) {
      api("/engagements/" + selected + "/advance?force=" + force, { method: "POST" })
        .then(function (r) {
          if (!r.advanced) {
            if (r.reason === "complete") {
              message.info("已完成全部阶段 🎉");
            } else {
              Modal.warning({
                title: "推进被 gate 拦截",
                content: (r.result.blockers || []).join("\n"),
              });
            }
          } else {
            message.success("已推进到 " + r.status.current_phase);
          }
          select(selected);
        })
        .catch(function (e) {
          message.error(String(e.message || e));
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
          load();
        })
        .catch(function (e) {
          message.error(String(e.message || e));
        });
    }

    var columns = [
      {
        title: "客户",
        dataIndex: "customer",
        render: function (t, r) {
          return h("div", null, h("b", null, t), h("div", { style: { fontSize: 11, color: "#8b98a9" } }, r.engagement_id));
        },
      },
      {
        title: "Profile",
        dataIndex: "profile",
        render: function (p) {
          return h(Tag, { color: p === "manufacturing" ? "orange" : "cyan" }, p);
        },
      },
      {
        title: "阶段",
        dataIndex: "current_phase",
        render: function (p, r) {
          return p + " · " + (ZONE_LABEL[r.current_zone] || r.current_zone);
        },
      },
      {
        title: "状态",
        render: function (_, r) {
          return r.is_complete ? h(Tag, { color: "green" }, "完成") : h(Tag, null, "进行中");
        },
      },
    ];

    var progress = 0;
    if (detail && phases.length) {
      for (var i = 0; i < phases.length; i++) {
        if (phases[i].slug === detail.current_phase) {
          progress = Math.round(((i + 1) / phases.length) * 100);
          break;
        }
      }
    }

    return h(
      "div",
      { style: { padding: 16, maxWidth: 1200, margin: "0 auto" } },
      h("div", { style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 14 } },
        h("h2", { style: { margin: 0 } }, "🛠️ FDE Scope"),
        h("span", { style: { color: "#8b98a9", fontSize: 13 } }, "18 阶段 SOP · 可执行 gate · 72h raw data → deployed agent"),
        h("div", { style: { marginLeft: "auto" } },
          h(Button, { type: "primary", onClick: function () { setCreating(true); } }, "+ 新建 Engagement")
        )
      ),
      h(Tabs, {
        defaultActiveKey: "sop",
        items: [
          {
            key: "sop",
            label: "🗺 SOP 工作台",
            children: h(
              "div",
              null,
              h(Card, { size: "small", title: "跨项目矩阵", style: { marginBottom: 14 } },
                engagements.length
                  ? h(Table, {
                      rowKey: "engagement_id",
                      columns: columns,
                      dataSource: engagements,
                      pagination: false,
                      size: "small",
                      onRow: function (r) {
                        return { onClick: function () { select(r.engagement_id); }, style: { cursor: "pointer" } };
                      },
                    })
                  : h(Empty, { description: "暂无 engagement — 点右上角创建第一个" })
              ),
              detail &&
                h(Card, {
                    size: "small",
                    title: detail.customer + " · " + detail.current_phase,
                    style: { marginBottom: 14 },
                    extra: h(Space, null,
                      h(Button, { onClick: function () { advance(false); } }, "⏭ 推进"),
                      h(Button, { danger: true, onClick: function () { advance(true); } }, "force 推进")
                    ),
                  },
                  h(Progress, { percent: progress, size: "small", style: { marginBottom: 10 } }),
                  h(SopPipeline, { phases: phases, current: detail.current_phase })
                ),
              detail &&
                h(Card, {
                    size: "small",
                    title: "Gates（可执行合规检查）",
                    extra: h(Button, { size: "small", onClick: function () { select(detail.engagement_id); } }, "刷新"),
                  },
                  h(GatesPanel, { eid: detail.engagement_id, gates: gates, refresh: function () { select(detail.engagement_id); } })
                )
            ),
          },
          { key: "forge", label: "📄 语料锻造", children: h(ForgePanel) },
          { key: "kpi", label: "📈 KPI", children: h(KpiPanel) },
          { key: "skills", label: "📚 技能库", children: h(SkillsPanel) },
          { key: "deploy", label: "🤖 Agent 部署", children: h(DeployPanel) },
          { key: "handoff", label: "📦 交接", children: h(HandoffPanel, { eid: detail ? detail.engagement_id : null }) },
        ],
      }),
      h(Modal, {
        open: creating,
        title: "新建 Engagement",
        onOk: create,
        onCancel: function () { setCreating(false); },
        okText: "创建",
        cancelText: "取消",
      },
        h("div", { style: { display: "grid", gap: 10 } },
          h(Input, {
            placeholder: "客户名，如 BMW Spartanburg",
            value: form.customer,
            onChange: function (e) { setForm({ customer: e.target.value, profile: form.profile }); },
          }),
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
