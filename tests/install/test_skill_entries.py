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


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    assert match, heading
    return match[1]


def _has(text: str, *patterns: str) -> None:
    for pattern in patterns:
        assert re.search(pattern, text, re.DOTALL), pattern


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
        policies = [p for p in paragraphs if re.search(rf"{role}(?:页|页面)", p)]
        assert any(
            "标题" in policy and "CTA" in policy
            and re.search(r"不(?:强制|要求|必)|无[需须]", policy)
            for policy in policies
        ), f"{relative}: {role} pages need title and CTA exceptions"
    assert re.search(r"判断页.{0,30}判断句", text)
    assert re.search(r"查阅页.{0,30}查阅职责", text)


@pytest.mark.parametrize("relative", ["deck-review.md", "references/method-review.md"])
def test_review_guidance_separates_qa_layers(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    qa = _section(text, "三层 QA")
    _has(qa, r"Q1.*业务.*语义", r"Q2.*保真.*可读", r"Q3.*可编辑.*Office", r"独立")
    if relative == "deck-review.md":
        assert "references/method-review.md#三层-qa" in LINK.findall(qa)
    else:
        _has(qa, r"不能.*(?:boolean|布尔)", r"status=pass.*不(?:等于|代表|证明)")
        _has(qa, r"visual_review", r"desktop_editing", r"not_evaluated", r"未执行")


def test_review_entry_requires_located_graded_evidence() -> None:
    entry = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    report = _section(entry, "怎样返回")
    _has(report, r"页.*(?:对象|区域)", r"问题", r"影响", r"建议", r"分级", r"依据", r"原句", r"没有验证|未验证")
    method = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    grades = _section(method, "缺陷分级")
    for grade, example in (("Critical", "事实|数字"), ("Major", "主视觉|失真"), ("Minor", "位置|行距")):
        item = re.search(rf"`{grade}`([\s\S]*?)(?=^- |\Z)", grades, re.MULTILINE)
        assert item, grade
        _has(item[1], example)


def test_review_consumes_supported_readback_findings_without_inventing_edges() -> None:
    entry = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    _has(entry, r"先.*findings.*再.*(?:阅图|画面)")
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
    _has(method, r"(?:没有|缺少)预期边.*(?:未检查|依据不足)")
    _has(method, r"不.*layout.*边")
    _has(method, r"不.*(?:编造|发明).*code")
    _has(_section(method, "三层 QA"), r"bbox.*pixel diff.*定位", r"不是唯一判断依据")


def test_review_requires_separate_blueprint_and_ppt_evidence() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    evidence = _section(text, "内容、主视觉与成品")
    for artifact in ("原图", "最终 PPT"):
        paragraphs = [p for p in re.split(r"\n\s*\n", evidence) if artifact in p]
        assert any("证据" in p and "未执行" in p for p in paragraphs), artifact
    _has(evidence, r"证据.*不能互相替代")


def test_review_protects_lookup_comparisons_and_synthetic_numbers() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    _has(text, r"查阅.*表.*(?:保留|保护)", r"E02.*同一.*口径", r"(?:合成|教学).*数字.*不能.*项目事实")


def test_master_turns_feedback_into_four_local_repair_paths() -> None:
    text = (SOURCE / "deck-master.md").read_text(encoding="utf-8")
    routes = dict(re.findall(r"^- (内容|设计|调用|重建)：([\s\S]*?)(?=^-[ ]|^## |\Z)", text, re.MULTILINE))
    assert set(routes) == {"内容", "设计", "调用", "重建"}
    _has(routes["内容"], r"正文", r"purpose", r"layout", r"notes", r"deck put --base", r"不.*自动.*生图")
    _has(routes["设计"], r"主视觉", r"视觉计划", r"必要.*调用")
    _has(routes["调用"], r"需要新蓝图", r"deck run start image --pages", r"task.md.*原文", r"attachments.json")
    _has(routes["重建"], r"蓝图.*可用.*直接修 SVG", r"主结构.*蓝图.*重建")
    assert "references/reconstruction.md" in _local_links(routes["重建"])


def test_design_can_enter_svg_repair_without_new_image() -> None:
    text = (SOURCE / "deck-design.md").read_text(encoding="utf-8")
    production = _section(text, "主视觉与制作")
    _has(production, r"蓝图.*可用.*直接.*SVG", r"需要新蓝图.*生图")
    steps = re.findall(r"^[12]\. (.+)$", production, re.MULTILINE)
    assert len(steps) == 2
    assert all("需要新蓝图时" in step for step in steps)


def test_review_routes_submission_faults_separately_from_design() -> None:
    text = (SOURCE / "deck-review.md").read_text(encoding="utf-8")
    report = _section(text, "怎样返回")
    _has(report, r"task.md.*附件.*正确", r"实际调用.*(?:改写|漏传).*交调用")
    _has(report, r"task.md.*原文", r"attachments.json.*提交", r"主视觉.*交设计")


def test_repair_rereview_links_to_existing_qa_judgments() -> None:
    text = (SOURCE / "deck-master.md").read_text(encoding="utf-8")
    rereview = next(p for p in re.split(r"\n\s*\n", text) if "复审" in p)
    _has(rereview, r"只.*复审.*受影响.*范围")
    qa = next(link for link in LINK.findall(rereview) if link.startswith("references/method-review.md#"))
    path, anchor = qa.split("#", 1)
    method = (SOURCE / path).read_text(encoding="utf-8")
    heading = next(h for h in re.findall(r"^## (.+)$", method, re.MULTILINE) if h.lower().replace(" ", "-") == anchor)
    target = _section(method, heading)
    _has(target, r"Q1.*业务", r"Q2.*视觉", r"Q3.*Office", r"独立")


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
    criteria = next(p for p in re.split(r"\n\s*\n", text) if "评标矩阵" in p)
    _has(criteria, r"出现.*(?:不等于|不代表).*查阅页", r"能画成.*(?:不是.*留表.*理由|不(?:代表|意味着).*禁表|仍可留表)")
    _has(criteria, r"评标矩阵.*必须留表.*逐[行条]", r"不是封闭名单")
    _has(text, r"读者必须按行.*(?:勾选|定位|查找)", r"查阅职责.*标题.*不等于.*网格")


@pytest.mark.parametrize("relative", [
    "SKILL.md", "references/page-writing.md", "references/content-to-visual.md",
])
def test_declared_relations_require_body_rewrite_before_image_run(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    if relative.endswith("content-to-visual.md"):
        assert "page-writing.md#构图句写出本页的空间逻辑" in LINK.findall(text)
        text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
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
    examples = re.findall(r"^- ([\s\S]*?)(?=^- |^## |\Z)", text, re.MULTILINE)
    for topic in ("验收：", "看板口径"):
        example = next(item for item in examples if topic in item)
        _has(example, r"(?:勾对|核对).*可留表", r"(?:过程|运转).*表不当主视觉")
    _has(text, r"例子.*不是封闭名单")
    example = next(p for p in re.split(r"\n\s*\n", text) if "交接清单" in p)
    _has(example, r"标题", r"逐[行条].*(?:勾对|核对)", r"layout.*表是主视觉.*可留表")


def test_review_routes_declared_relation_table_contradiction_to_design() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    policy = next(p for p in re.split(r"\n\s*\n", text) if "查阅表为主视觉" in p)
    _has(policy, r"purpose", r"layout", r"选错主视觉.*交设计")
    assert "page-writing.md" in _local_links(policy)
    protection = next(p for p in re.split(r"\n\s*\n", text) if "不因是表格" in p)
    _has(protection, r"查阅.*保留查阅效率", r"不因.*表格.*判失败")


@pytest.mark.parametrize("entry", ["SKILL.md", "deck-design.md", "deck-master.md"])
def test_reconstruction_entries_share_object_preservation_rules(entry: str) -> None:
    text = (SOURCE / entry).read_text(encoding="utf-8")
    assert "references/reconstruction.md" in _local_links(text)
    shared = (SOURCE / "references/reconstruction.md").read_text(encoding="utf-8")
    policy = shared.split("\n## ", 1)[0]
    _has(policy, r"原图.*对象和关系", r"不是.*正文块类型.*默认", r"说明文字.*不算还原")


def test_ui_annotations_keep_atoms_outside_and_controls_inside() -> None:
    ui = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "界面原型")
    _has(ui, r"内部必须出现.*对应控件", r"不留空白线框")
    _has(ui, r"外侧.*标注.*绑定.*atom", r"内部.*可编辑控件", r"不能.*说明句.*唯一内容")
    _has(ui, r"不要求.*拆成多个 atom", r"不改 atom 结构")


@pytest.mark.parametrize("relative", ["references/reconstruction.md", "references/visual-assets.md"])
def test_ui_nontext_assets_survive_with_editable_text_and_illustrative_status(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    _has(text, r"头像", r"SVG 子集.*重画", r"有边界的局部 PNG/JPEG", r"asset add", r"image")
    _has(text, r"关键文字.*可编辑", r"(?:截图|截取).*生成|生成.*截取")
    _has(text, r"示意属性.*不能冒充真实产品截图", r"只有框架和关键字.*不等于完成")
    if relative.endswith("reconstruction.md"):
        _has(text, r"先登记局部图.*再准备 SVG 任务", r"补图.*重新准备任务.*attachments.json")
    else:
        _has(text, r"主正文.*原生对象", r"选用前.*不得.*删掉")
        assert "优先保留可编辑的关键文字与框架" not in text


def test_journeys_keep_spatial_order_and_action_scene_layer() -> None:
    text = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "旅程与有方向的步骤")
    _has(text, r"步骤的空间顺序", r"人物.*动作.*场景", r"重画.*有边界的局部图")
    _has(text, r"不能.*模块卡片.*除非原图")


def test_directional_paths_keep_nodes_and_connections_with_lookup_exception() -> None:
    text = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "旅程与有方向的步骤")
    for token in ("节点边界", "连线端点", "方向", "分支", "回流"):
        assert token in text
    _has(text, r"不能.*箭头.*句子", r"没有空间方向.*清单", r"只有原图.*查阅清单.*逐[行条]核对")
    _has(text, r"构图句.*表是主视觉", r"purpose.*layout.*不得把表当主视觉", r"不按.*标题.*禁表")


