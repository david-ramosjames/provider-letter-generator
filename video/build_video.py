#!/usr/bin/env python3
"""
Austin Car Accident Explainer — automated video builder.

Downloads the Higgsfield-generated assets (voiceover, images, B-roll clips)
and stitches them into one finished 1920x1080 MP4 using ffmpeg:
  - Ken Burns (slow zoom/pan) motion on every still image
  - B-roll video clips dropped in on the dynamic beats
  - Burned-in on-screen text (step labels / stats / CTA)
  - Quinn voiceover as the master audio track (drives total runtime)

USAGE
  python3 build_video.py
  # ffmpeg required. If you don't have it:  pip install imageio-ffmpeg

Run this on your own machine / any host that can reach the Higgsfield CDN.
(The Claude Code web sandbox blocks that CDN, which is why this is a script
you run rather than something stitched in-session.)

Output:  ./austin_car_accident_explainer.mp4
"""

import os
import shutil
import subprocess
import sys
import urllib.request

# --------------------------------------------------------------------------
# ffmpeg discovery (system ffmpeg, else the imageio-ffmpeg bundled binary)
# --------------------------------------------------------------------------
def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ffmpeg not found. Install it, or run:  pip install imageio-ffmpeg")

FFMPEG = find_ffmpeg()

# --------------------------------------------------------------------------
# Optional on-screen text. Set DRAW_TEXT = False to disable burned-in text.
# A TTF font is required for text; we auto-detect common paths.
# --------------------------------------------------------------------------
DRAW_TEXT = True
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
FONT = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)


def _has_drawtext():
    try:
        out = subprocess.run([FFMPEG, "-hide_banner", "-filters"],
                             capture_output=True, text=True).stdout
        return " drawtext " in out
    except Exception:
        return False


if DRAW_TEXT and not FONT:
    print("[warn] No bold TTF font found; disabling burned-in text.")
    DRAW_TEXT = False
if DRAW_TEXT and not _has_drawtext():
    print("[warn] This ffmpeg build has no 'drawtext' filter, so on-screen text")
    print("       will be skipped. For burned-in text install a full ffmpeg")
    print("       (e.g. 'brew install ffmpeg' or 'apt install ffmpeg') instead")
    print("       of the pip imageio-ffmpeg binary, then re-run.")
    DRAW_TEXT = False

W, H, FPS = 1920, 1080, 30
CDN = "https://d8j0ntlcm91z4.cloudfront.net/user_3EzxIVq9VFMb2Cd4RPKbDIM04tb/"

# --------------------------------------------------------------------------
# Asset catalog (filename on CDN). All under the CDN prefix above.
# --------------------------------------------------------------------------
AUDIO = {
    "s1": "hf_20260623_170534_d34dc17f-5a0b-4ad6-8512-bc2080f9ab5c.mp3",
    "s2": "hf_20260623_170537_e5a2e3a3-cf16-4f6b-91d8-19f42ff31b8f.mp3",
    "s3": "hf_20260623_170542_b95fa9e4-347b-4cdf-a89e-b843da840d90.mp3",
    "s4": "hf_20260623_170544_be488cf7-e15e-4321-a264-e08565601cff.mp3",
    "s5": "hf_20260623_170548_6e617563-287b-42c4-ab31-7e3a25163ba8.mp3",
    "s6": "hf_20260623_170551_db9ed669-9c26-4931-a86d-c632d44d931e.mp3",
    "s7": "hf_20260623_170553_330addf1-a777-4dbd-af68-a1bf5c030134.mp3",
    "s8": "hf_20260623_170556_30174570-9061-4e41-b1cf-efa51bace937.mp3",
    "s9": "hf_20260623_170558_52d0dad8-70fb-4d7b-92f9-91da5ece34bb.mp3",
}
# Measured voiceover durations (seconds) — drives per-segment visual timing.
AUDIO_DUR = {
    "s1": 19.36, "s2": 20.24, "s3": 35.68, "s4": 31.92, "s5": 28.56,
    "s6": 33.60, "s7": 42.00, "s8": 28.08, "s9": 36.64,
}

