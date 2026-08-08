# High-Density Builder v2 Provider Smoke

Status: `historical-pass`, superseded for the v3 release gate

Date: 2026-08-05

The smoke used one fresh sanitized ImageGen output and completed the full
high-density chain on page `P001`:

This evidence predates the runtime-generated Provider challenge. It remains
useful as historical route evidence, but it cannot satisfy the current fresh
provider release gate. The current gate requires a new request bound to the
prompt nonce, request hash, timestamps, image, Scene, SVG, PPTX, and readback.

```text
prompt -> blueprint -> native SVG -> DrawingML PPTX -> visual parity -> readback
```

## Provider And Lineage

| Field | Sanitized value |
| --- | --- |
| provider tool | `codex.image_gen` |
| provider model | `fresh-imagegen-runtime` |
| run id | `sha256:33538da2b6713a46af50a7863a02dcdd6ed33d0797a52248b6b03e1ff9750b38` |
| prompt | `af17eca7527983ec0776e20df249319371255f84d1dfd1a448a5c822be918886` |
| image | `f114dcfb9513bb9b1714a3fa0689b4163a8c174c93d4076984d272018a902383` |
| content lock | `8e980f36956f3c1919b9deb43f9d6a5dfec639103ca365f3814760b1e6a6573b` |
| NBB plan | `48e5568d7bb8ad03794e9dd3a73aeac7414abc908b28173a8ffbc90e2e7b90d3` |
| style lock | `2ebfb0610012ab692e437cbe4c6734d240afd619e1335fc816f4eb6cb31c3de3` |

The provider request ID is retained only as a hash in the generated smoke
evidence. Raw provider payloads, the generated image, and the temporary run
directory are excluded from the repository.

## Gate Results

| Gate | Result |
| --- | --- |
| high-density manifest | `pass` |
| blueprint to SVG text-masked SSIM | `0.9312367` |
| blueprint to SVG P0 region SSIM | `0.9277791` |
| blueprint to SVG max bbox delta | `0 px` |
| SVG to PPTX text-masked SSIM | `0.9706456` |
| SVG to PPTX P0 region SSIM | `0.9815166` |
| SVG to PPTX max bbox delta | `0.000133 px` |
| visual review | `pass` |
| DrawingML readback | `pass` |
| raw provider payload included | `false` |

The machine-readable evidence is produced by
`high_density.provider_smoke` and contains only relative artifact paths,
artifact hashes, provider metadata hashes, lineage hashes, and gate results.
