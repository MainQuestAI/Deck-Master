import {canonical} from './api.js';
// Called only after BusinessOperations has verified the original receipt.
export function rememberAnnotation(draft, pending, result) {
  const context = pending.payload.display_context;
  const submission = draft.content.annotation_submission;
  if (!context?.annotation_draft_key || submission?.draft_key !== context.annotation_draft_key) return;
  submission.confirmed = {
    input_key: canonical(pending.payload.request.input), operation_id: pending.operation_id,
    annotation_refs: (result.annotations || []).map(item => item.ref).filter(Boolean)
  };
}
