---
description: Build (or update) a website for a business from its details or a business.json file
argument-hint: "[path/to/business.json | business details as free text]"
---

Build a website for a business using the **shingle** skill. Load it and follow its workflow
from Step 1 (INTAKE) through Step 7 (HANDOFF). Do not skip the interview or the verify step.

Input from the user: $ARGUMENTS

How to treat the input:
- If it is a path to an existing `.json` file, read it as `business.json`.
- If it is a path to a folder containing `.shingle/manifest.json`, this is an update of a site
  Shingle built: follow the skill's "Updating an existing site" section.
- If it is free text, extract the business details from it.
- If it is empty, ask the user for the business details (name, category, and any of: domain,
  address, phone, email, hours, socials) in one short message, then continue.