IMG = {
    "skyline":   "hf_20260623_165348_44d1978c-ad86-4e70-8313-c3e08a70dd34.png",
    "fender":    "hf_20260623_170713_504b6246-fed3-4b9d-8e25-0ee95b806c90.png",
    "i35":       "hf_20260623_170716_23459f35-9f68-4ae6-977c-1b9e256b9e7a.png",
    "hazbtn":    "hf_20260623_170719_e421b25d-ad16-41e3-88ad-024c222ef88a.png",
    "dial911":   "hf_20260623_170721_85357a2b-53bb-4b44-8bd4-a32542e9c576.png",
    "police":    "hf_20260623_170724_146b4d31-ccf2-4152-bee0-02eda54d797e.png",
    "photodmg":  "hf_20260623_170726_08636a8e-8dd0-4e0f-8878-c47cf17d2837.png",
    "exchange":  "hf_20260623_170729_8c32c4eb-0b6f-4ab6-a080-94a490a91451.png",
    "neck":      "hf_20260623_170732_fad55562-56da-4db9-bd91-3101ea6989cd.png",
    "doctor":    "hf_20260623_170734_d43aba51-9866-4037-91a4-9c4e21811c6e.png",
    "bills":     "hf_20260623_170739_743a3e23-8e8e-421e-b099-054719c6fb75.jpeg",
    "phonering": "hf_20260623_170742_06c4e81f-89dd-43e0-a32c-51daf6b28fb7.png",
    "check":     "hf_20260623_170745_00b39d18-d024-44a2-bba8-35bb0f28315b.png",
    "speedaway": "hf_20260623_170748_8f22b757-7cad-4c55-990f-8dfb56546f09.jpeg",
    "policy":    "hf_20260623_170751_4094497d-92e4-476b-ae08-2aa6f9de98b6.png",
    "hourglass": "hf_20260623_170753_06f5b00b-778d-42a9-8197-c0e3aa0a814d.png",
    "scales":    "hf_20260623_170756_c7fc0336-79c5-459b-b46d-34922be93198.png",
    "office":    "hf_20260623_170810_69c305c7-0a43-4878-81df-67d331b806c0.png",
    "endcard":   "hf_20260623_170817_5d5afd9a-7611-4916-a4b0-b2ff25a75756.png",
}
VID = {
    "v_hazard":   "hf_20260623_170820_3b6822d4-bb0d-41c9-8928-46a41cb3cb7d.mp4",
    "v_police":   "hf_20260623_170822_2557da7a-5e3f-44c7-ba46-231e85c3d061.mp4",
    "v_speedaway":"hf_20260623_170827_5522eebd-a48e-436e-ac70-669cab9a5392.mp4",
    "v_skyline":  "hf_20260623_170830_ab3321a6-dbd7-49ee-bab1-d2ba3b37e551.mp4",
    "v_i35":      "hf_20260623_170839_4e69fe38-f43e-481b-a3d2-a71ed405a44f.mp4",
}

# --------------------------------------------------------------------------
# Storyboard: ordered visuals per voiceover segment + the on-screen text.
# "kind": img | vid.  Visuals split their segment's duration evenly.
# --------------------------------------------------------------------------
SEGMENTS = [
    ("s1", "What To Do After a Car Accident in Austin",
        [("vid", "v_skyline"), ("img", "fender"), ("vid", "v_hazard"), ("img", "hazbtn")]),
    ("s2", "Austin: ~26,000 crashes a year",
        [("vid", "v_i35"), ("img", "i35"), ("img", "skyline")]),
    ("s3", "STEP 1   Get Safe + Call 911",
        [("img", "dial911"), ("vid", "v_police"), ("img", "police"), ("img", "fender")]),
    ("s4", "STEP 2   Document Everything - Never Admit Fault",
        [("img", "photodmg"), ("img", "exchange"), ("img", "fender")]),
    ("s5", "STEP 3   See a Doctor",
        [("img", "neck"), ("img", "doctor"), ("img", "bills")]),
    ("s6", "STEP 4   Beware Insurance Tactics",
        [("img", "phonering"), ("img", "check"), ("img", "policy")]),
    ("s7", "STEP 5   Hit-and-Run or Uninsured? Use Your UM Coverage",
        [("vid", "v_speedaway"), ("img", "speedaway"), ("img", "policy"), ("img", "bills")]),
    ("s8", "Texas Law:  2-Year Deadline  -  51% Fault Bar",
        [("img", "hourglass"), ("img", "scales"), ("img", "i35")]),
    ("s9", "Ramos James Law   (512) 537-3369   Free Consultation",
        [("img", "office"), ("img", "scales"), ("img", "endcard")]),
]

