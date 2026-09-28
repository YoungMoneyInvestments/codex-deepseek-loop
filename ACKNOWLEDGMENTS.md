# Acknowledgments

- **[claudex-loop](https://github.com/chaseai-yt/claudex-loop)** (Chase AI, MIT): the four-phase workflow, the structured review schema, plan-hash approval binding and change-manifest snapshot patterns used here are adapted from claudex-loop. This project keeps that architecture and replaces the second coding CLI with the DeepSeek API as the reviewer transport — no interactive CLI review sessions, no second subscription.
- **[DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)** (DeepSeek AI, MIT license): the reviewer model. Weights are open; the runner talks to the hosted API by default.
- **Claude Code** (Anthropic) and **Codex** (OpenAI): the host environments the loop runs inside. This project is not affiliated with or endorsed by Anthropic, OpenAI, DeepSeek or Chase AI.
