from .royalroad import RoyalRoad_WebBook


def webbook_from_url(url: str):
    if "royalroad.com/fiction/" in url:
        return RoyalRoad_WebBook(url)
    # TODO: add patreon / other sites
    raise ValueError("Unsupported URL")