ASSETS = "assets"
CLIPS = "clips"
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(CLIPS, exist_ok=True)


def download(fname):
    dst = os.path.join(ASSETS, fname)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return dst
    url = CDN + fname
    print(f"  downloading {fname}")
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            total = r.headers.get("Content-Length")
            if total and len(data) < int(total):
                raise IOError(f"incomplete: {len(data)}/{total}")
            with open(dst, "wb") as fh:
                fh.write(data)
            return dst
        except Exception as e:  # noqa
            last = e
            print(f"    retry {attempt + 1}/5 ({e})")
    raise RuntimeError(f"failed to download {fname}: {last}")


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def esc(text):
    # escape for ffmpeg drawtext
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,")


def drawtext_filter(text):
    if not DRAW_TEXT:
        return ""
    t = esc(text)
    # Lower-third: semi-transparent band + bold white text near the bottom.
    return (
        f",drawtext=fontfile='{FONT}':text='{t}':fontcolor=white:fontsize=52:"
        f"box=1:boxcolor=black@0.55:boxborderw=28:"
        f"x=(w-text_w)/2:y=h-180:line_spacing=8"
    )


def make_image_clip(src, dur, text, out):
    frames = max(1, int(round(dur * FPS)))
    # Ken Burns: gentle zoom-in, centered, rendered at output size.
    vf = (
        f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,"
        f"crop={W*2}:{H*2},"
        f"zoompan=z='min(zoom+0.0006,1.18)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}"
        f"{drawtext_filter(text)},format=yuv420p"
    )
    run([FFMPEG, "-y", "-loop", "1", "-i", src, "-t", f"{dur:.3f}",
         "-vf", vf, "-r", str(FPS), "-an", out])


def make_video_clip(src, dur, text, out):
    # Scale/pad to frame, set fps, loop+trim to the assigned duration.
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}"
        f"{drawtext_filter(text)},format=yuv420p"
    )
    run([FFMPEG, "-y", "-stream_loop", "-1", "-i", src, "-t", f"{dur:.3f}",
         "-vf", vf, "-r", str(FPS), "-an", out])


def main():
    print("[1/5] Downloading assets ...")
    for f in AUDIO.values():
        download(f)
    used = set()
    for _, _, vis in SEGMENTS:
        for kind, key in vis:
            used.add(("img", IMG[key]) if kind == "img" else ("vid", VID[key]))
    for kind, f in used:
        download(f)

    print("[2/5] Rendering per-segment visual clips (Ken Burns + text) ...")
    clip_files = []
    idx = 0
    for seg, text, vis in SEGMENTS:
        seg_dur = AUDIO_DUR[seg]
        per = seg_dur / len(vis)
        for kind, key in vis:
            out = os.path.join(CLIPS, f"clip_{idx:03d}.mp4")
            if kind == "img":
                make_image_clip(os.path.join(ASSETS, IMG[key]), per, text, out)
            else:
                make_video_clip(os.path.join(ASSETS, VID[key]), per, text, out)
            clip_files.append(out)
            idx += 1

    print("[3/5] Concatenating video track ...")
    with open("video_list.txt", "w") as fh:
        for c in clip_files:
            fh.write(f"file '{c}'\n")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "video_list.txt",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "video_track.mp4"])

    print("[4/5] Concatenating voiceover track ...")
    with open("audio_list.txt", "w") as fh:
        for s in AUDIO:
            fh.write(f"file '{os.path.join(ASSETS, AUDIO[s])}'\n")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "audio_list.txt",
         "-c:a", "aac", "-b:a", "192k", "narration.m4a"])

    print("[5/5] Muxing final video ...")
    out = "austin_car_accident_explainer.mp4"
    run([FFMPEG, "-y", "-i", "video_track.mp4", "-i", "narration.m4a",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-shortest", out])
    print(f"\nDONE -> {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
