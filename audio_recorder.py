import datetime
import os
import time
import wave

import openai
import pyaudio
from pydub import AudioSegment

# Read OpenAI API key from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Define constants
CHUNK = 1024  # number of audio samples per frame
FORMAT = pyaudio.paInt16  # audio format
CHANNELS = 1  # mono audio
RATE = 44100  # audio sample rate
MAX_RETRIES = 3  # maximum number of retries for failed transcriptions
RETRY_DELAY = 5  # delay in seconds between retries
OUTPUT_INTERVAL = 10  # output interval in seconds for total length of recording

# Create PyAudio object
audio = pyaudio.PyAudio()

# Start recording audio
stream = audio.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)

print("Recording audio... (Press Ctrl+C to stop recording)")

# Initialize variables
frames = []
start_time = datetime.datetime.now()
last_output_time = datetime.datetime.now()

# Record audio in chunks of CHUNK frames
try:
    while True:
        chunk = stream.read(CHUNK)
        frames.append(chunk)

        # Output total length of recording every
        elapsed_time = (datetime.datetime.now() -
                        last_output_time).total_seconds()
        if elapsed_time >= OUTPUT_INTERVAL:
            total_time = (datetime.datetime.now() - start_time).total_seconds()

            # format the time to HH:MM:SS
            print("Recording time: {}".format(
                str(datetime.timedelta(seconds=total_time)).split(".")[0]))
            last_output_time = datetime.datetime.now()


except KeyboardInterrupt:
    print("Stopping recording...")

finally:
    # Stop recording audio
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Save recorded audio to WAV file with timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    wav_filename = "recording_{}.wav".format(timestamp)
    wf = wave.open(wav_filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    # Export recorded audio to MP3 file with timestamp
    mp3_filename = "audio_{}.mp3".format(timestamp)
    audio_segment = AudioSegment.from_wav(wav_filename)
    audio_segment.export(mp3_filename, format="mp3")

    print("Recorded audio saved to file: {}".format(mp3_filename))

    # Split WAV file into 10-minute chunks using pydub
    chunks = [audio_segment[i:i+600000]
              for i in range(0, len(audio_segment), 600000)]
    transcriptions = []
    for i, chunk in enumerate(chunks):
        # Export chunk to MP3 file with timestamp
        chunk_filename = "chunk_{}_{}.mp3".format(i+1, timestamp)
        chunk.export(chunk_filename, format="mp3")

        print("Processing chunk {}...".format(i+1))

        # Transcribe chunk using Whisper API
        retries = 0
        success = False
        while not success and retries < MAX_RETRIES:
            try:
                with open(chunk_filename, "rb") as file:
                    transcription = openai.Audio.transcribe("whisper-1", file)

                success = True
            except openai.error.APIError as error:
                print("Transcription for chunk {} failed (retry {} of {}): {}".format(
                    i+1, retries+1, MAX_RETRIES, error))
                retries += 1
                time.sleep(RETRY_DELAY)

        if success:
            # Print transcription
            print("Transcription for chunk {}:".format(i+1))
            print(transcription)

            # Add transcription to list
            transcriptions.append(transcription)

            # Delete MP3 file
            os.remove(chunk_filename)
        else:
            print("Transcription for chunk {} failed after {} retries, skipping...".format(
                i+1, MAX_RETRIES))

    # Delete WAV

    os.remove(wav_filename)

    # Write transcriptions to file with timestamp
    txt_filename = "transcriptions_{}.txt".format(timestamp)
    with open(txt_filename, "w") as file:
        for transcription in transcriptions:
            file.write(transcription['text'] + "\n")

    print("Transcriptions saved to file: {}".format(txt_filename))

    # Print transcriptions to terminal
    print("\n\n--- Transcriptions ---\n\n")
    for i, transcription in enumerate(transcriptions):
        print("Chunk {}: {}".format(i+1, transcription['text']))

    print("\n\nRecording saved to {} and transcribed into {} chunks.".format(
        mp3_filename, len(chunks)))
