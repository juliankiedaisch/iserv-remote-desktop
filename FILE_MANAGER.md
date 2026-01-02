# File Manager Feature

The File Manager provides users with an easy-to-use interface for uploading, downloading, and managing files in their Docker containers.

## Overview

Users can manage files in two separate spaces:
- **Private Files**: Personal storage at `/home/kasm-user` in the container
- **Public Files**: Shared storage at `/home/kasm-user/Public` accessible by all users

## Features

### Upload Files
- Click "Upload Files" button to select files from your computer
- Drag and drop files directly into the file manager
- Upload multiple files simultaneously (processed in batches of 3)
- Files maintain proper permissions for container access

### Download Files
- Click the download icon (⬇️) next to any file
- Files download directly to your local machine

### Folder Management
- Create new folders with the "New Folder" button
- Navigate folders by clicking on folder names
- Delete folders and their contents with the delete icon (🗑️)
- Use breadcrumb navigation to quickly move between folders

### Navigation
- Breadcrumb trail shows current location
- Click any breadcrumb item to jump to that location
- "Up" button moves to parent directory
- Click space name (Private/Public) to return to root

## Accessing the File Manager

1. Log in to the remote desktop application
2. Click the File Manager icon (📁) in the header
3. The icon is located between your username and the teacher/admin icons

## Security

The File Manager implements multiple security measures:

- **Path Validation**: All file operations validate paths to prevent directory traversal attacks
- **Session Authentication**: All operations require a valid authenticated session
- **Secure Filenames**: File names are sanitized to prevent injection attacks
- **Permission Management**: Files are created with appropriate UID/GID for container access
- **No Implicit Creation**: Directories must be explicitly created (prevents arbitrary directory structures)

## Technical Details

### Backend API Endpoints

All endpoints require session authentication via `X-Session-ID` header or `session_id` query parameter.

#### List Files
```
GET /api/files/list?space={private|public}&path={relative_path}
```
Returns list of files and directories in the specified location.

#### Upload File
```
POST /api/files/upload
Content-Type: multipart/form-data

Fields:
- file: The file to upload
- space: "private" or "public"
- path: Relative path within the space (must exist)
```

#### Download File
```
GET /api/files/download?space={private|public}&path={relative_path}
```
Returns the file content with appropriate headers for download.

#### Delete File/Folder
```
DELETE /api/files/delete?space={private|public}&path={relative_path}
```

#### Create Folder
```
POST /api/files/create-folder
Content-Type: application/json

Body:
{
  "space": "private|public",
  "path": "parent_path",
  "folder_name": "new_folder"
}
```

### Frontend Route

The File Manager is accessible at `/files` and is a protected route requiring authentication.

### File Storage Mapping

Files are stored on the host system and mapped to containers:

- **Private Files**: 
  - Host: `/data/{user_id}/`
  - Container: `/home/kasm-user/`

- **Public Files**:
  - Host: `/data/shared/public/`
  - Container: `/home/kasm-user/Public/`

### Configuration

Optional environment variables in `.env`:

```bash
# UID for file ownership in containers (default: 1000)
CONTAINER_USER_ID=1000

# GID for file ownership in containers (default: 1000)
CONTAINER_GROUP_ID=1000
```

## Performance Considerations

- **Parallel Uploads**: Files are uploaded in batches of 3 to balance speed and server load
- **Efficient Downloads**: Direct Blob handling without unnecessary memory copies
- **Responsive Design**: Works seamlessly on both desktop and mobile devices

## Troubleshooting

### "Upload directory does not exist"
This means you're trying to upload to a folder that doesn't exist yet. Create the folder first using the "New Folder" button.

### "Invalid path" error
This security error means the requested path is outside the allowed directory. This can happen with malformed paths or security violations.

### Upload fails for specific files
- Check the filename for special characters
- Ensure you have a valid session
- Verify the target directory exists

### Cannot see uploaded files
- Click the "Refresh" button to reload the file list
- Ensure you're in the correct space (Private vs Public)
- Check that you're in the correct folder

## Best Practices

1. **Organize with Folders**: Create a folder structure that makes sense for your workflow
2. **Use Public Space Wisely**: Remember that all users can access public files
3. **Regular Cleanup**: Delete files you no longer need to save space
4. **Check Before Upload**: Verify you're in the correct space and folder before uploading

## Integration with Remote Desktop

Files uploaded through the File Manager are immediately available in your running Docker containers:

- Private files appear in `/home/kasm-user/` in your desktop
- Public files appear in `/home/kasm-user/Public/` in your desktop

This allows you to easily transfer files between your local machine and your remote desktop environment.
