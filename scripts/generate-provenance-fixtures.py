"""Real cryptographic synthetic fixtures; keys remain under ignored var/. No external signing."""

from pathlib import Path
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from PIL import Image, ImageDraw
import c2pa


def generate(root):
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    issuer_key = ec.generate_private_key(ec.SECP256R1())
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MOCK URANIUM TEST ROOT - NOT OFFICIAL")])
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(issuer_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(issuer_key.public_key()), critical=False)
        .sign(issuer_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MOCK Provenance Fixture Signer")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(issuer_key, hashes.SHA256())
    )
    root_pem = root_cert.public_bytes(serialization.Encoding.PEM)
    chain = cert.public_bytes(serialization.Encoding.PEM) + root_pem
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    (root / "test-root.pem").write_bytes(root_pem)
    (root / "signer.pem").write_bytes(chain)
    (root / "leaf.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (root / "test-signing-key.pem").write_bytes(private)
    image = Image.new("RGB", (900, 500), "white")
    ImageDraw.Draw(image).text((40, 40), "MOCK / SYNTHETIC C2PA CRYPTOGRAPHIC FIXTURE", fill="black")
    image.save(root / "unsigned.jpg")
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, chain, private, None)
    with c2pa.Signer.from_info(info) as signer:
        with c2pa.Context.from_dict(
            {
                "verify": {"remote_manifest_fetch": False, "ocsp_fetch": False},
                "builder": {"thumbnail": {"enabled": False}},
            }
        ) as context:
            with c2pa.Builder(
                {
                    "claim_generator_info": [{"name": "URANIUM MOCK FIXTURES", "version": "1"}],
                    "title": "MOCK signed provenance image",
                    "format": "image/jpeg",
                    "assertions": [
                        {
                            "label": "c2pa.actions",
                            "data": {
                                "actions": [
                                    {
                                        "action": "c2pa.created",
                                        "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCreation",
                                    }
                                ]
                            },
                        }
                    ],
                },
                context,
            ) as builder:
                builder.sign_file(root / "unsigned.jpg", root / "signed.jpg", signer)
    print("Generated real signed synthetic C2PA fixture and local test trust root; no keys printed.")
    import pymupdf
    from pyhanko.sign import signers
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((50, 65), "MOCK / SYNTHETIC SIGNED PDF - NOT AN OFFICIAL CERTIFICATE")
    pdf.save(root / "unsigned.pdf")
    signer = signers.SimpleSigner.load(
        str(root / "test-signing-key.pem"),
        str(root / "leaf.pem"),
        ca_chain_files=[str(root / "test-root.pem")],
    )
    with (root / "unsigned.pdf").open("rb") as source, (root / "signed.pdf").open("wb") as target:
        signers.PdfSigner(signers.PdfSignatureMetadata(field_name="MOCK-Signature"), signer=signer).sign_pdf(
            IncrementalPdfFileWriter(source), output=target
        )
    print("Generated genuinely signed synthetic PDF; test issuer root is separate from production trust.")


if __name__ == "__main__":
    generate(Path("var/provenance-fixtures"))
