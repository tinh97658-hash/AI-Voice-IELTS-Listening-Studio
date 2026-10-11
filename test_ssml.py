import asyncio
import edge_tts

async def test():
    # Test if edge-tts speaks <break> literally or respects it
    comm = edge_tts.Communicate("Hello. <break time='1000ms' /> World.", "en-GB-RyanNeural")
    data = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            data.extend(chunk["data"])
    print("Result size:", len(data))

asyncio.run(test())
