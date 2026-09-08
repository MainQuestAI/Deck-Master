"""Local CLI adapter for existing forcing questions and append-only decisions.

Actors are explicit local caller declarations, not authenticated remote identities.
Only user statements and permitted Agent assumptions are accepted by this adapter.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import uuid

from workflow.actions import revision_read, revision_input_path, stage_action_result, commit_action_result
from workflow.decisions import DecisionLog
from workflow.questions import QuestionResolver
from workflow.state import resolve_workflow_state


def _current(root):
    with revision_read(root) as revision:
        view = revision_input_path(root, root / "request.json").parent
        resolver = QuestionResolver()
        stage = resolve_workflow_state(view, run_id=root.name)['current_skill_stage']
        contract = resolver.registry.contract(stage)
        stage_fp = resolver.input_fingerprint(contract, view)
        questions = [asdict(q) for q in resolver.gaps(view, stage, include_optional=True)]
        files = {}
        for name in ['request.json', 'workflow/decision_log.jsonl']:
            path = view/name
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        # The revision pins every input, including explicit question dependencies.
        token = hashlib.sha256(json.dumps([revision, stage, stage_fp, files], sort_keys=True).encode()).hexdigest()
        return {'stage_id':stage, 'input_fingerprint':token, 'questions':questions}, view, resolver, contract, stage_fp, revision


def read_questions(root):
    return _current(Path(root).resolve())[0]


def answer_question(root, *, stage_id, question_id, answer, source_type, actor, input_fingerprint):
    root = Path(root).resolve()
    def validate():
        state, view, resolver, contract, stage_fp, revision = _current(root)
        if state['stage_id'] != stage_id:
            raise ValueError('answer stage is not the current workflow stage')
        if state['input_fingerprint'] != input_fingerprint:
            raise ValueError('stale question input fingerprint; read current questions again')
        if question_id not in {q['question_id'] for q in state['questions']}:
            raise ValueError('unknown or already answered current question')
        question = next(q for q in contract.forcing_questions if q['question_id'] == question_id)
        role = str(actor.get('role') or '')
        if not str(actor.get('id') or '').strip():
            raise ValueError('explicit local actor id required')
        if source_type == 'user':
            if role != 'user':
                raise ValueError('user source requires explicitly declared local user actor')
        elif source_type == 'agent_assumption':
            if role != 'agent' or not question.get('assumption_allowed'):
                raise ValueError('question does not permit this Agent assumption')
        else:
            raise ValueError('unsupported answer source; document evidence needs verified binding')
        resolver.validate_answer_authority(question, role)
        if question.get('evidence_required'):
            raise ValueError('this question requires verified external evidence; plain answer is insufficient')
        boolean = (question.get('answer_schema') or {}).get('type') == 'boolean' or question.get('prompt','').startswith(('是否','有无','有没有'))
        if isinstance(answer,bool) and not boolean:
            raise ValueError('boolean answer is uninformative for this open question')
        schema = question.get('answer_schema')
        if schema:
            import jsonschema
            jsonschema.validate(answer, schema)
        return state, view, resolver, question, stage_fp, revision
    state, view, resolver, question, stage_fp, revision = validate()
    decision = DecisionLog().record(view, run_id=root.name, stage_id=stage_id, question_id=question_id,
        answer=answer, actor=actor, required=bool(question.get('required')), assumption_allowed=bool(question.get('assumption_allowed')),
        input_fingerprint=stage_fp, source_type=source_type, category=question.get('category',''), persist=False)
    path = view/'workflow/decision_log.jsonl'
    existing = path.read_text() if path.exists() else ''
    if existing and not existing.endswith('\n'):
        existing += '\n'
    content = existing + json.dumps(decision, ensure_ascii=False) + '\n'
    action = 'question_'+uuid.uuid4().hex
    envelope = {'schema_version':'deck_stage_action.v1','action_id':action,'task_id':'workflow_question_answer','scope_pages':['workflow_questions'],'permission':'runtime','input_fingerprint':input_fingerprint}
    stage_action_result(root, envelope, {'decision_log':content})
    def locked_check():
        validate()  # commit invokes this under the existing run transaction lock
        return input_fingerprint
    receipt = commit_action_result(root, envelope, current_input_fingerprint=locked_check,
        targets={'decision_log':root/'workflow/decision_log.jsonl'}, expected_revision=revision or '',
        receipt_data={'decision_id':decision['decision_id']})
    return {'status':'recorded','decision':decision,'receipt':receipt,'remaining':read_questions(root)}
