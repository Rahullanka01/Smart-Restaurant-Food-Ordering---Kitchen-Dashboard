from .branding import BRAND_NAME, BRAND_TAGLINE


def branding_context(request):
    return {
        "brand_name": BRAND_NAME,
        "brand_tagline": BRAND_TAGLINE,
    }