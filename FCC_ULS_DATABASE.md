# FCC ULS Amateur Radio Database — Reference Guide

This file describes the SQLite database produced by `fcc_uls_to_sqlite.py`.
Use it to look up US amateur radio callsigns, licensee names, addresses,
operator classes, and license status.

---

## Database File

Default filename: `fcc_amateur.db`  
Created by: `python3 fcc_uls_to_sqlite.py`  
Source: FCC Universal Licensing System (ULS) — `l_amat.zip`  
Updated: Weekly by the FCC. Re-run the script to refresh.

---

## Tables

### `hd` — License Header
One row per license grant. This is the authoritative record for a callsign.

| Column | Type | Notes |
|---|---|---|
| `unique_system_identifier` | INTEGER PK | FCC internal ID, joins all tables |
| `call_sign` | TEXT | e.g. `NY4I`, `W1AW` |
| `license_status` | TEXT | `A`=Active, `C`=Cancelled, `E`=Expired, `T`=Terminated |
| `radio_service_code` | TEXT | `HA`=Amateur, `HV`=Amateur Vanity |
| `grant_date` | TEXT | MM/DD/YYYY |
| `expired_date` | TEXT | MM/DD/YYYY |
| `cancellation_date` | TEXT | MM/DD/YYYY |
| `effective_date` | TEXT | MM/DD/YYYY |
| `last_action_date` | TEXT | MM/DD/YYYY |

### `en` — Entity (Licensee)
Name, address, and contact info for the license holder.

| Column | Type | Notes |
|---|---|---|
| `unique_system_identifier` | INTEGER | Joins to `hd` and `am` |
| `call_sign` | TEXT | |
| `entity_type` | TEXT | `L`=Licensee, `A`=Applicant |
| `entity_name` | TEXT | Full name for clubs/organizations |
| `first_name` | TEXT | Individual first name |
| `mi` | TEXT | Middle initial |
| `last_name` | TEXT | Individual last name |
| `street_address` | TEXT | |
| `city` | TEXT | |
| `state` | TEXT | 2-letter state code, e.g. `GA`, `FL` |
| `zip_code` | TEXT | |
| `email` | TEXT | May be empty |
| `phone` | TEXT | 10-digit, no formatting |
| `frn` | TEXT | FCC Registration Number |
| `applicant_type_code` | TEXT | `I`=Individual, `B`=Amateur Club, `M`=Military, `G`=Government |

### `am` — Amateur-Specific Record
Ham radio specific fields for each license.

| Column | Type | Notes |
|---|---|---|
| `unique_system_identifier` | INTEGER | Joins to `hd` and `en` |
| `call_sign` | TEXT | |
| `operator_class` | TEXT | `T`=Technician, `G`=General, `E`=Amateur Extra, `A`=Advanced, `N`=Novice |
| `group_code` | TEXT | Callsign group: `A`=Extra, `B`=Advanced, `C`=General, `D`=Technician |
| `region_code` | INTEGER | ITU region |
| `trustee_call_sign` | TEXT | Club trustee's callsign (if club license) |
| `trustee_name` | TEXT | Club trustee's name |
| `previous_call_sign` | TEXT | Prior callsign if changed |
| `previous_operator_class` | TEXT | Prior license class |
| `systematic_call_sign_change` | TEXT | `Y` if changed via FCC system |
| `vanity_call_sign_change` | TEXT | `Y` if vanity change |

---

## The `callsigns` View

Pre-joined view combining all three tables. **Start here for most lookups.**
Selects only `entity_type = 'L'` (the primary licensee row from `en`).

```sql
SELECT * FROM callsigns WHERE call_sign = 'NY4I';
```

Columns available in the view:

`call_sign`, `license_status`, `radio_service_code`, `grant_date`,
`expired_date`, `effective_date`, `last_action_date`, `first_name`, `mi`,
`last_name`, `entity_name`, `street_address`, `city`, `state`, `zip_code`,
`email`, `applicant_type_code`, `operator_class`, `group_code`,
`previous_call_sign`, `trustee_call_sign`, `unique_system_identifier`

---

## Common Queries

### Look up a single callsign
```sql
SELECT * FROM callsigns WHERE call_sign = 'NY4I';
```

### Look up by last name and state
```sql
SELECT call_sign, first_name, last_name, city, state, operator_class
FROM callsigns
WHERE last_name = 'SMITH'
  AND state = 'GA'
  AND license_status = 'A';
```

### Find all active licensees in a city
```sql
SELECT call_sign, first_name, last_name, operator_class
FROM callsigns
WHERE city  = 'SAINT MARYS'
  AND state = 'GA'
  AND license_status = 'A'
ORDER BY call_sign;
```

