"""Fixtures communes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.nodon_enocean.gateway import Gateway

from .fake_dongle import FakeDongle


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def dongle():
    """Remplace la connexion série par un simulateur de USB300."""
    fake = FakeDongle()

    async def _connect(self: Gateway):
        fake.attach(self)
        fake.closed = False
        return await self.connect_transport(fake)

    with (
        patch.object(Gateway, "connect", _connect),
        patch(
            "custom_components.nodon_enocean.config_flow._list_ports",
            return_value=[("/dev/ttyUSB0", "/dev/ttyUSB0 — EnOcean USB 300")],
        ),
    ):
        yield fake
