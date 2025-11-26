# Bug Fixes Summary

## Overview
Fixed two critical bugs in the machine management API endpoints that manipulate the machines.yaml file.

## Bug 1: PUT Endpoint Nuking Unspecified Parameters

### Problem
When using PUT to update a machine, any parameter not specified in the request was removed from the .yaml file.

### Example of the Issue
- Machine has: `{name: "Server 1", ssh_host: "1.2.3.4", ssh_port: 22, cleanup_keep: 7}`
- User sends PUT with: `{cleanup_keep: 14}`
- BEFORE FIX: Machine becomes `{cleanup_keep: 14}` (WRONG - nukes other fields)
- AFTER FIX: Machine becomes `{name: "Server 1", ssh_host: "1.2.3.4", ssh_port: 22, cleanup_keep: 14}` (RIGHT - preserves other fields)

### Fix Applied
**File:** `/home/rambo/code/backup-api/utils/config.py`

**Method:** `update_machine()` (lines 132-163)

**Change:** Modified the update logic to merge the incoming data into the existing machine configuration instead of replacing it entirely.

```python
# BEFORE (line 146):
machines[i] = machine_data  # This replaced the entire machine

# AFTER (line 150):
machines[i].update(machine_data)  # This merges updates, preserving existing fields
machines[i]['id'] = machine_id  # Ensures ID is never changed
```

## Bug 2: DELETE Endpoint Removing Comments

### Problem
When using DELETE to remove a machine entry, it also removed any comments the user left in the YAML file.

### Example of the Issue
- machines.yaml contains comments like `# Production server` and `# Important: Do not delete`
- User deletes a machine entry
- BEFORE FIX: All comments in the file were lost
- AFTER FIX: All comments are preserved, only the specified machine entry is removed

### Fix Applied
**File:** `/home/rambo/code/backup-api/utils/config.py`

**Change:** Replaced PyYAML with ruamel.yaml, which preserves comments, formatting, and whitespace when reading and writing YAML files.

**Lines Modified:**
- Lines 1-13: Replaced `import yaml` with `from ruamel.yaml import YAML` and initialized YAML instance
- Line 44: Changed `yaml.safe_load(f)` to `yaml.load(f)`
- Line 61: Changed `yaml.dump(config, f, default_flow_style=False, sort_keys=False)` to `yaml.dump(config, f)`

**Additional File:** `/home/rambo/code/backup-api/requirements.txt`
- Added `ruamel.yaml==0.18.16` to dependencies

## Testing

### Test Script Created
Created comprehensive test script at `/home/rambo/code/backup-api/test_fixes.py` that verifies:

1. PUT endpoint preserves all unspecified fields
2. DELETE endpoint preserves YAML comments
3. Both operations work correctly with the underlying YAML file

### Test Results
All tests passed successfully:

**PUT Test Results:**
- Name preserved: True
- Host preserved: True
- SSH port preserved: True
- Backup type preserved: True
- cleanup_keep updated: True

**DELETE Test Results:**
- Top comment preserved: True
- Second comment preserved: True
- Deleted machine removed: True
- Other machines still exist: True

## Files Modified

1. `/home/rambo/code/backup-api/utils/config.py` - Core fix for both bugs
2. `/home/rambo/code/backup-api/requirements.txt` - Added ruamel.yaml dependency

## Files Created

1. `/home/rambo/code/backup-api/test_fixes.py` - Standalone test script
2. `/home/rambo/code/backup-api/test_api_endpoints.py` - HTTP integration test script
3. `/home/rambo/code/backup-api/BUG_FIXES_SUMMARY.md` - This summary document

## Dependencies Added

- `ruamel.yaml==0.18.16` - YAML library that preserves comments and formatting

## Backward Compatibility

Both fixes are backward compatible:
- The PUT endpoint now supports partial updates (you can send only the fields you want to change)
- The DELETE endpoint works exactly as before, but now preserves comments
- No API contract changes required
- Existing integrations will continue to work without modifications

## Recommendations

1. Update your virtual environment: `pip install -r requirements.txt`
2. Run the test script to verify: `python test_fixes.py`
3. Consider documenting the partial update capability in your API documentation
