import asyncio
import edge_tts

async def main():
    tts = edge_tts.Communicate("Hello world", "en-US-ChristopherNeural")
    await tts.save("test.mp3")

asyncio.run(main())
