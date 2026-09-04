from core.models import ProxyType
from engine.scanner import ProbeResult, select_proxy_type


def test_select_proxy_type_uses_specific_protocol_precedence():
    probes = {
        ProxyType.HTTP_FORWARD: ProbeResult(True, 40),
        ProxyType.HTTP_CONNECT: ProbeResult(True, 30),
        ProxyType.SOCKS4: ProbeResult(False),
        ProxyType.SOCKS5: ProbeResult(False),
    }
    assert select_proxy_type(probes) == ProxyType.HTTP_CONNECT


def test_select_proxy_type_prefers_socks5_when_multiple_protocols_work():
    probes = {
        ProxyType.HTTP_FORWARD: ProbeResult(True),
        ProxyType.HTTP_CONNECT: ProbeResult(True),
        ProxyType.SOCKS4: ProbeResult(True),
        ProxyType.SOCKS5: ProbeResult(True),
    }
    assert select_proxy_type(probes) == ProxyType.SOCKS5


def test_select_proxy_type_returns_none_when_all_probes_fail():
    assert select_proxy_type({}) is None
