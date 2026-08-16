# Two-Panel Lesson Player (Remotion)

Data-driven Remotion composition that plays each day's generated lesson as a
"TwoPanel HTML preview — kinetic text + TTS" video in the browser
(`docs/decisions.md` D8 — JS playback, no MP4).

## Layout

- `src/TwoPanelLesson.tsx` — the composition (input props: `{title, script, key_points, voiceover}`)
- `src/index.tsx` — mounts `@remotion/player` `<Player>` from `window.__LESSON_PROPS__`
- `../static/video/lesson-player.js` — the **pre-built bundle** Flask serves (committed)

## Rebuild

The committed bundle is built once with esbuild; no Node toolchain is needed
at runtime/deploy. To rebuild after editing the composition:

```bash
# node_modules (gitignored) — either `npm install` here, or link the
# skill project's deps: ln -s /path/to/SystemDesig/video-project/node_modules node_modules
npm run build   # writes ../static/video/lesson-player.js
```
