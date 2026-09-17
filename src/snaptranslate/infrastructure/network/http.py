"""带回退的 HTTP GET：代理连不上就直连重试一次。

为什么要回退：如果用户选了"跟随系统代理"而 Clash 被关掉了（注册表里仍留着代理地址），
所有翻译请求都会撞在死代理上——那比直连还糟。这里遇到 ``ProxyError`` 时自动直连重试一次，
让"代理失效"退化成"没走代理"，而不是"翻译全挂"。

``trust_env=False``：只认显式传入的 proxies，不去猜环境变量——避免"环境里有个残废代理"
这种更隐蔽的坑（原版恰恰相反：只认环境变量，见 KNOWN_ISSUES.md #1）。
"""

from __future__ import annotations

from typing import Any, Callable

import requests

from snaptranslate.infrastructure.network.proxy_policy import ProxyPolicy

Timeout = float | tuple[float, float]


def _new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def get(
    url: str,
    *,
    timeout: Timeout,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    policy: ProxyPolicy | None = None,
    session_factory: Callable[[], requests.Session] | None = None,
) -> requests.Response:
    """GET 一个 URL；``policy`` 决定是否走代理，代理失败自动回退直连。"""
    proxies = policy.proxies_for_url(url) if policy is not None else None
    factory = session_factory or _new_session
    session = factory()
    try:
        try:
            return session.get(url, timeout=timeout, headers=headers, params=params, proxies=proxies)
        except requests.exceptions.ProxyError:
            if not proxies:
                raise
            # 代理不可用 → 直连再试一次（proxies={} 且 trust_env=False = 真直连）
            return session.get(url, timeout=timeout, headers=headers, params=params, proxies={})
    finally:
        try:
            session.close()
        except Exception:
            pass


def probe(policy: ProxyPolicy, url: str, *, timeout: Timeout = (4, 8)) -> tuple[bool, str]:
    """代理自检：返回 ``(是否成功, 说明)``，供界面"测试代理"按钮使用。"""
    effective = policy.effective_url()
    if effective is None:
        return True, "当前未启用代理（直连）"
    proxies = policy.proxies_for_url(url)
    if proxies is None:
        return True, "该地址属于内网/回环，按策略直连"
    try:
        with _new_session() as session:
            response = session.get(url, timeout=timeout, proxies=proxies)
        return True, f"代理可用：HTTP {response.status_code}（{effective}）"
    except requests.exceptions.ProxyError as exc:
        return False, f"代理不可用：{type(exc).__name__}（{effective}）"
    except Exception as exc:
        return False, f"请求失败：{type(exc).__name__}: {str(exc)[:80]}"