def test_sentence_text_rule_cannot_collapse_multiple_visible_objects() -> None:
    text = (SOURCE / "references/svg-subset.md").read_text(encoding="utf-8")
    _has(text, r"句子型正文.*一个 text", r"保留完整句子", r"不在词中间硬折行")
    policy = next(p for p in re.split(r"\n\s*\n", text) if "多个可见对象" in p)
    _has(policy, r"多个入口", r"多个步骤节点", r"不要求.*整段塞进空框")
    _has(policy, r"外侧.*绑定原 atom", r"内侧重画.*可编辑文字", r"不要.*唯一一块字")


@pytest.mark.parametrize("relative", [
    "SKILL.md", "references/reconstruction.md", "references/method-review.md",
])
def test_reconstruction_acceptance_requires_actual_object_comparison(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    _has(text, r"实际打开.*预览.*原图", r"文字(?:回读|覆盖)", r"字符串齐全", r"(?:不能|未对照).*?(?:比对|对象|重建通过)")
    assert "重建未完成" in text
    if relative != "references/reconstruction.md":
        target = "references/reconstruction.md" if relative == "SKILL.md" else "reconstruction.md"
        assert f"{target}#对照原图验收" in LINK.findall(text)


def test_original_comparison_checks_screen_journey_and_path_objects() -> None:
    text = (SOURCE / "references/reconstruction.md").read_text(encoding="utf-8")
    acceptance = _section(text, "对照原图验收")
    for kind, behavior in (
        ("通用", r"阅读顺序.*说明文字"),
        ("界面原型", r"屏幕结构.*分区说明句"),
        ("顾客旅程", r"空间顺序.*人物动作或场景"),
        ("路径／步骤", r"连线端点.*对应对象"),
    ):
        item = re.search(rf"^- {kind}：([\s\S]*?)(?=^- |\Z)", acceptance, re.MULTILINE)
        assert item, kind
        _has(item[1], behavior)
    _has(acceptance, r"原图／编译预览对照", r"不新增自动视觉评分")
    _has(acceptance, r"visual_review", r"desktop_editing", r"not_evaluated", r"不能.*自动通过")


def test_reconstruction_retains_background_and_zero_picture_protections() -> None:
    text = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "同时满足可编辑与画面保真")
    _has(text, r"禁止.*方便转 SVG.*扁平色块", r"禁止.*整页蓝图.*背景")
    _has(text, r"禁止.*pictures=0.*普通矩形", r"pictures=0.*不是目标.*不是失败", r"对象计数和图片数不能代表质量")
