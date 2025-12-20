from faster_whisper import WhisperModel
import time

print("🎯 Whisper modell betöltése...")
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
print("✅ Modell betöltve!\n")

audio_file = "teszt.wav"

print(f"🎤 Átírás folyamatban: {audio_file}")
start = time.time()

segments, info = model.transcribe(
    audio_file, 
    language="hu",
    beam_size=5
)

print(f"⏱️  Észlelt nyelv: {info.language} ({info.language_probability:.2%})\n")

print("📝 Átírt szöveg:")
print("-" * 50)
for segment in segments:
    print(f"{segment.text}")

print("-" * 50)
print(f"✅ Kész! Időtartam: {time.time() - start:.2f} másodperc")
