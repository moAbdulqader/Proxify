from engine.scraper import ProxyScraper


def test_clean_proxy_accepts_valid_ip_and_port():
    scraper = ProxyScraper()
    assert scraper._clean_proxy("http://192.168.1.10:8080") == "192.168.1.10:8080"
    assert scraper._clean_proxy("10.0.0.1 3128") == "10.0.0.1:3128"


def test_clean_proxy_rejects_invalid_values():
    scraper = ProxyScraper()
    assert scraper._clean_proxy("999.1.1.1:8080") is None
    assert scraper._clean_proxy("10.0.0.1:0") is None
    assert scraper._clean_proxy("10.0.0.1:70000") is None
    assert scraper._clean_proxy("not-a-proxy") is None
