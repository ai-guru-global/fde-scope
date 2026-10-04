"""The shared app shell for the long-document pages.

Overview, certification and glossary all render as the same shape: a
sticky left sidebar carrying the site menu, and a scrolling article beside
it. Kept here rather than in ``app.py`` because ``certification.py`` and
``glossary.py`` are imported *by* ``app.py`` and cannot import back.

``SHELL_CSS`` expects the page to provide the site tokens (``--bg``,
``--border``, ``--accent`` …) and the ``.logo`` / ``.tag`` / ``.lang`` /
``.tbtn`` rules; it only adds the shell, the sidebar menu and the scroll
spy.
"""

#: Marks the section link whose target is currently on screen. The spy
#: below writes this class; page-level links (which carry ``active`` for
#: "you are here") are left alone.
SHELL_JS = """
(function(){
  var links = document.querySelectorAll('.snav a[href^="#"]');
  if (!links.length || !('IntersectionObserver' in window)) return;
  var byId = {};
  links.forEach(function(a){
    var el = document.getElementById(a.getAttribute('href').slice(1));
    if (el) byId[el.id] = a;
  });
  var spy = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (!e.isIntersecting) return;
      links.forEach(function(a){ a.classList.remove('on'); });
      if (byId[e.target.id]) byId[e.target.id].classList.add('on');
    });
  }, {rootMargin: '-8% 0px -70% 0px'});
  Object.keys(byId).forEach(function(id){ spy.observe(document.getElementById(id)); });
})();
"""

