import httpx

http_client = None

def get_http_client():
    """获取HTTP客户端"""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=30.0)
    return http_client

async def close_http_client():
    """关闭HTTP客户端"""
    global http_client
    if http_client:
        await http_client.aclose()
        http_client = None