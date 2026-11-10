# PR-3 screenshot diff (before = main 24756250, after = style/app-css-tokens eacd4083 on 688e9dbd)

Headless Chrome (/usr/bin/google-chrome via Playwright 1.65.0), deviceScaleFactor 1, full-page, animations disabled,
`deck serve` of a throwaway 3-page sample project (copied fresh per run from /tmp/pr3-sample/project).
Noise check: two BEFORE runs were byte-identical (max delta 0).

| scene | 1280x800 | 1440x900 | 375x812 |
|---|---|---|---|
| overview (制作总览) | identical | identical | identical |
| content (内容与页序) | identical | identical | identical |
| gallery (整稿画廊) | identical | identical | identical |
| delivery (任务与交付) | identical | identical | identical |
| page (单页工作区, page 01) | identical | identical | identical |
| dark overview / content / delivery | identical (1280 only) | — | — |

18/18 screenshots: 0 differing pixels (max channel delta 0). No rounding diffs either.
Computed-style dump (21 properties x 2122 element snapshots across all scenes/sizes/themes): 0 differences.
Machine-readable: diff/diff-summary.json. Codex's own extra state check (hover/active/disabled/reduced-motion, 86 comparisons, 0 differences): codex-state-check/.
