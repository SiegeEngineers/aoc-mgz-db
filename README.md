# Age of Empires II Recorded Game Database

Store and query recorded game metadata.

## Features

- Add by file, match, series, or csv
- Tag matches
- Supplement with Voobly player data
- Detect duplicates
- Detect player perspectives of the same match
- Detect incomplete matches
- CLI and API

# Setup

- Install and configure a relational database supported by [SQLAlchemy](https://docs.sqlalchemy.org/en/latest/dialects/)
- Determine [database connection url](https://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls)
- Ensure SSH connectivity to storage host

## Environmental Variables

Avoid passing credentials and connection information while using the CLI by setting the following environmental variables:

- `MGZ_DB`: database connection url
- `MGZ_STORE_HOST`: hostname of file storage
- `MGZ_STORE_PATH`: file system path for storage

Optional:

- `VOOBLY_KEY`: voobly api key
- `VOOBLY_USERNAME`: voobly username
- `VOOBLY_PASSWORD`: voobly password

# Relationship Diagram

![Relationship Diagram](/docs/schema.png?raw=true)

# Examples

## Adding

```bash
mgzdb add file rec.20181026-164339.mgz
mgzdb add match https://www.voobly.com/match/view/18916420
mgzdb add series "NAC2Q1 GrandFinal F1Re vs BacT.zip" "Q1 Grand Final" --tournament NAC2
mgzdb add csv matchDump.csv
```

## Querying

```bash
mgzdb query file 1
mgzdb query match 1
mgzdb query series 1
mgzdb query summary
```

## Removing

```bash
mgzdb remove --file 1
mgzdb remove --match 1
mgzdb remove --series 1
```

## Tagging

```bash
mgzdb tag 1 drush
```
