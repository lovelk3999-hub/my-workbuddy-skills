# HAI FLF2V Runner

Portable Tencent Cloud HAI skill for Wan2.1 first-last-frame video generation through ComfyUI.

It performs the complete local-to-cloud lifecycle: start HAI, restrict video ports to the active computer, submit frames and prompt, poll ComfyUI history, download and convert the result locally, clear remote output, and stop the instance.

See [SKILL.md](SKILL.md) for installation, one-command usage, recovery, and multi-computer handoff.

Private configuration is intentionally excluded from Git. Start with `config/haimgr.example.json` and create a local `config/haimgr.json`.
