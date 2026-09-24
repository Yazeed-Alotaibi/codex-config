# Local Kev server

The skill/client is installed locally; a model server is a separate component. It is **not** installed or started by `scripts/install_kev.py`. These steps are for the user's actual computer, not a cloud agent sandbox. Do not silently replace local inference with Hugging Face hosting.

## Requirements and source

- Git, uv, and Python 3.12 or 3.13 (upstream requires >=3.12,<3.14).
- The first model start downloads checkpoint/base weights. Model cache, memory and accelerator requirements are separate from this small skill.
- Inspected upstream: https://github.com/jaredpalmer/kev
- Pinned source revision: `badd506d71399f536a09bba7ad5dd663adb104d2`
- Upstream source license: Apache-2.0. Review the selected model/base licenses separately.

Use a new dedicated directory. Do not reset an existing checkout that has changes.

```bash
git clone https://github.com/jaredpalmer/kev.git kev-runtime
cd kev-runtime
git checkout --detach badd506d71399f536a09bba7ad5dd663adb104d2
uv sync --python 3.12 --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009
```

Run each step only if the preceding step succeeds. If uv is missing, use its official installation guidance: https://docs.astral.sh/uv/getting-started/installation/ . The upstream launcher selects an available backend; this integration does not claim CUDA compatibility or throughput was verified on the user's GPUs. Inspect metadata and the actual device before claiming GPU execution.

The server binds to 127.0.0.1. Keep its terminal running while using it. Stop with Ctrl+C. From another terminal, run this skill's client:

```bash
python scripts/kev_client.py check
python scripts/kev_client.py decide --state-file references/example-state.txt --questions-file references/example-questions.json
```

Resolve these paths relative to the installed skill directory. `GET /v1/models` exposes available model/backend metadata. Record actual checkpoint/backend/dtype/temperature values when returned; do not infer successful model loading just from installed files.

## Windows and WSL

The client/installer are portable Python. Upstream inference/dependencies still need testing on the actual Windows environment. If serving from WSL, run the check from the same environment first. Windows and WSL have separate home directories and may need separate skill installs. Do not assume localhost forwarding works without checking.

For an alternate loopback port, set `KEV_BASE_URL` or pass `--url http://127.0.0.1:PORT`. A remote native server requires HTTPS and explicit `--allow-remote`; a local tunnel is another option. A cloud n8n instance's localhost is not the user's PC.

Set `KEV_API_KEY` in both server and client environments if native authentication is needed. Do not commit it. The server's default calibration is checkpoint-fitted. `KEV_TEMPERATURE=1.0` selects raw probabilities; `KEV_DATE_FACTS=1` enables date preprocessing. Changing those is a deliberate experiment, not an accuracy guarantee.

No auto-start service, firewall rule, remote computer access, model download, or cloud fallback is created by the skill installer. Inference stays on the local Kev server, but results read by cloud Codex/Claude may be sent to those providers.
