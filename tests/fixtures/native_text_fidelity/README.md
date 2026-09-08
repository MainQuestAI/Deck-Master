# Native text fidelity regression

Public synthetic retail architecture from the real two-page ImageGen cold-start
acceptance run. SVG and Scene are the actual host reconstruction inputs, retained
byte-for-byte. No image, private customer material, or approval is included.

The four card captions deliberately use two visual lines while the Content Lock
semantic string has no newline. The compiler previously flattened these lines
and discarded per-line x positions. This fixture verifies the actual production
parser and native textbox output; it is not a substitute for ImageGen acceptance
or final human visual review.
