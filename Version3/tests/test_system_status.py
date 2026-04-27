from sensors.system_status import parse_ip_br_addr


def test_parse_ip_br_addr_extracts_eth_and_wifi_addresses():
    output = (
        "lo UNKNOWN 127.0.0.1/8 ::1/128\n"
        "eth0 UP 192.168.2.31/24 fe80::1/64\n"
        "wlan0 UP 172.20.10.5/28 fe80::2/64\n"
    )

    parsed = parse_ip_br_addr(output)

    assert parsed["eth0_ip"] == "192.168.2.31"
    assert parsed["wlan0_ip"] == "172.20.10.5"
