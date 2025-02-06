import math
import sys
import yt_dlp
import av
import matplotlib.pyplot as plt
import numpy as np
import mido

plt.ion()

USE_ALL_DEFAULTS = False # For testing

def main() -> int:
    # If the first parameter is a Youtube URL, download it using youtube-dl
    # If the first parameter is a file, use it as the input file
    if len(sys.argv) < 2:
        print("Usage: pianorollvideotomidi <source>")
        return 1
    
    source = sys.argv[1]
    print(source)
    
    path = source
    
    if source.startswith("https://www.youtube.com/watch?v="):
        print("Downloading Youtube video...")
        # Download the video
        path = download_youtube_video(source)
    else:
        print("Using input file...")
    
    print(f"Converting video at {path} to MIDI...")

    # Convert the video to MIDI.
    
    # Here's our process:
    # - Split the video into frames
    # - Allow the user to select the number and position of piano roll keys
    #   - Determine each individual key position
    #   - Show a preview of the detected locations
    # - Determine which notes are being played at each frame
    # - Convert the notes to MIDI
    
    container = av.open(path)
    frame_iterator = container.decode(video=0)
    
    first_frame = next(frame_iterator)
    first_frame_index = 0
    next_frames = []
    
    # First, ask the user if they already know the first frame index
    # If they do, we can skip the selection
    known_first_frame = 125 if USE_ALL_DEFAULTS else input("What is the index of the first frame? (leave empty if you don't know) ")
    if known_first_frame:
        first_frame_index = int(known_first_frame)
        for _ in range(first_frame_index):
            first_frame = next(frame_iterator)
    else:
        previous_frames = []
    
        # Allow the user to select the first frame by pressing right/left arrow and enter
        # We can't use imshow because it doesn't work with PIL images\
        fig, ax = plt.subplots()
        
        running = True
        
        def on_key(event):
            nonlocal running, next_frames, previous_frames, first_frame, first_frame_index
            
            if event.key == "enter":
                plt.close()
                running = False
            elif event.key == "right":
                print("Next frame")
                previous_frames.append(first_frame)
                first_frame = next(frame_iterator)
                first_frame_index += 1
            elif event.key == "left":
                print("Previous frame")
                if len(previous_frames) > 0:
                    next_frames.append(first_frame)
                    first_frame = previous_frames.pop()
                    first_frame_index -= 1
            elif event.key == "shift+right":
                print("Next 10 frames")
                for _ in range(10):
                    previous_frames.append(first_frame)
                    first_frame = next(frame_iterator)
                    first_frame_index += 1
            elif event.key == "shift+left":
                print("Previous 10 frames")
                if len(previous_frames) > 0:
                    for _ in range(10):
                        next_frames.append(first_frame)
                        first_frame = previous_frames.pop()
                        first_frame_index -= 1
            else:
                print(f"Key: {event.key}")
        
        fig.canvas.mpl_connect('key_press_event', on_key)
        
        while running:
            plt.show()
            
            ax.clear()
            ax.imshow(first_frame.to_image())
            
            plt.pause(1 / 30)
    
    print(f"First frame index: {first_frame_index}")
    
    # Next, we need to determine the position of the piano keys
    # We do a very similar thing to the first frame selection:
    # left and right arrows increase/decrease the key count, while up and down arrows change the key position.
    # This is quite inflexible, but it should work for now.
    known_key_count = 88 if USE_ALL_DEFAULTS else input("How many keys are there? (leave empty if you don't know) ")
    known_vertical_position = 0.18 if USE_ALL_DEFAULTS else input("What is the vertical position of the keys? (leave empty if you don't know) ")
    
    key_positions: list[tuple[float, float, int]] = []
    if known_key_count:
        key_positions = get_key_positions(int(known_key_count), float(known_vertical_position))
    else:
        # Allow the user to select the key count and position
        key_count = 88
        vertical_position = 0.18
        
        fig, ax = plt.subplots()
        
        running = True
        
        def on_key(event):
            nonlocal running, key_count, vertical_position
            
            if event.key == "enter":
                plt.close()
                running = False
            elif event.key == "right":
                print("Increase key count")
                key_count += 1
            elif event.key == "left":
                print("Decrease key count")
                key_count -= 1
            elif event.key == "up":
                print("Vertical position up")
                vertical_position += 0.01
            elif event.key == "down":
                print("Vertical position down")
                vertical_position -= 0.01
            elif event.key == "shift+up":
                print("Vertical position up 0.1")
                vertical_position += 0.1
            elif event.key == "shift+down":
                print("Vertical position down 0.1")
                vertical_position -= 0.1
            else:
                print(f"Key: {event.key}")
        
        fig.canvas.mpl_connect('key_press_event', on_key)
    
        while running:
            plt.show()
            
            ax.clear()
            ax.imshow(first_frame.to_image(), extent=(0, 1, 0, 1), aspect=first_frame.height / first_frame.width)
            
            key_positions = get_key_positions(key_count, vertical_position)
            # Plot the key positions (normalized to 0-1)
            for key_position in key_positions:
                ax.plot(key_position[0], key_position[1], 'ro')
            
            plt.pause(1 / 30)
        
        print(f"Key count: {key_count}")
        print(f"Vertical position: {vertical_position}")
    
    # Horray! We have the key positions.
    # Now, we need to determine the notes being played at each frame.
    # This is a bit more complicated, and it's a manual thresholding process
    # for now.
    KEY_ENABLED_LIGHTNESS = 0.93
    
    TICKS_PER_BEAT = 120
    midi_file = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    
    track = mido.MidiTrack()
    midi_file.tracks.append(track)
    
    track.name = "Piano"
    track.append(mido.Message('program_change', program=0)) # Set the instrument to piano
    
    # TRUNCATE_FRAME_COUNT = 10 # Temporary
    DEBUG = False
    TRUNCATE_FRAME_COUNT = 100 if DEBUG else float("inf")
    
    print("Processing the rest of the video...")
    frames = next_frames + list(truncate_iterator(frame_iterator, TRUNCATE_FRAME_COUNT))
    print(f"Video has {len(frames)} frames.")
    
    framerate = float(container.streams.video[0].base_rate)
    print(f"Framerate: {framerate}")
    time: float = 0.
    
    bpm = 204 if USE_ALL_DEFAULTS else int(input("What is the BPM? "))
    
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    
    notes_on: set[int] = set()
    last_update_time = 0
    
    def note_change(message: str, note: int, velocity: int):
        nonlocal time, track, last_update_time
        
        # We need to adjust since our note 0 is A and MIDI note 0 is C
        note += 21
        
        # Snap to the nearest bpm beat
        beats = math.floor(time * bpm / 60. * 2.) / 2.
        ticks = int(beats * TICKS_PER_BEAT)
        
        old_last_update_time = last_update_time
        last_update_time = ticks
        ticks -= old_last_update_time
        
        track.append(mido.Message(message, note=note, velocity=velocity, time=ticks))
    
    def note_on(note: int, velocity: int):
        note_change('note_on', note, velocity)
    def note_off(note: int, velocity: int):
        note_change('note_off', note, velocity)
    
    for i, frame in enumerate(frames):
        if i % 100 == 0:
            print(f"Frame {i + first_frame_index}")
        time += 1. / framerate
        
        # Convert the frame to grayscale
        frame_gray = frame.to_image().convert("L")
        frame_array = np.array(frame_gray)
        
        # Determine the notes being played
        notes: set[int] = set()
        for key_position in key_positions:
            x, y, key_index = key_position
            
            # Get the pixel value at the key position
            pixel_value = frame_array[int((1 - y) * frame.height), int(x * frame.width)]
            lightness = pixel_value / 255
            
            if KEY_ENABLED_LIGHTNESS > 0:
                if lightness > KEY_ENABLED_LIGHTNESS:
                    notes.add(key_index)
            else:
                if lightness < -KEY_ENABLED_LIGHTNESS:
                    notes.add(key_index)
        
        # Turn off notes that are no longer being played
        for note in notes_on - notes:
            note_off(note, 64)
        
        # Add the notes to the MIDI file that were just turned on
        for note in notes - notes_on:
            note_on(note, 64)
            
        if DEBUG and i % 1 == 0:
            # If debugging, draw a graph of the notes
            fig, ax = plt.subplots()
            ax.imshow(frame_array, cmap='gray')
            for key_position in key_positions:
                x, y, key_index = key_position
                active = key_index in notes
                ax.plot(x * frame.width, (1 - y) * frame.height, 'ro' if active else 'bo')
            plt.show()
            plt.waitforbuttonpress()
            plt.close()
        
        notes_on = notes
    
    # Turn off all notes at the end
    for note in notes_on:
        note_off(note, 64)
    
    # Save the MIDI file
    midi_file.save("output.mid")
    
    return 0

