"""Role entries stay independently addressable and share one method tree."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "deck-skill"
ROLES = ("deck-master", "deck-content", "deck-design", "deck-review")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")


def _local_links(text: str) -> list[str]:
    found = []
    for raw in LINK.findall(text):
        if raw.startswith(("http://", "https://", "mailto:")):
            continue
        path = raw.split("#", 1)[0]
        if path:
            found.append(path)
    return found


def _frontmatter_name(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing name in {path}")


def test_source_has_one_skill_manifest_and_unique_names() -> None:
    manifests = [path for path in SOURCE.rglob("SKILL.md")]
    assert manifests == [SOURCE / "SKILL.md"]
    names = [_frontmatter_name(SOURCE / "SKILL.md")]
    names.extend(_frontmatter_name(SOURCE / f"{role}.md") for role in ROLES)
    assert names == ["deck", *ROLES]


def test_role_entries_call_rust_deck() -> None:
    for role in ROLES:
        text = (SOURCE / f"{role}.md").read_text(encoding="utf-8")
        assert "`deck`" in text
        assert "deck_master" not in text
        assert "python -m deck_master" not in text
        for link in _local_links(text):
            assert link.startswith(("references/", "assets/"))


def test_shared_links_resolve_from_source_and_from_role_directory(tmp_path: Path) -> None:
    install = tmp_path / "skills"
    for role in ROLES:
        directory = install / role
        directory.mkdir(parents=True)
        os.symlink(SOURCE / f"{role}.md", directory / "SKILL.md")
        os.symlink(SOURCE / "references", directory / "references")
        os.symlink(SOURCE / "assets", directory / "assets")
        source_text = (SOURCE / f"{role}.md").read_text(encoding="utf-8")
        for link in _local_links(source_text):
            from_source = (SOURCE / link).resolve()
            from_install = (directory / link).resolve()
            assert from_source.is_file() or from_source.is_dir()
            assert from_install == from_source


def test_method_markdown_links_resolve() -> None:
    for path in SOURCE.rglob("*.md"):
        for link in _local_links(path.read_text(encoding="utf-8")):
            target = (path.parent / link).resolve()
            assert target.is_file() or target.is_dir(), f"{path} -> {link}"


@pytest.mark.parametrize("relative", ["deck-content.md", "references/page-writing.md"])
def test_title_policy_preserves_page_roles(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    paragraphs = re.split(r"\n\s*\n", text)
    for role in ("说明", "教学"):
        policies = [paragraph for paragraph in paragraphs if re.search(rf"{role}(?:页|页面)", paragraph)]
        assert any(
            re.search(r"(?:不(?:强制|要求|必)|无[需须]).{0,30}(?:结论|判断).{0,8}标题", policy)
            and re.search(r"(?:不(?:强制|要求|必)|无[需须]).{0,40}(?:商业\s*)?CTA", policy)
            for policy in policies
        ), f"{relative}: {role} pages need title and CTA exceptions"
    assert re.search(r"判断页.{0,30}判断句", text)
    assert re.search(r"查阅页.{0,30}查阅职责", text)


@pytest.mark.parametrize("relative", ["deck-review.md", "references/method-review.md"])
def test_review_guidance_separates_qa_layers(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    for layer, topics in (
        ("Q1", ("业务", "语义")),
        ("Q2", ("保真", "可读", "完成度")),
        ("Q3", ("可编辑", "Office")),
    ):
        assert any(
            layer in line and all(topic in line for topic in topics)
            for line in text.splitlines()
        ), f"{relative}: {layer}"
    assert re.search(r"(?:独立|分别).{0,40}(?:boolean|布尔)", text)
    boundary = next((p for p in re.split(r"\n\s*\n", text) if "status=pass" in p), "")
    assert all(token in boundary for token in ("视觉", "Office", "visual_review", "desktop_editing", "not_evaluated"))
    assert re.search(r"不(?:等于|代表|证明)", boundary)


def test_review_entry_requires_located_graded_evidence() -> None:
    entry = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    report = next(p for p in re.split(r"\n\s*\n", entry) if "每一条" in p)
    assert all(token in report for token in ("页", "对象", "区域", "原句", "问题", "影响", "建议", "分级", "依据", "验证"))
    method = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    for grade, examples in (
        ("Critical", ("事实", "数字", "方向", "分支", "能力", "打开", "正文")),
        ("Major", ("文字墙", "主视觉", "关系", "失真")),
        ("Minor", ("位置", "行距", "图标", "装饰")),
    ):
        line = next((line for line in method.splitlines() if grade in line), "")
        assert all(example in line for example in examples), grade


def test_review_consumes_supported_readback_findings_without_inventing_edges() -> None:
    entry = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    assert re.search(r"先.{0,30}findings.{0,60}再.{0,15}(?:阅图|画面)", entry)
    method = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", method))
    codes = {
        "reversed_arrow", "missing_edge", "missing_node", "edge_not_connected",
        "unreadable_text", "hidden_or_tiny_text", "missing_visible_atom",
    }
    assert codes <= documented
    supported = set()
    for name in ("render.py", "readback_text.py", "readback_relations.py"):
        tree = ast.parse((REPO / "deck-tools/src/deck_tools" / name).read_text(encoding="utf-8"))
        supported.update(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str))
    assert codes <= supported
    assert re.search(r"(?:没有|缺少)预期边[^\n]*(?:未检查|依据不足)", method)
    assert re.search(r"不[^\n]*layout[^\n]*边", method)
    assert re.search(r"不[^\n]*(?:编造|发明)[^\n]*code", method)
    assert re.search(r"bbox[^\n]*pixel diff[^\n]*定位[^\n]*不[^\n]*依据", method)


def test_review_requires_separate_blueprint_and_ppt_evidence() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    for artifact in ("原图", "最终 PPT"):
        assert re.search(rf"{artifact}[^\n]*证据[^\n]*未执行", text)
    assert re.search(r"证据[^\n]*不能互相替代", text)


def test_review_protects_lookup_comparisons_and_synthetic_numbers() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    assert re.search(r"查阅[^\n]*表[^\n]*(?:保留|保护)", text)
    assert re.search(r"E02[^\n]*同[^\n]*口径", text)
    assert re.search(r"(?:合成|教学)[^\n]*数字[^\n]*不[^\n]*项目事实", text)
    entry = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    arithmetic = next(p for p in re.split(r"\n\s*\n", entry) if "case_numbers" in p)
    assert all(token in arithmetic for token in ("算式", "来源", "归因", "ROI"))


def test_master_turns_feedback_into_four_local_repair_paths() -> None:
    text = (SOURCE / "deck-master.md").read_text(encoding="utf-8")
    task = next((p for p in re.split(r"\n\s*\n", text) if "用户" in p and "审查" in p and "分流" in p), "")
    assert all(token in task for token in ("页", "对象", "区域", "问题", "依据", "动作"))
    routes = dict(re.findall(r"^- (内容|设计|调用|重建)：(.+)$", text, re.MULTILINE))
    assert set(routes) == {"内容", "设计", "调用", "重建"}
    assert all(token in routes["内容"] for token in ("purpose", "layout", "notes", "正文", "deck put --base"))
    assert re.search(r"不[^。；]*自动[^。；]*生图", routes["内容"])
    assert re.search(r"主视觉[^。；]*视觉计划", routes["设计"])
    assert re.search(r"必要[^。；]*才[^。；]*调用", routes["设计"])
    assert re.search(r"需要新蓝图[^。；]*deck run start image --pages", routes["调用"])
    assert re.search(r"task.md[^。；]*原文[^。；]*attachments.json", routes["调用"])
    assert re.search(r"蓝图[^。；]*可用[^。；]*直接修 SVG", routes["重建"])
    assert re.search(r"主结构[^。；]*先[^。；]*蓝图[^。；]*再[^。；]*重建", routes["重建"])
    assert "references/reconstruction.md" in _local_links(routes["重建"])


def test_design_can_enter_svg_repair_without_new_image() -> None:
    text = (SOURCE / "deck-design.md").read_text(encoding="utf-8")
    entry = next((p for p in re.split(r"\n\s*\n", text) if "commands.md" in p and "SVG" in p), "")
    assert re.search(r"蓝图[^。；]*可用[^。；]*直接[^。；]*SVG", entry)
    assert re.search(r"需要新蓝图[^。；]*才[^。；]*生图", entry)


def test_review_routes_submission_faults_separately_from_design() -> None:
    text = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    report = next(p for p in re.split(r"\n\s*\n", text) if "每一条" in p)
    invocation = next((part for part in report.split("；") if "交调用" in part), "")
    assert re.search(r"task.md[^。；]*附件[^。；]*正确", invocation)
    assert re.search(r"实际调用[^。；]*(?:改写|漏传)", invocation)
    assert re.search(r"task.md[^。；]*原文[^。；]*attachments.json[^。；]*提交", invocation)


def test_repair_rereview_links_to_existing_qa_judgments() -> None:
    text = (SOURCE / "deck-master.md").read_text(encoding="utf-8")
    rereview = next(p for p in re.split(r"\n\s*\n", text) if "复审" in p)
    assert re.search(r"只[^。；]*复审[^。；]*受影响[^。；]*范围", rereview)
    links = LINK.findall(rereview)
    qa = next(link for link in links if link.startswith("references/method-review.md#"))
    path, anchor = qa.split("#", 1)
    method = (SOURCE / path).read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", method, re.MULTILINE)
    assert any(heading.lower().replace(" ", "-") == anchor for heading in headings)


@pytest.mark.parametrize("relative", [
    "SKILL.md", "deck-content.md", "deck-master.md",
    "references/methods/M08-narrative.md", "references/page-writing.md",
])
def test_lookup_success_requires_reading_task_and_table_composition(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    success = next((p for p in re.split(r"\n\s*\n", text) if "留表才算成功" in p), "")
    assert all(token in success for token in ("阅读任务", "逐行核对", "构图句", "表是主视觉"))
    assert re.search(r"(?:只有|须|必须)[^。]*构图句[^。]*才算成功", success)
    if relative != "references/page-writing.md":
        assert re.search(r"主视觉选择[^。；]*阅读任务[^。；]*一致[^。；]*才算成功", success)
    assert "查阅页留表算成功" not in text
    assert "按构图句留表" not in text


def test_lookup_choice_uses_task_instead_of_keywords_or_drawing_ability() -> None:
    text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    criteria = next((p for p in re.split(r"\n\s*\n", text) if "评标矩阵" in p), "")
    for keyword in ("证据", "对照", "规则", "计划"):
        assert keyword in criteria
    assert re.search(r"本身不等于查阅页", criteria)
    assert re.search(r"能画成[^。]*不是不得留表", criteria)
    assert re.search(r"评标矩阵[^。]*能画成图[^。]*必须留表[^。]*逐行", criteria)
    assert re.search(r"读者必须按行[^。]*勾选[^。]*定位[^。]*查找", text)
    assert "不是封闭名单" in criteria
    assert re.search(r"查阅职责[^。]*标题[^。]*不等于[^。]*网格", text)


@pytest.mark.parametrize("relative", [
    "SKILL.md", "references/page-writing.md", "references/content-to-visual.md",
])
def test_declared_relations_require_body_rewrite_before_image_run(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    policy = next((p for p in re.split(r"\n\s*\n", text) if "不得再把表当主视觉" in p), "")
    assert re.search(r"`purpose`\s*或\s*`layout`", policy)
    assert all(relation in policy for relation in ("时间线", "交接", "状态流", "闭环"))
    assert re.search(r"正文[^；。]*按关系重组", policy)
    assert re.search(r"表[^；。]*最多[^；。]*取材", policy)
    assert re.search(r"先改[^；。]*构图句[^；。]*正文[^；。]*再调用[^；。]*run start image", policy)
    if relative == "SKILL.md":
        preimage = text.split("## 生图前顺序", 1)[1].split("\n## ", 1)[0]
        assert policy in preimage


@pytest.mark.parametrize("entry,chain", [
    ("SKILL.md", ("references/page-writing.md",)),
    ("references/methods/M08-narrative.md", ("../page-writing.md",)),
    ("deck-master.md", ("references/page-writing.md",)),
    ("deck-content.md", ("references/page-writing.md",)),
    ("deck-design.md", ("references/content-to-visual.md", "page-writing.md")),
    ("deck-review.md", ("references/method-review.md", "page-writing.md")),
])
def test_entry_methods_reach_shared_relation_constraint(entry: str, chain: tuple[str, ...]) -> None:
    path = SOURCE / entry
    for link in chain:
        text = path.read_text(encoding="utf-8")
        assert link in _local_links(text)
        path = path.parent / link
    shared = path.read_text(encoding="utf-8")
    assert "不得再把表当主视觉" in shared
    assert "run start image" in shared


@pytest.mark.parametrize("relative", ["references/page-writing.md", "deck-design.md"])
def test_table_choice_is_not_a_title_or_block_type_ban(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    policy = next((line for line in text.splitlines() if "自动禁表" in line), "")
    assert all(title in policy for title in ("封面", "流程", "阶段", "计划", "分工"))
    assert re.search(r"不按[^。]*自动禁表", policy)
    writing = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    assert re.search(r"`table`[^。]*不自动等于[^。]*画面[^。]*表格", writing)


def test_lookup_and_state_flow_examples_keep_their_distinct_jobs() -> None:
    text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    lookup_start = text.index("读者要按行找到要求、响应和展开位置")
    state, lookup = text[:lookup_start], text[lookup_start:]
    assert "原模块表仅作取材" in state
    assert "正文按关系重组" in state
    assert "无空位进入排队" in state
    assert "| 要求 | 响应要点 | 展开位置 |" in lookup
    assert "读者要按行找到要求、响应和展开位置" in lookup
    visual = (SOURCE / "references/content-to-visual.md").read_text(encoding="utf-8")
    assert re.search(r"查阅页[^；。]*逐行核对[^；。]*留表", visual)
    assert re.search(r"比较和查阅[^。]*可以[^。]*表为主视觉", visual)
    system = (SOURCE / "references/design-system.md").read_text(encoding="utf-8")
    assert re.search(r"查阅页[^。]*保留逐行核对和定位所需的表格", system)


def test_examples_distinguish_lookup_from_proof_and_operation() -> None:
    text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    acceptance = next((line for line in text.splitlines() if "条款 → 证据" in line), "")
    assert all(token in acceptance for token in ("验收", "逐行勾对", "可留表", "证明过程", "责任交接", "表不当主视觉"))
    fields = next((line for line in text.splitlines() if "看板口径" in line), "")
    assert all(token in fields for token in ("模板对照", "字段", "清单", "可留表", "结构", "运转", "表不当主视觉"))
    assert re.search(r"例子[^。]*不是封闭名单", text)


def test_review_routes_declared_relation_table_contradiction_to_design() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    policy = next((p for p in re.split(r"\n\s*\n", text) if "查阅表为主视觉" in p), "")
    assert all(token in policy for token in ("purpose", "layout", "时间线", "交接", "状态流", "闭环", "导出", "构图"))
    assert re.search(r"记为选错主视觉[^。]*交设计", policy)
    protection = next(line for line in text.splitlines() if "不因是表格" in line)
    assert all(token in protection for token in ("查阅页", "要求响应矩阵", "逐行核对", "保留查阅效率", "封面", "判失败"))