BASE_CSS = """/* Hallmark · genre: modern-minimal · macrostructure: long-document · design-system: design.md (Graphite) · designed-as-app */
:root{--bg:oklch(0.973 0.003 255);--bg2:oklch(1 0 0);--panel:oklch(1 0 0);--panel2:oklch(0.945 0.005 255);
--fg:oklch(0.225 0.014 255);--muted:oklch(0.47 0.016 255);--faint:oklch(0.52 0.014 255);
--border:oklch(0.9 0.006 255);--border-strong:oklch(0.8 0.01 255);
--accent:oklch(0.5 0.095 235);--accent-2:oklch(0.44 0.095 235);--accent-ink:oklch(0.99 0.002 255);--accent-dim:oklch(0.5 0.095 235/0.09);
--good:oklch(0.51 0.12 152);--warn:oklch(0.53 0.11 75);--bad:oklch(0.55 0.17 25);--code:oklch(0.955 0.004 255);
--font:-apple-system,"SF Pro Text","Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
--mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;color-scheme:light}
html[data-theme="dark"]{--bg:oklch(0.165 0.012 255);--bg2:oklch(0.2 0.013 255);--panel:oklch(0.2 0.013 255);--panel2:oklch(0.22 0.015 255);
--fg:oklch(0.93 0.006 255);--muted:oklch(0.68 0.014 255);--faint:oklch(0.61 0.013 255);
--border:oklch(0.3 0.014 255);--border-strong:oklch(0.4 0.016 255);
--accent:oklch(0.74 0.085 232);--accent-2:oklch(0.79 0.07 232);--accent-ink:oklch(0.2 0.04 232);--accent-dim:oklch(0.74 0.085 232/0.13);
--good:oklch(0.76 0.13 152);--warn:oklch(0.8 0.13 85);--bad:oklch(0.7 0.16 25);--code:oklch(0.14 0.012 255);color-scheme:dark}
*{box-sizing:border-box}
html,body{overflow-x:clip}
body{margin:0;font:400 15px/1.65 var(--font);background:var(--bg);color:var(--fg)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:0.01ms!important;scroll-behavior:auto!important}}
a{color:var(--accent);text-decoration:none}
.ic,.ic-xs{fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;flex:none}
.ic{width:16px;height:16px}.ic-xs{width:13px;height:13px}
.mk-g{color:var(--accent)}.mk-w{color:var(--warn)}
.logo{font-size:1.08rem;font-weight:700;letter-spacing:-.01em}
.logo span{color:var(--accent)}
.tag{font:600 11px/1 var(--mono);color:var(--accent);background:var(--accent-dim);padding:5px 10px;border-radius:999px;white-space:nowrap}
.lang{font:600 11px/1 var(--mono);letter-spacing:.08em;color:var(--muted);border:1px solid var(--border);border-radius:999px;padding:7px 11px;transition:color .13s,border-color .13s;white-space:nowrap}
.lang:hover{color:var(--fg);border-color:var(--border-strong)}
.tbtn{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:7px;
border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:color .15s,border-color .15s}
.tbtn:hover{color:var(--fg);border-color:var(--border-strong)}
.when-dark{display:none}
html[data-theme="dark"] .when-light{display:none}
html[data-theme="dark"] .when-dark{display:inline}
.hero{padding:14px 0 34px;max-width:800px}
.hero .eyebrow{font:600 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin:0 0 16px}
.hero h2{font-size:clamp(30px,4.5vw,42px);font-weight:680;letter-spacing:-.022em;line-height:1.12;margin:0 0 14px;overflow-wrap:anywhere;min-width:0}
.hero p{color:var(--muted);font-size:1.02rem;margin:0;max-width:680px}
.hero .cta{margin-top:26px;display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:7px;background:var(--accent);color:var(--accent-ink);border:1px solid transparent;
padding:9px 16px;border-radius:7px;font-weight:600;font-size:.9rem;font-family:inherit;text-decoration:none;cursor:pointer;
transition:background-color .15s,border-color .15s,color .15s}
.btn:hover{background:var(--accent-2)}
.btn.ghost{background:transparent;border-color:var(--border);color:var(--fg)}
.btn.ghost:hover{border-color:var(--border-strong);background:var(--panel2)}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--border);
border:1px solid var(--border);border-radius:10px;overflow:hidden}
.stat{background:var(--bg2);padding:16px 18px}
.stat .num{font-size:1.9rem;font-weight:700;line-height:1.1;letter-spacing:-.02em;color:var(--accent)}
.stat .lab{font-size:.78rem;color:var(--muted);margin-top:3px}
section{padding-top:44px}
.sec-head{display:flex;align-items:center;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--border);margin-bottom:14px}
.sec-head .ic{color:var(--accent)}
.sec-head h2{margin:0;font-size:19px;font-weight:650;letter-spacing:-.01em;min-width:0;overflow-wrap:anywhere}
.sec-head .n{font:600 11px/1 var(--mono);color:var(--faint);margin-left:auto;letter-spacing:.1em}
.sec-note{font-size:.8rem;color:var(--muted);margin:0 0 14px;line-height:1.7;max-width:820px}
.grid{display:grid;gap:10px}
.cols-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:9px;padding:14px 16px;transition:border-color .15s;min-width:0}
.tile:hover{border-color:var(--border-strong)}
.tile>.ic{color:var(--muted);margin-bottom:9px}
.tile .name{font-weight:600;font-size:.95rem;margin-bottom:4px;overflow-wrap:anywhere;min-width:0;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tile.mono .name{font:600 .82rem/1.55 var(--mono)}
.tile .desc{color:var(--muted);font-size:.82rem;line-height:1.6}
.tile .desc a{white-space:nowrap}
footer{margin-top:56px;padding:22px 0 6px;border-top:1px solid var(--border);color:var(--faint);
font-size:.8rem;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
"""

