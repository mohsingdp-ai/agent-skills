# video-editing

Make videos as code. 9 skills from 8 open-source repos (all MIT), in one plugin.

| Skill | What it does | Needs |
| :--- | :--- | :--- |
| `huashu-motion` | Motion graphics, launch videos, explainers; point at a frame to change it | Node 22+ (runs `npx huashu-motion`) |
| `rossark-motion-skill` | Calm, believable character/object animation (blinks, breathing, waves) | — (SwiftUI examples) |
| `take-one` | Short film from a one-line request, studio-style (script, voice, storyboard, render) | Node, Chrome |
| `reanimate` | Clone an animation/section from a URL, video, gif or Lottie frame by frame | Node, ffmpeg |
| `argo-guide` | Product demo videos from Playwright scripts, with voiceover and overlays | `@argo-video/cli`, ffmpeg |
| `explainroo` | Explainer MP4 with local voice-over, no API key | explainroo CLI, ffmpeg, Chrome |
| `video-director` | Direct, build and check code-rendered videos (HTML/Canvas/GSAP/Remotion) | Node, ffmpeg |
| `earshot` | Lets the agent "hear": pick, trim, check sound and mixes | earshot (Python) |
| `real-sound` | Real-recording soundtracks for code-made videos | earshot |

Exact upstream commits: [UPSTREAM.md](UPSTREAM.md).

## Install

```bash
./install.sh
```

Invoke as `video-editing:<skill-name>`, e.g. `video-editing:take-one`.

## Update from upstream

```bash
./update.sh
```

Re-copies every skill from its repo and refreshes the installed plugin. Demo `.mp4`/`.gif` files are skipped to keep the repo small.

### Weekly auto-update (optional)

A systemd user timer (`~/.config/systemd/user/video-editing-update.{service,timer}`) runs `update.sh` every Monday 10:00, or at next boot if missed. Changes land uncommitted; review with `git diff`.

```bash
systemctl --user list-timers video-editing-update.timer   # next run
journalctl --user -u video-editing-update.service          # last output
systemctl --user disable --now video-editing-update.timer  # turn off
```
