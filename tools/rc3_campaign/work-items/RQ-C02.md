# RQ-C02: native proposal identity across layers

The campaign adapter rejected repeated proposal Refs globally. The public
input-revision consumer permits an existing Page's valid complete object in
both page_copy and speech. Its uniqueness rules apply within each layer.

The adapter now checks the entire collection before storage: Narrative and Plan
are singletons, and Page proposals are unique by page_id within each layer.
Different Refs for one Page across copy/speech remain legal. One frozen sidecar
per distinct new canonical object is stored once. Canonical Ref, original-byte,
Task binding, extra/missing object and layer checks remain in force.

Engineering checks must prove actual SDK acceptance for an existing Page with
shared Ref and with separate copy/speech Refs, rejection of layer-local
duplicates before any project write, and unchanged SDK refusal of new-Page
speech or speech body changes. A separately authorized new Page may carry its
initial notes through page_copy. Explicit synthetic observation seams are only
engineering evidence and do not establish native admission or content quality.

The earlier neutral run remains a failed engineering attempt: its actual result
also violated the unchanged SDK rule that speech cannot add a Page. This fix
does not validate that manuscript, erase its two native calls, or mutate its
Task. The new public layer supplement requires independent review and symmetric
dispatch in a fresh registration before new native outputs. Root completes
fresh native admission after the exact fixed commit passes independent review.
