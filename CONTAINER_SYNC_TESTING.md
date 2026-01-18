# Container Sync Testing Plan

## Test Overview

This document outlines the testing procedures for the IServ Container Sync mechanism.

## Prerequisites

1. Built Docker images with the sync scripts
2. Running backend with docker_manager.py
3. Test user account
4. Access to container logs

## Test Cases

### Test 1: Basic Sync Verification

**Objective**: Verify sync starts and runs

**Steps**:
1. Start a container for a test user
2. Check container logs for sync initialization:
   ```bash
   docker logs <container_id> | grep "IServ Profile Sync"
   ```
3. Verify sync process is running:
   ```bash
   docker exec <container_id> ps aux | grep iserv_profile_sync
   ```
4. Check PID file exists:
   ```bash
   docker exec <container_id> cat /tmp/.iserv_profile_sync.pid
   ```

**Expected Results**:
- Log shows "IServ Profile Sync started"
- Process is running
- PID file exists

### Test 2: Hidden Files Sync (Config)

**Objective**: Verify hidden files sync to config directory

**Steps**:
1. Start container
2. Create a test config file inside container:
   ```bash
   docker exec <container_id> bash -c "echo 'test=1' > /home/kasm-user/.testconfig"
   ```
3. Wait 35 seconds (default sync interval + buffer)
4. Check if file synced to host:
   ```bash
   ls -la /data/users/{user_id}/{desktop_type}/.testconfig
   cat /data/users/{user_id}/{desktop_type}/.testconfig
   ```

**Expected Results**:
- File exists on host in config directory
- Content matches: "test=1"

### Test 3: Visible Files Sync (Private)

**Objective**: Verify visible files sync to private directory

**Steps**:
1. Start container
2. Create a test file in Documents:
   ```bash
   docker exec <container_id> bash -c "echo 'Hello World' > /home/kasm-user/Documents/test.txt"
   ```
3. Wait 35 seconds
4. Check if file synced to host:
   ```bash
   cat /data/users/{user_id}/PRIVATE/Documents/test.txt
   ```

**Expected Results**:
- File exists on host in PRIVATE/Documents
- Content matches: "Hello World"

### Test 4: Directory Sync

**Objective**: Verify entire directories sync correctly

**Steps**:
1. Start container
2. Create a directory structure:
   ```bash
   docker exec <container_id> bash -c "mkdir -p /home/kasm-user/Documents/project && echo 'readme' > /home/kasm-user/Documents/project/README.md"
   ```
3. Wait 35 seconds
4. Check directory on host:
   ```bash
   ls -la /data/users/{user_id}/PRIVATE/Documents/project/
   cat /data/users/{user_id}/PRIVATE/Documents/project/README.md
   ```

**Expected Results**:
- Directory structure exists on host
- README.md file exists with correct content

### Test 5: Multiple Containers - Conflict Resolution

**Objective**: Verify newest file wins with multiple containers

**Steps**:
1. Start two containers for the same user (different desktop types if possible)
2. In Container 1, create a file:
   ```bash
   docker exec <container1_id> bash -c "echo 'From Container 1' > /home/kasm-user/Documents/shared.txt"
   ```
3. Wait 35 seconds for sync
4. In Container 2, modify the same file:
   ```bash
   docker exec <container2_id> bash -c "echo 'From Container 2' > /home/kasm-user/Documents/shared.txt"
   ```
5. Wait 35 seconds for sync
6. Check file on host:
   ```bash
   cat /data/users/{user_id}/PRIVATE/Documents/shared.txt
   ```

**Expected Results**:
- File contains: "From Container 2" (newer modification)

### Test 6: Shutdown Sync

**Objective**: Verify final sync on container shutdown

**Steps**:
1. Start container
2. Create a test file:
   ```bash
   docker exec <container_id> bash -c "echo 'shutdown test' > /home/kasm-user/Documents/shutdown.txt"
   ```
3. Immediately stop the container:
   ```bash
   docker stop <container_id>
   ```
4. Check container logs for final sync:
   ```bash
   docker logs <container_id> | grep "final sync"
   ```
5. Verify file on host:
   ```bash
   cat /data/users/{user_id}/PRIVATE/Documents/shutdown.txt
   ```

**Expected Results**:
- Log shows "Performing final IServ profile sync"
- Log shows "Final IServ profile sync completed"
- File exists on host with correct content

### Test 7: Config Directory Separation

