# v0.1.0 发布操作手册（TestPyPI 优先）

> **日期**：2026-11-10 · **状态**：tag 已推送，PyPI 上传待执行（需要你的 token）
> **为什么留给你**：PyPI 上传是不可逆的——`0.1.0` 这个版本号一旦被占用，
> 就算 yank 也**不能再用**。所以这一步我不代劳，只把命令和检查点写死。

---

## 0. 已经完成的部分

| 项 | 状态 | 证据 |
|---|---|---|
| CI 七 job 全绿 | ✅ | run `42758875833` · `conclusion: success` |
| 本地回归四道锚 | ✅ | 1304 passed / coverage 91.07% / ruff / mypy |
| `v0.1.0` 注解 tag | ✅ 已推送 | `git ls-remote --tags origin v0.1.0` → `cc633b9` |
| 产物构建（从 tag 树） | ✅ | `/tmp/release_dist/` |
| `twine check` | ✅ PASSED | wheel + sdist |
| 干净 venv 安装 | ✅ | `course doctor` → G0 通过 |

产物校验和（以你重新构建的结果为准，见 §1）：

```
e9b52687c02cfe8b1de7711d990ecf75e059a0e29e1c77a384bba8801acaf5b7  fde_scope-0.1.0-py3-none-any.whl
0ba2dd257c8921c364c29edc74b24fb48e04b888bcd80f3851c618544ae98c4c  fde_scope-0.1.0.tar.gz
```

---

## 1. 从 tag 重新构建（不要用工作区构建）

必须从 tag 树构建，保证"发布的东西"和"打 tag 的东西"是同一份：

```bash
cd /path/to/fde-scope
git fetch --tags
git worktree add /tmp/fde-rel v0.1.0
cd /tmp/fde-rel
python -m build --outdir /tmp/fde-release
twine check /tmp/fde-release/*
shasum -a 256 /tmp/fde-release/*
```

`twine check` 必须两行都 PASSED；哈希与本文 §0 不一致时**停下来查**，
不要"差不多就传"。

---

## 2. 配置 TestPyPI 凭据

先在 https://test.pypi.org/manage/account/token/ 创建 token（scope 选
"Entire account"，首次上传前项目还不存在）。

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-<你的 TestPyPI token>
# 不要写进 ~/.pypirc 再忘了它；用环境变量，用完 unset
```

---

## 3. 上传到 TestPyPI

```bash
python -m twine upload --repository-url https://test.pypi.org/legacy/ \
  /tmp/fde-release/*
```

首次上传前 TestPyPI 会要求你**先验证邮箱**（账号设置页），
没验证会报 `403 Invalid or non-existent authentication information`。

---

## 4. 从 TestPyPI 装一遍（**这一步才是验证**）

TestPyPI 不带依赖镜像，所以 extras 要指向正式 PyPI：

```bash
python -m venv /tmp/tp-verify
/tmp/tp-verify/bin/pip install -q \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "fde-scope[web]==0.1.0"

FDE_SCOPE_HOME=/tmp/tp-home /tmp/tp-verify/bin/fde-scope --version   # 期望 0.1.0
FDE_SCOPE_HOME=/tmp/tp-home /tmp/tp-verify/bin/fde-scope course doctor
# 期望：✅ G0 通过（5 通过 · 1 提醒 · 3 可选 · 0 失败）可以开 D1
```

再起一次 Web 确认页面不是空壳：

```bash
FDE_SCOPE_HOME=/tmp/tp-home /tmp/tp-verify/bin/fde-scope web --port 8899 &
sleep 5
curl -s -o /dev/null -w "/course %{http_code}\n" http://127.0.0.1:8899/course
curl -s http://127.0.0.1:8899/course | wc -c     # 期望 ~1.4 MB，不是几 KB
kill %1
```

> **判据**：`/course` 的字节数比几千字节大得多、`course doctor` 是 G0 通过。
> 如果只有几 KB，说明 wheel 里的课程数据没进去——回看 `pyproject.toml` 的
> `force-include`，**不要**直接传正式 PyPI。

---

## 5. 上传正式 PyPI

§4 全部通过后再执行：

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-<你的正式 PyPI token>
python -m twine upload /tmp/fde-release/*
unset TWINE_PASSWORD
```

上传成功后：

```bash
python -m venv /tmp/pkg-verify
/tmp/pkg-verify/bin/pip install "fde-scope[web]==0.1.0"
/tmp/pkg-verify/bin/fde-scope --version
```

然后去 https://pypi.org/project/fde-scope/ 确认 README 渲染正常
（`twine check` 已验证过，但线上渲染仍值得看一眼）。

---

## 6. 收尾（上传成功后我会改的文档）

上传成功后，`README.md` 里这几处**会变成过期信息**，需要一起改：

| 位置 | 现在写的 | 应改为 |
|---|---|---|
| README「最短安装路径」 | 「没有一条命令装完的路径…PyPI 返回 404」 | `pip install fde-scope` |
| README 发布进度块 | 「尚未上传 PyPI」 | 已发布 0.1.0 + 链接 |
| CHANGELOG 顶部基线注 | 「not on PyPI → 404」 | 首版已发布日期 |

告诉我上传结果，我一次性改完并提交。

---

## 7. 如果出问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `403 Invalid or non-existent authentication` | TestPyPI 邮箱未验证 / token 错 | 验证邮箱、重发 token |
| `400 File already exists` | 该版本已上传过 | **不可覆盖**。PyPI 上换版本号（0.1.1），tag 保留 |
| `twine check` 警告 README 渲染 | README 里有不支持的 HTML | 修 README 再构建（此时还没上传，安全） |
| 安装后 `/course` 很小 | wheel 缺课程数据 | 不要上传正式 PyPI，查 `force-include` |

**最关键的一条**：`0.1.0` 传上正式 PyPI 之后就不能改内容了。
所以 §4 的 TestPyPI 验证不是形式，是唯一一次"免费试错"的机会。