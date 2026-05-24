"""Generic NVIDIA Triton (KServe v2) adapter — J-26 deliverable.

Distinct from the TensorRT-LLM adapter in adapters/tensorrt/. This
adapter targets generic Triton workloads (non-LLM, multimodal,
embedding, classifier, custom models) via the KServe v2 HTTP protocol.
"""