**Objective**: Verify different desktop types have separate configs

**Steps**:
1. Start container with desktop type "ubuntu-desktop"
2. Modify a config:
   ```bash
   docker exec <container1_id> bash -c "echo 'ubuntu=true' > /home/kasm-user/.desktop-specific"
   ```
3. Wait 35 seconds
4. Start another container with different desktop type
5. Check the config doesn't appear in second container:
   ```bash
   docker exec <container2_id> cat /home/kasm-user/.desktop-specific
   ```
6. Verify configs are in different directories on host:
   ```bash
   ls /data/users/{user_id}/ubuntu-desktop/
   ls /data/users/{user_id}/{other-desktop-type}/
   ```

**Expected Results**:
- Config from first desktop doesn't appear in second
- Each desktop type has its own config directory on host

### Test 8: Sync Restart After Failure

**Objective**: Verify sync restarts if it crashes

**Steps**:
1. Start container
2. Find sync process PID:
   ```bash
   docker exec <container_id> cat /tmp/.iserv_profile_sync.pid
   ```
3. Kill the sync process:
   ```bash
   docker exec <container_id> kill -9 <sync_pid>
   ```
4. Wait 5 seconds (monitoring loop checks every 3 seconds)
5. Check if sync restarted:
   ```bash
   docker exec <container_id> ps aux | grep iserv_profile_sync
   docker logs <container_id> | tail -20
   ```

**Expected Results**:
- Log shows "IServ profile sync exited, restarting"
- New sync process is running

### Test 9: Performance Test

**Objective**: Verify sync doesn't cause performance issues

**Steps**:
1. Start container
2. Create many files:
   ```bash
   docker exec <container_id> bash -c "for i in {1..100}; do echo 'test' > /home/kasm-user/Documents/file\$i.txt; done"
   ```
3. Monitor sync time in logs
4. Check system resource usage:
   ```bash
   docker stats <container_id>
   ```

**Expected Results**:
- Sync completes without errors
- CPU/Memory usage remains reasonable (<10% CPU)

### Test 10: Sync Disabled

**Objective**: Verify sync can be disabled

**Steps**:
1. Modify docker_manager.py to set `ISERV_PROFILE_SYNC: '0'`
2. Start a container
3. Check sync process:
   ```bash
   docker exec <container_id> ps aux | grep iserv_profile_sync
   ```
4. Check logs:
   ```bash
   docker logs <container_id> | grep "IServ profile sync"
   ```

**Expected Results**:
- No sync process running
- Log may show "skipping sync" message

## Manual Testing Checklist

- [ ] Test 1: Basic Sync Verification
- [ ] Test 2: Hidden Files Sync (Config)
- [ ] Test 3: Visible Files Sync (Private)
- [ ] Test 4: Directory Sync
- [ ] Test 5: Multiple Containers - Conflict Resolution
- [ ] Test 6: Shutdown Sync
- [ ] Test 7: Config Directory Separation
- [ ] Test 8: Sync Restart After Failure
- [ ] Test 9: Performance Test
- [ ] Test 10: Sync Disabled

## Automated Testing

For automated testing, create a test script:

```bash
#!/bin/bash
# test_container_sync.sh

USER_ID=1
DESKTOP_TYPE="ubuntu-desktop"
USER_DATA_DIR="/data/users/${USER_ID}"

echo "Starting sync tests..."

# Test 1: Basic sync
echo "Test 1: Verifying sync process..."
# Implementation here

# Test 2: Hidden file sync
echo "Test 2: Testing hidden file sync..."
# Implementation here

# ... etc
```

## Notes

- Wait at least 35 seconds between creating files and checking sync (30s interval + 5s buffer)
- Always check both container logs and host filesystem
- Use `docker logs -f <container_id>` to watch sync in real-time
- If tests fail, check permissions on host directories (should be 1000:1000)

## Troubleshooting

If sync isn't working:

1. Check mounted directories exist:
   ```bash
   docker inspect <container_id> | grep -A 20 Mounts
   ```

2. Check permissions:
   ```bash
   ls -la /data/users/{user_id}/
   ```

3. Check sync logs in detail:
   ```bash
   docker logs <container_id> 2>&1 | grep -A 5 -B 5 sync
   ```

4. Manually trigger sync to test:
   ```bash
   docker exec <container_id> /dockerstartup/iserv_profile_sync_once.sh
   ```
