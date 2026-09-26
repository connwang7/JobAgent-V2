"""网络工具：本机/内网服务不应走系统代理。

开发机上常设置了 HTTP_PROXY/HTTPS_PROXY（如 Clash 127.0.0.1:7897），
httpx 默认 trust_env=True 会把 http://127.0.0.1:6333 这类请求也丢给代理，
表现为 502 upstream connect failed（目标计算机积极拒绝），而服务其实只是没启动
或不该被代理。这里统一判断"是否本机/内网端点"，据此决定是否读取代理环境变量。
"""
from urllib.parse import urlparse

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}


def is_local_endpoint(url: str) -> bool:
    """url 指向本机（localhost / 127.0.0.1 / ::1 / 私网段）时返回 True。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host in _LOCAL_HOSTS:
        return True
    # 私网段（Docker/局域网自托管，如 172.17.0.1、192.168.x.x）
    if host.startswith(("10.", "192.168.", "127.")):
        return True
    if host.startswith("172."):
        try:
            second = int(host.split(".")[1])
            return 16 <= second <= 31
        except (IndexError, ValueError):
            return False
    return False
