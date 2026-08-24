"""Windows HTTPS launcher and certificate setup integration tests."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SETUP_SCRIPT = ROOT / "scripts" / "setup_https.ps1"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher is Windows-specific")
def test_https_setup_generates_certificate_with_dns_and_ip_sans(tmp_path):
    powershell = shutil.which("powershell")
    openssl = shutil.which("openssl")
    if not powershell or not openssl:
        pytest.skip("PowerShell and OpenSSL are required for certificate integration test")

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SETUP_SCRIPT),
            "-OutputDir",
            str(tmp_path),
            "-DnsName",
            "simexai.test",
            "-IpAddress",
            "127.0.0.1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    ca_cert = tmp_path / "simexai-ca.cert.pem"
    server_cert = tmp_path / "simexai-server.cert.pem"
    server_key = tmp_path / "simexai-server.key.pem"
    assert ca_cert.is_file()
    assert server_cert.is_file()
    assert server_key.is_file()

    subprocess.run(
        [openssl, "x509", "-in", str(server_cert), "-noout", "-checkhost", "simexai.test"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [openssl, "x509", "-in", str(server_cert), "-noout", "-checkip", "127.0.0.1"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [openssl, "verify", "-CAfile", str(ca_cert), str(server_cert)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_launcher_exposes_tls_certificate_options():
    launcher = (ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "[switch]$Https" in launcher
    assert "$SslCertFile" in launcher
    assert "$SslKeyFile" in launcher
    assert '"--ssl-certfile"' in launcher
    assert '"--ssl-keyfile"' in launcher
    assert '"https://localhost:$Port"' in launcher
    assert "System.Net.Sockets.TcpClient" in launcher


def test_https_setup_resolves_default_output_after_parameter_binding():
    setup_script = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "[string]$OutputDir," in setup_script
    assert "if (-not $OutputDir)" in setup_script
    assert "Join-Path $PSScriptRoot '..\\.certs'" in setup_script
