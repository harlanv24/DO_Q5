# Secure File Sharing REST API - Architecture

```mermaid
flowchart TD
    U[Client / SDK]
    A[FastAPI API]
    V[Validation]
    DB[(SQLite Metadata + Audit)]
    ID[(Idempotency Store)]
    FS[(Private File Storage)]
    SG[HMAC Signer]
    DL[Download Handler]

    subgraph Upload[Upload Flow]
      U -->|1 POST files| A
      A --> V
      V -->|2 Check filename ownership| DB
      V -->|3 Check idempotency key| ID
      ID -->|match same hash replay 201| A
      ID -->|match different hash 409| A
      V -->|4 Write/overwrite bytes| FS
      V -->|5 Upsert metadata + audit| DB
      V -->|6 Save idempotency result| ID
      A -->|201 metadata or 409 conflict| U
    end

    subgraph Sign[Sign Link Flow]
      U -->|7 POST sign by name| A
      A -->|8 Validate ttl + file ownership| DB
      A --> SG
      SG -->|9 Build token file_id exp| A
      A -->|10 Audit LINK_GENERATED| DB
      A -->|200 signed URL| U
    end

    subgraph Download[Public Download Flow]
      U -->|11 GET download token| DL
      DL -->|12 Verify signature + exp| SG
      DL -->|13 Resolve file_id| DB
      DL -->|14 Stream bytes| FS
      DL -->|200 or 401 404 410| U
    end
```

## Notes

- Customer-facing API is filename-based; internal storage and tokens use internal `file_id`.
- Idempotency protects large upload retries (`Idempotency-Key` + request hash).
- Duplicate filenames return `409` unless `X-Overwrite-If-Exists: true`.
- Overwrites update `updated_at` and create an `OVERWRITTEN` audit event.
