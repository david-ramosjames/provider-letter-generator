# Austin Car Accident Explainer — Production Package

A faceless ~5-minute YouTube explainer ("What To Do After a Car Accident in
Austin") for **Ramos James Law, PLLC**. All assets were generated with
Higgsfield. Voiceover uses the **Quinn** preset voice (ElevenLabs engine).

- **Runtime:** ~4:36 of narration (≈5 min finished, 16:9, 1920×1080)
- **Style:** cinematic, faceless documentary B-roll + Ken Burns stills + burned-in text
- **Total narration words:** ~820

> ⚖️ **Disclaimer to keep on the end card:** *Attorney advertising. General
> information, not legal advice. No attorney-client relationship is formed by
> watching. Ramos James Law, PLLC, Austin, TX.*

---

## How to build the finished MP4

This repo includes **`video/build_video.py`**, which downloads every asset and
stitches the complete video with ffmpeg (Ken Burns motion, B-roll, on-screen
text, Quinn narration).

```bash
cd video
pip install imageio-ffmpeg      # only if you don't already have ffmpeg
python3 build_video.py
# -> austin_car_accident_explainer.mp4
```

Run it on your own machine (or any host that can reach the Higgsfield CDN).
The Claude Code **web sandbox blocks that CDN by network policy**, which is why
the video is delivered as a one-command build script rather than stitched in
the session. If you'd rather I stitch it automatically inside a session, start
the session in an environment whose network policy allows
`d8j0ntlcm91z4.cloudfront.net` (see
https://code.claude.com/docs/en/claude-code-on-the-web) and re-run the request.

Prefer a manual edit? Drop the assets onto a CapCut/Premiere timeline using the
shot list below — each voiceover segment's duration is given so timing is exact.

---

## Timeline / Shot list

Total ≈ 276s. Each segment = one voiceover file; listed visuals split that
segment's duration evenly (the build script does this automatically).

| # | Time | VO segment (Quinn) | Dur | Visuals (in order) | On-screen text |
|---|------|--------------------|-----|--------------------|----------------|
| 1 | 0:00 | Hook | 19.4s | skyline drone (vid) → fender-bender → hazard lights (vid) → hazard button | "What To Do After a Car Accident in Austin" |
| 2 | 0:19 | Austin crash stats | 20.2s | I-35 drone (vid) → I-35 aerial → skyline | "Austin: ~26,000 crashes a year" |
| 3 | 0:40 | Step 1: Safe + 911 | 35.7s | dialing 911 → police cruiser (vid) → police still → fender-bender | "STEP 1 · Get Safe + Call 911" |
| 4 | 1:15 | Step 2: Document | 31.9s | photographing damage → exchanging info → fender-bender | "STEP 2 · Document Everything – Never Admit Fault" |
| 5 | 1:47 | Step 3: Doctor | 28.6s | sore neck → doctor + X-ray → medical bills | "STEP 3 · See a Doctor" |
| 6 | 2:16 | Step 4: Insurance | 33.6s | phone ringing → settlement check → policy doc | "STEP 4 · Beware Insurance Tactics" |
| 7 | 2:50 | Step 5: Hit-run/Uninsured | 42.0s | car speeding away (vid) → speeding still → policy doc → bills | "STEP 5 · Hit-and-Run or Uninsured? Use Your UM Coverage" |
| 8 | 3:32 | Texas law: fault + deadline | 28.1s | hourglass → scales of justice → I-35 | "Texas Law: 2-Year Deadline · 51% Fault Bar" |
| 9 | 4:00 | Lawyer + CTA | 36.6s | law office exterior → scales → end-card bg | "Ramos James Law · (512) 537-3369 · Free Consultation" |

---

## Voiceover script (final, as generated)

1. **Hook** — You just got into a car accident in Austin. Your heart is pounding, your hands are shaking, and a hundred questions hit you at once. Take a breath. What you do in the next few minutes, and the next few days, can protect your health, your rights, and your wallet. So let's walk through exactly what to do, step by step.
2. **Austin** — Austin sees around twenty-six thousand crashes every year, and traffic deaths have been climbing, more than a hundred in 2024 alone. Many happen on the roads you drive every day: Interstate 35, MoPac, Highway 183, Ben White, and East Riverside. If it happens to you, here is your game plan.
3. **Step 1** — Step one: get safe, and call 911. … That report becomes one of the most important documents in your case.
4. **Step 2** — Step two: document everything. … get their name and phone number before they leave.
5. **Step 3** — Step three: see a doctor, even if you think you're okay. … the insurance company will argue you weren't really hurt.
6. **Step 4** — Step four: be careful with the insurance companies. … report the crash within twenty-four to seventy-two hours.
7. **Step 5** — What if the other driver takes off, or has no insurance? … buy it online through Buy Crash dot com for about nine dollars.
8. **Texas law** — Two more things you need to know about Texas law. First, fault … Second, the deadline — two years from the date of the crash.
9. **Lawyer/CTA** — Finally: talk to a lawyer before you settle. … call Ramos James Law at 512-537-3369. Drive safe out there. And if this helped, hit subscribe.

(Full text of every segment is embedded in the generated audio and in the build script's prompts.)

---

## Asset URLs

Base: `https://d8j0ntlcm91z4.cloudfront.net/user_3EzxIVq9VFMb2Cd4RPKbDIM04tb/`
(All filenames are listed in `build_video.py` under `AUDIO`, `IMG`, and `VID`.)

- **Voiceover:** 9 × `.mp3` (Quinn) — keys `s1`–`s9`
- **Images:** 19 × stills (16:9) — skyline, fender-bender, I-35, hazard button, dial 911, police, photographing damage, exchanging info, sore neck, doctor, bills, phone ringing, check, speeding away, policy doc, hourglass, scales, office, end-card bg
- **Video B-roll:** 6 × 5s clips — hazard lights, police cruiser, car speeding away, skyline drone, I-35 drone

---

## Notes & options

- **Music:** add a soft, hopeful ambient/corporate bed at low volume in your
  editor. (Higgsfield's audio tool here does TTS only — no standalone music.)
- **Captions:** burn in subtitles for muted autoplay (the script adds the big
  step labels; full word-level captions are best added in CapCut/YouTube).
- **Upscale:** clips are 720p and stills are 1K; both can be upscaled to
  1080p/4K (Higgsfield `upscale_video` / `upscale_image`) if you want crisper.
- **Shorts cut:** a 60-second vertical version can be assembled from segments
  1, 3, and 9 reframed to 9:16.
