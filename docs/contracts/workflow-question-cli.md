# Local forcing-question commands

`workflow questions --run-dir RUN` returns the current stage's unanswered forcing
questions (including optional questions) and its `input_fingerprint` token.
`workflow answer --run-dir RUN --stage-id STAGE --question-id ID --answer-json JSON
--source-type SOURCE --actor-id ID --actor-role ROLE --input-fingerprint TOKEN`
records an answer through the existing revision transaction and DecisionLog schema.
Re-read questions after each write. Unknown/resolved questions, stale inputs,
non-current stages, and disallowed authority are rejected without a decision write.

Authority comes from the existing `skills/stage-contracts.json` forcing-question
fields and `QuestionResolver.validate_answer_authority`. This local adapter accepts
`user` source only with explicitly declared `user` role, or `agent_assumption`
source only with `agent` role when assumptions are permitted. Agent assumptions
cannot fill user-reserved questions. Questions requiring evidence cannot be
resolved by a plain answer through this adapter; arbitrary references are not
accepted as verified document evidence. Other source types are rejected.

Actor id/role are local caller declarations, **not authenticated remote identities**.
Agents must not invent user statements or label their own inference as user input.
A synthetic test user is only a test fixture, not a customer approval. These commands
do not grant visual, file, or delivery approval. Boolean/yes-no questions accept
explicit negative answers; uninformative open answers retain follow-up status.
