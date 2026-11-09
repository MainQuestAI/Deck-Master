# Deck Master roadmap

当前架构与操作边界以 [AGENTS.md](AGENTS.md) 和 [Rust 重写开发稿](docs/specs/rust-rebuild/README.md) 为准。
作者入口是 Rust `deck`、独立 `deck-tools`、WebUI 与 `deck-skill/`；旧 Python 线只做维护。
安装与首次运行见 [getting-started](docs/getting-started.md)，当前跟进与限制见 [1.1.2 说明](docs/releases/1.1.2.md)。

下一轮「商业表达与专家共创改稿闭环」为**拟实施**，版本号未定。
通过会话与分文件包按切片推进，采用的设计并回既有 Rust 开发稿段落，不整包复制进仓库另建第二套权威；
入口身份见 [Spec 索引](docs/specs/README.md)。

## 历史：1.0.0 / RC4–RC5 已合入时点记录

下文保留旧线当时的工作与验收语境，不是当前推进主线或开工清单。
旧 Narrative 合同、writer 等级（含 writer floor）、方法冻结与证明链已在 Rust 线退役，不是新开发前置。
维护者验收记录只说明特定版本与机器上的观察，不构成跨环境保证。

The 1.0.0 source line includes the merged RC4 increment (PR124) and normal
installed native independent review (PR125). The
[RC4 specification](docs/specs/deck-master-next-iteration-20261019/README.md)
and [candidate ledger](tests/rebuild/fixtures/history/rc4/iteration-20261019/execution-ledger.json)
retain that increment's historical development contract and dated evidence.
Current installation, Host requirements and known limitations are in the
[first-run guide](docs/getting-started.md).
The package version, a built candidate, an active installation and a public
GitHub Release are separate facts. This roadmap does not announce a release.

PR127 merged the content-method catalog and bounded Host selection; PR128/129
merged feedback governance and documentation navigation for that source line.
PR130 merged fixed-revision content/method reading, evidence and bounded review
handoffs. The catalog and governance describe the old line, not a new development prerequisite.
The 1.0.0 publication preparation was tracked in the
[release preparation record](docs/releases/1.0.0-preparation.md).

### Included RC4 work at that time

1. N1: recover ordinary input updates from committed receipts, preserve
   legacy requests, and align the bounded HTTP/Python entry points.
2. N2: recover interrupted installation transactions while preserving path
   ownership, opt-out behavior and exact rollback replay.
3. N3: freeze Task methods and argument validation policy; apply the Review
   methods required by the actual scope.
4. N4: negotiate complete, deduplicated v2 reading contexts and reduce
   repeated history decoding without weakening recovery evidence.
5. N5: keep active instructions, contract mirrors and candidate/install
   identities consistent.
6. N6: make a concrete canonical method improvement and apply it to a
   complete normal task, with actual revisions and applicable checks.

The Runtime, CAS, immutable sources, four Skills and native
image → SVG → editable PPT chain were that source line's architecture.
Its content-only work ended with the requested content; it did not silently
start image or PPT production. The Rust rebuild superseded that architecture.

### Candidate closure at that time

The candidate workflow called for the unit matrix, real rendering, required
browser and installed/offline checks, with unavailable capabilities recorded on
the affected items. Engineering checks did not stand in for actual method
application, professional approval or user feedback.

Public release and installation activation required their own authorization.
The old rollback rule did not lower a project's writer floor; the Rust line has no writer floor.
Check [GitHub Releases](https://github.com/MainQuestAI/Deck-Master/releases)
for published assets; source version `1.0.0` alone does not publish them.

### Later decisions proposed at that time

That candidate's evidence was intended to inform further content/layout improvements
or a narrower service/Task boundary refactor. New providers, databases and
unrelated architecture rewrites were outside that increment.

Earlier preview milestones remain in
[the historical iteration plan](https://github.com/MainQuestAI/Deck-Master/blob/62dfcfc5637f0bee2358074c4458047689dd5299/docs/archive/pre-rebuild/docs/releases/2026-07-09-1.0.0-iteration-plan.md).
Use [CONTRIBUTING](CONTRIBUTING.md) for development and
[AGENTS](AGENTS.md) for task routing.
