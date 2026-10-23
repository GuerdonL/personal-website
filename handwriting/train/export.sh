#!/usr/bin/env bash
# Export the fine-tuned model to ONNX for transformers.js, then push it to the Hugging Face hub.
#   pip install "optimum[onnxruntime]" huggingface_hub
#   ./export.sh model GuerdonL/trocr-guerdon
set -euo pipefail
SRC=${1:-model}; REPO=${2:?hub repo id, e.g. GuerdonL/trocr-guerdon}
optimum-cli export onnx --model "$SRC" --task image-to-text-with-past "$SRC"/onnx_export
mkdir -p "$SRC"/hub/onnx
cp "$SRC"/onnx_export/encoder_model.onnx "$SRC"/hub/onnx/
# transformers.js wants decoder_model_merged.onnx; optimum names it that when it can merge
cp "$SRC"/onnx_export/decoder_model_merged.onnx "$SRC"/hub/onnx/ 2>/dev/null || cp "$SRC"/onnx_export/decoder_model.onnx "$SRC"/hub/onnx/decoder_model_merged.onnx
# int8 encoder keeps the download small; the decoder stays fp32 (int8 decoders degrade)
python - "$SRC" <<'PY'
import sys, pathlib
from onnxruntime.quantization import quantize_dynamic, QuantType
d = pathlib.Path(sys.argv[1]) / 'hub' / 'onnx'
quantize_dynamic(str(d / 'encoder_model.onnx'), str(d / 'encoder_model_quantized.onnx'), weight_type=QuantType.QUInt8)
PY
for f in config.json generation_config.json preprocessor_config.json tokenizer.json tokenizer_config.json vocab.json merges.txt special_tokens_map.json; do
  [ -f "$SRC/onnx_export/$f" ] && cp "$SRC/onnx_export/$f" "$SRC"/hub/ || true
done
huggingface-cli upload "$REPO" "$SRC"/hub . --repo-type model
echo "done → set the model id on /handwriting to $REPO"
