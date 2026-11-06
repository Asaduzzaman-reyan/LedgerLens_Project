# Verified local AI setup

Live extraction was exercised with the official Qwen2.5-0.5B-Instruct Q4_K_M model through llama.cpp b6000 on CPU, using two threads, a 4,096-token context and one slot. No API key or hosted inference was used. This small model is suitable for demonstrating the integration; its results do not establish production quality.

The 3-file smoke evaluation extracted 23 of 24 first-invoice header fields correctly after grounding checks (95.83%). Both digital fixtures scored 8/8; the degraded scan scored 7/8. All three calls returned valid schema-constrained results. The prompt/schema were developed on these fixtures, so this is a development smoke set, not a held-out accuracy benchmark. `reports/live-llm-evaluation.json` includes full results and validation flags. `reports/live-llm-api.json` records a real upload-to-worker-to-model-to-database check.

## On the prepared machine

From PowerShell, run the `Start-LedgerLens-AI.ps1` file beside this repository. It starts the model on loopback port 8081 in a hidden helper process, then starts the application on loopback port 8000. Stopping the launcher stops the owned model process. The plain `Start-LedgerLens.ps1` starts the default rules demo. These convenience launchers refer to the prepared sibling `work/` environment and are not portable setup scripts.

## Portable reproduction

1. Install the app dependencies using the README.
2. Obtain an official Windows CPU build of [llama.cpp](https://github.com/ggml-org/llama.cpp/releases/tag/b6000), or an equivalent build for your OS.
3. Download [the official Qwen GGUF model](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/main/qwen2.5-0.5b-instruct-q4_k_m.gguf).
4. Start the model server, adjusting the executable/model paths:

```powershell
.\llama-server.exe -m .\qwen2.5-0.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8081 -c 4096 -np 1 -t 2 -b 128 --alias local-qwen
```

5. In another shell, configure the application:

```powershell
$env:DOCINT_EXTRACTOR='llm'
$env:DOCINT_LLM_URL='http://127.0.0.1:8081/v1/chat/completions'
$env:DOCINT_LLM_MODEL='local-qwen'
$env:DOCINT_LLM_SCHEMA='1'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

6. Run `python scripts/evaluate_llm_smoke.py` with the same variables to reproduce the small live check. Use `python scripts/evaluate.py` to evaluate the broader fixture set, but first preserve the existing rules evaluation JSON because this script overwrites it.

`DOCINT_LLM_SCHEMA=1` enables llama.cpp's JSON-object schema extension. Leave it at zero for a provider that does not support that extension. Both modes validate all responses and withhold unsupported values. Generation is capped at 2,048 output tokens with a 90-second HTTP timeout; larger/complex units may fail and require splitting or a different provider configuration. The 24,000-character input guard is an upper bound, not a guarantee that a selected model's context fits that unit.

The authoring Windows environment needed Visual C++ runtime DLLs colocated with the server. Current b12099 initially crashed; the verified b6000 build worked after the DLL dependency was resolved. Model binaries and weights are kept outside the source repository. `reports/local-model-provenance.json` records the model download and hash; the model size is about 491 MB. A separately installed compatible Ollama service remains supported through the default JSON mode described in the README.
