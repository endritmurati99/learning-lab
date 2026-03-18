import os
import subprocess
import wave
import struct

def create_dummy_audio(filename="dummy.wav"):
    """Create a 1-second blank WAV file."""
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        num_frames = 8000
        f.writeframes(b'\x00' * 2 * num_frames)

if __name__ == "__main__":
    create_dummy_audio()
    print("Running buzz to cache the medium whisper model...")
    try:
        subprocess.run(["buzz", "transcribe", "--model", "medium", "dummy.wav"], shell=True, check=True)
        print("Model correctly cached!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to run buzz. Make sure it is installed and in your PATH. Error: {e}")
    finally:
        if os.path.exists("dummy.wav"):
            os.remove("dummy.wav")
