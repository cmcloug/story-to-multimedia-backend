import os
import random
import re
import pandas as pd
import asyncio
import edge_tts
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from datetime import datetime

# Paths
project_folder = os.path.join(os.getcwd(), "----")
csv_path = os.path.join(project_folder, "stories.csv")
audio_output_folder = os.path.join(project_folder, "audio output")
video_output_folder = os.path.join(project_folder, "video output")
vbin_folder = os.path.join(project_folder, "vbin")

os.makedirs(audio_output_folder, exist_ok=True)
os.makedirs(video_output_folder, exist_ok=True)

# Ask user: CSV or manual input
print("Select input method:")
print("1. Use CSV (process new stories)")
print("2. Paste a new story manually")
choice = input("Enter 1 or 2: ").strip()

if choice == "1":
    # --- Load CSV ---
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}")
    
    df = pd.read_csv(csv_path)

    # Auto-detect title/content columns
    title_variations = ['title', 'Title', 'TITLE', 'post_title', 'heading']
    content_variations = ['text', 'content', 'body', 'selftext', 'post_content', 'story']

    title_col = next((c for c in df.columns if c.lower() in [v.lower() for v in title_variations]), None)
    content_col = next((c for c in df.columns if c.lower() in [v.lower() for v in content_variations]), None)

    if not title_col or not content_col:
        raise ValueError("Could not auto-detect title/content columns in CSV.")

    # Add processed column if missing
    if 'processed' not in df.columns:
        df['processed'] = 0

    # Filter only unprocessed stories
    df_unprocessed = df[df['processed'] != 1].reset_index(drop=True)
    if df_unprocessed.empty:
        print("✅ No new stories to process.")
        exit()

    # Show user the available stories
    print("\n=== Available Stories ===")
    for idx, row in df_unprocessed.iterrows():
        preview = str(row[title_col])[:60]
        print(f"{idx + 1}. {preview}...")
    
    # Let user choose
    story_idx = int(input(f"\nSelect a story (1-{len(df_unprocessed)}): ").strip()) - 1
    if story_idx < 0 or story_idx >= len(df_unprocessed):
        raise ValueError("Invalid selection.")
    
    selected_story = df_unprocessed.iloc[story_idx]
    original_index = df[df[title_col] == selected_story[title_col]].index[0]
    
    story_title = str(selected_story[title_col])
    story_content = str(selected_story[content_col])
    story_text = f"{story_title}\n\n{story_content}"
    mark_processed = True  # Mark in CSV later

elif choice == "2":
    # --- Manual story input ---
    story_title = input("Enter story title: ").strip()
    story_link = input("Enter story link (optional): ").strip()
    story_body = input("Enter story content/body: ").strip()
    story_text = f"{story_title}\n{story_link}\n\n{story_body}" if story_link else f"{story_title}\n\n{story_body}"
    mark_processed = False  # Manual story won't be added to CSV automatically
    original_index = None

else:
    raise ValueError("Invalid choice. Enter 1 or 2.")

# Clean text to avoid random tts pausing
story_text = re.sub(r'\[.*?\]\(.*?\)', '', story_text)
story_text = re.sub(r'\*\*?', '', story_text)
story_text = re.sub(r'#{1,6}\s', '', story_text)
story_text = story_text.replace('"', '').replace("'", '').replace('(', '').replace(')', '')
story_text = re.sub(r'[\[\]]', '', story_text)

# Collapse multiple empty lines but keep paragraphs
story_text = re.sub(r'\n{2,}', '\n\n', story_text)
story_text = '\n'.join([line.strip() for line in story_text.split('\n') if line.strip() != ''])

print(f"\nProcessing story: {story_title[:50]}...")
print(f"Story length: {len(story_text)} chars")

# Generate unique filenames for puvlish
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
safe_title = re.sub(r'[^\w\s-]', '', story_title)[:50]
safe_title = re.sub(r'[-\s]+', '_', safe_title)
unique_name = f"{safe_title}_{timestamp}"

VOICE = "en-US-ChristopherNeural"
final_audio_file = os.path.join(audio_output_folder, f"{unique_name}.mp3")

# Async TTS & speed up for more enjoyable audio experience
async def generate_tts(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE, rate="+35%")
    await communicate.save(output_file)

# Split text into chunks for TTS, struggles with longer files
max_chars = 4000

# Split the entire story_text into chunks (including title)
sentences = re.split(r'(?<=[.!?])\s+', story_text)

chunks = []
current_chunk = ""
for sentence in sentences:
    if len(current_chunk) + len(sentence) < max_chars:
        current_chunk += sentence + " "
    else:
        if current_chunk:
            chunks.append(current_chunk.strip())
        current_chunk = sentence + " "
if current_chunk:
    chunks.append(current_chunk.strip())

# Generate audio onto local machine
temp_audio_files = []
for i, chunk in enumerate(chunks):
    print(f"Processing chunk {i+1}/{len(chunks)}...")
    temp_file = os.path.join(audio_output_folder, f"temp_chunk_{i}_{timestamp}.mp3")
    asyncio.run(generate_tts(chunk, temp_file))
    temp_audio_files.append(temp_file)

# Concatenate audio chunks
from moviepy import concatenate_audioclips
audio_clips = [AudioFileClip(f) for f in temp_audio_files]
final_audio = concatenate_audioclips(audio_clips)
final_audio.write_audiofile(final_audio_file)

# Clean up temp files
for f in temp_audio_files:
    os.remove(f)
for clip in audio_clips:
    clip.close()

print(f"✅ Audio generated: {final_audio_file}")

# Background videos generated locally
video_files = [f for f in os.listdir(vbin_folder) if f.endswith(".mp4")]
if not video_files:
    raise FileNotFoundError("No .mp4 files found in vbin folder.")
selected_video = random.choice(video_files)
background = VideoFileClip(os.path.join(vbin_folder, selected_video))

audio_clip = AudioFileClip(final_audio_file)
if background.duration < audio_clip.duration:
    n_loops = int(audio_clip.duration / background.duration) + 1
    background = concatenate_videoclips([background] * n_loops).subclipped(0, audio_clip.duration)
else:
    background = background.subclipped(0, audio_clip.duration)

background = background.with_audio(audio_clip)

# Add title text overlay
try:
    title_lines = [story_title[i:i+40] for i in range(0, len(story_title), 40)]
    txt_clip = (TextClip("\n".join(title_lines), fontsize=50, color='white',
                         size=(background.w - 100, None), method='caption', font='Arial')
                .set_duration(5)
                .set_position('center'))
    final_video = CompositeVideoClip([background, txt_clip])
except Exception:
    final_video = background

output_path = os.path.join(video_output_folder, f"{unique_name}.mp4")
print("Rendering final video...")
final_video.write_videofile(output_path, fps=30)

audio_clip.close()
background.close()
final_video.close()
print(f"✅ Video saved: {output_path}")

# Mark story as processed in CSV if applicable
if choice == "1" and mark_processed and original_index is not None:
    df.loc[original_index, 'processed'] = 1
    df.to_csv(csv_path, index=False)

    print("✅ Story marked as processed in CSV.")

