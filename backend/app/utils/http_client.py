import httpx

http_client = None

def get_http_client():
    """获取HTTP客户端"""
    global http_client
    if not http_client:
        http_client = httpx.AsyncClient(timeout=30.0)
    return http_client

def close_http_client():
    """关闭HTTP客户端"""
    if http_client:
        import asyncio
        asyncio.create_task(http_client.aclose())