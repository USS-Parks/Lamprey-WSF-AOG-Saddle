"""MAI ONNX Runtime adapter.

In-process inference for CPU / DirectML / CUDA via Microsoft ONNX Runtime.
Generation is wrapped through onnxruntime-genai when the loaded model
supports autoregressive decoding; otherwise the adapter degrades to
embedding-only and raises UnsupportedOperationError for generation.

DOUGHERTY J-24 deliverable.
"""

from adapters.onnxruntime.adapter import OnnxRuntimeAdapter
from adapters.onnxruntime.config import OnnxRuntimeConfig

__all__ = ["OnnxRuntimeAdapter", "OnnxRuntimeConfig"]
