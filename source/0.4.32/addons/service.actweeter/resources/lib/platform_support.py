"""Kodi platform identification shared by installation diagnostics."""

PLATFORM_CONDITIONS = (
    ("tvos", "System.Platform.TVOS"),
    ("android", "System.Platform.Android"),
    ("macos", "System.Platform.OSX"),
    ("windows", "System.Platform.Windows"),
    ("linux", "System.Platform.Linux"),
)

SUPPORTED_KODI_PLATFORMS = tuple(name for name, _ in PLATFORM_CONDITIONS)


def detect_platform(is_visible):
    """Map Kodi conditions to a canonical platform without implying runtime QA."""
    for name, condition in PLATFORM_CONDITIONS:
        try:
            if is_visible(condition):
                return name
        except Exception:
            continue
    return "unknown"