### Find by ZIP code
```sql
SELECT call_sign, first_name, last_name, operator_class
FROM callsigns
WHERE zip_code LIKE '31558%'
  AND license_status = 'A';
```

### All Extra class licensees in a state
```sql
SELECT call_sign, first_name, last_name, city
FROM callsigns
WHERE state          = 'GA'
  AND operator_class = 'E'
  AND license_status = 'A'
ORDER BY call_sign;
```

### Count licensees by operator class
```sql
SELECT operator_class, COUNT(*) AS count
FROM am
GROUP BY operator_class
ORDER BY count DESC;
```

### Count active licensees by state
```sql
SELECT e.state, COUNT(*) AS count
FROM hd h
JOIN en e ON e.unique_system_identifier = h.unique_system_identifier
WHERE h.license_status = 'A'
  AND e.entity_type    = 'L'
GROUP BY e.state
ORDER BY count DESC;
```

### Find all club licenses (with trustee info)
```sql
SELECT call_sign, entity_name, trustee_call_sign, trustee_name, city, state
FROM callsigns
WHERE applicant_type_code = 'B'
  AND license_status      = 'A'
ORDER BY call_sign;
```

### Find recently granted licenses
```sql
SELECT call_sign, first_name, last_name, grant_date, operator_class
FROM callsigns
WHERE license_status = 'A'
ORDER BY grant_date DESC
LIMIT 50;
```

### Look up a licensee by FRN
```sql
SELECT h.call_sign, e.first_name, e.last_name, e.frn
FROM en e
JOIN hd h ON h.unique_system_identifier = e.unique_system_identifier
WHERE e.frn = '0012345678';
```

### Find callsigns with a vanity change history
```sql
SELECT call_sign, previous_call_sign, operator_class
FROM am
WHERE previous_call_sign IS NOT NULL
  AND previous_call_sign != ''
ORDER BY call_sign;
```

### Full record for a call sign (raw tables, no view)
```sql
SELECT
    h.call_sign,
    h.license_status,
    h.grant_date,
    h.expired_date,
    e.first_name,
    e.last_name,
    e.street_address,
    e.city,
    e.state,
    e.zip_code,
    e.email,
    a.operator_class,
    a.group_code,
    a.previous_call_sign
FROM hd h
JOIN en e ON e.unique_system_identifier = h.unique_system_identifier
JOIN am a ON a.unique_system_identifier = h.unique_system_identifier
WHERE h.call_sign = 'NY4I';
```

---

## Key Codes Reference

### `license_status`
| Code | Meaning |
|---|---|
| `A` | Active |
| `C` | Cancelled |
| `E` | Expired |
| `T` | Terminated |

### `operator_class`
| Code | Class |
|---|---|
| `E` | Amateur Extra |
| `A` | Advanced (no longer issued) |
| `G` | General |
| `T` | Technician |
| `N` | Novice (no longer issued) |

### `group_code` (callsign prefix group)
| Code | Description |
|---|---|
| `A` | 1×2 and 2×1 format — Extra class |
| `B` | 1×3 format — Advanced class |
| `C` | 2×2 format — General class |
| `D` | 2×3 format — Technician class |

### `applicant_type_code`
| Code | Type |
|---|---|
| `I` | Individual |
| `B` | Amateur Club |
| `M` | Military Recreation |
| `R` | RACES (Civil Defense) |
| `G` | Government Entity |

### `radio_service_code`
| Code | Meaning |
|---|---|
| `HA` | Amateur |
| `HV` | Amateur Vanity (same privileges, different issuance path) |

---

## Notes

- **Encoding**: Source files are Latin-1. The import script converts to UTF-8.
- **Dates**: Stored as TEXT in MM/DD/YYYY format (FCC native format).
  For date comparisons use `strftime` or cast:
  ```sql
  WHERE substr(expired_date,7,4)||substr(expired_date,1,2)||substr(expired_date,4,2) > '20260101'
  ```
- **Trailing spaces**: Call signs are stored trimmed. Search with exact strings.
- **Case**: All text values are stored as-is from FCC (mostly uppercase).
  Use `UPPER(?)` or `COLLATE NOCASE` for case-insensitive searches:
  ```sql
  WHERE last_name = 'smith' COLLATE NOCASE
  ```
- **Multiple EN rows**: Some licenses have more than one `en` row
  (e.g., applicant + licensee). The `callsigns` view filters to `entity_type = 'L'`
  (the licensee). Query `en` directly if you need all entity rows.
- **Expired licenses**: All license records are present regardless of status.
  Add `AND license_status = 'A'` to restrict to active licenses.
- **Refresh**: Re-run `fcc_uls_to_sqlite.py` weekly to get the latest FCC data.
  The script drops and recreates the database each run.
