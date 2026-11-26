# Security policy

## Supported versions
Security fixes go to the latest minor release.

## Reporting a vulnerability
Please report privately through GitHub: **Security → Report a vulnerability** on this repository
(<https://github.com/Perarulalanloganathan/tabledig/security/advisories/new>). Do not open a public issue
for a vulnerability. Expect an acknowledgement within a few days.

## What matters here
tabledig opens PDFs you give it, so the realistic risks are in parsing untrusted files:
- crafted PDFs that make `pdfplumber`/`pdfminer`/`pypdfium2` (or Tesseract for OCR) crash, hang or use a lot
  of memory. Run batches on untrusted PDFs with `--workers` in a container and a time limit; the Docker
  image is meant for this.
- the MCP server reads files an assistant names. Set `TABLEDIG_MCP_ROOT` to restrict it to one folder.
- the result cache (`--cache`) stores extracted values keyed by a hash of the file; it does not execute
  anything from the cache.

tabledig does not make network calls. The optional `fallback=` hook runs a function you supply; what it
sends, and where, is up to that function.
