# EstudaUnB Study Methods Knowledge Base

## Recommended path

Place this directory at:

```text
backend/app/knowledge/study_methods/
```

## Files

- `study_methods.json`: canonical machine-readable source for retrieval.
- `evidence_based_study_methods_rag.pdf`: human-readable and auditable source.
- `README.md`: ingestion and versioning instructions.

## Critical ingestion rule

Do not embed both the PDF and JSON in the same vector collection. They contain equivalent content and would generate duplicated chunks.

Use:

```text
Retrieval source: study_methods.json
Audit source: evidence_based_study_methods_rag.pdf
```

Create one chunk per method and attach metadata:

```json
{
  "document_id": "estudaunb-study-methods-v1",
  "schema_version": "1.0.0",
  "method_id": "retrieval_practice",
  "category": "learning_strategy",
  "evidence_level": "strong",
  "source_file": "study_methods.json"
}
```

Use an idempotent upsert key:

```text
document_id + method_id + schema_version
```

## Checksums

- `evidence_based_study_methods_rag.pdf`: `3066bd0d53902a5c1bdab84d689c850f9257da18a9545db5f7da4a5ff107c855`
- `study_methods.json`: `4a186d18e44ea3187d29954f66bdf388b2869db08a4db3c74423ef52f7ce977e`

## Privacy

This package contains no student data. Keep uploaded academic documents in a separate, user-isolated storage path.
