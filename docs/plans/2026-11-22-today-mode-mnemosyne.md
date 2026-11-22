# Today mode control and Mnemosyne phone library

Goal: put the mode control beneath the server on Today only, and prepare a trustworthy, phone-first library under Mnemosyne.

Constraints: owner-only actions, unchanged hold confirmation, no live host changes, no private source data in git. Retain backup warnings visibly. Merges and deployment remain the owner's actions.

1. Move the existing mode DOM into Today's server block; preserve it across redraws and holds. Green active segment, unchanged device status colours. Verify navigation, hold/keyboard behaviour and narrow screens.
2. Inspect the existing library implementation and approved evidence/search brief. Implement a local, stdlib SQLite source/revision/passage catalog with FTS5, explicit extraction state and transactional ingestion. Preserve original source identity and prevent incomplete imports from replacing valid collections.
3. Add Mnemosyne library search and catalog to the existing Memory section. Search first; collapsed filters, source details and healthy backup administration. Keep problems and action outcomes visible. Provide original-source references only through validated configured roots/URLs; no arbitrary filesystem requests.
4. Add meaningful regression tests for search, failed imports, source boundaries and page state. Run relevant existing checks and inspect phone/desktop screenshots; independent visual review before completion.
5. Document migration and remaining live-host acceptance. Prepare a reviewable branch; do not install, merge or delete anything on the host.

The approved SOL brief is the acceptance reference for evidence identity, exact search, extraction diagnostics and safe publication. Semantic search and live archive migration must be explicitly reported if not exercised. Phone-deployment reliability follows the Mnemosyne work; no root/passkey scope is folded into this change.
