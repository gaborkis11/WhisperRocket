#!/usr/bin/env python3
"""
A/B check: one recording transcribed with and without the dictionary as hotwords.

    venv/bin/python tools/hotwords_ab.py sample.wav [more.m4a ...]
        [--cpu] [--language hu] [--hotwords "Sanyi, Zsófi"] [--beam 5]

Loads the model the way the app does (config.json: model, device, compute_type;
CUDA libraries on LD_LIBRARY_PATH like start.sh), packs the user's dictionary
exactly like the app (dictionary_manager.HotwordsProvider, so the same
[HOTWORDS] line is printed), then prints both transcripts, the time each took
and the words that differ. Read-only: nothing under ~/.config is touched.

What to look for, per the briefing:
  - words that got FIXED (the point of the feature)
  - words that got BROKEN - a real "Sonny" turning into "Sanyi" is a regression
  - text that was never said (a hotword the model forced in) - hallucination
"""
import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def ensure_cuda_libs_on_path():
    """
    Re-exec with the pip-installed CUDA libraries on LD_LIBRARY_PATH, the way
    start.sh does - the dynamic loader reads that variable once at startup, so
    setting it from inside the process is too late.
    """
    try:
        import nvidia.cudnn
        import nvidia.cublas
    except ImportError:
        return
    libs = [str(Path(nvidia.cudnn.__path__[0]) / "lib"),
            str(Path(nvidia.cublas.__path__[0]) / "lib")]
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if all(lib in current.split(":") for lib in libs):
        return
    os.environ["LD_LIBRARY_PATH"] = ":".join(libs + ([current] if current else []))
    os.execv(sys.executable, [sys.executable] + sys.argv)


def word_diff(a: str, b: str):
    """Pairs of (before, after) word runs that differ between two transcripts"""
    aw, bw = a.split(), b.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=aw, b=bw).get_opcodes():
        if tag != "equal":
            out.append((" ".join(aw[i1:i2]), " ".join(bw[j1:j2])))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="audio file(s) to transcribe")
    ap.add_argument("--cpu", action="store_true", help="force CPU / int8 (no CUDA needed)")
    ap.add_argument("--language", help="override config language (e.g. hu)")
    ap.add_argument("--hotwords", help="use this string instead of the dictionary")
    ap.add_argument("--beam", type=int, default=5, help="beam size (app uses 5)")
    ap.add_argument("--vad", action="store_true",
                    help="vad_filter=True (the hotkey path does not use it; file transcription does)")
    args = ap.parse_args()

    if not args.cpu:
        ensure_cuda_libs_on_path()

    from config_paths import get_config_path
    import dictionary_manager
    from model_manager import get_model_path_for_loading
    from faster_whisper import WhisperModel

    config = json.loads(Path(get_config_path()).read_text(encoding="utf-8"))
    language = args.language or config.get("language", "hu")
    device = "cpu" if args.cpu else config.get("device", "cpu")
    compute_type = "int8" if args.cpu else config.get("compute_type", "int8")
    model_name = config.get("model", "large-v3")

    print(f"[MODEL] {model_name} on {device}/{compute_type}, language={language}, "
          f"beam={args.beam}, vad={args.vad}")
    model_path = get_model_path_for_loading(model_name, device)
    t0 = time.time()
    model = WhisperModel(model_path, device=device, compute_type=compute_type)
    print(f"[MODEL] loaded in {time.time() - t0:.1f}s")

    tokenizer = model.hf_tokenizer
    count = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)  # noqa: E731
    if args.hotwords is not None:
        hotwords = args.hotwords.strip() or None
        print(f"[HOTWORDS] override: {count(' ' + hotwords) if hotwords else 0}/"
              f"{dictionary_manager.HOTWORDS_TOKEN_BUDGET} tokens")
    else:
        hotwords = dictionary_manager.HotwordsProvider(count).current()
    print(f"[HOTWORDS] {hotwords!r}\n")

    def run(path, hw):
        t = time.time()
        segments, _ = model.transcribe(path, language=language, beam_size=args.beam,
                                       vad_filter=args.vad,
                                       **dictionary_manager.hotwords_options(hw))
        text = " ".join(s.text.strip() for s in segments)
        return text, time.time() - t

    for path in args.files:
        print("=" * 72)
        print(f"FILE: {path}")
        base, t_base = run(path, None)
        with_hw, t_hw = run(path, hotwords)
        print(f"  WITHOUT ({t_base:.2f}s): {base}")
        print(f"  WITH    ({t_hw:.2f}s): {with_hw}")
        changes = word_diff(base, with_hw)
        if not changes:
            print("  DIFF: none")
        else:
            print(f"  DIFF ({len(changes)}):")
            for before, after in changes:
                print(f"    {before!r:40} -> {after!r}")
    print("=" * 72)


if __name__ == "__main__":
    main()
