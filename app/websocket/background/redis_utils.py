# import json
# import time


# async def get_cache(redis, key):
#     data = await redis.get(key)
#     if data:
#         return json.loads(data)
#     return None


# async def set_cache(redis, key, value, ttl):
#     payload = {"data": value, "cached_at": time.time()}
#     await redis.setex(key, ttl, json.dumps(payload))


# async def get_cached_dashboard(user_id, redis, compute_fn):
#     cache_key = f"dashboard:{user_id}"
#     cached = await get_cache(redis, cache_key)

#     if cached:
#         return cached["data"]

#     data = await compute_fn()
#     await set_cache(redis, cache_key, data, ttl=10)  # dashboard TTL

#     return data


import json
import time
import traceback


async def get_cache(redis, key):
    print(f"🔍 Checking cache for key: {key}")

    data = await redis.get(key)

    if data:
        print("✅ Cache HIT")
        return json.loads(data)

    print("❌ Cache MISS")
    return None


async def set_cache(redis, key, value, ttl):
    print(f"💾 Setting cache for key: {key}, ttl={ttl}")

    payload = {
        "data": value,
        "cached_at": time.time()
    }

    await redis.setex(key, ttl, json.dumps(payload))


async def get_cached_dashboard(user_id, redis, compute_fn):
    cache_key = f"dashboard:{user_id}"

    print(f"\n📊 Fetching dashboard for user {user_id}")

    cached = await get_cache(redis, cache_key)

    if cached:
        print("📦 Returning cached dashboard")
        return cached["data"]

    print("⚙️ Cache empty → computing dashboard")

    try:
        data = await compute_fn()
    except Exception as e:
        print("🔥 ERROR while computing dashboard:", e)
        traceback.print_exc()
        raise

    await set_cache(redis, cache_key, data, ttl=10)

    return data