SHELL_CSS = """
.shell{display:grid;grid-template-columns:250px minmax(0,1fr);align-items:start}
.side{position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column;
padding:22px 16px 0;border-right:1px solid var(--border);background:var(--bg2)}
.side .brand{display:flex;flex-direction:column;align-items:flex-start;gap:9px;
padding:0 8px 15px;border-bottom:1px solid var(--border);margin-bottom:12px}
/* the rail is 250px: pills that fit a full-width header must wrap here */
.side .brand .tag{white-space:normal;line-height:1.5;text-align:left}
.snav{display:flex;flex-direction:column;gap:2px;padding-bottom:14px}
.snav a{color:var(--muted);font-size:.85rem;padding:7px 10px;border-radius:7px;
border-left:2px solid transparent;transition:color .15s,background-color .15s,border-color .15s}
.snav a:hover{color:var(--fg);background:var(--panel2)}
.snav a.active{color:var(--accent);background:var(--accent-dim);border-left-color:var(--accent);font-weight:600}
.snav a.on{color:var(--accent);border-left-color:var(--accent)}
/* Group labels head their section: same size as the links under them, but a
   full weight step (700 vs 400) and full-strength ink, so hierarchy is carried
   by weight and tone. The old 10px faint mono uppercase eyebrow was illegible
   in Chinese and put the label below its own children. */
.snav .grp{font-weight:700;font-size:.85rem;line-height:1.35;letter-spacing:0;color:var(--fg);
padding:20px 10px 8px}
/* the rail is a tree: only the active destination expands into its own
   anchors. A flat list of every section on the site read as a 17-row wall. */
.snav .subnav{display:flex;flex-direction:column;gap:1px;margin:1px 0 4px;padding-left:12px}
.snav .subnav a{font-size:.79rem;font-weight:500;color:var(--faint);padding:5px 10px;
border-left:2px solid transparent;border-radius:0 7px 7px 0}
.snav .subnav a:hover{color:var(--fg);background:var(--panel2)}
.snav .subnav a.on{color:var(--accent);border-left-color:var(--accent)}
/* Third level: a destination that is itself long groups its anchors. Same
   weight/tone discipline as ``.grp`` — a bold caption one tone below the
   top-level groups, above its own 500-weight faint links. */
.snav .subnav .sgrp{font-weight:700;font-size:.72rem;line-height:1.3;color:var(--muted);
padding:12px 10px 3px}
.snav .subnav .sgrp:first-child{padding-top:2px}
/* pinned to the sidebar's foot: the nav outgrows a short viewport, and the
   locale/theme controls must stay reachable without scrolling it. The
   container has no bottom padding so this opaque block covers the edge. */
.side-foot{position:sticky;bottom:0;margin-top:auto;display:flex;align-items:center;gap:8px;
padding:15px 8px 18px;border-top:1px solid var(--border);background:var(--bg2)}
/* the rail scrolls under this block, so the fold would otherwise cut a link
   in half; fade the last sliver instead of slicing it */
.side-foot::before{content:"";position:absolute;left:0;right:0;bottom:100%;height:22px;
background:linear-gradient(to top,var(--bg2),transparent);pointer-events:none}
.main{min-width:0}
.main .wrap{max-width:1080px;margin:0 auto;padding:34px 30px 56px}
.main section{scroll-margin-top:16px}
@media(max-width:960px){
.shell{grid-template-columns:1fr}
.side{position:static;height:auto;border-right:0;border-bottom:1px solid var(--border);
padding:16px 16px 12px}
.side .brand{flex-direction:row;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.snav{flex-direction:row;flex-wrap:wrap}
.snav a{border-left:0;padding:6px 10px}
.snav a.active,.snav a.on{background:var(--accent-dim);border-left:0}
.snav .grp{width:100%;padding:10px 10px 4px}
.snav .subnav{width:100%;flex-direction:row;flex-wrap:wrap;padding-left:0;margin:0 0 2px}
.snav .subnav .sgrp{width:100%;padding:8px 0 2px}
.snav .subnav a{border-left:0;border-radius:7px;padding:5px 9px}
.snav .subnav a.on{background:var(--accent-dim)}
.side-foot{position:static;margin-top:10px;padding-bottom:0}
.side-foot::before{display:none}
.main .wrap{padding:22px 16px 40px}
}
"""
