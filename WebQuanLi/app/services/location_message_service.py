def google_maps_url(latitude: float, longitude: float) -> str:
    return f"https://www.google.com/maps?q={latitude:.6f},{longitude:.6f}"


def location_message_lines(latitude: float | None, longitude: float | None) -> list[str]:
    if latitude is None or longitude is None:
        return ["Vi tri: khong co du lieu GPS"]

    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return ["Vi tri: khong co du lieu GPS"]

    return [
        f"Vi tri: {lat:.6f}, {lng:.6f}",
        f"Google Maps: {google_maps_url(lat, lng)}",
    ]
