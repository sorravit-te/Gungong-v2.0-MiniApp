import asyncio
import time
import httpx
import sys

async def test_performance():
    url = "http://localhost:8001/check-fraud"
    payload = {
        "message": "ลองเล่นเว็บนี้ดู https://example.com",
        "user_id": "test_user_perf"
    }
    
    print(f"🚀 Sending request to {url}...")
    
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            end_time = time.time()
            
            duration = end_time - start_time
            print(f"✅ Request completed in {duration:.4f} seconds")
            
            if response.status_code == 200:
                data = response.json()
                print(f"📊 Result: {data.get('category')}")
                print(f"⚡ Server Execution Time: {data.get('execution_time', 'N/A')}s")
                
                if duration <= 3.0:
                    print("🎉 SUCCESS: Performance goal met (< 3s)")
                else:
                    print("⚠️ WARNING: Performance goal NOT met (> 3s)")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_performance())
