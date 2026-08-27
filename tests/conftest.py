"""Fixtures Assistant fixtures for integration tests."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading this custom integration."""


@pytest.fixture
def entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain="mast_flag",
        title="Mast Flag Status - Missouri",
        unique_id="US_MO",
        data={"api_key": "test-key", "country_code": "US", "state_code": "MO"},
    )
    entry.add_to_hass(hass)
    return entry
