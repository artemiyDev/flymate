# bot/i18n.py
"""Internationalization support using Fluent."""

from pathlib import Path
from typing import Optional
from contextvars import ContextVar

from fluent.runtime import FluentLocalization, FluentResourceLoader

# Path to locales directory
LOCALES_DIR = Path(__file__).parent / "locales"

# Supported locales
SUPPORTED_LOCALES = ["ru", "en"]
DEFAULT_LOCALE = "ru"

# Context variable to store current locale
current_locale: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)


class FluentI18n:
    """Fluent-based i18n handler."""

    def __init__(self, locales_dir: Path, locales: list[str], default_locale: str):
        self.locales_dir = locales_dir
        self.supported_locales = locales
        self.default_locale = default_locale
        self.loader = FluentResourceLoader(str(locales_dir / "{locale}"))

        # Pre-load all localizations
        self._localizations: dict[str, FluentLocalization] = {}
        for locale in locales:
            self._localizations[locale] = self._create_localization(locale)

    def _create_localization(self, locale: str) -> FluentLocalization:
        """Create FluentLocalization for given locale."""
        return FluentLocalization(
            [locale],
            ["common.ftl", "subscriptions.ftl", "notifications.ftl"],
            self.loader
        )

    def get_localization(self, locale: Optional[str] = None) -> FluentLocalization:
        """Get FluentLocalization for given or current locale."""
        if locale is None:
            locale = current_locale.get()

        # Fallback to default if locale not supported
        if locale not in self.supported_locales:
            locale = self.default_locale

        return self._localizations[locale]

    def format(self, message_id: str, args: Optional[dict] = None, locale: Optional[str] = None) -> str:
        """
        Format message with given args.

        Args:
            message_id: Fluent message ID (e.g., "start-welcome")
            args: Arguments to pass to the message (e.g., {"name": "John"})
            locale: Locale to use (defaults to current context locale)

        Returns:
            Formatted string
        """
        l10n = self.get_localization(locale)

        # Format message with args
        if args:
            return l10n.format_value(message_id, args)
        else:
            return l10n.format_value(message_id)


# Global i18n instance
i18n = FluentI18n(
    locales_dir=LOCALES_DIR,
    locales=SUPPORTED_LOCALES,
    default_locale=DEFAULT_LOCALE
)


def set_locale(locale: str) -> None:
    """Set current locale in context."""
    if locale in SUPPORTED_LOCALES:
        current_locale.set(locale)
    else:
        current_locale.set(DEFAULT_LOCALE)


def get_locale() -> str:
    """Get current locale from context."""
    return current_locale.get()


def _(message_id: str, **kwargs) -> str:
    """
    Shorthand for formatting messages.

    Usage:
        _("start-welcome")
        _("flight-found-price", price=500, currency="USD")
    """
    return i18n.format(message_id, kwargs if kwargs else None)
