import pytest

from serve import service_environment


def test_render_origin_is_added_without_losing_custom_domain():
    source = {"RENDER_EXTERNAL_URL": "https://example.onrender.com/", "CORS_ORIGINS": "https://docs.example.org/"}
    env, port, api_port = service_environment(source)
    assert env["CORS_ORIGINS"] == "https://docs.example.org,https://example.onrender.com"
    assert port == 10000 and api_port == 8000
    assert env["HOSTNAME"] == "0.0.0.0"
    assert "PORT" not in source


@pytest.mark.parametrize("settings", [{"PORT": "8000"}, {"PORT": "0"}, {"PORT": "65536"}, {"PORT": "invalid"}])
def test_invalid_port_configuration_fails_before_starting(settings):
    with pytest.raises(ValueError):
        service_environment(settings)