def truncate_iterator(iterator, count: int):
    for i, item in enumerate(iterator):
        if i >= count:
            break
        yield item

def get_key_positions(key_count: int, vertical_position: int) -> list[tuple[float, float, int]]:
    white_keys = math.ceil(key_count * 7 / 12)
    
    # We assume the first note is MIDI note 0.
    black_key_vertical_offset = 0.09
    black_key_horizontal_offset = 1 / white_keys / 2
    
    key_positions = []
    white_key_index = 0
    for i in range(key_count):
        # We start on A, so the black key indices are 1, 4, 6, 9, and 11
        is_black_key = i % 12 in [1, 4, 6, 9, 11]
        
        x = (white_key_index + 0.5) / white_keys
        y = vertical_position
        
        if is_black_key:
            x -= black_key_horizontal_offset
            y += black_key_vertical_offset
        else:
            white_key_index += 1
        
        key_positions.append((x, y, i))
    
    return key_positions

def download_youtube_video(url: str) -> str:
    # Download the video
    ydl_opts = {
        'outtmpl': 'video.%(ext)s',
        # 720p is ideal and we want to maximize the framerate. We also want to download in mp4 format.
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # print("Available formats:")
        # print(ydl.list_formats(ydl.extract_info(url)))
        
        ydl.download([url])
    
    # I'm not sure if this is a fixed path? Works for now, I guess.
    return "video.mp4"