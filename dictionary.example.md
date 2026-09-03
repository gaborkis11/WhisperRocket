# Your own words (example / template)
#
# Copy this to ~/.config/whisperrocket/dictionary.md, or open
# Settings > AI > Your own words and edit it there.
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS
#
# Speech recognition does not know the names you use - your projects, the tools
# you work with, people, in-house jargon. It does not leave them blank either:
# it writes down whatever sounded closest. Measured on this project, "tail
# scale" came back as "TeamViewer" - a real product that was never mentioned.
# A wrong-but-plausible name in a message is worse than a garbled one, because
# nobody notices it.
#
# ---------------------------------------------------------------------------
# HOW TO FILL IT IN
#
# One word or phrase per line, spelled the way you want it written. That's all.
#
# You do NOT have to write down what the recogniser gets wrong. The AI works
# that out from how the word sounds - measured, three runs out of three: given
# only the list below, it turned "tel szkel" into Tailscale, "klovolt ba" into
# "ClawVaultba" and "faszter viszper" into faster-whisper, inflection included.
#
# Lines starting with # are ignored, so you can keep notes and group things.

Tailscale
WhisperRocket
faster-whisper

# ---------------------------------------------------------------------------
# OPTIONAL: literal corrections
#
# If you want a specific mishearing fixed even with AI cleanup switched OFF,
# write it after a colon. Separate several with commas.
#
# This one is a literal, word-boundary replacement done in code, so it is
# guaranteed - but it only matches exactly what you spell out:
#
#     Tailscale: tail scale, télszkél
#
# Word boundaries are respected and case and accents are ignored, so
# "tail scale" matches but "tailscalexyz" does not.
#
# ---------------------------------------------------------------------------
# OPTIONAL: hints for the recogniser itself (off by default)
#
# The list is used by the AI cleanup, after recognition. faster-whisper can
# also take it as "hotwords" while still listening; that is switched off by
# default, because the hint competes with your speech for the decoder's
# budget, fits only a few dozen words, and the AI resolves the same names
# from this list anyway. To try it, set "hotwords_enabled": true in
# config.json. Only then does a ! in front of a word mean anything (it goes
# to the recogniser first); with hotwords off the marker changes nothing.
#
#     !Sanyi
#
# The log says what got through: [HOTWORDS] 36/112 words, 149/150 tokens; ...
