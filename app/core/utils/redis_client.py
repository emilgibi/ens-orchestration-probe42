import redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = "rediss://default:gQAAAAAAARuhAAIncDEyM2NkNmIxNDI4YTQ0NzUyYWJmYjA2ODY4YzliYzBhY3AxNzI2MDk@diverse-magpie-72609.upstash.io:6379"
SESSION_SET_KEY = "analysis_session_queue_session_ids"
VALIDATION_SESSION_SET_KEY = "validation_session_queue_session_ids"
rdb = redis.Redis.from_url(REDIS_URL, decode_responses=True)